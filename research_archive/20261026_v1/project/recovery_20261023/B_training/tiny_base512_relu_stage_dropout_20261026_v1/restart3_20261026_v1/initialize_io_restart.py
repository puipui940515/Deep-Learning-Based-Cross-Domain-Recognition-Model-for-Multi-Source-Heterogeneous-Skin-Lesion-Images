"""Initialize the explicitly authorized IO-only repair and replacement start."""
from pathlib import Path
import importlib.metadata,json,platform,sys
OUT=Path(__file__).resolve().parent;PROJECT=OUT.parents[3];AREA=PROJECT/'資料治理與泛化修復'
sys.path.insert(0,str(AREA/'scripts'))
import v2_relu_dropout_contract as c
from training_state import atomic_json,file_sha256

def main():
    if c.RESULTS.exists() or (OUT/'RESTART_AUTHORIZATION.md').exists():raise RuntimeError('Existing execution: inspect; no duplicate')
    previous=c.STUDY_RESULTS/'executions/restart2_20261026_v1'
    before_B=OUT.parent/'restart2_20261026_v1';state=c.read(previous/'state.json');stop=c.read(before_B/'FORMAL_STOP_RECEIPT.json')
    assert state['status']=='failed' and state['active'] is None and stop['formal_complete_epochs']==0 and stop['resume_available'] is False
    assert stop['run_id']=='9b38f8536746431b84a42f25d307569b' and (previous/'STOP').is_file()
    gate=c.read(previous/'EXECUTION_GATE.json');versions={key:importlib.metadata.version(key) for key in gate['versions']}
    assert versions==gate['versions'] and platform.python_version()==gate['python']
    for name in ('train_regularized.py','model_profiles.py','v2_relu_stage_dropout.py'):
        path=AREA/'scripts'/name;assert file_sha256(path)==gate['frozen_files'][str(path)]
    before=(OUT/'before/training_state.py').read_text(encoding='utf-8-sig');after=(AREA/'scripts/training_state.py').read_text(encoding='utf-8-sig')
    old="temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')"
    new="temporary = path.with_name('.atomic-' + uuid.uuid4().hex + '.tmp')"
    assert before.count(old)==1 and before.replace(old,new)==after
    auth=('使用者2026-10-26本B對話明確授權：\n'
        '「請一次完成Windows保存路徑修復與原定訓練接續。本訊息授權必要修復、CPU存檔驗證，以及修復後一次新的Seed1替代啟動，接續其餘五個Run。」\n'
        '只修正Checkpoint檔案IO，優先縮短同目錄暫存名稱，保留fsync／原子替換／雙代／原恢復保護，不改Windows或科學參數。\n'
        '在涵蓋六run最長正式路徑的隔離位置以微型CPU payload驗寫入、替換、index／best／雙代與讀回；不覆寫正式Checkpoint。\n'
        '沿用既有適用CPU與原train_epoch GPU更新證據，不再GPU前檢／benchmark。\n'
        'Tiny Seed1無Checkpoint，授權一次新Run ID／原預訓練／新head及空optimizer替代啟動，之後Tiny2/3、Base1/2/3依序。\n'
        '原失敗Run額外列帳，新增一次替代啟動；原六模型Seed任務及最多180已提交Epoch維持，無時間硬上限。\n'
        '只ReLU＋四Stage後一般Dropout.1；全部原AdamW／LR／資料／Batch／累積／AMP／Scheduler／早停不變。\n'
        '保留全部失敗、STOP、來源與實耗；新execution restart3_20261026_v1，不假作Resume。\n'
        '原資源政策、15秒MONITOR；無新門檻／安裝／下載／Windows或網站變更／Test。新真正異常即保存停止，不無限重試。\n')
    (OUT/'RESTART_AUTHORIZATION.md').write_text(auth,encoding='utf-8');c.RESULTS.mkdir(parents=True,exist_ok=False)
    for name in ('logs','attempts','budget','sources_runtime'):(c.RESULTS/name).mkdir()
    evidence=dict(status='passed_reused',CPU={},GPU={},versions=versions,python=gate['python'],
        architecture_and_native_training_unchanged=True,only_checkpoint_temporary_name_changed=True,new_GPU_prechecks=0)
    cpu_reused=c.read(before_B/'CPU_REUSE.json')
    for size in ('tiny','base'):
        cpu=Path(cpu_reused['evidence'][size]['receipt']);assert c.read(cpu)['status']=='passed'
        gpu=previous/'preflight'/f'{size}.json';proof=c.read(gpu)
        assert proof['status']=='passed' and proof['native_train_epoch'] and proof['optimizer_updates']==1 and proof['actual_AdamW_step']==1
        evidence['CPU'][size]=dict(receipt=str(cpu),sha256=file_sha256(cpu),reexecuted=False)
        evidence['GPU'][size]=dict(receipt=str(gpu),sha256=file_sha256(gpu),reexecuted=False)
    atomic_json(OUT/'REUSED_EVIDENCE.json',evidence)
    accounting=dict(prior_failed_formal_run=dict(run_id=stop['run_id'],result_root=str(previous),formal_attempt_seconds=stop['formal_attempt_seconds'],
        committed_epochs=0,uncommitted_epoch_segments=stop['uncommitted_epoch_segments'],resume_available=False),
        explicitly_authorized_additional_replacement_start=1,current_execution_model_seed_tasks=6,current_execution_start_limit=6,
        maximum_total_formal_starts_with_preserved_failure=7,max_total_committed_epochs=180,wall_clock_cap_seconds=None)
    atomic_json(OUT/'REPLACEMENT_ACCOUNTING.json',accounting)
    paths=[c.STUDY_RESULTS/'STOP',c.STUDY_RESULTS/'executions/restart1_20261026_v1/STOP',previous/'STOP',before_B/'FORMAL_STOP_RECEIPT.json',previous/'state.json',previous/'FINAL_RESULTS.json']
    atomic_json(OUT/'RESTART_RECEIPT.json',dict(status='authorized_IO_validation_pending',at=c.now(),execution_revision=c.EXECUTION_REV,
        prior_evidence_hashes={str(path):file_sha256(path) for path in paths},all_prior_STOPs_preserved=True,results=str(c.RESULTS)))
    print(json.dumps(dict(status='initialized_IO_only_validation_pending',results=str(c.RESULTS),new_GPU_prechecks=0),ensure_ascii=False))

if __name__=='__main__':main()
