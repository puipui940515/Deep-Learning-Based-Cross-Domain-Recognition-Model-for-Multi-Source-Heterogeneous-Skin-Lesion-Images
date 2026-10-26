"""Explicit one-run Resume admission; original frozen trainer/checkpoint/math unchanged."""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import sys
import time
import traceback

OUT=Path(__file__).resolve().parent
PROJECT=OUT.parents[3]
AREA=PROJECT/'資料治理與泛化修復'
ROOT=AREA/'results/v2_scale512_seed1_20261025_v1'
RUN=ROOT/'runs/v2in_scale512_large/regularized_seed1'
RUN_ID='7c6b140d4ed442389852be8707d8e2c6'

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))

def admit_resume(config,args,original_validate):
    # The sole compatibility exception is admission of this authorized --resume.
    # Everything else is still checked by the original unchanged gate/validator.
    permit=read(OUT/'PERMIT.json')
    active=read(ROOT/'state.json').get('active') or {}
    if (not permit['resume_authorized'] or not args.resume or args.seed!=1
            or config['experiment']['id']!='v2in_scale512_large'
            or active.get('resume_revision')!='large_resume1_20261025_v1'
            or active.get('resume_run_id')!=RUN_ID
            or active.get('token')!=permit['token']
            or os.environ.get('SKINDETECT_OPT_TOKEN')!=permit['token']
            or read(RUN/'run_inputs.json')['run_id']!=RUN_ID):
        raise RuntimeError('This one-time permit admits only Large same-run Resume')
    fresh_validation_view=copy.copy(args)
    fresh_validation_view.resume=False
    original_validate(config,fresh_validation_view)

def main():
    sys.path.insert(0,str(AREA/'scripts'))
    import v2_scale_contract as c
    from training_state import atomic_json,file_sha256
    started=time.perf_counter()
    receipt=dict(status='failed',run_id=RUN_ID,pid=os.getpid(),resume=True,start_epoch=13,next_epoch=14,
        restored_components={},source_files_unchanged=True,persistent_worker_bitwise_replay_guaranteed=False)
    permit=read(OUT/'PERMIT.json')
    try:
        for p,h in permit['resume_sources'].items():
            if file_sha256(p)!=h:raise RuntimeError('Resume bridge source/authorization changed: '+p)
        c.gate()
        assert read(RUN/'run_inputs.json')['contract']==permit['original_contract']
        import torch
        if not torch.cuda.is_available() or '5070' not in torch.cuda.get_device_name(0):raise RuntimeError('RTX5070 CUDA unavailable after driver change')
        x=torch.arange(4,dtype=torch.float32,device='cuda');y=x+x;torch.cuda.synchronize()
        assert y.cpu().tolist()==[0.,2.,4.,6.]
        receipt['cuda_minimum_check']=dict(elements=4,passed=True,device=torch.cuda.get_device_name(0),
            torch_version=torch.__version__,driver_after=permit['driver_after'],model_forward_calls=0)
        del x,y
        atomic_json(OUT/'CUDA_RECOVERY.json',receipt['cuda_minimum_check'])
        import train_regularized as trainer
        import model_profiles as profile
        original_validate=c.validate_execution
        c.validate_execution=lambda cfg,args:admit_resume(cfg,args,original_validate)
        original_load=trainer.CheckpointStore.load
        checkpoint={}
        def load_exact13(store,contract):
            if contract!=permit['original_contract']:raise RuntimeError('Resume full original contract mismatch')
            state=original_load(store,contract)
            if state is None or store.loaded_descriptor!=permit['checkpoint'] or store.loaded_descriptor['epoch']!=13:
                raise RuntimeError('Latest valid epoch13 required; no silent fallback or fresh initialization')
            if state['run_id']!=RUN_ID or state['epoch']!=13 or len(state['history'])!=13 or state['stop_reason'] is not None:
                raise RuntimeError('Checkpoint identity/history/stop state invalid')
            if state['best_record']['epoch']!=11 or state['bad_epochs']!=2 or state['best_score']!=permit['best_score']:
                raise RuntimeError('Best/EarlyStopping counter differs')
            if state['scheduler']['T_max']!=30 or state['scheduler']['last_epoch']!=13:raise RuntimeError('Scheduler reset/mismatch')
            if len(state['optimizer']['state'])!=380:raise RuntimeError('Full AdamW state missing')
            for key in ('python','numpy','torch_cpu','torch_cuda'):
                if key not in state['rng']:raise RuntimeError('RNG component missing: '+key)
            if not state['scaler'] or not state['loader_generator_states'] or state['sampler_generator_state'] is None:raise RuntimeError('AMP/sampler/loader state missing')
            checkpoint['state']=state
            receipt.update(checkpoint=store.loaded_descriptor,checksum_and_full_contract_valid=True,
                loaded_best_epoch=11,loaded_bad_epochs=2,loaded_history_epochs=13,
                loaded_current_lr=state['optimizer']['param_groups'][-1]['lr'],loaded_scaler=state['scaler'])
            atomic_json(OUT/'CHECKPOINT_LOADED.json',{k:v for k,v in receipt.items() if k!='restored_components'})
            return state
        trainer.CheckpointStore.load=load_exact13
        original_construct=profile.construct_model
        def construct_for_restore(cfg,restore=False):
            if not restore:raise RuntimeError('Resume must never load initialization backbone or create a fresh run')
            model=original_construct(cfg,restore=True)
            original_model_load=model.load_state_dict
            def restore_model(values,*args,**kwargs):
                result=original_model_load(values,*args,**kwargs)
                if result.missing_keys or result.unexpected_keys:raise RuntimeError('Strict model state restore mismatch')
                receipt['restored_components']['model']=True
                return result
            model.load_state_dict=restore_model
            return model
        profile.construct_model=construct_for_restore
        original_optimizer_factory=profile.optimizer_and_scheduler
        def optimizer_for_restore(model,cfg):
            optimizer,scheduler=original_optimizer_factory(model,cfg)
            ol,sl=optimizer.load_state_dict,scheduler.load_state_dict
            def restore_optimizer(values):
                ol(values)
                if len(optimizer.state)!=380:raise RuntimeError('AdamW state restoration incomplete')
                receipt['restored_components']['optimizer']=True
            def restore_scheduler(values):
                sl(values)
                if scheduler.last_epoch!=13 or scheduler.T_max!=30:raise RuntimeError('Cosine schedule reset')
                receipt['restored_components']['scheduler']=True
            optimizer.load_state_dict=restore_optimizer;scheduler.load_state_dict=restore_scheduler
            return optimizer,scheduler
        profile.optimizer_and_scheduler=optimizer_for_restore
        original_rng=trainer.restore_rng
        def restore_and_record_rng(values):
            original_rng(values)
            import inspect
            import random
            import numpy as np
            loc=inspect.currentframe().f_back.f_locals
            if random.getstate()!=values['python']:raise RuntimeError('Python RNG not restored')
            a,b=np.random.get_state(),values['numpy']
            if a[0]!=b[0] or not np.array_equal(a[1],b[1]) or a[2:]!=b[2:]:raise RuntimeError('NumPy RNG not restored')
            if not torch.equal(torch.get_rng_state(),values['torch_cpu'].cpu()):raise RuntimeError('CPU Torch RNG not restored')
            actual=torch.cuda.get_rng_state_all()
            if len(actual)!=len(values['torch_cuda']) or any(not torch.equal(x,y.cpu()) for x,y in zip(actual,values['torch_cuda'])):raise RuntimeError('CUDA RNG not restored')
            state=checkpoint['state']
            if not torch.equal(loc['sampler_generator'].get_state(),state['sampler_generator_state'].cpu()):raise RuntimeError('Sampler RNG not restored')
            if any(not torch.equal(g.get_state(),state['loader_generator_states'][name].cpu()) for name,g in loc['loader_generators'].items()):raise RuntimeError('Loader RNG not restored')
            if loc['scaler'].state_dict()!=state['scaler']:raise RuntimeError('AMP scaler reset')
            receipt['restored_components'].update(scaler=True,rng=True,sampler=True,loader_generators=True,
                history=True,best=True,early_stopping=True)
            receipt.update(status='resumed',all_required_state_restored=True)
            atomic_json(OUT/'RESTORED_STATE.json',receipt)
            print('AUTHORIZED_LARGE_RESUME: restored same run, epoch13 -> epoch14, best11, bad_epochs2',flush=True)
            # Do not retain another reference to the multi-GB original payload.
            checkpoint.clear()
        trainer.restore_rng=restore_and_record_rng
        sys.argv=[str(AREA/'scripts/train_regularized.py'),*permit['trainer_arguments']]
        trainer.main()
        receipt['status']=read(RUN/'result.json')['status']
    except BaseException as error:
        receipt.update(status='failed',error=repr(error),traceback=traceback.format_exc())
        c.close_failed_segment(permit['token'],'authorized_resume_exception')
        raise
    finally:
        receipt['seconds']=time.perf_counter()-started
        atomic_json(OUT/'WORKER_RECEIPT.json',receipt)

if __name__=='__main__':main()
