# Formal v1.1：訓練雜訊與小區域遮蔽

## 目的

在不改變 ConvNeXt-Tiny、資料切分、類別、最佳化器、學習率、epoch、seed 與左右換標規則的前提下，檢驗訓練階段的低強度隨機雜訊與小區域遮蔽能否降低 formal v1 的過擬合。

## 唯一新增因素

- 50% 機率加入 Gaussian noise：mean 0、standard deviation 0.025，結果限制在 `[0, 1]`。
- 35% 機率 Random Erasing：遮蔽輸入影像面積的 1%–6%，長寬比 0.3–3.3，填入隨機值。
- 兩者只作用於 training；validation 完全不加雜訊、不遮蔽。

Random Erasing 放在 Normalize 之前，因此遮蔽值仍位於原始 tensor `[0, 1]` 尺度。水平翻轉仍由原 formal v1 Dataset 處理，並同步交換左右標籤。

## 隔離

所有 checkpoint、JSON 與逐圖預測會寫入本資料夾下的 `checkpoints/formal_v1` 與 `results/formal_v1`，不覆寫 formal v1 原始結果。

官方 test 繼續封存。先比較 seed 17 的 true-site develop；只有 validation Balanced Accuracy 明顯改善，才執行完整控制組與後續 seeds。
