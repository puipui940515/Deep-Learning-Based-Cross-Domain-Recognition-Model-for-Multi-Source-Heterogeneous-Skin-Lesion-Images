"""Create only this dispatched architecture batch; no model/GPU work."""
from pathlib import Path
import copy,json,sys
OUT=Path(__file__).resolve().parent;PROJECT=OUT.parents[2];AREA=PROJECT/'資料治理與泛化修復'
sys.path.insert(0,str(AREA/'scripts'))
import v2_relu_dropout_contract as c
from training_state import atomic_json,file_sha256

def main():
    if c.CONFIG.exists() or c.RESULTS.exists():raise RuntimeError('Existing candidate artifacts: inspect, do not overwrite')
    task=PROJECT/'recovery_20261023/B_training/model512_relu_stage_dropout_queue_20261026_v2/B_NEXT_TASK.md'
    assert file_sha256(task)=='ece3cb71b27278217346edd8bdc347ec344d45a6f8c550442d9af6f27d09f725'
    queue=c.read(task.with_name('QUEUE_STATE.json'));assert queue['dispatch_token']==c.DISPATCH_TOKEN and queue['dispatch_count']==1
    old=AREA/'results/v2_scale512_followup_20261026_v1';state=c.read(old/'state.json')
    assert state['status']=='completed' and state['active'] is None and all(row['status']=='completed' for row in state['runs'].values())
    assert not (old/'STOP').exists() and (old/'FINAL_RESULTS.json').exists() and (old/'B_HANDOFF.md').exists()
    c.CONFIG.mkdir();c.RESULTS.mkdir()
    for folder in ('logs','attempts','budget','preflight','sources_runtime'):(c.RESULTS/folder).mkdir()
    authorization=('總控依使用者直接授權正式交B；非舊研究授權。唯一派送token '+c.DISPATCH_TOKEN+'。\n'
        '使用者明確要求目前整批結束後總控直接交B，AdamW不動，只改GELU→ReLU與每Stage後Dropout=.1；最新範圍「那tiny跟base都各跑seed1~3好了」。\n'
        '固定Tiny S1→S2→S3，再Base S1→S2→S3；最多6新run／180完整Epoch、無時間硬上限。\n'
        '本檔與本次派送僅同一批授權；原完整任務如下，不得另跑舊僅Tiny queue或追加Large。\n\n'+task.read_text(encoding='utf-8'))
    (c.CONFIG/'AUTHORIZATION.md').write_text(authorization,encoding='utf-8')
    for candidate in c.CANDIDATES:
        cfg=c.expected_config(candidate);c.validate_candidate(cfg);atomic_json(c.CONFIG/(candidate+'.json'),cfg)
    historical=AREA/'configs/v2_512_alpha025_20261024_v1/EVALUATION_CONTRACT.json'
    reference=c.read(historical)
    policy=dict(version=c.VERSION,status='prospective_comparison_contract_before_training',models=['tiny','base'],seeds=[1,2,3],ddof=1,
        primary_contrast='each modified model minus original same architecture 512 same Seed at its existing best',
        selection='first highest Validation Robust; full original Monitor/Validation every epoch',
        required_metrics=['Robust','merged Accuracy','merged Macro-F1','all source BA','all supported disease TP/N/Recall','combined MEL','mean/sampleSD and paired delta'],
        baseline_files={size:{str(seed):str(c.reference_folder(size,seed)/'result.json') for seed in (1,2,3)} for size in ('tiny','base')},
        historical_protection_reference={key:copy.deepcopy(reference[key]) for key in ('robust','mean_delta_min','NV_strict_improvement','other_supported_disease_mean_delta_min','other_supported_disease_keys')},
        protection_source=str(historical),protection_source_sha256=file_sha256(historical),new_adoption_thresholds_created=False,
        interpretation='D interprets complete three-Seed comparisons; thresholds preserved only as existing references, no automatic adoption',
        combined_change_not_separate_causality=True,cross_architecture_micro_mixup_limitation=True,PAD_DF_VASC='N/A; unsupported',
        validation_repeatedly_used_exploratory=True,significance_claim=False,test_used=False,automatic_model_website_adoption=False)
    atomic_json(c.CONFIG/'COMPARISON_CONTRACT.json',policy)
    atomic_json(OUT/'DISPATCH_RECEIPT.json',dict(status='accepted_not_launched',at=c.now(),dispatch_token=c.DISPATCH_TOKEN,source_thread='01a16a74-3356-7701-acf2-12096d5c2599',
        task=str(task),task_sha256=file_sha256(task),old_state=state['status'],old_complete_epochs=c.read(old/'FINAL_RESULTS.json')['formal_complete_epochs'],jobs=c.JOBS))
    print(json.dumps(dict(status='configured_not_launched',jobs=c.JOBS,dispatch_token=c.DISPATCH_TOKEN),ensure_ascii=False))

if __name__=='__main__':main()
