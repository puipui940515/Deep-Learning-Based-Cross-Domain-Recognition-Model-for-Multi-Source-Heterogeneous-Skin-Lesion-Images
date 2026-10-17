# Formal v1.2：Weighted Cross-Entropy + Label Smoothing 0.05

## 唯一變因

本版本完整沿用 formal v1 的影像、切分、ConvNeXt-Tiny、384×384、增強、左右換標、類別權重、AdamW、layer decay、cosine scheduler、epoch、patience 與 seed。

唯一修改：

```text
CrossEntropyLoss(weight=class_weights, label_smoothing=0.05)
```

不加入 Gaussian noise，不使用 Random Erasing。

## 數學定義

五分類且 smoothing `ε=0.05` 時，目標分布由 one-hot 改為：

```text
正確類別：1 - ε + ε/5 = 0.96
每個錯誤類別：ε/5 = 0.01
```

目的不是改變真實標籤，而是避免模型被要求將正確類別機率推到絕對 1.0，降低對訓練資料過度自信。

## 閘門

先執行 true-site seed 17。Validation Balanced Accuracy 必須至少達 `0.5953`，才執行 shuffled-label、其他 seeds 或後續 refit。官方 test 維持封存。
