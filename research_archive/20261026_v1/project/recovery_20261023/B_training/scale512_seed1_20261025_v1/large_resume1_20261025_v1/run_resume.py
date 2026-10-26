"""One authorized Large Resume controller, using unchanged original monitoring."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time

OUT=Path(__file__).resolve().parent
PROJECT=OUT.parents[3]
AREA=PROJECT/'資料治理與泛化修復'
sys.path.insert(0,str(AREA/'scripts'))
import v2_scale_contract as c
import run_v2_scale512 as old
from training_state import atomic_json,file_sha256,run_directory
ROOT=c.RESULTS
RUN=ROOT/'runs/v2in_scale512_large/regularized_seed1'
RUN_ID='7c6b140d4ed442389852be8707d8e2c6'
# Resume creates a second UUID log; filenames do not imply epoch order.
original_history=old.history
old.history=lambda folder:sorted(original_history(folder),key=lambda row:row['epoch'])

def main():
    permit=c.read(OUT/'PERMIT.json')
    if Path(sys.executable).resolve()!=c.PYTHON.resolve():raise RuntimeError('Recovery venv required')
    if (OUT/'LAUNCH_ONCE.json').exists():raise RuntimeError('Resume already consumed; no automatic second attempt')
    with run_directory(ROOT,resume=True):
        c.gate()
        for p,h in permit['resume_sources'].items():
            if file_sha256(p)!=h:raise RuntimeError('Resume bridge/authorization changed: '+p)
        if file_sha256(ROOT/'state.json')!=permit['original_state_sha256']:raise RuntimeError('Failed state changed after preparation')
        if file_sha256(ROOT/'STOP')!=permit['stop_sha256']:raise RuntimeError('STOP changed after preparation')
        if c.read(RUN/'checkpoints/index.json')['generations'][0]!=permit['checkpoint']:raise RuntimeError('Latest checkpoint changed')
        if c.budget_summary()['active']:raise RuntimeError('Existing epoch lease active')
        state=c.read(ROOT/'state.json');r=state['runs']['large']
        if state['status']!='failed' or state['active'] is not None or r['run_id']!=RUN_ID or r['status']!='failed':raise RuntimeError('Not the authorized failed Large run')
        schedule=old.original.schedule_check()
        atomic_json(OUT/'STARTUP.json',dict(at=c.now(),schedule=schedule,source='unchanged original startup policy'))
        token=permit['token'];command=[str(c.PYTHON),'-B','-u','-X','utf8',str(OUT/'resume_worker.py')]
        with (OUT/'LAUNCH_ONCE.json').open('x',encoding='utf-8') as handle:
            json.dump(dict(at=c.now(),controller_pid=os.getpid(),token=token,run_id=RUN_ID,command=command,permit_sha256=file_sha256(OUT/'PERMIT.json')),handle,indent=2)
        # The original STOP is preserved, not deleted; new STOPs retain normal meaning.
        (ROOT/'STOP').rename(OUT/'history_before/STOP.original')
        r.update(status='starting',reason=None,resume=True,resume_from_epoch=13,
            command=command,trainer_arguments=permit['trainer_arguments'],resume_started_utc=c.now(),
            stdout=str(ROOT/'logs'/f'large_resume1_{token}.stdout.log'),stderr=str(ROOT/'logs'/f'large_resume1_{token}.stderr.log'))
        state.update(status='running',controller_pid=os.getpid(),error=None,resume_revision=permit['version'],
            active=dict(size='large',candidate='v2in_scale512_large',seed=1,token=token,resume_revision=permit['version'],resume_run_id=RUN_ID))
        attempt=dict(token=token,size='large',candidate='v2in_scale512_large',seed=1,run_id=RUN_ID,
            resume=True,start_epoch=13,next_epoch=14,command=command,trainer_arguments=permit['trainer_arguments'],
            checkpoint=permit['checkpoint'],schedule=schedule,status='active',started_utc=c.now(),
            original_failed_attempt=str(OUT/'history_before/attempts/attempt_789aef49399b4f5e87c7c0dda06d7620.json'))
        attempt_path=ROOT/'attempts'/f'attempt_{token}.json'
        atomic_json(attempt_path,attempt);old.publish(state)
        env=os.environ.copy();env.update(PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',
            SKINDETECT_OPT_TOKEN=token,SKINDETECT_OPT_VERSION=c.VERSION,SKINDETECT_SUITE_STOP_FILE=str(ROOT/'STOP'))
        child=None;failure=None;started=time.perf_counter()
        try:
            with Path(r['stdout']).open('xb') as stdout,Path(r['stderr']).open('xb') as stderr:
                child=subprocess.Popen(command,cwd=PROJECT,env=env,stdout=stdout,stderr=stderr)
                r.update(status='running',pid=child.pid);state['active']['pid']=child.pid
                attempt['pid']=child.pid;atomic_json(attempt_path,attempt);old.publish(state)
                last=0
                while child.poll() is None:
                    if time.monotonic()-last>=15:
                        try:
                            sample=old.original.memory();sample.update(size='large',pid=child.pid,gpu=old.original.gpu_metadata())
                            state['resource']=sample
                            with (ROOT/'resource_samples.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(sample)+'\n')
                            old.publish(state)
                        except Exception:
                            (ROOT/'STOP').touch(exist_ok=True);child.wait();raise
                        last=time.monotonic()
                    try:child.wait(timeout=1)
                    except subprocess.TimeoutExpired:pass
                attempt['exit_code']=child.returncode
                if child.returncode:failure='trainer_nonzero_exit'
        except BaseException as error:
            failure=repr(error)
            if child is not None:old.original.kill_owned_tree(child)
            (ROOT/'STOP').touch(exist_ok=True)
        finally:
            c.close_failed_segment(token,failure or 'child_exit')
            attempt.update(status='failed' if failure else 'exited',reason=failure,seconds=time.perf_counter()-started,ended_utc=c.now())
            atomic_json(attempt_path,attempt)
            r.update(ended_utc=c.now(),attempt_receipt=str(attempt_path),exit_code=attempt.get('exit_code'))
            state['active']=None
        if failure:
            (ROOT/'STOP').touch(exist_ok=True);r.update(status='failed',reason=failure);state.update(status='failed',error=failure)
            old.publish(state);atomic_json(OUT/'CONTROLLER_RECEIPT.json',dict(status='failed',attempt=attempt));return
        observed=c.read(RUN/'result.json')
        if observed['status']!='completed':
            r.update(status=observed['status'],epochs_completed=observed['epochs_completed']);state['status']='paused'
            old.publish(state);atomic_json(OUT/'CONTROLLER_RECEIPT.json',dict(status='paused',attempt=attempt));return
        result=old.verify('large',r);r['status']=result['status']
        state.update(status='completed_with_skips',ended_utc=c.now());old.publish(state)
        attempts=[c.read(p) for p in (ROOT/'attempts').glob('attempt_*.json')]
        atomic_json(ROOT/'FINAL_RESULTS.json',dict(version=c.VERSION,status=state['status'],rows=state['runs'],tiny_reference=state['tiny_reference'],
            formal_complete_epochs=c.budget_summary()['completed_epoch_segments'],total_formal_attempt_seconds=sum(a['seconds'] for a in attempts),
            failed_attempt_seconds=sum(a['seconds'] for a in attempts if a['status']=='failed'),resume_attempt_seconds=attempt['seconds'],
            accounting_note='attempt totals include epochs; never add nested epoch/phase seconds again',
            preflight_separate=str(ROOT/'preflight'),resume_evidence=str(OUT),automatic_model_adoption=False,test_used=False))
        (ROOT/'B_HANDOFF.md').write_text('本輪Base與Large單Seed訓練完成；Huge估算略過，Tiny引用舊結果。訓練完成，尚未判定採納。Large原CUDA失敗與同Run第13輪Resume證據另存B large_resume1_20261025_v1；完整結果／來源疾病／耗時／峰值見FINAL_RESULTS與各run result、metrics、Checkpoint。失敗attempt與成功Resume分開計帳，不與所含Epoch重複相加。交總控供D判讀，不自動換網站或追加實驗。\n',encoding='utf-8')
        atomic_json(OUT/'CONTROLLER_RECEIPT.json',dict(status=state['status'],attempt=attempt,run_id=RUN_ID,epochs_completed=r['epochs_completed'],best_epoch=r['best_epoch']))

if __name__=='__main__':
    try:main()
    except BaseException as error:
        atomic_json(OUT/'CONTROLLER_ERROR.json',dict(at=c.now(),error=repr(error),pid=os.getpid()))
        if (OUT/'LAUNCH_ONCE.json').exists():
            (ROOT/'STOP').touch(exist_ok=True)
            observed=c.read(ROOT/'state.json')
            if observed.get('controller_pid')==os.getpid():
                observed.update(status='failed',error=repr(error),active=None)
                observed['runs']['large'].update(status='failed',reason=repr(error))
                old.publish(observed)
        raise
