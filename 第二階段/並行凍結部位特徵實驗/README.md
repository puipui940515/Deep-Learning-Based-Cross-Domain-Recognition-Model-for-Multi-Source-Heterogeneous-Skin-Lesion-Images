# 第二階段並行凍結部位特徵實驗

## 流程

同一張影像經相同幾何增強後分成兩個張量表示：

1. 可訓練的 ImageNet ConvNeXt-Tiny student 接收第二階段既有 `[0.5, 0.5, 0.5]` normalization。
2. 凍結的 ConvNeXt-Tiny teacher 接收轉換回 `[0,1]` 後再施加 ImageNet normalization 的影像。
3. student 與 teacher 各輸出 768 維 pooled feature，串接成 1,536 維。
4. Linear 1,536→7 輸出 HAM10000 七類 logits。

Teacher 始終為 eval mode、零可訓練參數；下游不直接使用五類部位 logits或 metadata。

## 比較

- Frozen ImageNet teacher：控制只是增加並行模型與特徵。
- Frozen DensePose true teacher：主要部位特徵條件。
- Frozen DensePose shuffled teacher：探索性控制，現有 checkpoint 預訓練保存 epoch 不匹配。

三組的 student、fusion head、HAM10000 split、224 尺度、batch 16、gradient accumulation 2、CE、5 epochs 與 seeds 完全一致。此設計是特徵融合，不是純預訓練初始化；teacher 在正式推論時也必須保留。
