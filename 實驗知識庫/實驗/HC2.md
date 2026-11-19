# HC2　HC v2 manifest：修正跨來源同病灶切分洩漏，並重跑 20 epoch 基準

- 日期：2026-11-18 ～ 2026-11-19
- 狀態：manifest 完成並經獨立驗證；seed 17 基準完成；seed 42 進行中（第 15 epoch 存檔後依排程暫停）
- 相關：修正 E123 的 HC manifest；提案 P032（登記與判定門檻）、P033（HC v2 泛化落差）、P029／P007／P031（改在 HC v2 上跑）、P011（同樣有洩漏）

## 目的
HAM10000 與 ISIC Archive 有一部分是同一批病灶：兩邊使用相同的 ISIC 病灶編號（lesion_id），但在我們的 manifest 裡被分進不同的 `cp005_group`。切分是以 `cp005_group` 為單位，所以同一個病灶可能一張在 train、一張在 val_select 或 val_assess。

E123 的 HC manifest、更早的 cp005 manifest，以及 P011 的下一代 manifest，都有這個問題。實際的重疊量：
- train∩val_select 167 個病灶
- train∩val_assess 102 個病灶
- val_select∩val_assess 27 個病灶
- 另有 9 列 train 與官方測試集同病灶

## 做法
- **先登記後產生**：規則寫在 P032 的判定門檻檔，之後才寫程式。
- **連通**：在 live 的三個 split 裡，用 `cp005_group`＋非空 `lesion_id` 做 union-find 連通。
- **保留規則**：一個連通分量跨 split 時，保留優先序最高的 split（val_assess > val_select > train），其餘列改為 excluded。
  - 只排除，不搬列，不改標籤。
- **官方保留集**：live 列的 lesion_id 若與官方測試集相同，也排除。
- **不覆寫既有檔**：寫成新檔 `cp005_manifest_hc_v2.csv`，母檔不動。
- **寫檔前的驗證**（任一不過就不寫檔）：
  - 列數、欄位、順序與母檔相同。
  - 只有被排除的列有變動，而且只改三欄。
  - live split 之間沒有任何 lesion_id、cp005_group、split_group_id 橫跨。
  - live 與官方保留集沒有共用 lesion_id。
  - train 仍有 8 類，每個來源的 val_select 仍有列。
- **獨立驗證**：另一個助理（Codex）用自己寫的程式從頭重建排除名單，與原名單 0 差異。
- **基準重跑**：用 HC v2 重跑 R2-HC-S20（convnext_small@384、20 epoch 短跑），seed 17 與 42。

## 結果
**manifest**
- 排除 642 列：跨 split 洩漏 633 列（train 576、val_select 57），與官方保留集同病灶 9 列（train）。
- val_assess 一列都沒變，所以新舊基準在 val_assess 上是**同一批 8,369 張影像**。
- HC v2 的 live 列數：train 54,812、val_select 10,496、val_assess 8,369。

**seed 17 基準（best epoch 20）**

主指標＝各來源 macro-F1_ge30 取最低：

| | val_select 最差 macro-F1_ge30 | val_assess 最差 macro-F1_ge30 | val_assess 最差來源 balanced accuracy | val_assess 平均來源 balanced accuracy |
|---|---|---|---|---|
| HC v2 seed 17 | 0.6781 | 0.6644 | 0.6238 | 0.7089 |
| HC（修正前）seed 17 | 0.6715 | 0.6623 | 0.6033 | 0.7160 |

val_assess 各來源 balanced accuracy：

| | BCN | HAM | ISIC | PAD |
|---|---|---|---|---|
| HC v2 seed 17 | 0.6238 | 0.7704 | 0.6971 | 0.7445 |
| HC（修正前）seed 17 | 0.6033 | 0.7758 | 0.7032 | 0.7818 |

HC v2 seed 17 在 val_assess 的各類召回與 one-vs-rest AUC：

| 類別 | AKIEC | BCC | BKL | DF | NV | VASC | MEL | SCC |
|---|---|---|---|---|---|---|---|---|
| 召回 | 0.54 | 0.87 | 0.60 | 0.55 | 0.90 | 0.79 | 0.69 | 0.61 |
| AUC | 0.873 | 0.973 | 0.911 | 0.916 | 0.966 | 0.966 | 0.916 | 0.925 |

整體：top-1／2／3 準確率 0.817／0.919／0.952，macro AUC 0.931。

## 推論
- 修正前的 manifest 讓同一個病灶同時出現在訓練與評估裡。**P032 之前的所有數字都量在有洩漏的 manifest 上**，包括本知識庫多數實驗頁。
  - 洩漏對分數的影響有多大，目前還沒量化。
  - 同一份 manifest 內的相對比較（例如消融）仍可參考，但絕對數字不要與 HC v2 的結果並列。
- 同一批 val_assess 影像上，HC v2 seed 17 的最差來源 balanced accuracy 高 2.05pp，平均低 0.71pp，PAD 降最多（只有 221 張）。
  - 只有一個 seed，差距在 seed 雜訊量級內（見 README「讀數字前要知道的事」第 4 點），要等 seed 42。
- 之後的實驗（P029、P007、P031、P034、P035）一律以 HC v2 的 R2-HC2-S20 seed 17／42 為對照。

## 限制
- 只處理 `lesion_id` 有填的列。沒有病灶編號的同病灶影像抓不到。
- 與官方保留集「同病人、不同病灶」的 281 個群組只做記錄，不在本次範圍。
- 「洩漏讓分數偏高」是合理推測，但沒有量過，不能當結論寫。

<!-- 族譜:開始（自動產生，勿手改） -->
## 前因與後果

**後果**
- 推翻或更正｜[E123](E123.md)（建立排除 ISIC 各屆挑戰賽官方測試集（與驗證集）的 ）：HC2 發現 E123 的 HC manifest 有 HAM 與 ISIC 共用病灶編號造成的跨切分洩漏，排除 642 列修正。
- 前置｜[G1](G1.md)（Grad-CAM 熱區只佔病灶一小塊：集中度、覆蓋率與遮）：G1 的 HC v2 重跑使用 HC2 的 seed 17 基準權重。

完整關係見 [族譜](../族譜.md)、[結論](../結論.md)。
<!-- 族譜:結束 -->

## 來源檔案
`模型改進/reports/P032_判定門檻.json`、`P032_病灶合併manifest.json`、`P032_獨立驗證.md`、`cp005_split_hc_v2.json`；`audit/p032_lesion_merge_manifest.py`、`audit/p032_verify_codex.py`；`results/R2-HC2-S20_e421390c_seed17/result.json`、`val_assess_logits.npz`。
