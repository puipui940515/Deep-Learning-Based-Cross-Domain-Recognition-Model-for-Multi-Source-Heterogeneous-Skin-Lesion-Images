# 第二階段接續部位模型實驗

本實驗將四來源部位模型凍結，取其五類部位機率，接到第二階段 v7 疾病分類 logits 上。只訓練一個小型 `5 → 7` residual fusion head，不修改原始疾病或部位 checkpoint。

## 對照

- baseline：原始 v7 疾病 logits。
- bias_control：相同 residual head，但部位輸入全為 0，只能學疾病 bias。
- site_fusion：使用真實的部位模型預測機率。
- shuffled_site：全域打亂部位機率，檢查額外參數或偶然相關。

三個疾病 seeds 分別比較。HAM test 維持封存；只使用 train 與 validation。這是 frozen-output pilot，不等於端到端正式融合。部位模型挑選曾觀察 HAM validation 的部位標籤，因此論文正式結果應改用 nested／out-of-fold 部位預測。
