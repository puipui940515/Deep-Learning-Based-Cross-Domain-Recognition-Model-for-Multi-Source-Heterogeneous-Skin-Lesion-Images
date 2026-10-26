"""Freeze this successful native-flow verification and six-run authorization."""
from pathlib import Path
import importlib.metadata,json,platform,shutil,sys
OUT=Path(__file__).resolve().parent;PROJECT=OUT.parents[3];AREA=PROJECT/'資料治理與泛化修復'
sys.path.insert(0,str(AREA/'scripts'))
import v2_relu_dropout_contract as c
from training_state import atomic_json,file_sha256

def main():
    if (c.RESULTS/'EXECUTION_GATE.json').exists():raise RuntimeError('Existing gate preserved; do not overwrite')
    if (c.RESULTS/'STOP').exists() or (c.RESULTS/'state.json').exists():raise RuntimeError('Stopped or initialized execution; no duplicate')
    reused=c.read(OUT/'CPU_REUSE.json');checks=c.read(OUT/'CPU_DISPATCH_CHECKS.json')
    assert reused['status']=='passed_reused' and checks['status']=='passed'
    versions={name:importlib.metadata.version(name) for name in reused['versions']}
    assert versions==reused['versions'] and platform.python_version()==reused['python']
    gpu={size:c.read(c.RESULTS/'preflight'/f'{size}.json') for size in ('tiny','base')}
    for size,proof in gpu.items():
        assert proof['status']=='passed' and proof['native_train_epoch'] and not proof['added_preAMP_gradient_stop']
        assert proof['model_forwards']==1 and proof['optimizer_updates']==1 and proof['actual_AdamW_step']==1 and proof['backbone_updated']
        assert proof['loss_divisor']==64//c.MICRO[size] and proof['architecture_audit']==reused['evidence'][size]['architecture_audit']
        assert not proof['weights_reused_for_formal']
    for candidate in c.CANDIDATES:c.validate_candidate(c.read(c.CONFIG/(candidate+'.json')))
    files=[AREA/'scripts'/name for name in ('train_regularized.py','model_profiles.py','v2_relu_stage_dropout.py','v2_relu_dropout_contract.py',
        'run_v2_relu_dropout.py','training_state.py','v2_opt_contract.py','run_v2_alpha025.py','coverage_sampler.py')]
    files += [PROJECT/'第二階段/src/stage2'/name for name in ('models.py','engine.py','metrics.py')]
    files += list(c.CONFIG.glob('*'))+list(OUT.glob('*.py'))+[OUT/'RESTART_AUTHORIZATION.md',OUT/'CPU_REUSE.json',OUT/'CPU_DISPATCH_CHECKS.json',OUT/'RESTART_RECEIPT.json']
    files += [c.RESULTS/'preflight'/f'{size}.json' for size in ('tiny','base')]
    for size in ('tiny','base'):
        files += [Path(reused['evidence'][size]['receipt']),c.BASE_CONFIGS[size]]
        for seed in (1,2,3):files += [c.reference_folder(size,seed)/name for name in ('result.json','run_inputs.json')]
    files += [AREA/'config.json',OUT.parent/'CPU_tiny.json',OUT.parent/'STOPPED_RECEIPT.json',OUT.parent/'restart1_20261026_v1/STOPPED_RECEIPT.json',
        c.STUDY_RESULTS/'STOP',c.STUDY_RESULTS/'executions/restart1_20261026_v1/STOP',
        PROJECT/'recovery_20261023/B_training/model512_relu_stage_dropout_queue_20261026_v2/B_NEXT_TASK.md']
    files=list(dict.fromkeys(files));hashes={str(path):file_sha256(path) for path in files}
    for path in files:
        target=c.RESULTS/'sources_runtime'/path.relative_to(PROJECT);target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():raise RuntimeError('Existing source snapshot retained')
        shutil.copy2(path,target)
    gate=dict(version=c.VERSION,execution_revision=c.EXECUTION_REV,dispatch_token=c.DISPATCH_TOKEN,execution_authorized=True,
        cpu_passed=True,cpu_architecture_reused=True,gpu_passed=True,limits=c.LIMITS,jobs=c.JOBS,versions=versions,
        python=platform.python_version(),frozen_files=hashes,native_gradient_policy=True,additional_preAMP_gradient_stop=False)
    atomic_json(c.RESULTS/'EXECUTION_GATE.json',gate);c.gate()
    atomic_json(OUT/'READY_RECEIPT.json',dict(status='ready_not_started',at=c.now(),execution_revision=c.EXECUTION_REV,
        gate_sha256=file_sha256(c.RESULTS/'EXECUTION_GATE.json'),jobs=c.JOBS,limits=c.LIMITS,
        CPU_reused=True,GPU_actual_updates={size:proof['optimizer_updates'] for size,proof in gpu.items()},results=str(c.RESULTS)))
    print(json.dumps(dict(status='ready_not_started',gate_sha256=file_sha256(c.RESULTS/'EXECUTION_GATE.json'),
        gpu={size:{key:proof[key] for key in ('optimizer_updates','loss','amp_scale_before','amp_scale_after','peak_allocated_bytes')} for size,proof in gpu.items()}),ensure_ascii=False))

if __name__=='__main__':main()
