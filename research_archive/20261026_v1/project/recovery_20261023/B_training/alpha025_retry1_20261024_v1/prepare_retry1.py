"""Narrow authorization/source/retry binding only. No model or GPU tests."""
import ast
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import sys
from datetime import datetime

REVISION='retry1_20261024_v1'
os.environ['SKINDETECT_ALPHA025_EXECUTION']=REVISION
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
SCRIPTS=ROOT/'資料治理與泛化修復/scripts'
sys.path.insert(0,str(SCRIPTS))
import v2_alpha025_contract as c
from training_state import atomic_json,file_sha256

def fn(path,name):
    return next(x for x in ast.parse(path.read_text(encoding='utf-8-sig')).body if isinstance(x,ast.FunctionDef) and x.name==name)

def main():
    checks=[]
    def verify(name,ok):
        checks.append(dict(name=name,passed=bool(ok)))
        if not ok:raise RuntimeError(name)
    if c.RESULTS.exists():raise RuntimeError('Retry1 already prepared; preserve and inspect, never duplicate')
    parent=c.read(c.STUDY_ROOT/'state.json')
    verify('parent_failed_zero_complete_epochs',parent['status']=='failed' and parent['runs']['1']['run_id']=='d87cb2eef21d47fc8a408aa16b70e641' and not (c.STUDY_ROOT/'runs'/c.CANDIDATE/'regularized_seed1/checkpoints/index.json').exists())
    verify('parent_STOP_preserved',(c.STUDY_ROOT/'STOP').is_file())
    verify('parent_gate_unchanged',file_sha256(c.STUDY_ROOT/'EXECUTION_GATE.json')==parent['gate_sha256'])
    previous=[c.read(p) for p in (c.STUDY_ROOT/'attempts').glob('attempt_*.json')]
    verify('exactly_one_parent_failed_attempt',len(previous)==1 and previous[0]['status']=='failed' and previous[0]['seed']==1)
    for p in (c.STUDY_ROOT/'budget').glob('epoch_*.json'):
        verify('no_parent_completed_epoch_or_active_lease',c.read(p)['committed'] is False and c.read(p)['status']=='interrupted')
    verify('execution_is_distinct',c.RESULTS==c.STUDY_ROOT/'executions'/REVISION and c.execution_root('')==c.STUDY_ROOT)
    try:c.execution_root('retry2')
    except RuntimeError:verify('arbitrary_retry_root_rejected',True)
    else:verify('arbitrary_retry_root_rejected',False)
    # The scientific delivery is preserved; only the new execution metadata changes.
    qa=c.read(c.CONFIG/'STATIC_QA.json')
    for name,sha in qa['output_sha256'].items():verify('C_file:'+name,file_sha256(c.CONFIG/name)==sha)
    config=c.read(c.CONFIG/(c.CANDIDATE+'.json'));c.validate_candidate(config)
    verify('C_training_matches',config['training']==c.read(c.CONFIG/'PLANNED_EFFECTIVE_CONTRACT.json')['training'])
    restoration=ROOT/'recovery_20261023/B_training/alpha025_stop_policy_restore_20261024_v1'
    revision=c.read(restoration/'REVISION.json')
    trainer_sha=next(x['sha256'] for x in revision['source_files'] if x['path'].endswith('train_regularized.py'))
    verify('restored_trainer_unmodified',file_sha256(SCRIPTS/'train_regularized.py').lower()==trainer_sha.lower())
    before=OUT/'before/run_v2_alpha025.py'
    for name in ('schedule_check','process_conflicts','run_seed','memory','gpu_metadata'):
        verify('restored_policy_unchanged:'+name,ast.dump(fn(before,name),include_attributes=False)==ast.dump(fn(SCRIPTS/'run_v2_alpha025.py',name),include_attributes=False))
    verify('finite_workload_unbounded_time',c.LIMITS=={'runs':3,'epochs':90,'max_epochs_per_run':30,'wall_clock_cap_seconds':None,'time_limit_mode':'explicit_unbounded_elapsed_time_finite_workload'})
    for p in (SCRIPTS/'run_v2_alpha025.py',SCRIPTS/'v2_alpha025_contract.py',Path(__file__)):
        ast.parse(p.read_text(encoding='utf-8-sig'))
    verify('no_torch_import','torch' not in sys.modules)
    original=c.read(c.STUDY_ROOT/'EXECUTION_GATE.json')
    # Metadata-only continuity check; not a repeated environment validation.
    for name,version in original['versions'].items():verify('version_continuity:'+name,importlib.metadata.version(name)==version)
    sources=[SCRIPTS/n for n in ('run_v2_alpha025.py','v2_alpha025_contract.py','model_profiles.py','train_regularized.py','training_state.py','coverage_sampler.py','v2_opt_contract.py','Start-V2Alpha025Retry1.ps1')]
    sources += [ROOT/'第二階段/src/stage2'/n for n in ('models.py','engine.py','metrics.py')]
    # Keep all immutable previous frozen inputs (never edit their recorded hashes).
    frozen=[Path(p) for p in original['frozen_files'] if Path(p).is_file()]
    frozen += sources+[OUT/'AUTHORIZATION.md',Path(__file__),c.STUDY_ROOT/'EXECUTION_GATE.json',c.STUDY_ROOT/'state.json',c.STUDY_ROOT/'STOP']
    frozen += list((c.STUDY_ROOT/'attempts').glob('*.json'))+list((c.STUDY_ROOT/'budget').glob('*.json'))
    c.RESULTS.mkdir(parents=True)
    for name in ('attempts','budget','logs','sources_runtime'):(c.RESULTS/name).mkdir()
    for p in sources:
        dest=c.RESULTS/'sources_runtime'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    gate=dict(version=c.VERSION,execution_revision=REVISION,at=datetime.now().astimezone().isoformat(),
        execution_authorized=True,fresh_initializations_per_seed={'1':1,'2':1,'3':1},
        parent_failed_run_id='d87cb2eef21d47fc8a408aa16b70e641',parent_failed_attempt_seconds=sum(p['seconds'] for p in previous),
        parent_failed_results_root=str(c.STUDY_ROOT),parent_gate_sha256=parent['gate_sha256'],
        B_authorization_source=str(OUT/'AUTHORIZATION.md'),limits=c.LIMITS,
        cpu_compatibility_passed=True,cpu_basis='reuse restoration verification; only current authorization/source/retry checks added',
        narrow_checks=checks,versions=original['versions'],python_version=original['python_version'],python=str(c.PYTHON),
        frozen_files={str(p):file_sha256(p) for p in frozen})
    atomic_json(c.RESULTS/'EXECUTION_GATE.json',gate)
    c.gate()
    atomic_json(OUT/'PREPARATION.json',dict(status='retry1_gate_prepared',execution_revision=REVISION,
        root=str(c.RESULTS),checks=checks,gate_sha256=file_sha256(c.RESULTS/'EXECUTION_GATE.json'),
        training_started=False,resume=False,additional_CPU_suite_or_GPU_tests=False))
    print(json.dumps(dict(status='retry1_gate_prepared',root=str(c.RESULTS),narrow_checks=len(checks),no_torch='torch' not in sys.modules),ensure_ascii=False))

if __name__=='__main__':main()
