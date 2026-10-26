"""Bounded compatibility work: 2 effective batches + 8 validation images, per option."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import traceback
OUT=Path(__file__).resolve().parent;PROJECT=OUT.parents[2];AREA=PROJECT/'資料治理與泛化修復'
sys.path.insert(0,str(AREA/'scripts'))
import v2_scale_contract as c
from training_state import atomic_json

def main(size,micro):
    started=time.perf_counter();path=c.RESULTS/'preflight'/f'{size}_micro{micro}.json'
    if path.exists():raise RuntimeError('Existing preflight attempt must be reused, not repeated')
    result=dict(size=size,micro_batch=micro,accumulation=64//micro,status='failed',pid=os.getpid(),
        formal_training=False,seed=1,initialization_independent=True,training_samples=128,validation_samples=8,
        optimizer_updates_planned=2,weights_reused_for_formal=False,workers=4,not_full_benchmark=True)
    try:
        import torch
        import numpy as np
        from train_regularized import SkinDataset,read_csv,stratified_limit,train_epoch,evaluate
        from stage2.engine import seed_everything
        import model_profiles as profile
        cfg=c.read(c.CONFIG/f'v2in_scale512_{size}.json')
        cfg['training'].update(batch_size=micro,gradient_accumulation=64//micro)
        profile.validate_profile(cfg,formal=True)
        torch.set_num_threads(1);torch.set_num_interop_threads(1)
        seed_everything(1)
        torch.cuda.reset_peak_memory_stats()
        model=profile.construct_model(cfg,restore=False).cuda()
        head=profile.classifier(model,cfg['training']['model'])
        result['initial_classifier_sha256']=hashlib.sha256(head.weight.detach().cpu().numpy().tobytes()).hexdigest()
        optimizer,scheduler=profile.optimizer_and_scheduler(model,cfg)
        assert not optimizer.state
        criterion=torch.nn.CrossEntropyLoss(label_smoothing=.1).cuda()
        scaler=torch.amp.GradScaler('cuda',enabled=True)
        rows=read_csv(AREA/'data/governed_18979_20261018_v1/mixed_manifest.csv')
        train=stratified_limit([r for r in rows if r['split']=='train'],64,2)
        val=sorted([r for r in rows if r['split']=='validation'],key=lambda r:r['record_id'])[:8]
        assert len(train)==64 and len(val)==8 and all(r['split'] in ('train','validation') for r in train+val)
        dataset=SkinDataset(train,512,True)
        loader=torch.utils.data.DataLoader(dataset,batch_size=micro,num_workers=4,prefetch_factor=4,
            persistent_workers=True,generator=torch.Generator().manual_seed(101),shuffle=False)
        validation=torch.utils.data.DataLoader(SkinDataset(val,512,False),batch_size=micro,num_workers=4,
            prefetch_factor=4,persistent_workers=True,generator=torch.Generator().manual_seed(102),shuffle=False)
        stem_before=next(model.parameters()).detach().cpu().clone()
        result.update(stage='backward_accumulation_and_optimizer',train_transform=repr(dataset.transform),validation_transform=repr(validation.dataset.transform))
        cycles=[]
        for cycle in (1,2):
            timing=dict(data_wait_including_iterator_tqdm_seconds=0.,batch_processing_seconds_with_existing_loss_sync=0.,batches=0)
            torch.cuda.synchronize();t=time.perf_counter()
            loss=train_epoch(model,loader,criterion,optimizer,scaler,torch.device('cuda'),64//micro,.2,1.,True,timing)
            torch.cuda.synchronize();seconds=time.perf_counter()-t
            assert math.isfinite(loss)
            states=len(optimizer.state)
            assert states==sum(p.requires_grad for p in model.parameters()), 'Optimizer state allocation incomplete/skipped AMP step'
            assert all(torch.isfinite(v['exp_avg']).all() and torch.isfinite(v['exp_avg_sq']).all() for v in optimizer.state.values())
            cycles.append(dict(cycle=cycle,loss=loss,seconds=seconds,images=64,images_per_second=64/seconds,
                               optimizer_state_entries=states,**timing))
        assert not torch.equal(stem_before,next(model.parameters()).detach().cpu()),'Backbone did not update'
        torch.cuda.synchronize();t=time.perf_counter()
        vm=evaluate(model,validation,criterion,torch.device('cuda'),list(range(7)),'scale preflight validation',True)
        torch.cuda.synchronize();validation_seconds=time.perf_counter()-t
        assert math.isfinite(vm['loss'])
        result.update(status='passed',stage='complete',cycles=cycles,optimizer_state_allocated=True,
            backbone_update_observed=True,validation_seconds=validation_seconds,validation_images_per_second=8/validation_seconds,
            peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved(),
            steady_train_images_per_second=cycles[1]['images_per_second'],
            mixup_note='Original microbatch-local randperm; micro1 pairs with itself and makes MixUp ineffective' if micro==1 else 'Original microbatch-local randperm; pairing pool differs from Tiny8 when microbatch differs',
            checkpoint_save_seconds=None,save_scope='only small preflight receipt; full protected Checkpoint timing measured during formal epochs',
            cold_start_limit='cycle1 includes worker startup and first optimizer-state allocation; cycle2 is a short necessary sample, not long-term performance')
        del loader,validation,model,optimizer
    except torch.OutOfMemoryError as exc:
        result.update(status='oom',error=str(exc),stage=result.get('stage','model_or_state_allocation'))
    except BaseException as exc:
        result.update(status='failed',error=repr(exc),traceback=traceback.format_exc())
    finally:
        result['elapsed_seconds']=time.perf_counter()-started
        t=time.perf_counter();atomic_json(path,result);result['receipt_save_seconds']=time.perf_counter()-t;atomic_json(path,result)
    print(json.dumps({k:result.get(k) for k in ('size','micro_batch','status','steady_train_images_per_second','peak_allocated_bytes','error')},ensure_ascii=False),flush=True)
    return 0 if result['status']=='passed' else 10 if result['status']=='oom' else 1

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--size',choices=c.SIZES,required=True);parser.add_argument('--micro',type=int,choices=(8,4,2,1),required=True)
    args=parser.parse_args();sys.exit(main(args.size,args.micro))
