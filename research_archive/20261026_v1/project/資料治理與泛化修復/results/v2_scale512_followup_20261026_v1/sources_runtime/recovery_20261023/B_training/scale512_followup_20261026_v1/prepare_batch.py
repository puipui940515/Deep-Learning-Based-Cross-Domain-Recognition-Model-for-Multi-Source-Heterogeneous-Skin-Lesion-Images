"""Materialize the authorized batch, CPU dispatch tests and reproducibility gate."""
from __future__ import annotations
import ast
import copy
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from types import SimpleNamespace

OUT=Path(__file__).resolve().parent
PROJECT=OUT.parents[2]
AREA=PROJECT/'資料治理與泛化修復'
sys.path.insert(0,str(AREA/'scripts'))
import v2_scale_followup_contract as c
from training_state import atomic_json,file_sha256

def new_json(path,value):
    if path.exists():raise RuntimeError('Refuse to overwrite prepared artifact: '+str(path))
    atomic_json(path,value)

def require_raises(fn):
    try:fn()
    except (RuntimeError,KeyError):return
    raise AssertionError('Invalid admission unexpectedly accepted')

def main():
    if (OUT/'PREPARED.json').exists():
        print('Existing prepared package retained; inspect status, do not repeat launch.');return
    for path in (c.CONFIG,c.RESULTS):
        if path.exists():raise RuntimeError('Existing target; inspect partial state before continuing: '+str(path))
    old_gate=c.read(c.OLD_RESULTS/'EXECUTION_GATE.json')
    for path,sha in old_gate['frozen_files'].items():
        path=Path(path)
        if path.name in ('train_regularized.py','model_profiles.py'):
            path=OUT/'before'/path.name
        if file_sha256(path)!=sha:raise RuntimeError('Old compatible evidence changed before followup: '+str(path))
    versions={name:importlib.metadata.version(name) for name in old_gate['versions']}
    if versions!=old_gate['versions'] or platform.python_version()!=old_gate['python']:raise RuntimeError('Environment invalidates reused evidence')
    old_final=c.read(c.OLD_RESULTS/'FINAL_RESULTS.json')
    if old_final['status']!='completed_with_skips':raise RuntimeError('Old study not closed')
    numeric_path=PROJECT/'recovery_20261023/D_v2_analysis/scale512_review_20261026_v1/NUMERIC_ANALYSIS.json'
    numeric=c.read(numeric_path)
    if numeric['proposed_budget']['max_complete_epochs']!=90:raise RuntimeError('D draft budget conflict')
    for size in ('base','large'):
        proof=c.read(c.OLD_RESULTS/'preflight'/f'{size}_micro2.json')
        if not (proof['status']=='passed' and proof['optimizer_state_allocated'] and proof['backbone_update_observed']
                and proof['micro_batch']==2 and proof['accumulation']==32 and len(proof['cycles'])==2):raise RuntimeError('Micro2 evidence gap')
    serialization=PROJECT/'recovery_20261023/B_training/scale512_seed1_20261025_v1/large_resume2_20261025_v1/SERIALIZATION_CHECK.json'
    if c.read(serialization)['status']!='passed':raise RuntimeError('Saved serialization evidence not passed')
    restored=c.read(serialization.parent/'RESTORED_STATE.json')
    driver=subprocess.run(['nvidia-smi','--query-gpu=driver_version','--format=csv,noheader'],capture_output=True,text=True,check=True,timeout=8).stdout.strip()
    if driver!=restored['cuda']['driver']:raise RuntimeError('Driver changed since applicable successful GPU execution; report gap without new GPU tests')
    c.CONFIG.mkdir();c.RESULTS.mkdir()
    for name in ('logs','attempts','budget','sources_runtime'):(c.RESULTS/name).mkdir()
    draft=PROJECT/'recovery_20261023/D_v2_analysis/scale512_review_20261026_v1/B_NEXT_BATCH_DRAFT.md'
    authorization=('使用者2026-10-26在本B對話明確核定完整D草案並授權：\n'
        '「我正式核定上方完整草案，授權B完成必要準備後，依固定順序執行這三個新run；最多90完整Epoch，其餘範圍、保護與停止規則全部照草案，不追加研究。」\n\n'
        '固定Base512 Seed2、Base512 Seed3、Large512 Seed1；全部micro2×accum32。各新初始化一次、新RunID／head、空optimizer，不Resume。\n'
        '本批3新run／90完整Epoch／各Max30；無wall-clock硬上限。異常即整批停止，不自動重試、Resume、換batch或追加候選。\n'
        '原Train18919／Monitor1500／Val3611七類／512完整前處理、釘選本機FCMAE ImageNet1K；無下載、安裝、Windows變更或Test。\n'
        'alpha.5、三來源各1/3、有放回抽樣、LR1e-4、AdamW WD.05 LD1、LS.1 MixUp.2 RE.15 clip1 AMP、workers4 prefetch4 persistent。\n'
        'Min12 Max30 Patience5 MinDelta0 CosineTmax30 eta_min1e-6，首次最高Robust；原STOP／整輪非有限／Checkpoint與原啟動資源政策。\n'
        'Base S1及Tiny三Seed引用既有結果；Large2主對照舊Large1，不是純MixUp因果／正式採納。每15秒MONITOR，交總控供D判讀；不聯絡其他Thread或修改共用索引／網站。\n\n'
        '完整核定草案來源：'+str(draft)+'\nSHA256：'+file_sha256(draft)+'\n\n'+draft.read_text(encoding='utf-8'))
    (c.CONFIG/'AUTHORIZATION.md').write_text(authorization,encoding='utf-8')
    specs=c.read(c.OLD_CONFIG/'WEIGHT_SPECS.json')
    new_json(c.CONFIG/'WEIGHT_SPECS.json',{key:specs[key] for key in ('base','large')})
    for candidate in c.CANDIDATES:new_json(c.CONFIG/(candidate+'.json'),c.expected_config(candidate))
    previous_policy=AREA/'configs/v2_512_alpha025_20261024_v1/EVALUATION_CONTRACT.json'
    historical=c.read(previous_policy)
    base={key:copy.deepcopy(historical[key]) for key in ('seeds','all_three_required','mean_and_sample_sd_ddof','delta_units','combine_conditions',
        'robust','mean_delta_min','NV_strict_improvement','other_supported_disease_mean_delta_min','other_supported_disease_keys','PAD_DF_VASC','validation_usage')}
    base.update(primary_contrast='new Base seeds1/2/3 minus original Tiny512 same seeds; Base1 reused',prospective_for_new_candidate=True,
        retrospective_seed1_already_observed=True,not_rewriting_old_scale_or_alpha_decision=True)
    guards=dict(base['mean_delta_min']);guards.update({key:-.05 for key in base['other_supported_disease_keys']})
    large=dict(primary_contrast='new Large Seed1 micro2 minus saved Large Seed1 micro1 best epoch11',
        auxiliary_comparisons=['saved Base Seed1 micro2','saved Tiny512 Seed1'],seed=1,robust_signal_min=.01,
        robust_nonpositive_not_supporting=True,delta_min=guards,NV_strict_OR_required=False,
        between_0_and_1pp_or_guard_loss='small benefit/tradeoff/undetermined; D interprets',formal_adoption=False,pure_mixup_causality=False,
        automatic_large_seed2_3=False)
    policy=dict(version=c.VERSION,status='prospective_user_approved_before_new_training',draft_source=str(draft),draft_sha256=file_sha256(draft),
        historical_numeric_source=str(previous_policy),historical_numeric_sha256=file_sha256(previous_policy),
        base_confirmation=base,large_micro2_diagnostic=large,automatic_model_or_website_adoption=False,test_used=False)
    new_json(c.CONFIG/'EVALUATION_CONTRACT.json',policy)
    changes={}
    for candidate,(size,_) in c.CANDIDATES.items():
        before=c.read(c.OLD_CONFIG/f'v2in_scale512_{size}.json');after=c.read(c.CONFIG/(candidate+'.json'))
        changes[candidate]=dict(scientific_training_changes={key:{'before':before['training'][key],'after':value} for key,value in after['training'].items() if before['training'][key]!=value},
            new_seed_list=after['formal_suite']['seeds'],weight_spec_unchanged=after['experiment']['weights']==before['experiment']['weights'])
    assert changes['v2in_scale512_base_confirm']['scientific_training_changes']=={}
    assert set(changes['v2in_scale512_large_micro2']['scientific_training_changes'])=={'batch_size','gradient_accumulation'}
    new_json(c.CONFIG/'CONFIG_DIFF.json',changes)
    checks=[]
    # Minimal AST proof that additions are dispatch-only, not training math.
    def stripped(tree):
        class Strip(ast.NodeTransformer):
            def visit_If(self,node):
                node=self.generic_visit(node)
                text=ast.unparse(node.test)
                if 'v2_scale512_followup_20261026_v1' in text or 'v2in_scale512_base_confirm' in text:
                    return node.orelse
                return node
        return ast.dump(Strip().visit(tree),include_attributes=False)
    for name in ('train_regularized.py','model_profiles.py'):
        before=ast.parse((OUT/'before'/name).read_text(encoding='utf-8-sig'));after=ast.parse((AREA/'scripts'/name).read_text(encoding='utf-8-sig'))
        assert ast.dump(before,include_attributes=False)==stripped(after)
        checks.append(name+': AST unchanged after removing only new dispatch branches')
    for path in [Path(__file__),AREA/'scripts/v2_scale_followup_contract.py',AREA/'scripts/run_v2_scale_followup.py']:
        ast.parse(path.read_text(encoding='utf-8'));checks.append(path.name+': syntax passed')
    import model_profiles as profile
    for candidate in c.CANDIDATES:
        cfg=c.read(c.CONFIG/(candidate+'.json'));c.validate_candidate(cfg);profile.validate_profile(cfg,formal=True)
        for key,value in [('learning_rate',2e-4),('batch_size',1),('class_balance_alpha',.25),('num_workers',0),('epochs',31)]:
            wrong=copy.deepcopy(cfg);wrong['training'][key]=value;require_raises(lambda:c.validate_candidate(wrong))
        checks.append(candidate+': exact recipe and forbidden change rejection')
    assert base['mean_delta_min']==historical['mean_delta_min'] and len(base['other_supported_disease_keys'])==12
    assert len(guards)==25 and not large['NV_strict_OR_required']
    checks.append('prospective Base 31 numerical terms and Large n1 guard magnitudes copied unchanged; no n3 or NV OR imposed on Large')
    real_read,real_gate=c.read,c.gate
    saved_env={key:os.environ.get(key) for key in ('SKINDETECT_OPT_TOKEN','SKINDETECT_OPT_VERSION')}
    os.environ.update(SKINDETECT_OPT_TOKEN='CPU_BOUNDARY_TOKEN',SKINDETECT_OPT_VERSION=c.VERSION)
    try:
        c.gate=lambda:None
        for job,candidate,seed,size in c.JOBS:
            cfg=real_read(c.CONFIG/(candidate+'.json'))
            active=dict(job=job,candidate=candidate,seed=seed,token='CPU_BOUNDARY_TOKEN')
            c.read=lambda path,active=active: {'active':active} if Path(path)==c.RESULTS/'state.json' else real_read(path)
            args=SimpleNamespace(formal=True,require_cuda=True,resume=False,seed=seed,config=c.CONFIG/(candidate+'.json'),output_root=c.RESULTS/'runs'/candidate)
            c.validate_execution(cfg,args)
            for key,value in [('resume',True),('seed',17),('formal',False),('require_cuda',False),('output_root',c.OLD_RESULTS/'runs'/candidate)]:
                invalid=copy.copy(args);setattr(invalid,key,value);require_raises(lambda:c.validate_execution(cfg,invalid))
            active['token']='wrong';require_raises(lambda:c.validate_execution(cfg,args))
            # Contract-only fixture copies saved IDs; no image/model/weight access.
            fixture=copy.deepcopy(real_read(c.TINY/f'regularized_seed{seed}/run_inputs.json'))
            fixture.update(seed=seed,initial_classifier_sha256='a'*64,initial_optimizer_state_entries=0,effective_training_config=cfg['training'])
            fixture['contract'].update(seed=seed,experiment_id=candidate,pretrained_sha256=cfg['experiment']['weights']['sha256'],
                effective_transforms=real_read(c.OLD_RESULTS/'runs/v2in_scale512_base/regularized_seed1/run_inputs.json')['contract']['effective_transforms'])
            if seed==1:fixture['initial_classifier_sha256']=real_read(c.OLD_RESULTS/'preflight/large_micro2.json')['initial_classifier_sha256']
            c.verify_initialization(fixture)
            invalid=copy.deepcopy(fixture);invalid['initial_optimizer_state_entries']=1;require_raises(lambda:c.verify_initialization(invalid))
            checks.append(job+': fresh seed/config/token/output admission, Resume rejection, saved data contract; seed2/3 accepted without Seed1 head equality')
    finally:
        c.read,c.gate=real_read,real_gate
        for key,value in saved_env.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value
    actual_root,actual_summary=c.RESULTS,c.budget_summary
    scratch=OUT/'cpu_budget_fixture';scratch.mkdir();(scratch/'budget').mkdir()
    old_token=os.environ.get('SKINDETECT_OPT_TOKEN');os.environ['SKINDETECT_OPT_TOKEN']='CPU_BOUNDARY_TOKEN'
    try:
        c.RESULTS=scratch
        budget=c.EpochBudget(real_read(c.CONFIG/'v2in_scale512_base_confirm.json'),2,'cpu_fixture')
        assert budget.begin(1);require_raises(lambda:budget.begin(1))
        budget.finish(dict(epoch=1,file='fixture_only',sha256='fixture'))
        require_raises(lambda:budget.begin(1));require_raises(lambda:budget.begin(3))
        (scratch/'STOP').touch();assert budget.begin(2) is False
        c.budget_summary=lambda:dict(active=[],completed_epoch_segments=90,events=[])
        require_raises(lambda:budget.begin(2))
        c.budget_summary=lambda:dict(active=[],completed_epoch_segments=1,events=[dict(candidate=budget.candidate,seed=2,run_id='another',epoch=1,committed=True)])
        require_raises(lambda:budget.begin(2))
        checks.append('original-style epoch lease/STOP/90-epoch cap, sequence gaps, repeated epochs and different run IDs rejected in CPU fixture only')
    finally:
        c.RESULTS,c.budget_summary=actual_root,actual_summary
        if old_token is None:os.environ.pop('SKINDETECT_OPT_TOKEN',None)
        else:os.environ['SKINDETECT_OPT_TOKEN']=old_token
    if 'torch' in sys.modules or 'timm' in sys.modules:raise RuntimeError('CPU dispatch checks unexpectedly imported model runtime')
    new_json(OUT/'CPU_CHECKS.json',dict(status='passed',checks=checks,model_runtime_imported=False,gpu_tests_repeated=False,
        old_serialization_receipt=str(serialization),old_serialization_sha256=file_sha256(serialization)))
    new_json(OUT/'REUSED_EVIDENCE.json',dict(versions=versions,python=platform.python_version(),driver=driver,
        reused_micro2=[str(c.OLD_RESULTS/'preflight'/f'{size}_micro2.json') for size in ('base','large')],
        prior_successful_driver_evidence=str(serialization.parent/'RESTORED_STATE.json'),scientific_math_AST_unchanged=True,
        no_new_preflight_benchmark_install_download=True,old_study_closed=True,old_gate_sha256=file_sha256(c.OLD_RESULTS/'EXECUTION_GATE.json')))
    files=[AREA/'scripts'/name for name in ('train_regularized.py','model_profiles.py','v2_scale_followup_contract.py','run_v2_scale_followup.py',
        'training_state.py','v2_opt_contract.py','run_v2_alpha025.py','coverage_sampler.py')]
    files += [PROJECT/'第二階段/src/stage2'/name for name in ('models.py','engine.py','metrics.py')]
    files += list(c.CONFIG.glob('*'))+[Path(__file__),OUT/'CPU_CHECKS.json',OUT/'REUSED_EVIDENCE.json',draft,numeric_path,draft.with_name('REPORT.md'),previous_policy]
    files += [c.OLD_CONFIG/f'v2in_scale512_{size}.json' for size in ('base','large')]
    files += [c.OLD_RESULTS/'preflight'/f'{size}_micro2.json' for size in ('base','large')]
    files += [AREA/'config.json',serialization,c.OLD_RESULTS/'FINAL_RESULTS.json']
    for folder in [c.TINY/f'regularized_seed{s}' for s in (1,2,3)]+[c.OLD_RESULTS/'runs'/f'v2in_scale512_{size}'/'regularized_seed1' for size in ('base','large')]:
        files += [folder/'result.json',folder/'run_inputs.json']
    for path in files:
        target=c.RESULTS/'sources_runtime'/path.relative_to(PROJECT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    proof=dict(version=c.VERSION,execution_authorized=True,cpu_passed=True,limits=c.LIMITS,jobs=c.JOBS,
        versions=versions,python=platform.python_version(),driver=driver,frozen_files={str(path):file_sha256(path) for path in files})
    new_json(c.RESULTS/'EXECUTION_GATE.json',proof);c.gate()
    new_json(OUT/'PREPARED.json',dict(status='prepared_not_started',at=c.now(),jobs=c.JOBS,gate_sha256=file_sha256(c.RESULTS/'EXECUTION_GATE.json'),
        config_diff=changes,checks=len(checks),command=sys.argv,python=sys.executable))
    print(json.dumps(dict(status='prepared_not_started',checks=len(checks),jobs=c.JOBS,gate_sha256=file_sha256(c.RESULTS/'EXECUTION_GATE.json')),ensure_ascii=False))

if __name__=='__main__':main()
