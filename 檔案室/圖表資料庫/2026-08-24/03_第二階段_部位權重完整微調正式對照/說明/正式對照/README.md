# 部位權重完整微調正式對照

## 研究問題

預先學過人體部位的 ConvNeXt-Tiny，在完整解凍後，是否比一般 ImageNet 初始化更有利於 HAM10000 七類疾病分類。

## 三組模型

| 組別 | 初始化 | 輸出 | 模型用途 |
|---|---|---|---|
| A | ImageNet | 7 個疾病 logits | 一般視覺預訓練基準 |
| B | DensePose 真實五類部位預訓練 | 7 個疾病 logits | 檢驗真實部位知識的遷移效果 |
| C | DensePose 打亂標籤、同樣訓練 8 epoch | 7 個疾病 logits | 排除額外預訓練計算量造成的效果 |

三組皆為單一 ConvNeXt-Tiny、重建相同七類分類頭、完整解凍、相同固定資料切分、超參數及 seeds（17、42、2026）。模型不會輸出部位，也不使用部位標籤作為疾病分類輸入。

## 執行順序

長時間正式訓練尚未自動啟動。檢查設定後，在專案根目錄執行：

```powershell
powershell -ExecutionPolicy Bypass -File ".\第二階段\部位權重完整微調正式對照\run_all.ps1" -Epochs 30
```

流程會自動：

1. 建立完成 8 epoch 的打亂標籤負對照資產；已完成時自動跳過。
2. 依序訓練 A、B、C 三組，每組三個 seed。
3. 每個任務每個 epoch 顯示進度，並保存 `last.pt`，中斷後可續訓。
4. 自動輸出 `results/summary.json`。
5. 自動產生中文版 Balanced Accuracy、Macro-F1 與 Loss 曲線。

## 正式判讀規則

- B 必須同時優於 A 與 C。
- 多數 seed 的差異方向必須一致。
- 主要指標是 Validation Balanced Accuracy；同時檢查 Macro-F1 與各類 Recall。
- 平均提升至少 1 個百分點才視為具有實務意義。
- 保留測試集不使用；所有輸出皆記錄 `test_used: false`。

