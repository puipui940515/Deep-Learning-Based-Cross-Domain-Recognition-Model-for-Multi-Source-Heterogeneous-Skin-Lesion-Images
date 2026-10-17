# 全資料集正式測試協定

建立日期：2026-08-14  
狀態：模型、checkpoint、資料映射與統計方式先固定，測試期間不調參。

## 目的

比較第一階段 v1／第二階段 v5 基線與固定核心 noisefilter 搭載版本，在全部本地資料來源上的分類表現及光照擾動穩定性。

## 全量範圍

| 來源 | 全部影像 | 用於相容分類指標 | 其餘影像用途 |
|---|---:|---:|---|
| HAM10000 | 10,015 | validation 1,504 | train 7,008 與封存 test 1,503 只做無標籤穩定性 |
| SCIN | 820 | 0 | 全部只做穩定性；不把臨床鑑別診斷硬套成 HAM 類別 |
| PAD-UFES-20 | 2,298 | 2,106 | SCC 192 只做穩定性 |
| ISIC Archive | 7,886 | BCC＋MEL 6,607 | SCC 1,279 只做穩定性 |
| BCN20000 | 18,914 | train 中七個相容類別 11,982 | train SCC 431 與無標籤 test 6,501 只做穩定性 |
| **合計** | **39,933** | **22,199** | **17,734** |

## 類別映射

HAM 類別索引：0 AKIEC、1 BCC、2 BKL、3 DF、4 NV、5 VASC、6 MEL。

- BCN：AK→0、BCC→1、BKL→2、DF→3、NV→4、VASC→5、MEL→6；SCC 不映射。
- PAD：ACK→0、BCC→1、SEK→2、NEV→4、MEL→6；SCC 不映射。
- ISIC：BCC→1、Melanoma→6；SCC 不映射。
- SCIN：全部不映射。

## 模型

- 第一階段：v1 seeds 17／42／2026，對照同 seeds 的固定核心 noisefilter 搭載版本。
- 第二階段：v5 seeds 17／42／2026，對照同 seeds 的固定核心 noisefilter 搭載版本。
- 搭載內容：LogContrast、IlluminationFlatten、GlobalColorConstancy、PeripheralReference。
- Alpha：`[0.25, 0.5, 0.5, 0.5]`；沿用 train-only 校準 checkpoint。
- 不重新訓練、不選新 checkpoint、不使用本測試調參。

## 指標

分類指標只在 22,199 張相容標籤影像計算：

- Balanced Accuracy（主指標）
- Accuracy
- 各來源分開結果
- 三 seeds 平均與標準差
- 三 seeds 機率平均 ensemble 的搭載－基線 BA 差值
- 依類別分層 bootstrap 1,000 次之 95% 信賴區間

全部 39,933 張均計算：

- 乾淨／合成光照擾動之預測一致率
- Softmax 機率 L1 漂移
- 平均乾淨信心

## 防止洩漏

- HAM test 的 label 在 manifest 中設為不可用，不計算任何分類效能。
- HAM train 同樣不列入正式分類指標，避免用訓練樣本美化結果。
- BCN 官方 test 無標籤，不推測或補標。
- 測試結果不得再用來挑選本輪 alpha 或 checkpoint；若據此提出新設定，必須建立下一個獨立實驗。

## 超大影像解碼規則

- ISIC 多層金字塔 TIFF 不解碼數億像素主層；使用仍不小於模型輸入的最小內建解析度層。
- 大型 JPEG 使用 Pillow JPEG draft 降採樣後再縮放。
- Pillow 像素安全上限設為 500,000,000；不無限制關閉 decompression-bomb 保護。

## 限制

- 不同來源的疾病定義、攝影模式與病例組成不同；來源間 BA 不應直接視為同一臨床任務。
- 全量指的是全部本地來源影像條目；未進行跨來源內容去重，因此潛在相同影像仍按來源分開統計。
- 合成光照擾動只代表指定的技術擾動，不等同所有真實 domain shift。
