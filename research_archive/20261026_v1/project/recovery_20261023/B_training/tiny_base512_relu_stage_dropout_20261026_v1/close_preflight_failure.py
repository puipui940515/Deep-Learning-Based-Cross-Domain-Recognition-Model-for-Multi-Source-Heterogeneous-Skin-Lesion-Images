"""Preserve the one failed CPU validation and close this unlaunched batch."""
from pathlib import Path
import json,shutil,sys
OUT=Path(__file__).resolve().parent;PROJECT=OUT.parents[2];AREA=PROJECT/'資料治理與泛化修復'
sys.path.insert(0,str(AREA/'scripts'))
import v2_relu_dropout_contract as c
from training_state import atomic_json,file_sha256

def main():
    if (OUT/'STOPPED_RECEIPT.json').exists():raise RuntimeError('Failure already closed; preserve existing receipts')
    failed=c.read(OUT/'CPU_tiny.json');assert failed['status']=='failed' and (c.RESULTS/'STOP').exists()
    assert not list((c.RESULTS/'attempts').glob('*.json')) and not list((c.RESULTS/'budget').glob('*.json'))
    sources=[AREA/'scripts'/name for name in ('train_regularized.py','model_profiles.py','v2_relu_stage_dropout.py','v2_relu_dropout_contract.py','run_v2_relu_dropout.py')]
    sources+=list(OUT.glob('*.py'))+list(c.CONFIG.glob('*'))+[OUT/'CPU_tiny.json',OUT/'DISPATCH_RECEIPT.json']
    hashes={}
    for source in sources:
        target=c.RESULTS/'sources_runtime'/source.relative_to(PROJECT);target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():raise RuntimeError('Existing snapshot retained: '+str(target))
        shutil.copy2(source,target);hashes[str(source)]=file_sha256(source)
    reason='CPU validation assumed torch.nn.GELU, but local timm GELU is its own nn.Module subclass. CPU test and candidate replacement helper share this incorrect assumption.'
    receipt=dict(version=c.VERSION,status='failed_preflight',at=c.now(),dispatch_token=c.DISPATCH_TOKEN,reason=reason,
        error=failed['error'],traceback=failed['traceback'],cpu_attempt_seconds=failed['seconds'],
        CPU_attempts=1,GPU_prechecks=0,formal_runs_started=0,formal_complete_epochs=0,total_formal_attempt_seconds=0,
        old_followup_remains_completed=True,no_real_images_or_pretrained_weights_read=True,
        auto_retry=False,auto_resume=False,windows_environment_unchanged=True,test_used=False,
        evidence_hashes=hashes,shared_source_rollback='pending exact reversion of this batch dispatch only')
    atomic_json(OUT/'STOPPED_RECEIPT.json',receipt)
    rows={job:dict(candidate=candidate,seed=seed,model=size,status='not_started_due_preflight_failure',run_id=None,epochs_completed=0,
                  micro_batch=c.MICRO[size],accumulation=64//c.MICRO[size]) for job,candidate,seed,size in c.JOBS}
    atomic_json(c.RESULTS/'state.json',dict(version=c.VERSION,status='failed_preflight',updated_utc=c.now(),active=None,controller_pid=None,
        dispatch_token=c.DISPATCH_TOKEN,limits=c.LIMITS,runs=rows,error=reason))
    atomic_json(c.RESULTS/'EXECUTION_GATE.json',dict(version=c.VERSION,human_execution_authorized=True,execution_authorized=False,cpu_passed=False,gpu_passed=False,
        dispatch_token=c.DISPATCH_TOKEN,limits=c.LIMITS,jobs=c.JOBS,reason=reason))
    atomic_json(c.RESULTS/'FINAL_RESULTS.json',dict(version=c.VERSION,status='failed_preflight',rows=rows,formal_complete_epochs=0,
        total_formal_attempt_seconds=0,CPU_attempt_seconds=failed['seconds'],GPU_prechecks_performed=0,
        stopped_receipt=str(OUT/'STOPPED_RECEIPT.json'),test_used=False,automatic_model_adoption=False))
    (c.RESULTS/'MONITOR.md').write_text('# ReLU＋Stage Dropout批次：前檢失敗已停止\n\n'+c.now()+'；此為停止收據，沒有活控制器，不是每15秒更新的即時表。\n\nCPU型別檢查錯誤；GPU前檢0次、正式run0、完整Epoch0。STOP保留，不自動重試或Resume。\n',encoding='utf-8')
    (c.RESULTS/'B_HANDOFF.md').write_text('本批在第一個Tiny CPU相容檢查停止，未做GPU前檢、未啟任何正式run。原因為B將timm自訂GELU誤認torch.nn.GELU；替換helper亦須修正。配置與比較契約已另版建立，尚未通過架構／映射／Checkpoint驗收。失敗收據、來源快照及STOP保留；原followup整批completed不變。依交辦失敗即停，不自動重試、Resume或借用派送token再啟動。供總控決定修復與重新驗證／執行範圍，B未聯絡其他Thread或改共用索引。\n',encoding='utf-8')
    print(json.dumps({key:receipt[key] for key in ('status','CPU_attempts','GPU_prechecks','formal_runs_started','formal_complete_epochs','reason')},ensure_ascii=False))

if __name__=='__main__':main()
