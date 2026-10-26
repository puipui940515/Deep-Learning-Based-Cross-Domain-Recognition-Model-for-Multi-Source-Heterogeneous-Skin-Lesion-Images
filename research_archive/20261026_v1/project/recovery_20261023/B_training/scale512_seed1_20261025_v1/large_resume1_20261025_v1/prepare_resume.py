"""Prepare one authorized same-run Resume; never start a model here."""
from pathlib import Path
import ast
import json
import os
import shutil
import subprocess
import sys
import uuid

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

def main():
    if (OUT/'PERMIT.json').exists():
        print('Existing permit retained; preparation not repeated.');return
    with run_directory(ROOT,resume=True):
        if (OUT/'PERMIT.json').exists():raise RuntimeError('Another preparer already completed')
        c.gate()
        state=c.read(ROOT/'state.json');r=state['runs']['large']
        assert state['status']=='failed' and state['active'] is None
        assert r['status']=='failed' and r['run_id']==RUN_ID and r['epochs_completed']==13
        assert state['runs']['base']['status']=='completed' and state['runs']['huge']['status']=='skipped'
        assert (ROOT/'STOP').is_file() and not (RUN/'STOP').exists() and not (RUN/'result.json').exists()
        assert not c.budget_summary()['active']
        inputs=c.read(RUN/'run_inputs.json');assert inputs['run_id']==RUN_ID
        cfg=c.read(c.CONFIG/'v2in_scale512_large.json');c.validate_candidate(cfg)
        assert inputs['contract']['optimization']==c.runtime_contract(cfg)
        assert inputs['effective_training_config']==cfg['training']
        index=c.read(RUN/'checkpoints/index.json');latest=index['generations'][0]
        assert latest['epoch']==13 and latest['file']=='epoch-0013-81822a02ce1649848ae54c11b4aac6f0.pt'
        assert latest['sha256']=='32457b3e0c75c43c7874ea5cab06a83ebf9207b3730ff8393efb98f87d2d11a9'
        if file_sha256(RUN/'checkpoints'/latest['file'])!=latest['sha256']:raise RuntimeError('Latest epoch13 checksum invalid; no fallback')
        rows=old.history(RUN);assert rows[-1]['epoch']==13 and rows[-1]['bad_epochs']==2 and rows[-1]['best_epoch']==11
        schedule=old.original.schedule_check()
        driver=subprocess.run(['nvidia-smi','--query-gpu=driver_version','--format=csv,noheader'],capture_output=True,text=True,check=True,timeout=8).stdout.strip()
        checks=[]
        for name in ('resume_worker.py','run_resume.py','prepare_resume.py'):
            ast.parse((OUT/name).read_text(encoding='utf-8'));checks.append(name+': syntax passed')
        # Only the new admission boundary is executed for CPU positive/negative checks.
        import resume_worker as bridge
        from types import SimpleNamespace
        token=uuid.uuid4().hex
        permit=dict(version='large_resume1_20261025_v1',resume_authorized=True,token=token,run_id=RUN_ID,
            created_utc=c.now(),checkpoint=latest,original_contract=inputs['contract'],best_score=rows[-1]['best_score'],
            original_gate_sha256=file_sha256(ROOT/'EXECUTION_GATE.json'),original_state_sha256=file_sha256(ROOT/'state.json'),
            stop_sha256=file_sha256(ROOT/'STOP'),driver_before=None,driver_before_note='not recorded in original driver metadata',
            driver_after=driver,driver_reinstall_source='human report; not proof of unique root cause',
            trainer_arguments=r['command'][6:]+['--resume'],original_schedule=schedule,
            retry_boundary='one same-run Resume only; never fresh/fallback/automatic retry')
        assert permit['trainer_arguments'][0]=='--config'
        real_read=bridge.read
        real_token=os.environ.get('SKINDETECT_OPT_TOKEN')
        fake_active=dict(resume_revision=permit['version'],resume_run_id=RUN_ID,token=token)
        bridge.read=lambda p: permit if p.name=='PERMIT.json' else ({'active':fake_active} if p.name=='state.json' else inputs)
        os.environ['SKINDETECT_OPT_TOKEN']=token
        calls=[]
        try:
            args=SimpleNamespace(resume=True,seed=1)
            bridge.admit_resume(cfg,args,lambda cfg,a:calls.append(a.resume))
            assert calls==[False] and args.resume
            checks.append('one same-run admission only; original validator receives all unchanged arguments except explicit resume admission')
            for invalid in (SimpleNamespace(resume=False,seed=1),SimpleNamespace(resume=True,seed=2)):
                try:bridge.admit_resume(cfg,invalid,lambda *a:None)
                except RuntimeError:pass
                else:raise AssertionError('Invalid resume/seed admitted')
            fake_active['resume_run_id']='wrong'
            try:bridge.admit_resume(cfg,args,lambda *a:None)
            except RuntimeError:pass
            else:raise AssertionError('Different Run ID admitted')
            checks.append('fresh, other Seed and other Run ID rejected')
        finally:
            bridge.read=real_read
            if real_token is None:os.environ.pop('SKINDETECT_OPT_TOKEN',None)
            else:os.environ['SKINDETECT_OPT_TOKEN']=real_token
        archive=OUT/'history_before';archive.mkdir(exist_ok=False)
        # Copy small evidence and preserve large checkpoint bytes using NTFS links.
        files=[ROOT/'state.json',ROOT/'MONITOR.md',ROOT/'EXECUTION_GATE.json',ROOT/'STOP',RUN/'run_inputs.json',RUN/'checkpoints/index.json']
        files+=list((ROOT/'attempts').glob('*.json'))+list((ROOT/'budget').glob('*.json'))
        files+=list((ROOT/'logs').glob('large_789aef49399b4f5e87c7c0dda06d7620.*'))
        files+=list(RUN.glob('attempt_*.json'))+list(RUN.glob('metrics_*.jsonl'))
        for source in files:
            target=archive/source.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        links=[]
        for source in [RUN/'best.pt',*[RUN/'checkpoints'/g['file'] for g in index['generations']]]:
            target=archive/source.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
            os.link(source,target);links.append(dict(source=str(source),archive=str(target),method='NTFS hardlink; original atomic replacement/rotation cannot delete archived bytes'))
        permit['resume_sources']={str(OUT/name):file_sha256(OUT/name) for name in ('AUTHORIZATION.md','resume_worker.py','run_resume.py','prepare_resume.py')}
        atomic_json(OUT/'CPU_CHECKS.json',dict(status='passed',checks=checks,no_model_import=True,no_old_preflight_repeated=True))
        atomic_json(OUT/'HISTORY_ARCHIVE.json',dict(created_utc=c.now(),root=str(archive),large_files=links,original_failed_attempt_seconds=c.read(Path(r['attempt_receipt']))['seconds']))
        atomic_json(OUT/'PERMIT.json',permit)
        print(json.dumps(dict(status='prepared',checkpoint=latest,driver=driver,resource=schedule,token=token),ensure_ascii=False))

if __name__=='__main__':main()
