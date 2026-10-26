"""One temporary real microbatch, using the original train_epoch verbatim."""
from pathlib import Path
import argparse,hashlib,json,math,os,sys,time,traceback
OUT=Path(__file__).resolve().parent;PROJECT=OUT.parents[3];AREA=PROJECT/'資料治理與泛化修復'
sys.path.insert(0,str(AREA/'scripts'));sys.path.insert(0,str(PROJECT/'第二階段/src'))
import v2_relu_dropout_contract as c
from training_state import atomic_json,file_sha256

def main(size):
    target=c.RESULTS/'preflight'/f'{size}.json'
    if target.exists():raise RuntimeError('This GPU precheck already consumed; no retry')
    reused=c.read(OUT/'CPU_REUSE.json');assert reused['status']=='passed_reused'
    receipt=dict(size=size,status='failed',pid=os.getpid(),formal_training=False,seed=1,micro_batch=c.MICRO[size],
        accumulation=64//c.MICRO[size],real_train_images=c.MICRO[size],model_forwards=0,optimizer_updates=0,
        weights_reused_for_formal=False,benchmark=False,native_train_epoch=True,added_preAMP_gradient_stop=False)
    started=time.perf_counter();peak_ready=False
    try:
        import torch
        import model_profiles as profile
        from stage2.engine import seed_everything
        from train_regularized import read_csv,SkinDataset,train_epoch
        torch.set_num_threads(1);torch.set_num_interop_threads(1);seed_everything(1)
        cfg=c.read(c.CONFIG/f'v2in_{size}512_relu_stage_dropout.json');profile.validate_profile(cfg,formal=True)
        model=profile.construct_model(cfg,restore=False).cuda()
        receipt['initial_classifier_sha256']=hashlib.sha256(profile.classifier(model,cfg['training']['model']).weight.detach().cpu().numpy().tobytes()).hexdigest()
        receipt['architecture_audit']=c.model_audit(model,cfg)
        assert receipt['architecture_audit']==reused['evidence'][size]['architecture_audit']
        optimizer,_=profile.optimizer_and_scheduler(model,cfg);assert not optimizer.state
        rows=read_csv(AREA/'data/governed_18979_20261018_v1/mixed_manifest.csv')
        rows=[row for row in rows if row['split']=='train' and row['training_eligible'].lower()=='true'][:c.MICRO[size]]
        assert len(rows)==c.MICRO[size] and all(row['split']=='train' for row in rows)
        dataset=SkinDataset(rows,512,True);items=[dataset[i] for i in range(len(rows))]
        images=torch.stack([item[0] for item in items]);targets=torch.tensor([int(item[1]) for item in items],dtype=torch.long)
        loader=[(images,targets,[row['source'] for row in rows])]
        receipt.update(record_ids=[row['record_id'] for row in rows],data_version='governed_18979_20261018_v1',
            input_shape=list(images.shape),device=torch.cuda.get_device_name(0),train_transform=repr(dataset.transform),
            precheck_image_read_workers=0,formal_workers_unchanged=4,train_epoch_source_sha256=file_sha256(AREA/'scripts/train_regularized.py'))
        scaler=torch.amp.GradScaler('cuda',enabled=cfg['training']['amp'])
        criterion=torch.nn.CrossEntropyLoss(label_smoothing=cfg['training']['label_smoothing']).cuda()
        receipt['amp_scale_before']=float(scaler.get_scale())
        def observe_output(module,args,output):
            receipt['model_forwards']+=1;receipt['output_shape']=list(output.shape)
            receipt['output_finite']=bool(torch.isfinite(output).all());receipt['output_device']=str(output.device)
        hook=model.register_forward_hook(observe_output)
        stem_before=next(model.parameters()).detach().cpu().clone()
        torch.cuda.reset_peak_memory_stats();peak_ready=True
        try:
            loss=train_epoch(model,loader,criterion,optimizer,scaler,torch.device('cuda'),
                cfg['training']['gradient_accumulation'],cfg['training']['mixup_alpha'],cfg['training']['gradient_clip_norm'],cfg['training']['amp'])
        finally:hook.remove()
        torch.cuda.synchronize()
        receipt.update(loss=float(loss),amp_scale_after=float(scaler.get_scale()),optimizer_state_entries=len(optimizer.state),
            required_optimizer_state_entries=sum(p.requires_grad for p in model.parameters()))
        if not math.isfinite(loss):raise RuntimeError('Original epoch Loss is non-finite')
        if receipt['model_forwards']!=1 or receipt['output_shape']!=[c.MICRO[size],7] or not receipt['output_finite']:
            raise RuntimeError('Required finite single-forward output mismatch')
        # Check a real update after AMP handled the step; never substitute a mere call.
        if len(optimizer.state)!=receipt['required_optimizer_state_entries']:
            raise RuntimeError('Native AMP did not complete the required optimizer update; no fake success or automatic second batch')
        steps=[int(value['step'].item()) for value in optimizer.state.values()]
        if any(step!=1 for step in steps):raise RuntimeError('Unexpected actual AdamW update count')
        if not all(bool(torch.isfinite(value['exp_avg']).all()) and bool(torch.isfinite(value['exp_avg_sq']).all()) for value in optimizer.state.values()):
            raise RuntimeError('Optimizer state is non-finite after original AMP update')
        if torch.equal(stem_before,next(model.parameters()).detach().cpu()):raise RuntimeError('Required actual backbone update not observed')
        receipt.update(status='passed',optimizer_updates=1,actual_AdamW_step=1,backbone_updated=True,
            loss_divisor=cfg['training']['gradient_accumulation'],finite=True,not_full_accumulation_or_epoch=True,temporary_only=True)
    except BaseException as error:
        receipt.update(error=repr(error),traceback=traceback.format_exc());(c.RESULTS/'STOP').touch(exist_ok=True)
    finally:
        if peak_ready:
            receipt.update(peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved())
        receipt.update(seconds=time.perf_counter()-started,command=sys.argv);atomic_json(target,receipt)
    print(json.dumps({key:receipt.get(key) for key in ('size','status','model_forwards','optimizer_updates','amp_scale_before','amp_scale_after','error')},ensure_ascii=False))
    return 0 if receipt['status']=='passed' else 1

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--size',choices=['tiny','base'],required=True);args=parser.parse_args();sys.exit(main(args.size))
