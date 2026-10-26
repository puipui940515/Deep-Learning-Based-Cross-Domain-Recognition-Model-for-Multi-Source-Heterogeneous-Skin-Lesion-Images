"""Reuse passed architecture checks and create one newly authorized execution."""
from pathlib import Path
import ast,importlib.metadata,json,platform,sys
OUT=Path(__file__).resolve().parent;PROJECT=OUT.parents[3];AREA=PROJECT/'資料治理與泛化修復'
sys.path.insert(0,str(AREA/'scripts'))
import v2_relu_dropout_contract as c
from training_state import atomic_json,file_sha256

def function_ast(path,name):
    tree=ast.parse(path.read_text(encoding='utf-8-sig'))
    return ast.dump(next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name==name),include_attributes=False)

def main():
    if c.RESULTS.exists() or (OUT/'RESTART_AUTHORIZATION.md').exists():raise RuntimeError('Execution exists; inspect, no duplicate')
    previous=OUT.parent/'restart1_20261026_v1';prior=c.STUDY_RESULTS/'executions/restart1_20261026_v1'
    assert c.read(prior/'state.json')['status']=='failed_gpu_preflight' and (prior/'STOP').exists() and (c.STUDY_RESULTS/'STOP').exists()
    stopped=c.read(previous/'STOPPED_RECEIPT.json');versions=c.read(AREA/'results/v2_scale512_followup_20261026_v1/EXECUTION_GATE.json')
    assert {name:importlib.metadata.version(name) for name in versions['versions']}==versions['versions'] and platform.python_version()==versions['python']
    # Architecture/model/optimizer code is byte-identical to the successful CPU validation.
    for name in ('model_profiles.py','v2_relu_stage_dropout.py'):
        path=AREA/'scripts'/name
        assert file_sha256(path)==stopped['source_hashes'][str(path)]
    for name in ('models.py','engine.py','metrics.py'):
        path=PROJECT/'第二階段/src/stage2'/name
        assert file_sha256(path)==versions['frozen_files'][str(path)]
    native=AREA/'scripts/train_regularized.py'
    baseline=OUT/'before/train_regularized.py'
    checks={name:function_ast(native,name)==function_ast(baseline,name) for name in ('train_epoch','evaluate','build_transform','load_governed_release')}
    assert all(checks.values())
    evidence={}
    for size in ('tiny','base'):
        receipt=previous/f'CPU_{size}.json';data=c.read(receipt);assert data['status']=='passed'
        assert file_sha256(receipt)==stopped['source_hashes'][str(receipt)]
        evidence[size]=dict(receipt=str(receipt),sha256=file_sha256(receipt),architecture_audit=data['architecture_audit'],reexecuted=False)
    auth=('使用者2026-10-26本B對話明確授權一次修正後驗證與既定六run啟動，非無限重試：\n'
        '「請修正前檢與原訓練流程不一致的問題，完成必要驗證後重新執行既定六個Run。本訊息授權一次修正後的驗證與啟動，不包含無限重試。」\n'
        'GPU前檢直接呼叫共用train_epoch：loss÷累積、原AMP／clip／optimizer流程。撤回新增AMP處理前梯度強停，不忽略真正異常或偽造更新。\n'
        '只保留GELU→非inplace ReLU及四Stage後一般Dropout.1；所有原AdamW、LR、資料、釘選預訓練、batch／累積／AMP／Scheduler／停止不變。\n'
        'Tiny512 Seeds1/2/3 8×8，再Base512 Seeds1/2/3 2×32；最多6正式run／180完整Epoch，無wall-clock上限。每run重新初始化，不接best/last。\n'
        '原啟動資源政策、STOP、Checkpoint／CUDA／Loss非有限與契約處理、15秒監控保留；本次真異常即保存停止、不自動重試或Resume。\n'
        '沿用已通過CPU Tiny/Base架構／mapping／Checkpoint，不重跑。兩次舊失敗與STOP全部保留，新execution restart2_20261026_v1，無Test／安裝／下載／Windows或網站變更。\n')
    (OUT/'RESTART_AUTHORIZATION.md').write_text(auth,encoding='utf-8');c.RESULTS.mkdir(parents=True,exist_ok=False)
    for name in ('logs','attempts','budget','preflight','sources_runtime'):(c.RESULTS/name).mkdir()
    atomic_json(OUT/'CPU_REUSE.json',dict(status='passed_reused',at=c.now(),evidence=evidence,unchanged_functions=checks,
        architecture_and_optimizer_sources_unchanged=True,versions=versions['versions'],python=versions['python'],no_model_reconstruction_or_GPU_test=True))
    atomic_json(OUT/'RESTART_RECEIPT.json',dict(status='authorized_preparing',execution_revision=c.EXECUTION_REV,at=c.now(),
        authorization_sha256=file_sha256(OUT/'RESTART_AUTHORIZATION.md'),prior_failure_hashes={str(path):file_sha256(path) for path in
        (c.STUDY_RESULTS/'STOP',prior/'STOP',c.STUDY_RESULTS/'state.json',prior/'state.json',previous/'STOPPED_RECEIPT.json',OUT.parent/'STOPPED_RECEIPT.json')},
        both_prior_STOPs_preserved=True,results=str(c.RESULTS)))
    print(json.dumps(dict(status='prepared_native_precheck_not_yet_run',CPU_reused=['tiny','base'],results=str(c.RESULTS)),ensure_ascii=False))

if __name__=='__main__':main()
