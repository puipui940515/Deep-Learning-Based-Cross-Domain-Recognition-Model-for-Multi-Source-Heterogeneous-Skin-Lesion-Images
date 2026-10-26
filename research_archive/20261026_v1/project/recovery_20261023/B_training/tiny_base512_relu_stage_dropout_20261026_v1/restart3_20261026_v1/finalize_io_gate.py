"""Freeze IO repair validation and reused model/GPU evidence for replacement run."""
from pathlib import Path
import ast,importlib.metadata,json,os,platform,shutil,sys
OUT=Path(__file__).resolve().parent;PROJECT=OUT.parents[3];AREA=PROJECT/'資料治理與泛化修復'
sys.path.insert(0,str(AREA/'scripts'))
import v2_relu_dropout_contract as c
from training_state import atomic_json,file_sha256

def main():
    if (c.RESULTS/'EXECUTION_GATE.json').exists() or (c.RESULTS/'state.json').exists() or (c.RESULTS/'STOP').exists():
        raise RuntimeError('Existing/stopped execution: no overwrite or duplicate')
    io=c.read(OUT/'IO_VALIDATION.json');reuse=c.read(OUT/'REUSED_EVIDENCE.json')
    assert io['status']=='passed' and io['case_count']==6 and io['all_six_formal_paths_covered']
    assert io['training_state_sha256']==file_sha256(AREA/'scripts/training_state.py') and io['actual_fsync_calls']>0
    assert reuse['status']=='passed_reused' and reuse['new_GPU_prechecks']==0
    assert {key:importlib.metadata.version(key) for key in reuse['versions']}==reuse['versions'] and platform.python_version()==reuse['python']
    for size in ('tiny','base'):
        for category in ('CPU','GPU'):
            item=reuse[category][size];assert file_sha256(item['receipt'])==item['sha256'] and c.read(item['receipt'])['status']=='passed'
        proof=c.gpu_evidence(size);assert proof['native_train_epoch'] and proof['actual_AdamW_step']==1 and proof['backbone_updated']
    for candidate in c.CANDIDATES:c.validate_candidate(c.read(c.CONFIG/(candidate+'.json')))
    old_run=c.STUDY_RESULTS/'executions/restart2_20261026_v1/runs/v2in_tiny512_relu_stage_dropout/regularized_seed1/run_inputs.json'
    c.verify_initialization(c.read(old_run))  # Saved initial identity only, not a new run or Resume.
    for path in (AREA/'scripts/training_state.py',AREA/'scripts/v2_relu_dropout_contract.py',AREA/'scripts/run_v2_relu_dropout.py'):
        ast.parse(path.read_text(encoding='utf-8-sig'))
    files=[AREA/'scripts'/name for name in ('training_state.py','train_regularized.py','model_profiles.py','v2_relu_stage_dropout.py',
        'v2_relu_dropout_contract.py','run_v2_relu_dropout.py','v2_opt_contract.py','run_v2_alpha025.py','coverage_sampler.py')]
    files += [PROJECT/'第二階段/src/stage2'/name for name in ('models.py','engine.py','metrics.py')]
    files += list(c.CONFIG.glob('*'))+list(OUT.glob('*.py'))+[OUT/'RESTART_AUTHORIZATION.md',OUT/'REUSED_EVIDENCE.json',OUT/'REPLACEMENT_ACCOUNTING.json',OUT/'RESTART_RECEIPT.json',OUT/'IO_VALIDATION.json']
    for size in ('tiny','base'):
        files += [Path(reuse[category][size]['receipt']) for category in ('CPU','GPU')]+[c.BASE_CONFIGS[size]]
        for seed in (1,2,3):files += [c.reference_folder(size,seed)/name for name in ('run_inputs.json','result.json')]
    files += [AREA/'config.json',old_run,OUT.parent/'restart2_20261026_v1/FORMAL_STOP_RECEIPT.json']
    files=list(dict.fromkeys(files));hashes={str(path):file_sha256(path) for path in files}
    def extended(path):return Path('\\\\?\\'+str(path.absolute())) if os.name=='nt' else path
    for path in files:
        target=extended(c.RESULTS/'sources_runtime'/path.relative_to(PROJECT));target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():raise RuntimeError('Existing source snapshot retained')
        shutil.copy2(extended(path),target)
    proof=dict(version=c.VERSION,execution_revision=c.EXECUTION_REV,dispatch_token=c.DISPATCH_TOKEN,execution_authorized=True,
        cpu_passed=True,gpu_passed=True,CPU_architecture_reused=True,GPU_evidence_reused=True,new_GPU_prechecks=0,
        IO_validation_passed=True,authorized_replacement_start_for_run='9b38f8536746431b84a42f25d307569b',
        limits=c.LIMITS,jobs=c.JOBS,versions=reuse['versions'],python=reuse['python'],frozen_files=hashes)
    atomic_json(c.RESULTS/'EXECUTION_GATE.json',proof);c.gate()
    atomic_json(OUT/'READY_RECEIPT.json',dict(status='ready_not_started',at=c.now(),gate_sha256=file_sha256(c.RESULTS/'EXECUTION_GATE.json'),
        IO_validation='six deeper isolated paths; native atomic/fsync/two-generation/index/best/restore checks passed',
        CPU_GPU_reexecuted=False,authorized_replacement_starts=1,current_model_seed_tasks=6,max_committed_epochs=180,results=str(c.RESULTS)))
    print(json.dumps(dict(status='ready_not_started',gate_sha256=file_sha256(c.RESULTS/'EXECUTION_GATE.json'),IO_cases=6,new_GPU_prechecks=0),ensure_ascii=False))

if __name__=='__main__':main()
