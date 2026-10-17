# 多來源混合訓練第二版

<!-- skindetect:status v1 -->
| 欄位 | 值 |
|---|---|
| 階段 | 多來源訓練階段 |
| 首次執行 | 2026-09-01 |
| 狀態 | 已完成 |
| seeds | 17 |
| 主要指標 | 三來源平均 BA 69.37%；train-val 落差 BCN 38.00pp |
| 正式輸入 | `多來源混合訓練_第二版/data/mixed_manifest.csv` |
| 結果證據 | `多來源混合訓練_第二版/results/imagenet_seed17/result.json` |
| 歸檔 | `檔案室` 任務 09 |
| 時間軸 | [`開發歷程/時間軸.md`](../開發歷程/時間軸.md) |
| 格式約定 | [`開發歷程/格式約定.md`](../開發歷程/格式約定.md) |
<!-- /skindetect:status -->

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
