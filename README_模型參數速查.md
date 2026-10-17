# SkinDetect 模型參數速查

整理日期：2026-09-23。所有數值直接取自專案內的 config 與 result 檔，未經推估。
每一節結尾都標出來源檔案路徑，被追問時可以當場翻。

---

## 一、全專案共通

| 項目 | 值 | 來源 |
|---|---|---|
| 疾病類別 | 7 類：AKIEC、BCC、BKL、DF、NV、VASC、MEL | `多來源混合訓練_第二版/config.json` |
| HAM10000 切分 | train 7,008／validation 1,504，依 lesion 分組，切分 seed 20260814 | `第一階段/config/stage1.json` |
| seeds | 17／42／2026 | 各階段 config |
| 主要指標 | Validation Balanced Accuracy | 全專案 |
| 輔助指標 | Macro-F1、Accuracy、ECE、逐類 recall、混淆矩陣 | 各 `result.json` |
| 測試集 | 全程封存，所有結果皆 `test_used: false` | 各 `result.json` |
| 納入規則 | 提升幅度小於 seed 樣本標準差者不納入 | `皮膚病偵測_漸進式架構實驗計畫書.md` §3.4 |

**有效批次**：v5 之後所有實驗的 `batch_size × gradient_accumulation` 都等於 **32**，只是拆法不同（顯存越吃緊就把 batch 拆越小、累積次數越多）。被問到批次設定不一致時，這是答案。

---

## 二、逐模型參數

### 章節 01｜MLP（第一階段 v1）

| 項目 | 值 |
|---|---|
| 特徵擷取模型 | MLP（展平後全連接） |
| 參數量 | 約 6.43M |
| 預訓練權重 | 不使用 |
| 輸入 | 64 × 64 |
| 資料增強 | 無 |
| batch / 梯度累積 | 64 / 1（有效批次 64） |
| epochs / 早停 | 30 / patience 7 |
| 最佳化器 | AdamW |
| learning rate | 1e-3 |
| weight decay | 1e-4 |
| layer decay | 無 |
| 損失 | Cross-Entropy |
| 結果 | 三 seed BA 平均 **35.37%**（33.76／33.91／38.44），s = 2.66 |

來源：`第一階段/config/stage1.json`、`第一階段/noisefilter搭載實驗/搭載實驗記錄.md`

> 註：35.37% 取自 noisefilter 搭載實驗的**基線**欄，那是 v1 在同一份固定切分上的三 seed 乾淨 BA。

---

### 章節 02｜ResNet18 從零訓練（第二階段 v5）

| 項目 | 值 |
|---|---|
| 特徵擷取模型 | ResNet18 |
| 參數量 | 約 11.18M |
| 預訓練權重 | **不使用**（`pretrained: false`） |
| 輸入 | 224 × 224 |
| batch / 梯度累積 | 32 / 1（有效批次 32） |
| epochs / 早停 | 30 / patience 7 |
| learning rate | 3e-4（base） |
| weight decay | 1e-4 |
| layer decay | **關閉** |
| 損失 | Cross-Entropy |
| 結果 | 三 seed BA 平均 **57.28%**，s = 0.98，Macro-F1 57.95% |

來源：`第二階段/config/stage2.json`、`第二階段/results/version_summary.csv`

---

### 章節 03｜ResNet18 + ImageNet（第二階段 v6）

與 v5 **唯一的差別是 `pretrained: true`**，其餘全部相同。

| 項目 | 值 |
|---|---|
| 預訓練權重 | ImageNet |
| 其餘設定 | 同 v5（224、batch 32、累積 1、30 epochs、lr 3e-4、layer decay 關閉） |
| 結果 | 三 seed BA 平均 **70.90%**，s = 2.88，Macro-F1 71.43% |
| 對前一版差值 | **+13.62 個百分點** |

來源：同上

---

### 章節 04｜ConvNeXt-Tiny + ImageNet 384（第二階段 v8）

| 項目 | 值 |
|---|---|
| 特徵擷取模型 | ConvNeXt-Tiny |
| 參數量 | 約 27.83M |
| 預訓練權重 | ImageNet |
| 輸入 | **384 × 384** |
| batch / 梯度累積 | 8 / 4（有效批次 32） |
| epochs / 早停 | 30 / patience 7 |
| learning rate | 3e-4（base） |
| weight decay | 1e-4 |
| layer decay | **0.7（開啟）** |
| 損失 | Cross-Entropy |
| 結果 | 三 seed BA 平均 **80.97%**，s = 1.17，Macro-F1 80.37% |

**中間那一版（v7，簡報未單獨列頁）**：ConvNeXt-Tiny、**224**、ImageNet、batch 16 / 累積 2、layer decay 0.7 → 三 seed BA **77.30%**，s = 0.51。

> v6 → v7 同時改了三件事：特徵擷取模型、批次拆法、layer decay 從關閉變開啟。所以 +6.4 是版本差距，不能歸因給架構。

來源：`第二階段/config/stage2.json`、`第二階段/results/version_summary.csv`

---

### 部位辨識模型（DensePose 五類）

| 項目 | 值 |
|---|---|
| 特徵擷取模型 | ConvNeXt-Tiny |
| 預訓練權重 | **ImageNet**（它自己也是從 ImageNet 出發的） |
| 輸入 | 224 × 224，保留部位周邊人體脈絡的裁切 |
| 訓練資料 | DensePose-COCO 人體部位裁切，**不是皮膚影像、不含疾病標籤** |
| 類別 | head／torso／upper_extremity／lower_extremity／hands_feet |
| 取樣 | 固定抽樣 train 50,000／val 10,000，sample seed 20260824 |
| batch | 16 |
| epochs | 8 |
| learning rate | 3e-4 |
| weight decay | 1e-4 |
| 損失 | **未加權** Cross-Entropy |
| seeds | 真標籤 17、42；亂標籤控制組 17 |
| 結果 | 真標籤兩 seed BA 平均 **91.48%**（91.44／91.52），s ≈ 0.06 |
| 亂標籤控制組 | BA **20.00%** ＝ 五分類隨機 |
| 測試集 | DensePose minival 未使用 |

來源：`部位預測階段/DensePose_部位預訓練/results/overnight_2026-08-24/正式實驗記錄.md`

> 注意：`部位預測階段/` 底下另有一個 **HAM10000 五類部位的 ResNet-18** 模型（BA 約 50.1%），那是更早的探索模型，**不是**章節 05／07 使用的那一個。

---

### 章節 05｜用法一：凍結成第二條特徵路徑

| 項目 | 值 |
|---|---|
| 可訓練路徑 | ConvNeXt-Tiny，ImageNet 初始化，正常訓練 |
| 凍結路徑 | ConvNeXt-Tiny，`eval` 模式、零可訓練參數 |
| 特徵融合 | 兩路各輸出 768 維 pooled feature → 串接 1,536 維 → Linear 1,536→7 |
| 總參數量 | 約 56.42M（約為單路的兩倍） |
| 輸入 | 224 × 224 |
| batch / 梯度累積 | 16 / 2（有效批次 32） |
| **epochs** | **5（無早停）** ← 探索性短跑 |
| learning rate | 3e-4 |
| weight decay | 1e-4 |
| layer decay | 0.7 |
| 損失 | 未加權 Cross-Entropy |
| seeds | 17／42／2026 |
| 正規化 | student 用 `[0.5,0.5,0.5]`；teacher 轉回 `[0,1]` 後套 ImageNet mean/std |
| 推論 | **兩條路徑都必須執行** |

三組結果（三 seed BA 平均）：

| 凍結路徑放什麼 | BA | s | 最佳 epoch |
|---|---|---|---|
| 部位辨識模型（真標籤） | **76.13%** | 0.65 | 5／5／4 |
| ImageNet 模型 | **76.04%** | 1.13 | 5／5／5 |
| 部位辨識模型（亂標籤） | **75.39%** | 1.76 | 4／5／4 |

來源：`第二階段/並行凍結部位特徵實驗/config.json`、`README.md`、`results/summary.json`

> **已知限制**：亂標籤 teacher 的預訓練 epoch 與真標籤不匹配（config 標註 `exploratory_pretrain_duration_mismatch`），章節 07 已改用對齊版本。

---

### 章節 06｜ImageNet 完整微調

| 項目 | 值 |
|---|---|
| 特徵擷取模型 | ConvNeXt-Tiny（單路） |
| 參數量 | 約 27.83M |
| 預訓練權重 | ImageNet，**全部參數解凍** |
| 輸入 | 224 × 224 |
| batch / 梯度累積 | 16 / 2（有效批次 32） |
| **epochs / 早停** | **30 / patience 7** |
| learning rate | 3e-4 |
| weight decay | 1e-4 |
| layer decay | 0.7 |
| 損失 | Cross-Entropy |
| seeds | 17／42／2026 |
| 結果 | 三 seed BA 平均 **77.50%**（78.13／77.44／76.93），s = 0.60 |
| 最佳 epoch | 16／11／9 |
| Accuracy | 平均 85.7%；ECE 平均 9.79% |

逐類 recall（三 seed 平均）：

| AKIEC | BCC | BKL | DF | NV | VASC | **MEL** |
|---|---|---|---|---|---|---|
| 72.8 | 84.4 | 70.7 | 79.6 | 93.7 | 83.3 | **57.9** |

來源：`第二階段/部位權重完整微調正式對照/config.json`、`results/summary.json`

> **與章節 05 的 epoch 預算不同**（30 vs 5）。若只取前 5 個 epoch 內的最佳，本組是 **74.75%**（s = 1.71），反而低於雙路的 76.13%。跨章節的絕對分數不適合嚴格並列。

---

### 章節 07｜用法二：部位辨識模型的權重當起點

與章節 06 **共用同一份 config**，唯一差別是初始化權重的來源。

| 項目 | 值 |
|---|---|
| 預訓練權重 | 部位辨識模型（`densepose_true_seed17.pt`），全部參數解凍 |
| 權重 SHA-256 | `D16B37…C215C59` |
| 其餘設定 | 同章節 06 |
| 結果 | **seed 17 BA 68.61%**（另外兩個 seed 尚未完成） |
| 同 seed 對照 | ImageNet 起點 78.13% → 差 **9.52 個百分點** |
| 採納門檻 | 平均提升至少 1 個百分點才視為有實務意義 |

來源：`第二階段/部位權重完整微調正式對照/config.json`、`results/summary.json`

---

### 章節 08｜三來源混合訓練（目前 UI 預設）

| 項目 | 值 |
|---|---|
| 特徵擷取模型 | ConvNeXt-Tiny |
| 預訓練權重 | ImageNet |
| 輸入 | 224 × 224 |
| batch / 梯度累積 | 16 / 2（有效批次 32） |
| epochs / 早停 | 8 / patience 4 |
| learning rate | 3e-4 |
| weight decay | 1e-4 |
| layer decay | 0.7 |
| 取樣 | source-balanced、class-smoothed weighted sampler，`class_balance_alpha = 0.5` |
| **選模指標** | `mean_source_balanced_accuracy`（各來源只算它支援的類別） |
| seed | **僅 17**（單一 seed） |
| 訓練張數 | 18,979 |
| 驗證張數 | BCN 1,716／HAM 1,504／PAD 401 |
| 最佳 epoch | 6 |

結果（seed 17）：

| 來源 | BA | Macro-F1 | Accuracy | ECE |
|---|---|---|---|---|
| HAM10000 | 79.10% | 76.12% | 83.38% | 9.71% |
| BCN20000 | 57.79% | 59.36% | 68.24% | 18.13% |
| PAD-UFES-20 | 71.21% | 70.71% | 76.56% | 16.54% |
| **三來源平均** | **69.37%** | — | — | — |

訓練 BA 95.79%，與驗證平均差 26.42 個百分點。

> **PAD 只支援 5 類**（0、1、2、4、6，缺 DF 與 VASC），所以它的 BA 是五類平均，與另外兩個來源的七類 BA 不是同一個數字。

來源：`多來源混合訓練_第二版/config.json`、`results/imagenet_seed17/result.json`

---

### 章節 09｜資料治理版

與章節 08 **不只資料不同，訓練設定也換了**：

| 項目 | 章節 08 | 章節 09 |
|---|---|---|
| learning rate | 3e-4 | **1e-4** |
| weight decay | 1e-4 | **0.05** |
| layer decay | 0.7 | **0.75** |
| epochs / 早停 | 8 / 4 | **12 / 4** |
| label smoothing | 無 | **0.1** |
| mixup | 無 | **alpha 0.2** |
| 梯度裁剪 | 無 | **norm 1.0** |
| 正規化 | 0.5／0.5 | **ImageNet mean/std** |
| 選模指標 | 三來源平均 BA | **0.5 × 三來源平均 + 0.5 × 最差來源**（實際上最差的一直是 BCN） |

其餘相同：ConvNeXt-Tiny、ImageNet、224、batch 16／累積 2、`class_balance_alpha 0.5`。

去重門檻：pHash 距離 ≤ 1、dHash ≤ 2 判定為近重複；pHash ≤ 4、dHash ≤ 8 列入人工複查。

結果：

| | BA |
|---|---|
| seed 17 三來源平均 | **72.06%**（HAM 76.83／BCN 62.83／PAD 76.54） |
| 三 seed 平均 | **70.78%**，s = 1.94 |
| ECE（seed 17） | HAM 7.39%／BCN 3.26%／PAD 5.74% |

來源：`資料治理與泛化修復/config.json`、`reports/seed_variance_v1.json`、`results/formal_v1/regularized_seed17/result.json`

> **與章節 08 不可直接比較**：驗證切分不同、選模指標不同、訓練設定不同、章節 08 只有一個 seed。公平比較需要把章節 08 的權重放到治理後的相同切分重新評估，尚未執行。

---

## 三、架構特性速記

| | MLP | ResNet18 | ConvNeXt-Tiny |
|---|---|---|---|
| 年份 | — | 2015 | 2022 |
| 參數量 | 6.43M | 11.18M | 27.83M |
| 核心機制 | 全連接 | 3×3 卷積 + 殘差連接 | 7×7 depthwise 卷積 + inverted bottleneck |
| 正規化 | — | BatchNorm | LayerNorm |
| 激活 | ReLU | ReLU | GELU |
| 空間先驗 | 無 | 局部性 + 權重共享 | 同左，感受野更大 |
| Grad-CAM | 不支援 | 支援 | 支援 |

**MLP**：展平後每個像素與每個神經元獨立連線，沒有任何空間假設。代價是丟失鄰接關係、沒有平移不變性、沒有空間特徵圖。

**ResNet18**：卷積帶來局部性與權重共享，病灶出現在哪裡都能偵測。殘差連接讓梯度可以繞過中間層直接回傳，解決深層網路退化。

**ConvNeXt-Tiny**：把 ResNet 依 Transformer 的設計慣例重新改造，本體仍是純卷積。主要改動是大 kernel 的 depthwise 卷積、inverted bottleneck、LayerNorm 取代 BatchNorm、GELU 取代 ReLU、減少正規化與激活層數量。保留卷積的歸納偏置，因此不需要 ViT 那樣的資料量。

---

## 四、設定檔中已定義但尚無結果

| 版本 | 設定 | 狀態 |
|---|---|---|
| v9 | ConvNeXt-Tiny、384、**logit-adjusted CE** | 三 seed 未完成 |
| v10 | ConvNeXt-Tiny、224、**pretrained: false** | 無結果 |
| 章節 07 的 C 組 | 亂標籤權重初始化（對齊版） | 未執行 |
| noisefilter v2 | ToneNormalize／ShadingCorrection／SkinReferenceWB | 狀態「未開始」，僅有前處理層級量測 |

---

## 五、容易被問到的不一致

1. **批次大小不同** — 有效批次都是 32，只是顯存吃緊時拆得更細（v8 是 8×4）。
2. **layer decay 有開有關** — v5、v6 關閉，v7 之後開啟。這是 v6→v7 的混合變因之一。
3. **章節 05 只跑 5 epochs** — 探索性短跑，三組內部比較仍然受控；跨章節的絕對分數不宜並列。
4. **章節 07 只有一個 seed** — 另外兩個尚未補完。
5. **部位辨識模型只有兩個 seed** — 尚未補第三個。
6. **PAD 的 BA 只涵蓋五類** — 它沒有 DF 與 VASC 的樣本。
7. **章節 08 與 09 的選模指標不同** — 前者是三來源平均，後者是 0.5×平均 + 0.5×最差來源。
