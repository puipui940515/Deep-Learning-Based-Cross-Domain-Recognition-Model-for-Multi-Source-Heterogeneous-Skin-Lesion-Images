"""CPU/static acceptance; no CUDA initialization, forward or training."""
import argparse
import hashlib
import importlib.metadata
import os
import platform
import subprocess
import sys
from training_state import atomic_json,file_sha256
import v2_resolution_contract as opt

def main():
    p=argparse.ArgumentParser();p.add_argument('--verify-only',action='store_true');args=p.parse_args()
    if args.verify_only:opt.gate();print('PASS: formal resolution runtime including independent GPU Resume acceptance');return
    if (opt.CONFIG/'ACCEPTANCE.json').exists():raise RuntimeError('CPU acceptance exists; no repeated validation')
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    import torch
    import train_regularized as trainer
    import model_profiles as profile
    torch.set_num_threads(2)
    opt.gate(False)
    base=opt.read(opt.BASE_CONFIG)
    _,rows,provenance=trainer.load_governed_release(opt.AREA/'data/governed_18979_20261018_v1',base)
    assert len([r for r in rows if r['split']=='train'])==18919 and len([r for r in rows if r['split']=='validation'])==3611
    assert provenance['manifest_sha256']==base['formal_suite']['manifest_sha256']
    versions={p:importlib.metadata.version(p) for p in ['torch','torchvision','timm','numpy','Pillow']}
    assert versions=={'torch':'2.11.0+cu128','torchvision':'0.26.0+cu128','timm':'1.0.30','numpy':'1.26.4','Pillow':'10.4.0'}
    identity=profile.weight_identity(base);report={}
    for candidate,(size,batch,accum) in opt.CANDIDATES.items():
        config=opt.read(opt.CONFIG/(candidate+'.json'));profile.validate_profile(config,True)
        assert batch*accum==64
        tr=trainer.build_transform(size,True);val=trainer.build_transform(size,False)
        assert tr.transforms[-1].p==.15 and val.transforms[0].size==(size,size) and 'Random' not in repr(val)
        heads={}
        for seed in (1,2,3):
            trainer.seed_everything(seed);model=profile.construct_model(config)
            head=hashlib.sha256(profile.classifier(model,'convnextv2_tiny').weight.detach().numpy().tobytes()).hexdigest()
            assert head==opt.read(opt.BASE_RESULTS/f'regularized_seed{seed}'/'run_inputs.json')['initial_classifier_sha256']
            optimizer,scheduler=profile.optimizer_and_scheduler(model,config)
            assert not optimizer.state
            heads[seed]=head
            if seed==1:
                groups=opt.describe_groups(model,optimizer);assert len(groups)==18
                trajectory=[[g['lr'] for g in optimizer.param_groups]]
                for epoch in range(30):optimizer.step();scheduler.step();trajectory.append([g['lr'] for g in optimizer.param_groups])
                assert all(all(y<=x+1e-15 for x,y in zip(a,b)) for a,b in zip(trajectory,trajectory[1:]))
                assert all(abs(lr-1e-6)<1e-12 for lr in trajectory[-1])
            del model,optimizer,scheduler
        assert len(set(heads.values()))==3
        report[candidate]=dict(heads=heads,optimizer_groups=groups,lr_trajectory=trajectory,train_transform=repr(tr),validation_transform=repr(val))
    result=subprocess.run([sys.executable,'-B','-m','unittest','test_training_resume','test_model_profiles','test_v2_resolution','-v'],cwd=opt.AREA/'scripts',capture_output=True,text=True,encoding='utf-8')
    (opt.CONFIG/'CPU_TESTS.log').write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
    if result.returncode:raise RuntimeError('CPU regression failed; see CPU_TESTS.log')
    atomic_json(opt.CONFIG/'PREFLIGHT.json',dict(passed=True,kind='cpu_static_no_training',at=opt.now(),versions=versions,python=platform.python_version(),
                profiles=report,weight_identity=identity,manifest=provenance,no_test_read=True))
    paths=[opt.CONFIG/'suite.json',opt.CONFIG/'PREFLIGHT.json',opt.CONFIG/'CPU_TESTS.log']
    atomic_json(opt.CONFIG/'ACCEPTANCE.json',dict(passed=True,kind='non_training_cpu',at=opt.now(),versions=versions,python=platform.python_version(),
                runtime_hashes={str(p):file_sha256(p) for p in paths}))
    opt.gate(True,False);print('PASS: CPU contracts, source/data/weights, six independent heads, scheduler and resume regressions')

if __name__=='__main__':main()
