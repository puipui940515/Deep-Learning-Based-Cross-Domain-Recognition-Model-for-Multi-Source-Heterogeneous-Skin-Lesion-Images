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
import v2_resolution_contract as opt

PYTHON = opt.PROJECT / '.venv-skindetect/Scripts/python.exe'
TRAINER = opt.AREA / 'scripts/train_regularized.py'
ROOT = opt.RESULTS


def schedule_check():
    script = "$ErrorActionPreference='Stop'; @(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^python'} | Select-Object ProcessId,ParentProcessId,CommandLine) | ConvertTo-Json -Compress"
    result = subprocess.run(['powershell.exe', '-NoProfile', '-Command', script], capture_output=True, text=True, check=True)
    processes = json.loads(result.stdout or '[]')
    if isinstance(processes, dict):
        processes = [processes]
    conflicts = [p for p in processes if p['ProcessId'] not in (os.getpid(), os.getppid()) and re.search(
        r'train_regularized\.py|run_formal_seeds\.py|baseline_job\.py|gpu_acceptance\.py|run_v2_optimization\.py|run_v2_resolution\.py|ensemble_server\.py.*--device\s+cuda.*--enable-models',
        p.get('CommandLine') or '', re.I) and
        not ('run_v2_resolution.py' in (p.get('CommandLine') or '') and p['ProcessId'] == os.getppid())]
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
    rows=[];budget=opt.budget_summary()
    sample=subprocess.run(['nvidia-smi','--query-gpu=timestamp,utilization.gpu,memory.used,memory.total,power.draw','--format=csv,noheader'],capture_output=True,text=True,timeout=8).stdout.strip()
    for candidate in opt.CANDIDATES:
        for seed in (1,2,3):
            rec=state['runs'][candidate][str(seed)];directory=ROOT/'runs'/candidate/f'regularized_seed{seed}'
            latest,checkpoints=latest_row(directory)
            running=re.findall(r'Epoch\s+(\d+)/\d+',tail(rec.get('stdout'))) if rec['status']=='running' else []
            rows.append(dict(profile=candidate,model='ConvNeXt V2-Tiny ImageNet',resolution=opt.CANDIDATES[candidate][0],initialization='ImageNet',
                             seed=seed,status=rec['status'],current_epoch=int(running[-1]) if running else None,latest=latest,checkpoints=checkpoints,
                             pid=rec.get('pid'),output_directory=str(directory),run_id=rec.get('run_id')))
    payload=dict(observed_at=opt.now(),source_age_seconds=0,rows=rows,job=dict(job_id=state['job_id'],status=state['status'],gpu_snapshot=sample,
                 completed_runs=sum(r['status']=='completed' for r in rows)),budget={k:v for k,v in budget.items() if k not in ('events','active')},result_directory=str(ROOT),
                 note='每15秒更新；Epoch完整提交後更新指標。純GPU及資料載入耗時N/A。完整三Seed比較，不因品質取消Seed3。')
    atomic_json(ROOT/'MONITORING.json',payload)
    with (ROOT/'gpu_samples.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(dict(at=opt.now(),active=state.get('active'),gpu=sample),ensure_ascii=False)+'\n')
    lines=['# V2 320／512 三Seed正式研究即時監測','',f'更新：{opt.now()}；狀態：{state["status"]}',
           '核定320→512各Seed1/2/3，不以兩Seed分數取消第三Seed。分尺寸上限19440／42120秒，總61560秒。',
           '已用／剩餘秒：'+str(budget['used_seconds'])+'／'+str(budget['remaining_seconds']),
           '分尺寸預算：'+json.dumps(budget['by_candidate'],ensure_ascii=False),'',
           '|尺寸|Seed|狀態|執行Epoch|完整Epoch|Loss|Robust|Train秒|評估秒|存檔秒|CUDA峰值GiB|',
           '|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for row in rows:
        m=row['latest']
        def v(key):return f'{m[key]:.5f}' if key in m else 'N/A'
        peak=f"{m['cuda_reserved_peak_bytes']/1024**3:.3f}" if 'cuda_reserved_peak_bytes' in m else 'N/A'
        lines.append(f"|{row['resolution']}|{row['seed']}|{row['status']}|{row['current_epoch'] or 'N/A'}|{m.get('epoch','N/A')}|{v('train_loss')}|{v('robust_selection_score')}|{v('train_seconds')}|{v('evaluation_seconds')}|{v('checkpoint_seconds')}|{peak}|")
    lines+=['','GPU瞬間快照：'+sample,'純GPU核心／資料載入耗時：N/A。Workers=4/loader，AMP=True；保留完整Epoch與兩代Checkpoint。',
            '',f'配置、授權、來源／驗收：`{opt.CONFIG}`。','',
            f"獨立啟動：& '{opt.AREA/'scripts/Start-V2Resolution.ps1'}'",
            f"同契約Resume：& '{opt.AREA/'scripts/Start-V2Resolution.ps1'}' -Resume",
            'STOP／BUDGET_PAUSE存在時先查明停止原因，不自動刪除；缺checkpoint或契約不同立即停止。',
            'F CUDA網站GPU服務存在時不開始新Run；原始224基線／Test／Ensemble不改動。']
    (ROOT/'EXPERIMENT_STATE.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


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
    budget = opt.budget_summary(candidate=candidate)
    observed = [e['seconds'] for e in budget['events'] if e.get('committed') and e['candidate']==candidate]
    min_estimate = 12*max(390.0 if candidate=='v2in_res512' else 180.0, (sum(observed)/len(observed)*1.2) if observed else 0) + 600
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
            remaining=opt.budget_summary(candidate=candidate)['remaining_seconds']
            if remaining<15:
                (ROOT/'STOP').touch(exist_ok=True)
                subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],capture_output=True)
                child.wait();break
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
    if Path(sys.executable).resolve()!=PYTHON.resolve():raise RuntimeError('Use project Python')
    contract=dict(suite_sha256=file_sha256(opt.CONFIG/'suite.json'),acceptance_sha256=file_sha256(opt.CONFIG/'ACCEPTANCE.json'),gpu_acceptance_sha256=file_sha256(opt.CONFIG/'GPU_ACCEPTANCE.json'))
    with run_directory(ROOT,resume=True):
        state_path=ROOT/'state.json'
        if state_path.exists():
            state=opt.read(state_path)
            if state['contract']!=contract or not args.resume:raise RuntimeError('Matching --resume required; no overwrite')
            if state['status']=='completed':monitor(state);return
        else:
            if args.resume:raise RuntimeError('No existing study; Resume cannot start new seeds')
            state=dict(job_id=uuid.uuid4().hex,contract=contract,status='prepared',created_utc=opt.now(),active=None,
                       runs={c:{str(s):{'status':'pending'} for s in (1,2,3)} for c in opt.CANDIDATES})
        if opt.budget_summary()['active']:raise RuntimeError('Orphan timing lease; manual reconciliation required')
        try:
            state['status']='running';state.pop('error',None);atomic_json(state_path,state);monitor(state);opt.publish_history(state)
            # Explicitly all three seeds per resolution; no score-based gate or adoption shortcut.
            for candidate in opt.CANDIDATES:
                for seed in (1,2,3):
                    result=run_seed(state,candidate,seed)
                    if result is None:
                        state['status']='budget_paused' if (ROOT/'BUDGET_PAUSE.json').exists() else 'paused'
                        atomic_json(state_path,state);monitor(state);opt.finalize(state);return
            state.update(status='completed',ended_utc=opt.now())
            atomic_json(state_path,state);monitor(state);opt.finalize(state)
        except BaseException as error:
            state.update(status='failed',error=repr(error),updated_utc=opt.now())
            atomic_json(state_path,state);monitor(state);opt.publish_history(state);raise

if __name__=='__main__':main()
