# SkinDetect 驗證閘門

<!-- skindetect:status v1 -->
| 欄位 | 值 |
|---|---|
| 階段 | 驗證階段 |
| 首次執行 | 2026-08-14 |
| 狀態 | 已完成 |
| seeds | — |
| 主要指標 | majority baseline BA = 1/7；lesion_id 三方交集 0 |
| 正式輸入 | `Dataset/HAM10000/` |
| 結果證據 | `驗證/reports/validation_gate.json` |
| 歸檔 | — |
| 時間軸 | [`開發歷程/時間軸.md`](../開發歷程/時間軸.md) |
| 格式約定 | [`開發歷程/格式約定.md`](../開發歷程/格式約定.md) |
<!-- /skindetect:status -->

本資料夾集中存放跨實驗共用的資料驗證、指標 sanity check、單元測試及驗證報告。正式實驗開始前必須執行：

```powershell
python "驗證/run_all.py"
```

只有 `reports/validation_gate.json` 的 `passed` 為 `true` 時，第一階段訓練程式才允許啟動。

驗證內容：

1. HAM10000 共 10,015 張，影像 ID 無重複。
2. 固定切分接近 70/15/15。
3. train、validation、test 的 `lesion_id` 交集為 0。
4. manifest 中所有影像路徑均存在。
5. HAM10000 與三個 ISIC 安全子集的 `isic_id` 交集檢查。
6. 多數類別退化模型的 balanced accuracy 必須等於 1/7。
7. manifest、指標與模型結構單元測試。

```text
驗證/
├─ scripts/
│  ├─ prepare_and_validate.py
│  └─ sanity_check.py
├─ tests/
│  ├─ test_manifest.py
│  ├─ test_metrics.py
│  └─ test_models.py
├─ reports/
│  ├─ split_validation.json
│  ├─ isic_overlap_report.json
│  ├─ sanity_check.json
│  └─ validation_gate.json
└─ run_all.py
```

