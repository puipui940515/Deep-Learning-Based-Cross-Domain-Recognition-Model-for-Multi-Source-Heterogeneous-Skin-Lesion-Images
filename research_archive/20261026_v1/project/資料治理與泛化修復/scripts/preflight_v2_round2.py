"""Non-training preflight; --verify-only checks the frozen accepted runtime."""
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from training_state import atomic_json,file_sha256
import v2_round2_contract as opt


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--verify-only',action='store_true');args=parser.parse_args()
    if args.verify_only:
        opt.gate();print('PASS: authorized candidate, source, configuration, baseline and non-training acceptance fingerprints');return
    if (opt.CONFIG/'ACCEPTANCE.json').exists():raise RuntimeError('Existing acceptance; use --verify-only, never overwrite')
    if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise RuntimeError('Non-training preflight must explicitly hide all CUDA devices')
    import torch
    import model_profiles as profiles
    import train_regularized as trainer
    from stage2.engine import seed_everything
    torch.set_num_threads(2)
    opt.gate(False)
    base=opt.read(opt.BASE_CONFIG)
    path,rows,provenance=trainer.load_governed_release(opt.AREA/'data/governed_18979_20261018_v1',base)
    counts={split:sum(r['split']==split for r in rows) for split in ('train','validation')}
    if counts!={'train':18919,'validation':3611}:raise RuntimeError('Formal dataset counts differ')
    if provenance['manifest_sha256']!=base['formal_suite']['manifest_sha256']:raise RuntimeError('Formal Manifest SHA differs')
    expected_versions={'torch':'2.11.0+cu128','torchvision':'0.26.0+cu128','timm':'1.0.30','numpy':'1.26.4','Pillow':'10.4.0'}
    versions={name:importlib.metadata.version(name) for name in expected_versions}
    if versions!=expected_versions:raise RuntimeError('Environment differs')
    identity=profiles.weight_identity(base)
    train_rows=[r for r in rows if r['split']=='train']
    policy_checks={}
    original_weights,original_audit=trainer.sample_weights(train_rows,.5)
    original_val=repr(trainer.build_transform(224,False))
    grouped={}
    for candidate in opt.CANDIDATES:
        config=opt.read(opt.CONFIG/(candidate+'.json'));profiles.validate_profile(config,True)
        weights,audit=trainer.sample_weights(train_rows,.5,config['training'].get('source_sampling_shares'))
        expectations=opt.sampling_expectations(train_rows,weights)
        requested=config['training'].get('source_sampling_shares',{s:1/3 for s in config['sources']})
        if not all(abs(audit['expected_source_share'][s]-q)<1e-10 for s,q in requested.items()):
            raise RuntimeError('Effective sampling source shares differ')
        p=config['training'].get('augmentation_overrides',{}).get('random_erasing_p',.15)
        transform=trainer.build_transform(224,True,random_erasing_p=p)
        if transform.transforms[-1].p!=p or repr(trainer.build_transform(224,False))!=original_val:
            raise RuntimeError('RandomErasing or Validation transform not applied exactly')
        policy_checks[candidate]=dict(source_shares=requested,audit=audit,expectations=expectations,train_transform=repr(transform),validation_transform=original_val)
        seed_everything(1);model=profiles.construct_model(config)
        if sum(type(m).__name__=='GlobalResponseNorm' for m in model.modules())!=18:raise RuntimeError('Not true V2 Tiny')
        initial=hashlib.sha256(profiles.classifier(model,'convnextv2_tiny').weight.detach().numpy().tobytes()).hexdigest()
        original=opt.read(opt.BASE_RESULTS/'regularized_seed1/run_inputs.json')
        if initial!=original['initial_classifier_sha256']:raise RuntimeError('Seed 1 initial head differs')
        optimizer,scheduler=profiles.optimizer_and_scheduler(model,config)
        if optimizer.state:raise RuntimeError('Optimizer is not empty')
        groups=opt.describe_groups(model,optimizer)
        if len(groups)!=18:raise RuntimeError('Unexpected V2 parameter grouping')
        names=[name for g in groups for name in g['parameter_names']]
        if len(names)!=len(set(names)) or set(names)!={n for n,p in model.named_parameters() if p.requires_grad}:raise RuntimeError('Parameter grouping missing or duplicated parameters')
        trajectory=[[g['lr'] for g in optimizer.param_groups]]
        for epoch in range(30):
            optimizer.step();scheduler.step() # No forward/backward or gradients, only scheduler clock.
            trajectory.append([g['lr'] for g in optimizer.param_groups])
        if not all(all(after<=before+1e-15 and after>=1e-6-1e-15 for before,after in zip(a,b)) for a,b in zip(trajectory,trajectory[1:])):
            raise RuntimeError('Cosine increases a group LR or violates eta_min')
        if not all(abs(lr-1e-6)<1e-12 for lr in trajectory[-1]):raise RuntimeError('Scheduler endpoint differs')
        stem=next(g['initial_lr'] for g in groups if any(n.startswith('stem.') for n in g['parameter_names']))
        expected_stem=config['training']['learning_rate']*config['training']['layer_decay']**8
        if abs(stem-expected_stem)>1e-15:raise RuntimeError('Stem LR does not match local depth map')
        grouped[candidate]=dict(groups=groups,all_31_lr_states=trajectory,initial_classifier_sha256=initial,
                                 initial_optimizer_state_entries=0,stem_lr=stem)
        del model,optimizer,scheduler
    train_transform=repr(trainer.build_transform(224,True));val_transform=repr(trainer.build_transform(224,False))
    if 'RandomErasing(p=0.15' not in train_transform or 'Random' in val_transform:raise RuntimeError('Transforms differ')
    # Existing accepted CPU tests plus candidate-specific regression. No GPU work.
    result=subprocess.run([sys.executable,'-B','-m','unittest','test_training_resume','test_model_profiles','test_v2_optimization','test_v2_round2','-v'],
                          cwd=opt.AREA/'scripts',capture_output=True,text=True,encoding='utf-8',env=dict(os.environ,PYTHONUTF8='1'))
    (opt.CONFIG/'CPU_TESTS.log').write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
    if result.returncode:raise RuntimeError('CPU regressions failed; see CPU_TESTS.log')
    report=dict(passed=True,kind='non_training_cpu',at=opt.now(),versions=versions,python=platform.python_version(),
                counts=counts,manifest_sha256=provenance['manifest_sha256'],weight_identity=identity,
                train_transform=train_transform,validation_transform=val_transform,grouped=grouped,policy_checks=policy_checks,
                cpu_test_log_sha256=file_sha256(opt.CONFIG/'CPU_TESTS.log'),cuda_training_or_gpu_resume_tested=False,
                sealed_test_content_read=False,baseline_profile_semantics_preserved=True)
    atomic_json(opt.CONFIG/'PREFLIGHT.json',report)
    paths=[opt.CONFIG/'suite.json',opt.CONFIG/'PREFLIGHT.json',opt.CONFIG/'CPU_TESTS.log']
    paths+=list(map(Path,opt.suite()['immutable_inputs']))
    runtime_hashes={str(p):file_sha256(p) for p in paths}
    atomic_json(opt.CONFIG/'ACCEPTANCE.json',dict(passed=True,kind='non_training_cpu',at=opt.now(),runtime_hashes=runtime_hashes))
    opt.gate();print(json.dumps(dict(passed=True,kind='non_training_cpu',candidate_groups={k:len(v['groups']) for k,v in grouped.items()},counts=counts,sealed_test_content_read=False),ensure_ascii=False))


if __name__=='__main__':main()
