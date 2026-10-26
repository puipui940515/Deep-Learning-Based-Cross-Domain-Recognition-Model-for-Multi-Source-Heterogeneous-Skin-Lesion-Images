"""Serial scale screen, restored startup policy; passive runtime monitoring only."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone,timedelta
import json
import os
from pathlib import Path
import statistics
import subprocess
import time
import uuid
import v2_scale_contract as c
import run_v2_alpha025 as original
from training_state import atomic_json,file_sha256,run_directory

ROOT=c.RESULTS
original.ROOT=ROOT

def history(folder):
    rows=[]
    for p in sorted(folder.glob('metrics_*.jsonl')):
        content=p.read_text(encoding='utf-8')
        lines=content.splitlines()
        if content and not content.endswith('\n'):lines=lines[:-1]
        rows.extend(json.loads(line) for line in lines if line)
    return rows

def local(value):return datetime.fromisoformat(value).astimezone(timezone(timedelta(hours=8))).strftime('%m/%d %H:%M:%S')
def pct(value):return 'N/A' if value is None else f'{value*100:.3f}%'
def sec(value):return 'N/A' if value is None else f'{value:.2f}'
def tail(path):
    with Path(path).open('rb') as f:
        f.seek(max(0,os.fstat(f.fileno()).st_size-32768));return f.read().decode('utf-8',errors='replace')

def publish(state):
    state['updated_utc']=c.now();atomic_json(ROOT/'state.json',state)
    lines=['# ConvNeXt V2 512模型大小初篩：完整即時監控','',
        f"更新：{local(state['updated_utc'])}（臺北）；每15秒更新。總狀態：{state['status']}。",
        f"控制器PID：{state['controller_pid']}；單GPU順序Base→Large→Huge；Tiny只引用既有原512。",
        'Seed1／512／alpha.5／Train18919、Monitor1500、Val3611；完整七類、原前處理。',
        '有效Batch64，LR1e-4／AdamW／Min12 Max30 Patience5 MinDelta0 Tmax30；首次最高Robust選模。',
        '最多3新run／90完整Epoch；wall-clock上限明確為null。單Seed初篩，不自動採納／換網站。','',
        '|模型|Seed|微批×累積|Run ID|狀態|完整Epoch|最佳Epoch|最佳Robust|',
        '|---|---|---|---|---|---|---|---|']
    tiny=state['tiny_reference'];lines.append(f"|Tiny（歷史）|1|8×8|{tiny['run_id']}|completed/reference|{tiny['epochs_completed']}|{tiny['best_epoch']}|{pct(tiny['metrics']['values']['robust'])}|")
    all_history={}
    for size,r in state['runs'].items():
        folder=ROOT/'runs'/f'v2in_scale512_{size}'/'regularized_seed1'
        h=history(folder);all_history[size]=h
        if h:r.update(epochs_completed=h[-1]['epoch'],best_epoch=h[-1]['best_epoch'],best_robust=h[-1]['best_score'])
        if (folder/'run_inputs.json').exists():r['run_id']=c.read(folder/'run_inputs.json')['run_id']
        micro=r.get('micro_batch');accum=r.get('accumulation')
        lines.append(f"|{size}|1|{micro or 'N/A'}×{accum or 'N/A'}|{r.get('run_id','N/A')}|{r['status']}|{r.get('epochs_completed',0)}|{r.get('best_epoch','N/A')}|{pct(r.get('best_robust'))}|")
    for size,r in state['runs'].items():
        h=all_history[size]
        if r.get('reason'):lines+=['',f"{size}說明：{r['reason']}"]
        if not h:continue
        last=h[-1]
        steady=h[1:] if len(h)>1 else h
        epoch=statistics.median(row['epoch_seconds'] for row in steady[-3:])
        remain_min=max(0,12-last['epoch'])*epoch/3600
        remain_max=max(0,30-last['epoch'])*epoch/3600
        lines+=['',f'## {size}：最近完整輪與估時','',
            f"目前完整Epoch {last['epoch']}；最近每輪{last['epoch_seconds']/60:.2f}分；參考每輪{epoch/60:.2f}分。",
            f"若仍執行，到Min12尚約{remain_min:.2f}小時、到Max30約{remain_max:.2f}小時；Early Stopping決定實際停止點，這不是完工時間保證。",
            '只有首輪時估計含worker啟動、CUDA與首存檔成本；模型初始化另計於attempt。第二輪起優先用排除首輪的最近最多3輪中位數，不能把必要預檢吞吐當整輪時間。', '',
            '|Epoch|Loss|Robust|LR|未改善輪數|訓練秒|資料等待秒|批次處理秒|訓練張/s|Monitor秒|Validation秒|Val張/s|存檔秒|整輪秒|配置峰值GiB|保留峰值GiB|',
            '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|']
        for row in h:
            timing=row.get('batch_timing',{})
            lines.append('|'+ '|'.join(map(str,[row['epoch'],sec(row['train_loss']),pct(row['robust_selection_score']),f"{row['learning_rate']:.8f}",row['bad_epochs'],
                sec(row['train_seconds']),sec(timing.get('data_wait_including_iterator_tqdm_seconds')),sec(timing.get('batch_processing_seconds_with_existing_loss_sync')),
                sec(18919/row['train_seconds']),sec(row.get('train_monitor_seconds')),sec(row.get('validation_seconds')),sec(3611/row['validation_seconds']) if row.get('validation_seconds') else 'N/A',sec(row['checkpoint_seconds']),sec(row['epoch_seconds']),
                sec(row['cuda_allocated_peak_bytes']/2**30),sec(row['cuda_reserved_peak_bytes']/2**30)]))+'|')
        lines+=['','資料等待與批次處理已含於訓練時間，不重複相加；評估含1500 Train Monitor＋3611 Validation，未減少資料。存檔沿用完整雙代CheckpointStore與best保護。']
    active=state.get('active')
    if active:
        r=state['runs'][active['size']]
        if r.get('stderr') and Path(r['stderr']).exists():
            progress=[line for line in tail(r['stderr']).replace('\r','\n').splitlines() if line.strip()]
            if progress:lines+=['','當前日誌進度：', '', '```text',progress[-1],'```']
    sample=state.get('resource')
    if sample:
        gpu=sample['gpu'];lines+=['','## 被動資源樣本','',f"時間：{local(sample['at'])}；無執行中資源停止門檻。",'',
            '|GPU使用率|顯存已用/總MiB|空閒MiB|Commit餘裕GiB|RAM可用GiB|', '|---|---|---|---|---|',
            f"|{gpu['utilization_percent']}%|{gpu['used_mib']}/{gpu['total_mib']}|{gpu['free_mib']}|{sample['commit_headroom_gib']:.2f}|{sample['available_ram_gib']:.2f}|"]
    lines+=['','預檢證據：preflight/SELECTION.json與各micro配置收據；正式逐輪原值在runs/*/regularized_seed1/metrics_*.jsonl。',
        '模型初始化／失敗的總嘗試耗時另在attempts/；不要與其中的Epoch區段相加。正式開始後不變更微批、Workers或配方。']
    (ROOT/'MONITOR.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    # Persist the populated actual Run IDs/epochs as well as the table.
    atomic_json(ROOT/'state.json',state)

def verify(size,r):
    candidate=f'v2in_scale512_{size}';folder=ROOT/'runs'/candidate/'regularized_seed1'
    result=c.read(folder/'result.json');inp=c.read(folder/'run_inputs.json');cfg=c.read(c.CONFIG/(candidate+'.json'))
    if result['status']!='completed' or result['test_used'] or result['seed']!=1 or result['run_id']!=inp['run_id']:
        raise RuntimeError('Result identity/status mismatch')
    if result['regularization']!=cfg['training'] or inp['effective_training_config']!=cfg['training']:raise RuntimeError('Effective recipe mismatch')
    c.verify_initialization(inp)
    if inp['contract']['optimization']!=c.runtime_contract(cfg):raise RuntimeError('Gate identity changed')
    index=c.read(folder/'checkpoints/index.json')
    if result['last_checkpoint'] not in index['generations']:raise RuntimeError('Final checkpoint missing')
    for generation in index['generations']:
        if file_sha256(folder/'checkpoints'/generation['file'])!=generation['sha256']:raise RuntimeError('Checkpoint SHA mismatch')
    r.update(run_id=result['run_id'],epochs_completed=result['epochs_completed'],best_epoch=result['best']['epoch'],
             stop_reason=result['stop_reason'],metrics=c.best_metrics(result),
             receipt={name:file_sha256(folder/name) for name in ('result.json','run_inputs.json','best.pt','checkpoints/index.json')})
    return result

def run_model(state,size):
    r=state['runs'][size]
    if r['status']!='pending':return True
    if (ROOT/'STOP').exists():state['status']='paused';return False
    c.gate();schedule=original.schedule_check()
    candidate=f'v2in_scale512_{size}';folder=ROOT/'runs'/candidate/'regularized_seed1'
    if folder.exists():raise RuntimeError('Existing formal output: no overwrite/fresh retry')
    token=uuid.uuid4().hex
    command=[str(c.PYTHON),'-B','-u','-X','utf8',str(c.AREA/'scripts/train_regularized.py'),
        '--config',str(c.CONFIG/(candidate+'.json')),'--seed','1','--manifest-release',str(c.AREA/'data/governed_18979_20261018_v1'),
        '--output-root',str(ROOT/'runs'/candidate),'--require-cuda','--formal']
    r.update(status='starting',started_utc=c.now(),command=command,
             stdout=str(ROOT/'logs'/f'{size}_{token}.stdout.log'),stderr=str(ROOT/'logs'/f'{size}_{token}.stderr.log'))
    state['active']=dict(size=size,candidate=candidate,seed=1,token=token)
    attempt=dict(token=token,size=size,candidate=candidate,seed=1,command=command,schedule=schedule,resume=False,status='active',started_utc=c.now())
    attempt_path=ROOT/'attempts'/f'attempt_{token}.json';atomic_json(attempt_path,attempt);publish(state)
    env=os.environ.copy();env.update(PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',
        SKINDETECT_OPT_TOKEN=token,SKINDETECT_OPT_VERSION=c.VERSION,SKINDETECT_SUITE_STOP_FILE=str(ROOT/'STOP'))
    child=None;failure=None;started=time.perf_counter()
    try:
        with Path(r['stdout']).open('xb') as out,Path(r['stderr']).open('xb') as err:
            child=subprocess.Popen(command,cwd=c.PROJECT,env=env,stdout=out,stderr=err)
            r.update(status='running',pid=child.pid);state['active']['pid']=child.pid
            attempt['pid']=child.pid;atomic_json(attempt_path,attempt);publish(state)
            last=0
            while child.poll() is None:
                if time.monotonic()-last>=15:
                    try:
                        sample=original.memory();sample.update(size=size,pid=child.pid,gpu=original.gpu_metadata())
                        state['resource']=sample
                        with (ROOT/'resource_samples.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(sample)+'\n')
                        publish(state)
                    except Exception:
                        (ROOT/'STOP').touch(exist_ok=True);child.wait();raise
                    last=time.monotonic()
                try:child.wait(timeout=1)
                except subprocess.TimeoutExpired:pass
            attempt['exit_code']=child.returncode
            if child.returncode:failure='trainer_nonzero_exit'
    except BaseException as exc:
        failure=repr(exc)
        if child is not None:original.kill_owned_tree(child)
        (ROOT/'STOP').touch(exist_ok=True)
    finally:
        c.close_failed_segment(token,failure or 'child_exit')
        attempt.update(status='failed' if failure else 'exited',reason=failure,seconds=time.perf_counter()-started,ended_utc=c.now())
        atomic_json(attempt_path,attempt)
        r.update(ended_utc=c.now(),attempt_receipt=str(attempt_path),exit_code=attempt.get('exit_code'))
        state['active']=None
    if failure:
        (ROOT/'STOP').touch(exist_ok=True);r.update(status='failed',reason=failure);state.update(status='failed',error=failure);publish(state);return False
    observed=c.read(folder/'result.json')
    if observed['status']!='completed':
        r.update(status=observed['status'],epochs_completed=observed['epochs_completed']);state['status']='paused';publish(state);return False
    result=verify(size,r)
    r['status']=result['status'];publish(state);return True

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--status',action='store_true');parser.add_argument('--check-only',action='store_true');args=parser.parse_args()
    if args.status:
        print((ROOT/'state.json').read_text(encoding='utf-8') if (ROOT/'state.json').exists() else 'Not started');return
    c.gate()
    if Path(os.sys.executable).resolve()!=c.PYTHON.resolve():raise RuntimeError('Recovery venv required')
    if args.check_only:print(json.dumps(original.schedule_check(),indent=2));return
    if (ROOT/'state.json').exists():raise RuntimeError('Already initialized; no implicit Resume/retry')
    with run_directory(ROOT,resume=True):
        if (ROOT/'state.json').exists():raise RuntimeError('Another initializer created state')
        selection=c.read(ROOT/'preflight/SELECTION.json')
        tiny=c.read(c.TINY_RESULTS/'result.json')
        state=dict(version=c.VERSION,status='running',job_id=uuid.uuid4().hex,created_utc=c.now(),controller_pid=os.getpid(),active=None,
            gate_sha256=file_sha256(ROOT/'EXECUTION_GATE.json'),limits=c.LIMITS,
            tiny_reference=dict(run_id=tiny['run_id'],epochs_completed=tiny['epochs_completed'],best_epoch=tiny['best']['epoch'],metrics=c.best_metrics(tiny),result=str(c.TINY_RESULTS/'result.json')),
            runs={size:dict(status='pending' if selection[size]['status']=='passed' else 'skipped',seed=1,
                micro_batch=selection[size].get('micro_batch'),accumulation=selection[size].get('accumulation'),
                reason=None if selection[size]['status']=='passed' else selection[size].get('reason')) for size in c.SIZES})
        publish(state)
        try:
            for size in c.SIZES:
                if not run_model(state,size):return
            state.update(status='completed_with_skips' if any(r['status']=='skipped' for r in state['runs'].values()) else 'completed',ended_utc=c.now())
            publish(state)
            attempts=[c.read(p) for p in (ROOT/'attempts').glob('attempt_*.json')]
            atomic_json(ROOT/'FINAL_RESULTS.json',dict(version=c.VERSION,status=state['status'],rows=state['runs'],tiny_reference=state['tiny_reference'],
                formal_complete_epochs=c.budget_summary()['completed_epoch_segments'],total_formal_attempt_seconds=sum(p['seconds'] for p in attempts),
                preflight_separate=str(ROOT/'preflight'),automatic_model_adoption=False,test_used=False))
            (ROOT/'B_HANDOFF.md').write_text('本輪單Seed模型大小初篩完成／略過者另記。結果見FINAL_RESULTS、每run result/run_inputs/逐輪metrics/best.pt/雙代完整Checkpoint；耗時分項與峰值顯存已存。交總控供D分析，不自動採納／換網站或追加實驗。\n',encoding='utf-8')
        except BaseException as exc:
            state.update(status='failed',error=repr(exc));publish(state);raise

if __name__=='__main__':main()
