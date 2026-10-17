# 第二階段：凍結部位 Backbone 短訓練

本實驗只訓練新建的 HAM10000 七類 Linear head，ConvNeXt-Tiny backbone 完全凍結。下游不輸入部位標籤、部位 logits 或 anatomical metadata。

## 公平比較

- A：ImageNet-frozen
- B：DensePose true-site-frozen
- C：DensePose shuffled-site-frozen（探索性；預訓練保存 epoch 與 B 不同）
- 三組使用相同 224 尺度、batch 16、gradient accumulation 2、CE、5 epochs、固定 HAM10000 split 與 seeds 17/42/2026。
- 這些設定對齊既有第二階段 v7 尺度；既有 v7 是全模型微調，只能作歷史參考，不能與本實驗直接作因果比較。

正式論文 C 組必須另行補訓練時長完全匹配的 shuffled final backbone。
