# 顯式影像特徵融合實驗

## 目的

測試先從原圖擷取可解釋的色調、色彩分布、紋理、清晰度、曝光、構圖與中央／邊緣差值，是否能讓疾病分類更容易，並降低完全依賴 ConvNeXt 自行摸索特徵的負擔。

本實驗獨立於 V1、V2、V3A，不會覆蓋既有模型或結果。

## 第一版的範圍

- 每張圖片快取 65 個非生成式數值，其中 58 個進入模型，7 個只供品質／來源稽核。
- 包含 RGB、HSV、CIELAB 統計、灰階熵、梯度、清晰度、曝光、飽和度、暗邊與中央／邊緣色差。
- 沒有病灶分割，所以中央／邊緣差值只是一個代理特徵，不能稱為病灶相對膚色。
- source、device、清晰度、過曝／欠曝、黑邊、暗角、長寬比與原始像素數不進入疾病分類器，只保留在快取中供稽核。
- 特徵標準化的 mean/std 只用訓練切分計算，避免驗證資訊洩漏。

## 兩種模式

1. `feature_only`：只用顯式數值特徵的小型 MLP。執行快，用來確認這些統計是否有訊號。
2. `fusion`：ImageNet ConvNeXt-Tiny 影像特徵加上顯式特徵分支，再共同輸出七類 logits。

## 正式執行指令

先完整擷取並快取特徵：

```powershell
C:\anaconda3\python.exe ".\資料治理與泛化修復\顯式影像特徵融合實驗\scripts\extract_features.py"
```

先跑成本很低的顯式特徵小模型：

```powershell
C:\anaconda3\python.exe ".\資料治理與泛化修復\顯式影像特徵融合實驗\scripts\train.py" --mode feature_only --seed 17 --epochs 30
```

若小模型顯示有跨來源訊號，再執行融合模型：

```powershell
C:\anaconda3\python.exe ".\資料治理與泛化修復\顯式影像特徵融合實驗\scripts\train.py" --mode fusion --seed 17 --epochs 12
```

中斷後可在相同模式加入 `--resume`：

```powershell
C:\anaconda3\python.exe ".\資料治理與泛化修復\顯式影像特徵融合實驗\scripts\train.py" --mode fusion --seed 17 --epochs 12 --resume
```

## 判定方式

正式比較仍使用 V1 的相同統一資料清單、相同來源驗證集、seed 17，以及：

- HAM10000、BCN20000、PAD-UFES-20 各自 Balanced Accuracy。
- 三來源平均 Balanced Accuracy。
- 最差來源 Balanced Accuracy。
- `0.5 × 三來源平均 + 0.5 × 最差來源` 的穩健選模分數。
- macro-F1、ECE 與各類召回率。

只有融合模型在相同來源驗證下穩定超過 V1，才可說明顯式特徵對目前任務有幫助。煙霧測試只驗證程式能否執行，不用來比較模型優劣。
