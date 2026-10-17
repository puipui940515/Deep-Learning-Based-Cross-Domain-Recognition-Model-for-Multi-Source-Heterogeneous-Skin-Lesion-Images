# noisefilter 實驗清單檢查報告

檢查日期：2026-08-15  
對應清單：`noisefilter_實驗待處理清單.md`  
結果：45 項中 31 項已完成或已確認條件不觸發，14 項仍待處理。

## 結論摘要

1. A1–A3 的 ISIC ID 交集全部為 0，因此聚合列可以保留，沒有觸發 incident 或 bootstrap 重算。
2. 第二階段「全部相容標籤」雖有正向 bootstrap CI，但 +0.0186 小於搭載組 seed std 0.0234，依計畫書 §3.4 不通過，不能納入架構或概括為提升泛化能力。
3. seed 42 並非 loss 發散或完全多數類別塌縮；它收斂到較差解，且 DF recall 持續為 0。第二階段搭載組乾淨 BA seed std 是基線 4.49 倍。
4. `GlobalColorConstancy` 與 `PeripheralReference` 的修正方向高度重疊，平均 cosine 0.9953，是目前最明確的設計風險。
5. 現行 `IlluminationPerturb` 與濾鏡目標同屬光照擾動族，只能作 sanity check；獨立擾動族尚未建立。
6. 四組 ablation、alpha 0.05／0.10 與 v6 三 seed 均尚未執行。

## A. 資料重疊

| 檢查 | 左集合 | 右集合 | 交集 | 判定 |
|---|---:|---:|---:|---|
| A1 HAM metadata vs 三個 ISIC metadata | 10,015 | 7,886 | 0 | 通過 |
| A2 BCN collection 249 vs ISIC 安全子集 | 18,946 | 7,886 | 0 | 通過 |
| A3 HAM validation vs ISIC mapped | 1,504 | 6,607 | 0 | 通過 |

A2 使用完整 collection 249 metadata 作保守上界；完整集合交集為 0，因此本地 18,914 張 BCN 子集也不可能含相同 ISIC ID。A4 不需撤表，A5、A6 的條件均未觸發。此檢查只排除 ID 重疊，不能排除不同 ID 的相同內容。

證據：`驗證/reports/noisefilter_checklist_evidence.json`。

## B. 統計報告

兩份正式結論現在同時列出三 seed 平均 ± std 與 ensemble bootstrap CI，並明確區分：

- seed std：重新訓練一次的變異。
- bootstrap CI：固定已訓練模型，換一批影像的抽樣變異。

依「正向差值 > 搭載組 seed std」判定，第一階段只有 PAD 擾動列通過；第二階段通過 BCN 乾淨／擾動、PAD 乾淨／擾動、ISIC 擾動。第二階段全部相容標籤乾淨 +0.0186／0.0234 與擾動 +0.0185／0.0197 均未通過。

第一階段原始 HAM validation 平均乾淨差值 −0.0309，小於搭載組 sample std 0.0405；實驗記錄已改為「方向為負且未通過種子變異門檻」，不把 3.09 個百分點寫成穩定效應。

## C. 訓練穩定性

| 實驗 | seed 42 val BA 初始／最佳／末期 | val loss 初始／最低／末期 | 判定 |
|---|---:|---:|---|
| 第一階段搭載 | 0.1543／0.2765／0.2620 | 0.9952／0.8465／0.9039 | 無發散；較差局部解；最佳點 DF recall=0 |
| 第二階段搭載 | 0.2569／0.4585／0.4273 | 0.8577／0.6667／0.6667 | 無發散；非完全多數類塌縮；最佳點 DF recall=0 |

乾淨 BA sample std：第一階段基線 0.0266、搭載 0.0405，倍率 1.52；第二階段基線 0.0098、搭載 0.0440，倍率 4.49。由於沒有判定成最佳化發散，C4 不觸發重跑。

完整曲線保留於兩個 `stage*_seed42.json` 的 `history`，摘要位於 `驗證/reports/noisefilter_checklist_evidence.json`。

## D. 濾鏡設計

D1 已輸出 40 張固定 HAM validation 樣本的 original／weight overlay 與 contact sheet。權重統計：中央 `r<0.5` 平均 0.0062、外環 `r>0.8` 平均 0.8524、權重大於 0.5 的像素約 50.1%。

D2 尚待人工目視：目前 Windows ACL 阻止本輪直接顯示新產生的 contact sheet；更重要的是，目視只能做抽樣判斷，不能替代病灶遮罩。D3 無法可靠完成，因專案中的 HAM10000 沒有 lesion segmentation mask。

在全部 1,504 張 validation、stage2 實際 checkpoint 與固定 alpha 下：

| 模組／組合 | 平均實際像素 MAE |
|---|---:|
| LogContrast | 0.0179 |
| IlluminationFlatten | 0.0398 |
| GlobalColorConstancy | 0.0436 |
| PeripheralReference | 0.0222 |
| 完整 chain 對輸入 | 0.0769 |
| 完整 chain 中 GCC 的實際貢獻 | 0.0218 |
| 完整 chain 中 PeripheralReference 的實際貢獻 | 0.0222 |

`GlobalColorConstancy` 與 `PeripheralReference` delta cosine 平均 0.9953，顯示功能高度重疊。`LogContrast` 對 GCC／Peripheral 的平均 cosine 分別約 −0.0155／−0.0143，主要功能不重疊。

圖檔與數值：`驗證/reports/noisefilter_design/`。

## E、F、G 未完成實驗

- E1–E7：沒有四個逐一關閉 ablation、alpha 0.05／0.10 或相應 OOD 產物。
- F3–F4：沒有 JPEG 壓縮、動態模糊或相機色彩管理等第二擾動族。
- G1–G3：v6 ImageNet 預訓練 ResNet-18 尚無三 seed 結果。

F1、F2、F5 已完成：正式結論已把現行光照擾動定位為同族 sanity check，並移除把它當作獨立模組效益的措辭。

## H. 逐類別 recall 與絕對水準

以下為乾淨影像、三 seed 機率 ensemble：

| 階段／版本 | HAM BA（×0.143） | BCN BA（×0.143） | PAD BA（×0.143） | ISIC BA（×0.143） | 零 recall |
|---|---:|---:|---:|---:|---|
| 第一階段基線 | 0.3412（2.39×） | 0.2226（1.56×） | 0.2771（1.94×） | 0.2290（1.60×） | HAM/BCN：DF |
| 第一階段搭載 | 0.3528（2.47×） | 0.2082（1.46×） | 0.2715（1.90×） | 0.2176（1.52×） | HAM/BCN：DF |
| 第二階段基線 | 0.5861（4.10×） | 0.2211（1.55×） | 0.2877（2.01×） | 0.2364（1.65×） | BCN：DF |
| 第二階段搭載 | 0.5394（3.78×） | 0.2509（1.76×） | 0.3155（2.21×） | 0.2636（1.85×） | HAM/BCN：DF |

DF 映射已核對：HAM label 3 與 BCN diagnosis `DF` 均映射到 class 3，未發現程式映射錯誤。零 recall 是稀有類別／模型結果。完整 112 列逐類別數值在 `驗證/reports/noisefilter_per_class_recall.csv`。外部來源 BA 約 0.21–0.32，報告已加入此限制。

## I. 結論措辭

正式結論現在限定於未預訓練 ResNet-18、固定 alpha 與七類設定，保留 HAM10000 同域代價 −0.0466，並明記第一階段未出現跨來源增益。未限定的「提升泛化能力」已移除。

A1–A3 全為 0 後，PAD-UFES-20 不再是「唯一通過重疊檢查」的集合；較精確的說法是 PAD 為唯一不依賴 ISIC ID 稽核、來源結構上獨立的集合。

## 下一步順序

1. 人工檢視 40 張權重圖；若外環常含病灶，需先取得 segmentation mask 再做 D3。
2. 優先做 `PeripheralReference` 與 `GlobalColorConstancy` ablation，因兩者 delta cosine 0.9953。
3. 補 alpha 0.05／0.10，並以 HAM 乾淨 BA 不明顯退化作 gate。
4. 建立獨立擾動族，再評估穩健性。
5. 完成 v6 三 seed 後，才判斷效果能否延續到預訓練強模型。
