"""Close the failed single GPU precheck; preserve both preparation executions."""
from pathlib import Path
import json,shutil,sys
OUT=Path(__file__).resolve().parent;PROJECT=OUT.parents[3];AREA=PROJECT/'資料治理與泛化修復'
sys.path.insert(0,str(AREA/'scripts'))
import v2_relu_dropout_contract as c
from training_state import atomic_json,file_sha256

def main():
    target=OUT/'STOPPED_RECEIPT.json'
    if target.exists():raise RuntimeError('Existing stopped receipt retained')
    tiny=c.read(c.RESULTS/'preflight/tiny.json');assert tiny['status']=='failed' and (c.RESULTS/'STOP').exists()
    assert not list((c.RESULTS/'attempts').glob('*.json')) and not (c.RESULTS/'preflight/base.json').exists()
    sources=[AREA/'scripts'/name for name in ('train_regularized.py','model_profiles.py','v2_relu_stage_dropout.py','v2_relu_dropout_contract.py','run_v2_relu_dropout.py')]
    sources+=list(OUT.glob('*.py'))+list(c.CONFIG.glob('*'))+list(OUT.glob('*.json'))+[OUT/'RESTART_AUTHORIZATION.md',c.RESULTS/'preflight/tiny.json']
    hashes={}
    for source in sources:
        snapshot=c.RESULTS/'sources_runtime'/source.relative_to(PROJECT);snapshot.parent.mkdir(parents=True,exist_ok=True)
        if snapshot.exists():raise RuntimeError('Existing snapshot retained')
        shutil.copy2(source,snapshot);hashes[str(source)]=file_sha256(source)
    reason='Tiny single-batch GPU precheck: output/loss finite, but AMP backward/unscale produced at least one non-finite gradient; optimizer step not executed.'
    data=dict(version=c.VERSION,execution_revision=c.EXECUTION_REV,status='failed_gpu_preflight',at=c.now(),
        reason=reason,traceback=tiny['traceback'],CPU_tiny_status=c.read(OUT/'CPU_tiny.json')['status'],CPU_base_status=c.read(OUT/'CPU_base.json')['status'],
        GPU_prechecks=1,GPU_model_forwards=1,GPU_backwards=1,GPU_optimizer_updates=0,real_train_images=8,Base_GPU_precheck=False,
        formal_runs_started=0,formal_complete_epochs=0,total_formal_attempt_seconds=0,
        GPU_worker_seconds=tiny['seconds'],GPU_process_attempt_seconds=c.read(OUT/'GPU_EXIT_tiny.json')['seconds'],
        original_CPU_failure_seconds=8.498143600008916,accounting='CPU and temporary GPU checks separate from formal attempts; worker seconds included in process attempt',
        peak_memory_bytes=None,peak_memory_note='failure occurred before recording peak; not remeasured',
        known_precheck_difference='precheck used scaler.scale(loss) instead of native scaler.scale(loss/gradient_accumulation=8); native AMP step normally manages overflow',
        cause_not_yet_proven='AMP initial scaling and architecture combination not separated; no OOM/CUDA unknown error observed; no claim that formal recipe is untrainable',
        source_hashes=hashes,test_used=False,no_auto_retry=True,original_failure_and_STOP_preserved=True)
    atomic_json(target,data)
    rows={job:dict(candidate=candidate,seed=seed,model=size,status='not_started_due_preflight_failure',run_id=None,epochs_completed=0,
        micro_batch=c.MICRO[size],accumulation=64//c.MICRO[size]) for job,candidate,seed,size in c.JOBS}
    atomic_json(c.RESULTS/'state.json',dict(version=c.VERSION,execution_revision=c.EXECUTION_REV,status='failed_gpu_preflight',updated_utc=c.now(),
        active=None,controller_pid=None,error=reason,limits=c.LIMITS,runs=rows))
    atomic_json(c.RESULTS/'EXECUTION_GATE.json',dict(version=c.VERSION,execution_revision=c.EXECUTION_REV,human_execution_authorized=True,
        execution_authorized=False,cpu_passed=True,gpu_passed=False,dispatch_token=c.DISPATCH_TOKEN,limits=c.LIMITS,jobs=c.JOBS,reason=reason))
    atomic_json(c.RESULTS/'FINAL_RESULTS.json',dict(version=c.VERSION,execution_revision=c.EXECUTION_REV,status='failed_gpu_preflight',rows=rows,
        formal_complete_epochs=0,total_formal_attempt_seconds=0,GPU_prechecks_performed=1,GPU_optimizer_updates=0,
        stopped_receipt=str(target),automatic_model_adoption=False,test_used=False))
    (c.RESULTS/'B_HANDOFF.md').write_text('restart1因Tiny單批GPU前檢非有限梯度停止。Tiny/Base CPU架構／權重鍵形狀／eval／Checkpoint往返均通過；真實Train8張前向8×7與Loss有限，backward後unscale梯度檢查失敗，未做optimizer.step；Base GPU及正式六run均未啟動。前檢未沿原loss/accum8縮放，是已確認的程式路徑差異，是否為唯一原因未證明，不能直接說新配方不可訓練。保存原與本次STOP／來源／收據，不自動重試或Resume。交總控核定後續，尚未採納。\n',encoding='utf-8')
    (c.RESULTS/'MONITOR.md').write_text('# restart1：GPU前檢失敗，已停止\n\n'+c.now()+'；無活控制器，此為靜態停止收據，不是每15秒即時監控。\n\nCPU Tiny/Base通過；Tiny GPU 1前向、1反向、0更新；正式0run/0Epoch。STOP保留。\n',encoding='utf-8')
    pointer=c.STUDY_RESULTS/'ACTIVE_EXECUTION.json'
    if not pointer.exists():atomic_json(pointer,dict(execution_revision=c.EXECUTION_REV,results=str(c.RESULTS),status='failed_gpu_preflight',at=c.now()))
    print(json.dumps({key:data[key] for key in ('status','GPU_prechecks','GPU_optimizer_updates','formal_runs_started','formal_complete_epochs')},ensure_ascii=False))

if __name__=='__main__':main()
