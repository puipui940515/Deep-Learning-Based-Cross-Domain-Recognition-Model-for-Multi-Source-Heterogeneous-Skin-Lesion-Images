"""One explicitly reauthorized restart; keep original failure and STOP untouched."""
from pathlib import Path
import json,sys
OUT=Path(__file__).resolve().parent;PROJECT=OUT.parents[3];AREA=PROJECT/'資料治理與泛化修復'
sys.path.insert(0,str(AREA/'scripts'))
import v2_relu_dropout_contract as c
from training_state import atomic_json,file_sha256

def main():
    if c.RESULTS.exists() or (OUT/'RESTART_AUTHORIZATION.md').exists():raise RuntimeError('Existing restart: inspect, no duplicate')
    old=c.read(c.STUDY_RESULTS/'state.json')
    assert old['status']=='failed_preflight' and old['active'] is None and (c.STUDY_RESULTS/'STOP').exists()
    assert not list((c.STUDY_RESULTS/'attempts').glob('*.json'))
    auth=('2026-10-26本B對話使用者在得知CPU GELU型別誤判、正式0run／GPU0次及失敗停止後明確要求：「請重新開始任務」。\n'
        '此為修正已知型別判斷、完成必要CPU／各模型一次單批GPU驗證後，再啟動原Tiny S1/2/3→Base S1/2/3六run的新的當次授權。\n'
        '完整科學範圍維持原AUTHORIZATION與B_NEXT_TASK，Tiny8×8／Base2×32、ReLU＋四Stage元素Dropout.1、其餘原配方。最多6新run／180完整Epoch、無時間上限。\n'
        '不是Resume，未有舊正式run／Checkpoint；各run新head／空optimizer／新ID。初次CPU失敗8.4981436秒及原STOP／來源／gate不改寫不刪除。\n'
        '新execution restart1_20261026_v1、新准入／token／來源；只授權這次重新準備及一次啟動。必要驗證失敗或正式異常即保存停止，無自動再試。\n'
        '不下載／安裝、改Windows／超參數、讀Test、聯絡其他Thread或改共用索引。\n')
    (OUT/'RESTART_AUTHORIZATION.md').write_text(auth,encoding='utf-8')
    c.RESULTS.mkdir(parents=True,exist_ok=False)
    for name in ('logs','attempts','budget','preflight','sources_runtime'):(c.RESULTS/name).mkdir()
    hashes={str(path):file_sha256(path) for path in (c.STUDY_RESULTS/'STOP',c.STUDY_RESULTS/'state.json',OUT.parent/'CPU_tiny.json',OUT.parent/'STOPPED_RECEIPT.json',c.STUDY_RESULTS/'EXECUTION_GATE.json')}
    atomic_json(OUT/'RESTART_RECEIPT.json',dict(status='authorized_preparing',at=c.now(),execution_revision=c.EXECUTION_REV,
        original_dispatch_token=c.DISPATCH_TOKEN,prior_failure_hashes=hashes,original_STOP_preserved=True,
        authorization_sha256=file_sha256(OUT/'RESTART_AUTHORIZATION.md'),results=str(c.RESULTS)))
    print(json.dumps(dict(status='restart_initialized_not_started',execution_revision=c.EXECUTION_REV,results=str(c.RESULTS)),ensure_ascii=False))

if __name__=='__main__':main()
