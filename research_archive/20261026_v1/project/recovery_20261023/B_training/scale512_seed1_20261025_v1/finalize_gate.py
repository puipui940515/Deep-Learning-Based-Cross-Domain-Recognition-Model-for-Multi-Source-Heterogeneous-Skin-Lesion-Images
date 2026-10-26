"""Freeze measured microbatch choices and current minimal integration, no GPU tests."""
import ast
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import sys
OUT=Path(__file__).resolve().parent;PROJECT=OUT.parents[2];AREA=PROJECT/'資料治理與泛化修復'
sys.path.insert(0,str(AREA/'scripts'))
import v2_scale_contract as c
import model_profiles as profile
from training_state import atomic_json,file_sha256
if (c.RESULTS/'state.json').exists() or (c.RESULTS/'EXECUTION_GATE.json').exists():raise RuntimeError('Existing execution gate/state must be reused, not overwritten')
selection=c.read(c.RESULTS/'preflight/SELECTION.json')
assert set(selection)==set(c.SIZES)
checks=[]
startup=c.read(c.RESULTS/'preflight/STARTUP.json')
for size in c.SIZES:
    cfg=c.read(c.CONFIG/f'v2in_scale512_{size}.json');profile.validate_profile(cfg,formal=True)
    if selection[size]['status']=='passed':
        accepted=c.read(selection[size]['evidence'])
        assert cfg['training']['batch_size']==accepted['micro_batch'] and cfg['training']['gradient_accumulation']==accepted['accumulation']
        assert accepted['optimizer_state_allocated'] and accepted['backbone_update_observed'] and len(accepted['cycles'])==2
        assert accepted['peak_reserved_bytes']<=startup['gpu']['free_mib']*2**20,'Selected configuration would rely on memory beyond free dedicated VRAM'
        all_passed=[c.read(p) for p in (c.RESULTS/'preflight').glob(size+'_micro*.json') if c.read(p)['status']=='passed']
        assert accepted['steady_train_images_per_second']==max(p['steady_train_images_per_second'] for p in all_passed)
        assert len({p['initial_classifier_sha256'] for p in all_passed})==1
        checks.append(size+'_measured_choice_optimizer_allocation_backbone_update_and_VRAM')
    else:
        assert size=='huge' and selection[size]['status']=='skipped_infeasible_estimate'
        assert selection[size]['lower_bound_gib']>selection[size]['free_vram_gib']
        checks.append('huge_estimated_before_GPU_no_forced_run')
def node(text,name):return ast.dump(next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name==name),include_attributes=False)
before=(OUT/'before/train_regularized.py').read_text(encoding='utf-8')
current=(AREA/'scripts/train_regularized.py').read_text(encoding='utf-8')
for name in ('train_epoch','evaluate','supported_source_metrics','build_transform'):
    assert node(before,name)==node(current,name);checks.append(name+'_calculation_unchanged')
paths=[AREA/'scripts/train_regularized.py',AREA/'scripts/model_profiles.py',AREA/'scripts/v2_scale_contract.py',AREA/'scripts/run_v2_scale512.py',
       AREA/'scripts/run_v2_alpha025.py',AREA/'scripts/training_state.py',AREA/'scripts/v2_opt_contract.py',AREA/'scripts/coverage_sampler.py',
       PROJECT/'第二階段/src/stage2/models.py',PROJECT/'第二階段/src/stage2/engine.py',PROJECT/'第二階段/src/stage2/metrics.py']
for p in paths:ast.parse(p.read_text(encoding='utf-8'))
assert file_sha256(AREA/'config.json')==c.read(c.BASE_CONFIG)['formal_suite']['baseline_config_sha256']
protected=c.read(OUT/'PROTECTED_INPUTS.json');assert all(file_sha256(p)==h for p,h in protected.items())
checks+=['all_integrated_sources_syntax','baseline_config_identity','existing_unrelated_files_retained','passive_monitor_and_validation_timing_only']
assert not any(p in sys.modules for p in ('torch','timm','torchvision'))
atomic_json(OUT/'FINAL_CPU_CHECKS.json',dict(status='passed',checks=checks,no_new_GPU_work=True,old_CPU_checks=str(OUT/'CPU_CHECKS.json')))
frozen=paths+[AREA/'scripts/Start-V2Scale512.ps1',c.BASE_CONFIG,AREA/'config.json',c.RESULTS/'preflight/SELECTION.json',OUT/'FINAL_CPU_CHECKS.json',OUT/'CPU_CHECKS.json']
frozen+=list(c.CONFIG.glob('*'))
frozen+=[Path(r['evidence']) for r in selection.values() if r['status']=='passed']
for path in paths:
    dest=c.RESULTS/'sources_runtime'/path.relative_to(PROJECT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
proof=dict(version=c.VERSION,execution_authorized=True,cpu_passed=True,limits=c.LIMITS,
    versions={p:importlib.metadata.version(p) for p in ('torch','torchvision','timm','numpy','Pillow')},python=platform.python_version(),
    frozen_files={str(p):file_sha256(p) for p in frozen},
    accepted_preflight=selection,resource_policy='original startup-only; no runtime resource thresholds',
    formal_initialization='new pinned ImageNet1K FCMAE backbone + independent Seed1 7-class head; never preflight state or old best',
    screen_limitations='single Seed; microbatch changes local MixUp pairing; Large micro1 has self pairing',
    test_used=False,automatic_model_adoption=False)
atomic_json(c.RESULTS/'EXECUTION_GATE.json',proof)
c.gate()
print(json.dumps(dict(status='new_scale_gate_ready',passed=checks,microbatches={s:r.get('micro_batch') for s,r in selection.items()}),ensure_ascii=False))
