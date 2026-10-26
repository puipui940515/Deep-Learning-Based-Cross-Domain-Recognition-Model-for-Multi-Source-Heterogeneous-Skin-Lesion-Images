"""New finite three-seed controller; no wall-clock cap or automatic retries."""
from __future__ import annotations
import argparse
import ctypes
import ctypes.wintypes as w
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid
from training_state import atomic_json, file_sha256, run_directory
import v2_alpha025_contract as c

ROOT=c.RESULTS

def memory():
    class PI(ctypes.Structure):
        _fields_=[('cb',w.DWORD)]+[(k,ctypes.c_size_t) for k in (
            'CommitTotal','CommitLimit','CommitPeak','PhysicalTotal','PhysicalAvailable',
            'SystemCache','KernelTotal','KernelPaged','KernelNonpaged','PageSize')]+[(k,w.DWORD) for k in ('HandleCount','ProcessCount','ThreadCount')]
    p=PI();p.cb=ctypes.sizeof(p)
    if not ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(p),p.cb):raise ctypes.WinError()
    return dict(at=c.now(),commit_headroom_gib=(p.CommitLimit-p.CommitTotal)*p.PageSize/2**30,
                commit_limit_gib=p.CommitLimit*p.PageSize/2**30,commit_used_gib=p.CommitTotal*p.PageSize/2**30,
                available_ram_gib=p.PhysicalAvailable*p.PageSize/2**30)

def process_conflicts(own_child=None):
    script=("$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); "
            "$OutputEncoding=[Console]::OutputEncoding; "
            "$rows=@(Get-CimInstance Win32_Process -Filter \"Name LIKE 'python%'\" | "
            "Select-Object ProcessId,ParentProcessId,CommandLine); ConvertTo-Json -InputObject $rows -Compress")
    p=subprocess.run(['powershell.exe','-NoProfile','-Command',script],capture_output=True,
                     encoding='utf-8',errors='strict',timeout=15,check=True)
    rows=json.loads(p.stdout)
    if isinstance(rows,dict):rows=[rows]
    own={os.getpid(),os.getppid()}
    if own_child:
        own.add(own_child)
        for _ in rows:
            own.update(r['ProcessId'] for r in rows if r.get('ParentProcessId') in own)
    pattern=r'(train_regularized|run_formal_seeds|baseline_job|gpu_acceptance|suite_runner|run_v2_optimization|run_v2_resolution|run_v2_round2|run_v2_alpha025)\.py|ensemble_server\.py.*--device\s+cuda.*--enable-models|--formal'
    return [r for r in rows if r['ProcessId'] not in own and re.search(pattern,r.get('CommandLine') or '',re.I)]

def gpu_metadata():
    p=subprocess.run(['nvidia-smi','--query-gpu=name,utilization.gpu,memory.used,memory.total,power.draw',
                      '--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=8,check=True)
    fields=[s.strip() for s in p.stdout.strip().split(',')]
    if len(fields)!=5 or '5070' not in fields[0]:raise RuntimeError('GPU metadata/device unavailable')
    return dict(name=fields[0],utilization_percent=float(fields[1]),used_mib=float(fields[2]),
                total_mib=float(fields[3]),free_mib=float(fields[3])-float(fields[2]),power_w=float(fields[4]))

def schedule_check():
    m=memory();g=gpu_metadata();conflicts=process_conflicts()
    if conflicts:raise RuntimeError('Training/GPU service conflict: '+json.dumps(conflicts))
    if m['commit_headroom_gib']<8:raise RuntimeError('Insufficient system commit headroom')
    if g['utilization_percent']>10 or g['free_mib']<6500:raise RuntimeError('GPU startup guard failed')
    free=shutil.disk_usage(ROOT).free/2**30
    if free<10:raise RuntimeError('Output disk below10GiB')
    return dict(memory=m,gpu=g,conflicts=conflicts,free_disk_gib=free)

def command(seed,resume=False):
    args=[str(c.PYTHON),'-B','-u','-X','utf8',str(c.AREA/'scripts/train_regularized.py'),
          '--config',str(c.CONFIG/(c.CANDIDATE+'.json')),'--seed',str(seed),
          '--manifest-release',str(c.AREA/'data/governed_18979_20261018_v1'),
          '--output-root',str(ROOT/'runs'/c.CANDIDATE),'--require-cuda','--formal']
    return args+(['--resume'] if resume else [])

def publish(state):
    state['updated_utc']=c.now()
    atomic_json(ROOT/'state.json',state)
    budget=c.budget_summary()
    lines=['# V2 512 alpha025 正式訓練狀態','',f"更新：{state['updated_utc']}；status={state['status']}",
           'Seeds1→2→3；3run／最多90完整Epoch；wall_clock_cap_seconds=null（不設時間上限）。',
           'alpha=.25；512／8×8；Min12/Max30/Patience5/Tmax30；不以分數取消Seed3。','',
           '|Seed|狀態|Run ID|完整Epoch|最佳輪|','|---|---|---|---:|---:|']
    for seed,r in state['runs'].items():
        lines.append(f"|{seed}|{r['status']}|{r.get('run_id','N/A')}|{r.get('epochs_completed',0)}|{r.get('best_epoch','N/A')}|")
    lines += ['',f"完整Epoch區段：{budget['completed_epoch_segments']}/90；Epoch區段實耗：{budget['used_epoch_seconds']:.3f}秒。",
              '整次嘗試（包含初始化／失敗）耗時見attempts/*.json；與Epoch區段不重複相加。',
              '沿用舊啟動前檢查：Commit>=8GiB／顯存>=6500MiB／GPU利用率<=10%／磁碟>=10GiB及程序衝突。',
              '訓練中資源僅記錄；STOP於完整Epoch邊界處理，保留原整輪非有限值／資料契約／Checkpoint／異常退出。',
              '無自動重試、不改配方、不讀Test、不換網站；persistent workers不保證逐位元恢復。',
              '',state.get('error','')]
    (ROOT/'EXPERIMENT_STATE.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

def verify_completed(seed,record):
    folder=ROOT/'runs'/c.CANDIDATE/f'regularized_seed{seed}'
    r=c.read(folder/'result.json');inputs=c.read(folder/'run_inputs.json')
    if r['status']!='completed' or r['test_used'] is not False or inputs['contract']['training']!=c.read(c.CONFIG/(c.CANDIDATE+'.json'))['training']:
        raise RuntimeError('Result/config/test contract mismatch')
    if r['run_id']!=inputs['run_id'] or r['seed']!=seed:raise RuntimeError('Result run identity mismatch')
    c.verify_initialization(inputs)
    if inputs['contract']['optimization']!=c.runtime_contract(c.read(c.CONFIG/(c.CANDIDATE+'.json'))):
        raise RuntimeError('Result execution gate changed')
    index=c.read(folder/'checkpoints/index.json')
    if r['last_checkpoint'] not in index['generations']:raise RuntimeError('Missing final checkpoint index')
    for gen in index['generations']:
        if file_sha256(folder/'checkpoints'/gen['file'])!=gen['sha256']:raise RuntimeError('Checkpoint SHA mismatch')
    receipt={n:file_sha256(folder/n) for n in ('result.json','run_inputs.json','best.pt','checkpoints/index.json')}
    if record.get('receipt') and receipt!=record['receipt']:raise RuntimeError('Completed receipt changed; no retraining')
    record.update(receipt=receipt,run_id=r['run_id'],epochs_completed=r['epochs_completed'],best_epoch=r['best']['epoch'],stop_reason=r['stop_reason'])
    return r

def kill_owned_tree(child):
    if child.poll() is None:
        subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],capture_output=True,timeout=15)
        try:child.wait(timeout=15)
        except subprocess.TimeoutExpired:
            child.kill();child.wait(timeout=5)

def run_seed(state,seed):
    r=state['runs'][str(seed)]
    if r['status']=='completed':
        verify_completed(seed,r);return True
    if (ROOT/'STOP').exists():state['status']='paused';return False
    c.gate()
    schedule=schedule_check()
    folder=ROOT/'runs'/c.CANDIDATE/f'regularized_seed{seed}'
    resume=r['status']!='pending'
    if resume:
        if not (folder/'checkpoints/index.json').is_file():raise RuntimeError('No complete checkpoint; fresh retry forbidden')
    elif folder.exists():raise RuntimeError('Unexpected seed directory; refusing overwrite')
    token=uuid.uuid4().hex
    logs=ROOT/'logs';logs.mkdir(exist_ok=True)
    cmd=command(seed,resume)
    r.update(status='starting',command=cmd,stdout=str(logs/f'seed{seed}_{token}.stdout.log'),
             stderr=str(logs/f'seed{seed}_{token}.stderr.log'),resume=resume,started_utc=c.now())
    state['active']=dict(candidate=c.CANDIDATE,seed=seed,token=token)
    publish(state)
    attempt=dict(token=token,seed=seed,candidate=c.CANDIDATE,status='active',started_utc=c.now(),
                 started_unix=time.time(),command=cmd,schedule=schedule,resume=resume)
    attempt_path=ROOT/'attempts'/f'attempt_{token}.json'
    atomic_json(attempt_path,attempt)
    env=os.environ.copy();env.update(PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',
        SKINDETECT_OPT_TOKEN=token,SKINDETECT_OPT_VERSION=c.VERSION,SKINDETECT_SUITE_STOP_FILE=str(ROOT/'STOP'))
    started=time.perf_counter();child=None;failure=None
    try:
        with Path(r['stdout']).open('xb') as out,Path(r['stderr']).open('xb') as err:
            child=subprocess.Popen(cmd,cwd=c.PROJECT,env=env,stdout=out,stderr=err)
            r.update(status='running',pid=child.pid);state['active']['pid']=child.pid
            attempt['pid']=child.pid;atomic_json(attempt_path,attempt);publish(state)
            last_monitor=0
            while child.poll() is None:
                if time.monotonic()-last_monitor>=15:
                    try:
                        m=memory();m.update(seed=seed,pid=child.pid,gpu=gpu_metadata())
                        inputs=folder/'run_inputs.json'
                        if inputs.is_file():
                            inp=c.read(inputs);r['run_id']=inp['run_id']
                        index=folder/'checkpoints/index.json'
                        if index.is_file():r['epochs_completed']=c.read(index)['generations'][0]['epoch']
                        result=folder/'result.json'
                        if result.is_file():r['best_epoch']=c.read(result).get('best',{}).get('epoch')
                        publish(state)
                        with (ROOT/'resource_samples.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(m,ensure_ascii=False)+'\n')
                    except Exception:
                        # Match the original controller's monitor-error handling:
                        # request STOP and wait for its durable epoch boundary.
                        (ROOT/'STOP').touch(exist_ok=True)
                        child.wait()
                        raise
                    last_monitor=time.monotonic()
                try:child.wait(timeout=1)
                except subprocess.TimeoutExpired:pass
            child.wait()
            attempt['exit_code']=child.returncode
            if child.returncode and not failure:failure='trainer_nonzero_exit'
    except BaseException as exc:
        failure=repr(exc)
        if child is not None:kill_owned_tree(child)
        (ROOT/'STOP').touch(exist_ok=True)
    finally:
        c.close_failed_segment(token,failure or 'child_exit')
        attempt.update(ended_utc=c.now(),seconds=time.perf_counter()-started,
                       status='failed' if failure else 'exited',reason=failure)
        atomic_json(attempt_path,attempt)
        r.update(ended_utc=c.now(),exit_code=attempt.get('exit_code'),attempt_receipt=str(attempt_path))
        state['active']=None
        if (folder/'run_inputs.json').is_file():r['run_id']=c.read(folder/'run_inputs.json')['run_id']
    if failure:
        r['status']='failed';state.update(status='failed',error=failure);publish(state)
        return False
    result=c.read(folder/'result.json')
    r.update(status=result['status'],epochs_completed=result['epochs_completed'])
    if result['status']=='completed':verify_completed(seed,r);publish(state);return True
    state['status']='paused';publish(state);return False

def main():
    p=argparse.ArgumentParser();p.add_argument('--resume',action='store_true');p.add_argument('--status',action='store_true');p.add_argument('--check-only',action='store_true');args=p.parse_args()
    if args.status:
        print((ROOT/'state.json').read_text(encoding='utf-8') if (ROOT/'state.json').exists() else 'No formal state yet');return
    c.gate()
    if Path(sys.executable).resolve()!=c.PYTHON.resolve():raise RuntimeError('Use approved recovery venv')
    if args.check_only:
        print(json.dumps(schedule_check(),ensure_ascii=False,indent=2));return
    state_path=ROOT/'state.json'
    if state_path.exists() and c.read(state_path)['status']=='completed':raise RuntimeError('Already completed; no Resume or refresh')
    with run_directory(ROOT,resume=True):
        if state_path.exists():
            if not args.resume:raise RuntimeError('Existing state requires explicit applicable Resume; no overwrite')
            state=c.read(state_path)
            if state['gate_sha256']!=file_sha256(ROOT/'EXECUTION_GATE.json'):raise RuntimeError('Resume gate mismatch')
            if state['status']=='failed':raise RuntimeError('Abnormal failure requires review; no automatic Resume')
        else:
            if args.resume:raise RuntimeError('Resume cannot start a new study')
            state=dict(job_id=uuid.uuid4().hex,version=c.VERSION,status='running',created_utc=c.now(),
                       controller_pid=os.getpid(),gate_sha256=file_sha256(ROOT/'EXECUTION_GATE.json'),active=None,
                       execution_revision=c.EXECUTION_REVISION,
                       parent_failed_run_id=c.read(ROOT/'EXECUTION_GATE.json').get('parent_failed_run_id'),
                       limits=c.LIMITS,runs={str(s):{'status':'pending'} for s in (1,2,3)})
        if c.budget_summary()['active']:raise RuntimeError('Orphan epoch lease: review before Resume')
        state.update(status='running',controller_pid=os.getpid());publish(state)
        try:
            for seed in (1,2,3):
                if not run_seed(state,seed):return
            state.update(status='completed',ended_utc=c.now());publish(state)
            rows=[]
            for seed in (1,2,3):
                result=verify_completed(seed,state['runs'][str(seed)])
                rows.append(dict(seed=seed,**state['runs'][str(seed)],metrics=c.best_metrics(result)))
            attempts=[c.read(p) for p in (ROOT/'attempts').glob('attempt_*.json')]
            proof=c.read(ROOT/'EXECUTION_GATE.json')
            atomic_json(ROOT/'FINAL_RESULTS.json',dict(version=c.VERSION,status='completed',rows=rows,
                execution_revision=c.EXECUTION_REVISION,parent_failed_run_id=proof.get('parent_failed_run_id'),
                budget={k:v for k,v in c.budget_summary().items() if k not in ('events','active')},
                total_attempt_seconds_including_initialization_and_failures=sum(x['seconds'] for x in attempts),
                prior_failed_attempt_seconds=proof.get('parent_failed_attempt_seconds',0),
                total_attempt_seconds_including_parent_failure=sum(x['seconds'] for x in attempts)+proof.get('parent_failed_attempt_seconds',0),
                automatic_model_adoption=False,test_used=False))
            (ROOT/'C_HANDOFF.md').write_text('三Seed完成；原result/run_inputs/metrics/checkpoint及FINAL_RESULTS保留。請C依核定EVALUATION_CONTRACT整理同Seed原512差值，D判讀。B不作採納，不讀Test。\n',encoding='utf-8')
        except BaseException as exc:
            state.update(status='failed',error=repr(exc));publish(state);raise

if __name__=='__main__':main()
