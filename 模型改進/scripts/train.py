"""CP005 eight-class training. No evaluation split participates in checkpoint selection."""
from pathlib import Path
import sys
import argparse
import copy
import hashlib
import json
import random
import subprocess
from collections import Counter

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from common import ROOT,EXP,load,read_rows,write,sha
from metrics import evaluate,source_summary
from geometry import crop
from preprocessing import mode as preprocessing_mode, spatial_transform, ResizeToFit, RealPixelInput, pilot_config
from versioning import revision
sys.path.insert(0,str(EXP/'queue'))
from safety import check_finite, safe_save, check_disk, optimizer_step
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader,Dataset,WeightedRandomSampler
from torchvision import transforms
from PIL import Image,ImageOps
from tqdm import tqdm

sys.path.insert(0,str(ROOT/'第二階段/src'))
from stage2.models import build_model,parameter_groups_with_layer_decay


class Images(Dataset):
    def __init__(self,rows,cfg,train=False,cache=None):
        self.rows,self.cfg,self.cache=rows,cfg,cache
        r,t,n=cfg['run'],cfg['training'],cfg['normalization']
        if 'noisefilter_v2' in cfg:
            from nf_adapter import dataset_chain
            self.transform=RealPixelInput(cfg,train,dataset_chain(cfg['noisefilter_v2']['profile']))
            return
        letterbox=preprocessing_mode(cfg)=='letterbox'
        spatial=transforms.RandomResizedCrop(r['size'],scale=t['crop_scale'],ratio=t['crop_ratio']) if train and preprocessing_mode(cfg)=='legacy' else spatial_transform(cfg)
        ops=[] if letterbox else [spatial]
        if letterbox and train:
            ops.append(ResizeToFit(r['size'],cfg['preprocessing']['fill'],cfg['preprocessing'].get('allow_upscale',True)))
        if train:
            ops += [transforms.RandomHorizontalFlip(),transforms.RandomVerticalFlip(),
                    transforms.ColorJitter(.22,.22,.20,.03)]
        if letterbox: ops.append(spatial)  # Fill AFTER jitter: no synthetic border color augmentation.
        ops += [transforms.ToTensor(),transforms.Normalize(n['mean'],n['std'])]
        self.transform=transforms.Compose(ops)
    def __len__(self): return len(self.rows)
    def __getitem__(self,i):
        r=self.rows[i]
        with Image.open(ROOT/r['image_path']) as im:
            im=ImageOps.exif_transpose(im).convert('RGB')
            im=crop(im,self.cfg['run']['crop'],self.cfg['run']['k'],self.cache.get(r['record_id']) if self.cache else None)
            return self.transform(im),int(r['label']),r['source']


def probabilities(logits):
    z=logits-logits.max(1,keepdims=True); p=np.exp(z); return p/p.sum(1,keepdims=True)


def report(logits,y,sources):
    result={}
    for source in sorted(set(sources)):
        mask=np.array(sources)==source
        result[source]=evaluate(probabilities(logits[mask]),y[mask],sorted(set(y[mask].tolist())))
    return {'by_source':result,**source_summary(result,sorted(set(sources)))}


@torch.inference_mode()
def infer(model,loader,device,tta=False):
    model.eval(); logits=[]; targets=[]; sources=[]
    for x,y,s in tqdm(loader,desc='評估',leave=False):
        x=x.to(device)
        with torch.autocast(device_type=device.type,enabled=device.type=='cuda'):
            if tta:
                # Geometric transformations are applied after the same deterministic crop/resize.
                ps=[model(torch.rot90(x.flip(-1) if flip else x,k,(-2,-1))).float().softmax(1)
                    for flip in [False,True] for k in range(4)]
                z=torch.stack(ps).mean(0).clamp_min(1e-12).log()
            else: z=model(x).float()
        check_finite(z, 'evaluation logits')
        logits.append(z.cpu().numpy()); targets.extend(y.tolist()); sources.extend(s)
    return np.concatenate(logits),np.array(targets),sources


def allocate(parent,run_id):
    parent.mkdir(parents=True,exist_ok=True)
    for n in range(10000):
        folder=parent/(run_id if n==0 else f'{run_id}_rerun{n}')
        try: folder.mkdir(); return folder
        except FileExistsError: pass
    raise RuntimeError('Too many reruns')


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--run',default='R0'); ap.add_argument('--seed',type=int,default=17)
    ap.add_argument('--resume',type=Path); ap.add_argument('--smoke',action='store_true')
    ap.add_argument('--check-only',action='store_true',help='Validate setup without creating a run or training')
    ap.add_argument('--continuous',action='store_true',help='Independent additional seeds; defer assessment; enable graceful stop')
    ap.add_argument('--nf-profile',choices=['off','full','no-tone'],default='off')
    ap.add_argument('--input-pilot',choices=['stretch','letterbox'])
    args=ap.parse_args(); cfg=load(EXP/'config.json')
    if args.input_pilot and (args.nf_profile!='off' or not args.continuous or args.seed!=17):
        raise SystemExit('Input pilots require off/continuous/seed17')
    pilot_config(cfg,args.input_pilot)
    preprocessing_mode(cfg)  # Reject unknown modes before allocating an output.
    if args.run not in cfg['runs'] or (args.seed not in cfg['seeds'] and not (args.continuous and 10000<=args.seed<2**32)): raise SystemExit('Unregistered run/seed')
    if args.continuous:
        cfg['continuous_protocol']='independent-seeds-deferred-assessment-v1'
    cfg['run']=cfg['runs'][args.run]; cfg.pop('runs')
    cfg['seed']=args.seed; cfg['run_name']=args.run; cfg['smoke_test']=args.smoke
    split_gate=load(ROOT/cfg.get('split_report','模型改進/reports/cp005_split.json'))
    manifest=ROOT/cfg['manifest']
    assert split_gate['passed'] and split_gate['manifest_sha256']==sha(manifest)
    cfg['manifest_sha256']=sha(manifest)
    if args.nf_profile!='off':
        if preprocessing_mode(cfg) not in ['letterbox','stretch']: raise SystemExit('NF2 requires explicit whole-image preprocessing')
        if args.run!='R0' or not args.continuous: raise SystemExit('NF2 supported only in deferred-assessment R0; LOSO requires separate calibration')
        from nf_adapter import metadata
        cfg['noisefilter_v2']=metadata(args.nf_profile)
    cache=None
    if cfg['run']['crop']=='D2':
        gate=load(EXP/'reports/R0_bbox_stats.json')
        assert gate['quantitative_passed'] and gate['visual_review_approved'], 'G-R0 not approved'
        assert gate['manifest_sha256']==sha(manifest)
        cache=load(EXP/'data/bbox_D2.json')['records']
        cfg['bbox_sha256']=sha(EXP/'data/bbox_D2.json')
    if args.run in ['R3','R4','R5','R6']:
        assert load(EXP/'reports/G_R1.json')['passed'], 'G-R1 not passed'
    commit=revision(ROOT)
    code_paths=sorted((EXP/'src').glob('*.py'))+sorted((EXP/'scripts').glob('*.py'))
    code_paths += sorted((ROOT/'第二階段/src/stage2').glob('*.py'))
    code_paths += sorted((ROOT/'noisefilter_v2強化實驗/vendor/noisefilter_v2').glob('*.py'))
    code_paths += [ROOT/'noisefilter_v2強化實驗/scripts/runtime_bootstrap.py']
    code_paths += sorted((EXP/'queue').glob('*.py'))
    code_paths += [ROOT/'noisefilter_v2強化實驗/scripts/_common.py',ROOT/'noisefilter_v2強化實驗/scripts/source_probe_input.py']
    cfg['code_sha256']=hashlib.sha256(''.join(sha(p) for p in code_paths).encode()).hexdigest()
    tc=cfg['training']; r=cfg['run']
    if args.smoke: tc['epochs']=1
    assert tc['effective_batch']==32 and 32%r['batch_size']==0
    identity_cfg={k:v for k,v in cfg.items() if k!='seed'}
    digest=hashlib.sha256((json.dumps(identity_cfg,sort_keys=True,separators=(',',':'))+commit).encode()).hexdigest()[:8]
    run_id=f'{args.run}_{digest}_seed{args.seed}'
    if args.check_only:
        print(f'CHECK OK commit={commit} run_id={run_id} CUDA={torch.cuda.is_available()}')
        return
    if args.resume:
        output=args.resume.resolve(); existing=load(output/'config_snapshot.json')
        if existing['config']!=cfg: raise SystemExit('Resume config/code/manifest mismatch')
        if (output/'result.json').exists(): raise SystemExit('Completed result is immutable; no resume needed')
        run_id=existing['run_id']; commit=existing['git_commit']
    else:
        output=allocate(EXP/('smoke_results' if args.smoke else 'results'),run_id)
        write(output/'config_snapshot.json',{'config':cfg,'git_commit':commit,'run_id':run_id})
    rows=read_rows(manifest)
    train=[x for x in rows if x['split']=='train' and x['source']!=r['held_out']]
    select=[x for x in rows if x['split']=='val_select' and x['source']!=r['held_out']]
    assess=[x for x in rows if x['split']=='val_assess']
    if args.input_pilot:
        from _common import balanced_sample
        train=balanced_sample(train,cfg['input_pilot']['train_per_source'],17)
        select=balanced_sample(select,cfg['input_pilot']['select_per_source'],17)
    if args.smoke:
        def small(items):
            chosen={}
            for row in items: chosen.setdefault((row['source'],row['label']),row)
            return list(chosen.values())
        train,select,assess=small(train),small(select),small(assess)
    assert not {x['cp005_group'] for x in train}&{x['cp005_group'] for x in select+assess}
    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed); torch.backends.cudnn.deterministic=True; torch.backends.cudnn.benchmark=False
    device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    if device.type!='cuda' and not args.smoke: raise SystemExit('CUDA required for formal runs')
    counts=Counter((x['source'],int(x['label'])) for x in train)
    normalizers={s:sum(n**.5 for (src,_),n in counts.items() if src==s) for s,_ in counts}
    weights=[counts[x['source'],int(x['label'])]**-.5/normalizers[x['source']] for x in train]
    generator=torch.Generator().manual_seed(args.seed+4)
    # Full effective batches including last step; draws are with replacement, not full coverage.
    draws=((len(train)+31)//32)*32
    sampler=WeightedRandomSampler(weights,draws,generator=generator)
    def loader(items,training=False):
        return DataLoader(Images(items,cfg,training,cache),batch_size=r['batch_size'],
            sampler=sampler if training else None,num_workers=tc['num_workers'],pin_memory=device.type=='cuda')
    train_loader,select_loader,assess_loader=loader(train,True),loader(select),loader(assess)
    model=build_model('convnext_tiny',pretrained=not args.smoke,num_classes=8).to(device)
    optimizer=torch.optim.AdamW(parameter_groups_with_layer_decay(model,tc['lr'],tc['weight_decay'],tc['layer_decay']))
    if args.nf_profile!='off': torch.set_num_threads(4)
    scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,tc['epochs'],eta_min=1e-6)
    scaler=torch.amp.GradScaler('cuda',enabled=device.type=='cuda')
    criterion=nn.CrossEntropyLoss(label_smoothing=tc['label_smoothing'])
    history=[]; best=-1.; patience=0; start=0; consecutive_overflows=0
    if args.resume:
        st=torch.load(output/'last.pt',map_location=device,weights_only=False)
        check_finite(st, 'resume checkpoint')
        model.load_state_dict(st['model']); optimizer.load_state_dict(st['optimizer']); scheduler.load_state_dict(st['scheduler']); scaler.load_state_dict(st['scaler'])
        history,best,patience,start=st['history'],st['best'],st['patience'],st['epoch']
        consecutive_overflows=st.get('consecutive_amp_overflows',0)
        generator.set_state(st['sampler_rng'].cpu()); torch.set_rng_state(st['torch_rng'].cpu())
        np.random.set_state(st['numpy_rng']); random.setstate(st['python_rng'])
        if device.type=='cuda': torch.cuda.set_rng_state_all([x.cpu() for x in st['cuda_rng']])
    print(f'RUN {output.name} train={len(train)} val_select={len(select)} val_assess={len(assess)}',flush=True)
    accum=32//r['batch_size']
    for epoch in range(start,tc['epochs']):
        if patience>=tc['patience']: break
        model.train(); optimizer.zero_grad(set_to_none=True); loss_sum=0.
        amp_skipped_updates=0; optimizer_updates=0
        for step,(x,y,_) in enumerate(tqdm(train_loader,desc=f'{epoch+1}/{tc["epochs"]} 訓練')):
            x,y=x.to(device),y.to(device); lam=float(np.random.beta(tc['mixup_alpha'],tc['mixup_alpha']))
            check_finite(x, 'input')
            perm=torch.randperm(len(y),device=device)
            with torch.autocast(device_type=device.type,enabled=device.type=='cuda'):
                z=model(lam*x+(1-lam)*x[perm]); loss=lam*criterion(z,y)+(1-lam)*criterion(z,y[perm])
            check_finite(z, 'logits'); check_finite(loss, 'loss')
            scaler.scale(loss/accum).backward(); loss_sum+=float(loss.detach())*len(y)
            if (step+1)%accum==0:
                old_scale=scaler.get_scale()
                if optimizer_step(model.parameters(),optimizer,scaler,consecutive_overflows):
                    consecutive_overflows=0; optimizer_updates+=1
                else:
                    consecutive_overflows+=1; amp_skipped_updates+=1
                    print(f'AMP overflow: epoch={epoch+1} batch={step+1}; update skipped; '
                          f'scale={old_scale:g}->{scaler.get_scale():g}; consecutive={consecutive_overflows}/8',flush=True)
        if optimizer_updates==0:
            raise FloatingPointError('No successful optimizer updates this epoch; no checkpoint saved')
        z,y,s=infer(model,select_loader,device); metrics=report(z,y,s)
        record={'epoch':epoch+1,'train_loss':loss_sum/draws,'val_select':metrics,
                'amp_skipped_updates':amp_skipped_updates,'optimizer_updates':optimizer_updates,
                'amp_scale':scaler.get_scale()}; history.append(record)
        score=metrics['worst_source_balanced_accuracy']
        check_finite(score, 'selection score')
        check_disk(output)
        if score>best:
            best,patience=score,0
            safe_save({'model':model.state_dict(),'config':cfg,'epoch':epoch+1,'run_id':run_id},output/'best.pt')
        else: patience+=1
        scheduler.step()
        safe_save({'model':model.state_dict(),'optimizer':optimizer.state_dict(),'scheduler':scheduler.state_dict(),
                    'scaler':scaler.state_dict(),'epoch':epoch+1,'history':history,'best':best,'patience':patience,
                    'consecutive_amp_overflows':consecutive_overflows,
                    'sampler_rng':generator.get_state(),'torch_rng':torch.get_rng_state(),'numpy_rng':np.random.get_state(),
                    'python_rng':random.getstate(),'cuda_rng':torch.cuda.get_rng_state_all() if device.type=='cuda' else []},output/'last.pt')
        write(output/'progress.json',{'history':history,'run_id':run_id})
        print(f'epoch={epoch+1} val_select 最差來源 BA={score:.4f}',flush=True)
        if args.continuous and (EXP/'results/continuous/STOP').exists():
            print('Graceful stop: checkpoint saved.',flush=True)
            return
    st=torch.load(output/'best.pt',map_location=device,weights_only=False); model.load_state_dict(st['model'])
    outputs={}
    for role,dl in ([('val_select',select_loader)] if args.continuous else [('val_select',select_loader),('val_assess',assess_loader)]):
        z,y,s=infer(model,dl,device); outputs[role]=report(z,y,s)
        check_finite(z, 'final logits')
        np.savez_compressed(output/f'{role}_logits.npz',logits=z,targets=y,sources=np.array(s),
                            record_ids=np.array([x['record_id'] for x in dl.dataset.rows]))
    write(output/'result.json',{'run_id':run_id,'run_directory':output.name,'run':args.run,'config':cfg,
        'git_commit':commit,'seed':args.seed,'seeds':[args.seed],'pilot':True,'smoke_test':args.smoke,
        'history':history,'best_epoch':st['epoch'],'metrics':outputs,'sealed_test_used':False,
        'train_count':len(train),'sampling':'equal source mass; inverse sqrt class frequency; replacement',
        'held_out_source':r['held_out'],'note':'Formal three-seed statistics are separate aggregate artifacts.'})
    print('Completed:',output,flush=True)


if __name__=='__main__': main()
