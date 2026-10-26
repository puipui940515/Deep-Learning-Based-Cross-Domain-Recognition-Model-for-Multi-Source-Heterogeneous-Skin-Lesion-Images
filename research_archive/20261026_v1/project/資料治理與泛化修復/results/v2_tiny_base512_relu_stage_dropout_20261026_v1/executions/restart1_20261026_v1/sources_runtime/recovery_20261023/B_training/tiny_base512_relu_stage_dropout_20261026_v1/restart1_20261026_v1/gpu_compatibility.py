"""Exactly one real non-Test microbatch and one optimizer update per model."""
from pathlib import Path
import argparse,hashlib,json,math,os,sys,time,traceback
OUT=Path(__file__).resolve().parent;PROJECT=OUT.parents[3];AREA=PROJECT/'資料治理與泛化修復'
sys.path.insert(0,str(AREA/'scripts'));sys.path.insert(0,str(PROJECT/'第二階段/src'))
import v2_relu_dropout_contract as c
from training_state import atomic_json

def main(size):
    target=c.RESULTS/'preflight'/f'{size}.json'
    if target.exists():raise RuntimeError('One GPU precheck already consumed; no automatic retry')
    cpu=c.read(OUT/f'CPU_{size}.json');assert cpu['status']=='passed'
    receipt=dict(size=size,status='failed',pid=os.getpid(),formal_training=False,seed=1,micro_batch=c.MICRO[size],
        real_train_images=c.MICRO[size],model_forwards=0,optimizer_updates=0,weights_reused_for_formal=False,benchmark=False)
    started=time.perf_counter()
    try:
        import torch
        import model_profiles as profile
        from stage2.engine import seed_everything
        from train_regularized import read_csv,SkinDataset
        torch.set_num_threads(1);torch.set_num_interop_threads(1);seed_everything(1)
        cfg=c.read(c.CONFIG/f'v2in_{size}512_relu_stage_dropout.json');profile.validate_profile(cfg,formal=True)
        model=profile.construct_model(cfg,restore=False).cuda();model.train()
        receipt['initial_classifier_sha256']=hashlib.sha256(profile.classifier(model,cfg['training']['model']).weight.detach().cpu().numpy().tobytes()).hexdigest()
        receipt['architecture_audit']=c.model_audit(model,cfg)
        assert receipt['architecture_audit']==cpu['architecture_audit']
        optimizer,_=profile.optimizer_and_scheduler(model,cfg);assert not optimizer.state
        rows=read_csv(AREA/'data/governed_18979_20261018_v1/mixed_manifest.csv')
        rows=[row for row in rows if row['split']=='train' and row['training_eligible'].lower()=='true'][:c.MICRO[size]]
        assert len(rows)==c.MICRO[size] and all(row['split']=='train' for row in rows)
        dataset=SkinDataset(rows,512,True);items=[dataset[i] for i in range(len(rows))]
        images=torch.stack([item[0] for item in items]).cuda();targets=torch.tensor([int(item[1]) for item in items],device='cuda')
        receipt.update(record_ids=[row['record_id'] for row in rows],data_version='governed_18979_20261018_v1',precheck_image_read_workers=0,formal_workers_unchanged=4,
            input_shape=list(images.shape),device=torch.cuda.get_device_name(0),train_transform=repr(dataset.transform))
        scaler=torch.amp.GradScaler('cuda',enabled=True);criterion=torch.nn.CrossEntropyLoss(label_smoothing=.1)
        optimizer.zero_grad(set_to_none=True);torch.cuda.reset_peak_memory_stats()
        with torch.autocast(device_type='cuda',enabled=True):
            permutation=torch.randperm(images.size(0),device=images.device)
            import numpy as np
            lam=float(np.random.beta(.2,.2));mixed=lam*images+(1-lam)*images[permutation]
            logits=model(mixed);receipt['model_forwards']=1
            loss=lam*criterion(logits,targets)+(1-lam)*criterion(logits,targets[permutation])
        assert logits.shape==(c.MICRO[size],7) and torch.isfinite(logits).all() and torch.isfinite(loss)
        # A bounded compatibility update, not a simulated full effective-batch run.
        scaler.scale(loss).backward();scaler.unscale_(optimizer)
        assert all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None)
        torch.nn.utils.clip_grad_norm_(model.parameters(),1.);scaler.step(optimizer);scaler.update();torch.cuda.synchronize()
        assert len(optimizer.state)==sum(p.requires_grad for p in model.parameters())
        assert all(torch.isfinite(value['exp_avg']).all() and torch.isfinite(value['exp_avg_sq']).all() for value in optimizer.state.values())
        receipt.update(status='passed',optimizer_updates=1,optimizer_state_entries=len(optimizer.state),loss=float(loss.detach()),output_shape=list(logits.shape),finite=True,
            peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved(),
            not_full_accumulation_or_epoch=True,temporary_only=True)
    except BaseException as error:
        receipt.update(error=repr(error),traceback=traceback.format_exc());(c.RESULTS/'STOP').touch(exist_ok=True)
    receipt.update(seconds=time.perf_counter()-started,command=sys.argv);atomic_json(target,receipt)
    print(json.dumps({k:receipt.get(k) for k in ('size','status','model_forwards','optimizer_updates','peak_allocated_bytes','error')},ensure_ascii=False))
    return 0 if receipt['status']=='passed' else 1

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--size',choices=['tiny','base'],required=True);args=parser.parse_args();sys.exit(main(args.size))
