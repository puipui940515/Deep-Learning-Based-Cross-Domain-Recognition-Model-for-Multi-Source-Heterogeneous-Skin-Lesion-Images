"""Detached sequential controller for the two explicitly approved V2 candidates."""
from __future__ import annotations
import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from training_state import atomic_json, file_sha256, run_directory, atomic_write
import v2_round2_contract as opt

PYTHON = opt.PROJECT / '.venv-skindetect/Scripts/python.exe'
TRAINER = opt.AREA / 'scripts/train_regularized.py'
ROOT = opt.RESULTS


def schedule_check():
    script = "$ErrorActionPreference='Stop'; @(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^python'} | Select-Object ProcessId,ParentProcessId,CommandLine) | ConvertTo-Json -Compress"
    result = subprocess.run(['powershell.exe', '-NoProfile', '-Command', script], capture_output=True, text=True, check=True)
    processes = json.loads(result.stdout or '[]')
    if isinstance(processes, dict):
        processes = [processes]
    conflicts = [p for p in processes if p['ProcessId'] != os.getpid() and re.search(
        r'train_regularized\.py|run_formal_seeds\.py|baseline_job\.py|gpu_acceptance\.py|run_v2_optimization\.py|run_v2_round2\.py',
        p.get('CommandLine') or '', re.I) and
        not ('run_v2_round2.py' in (p.get('CommandLine') or '') and p['ProcessId'] == os.getppid())]
    if conflicts:
        raise RuntimeError('Other training/controller process exists: ' + json.dumps(conflicts))
    sample = subprocess.run(['nvidia-smi', '--query-gpu=name,utilization.gpu,memory.used,memory.total,power.draw',
                             '--format=csv,noheader,nounits'], capture_output=True, text=True, check=True).stdout.strip()
    gpu = [x.strip() for x in sample.split(',')]
    if len(gpu) != 5 or '5070' not in gpu[0] or float(gpu[1]) > 10 or float(gpu[3])-float(gpu[2]) < 6500:
        raise RuntimeError('GPU schedule/free memory check failed: ' + sample)
    import ctypes
    class Memory(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [(k, ctypes.c_ulonglong) for k in
            ('total_physical', 'available_physical', 'total_commit', 'available_commit', 'total_virtual', 'available_virtual', 'extended')]
    memory = Memory(); memory.length = ctypes.sizeof(memory)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)) or memory.available_commit < 8*1024**3:
        raise RuntimeError('Insufficient system commit headroom or memory status unavailable')
    import shutil
    if shutil.disk_usage(ROOT).free < 10*1024**3:
        raise RuntimeError('Less than 10 GiB free output disk space')
    return dict(at=opt.now(), gpu=sample, python_processes=processes, available_commit_bytes=memory.available_commit,
                available_physical_bytes=memory.available_physical)


def command(candidate, seed, resume=False):
    value = [str(PYTHON), '-B', '-u', str(TRAINER), '--config', str(opt.CONFIG / (candidate + '.json')),
             '--seed', str(seed), '--manifest-release', str(opt.AREA / 'data/governed_18979_20261018_v1'),
             '--output-root', str(ROOT / 'runs' / candidate), '--require-cuda', '--formal']
    return value + (['--resume'] if resume else [])


def tail(path):
    if not path or not Path(path).exists():
        return ''
    with Path(path).open('rb') as stream:
        stream.seek(0, 2); stream.seek(max(0, stream.tell()-65536))
        return stream.read().decode('utf-8', 'replace')


def latest_row(directory):
    index_path = directory / 'checkpoints/index.json'
    if not index_path.exists():
        return {}, []
    index = opt.read(index_path)['generations']
    valid = {(g['file'], g['sha256']) for g in index}
    rows = []
    for path in directory.glob('metrics_*.jsonl'):
        for line in path.read_text(encoding='utf-8').splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if (row.get('checkpoint'), row.get('checkpoint_sha256')) in valid:
                rows.append(row)
    return max(rows, key=lambda row: row['epoch'], default={}), index


def monitor(state):
    rows = []
    budget = opt.budget_summary()
    try:
        gpu = subprocess.run(['nvidia-smi', '--query-gpu=timestamp,utilization.gpu,memory.used,memory.total,power.draw',
                              '--format=csv,noheader'], capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        gpu = 'N/A'
    for candidate in opt.CANDIDATES:
        for seed in (1, 2, 3):
            record = state['runs'][candidate][str(seed)]
            directory = ROOT / 'runs' / candidate / f'regularized_seed{seed}'
            latest, checkpoints = latest_row(directory)
            running = re.findall(r'Epoch\s+(\d+)/\d+', tail(record.get('stdout'))) if record['status']=='running' else []
            rows.append(dict(profile=candidate, model='V2 ImageNet · '+candidate, initialization='ImageNet', seed=seed,
                             status=record['status'], current_epoch=int(running[-1]) if running else None,
                             latest=latest, checkpoints=checkpoints, pid=record.get('pid'),
                             output_directory=str(directory), run_id=record.get('run_id')))
    updated = opt.now()
    payload = dict(observed_at=updated, source_age_seconds=0, rows=rows,
                   job=dict(job_id=state['job_id'], status=state['status'], updated_utc=updated,
                            completed_runs=sum(r['status']=='completed' for r in rows), gpu_snapshot=gpu),
                   budget={k: v for k,v in budget.items() if k not in ('events', 'active')},
                   result_directory=str(ROOT), note='畫面每 5 秒讀取；原監控約每 15 秒更新；完整 Epoch 提交後更新指標。')
    atomic_json(ROOT / 'MONITORING.json', payload)
    summary = ['# V2 第二輪最佳化執行狀態', '', '更新 UTC：'+updated,
               '狀態：'+state['status'], '授權：僅 v2in_r2_bcn50 → v2in_r2_re0，D第二輪第七節全部門檻；新增VASC保護；無候選3、無額外GPU測試。',
               f"預算：累計 {budget['used_seconds']:.2f} / 25920 秒；剩餘 {budget['remaining_seconds']:.2f} 秒；已完成實際 Epoch 區段 {budget['completed_epoch_segments']} / 180。",
               '計時：每次實際 Epoch 開始到 Train、Validation、Checkpoint 與指標 fsync 完成；初始化／停機不計。',
               '合法 Resume 只讀舊狀態，不建立時間事件；每個實際區段 UUID 只計一次。失敗區段另計其實際工作時間；重新計算的 Epoch 是新工作，恢復本身不計輪數。',
               '若控制器與 trainer 同時非正常消失且遺留未結束計時，停止要求人工核對，不歸零或猜測停機時間。',
               '每個 Epoch 前保留 max(600 秒, 2×歷來最慢完整 Epoch)；不足時安全暫停。此為保守預估，非純 GPU 核心計時。',
               '', '|候選|Seed|狀態|執行 Epoch|完整 Epoch|Loss|Robust|最佳 Robust|Train秒|評估秒|存檔秒|累計預算秒|',
               '|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for row in rows:
        m = row['latest']
        charged = sum(e.get('seconds', max(0,time.time()-e['started_unix'])) for e in budget['events']
                      if e['candidate']==row['profile'] and e['seed']==row['seed'])
        def value(key):
            return f'{m[key]:.5f}' if key in m else 'N/A'
        summary.append(f"|{row['profile']}|{row['seed']}|{row['status']}|{row['current_epoch'] or 'N/A'}|{m.get('epoch','N/A')}|{value('train_loss')}|{value('robust_selection_score')}|{value('best_score')}|{value('train_seconds')}|{value('evaluation_seconds')}|{value('checkpoint_seconds')}|{charged:.2f}|")
    summary += ['', 'GPU 快照：'+gpu, '純 GPU／獨立資料載入時間：N/A。PID 為記錄值；GPU 是瞬間快照。',
                '', '## 指紋與命令', '', 'suite.json SHA256：'+state['contract']['suite_sha256'],
                'ACCEPTANCE.json SHA256：'+state['contract']['acceptance_sha256'],
                '使用者授權與指紋：'+str(opt.CONFIG / 'AUTHORIZATION.md'),
                '環境與各組 LR：'+str(opt.CONFIG / 'PREFLIGHT.json'),
                '修改前／後來源：'+str(opt.CONFIG / 'sources_before')+' / sources_runtime',
                '', '獨立啟動：', '```powershell', f"& '{opt.AREA / 'scripts/Start-V2Round2.ps1'}'", '```',
                '同一實驗 Resume（保留全部預算；STOP 存在時須先處理停止原因）：', '```powershell',
                f"& '{opt.AREA / 'scripts/Start-V2Round2.ps1'}' -Resume", '```',
                '安全暫停：在本結果根目錄建立 STOP；目前完整 Epoch 保存後停止，不跑下一 Seed。',
                '', '## 決策', '', json.dumps(state.get('decisions', {}),ensure_ascii=False,indent=2),
                '', '## 實際各次命令／Checkpoint／狀態', '', '```json',
                json.dumps(state['runs'],ensure_ascii=False,indent=2), '```',
                '', '## 待辦／C 入口', '',
                '執行結束後由 C 讀取本目錄 state.json、decisions/*.json、runs/*/regularized_seed*/result.json、best_validation.json 與完整 metrics/checkpoints，建立新版本三 Seed 配對分析。n=2 僅為篩選；所有淘汰及錯誤保留。',
                '若 status=completed：研究佇列已結束，採納判定見 decisions；未通過時保留原基線。',
                '若 status=running/paused/failed/budget_paused：尚未完成；未完成或失敗不視為成效淘汰。',
                state.get('error','')]
    atomic_write(ROOT / 'EXPERIMENT_STATE.md', lambda handle: handle.write(('\n'.join(summary)+'\n').encode('utf-8')))


def verify_result(candidate, seed, record, require_receipt=True):
    directory = ROOT / 'runs' / candidate / f'regularized_seed{seed}'
    result = opt.read(directory / 'result.json')
    inputs = opt.read(directory / 'run_inputs.json')
    config = opt.read(opt.CONFIG / (candidate+'.json'))
    c = inputs['contract']
    if (result['status']!='completed' or result['test_used'] is not False or inputs['test_used'] is not False
            or result['experiment_id']!=candidate or result['seed']!=seed or c['seed']!=seed
            or c['experiment_id']!=candidate or c['training']!=config['training']
            or c['config_sha256']!=file_sha256(opt.CONFIG/(candidate+'.json'))
            or c['optimization']!=opt.runtime_contract(config) or result['run_id']!=c['run_id']
            or inputs['initial_optimizer_state_entries']!=0 or not 12<=result['epochs_completed']<=30
            or len(result['history'])!=result['epochs_completed']):
        raise RuntimeError('Completed run contract differs')
    baseline_inputs = opt.read(opt.BASE_RESULTS/f'regularized_seed{seed}'/'run_inputs.json')
    if (inputs['initial_classifier_sha256']!=baseline_inputs['initial_classifier_sha256']
            or inputs['selected_train_record_ids']!=baseline_inputs['selected_train_record_ids']
            or inputs['selected_validation_record_ids']!=baseline_inputs['selected_validation_record_ids']):
        raise RuntimeError('Seed head or selected train/validation members differ')
    index = opt.read(directory/'checkpoints/index.json')
    descriptor = result['last_checkpoint']
    if descriptor not in index['generations'] or file_sha256(directory/'checkpoints'/descriptor['file'])!=descriptor['sha256']:
        raise RuntimeError('Final resume checkpoint missing or corrupt')
    receipt = {name: file_sha256(directory/name) for name in ('result.json','run_inputs.json','best.pt','checkpoints/index.json')}
    if require_receipt and receipt != record.get('receipt'):
        raise RuntimeError('Previously completed result receipt differs; refusing retraining')
    if not all(len(m.get('learning_rates',[]))==len(inputs['optimizer_groups']) for m in result['history']):
        raise RuntimeError('Per-group LR history missing')
    atomic_json(directory/'best_validation.json', opt.best_metrics(result))
    return result, receipt


def run_seed(state, candidate, seed):
    record = state['runs'][candidate][str(seed)]
    if record['status']=='completed':
        return verify_result(candidate,seed,record)[0]
    if (ROOT/'STOP').exists() or (ROOT/'BUDGET_PAUSE.json').exists():
        return None
    budget = opt.budget_summary()
    observed = [e['seconds'] for e in budget['events'] if e.get('committed')]
    min_estimate = 12*max(120.0, (sum(observed)/len(observed)*1.2) if observed else 120.0) + 600
    if record['status']=='pending' and budget['remaining_seconds'] < min_estimate:
        atomic_json(ROOT/'BUDGET_PAUSE.json',dict(at=opt.now(),reason='insufficient_minimum_run_reserve',required_seconds=min_estimate,remaining_seconds=budget['remaining_seconds']))
        return None
    opt.gate()
    schedule = schedule_check()
    atomic_json(ROOT/f'schedule_{candidate}_seed{seed}_{uuid.uuid4().hex}.json',schedule)
    directory = ROOT/'runs'/candidate/f'regularized_seed{seed}'
    resume = record['status']!='pending'
    if resume and not (directory/'checkpoints/index.json').is_file():
        raise RuntimeError('Resume checkpoint missing; refusing fresh seed restart')
    if not resume and directory.exists():
        raise RuntimeError('Unexpected existing pending-seed directory')
    token = uuid.uuid4().hex
    logs=ROOT/'runs'/candidate/'logs'; logs.mkdir(parents=True,exist_ok=True)
    cmd = command(candidate,seed,resume)
    record.update(status='running', command=cmd, stdout=str(logs/(f'seed{seed}_{token}.stdout.log')),
                  stderr=str(logs/(f'seed{seed}_{token}.stderr.log')), resume=resume, started_utc=opt.now())
    record.setdefault('attempts',[]).append(dict(token=token,resume=resume,command=cmd,started_utc=record['started_utc']))
    state['active']=dict(candidate=candidate,seed=seed,token=token)
    atomic_json(ROOT/'state.json',state)
    env=os.environ.copy();env.update(PYTHONUTF8='1',PYTHONUNBUFFERED='1',SKINDETECT_OPT_TOKEN=token,SKINDETECT_OPT_VERSION=opt.VERSION,
        SKINDETECT_SUITE_STOP_FILE=str(ROOT/'STOP'),TORCH_HOME=str(opt.PROJECT/'.venv-skindetect/torch_cache'))
    with Path(record['stdout']).open('xb') as out, Path(record['stderr']).open('xb') as err:
        child=subprocess.Popen(cmd,cwd=opt.PROJECT,env=env,stdout=out,stderr=err)
        record['pid']=child.pid; state['active']['pid']=child.pid;atomic_json(ROOT/'state.json',state)
        last_monitor = 0
        while child.poll() is None:
            if time.monotonic()-last_monitor >= 15:
                try:
                    monitor(state)
                except Exception:
                    (ROOT/'STOP').touch(exist_ok=True)
                    child.wait()  # Existing trainer stops only after a durable epoch.
                    raise
                last_monitor=time.monotonic()
            try:
                child.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
        code=child.returncode
    opt.close_failed_segment(token,'controller_observed_child_exit')
    record.update(exit_code=code,ended_utc=opt.now());record['attempts'][-1].update(ended_utc=record['ended_utc'],exit_code=code)
    state['active']=None
    if code:
        record['status']='failed';atomic_json(ROOT/'state.json',state)
        raise RuntimeError(f'{candidate} Seed {seed} trainer exit {code}; see {record["stderr"]}')
    result=opt.read(directory/'result.json')
    record.update(status=result['status'],run_id=result['run_id'],epochs_completed=result['epochs_completed'],
                  checkpoint=result['last_checkpoint'],stop_reason=result['stop_reason'])
    if result['status']=='completed':
        result,record['receipt']=verify_result(candidate,seed,record,False)
    atomic_json(ROOT/'state.json',state);monitor(state)
    return result if result['status']=='completed' else None


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--resume',action='store_true');args=parser.parse_args()
    opt.gate()
    if Path(sys.executable).resolve()!=PYTHON.resolve():
        raise RuntimeError('Use project Python')
    contract=dict(suite_sha256=file_sha256(opt.CONFIG/'suite.json'), acceptance_sha256=file_sha256(opt.CONFIG/'ACCEPTANCE.json'))
    with run_directory(ROOT,resume=True):
        state_path=ROOT/'state.json'
        if state_path.exists():
            state=opt.read(state_path)
            if state['contract']!=contract or not args.resume:
                raise RuntimeError('Existing state requires matching --resume; never overwrite')
            if state['status']=='completed':
                for candidate in opt.CANDIDATES:
                    for seed in (1,2,3):
                        record=state['runs'][candidate][str(seed)]
                        if record['status']=='completed':verify_result(candidate,seed,record)
                monitor(state);opt.finalize(state);return
        else:
            if args.resume:
                raise RuntimeError('No original state; refusing Resume as new experiment')
            state=dict(job_id=uuid.uuid4().hex,contract=contract,status='prepared',created_utc=opt.now(),decisions={},active=None,
                       runs={c:{str(s):{'status':'pending'} for s in (1,2,3)} for c in opt.CANDIDATES})
        if opt.budget_summary()['active']:
            raise RuntimeError('Orphan active timing lease; budget reconciliation required before Resume')
        try:
            state['status']='running';state.pop('error',None);atomic_json(state_path,state);monitor(state)
            opt.publish_history(state)
            for candidate in opt.CANDIDATES:
                if state['decisions'].get(candidate,{}).get('outcome') in ('rejected','screen_failed'):
                    continue
                results={}
                for seed in (1,2):
                    result=run_seed(state,candidate,seed)
                    if result is None:
                        state['status']='budget_paused' if (ROOT/'BUDGET_PAUSE.json').exists() else 'paused'
                        atomic_json(state_path,state);monitor(state);opt.publish_history(state);return
                    results[seed]=result
                baselines={s:opt.read(opt.BASE_RESULTS/f'regularized_seed{s}'/'result.json') for s in (1,2)}
                screen=opt.decide(candidate,results,baselines)
                atomic_json(ROOT/'decisions'/f'{candidate}_screen.json',screen)
                state['decisions'][candidate]={'screen_passed':screen['passed'],'outcome':'screen_passed' if screen['passed'] else 'screen_failed'}
                atomic_json(state_path,state)
                if not screen['passed']:
                    state['runs'][candidate]['3']['status']='not_run';continue
                result=run_seed(state,candidate,3)
                if result is None:
                    state['status']='budget_paused' if (ROOT/'BUDGET_PAUSE.json').exists() else 'paused'
                    atomic_json(state_path,state);monitor(state);opt.publish_history(state);return
                results[3]=result;baselines[3]=opt.read(opt.BASE_RESULTS/'regularized_seed3/result.json')
                adoption=opt.decide(candidate,results,baselines)
                atomic_json(ROOT/'decisions'/f'{candidate}_adoption.json',adoption)
                state['decisions'][candidate]['outcome']='adopted' if adoption['passed'] else 'rejected'
                atomic_json(state_path,state)
                if adoption['passed']:
                    state['selected_candidate']=candidate;break
            for records in state['runs'].values():
                for record in records.values():
                    if record['status']=='pending':record['status']='not_run'
            state.update(status='completed',ended_utc=opt.now())
            state.setdefault('selected_candidate','original_v2_imagenet_baseline')
            atomic_json(state_path,state);monitor(state)
            opt.finalize(state)
        except BaseException as error:
            state.update(status='failed',error=repr(error),updated_utc=opt.now())
            atomic_json(state_path,state);monitor(state);opt.publish_history(state);raise


if __name__=='__main__':main()
