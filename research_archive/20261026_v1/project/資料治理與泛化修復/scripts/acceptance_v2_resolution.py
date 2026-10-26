"""Bounded two-process GPU trainer Resume acceptance for both approved sizes."""
import gc
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from training_state import CheckpointStore,atomic_json,file_sha256
import v2_resolution_contract as opt
from run_v2_resolution import schedule_check

def model_sha(state):
    h=hashlib.sha256()
    for key,value in sorted(state.items()):h.update(key.encode());h.update(value.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()

def main():
    opt.gate(True,False)
    if (opt.CONFIG/'GPU_ACCEPTANCE.json').exists():raise RuntimeError('GPU acceptance already exists; do not repeat')
    report={};evidence={}
    env=dict(os.environ,PYTHONUTF8='1',PYTHONUNBUFFERED='1',PYTHONDONTWRITEBYTECODE='1',SKINDETECT_RES_ACCEPTANCE_TOKEN=opt.suite()['acceptance_nonce'])
    trainer=opt.AREA/'scripts/train_regularized.py'
    for candidate in opt.CANDIDATES:
        receipt=opt.CONFIG/f'GPU_RECEIPT_{candidate}.json'
        if receipt.exists():
            saved=opt.read(receipt);report[candidate]=saved
            for p,h in saved['evidence_hashes'].items():
                if file_sha256(p)!=h:raise RuntimeError('Existing accepted evidence changed')
            evidence.update(saved['evidence_hashes']);continue
        atomic_json(opt.CONFIG/'GPU_ACCEPTANCE_STATE.json',dict(active_candidate=candidate,status='running',at=opt.now()))
        root=opt.CONFIG/'gpu_acceptance'/candidate;directory=root/'regularized_seed1'
        command=[sys.executable,'-B','-u',str(trainer),'--config',str(opt.CONFIG/(candidate+'.json')),'--seed','1',
                 '--manifest-release',str(opt.AREA/'data/governed_18979_20261018_v1'),'--output-root',str(root),'--require-cuda',
                 '--epochs','2','--min-epochs','1','--no-early-stopping','--max-train-samples','128','--max-val-samples-per-source','7','--stop-after-epoch','1']
        def launch(resume):
            schedule=schedule_check()
            atomic_json(opt.CONFIG/f'GPU_SCHEDULE_{candidate}_{"resume" if resume else "start"}.json',schedule)
            label='resume' if resume else 'start'
            print(candidate+': independent GPU process '+label,flush=True)
            path=opt.CONFIG/f'{candidate}_{label}.log'
            if path.exists():raise RuntimeError('Existing attempt log; inspect before retry, never repeat silently')
            with path.open('xb') as f:
                child=subprocess.Popen(command+(['--resume'] if resume else []),env=env,cwd=opt.PROJECT,stdout=f,stderr=subprocess.STDOUT)
                try:code=child.wait(timeout=480)
                except subprocess.TimeoutExpired:
                    subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],capture_output=True)
                    raise RuntimeError('GPU acceptance exceeded bounded time; own process tree stopped')
            if code:raise RuntimeError('GPU acceptance trainer failed: '+str(path))
        if not directory.exists():launch(False)
        if not (directory/'result.json').exists() or not (directory/'checkpoints/index.json').exists():
            raise RuntimeError('Incomplete GPU smoke; no fresh restart allowed')
        r=opt.read(directory/'result.json')
        if r['epochs_completed']==1:launch(True)
        import torch
        inputs=opt.read(directory/'run_inputs.json');contract=inputs['contract']
        store=CheckpointStore(directory);after=store.load(contract)
        if len(store.index['generations'])!=2:raise RuntimeError('Previous complete checkpoint not retained')
        prev=store.index['generations'][1];prevpath=store.directory/prev['file']
        if file_sha256(prevpath)!=prev['sha256']:raise RuntimeError('Previous checkpoint SHA differs')
        before=torch.load(prevpath,map_location='cpu',weights_only=False)
        result=opt.read(directory/'result.json')
        def steps(state):return sorted({int(v['step'].item()) for v in state['optimizer']['state'].values()})
        assert before['epoch']==1 and before['stop_reason'] is None
        assert after['epoch']==2 and after['stop_reason']=='max_epochs' and result['status']=='completed'
        assert before['run_id']==after['run_id']==result['run_id']==contract['run_id']
        assert before['contract']==after['contract']==contract and contract['optimization']['smoke_only']
        assert before['scheduler']['last_epoch']==1 and after['scheduler']['last_epoch']==2
        assert min(steps(before))>0 and min(steps(after))>max(steps(before))
        assert model_sha(before['model'])!=model_sha(after['model'])
        assert before['scaler'] and after['scaler']
        assert before['rng']['torch_cuda'] and after['rng']['torch_cuda']
        assert model_sha({'s':before['sampler_generator_state']})!=model_sha({'s':after['sampler_generator_state']})
        assert set(after['loader_generator_states'])=={'train','monitor','HAM10000','BCN20000','PAD-UFES-20'}
        attempts=[opt.read(p) for p in directory.glob('attempt_*.json')]
        assert len(attempts)==2 and any(a['resume'] and a['start_epoch']==1 for a in attempts)
        assert len(before['history'])==1 and len(after['history'])==2
        assert after['best_score']>=before['best_score'] and 1<=after['best_record']['epoch']<=2
        durable=[json.loads(line) for p in directory.glob('metrics_*.jsonl') for line in p.read_text(encoding='utf-8').splitlines()]
        assert sorted(x['epoch'] for x in durable)==[1,2] and durable[-1]['elapsed_seconds']>durable[0]['elapsed_seconds']
        assert all(x['cuda_reserved_peak_bytes']>0 for x in durable)
        for change in [dict(contract,seed=2),dict(contract,training=dict(contract['training'],image_size=224)),dict(contract,data={})]:
            try:CheckpointStore(directory).load(change)
            except RuntimeError as e:assert 'contract mismatch' in str(e)
            else:raise AssertionError('Mismatched Seed/size/Manifest not rejected')
        paths=[directory/'run_inputs.json',directory/'result.json',directory/'checkpoints/index.json',*directory.glob('attempt_*.json'),*directory.glob('metrics_*.jsonl')]
        hashes={str(p):file_sha256(p) for p in paths}
        saved=dict(passed=True,run_id=after['run_id'],start_epoch=1,resume_epoch=2,separate_processes=True,optimizer_steps_before=steps(before),optimizer_steps_after=steps(after),
                   scaler_before=before['scaler'],scaler_after=after['scaler'],resume_attempts=attempts,
                   gpu_peak_reserved=max(x['cuda_reserved_peak_bytes'] for x in durable),evidence_hashes=hashes,
                   model_optimizer_scheduler_scaler_rng_sampler_loader_state_present=True,wrong_seed_size_manifest_rejected=True,
                   same_epoch_bitwise_augmentation_replay_not_claimed=True)
        atomic_json(receipt,saved);report[candidate]=saved;evidence.update(hashes)
        del before,after;gc.collect()
        print(candidate+': PASS separate-process Epoch1→2 Resume, previous generation, identities, metrics and peak VRAM.',flush=True)
    atomic_json(opt.CONFIG/'GPU_ACCEPTANCE_STATE.json',dict(active_candidate=None,status='completed',at=opt.now()))
    atomic_json(opt.CONFIG/'GPU_ACCEPTANCE.json',dict(passed=True,kind='independent_process_gpu_trainer_resume',at=opt.now(),cases=report,
                cpu_acceptance_sha256=file_sha256(opt.CONFIG/'ACCEPTANCE.json'),evidence_hashes=evidence,test_used=False,formal_training_started=False))
    opt.gate();print('PASS: formal resolution runtime ready, six formal runs not yet started.',flush=True)

if __name__=='__main__':main()
