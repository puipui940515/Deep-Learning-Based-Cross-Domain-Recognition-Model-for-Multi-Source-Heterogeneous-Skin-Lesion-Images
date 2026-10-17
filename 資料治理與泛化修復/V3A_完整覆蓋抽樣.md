# V3A：完整覆蓋、有限補抽實驗

## 研究問題

在模型、資料切分、損失函數與其他超參數維持和 `formal_v1` 相同時，把「有放回的來源平衡抽樣」改成「每筆資料至少一次、有限補抽」，是否能改善跨來源泛化並降低少數影像被反覆記憶的情況。

## 唯一主要改動

- 舊版：每個 epoch 有放回抽取 18,922 次，不保證每張圖片都出現。
- V3A：每個 epoch 先完整走過 18,922 張訓練圖片，再有限補抽較小來源與少數類別。
- 單張影像每個 epoch 最多出現 2 次。
- 補抽時仍使用來源內 `class_count^-0.5`，讓少數類別有較高機率被選中。
- 驗證集、ConvNeXt-Tiny、ImageNet 初始化、資料增強、Cross Entropy、MixUp、選模公式均不變。

## 正式資料的每 epoch 取樣量

| 來源 | 不重複訓練影像 | V3A 每 epoch 取樣 |
|---|---:|---:|
| HAM10000 | 7,007 | 10,221 |
| BCN20000 | 10,221 | 10,221 |
| PAD-UFES-20 | 1,694 | 3,388 |
| 合計 | 18,922 | 23,830 |

PAD 規模較小，因此只允許每張最多出現兩次，不會強制重複到與 BCN 完全相同。這使 PAD 的每 epoch 比例由原始約 9% 提高到約 14.2%，但不會像完全來源平衡抽樣那樣提高到 33.3%。

## 煙霧測試

```powershell
python ".\資料治理與泛化修復\scripts\train_regularized.py" `
  --seed 17 `
  --epochs 1 `
  --sampling-method full_coverage_capped `
  --max-repeats-per-epoch 2 `
  --max-train-samples 280 `
  --max-val-samples-per-source 70 `
  --output-root ".\資料治理與泛化修復\smoke_results\v3a_coverage"
```

## 正式 seed 17

```powershell
python ".\資料治理與泛化修復\scripts\train_regularized.py" `
  --seed 17 `
  --epochs 12 `
  --batch-size 16 `
  --learning-rate 0.0001 `
  --weight-decay 0.05 `
  --label-smoothing 0.1 `
  --mixup-alpha 0.2 `
  --early-stopping-patience 4 `
  --sampling-method full_coverage_capped `
  --max-repeats-per-epoch 2 `
  --output-root ".\資料治理與泛化修復\results\formal_v3a_coverage"
```

## 續跑

續跑時必須保留相同的抽樣模式、重複上限、seed 與輸出根目錄：

```powershell
python ".\資料治理與泛化修復\scripts\train_regularized.py" `
  --seed 17 `
  --epochs 12 `
  --sampling-method full_coverage_capped `
  --max-repeats-per-epoch 2 `
  --output-root ".\資料治理與泛化修復\results\formal_v3a_coverage" `
  --resume
```

## 判定標準

- 三來源平均 BA 必須高於 72.06%。
- 最差來源及 BCN BA 必須高於 62.83%。
- Robust score 必須高於 67.45%。
- 任一來源 BA 不應下降超過 2 個百分點。
- 只有 seed 17 通過以上條件後，才補跑 seed 42 與 2026。

本實驗不使用 test split，也不把驗證資料加入訓練。
