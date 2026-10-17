# 第一階段 noisefilter 搭載實驗

## 比較對象

- 原始基線：第一階段 `v1`，MLP、64×64、無 augmentation。
- 搭載版本：`stage1_v1_noisefilter_core_fixed`。
- 固定資料：HAM10000 同一份 `data/fixed_split.csv`。
- 固定 seeds：17、42、2026。
- test split：不使用。

## 本次搭載內容

在輸入 MLP 前加入 noisefilter 核心 `FilterChain`：

1. `LogContrast`：對數亮度均值與對比標準化。
2. `IlluminationFlatten`：去除低頻乘性光照。
3. `GlobalColorConstancy`：降低全域色偏與白平衡差異。
4. `PeripheralReference`：以影像周邊作為殘餘色偏參考。

固定 alpha 為 `[0.25, 0.5, 0.5, 0.5]`。`LogContrast` 較低是因它可能直接改變具診斷價值的病灶對比。正式訓練前使用完整 train split、無 augmentation 的影像校準 `target_std` 與 `target_mean`，校準後四段濾鏡參數全部凍結，因此可訓練參數量與 v1 相同。

原模型輸入使用 `[-1,1]` normalization；濾鏡只接受 `[0,1]`，因此模型 wrapper 會先反正規化、濾波，再正規化回 `[-1,1]`。

## 刻意未搭載

- `InvarianceLoss`
- `DomainAlign`、CORAL、MMD
- `AlphaSampler`、`FiLMFromAlpha`、`AlphaTemperature`

本輪只回答「固定核心前處理是否有幫助」，避免同時改變訓練目標、來源對齊及模型條件化。

## 執行

```powershell
python .\第一階段\noisefilter搭載實驗\scripts\train.py --seed 17
python .\第一階段\noisefilter搭載實驗\scripts\train.py --seed 42
python .\第一階段\noisefilter搭載實驗\scripts\train.py --seed 2026
python .\第一階段\noisefilter搭載實驗\scripts\summarize.py
```

輸出只寫入本資料夾的 `checkpoints/` 與 `results/`，不覆寫第一階段原始 v1 checkpoint 或結果。
