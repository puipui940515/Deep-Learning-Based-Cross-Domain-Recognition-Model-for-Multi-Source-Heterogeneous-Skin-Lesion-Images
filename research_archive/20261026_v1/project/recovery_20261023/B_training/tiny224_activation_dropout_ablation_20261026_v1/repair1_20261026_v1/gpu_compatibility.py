"""One full 32x2 update through the unchanged trainer for each new arm."""
from pathlib import Path
import argparse,hashlib,json,math,os,sys,time,traceback
OUT=Path(__file__).resolve().parent;PROJECT=OUT.parents[3];AREA=PROJECT/'資料治理與泛化修復'
sys.path.insert(0,str(AREA/'scripts'));sys.path.insert(0,str(PROJECT/'第二階段/src'))
import v2_tiny224_ablation_contract as c
from training_state import atomic_json,file_sha256


def main(group):
    target=OUT/f'GPU_{group}.json'
    if target.exists() or (c.RESULTS/'STOP').exists():raise RuntimeError('GPU attempt consumed/stopped; no retry')
    receipt=dict(group=group,status='failed',formal_training=False,seed=1,micro_batch=32,accumulation=2,
        model_forwards=0,optimizer_updates=0,native_train_epoch=True,loss_divisor=2,
        added_preAMP_gradient_stop=False,weights_reused_for_formal=False,benchmark=False)
    start=time.perf_counter();peak=False
    try:
        import torch
        import model_profiles as profile
        from stage2.engine import seed_everything
        from train_regularized import read_csv,SkinDataset,train_epoch
        torch.set_num_threads(1);torch.set_num_interop_threads(1);seed_everything(1)
        assert c.read(c.CPU_ROOT/'IO_VALIDATION_fix1.json')['status']=='passed'
        cpu=c.read(c.CPU_ROOT/f'CPU_{group}.json');assert cpu['status']=='passed'
        candidate=next(k for k,v in c.CANDIDATES.items() if v[0]==group)
        cfg=c.read(c.CONFIG/(candidate+'.json'));profile.validate_profile(cfg,formal=True)
        model=profile.construct_model(cfg,restore=False).cuda();receipt['architecture_audit']=c.model_audit(model,cfg)
        assert receipt['architecture_audit']==cpu['architecture_audit']
        receipt['initial_classifier_sha256']=hashlib.sha256(model.get_classifier().weight.detach().cpu().numpy().tobytes()).hexdigest()
        old=c.read(c.reference_folder(group,1)/'run_inputs.json')
        assert receipt['initial_classifier_sha256']==old['initial_classifier_sha256']
        optimizer,_=profile.optimizer_and_scheduler(model,cfg);assert not optimizer.state
        rows=read_csv(AREA/'data/governed_18979_20261018_v1/mixed_manifest.csv')
        rows=[r for r in rows if r['split']=='train' and r['training_eligible'].lower()=='true'][:64]
        assert len(rows)==64 and all(r['split']=='train' for r in rows)
        dataset=SkinDataset(rows,224,True);loader=[]
        for start_index in (0,32):
            items=[dataset[i] for i in range(start_index,start_index+32)]
            loader.append((torch.stack([item[0] for item in items]),torch.tensor([int(item[1]) for item in items],dtype=torch.long),[r['source'] for r in rows[start_index:start_index+32]]))
        receipt.update(real_train_images=64,input_shapes=[list(batch[0].shape) for batch in loader],
            record_ids=[r['record_id'] for r in rows],data_version='governed_18979_20261018_v1',
            train_transform=repr(dataset.transform),device=torch.cuda.get_device_name(0),
            precheck_image_read_workers=0,formal_workers_unchanged=4,
            train_epoch_source_sha256=file_sha256(AREA/'scripts/train_regularized.py'))
        scaler=torch.amp.GradScaler('cuda',enabled=cfg['training']['amp'])
        criterion=torch.nn.CrossEntropyLoss(label_smoothing=cfg['training']['label_smoothing']).cuda()
        receipt['amp_scale_before']=float(scaler.get_scale())
        actual_updates=[]
        update_hook=optimizer.register_step_post_hook(lambda *args:actual_updates.append(True))
        def observe(module,args,output):
            receipt['model_forwards']+=1;receipt['output_shape']=list(output.shape)
            receipt['output_finite']=bool(torch.isfinite(output).all());receipt['output_device']=str(output.device)
        model_hook=model.register_forward_hook(observe)
        before=next(model.parameters()).detach().cpu().clone()
        torch.cuda.reset_peak_memory_stats();peak=True
        try:
            loss=train_epoch(model,loader,criterion,optimizer,scaler,torch.device('cuda'),
                cfg['training']['gradient_accumulation'],cfg['training']['mixup_alpha'],cfg['training']['gradient_clip_norm'],cfg['training']['amp'])
        finally:
            model_hook.remove();update_hook.remove()
        torch.cuda.synchronize()
        required=sum(p.requires_grad for p in model.parameters())
        receipt.update(loss=float(loss),amp_scale_after=float(scaler.get_scale()),
            optimizer_state_entries=len(optimizer.state),required_optimizer_state_entries=required,
            optimizer_updates=len(actual_updates))
        if not math.isfinite(loss):raise RuntimeError('Original whole-epoch loss is non-finite')
        if receipt['model_forwards']!=2 or receipt['output_shape']!=[32,7] or not receipt['output_finite']:
            raise RuntimeError('Required native 32x2 forward result differs')
        if len(actual_updates)!=1 or len(optimizer.state)!=required:
            raise RuntimeError('Native AMP did not complete the required actual AdamW update; no fake success or retry')
        steps=[int(value['step'].item()) for value in optimizer.state.values()]
        if any(step!=1 for step in steps):raise RuntimeError('Actual optimizer steps differ')
        if not all(bool(torch.isfinite(value['exp_avg']).all()) and bool(torch.isfinite(value['exp_avg_sq']).all()) for value in optimizer.state.values()):
            raise RuntimeError('Optimizer moments non-finite after original AMP processing')
        if torch.equal(before,next(model.parameters()).detach().cpu()):raise RuntimeError('Actual backbone update not observed')
        receipt.update(status='passed',actual_AdamW_step=1,backbone_updated=True,finite=True,full_accumulation_window=True,temporary_only=True)
    except BaseException as e:
        receipt.update(error=repr(e),traceback=traceback.format_exc());(c.RESULTS/'STOP').touch(exist_ok=True)
    finally:
        if peak:receipt.update(peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved())
        receipt.update(seconds=time.perf_counter()-start,command=sys.argv,python=sys.executable,pid=os.getpid())
        atomic_json(target,receipt)
    print(json.dumps({k:receipt.get(k) for k in ['group','status','model_forwards','optimizer_updates','amp_scale_before','amp_scale_after','seconds','error']},ensure_ascii=False))
    return 0 if receipt['status']=='passed' else 1


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--group',choices=['relu','dropout'],required=True)
    sys.exit(main(p.parse_args().group))
