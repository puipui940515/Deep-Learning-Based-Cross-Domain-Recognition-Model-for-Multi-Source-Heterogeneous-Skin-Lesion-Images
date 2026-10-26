"""Read only saved state/logs and preserve the actual formal checkpoint failure."""
from pathlib import Path
import ast,json,re,sys
OUT=Path(__file__).resolve().parent;PROJECT=OUT.parents[3];AREA=PROJECT/'資料治理與泛化修復'
sys.path.insert(0,str(AREA/'scripts'))
import v2_relu_dropout_contract as c
from training_state import atomic_json,file_sha256

def main():
    target=OUT/'FORMAL_STOP_RECEIPT.json'
    if target.exists():raise RuntimeError('Existing formal stop receipt retained')
    state=c.read(c.RESULTS/'state.json');assert state['status']=='failed' and state['active'] is None
    row=state['runs']['tiny_seed1'];folder=c.folder(row['candidate'],row['seed'])
    assert row['run_id']=='9b38f8536746431b84a42f25d307569b' and row['epochs_completed']==0 and (c.RESULTS/'STOP').exists()
    assert not (folder/'checkpoints/index.json').exists() and not (folder/'best.pt').exists()
    stderr=Path(row['stderr']).read_text(encoding='utf-8')
    match=re.findall(r"FileNotFoundError:.*?directory: ('.*')",stderr)
    if not match:raise RuntimeError('Expected actual checkpoint path exception not found')
    failed_path=ast.literal_eval(match[-1]);attempt=c.read(Path(row['attempt_receipt']))
    events=[c.read(path) for path in (c.RESULTS/'budget').glob('*.json')]
    data=dict(status='failed_checkpoint_write',at=c.now(),version=c.VERSION,execution_revision=c.EXECUTION_REV,
        run_id=row['run_id'],formal_runs_started=1,formal_complete_epochs=0,unstarted_jobs=[job for job,other in state['runs'].items() if other['status']=='pending'],
        reason='Windows file IO failed opening the atomic Checkpoint temporary filename at a 266-character path',
        actual_failed_path=failed_path,actual_failed_path_chars=len(failed_path),checkpoint_directory_exists=(folder/'checkpoints').is_dir(),
        indexed_checkpoint_exists=False,best_exists=False,resume_available=False,
        failure_before_torch_save=True,training_and_full_validation_reached_checkpoint_commit=True,
        CPU_architecture_reused=True,native_GPU_prechecks_passed=True,added_preAMP_gradient_stop=False,
        formal_attempt_seconds=attempt['seconds'],uncommitted_epoch_segments=events,
        accounting='uncommitted epoch seconds included in formal attempt; GPU/CPU prechecks and prior failures separate',
        model_quality_result_available=False,formal_peak_memory_recorded=False,
        source_gate_sha256=file_sha256(c.RESULTS/'EXECUTION_GATE.json'),traceback=stderr[stderr.rfind('Traceback (most recent call last):'):],
        sources_unchanged_after_launch=True,auto_retry=False,test_used=False,
        original_and_restart1_STOPs_preserved=(c.STUDY_RESULTS/'STOP').exists() and (c.STUDY_RESULTS/'executions/restart1_20261026_v1/STOP').exists(),
        next_minimum_fix='shorten the unique atomic temporary basename or use extended Windows IO paths, preserving same-directory atomic replace/fsync/two-generation protection; test at the real maximum output path using a tiny CPU payload',
        restart_limit='No committed Checkpoint: cannot Resume this run. Any later attempt requires explicit fresh Seed1 initialization authorization and new execution/gate; do not delete STOP or reuse old Run ID.')
    atomic_json(target,data)
    print(json.dumps({key:data[key] for key in ('status','run_id','formal_runs_started','formal_complete_epochs','actual_failed_path_chars','formal_attempt_seconds','resume_available')},ensure_ascii=False))

if __name__=='__main__':main()
