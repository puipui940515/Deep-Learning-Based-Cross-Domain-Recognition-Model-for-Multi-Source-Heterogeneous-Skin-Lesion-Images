"""One same-run Resume; observe restored objects without modifying their methods."""
from __future__ import annotations
import copy
import io
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

def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))

def admit_resume(config,args,original_validate):
    permit=read(OUT/'PERMIT.json');active=read(ROOT/'state.json').get('active') or {}
    if (not permit['resume_authorized'] or not args.resume or args.seed!=1
            or config['experiment']['id']!='v2in_scale512_large'
            or active.get('resume_revision')!='large_resume2_20261025_v1'
            or active.get('resume_run_id')!=RUN_ID or active.get('token')!=permit['token']
            or os.environ.get('SKINDETECT_OPT_TOKEN')!=permit['token']
            or read(RUN/'run_inputs.json')['run_id']!=RUN_ID):
        raise RuntimeError('This one-time permit admits only Large same-run Resume')
    admission_view=copy.copy(args);admission_view.resume=False
    original_validate(config,admission_view)

def observe_restored_objects(model,optimizer,scheduler,state,expected_entries=380):
    """No monkeypatch on model/optimizer/scheduler: their native state stays native."""
    import torch
    for obj in (model,optimizer,scheduler):
        if 'load_state_dict' in vars(obj) or 'state_dict' in vars(obj):
            raise RuntimeError('Unexpected instance method in restored training object')
    if set(model.state_dict())!=set(state['model']):raise RuntimeError('Restored model keys mismatch')
    if len(optimizer.state)!=expected_entries:raise RuntimeError('Incomplete optimizer state')
    actual=optimizer.state_dict()
    for current,saved in zip(actual['param_groups'],state['optimizer']['param_groups'],strict=True):
        if current!=saved:raise RuntimeError('Restored optimizer groups differ')
    if scheduler.state_dict()!=state['scheduler']:raise RuntimeError('Restored schedule differs')
    # Exercise the exact formerly broken serialization boundary before any epoch.
    target=io.BytesIO();torch.save({'scheduler':scheduler.state_dict()},target)
    return dict(model=True,optimizer=True,scheduler=True,scheduler_serialization=True,
                native_model_optimizer_scheduler_methods=True)

def main():
    sys.path.insert(0,str(AREA/'scripts'))
    import v2_scale_contract as c
    from training_state import atomic_json,file_sha256
    started=time.perf_counter();permit=read(OUT/'PERMIT.json')
    receipt=dict(status='failed',run_id=RUN_ID,pid=os.getpid(),resume=True,start_epoch=13,next_epoch=14,
        restored_components={},source_files_unchanged=True,persistent_worker_bitwise_replay_guaranteed=False)
    try:
        for path,sha in permit['resume_sources'].items():
            if file_sha256(path)!=sha:raise RuntimeError('Resume source/authorization changed: '+path)
        c.gate()
        assert read(RUN/'run_inputs.json')['contract']==permit['original_contract']
        import torch
        if not torch.cuda.is_available() or '5070' not in torch.cuda.get_device_name(0):raise RuntimeError('RTX5070 CUDA unavailable')
        receipt['cuda']=dict(device=torch.cuda.get_device_name(0),torch_version=torch.__version__,
            driver=permit['driver_after'],prior_recovery_test=permit['prior_cuda_receipt'],repeated_synthetic_test=False)
        import train_regularized as trainer
        original_validate=c.validate_execution
        c.validate_execution=lambda cfg,args:admit_resume(cfg,args,original_validate)
        original_load=trainer.CheckpointStore.load
        checkpoint={}
        def load_exact13(store,contract):
            if contract!=permit['original_contract']:raise RuntimeError('Original Resume contract mismatch')
            state=original_load(store,contract)
            if state is None or store.loaded_descriptor!=permit['checkpoint'] or state['epoch']!=13:
                raise RuntimeError('Latest valid epoch13 required; no fallback/fresh initialization')
            if state['run_id']!=RUN_ID or len(state['history'])!=13 or state['stop_reason'] is not None:
                raise RuntimeError('Checkpoint run/history/stop state invalid')
            if state['best_record']['epoch']!=11 or state['bad_epochs']!=2 or state['best_score']!=permit['best_score']:
                raise RuntimeError('Best/EarlyStopping counter mismatch')
            if state['scheduler']['T_max']!=30 or state['scheduler']['last_epoch']!=13:raise RuntimeError('Scheduler reset/mismatch')
            if len(state['optimizer']['state'])!=380:raise RuntimeError('Full AdamW state missing')
            checkpoint['state']=state
            receipt.update(checkpoint=store.loaded_descriptor,checksum_and_full_contract_valid=True,
                loaded_best_epoch=11,loaded_bad_epochs=2,loaded_history_epochs=13,
                loaded_current_lr=state['optimizer']['param_groups'][-1]['lr'],loaded_scaler=state['scaler'])
            atomic_json(OUT/'CHECKPOINT_LOADED.json',receipt)
            return state
        trainer.CheckpointStore.load=load_exact13
        original_rng=trainer.restore_rng
        def restore_and_observe_rng(values):
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
            receipt['restored_components'].update(observe_restored_objects(loc['model'],loc['optimizer'],loc['scheduler'],state))
            if loc['start_epoch']!=13 or loc['patience']!=2 or loc['best_record']['epoch']!=11 or len(loc['history'])!=13:
                raise RuntimeError('History/best/early-stopping reset')
            receipt['restored_components'].update(scaler=True,rng=True,sampler=True,loader_generators=True,history=True,best=True,early_stopping=True)
            receipt.update(status='resumed',all_required_state_restored=True,restored_at=c.now())
            atomic_json(OUT/'RESTORED_STATE.json',receipt)
            print('AUTHORIZED_LARGE_RESUME2: native state restored; scheduler serialization passed; epoch13 -> epoch14; best11; bad_epochs2',flush=True)
            checkpoint.clear()
        trainer.restore_rng=restore_and_observe_rng
        sys.argv=[str(AREA/'scripts/train_regularized.py'),*permit['trainer_arguments']]
        trainer.main()
        receipt['status']=read(RUN/'result.json')['status']
    except BaseException as error:
        receipt.update(status='failed',error=repr(error),traceback=traceback.format_exc())
        c.close_failed_segment(permit['token'],'authorized_resume2_exception')
        raise
    finally:
        receipt['seconds']=time.perf_counter()-started
        atomic_json(OUT/'WORKER_RECEIPT.json',receipt)

if __name__=='__main__':main()
