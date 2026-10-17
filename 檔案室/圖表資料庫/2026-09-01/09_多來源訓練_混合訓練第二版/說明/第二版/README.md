# 多來源混合訓練第二版

第二版在第一版 HAM10000＋BCN20000 的基礎上加入 PAD-UFES-20 臨床手機影像，目標是增加來源與成像方式的多樣性。

## 實驗固定條件

- 模型：ConvNeXt-Tiny
- 初始化：ImageNet
- 影像大小：224×224
- 類別：沿用 HAM10000 七類
- seed：17
- epochs：8
- HAM、BCN、PAD 三個來源的預期抽樣比例各約三分之一
- 最佳模型依三個來源 Validation Balanced Accuracy 的等權平均選擇
- 不使用 HAM test、BCN 官方無標籤 test
- ISIC Archive 不加入訓練，保留作後續外部驗證

## PAD-UFES-20 處理方式

- `ACK → AKIEC`
- `BCC → BCC`
- `SEK → BKL`
- `NEV → NV`
- `MEL → MEL`
- `SCC` 排除
- 使用 `patient_id` 做 StratifiedGroupKFold，避免同一患者跨越訓練與驗證
- PAD 驗證 BA／Macro-F1 只平均實際存在的五類，不把不存在的 DF、VASC 計為零分

## 1. 建立資料清單

```powershell
python ".\多來源混合訓練_第二版\scripts\build_manifest_v2.py"
```

如需重新執行完整 SHA-256 重複檔案稽核：

```powershell
python ".\多來源混合訓練_第二版\scripts\build_manifest_v2.py" --hash-audit
```

## 2. 由使用者執行 smoke test

```powershell
python ".\多來源混合訓練_第二版\scripts\train_mixed_v2.py" --seed 17 --epochs 1 --max-train-samples 96 --max-val-samples-per-source 32 --output-root ".\多來源混合訓練_第二版\smoke_results"
```

## 3. 由使用者執行八輪正式訓練

```powershell
python ".\多來源混合訓練_第二版\scripts\train_mixed_v2.py" --seed 17 --epochs 8
```

中斷後續訓：

```powershell
python ".\多來源混合訓練_第二版\scripts\train_mixed_v2.py" --seed 17 --epochs 8 --resume
```

正式輸出位於 `results/imagenet_seed17/`。訓練由使用者執行，本資料夾的建立與稽核流程不會自行啟動訓練。
