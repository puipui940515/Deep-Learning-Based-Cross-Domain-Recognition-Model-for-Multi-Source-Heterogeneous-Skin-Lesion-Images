# 第二階段：遷移學習實驗（v5–v9）

<!-- skindetect:status v1 -->
| 欄位 | 值 |
|---|---|
| 階段 | 第二階段 |
| 首次執行 | 2026-08-14 |
| 狀態 | 已結案 |
| seeds | 17／42／2026 |
| 主要指標 | v5 隨機 57.28%、v6 ImageNet 70.90%、v7 ConvNeXt 77.30%、v8 384 80.97%（三 seed 平均）；v9 未完成 |
| 正式輸入 | `第二階段/data/fixed_split.csv` |
| 結果證據 | `第二階段/results/` |
| 歸檔 | `檔案室` 任務 03–06 |
| 時間軸 | [`開發歷程/時間軸.md`](../開發歷程/時間軸.md) |
| 格式約定 | [`開發歷程/格式約定.md`](../開發歷程/格式約定.md) |
<!-- /skindetect:status -->

本資料夾隔離第二階段的設定、程式、manifest 副本、checkpoint、逐 epoch 結果與實驗記錄。只共用中央 `Dataset/HAM10000` 影像及根目錄 `驗證/` 的驗證閘門。

> 第一階段目前只完成 v1；v2–v4 尚未完成。因此可以執行 v5–v9，但在 v4 完成前，不計算或宣稱 v4→v5 的正式增益。

## 版本

| 版本 | 模型 | 初始化 | 解析度 | 唯一主要變更 |
|---|---|---|---:|---|
| v5 | ResNet-18 | 隨機 | 224 | 小型 CNN 改為深層殘差網路 |
| v6 | ResNet-18 | ImageNet | 224 | 只更換初始化 |
| v7 | ConvNeXt-Tiny | ImageNet | 224 | 現代骨幹＋逐層學習率衰減 0.7 |
| v8 | ConvNeXt-Tiny | ImageNet | 384 | 只提高解析度 |
| v9 | ConvNeXt-Tiny | ImageNet | 384 | CE 改為 logit-adjusted CE |

## 執行

```powershell
python "驗證/run_all.py"
python "第二階段/scripts/smoke_test.py"
python "第二階段/scripts/train.py" --version v5 --seed 17
python "第二階段/scripts/run_stage2.py"
python "第二階段/scripts/summarize_results.py"
```

測試集維持封存。模型選擇只使用 validation balanced accuracy。

## noisefilter 搭載實驗

固定核心四段濾鏡的三 seeds 對照已獨立放在 `noisefilter搭載實驗/`。搭載項目、未搭載項目、設定、checkpoint、逐 seed 結果與結論見 `noisefilter搭載實驗/搭載實驗記錄.md`。BCN20000 未加入訓練或對齊，test split 未使用，v5 原始結果未覆寫。

## 全資料集快速測試

五個本地來源的固定抽樣快速推論結果位於專案根目錄 `全資料集快速測試/第二階段/`；HAM test 未使用，SCIN 與不相容標籤只做穩定性分析。
