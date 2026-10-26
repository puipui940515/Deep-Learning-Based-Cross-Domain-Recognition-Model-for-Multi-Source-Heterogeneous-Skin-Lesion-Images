# 原 V2 推論服務 v1

程式已接上原 ConvNeXt V2-Tiny ImageNet Seed1 與 Seed1/2/3 等權機率 Ensemble。GPU 驗證與本機測速已完成；不代表已決定研究上正式採用 Ensemble。

完整條件／數據／啟動命令：`ui_prototype/validation/ensemble_20261021_v1/REPORT.md`。

## 檔案職責

| 檔案 | 功能 |
|---|---|
| core.py | 七類順序、模式、分數驗證、等權機率、研究用途提示；不依賴 torch |
| models_v1.json | 三份原 checkpoint／best epoch、配置／來源／版本／SHA 契約 |
| contract.py | 唯讀比對正式 metadata、權重 SHA 與建模／Validation 函式 AST |
| runtime.py | 延遲載入、排程與併發保護、真實前處理與推論、完整追溯回應 |
| verify_reference.py | 沿用 C 既有分數驗證公式；不載入模型、不讀圖片 |
| gpu_acceptance.py | B 釋放後的有界真實一致性／兩模式隔離測速；保留完成收據 |
| tests/test_lightweight.py | CPU 合成圖、測試替身、契約／HTTP／GPU gate 等輕量測試 |

`ui_prototype/ensemble_server.py` 為本機 API 入口；舊 server.py／model_runtime.py 不變。

## API 契約

- `GET /api/v2/health`、`GET /api/v2/models`：執行開關、metadata、GPU 驗證收據、模式／權重／類序與限制。預設關閉不 import torch。
- `POST /api/v2/predict`：同源 `application/json`，欄位 `model_id`、`image_name`、`image_data_url`。model_id 為 `v2_imagenet_seed1` 或 `v2_imagenet_ensemble123`；JPG／PNG／WebP，20 MiB／64M pixels 上限。
- 成功：`is_mock:false`、七類 `disease`、`members`（seed、best_epoch、weight、checkpoint_sha256 等）、`member_probabilities`、`checkpoint_version`、`calibrated:false`、`medical_notice`、`timing`；`heatmap.available:false` 明示尚無 Grad-CAM。前處理契約由 GET models 提供。實際欄位以 runtime.py 為準。
- 失敗：HTTP 4xx/5xx 與 `code`、`error`；未開模型／GPU 忙／契約不符拒絕；沒有 mock fallback、CPU fallback、訓練或 Test 路由。

推論不寫影像或個案；標準 HTTP log 只記路由／狀態，不包含影像 payload。此為本機展示服務，未宣稱公開部署安全性或臨床能力。
