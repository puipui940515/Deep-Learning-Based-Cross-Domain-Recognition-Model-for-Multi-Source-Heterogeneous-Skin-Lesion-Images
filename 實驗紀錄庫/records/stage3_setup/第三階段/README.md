# 第三階段：多視角融合（v10–v12）

<!-- skindetect:status v1 -->
| 欄位 | 值 |
|---|---|
| 階段 | 第三階段 |
| 首次執行 | 2026-08-22 |
| 狀態 | 已鎖定 |
| seeds | — |
| 主要指標 | 尚未訓練；前置條件 v9 三 seed 未完成 |
| 正式輸入 | `第三階段/data/fixed_split_with_site.csv` |
| 結果證據 | — |
| 歸檔 | — |
| 時間軸 | [`開發歷程/時間軸.md`](../開發歷程/時間軸.md) |
| 格式約定 | [`開發歷程/格式約定.md`](../開發歷程/格式約定.md) |
<!-- /skindetect:status -->

本資料夾只保存第三階段程式、設定、checkpoint 與實驗紀錄。主線只使用 HAM10000，沿用依 `lesion_id` 分組的固定切分；部位標籤已加入正式資料流程。

## 目前狀態

- 已啟動：v10 空對照實作、前置閘門、顯存驗證與部位標籤流程。
- 正式訓練尚未解鎖：第二階段 v9 的 3 個 seeds 尚未完成，不得改用 v5 或隨機權重冒充。
- v11、v12 順序不變，在 v10 三種子完成前保持鎖定。
- test split 繼續封存；第三階段只使用 train／validation。

## 部位標籤

- `data/fixed_split_with_site.csv` 在原固定切分上加入 `anatom_site_raw`、`site_group`、`site_label`、`site_known`。
- v10–v12 的部位標籤只跟隨 batch 並產生分部位指標，不輸入模型、不參與梯度。
- 部位平衡取樣預留給 v13a label-only control；v13b 才測試 metadata 融合。
- 詳見 `部位標籤正式訓練流程.md`。

## v10 任務

四分支都接收同一張增強後 RGB，並共享 ConvNeXt-Tiny 骨幹；各分支加入視角嵌入，再用 concat + MLP 融合。此空對照用來分離「融合架構收益」與「不同視角資訊收益」。

## 使用方式

```powershell
python 第三階段/scripts/build_site_manifest.py
python 第三階段/scripts/site_label_smoke_test.py
python 第三階段/scripts/check_prerequisites.py
python 第三階段/scripts/memory_smoke_test.py
python 第三階段/scripts/train_v10.py --seed 17 --resume
```

只有 v9 三種子 checkpoint／result 齊全、固定切分一致、部位 manifest 通過且根目錄驗證閘門通過時，正式 v10 才會啟動。
