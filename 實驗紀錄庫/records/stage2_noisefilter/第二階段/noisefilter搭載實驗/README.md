# 第二階段 noisefilter 搭載實驗

## 比較對象

- 原始基線：第二階段 `v5`，未預訓練 ResNet-18、224×224、CE loss。
- 搭載版本：`stage2_v5_noisefilter_core_fixed`。
- 固定資料：HAM10000 同一份 `data/fixed_split.csv`。
- 固定 augmentation、optimizer、learning rate、batch size、early stopping 與 seeds。
- test split：不使用。

## 本次搭載內容

在 ResNet-18 前加入 noisefilter 核心 `FilterChain`：

1. `LogContrast`
2. `IlluminationFlatten`
3. `GlobalColorConstancy`
4. `PeripheralReference`

固定 alpha 為 `[0.25, 0.5, 0.5, 0.5]`。使用完整 train split 的無 augmentation 影像校準 LogContrast，之後濾鏡參數凍結，因此 ResNet-18 的可訓練參數量不變。wrapper 負責在原本 `[-1,1]` normalization 與濾鏡要求的 `[0,1]` 之間轉換。

## 刻意未搭載

- `InvarianceLoss`
- `DomainAlign`、CORAL、MMD
- `AlphaSampler`、`FiLMFromAlpha`、`AlphaTemperature`

本輪只檢驗固定核心濾鏡，並分別比較乾淨 validation 與相同合成光照擾動 validation。BCN20000 不加入訓練或對齊，保留未來作 OOD 評估的資格。

## 執行

```powershell
python .\第二階段\noisefilter搭載實驗\scripts\train.py --seed 17
python .\第二階段\noisefilter搭載實驗\scripts\train.py --seed 42
python .\第二階段\noisefilter搭載實驗\scripts\train.py --seed 2026
python .\第二階段\noisefilter搭載實驗\scripts\summarize.py
```

輸出只寫入本資料夾，不覆寫第二階段原始 v5 checkpoint 或結果。
