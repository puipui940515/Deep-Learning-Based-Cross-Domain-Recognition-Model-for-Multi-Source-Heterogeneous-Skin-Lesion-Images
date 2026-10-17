# 獨立部位預測階段

<!-- skindetect:status v1 -->
| 欄位 | 值 |
|---|---|
| 階段 | 部位預測階段 |
| 首次執行 | 2026-08-23 |
| 狀態 | 已結案 |
| seeds | 17／42／2026 |
| 主要指標 | HAM 部位五類 BA 約 50.1%；DensePose 91.48%，但轉移至疾病分類三種接法皆為負 |
| 正式輸入 | `Dataset/HAM10000/`、iToBoS、DensePose |
| 結果證據 | `部位預測階段/results/summary.json` |
| 歸檔 | `檔案室` 任務 02 |
| 時間軸 | [`開發歷程/時間軸.md`](../開發歷程/時間軸.md) |
| 格式約定 | [`開發歷程/格式約定.md`](../開發歷程/格式約定.md) |
<!-- /skindetect:status -->

這是一個與疾病分類分離的任務。模型只根據 HAM10000 皮膚鏡影像預測解剖部位，不預測疾病。

## 任務

- 輸入：單張 HAM10000 影像。
- 輸出：`head_neck`、`trunk`、`upper_extremity`、`lower_extremity`、`anogenital` 五類。
- `unknown` 共 241 張，因為沒有可靠真實部位，不加入訓練或驗證。
- 主指標：Validation Balanced Accuracy。
- 輔助指標：macro-F1、Accuracy、ECE、各部位 Recall／Precision／F1、混淆矩陣。
- test split 保持封存，不參與訓練、早停或模型選擇。

## 基線模型

- ResNet-18，ImageNet 預訓練。
- 224 × 224。
- sqrt inverse-frequency weighted CE，緩和部位不平衡。
- 三個 seeds：17、42、2026。
- 依 Validation Balanced Accuracy 早停與保存 checkpoint。

`anogenital` 只有 31 張訓練影像及 11 張驗證影像，因此該類指標的不確定性很高，報告時必須同時呈現 support。

## 執行

```powershell
python "部位預測階段/scripts/audit_data.py"
python "部位預測階段/scripts/smoke_test.py"
python "部位預測階段/scripts/train.py" --seed 17
python "部位預測階段/scripts/train.py" --seed 42
python "部位預測階段/scripts/train.py" --seed 2026
python "部位預測階段/scripts/summarize.py"
```
