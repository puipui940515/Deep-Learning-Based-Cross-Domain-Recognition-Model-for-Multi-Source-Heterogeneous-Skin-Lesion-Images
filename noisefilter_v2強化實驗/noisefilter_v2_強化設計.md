# noisefilter v2 強化設計

建立日期：2026-09-17　狀態：`未開始`（程式與前處理層級量測已完成，尚未訓練）　適用線：CP-003 §6-2  
程式：`noisefilter_v2強化實驗/vendor/noisefilter_v2/`　設定：`noisefilter_v2強化實驗/config.json`

> **一句話**：v1 失敗不只是「單來源測錯場景」。四段濾鏡中有三個可以量到的設計缺陷，會直接破壞病灶對比與色度，而且會在 BCN 的黑色孔徑影像上製造新的來源指紋。v2 把這三個缺陷逐一修掉，並把兩段冗餘合成一段。v2 已經證明「不破壞影像」，但還沒證明「提升泛化」，後者要靠 §6 的實驗來回答。

---

## 1. 背景與現有證據

| 來源 | 內容 |
|---|---|
| `第一階段/noisefilter搭載實驗/搭載實驗記錄.md` | MLP 三 seed 平均乾淨 BA −3.09pp，未通過 seed std 門檻 |
| `第二階段/noisefilter搭載實驗/搭載實驗記錄.md` | ResNet-18（未預訓練）乾淨 BA −6.73pp，seed std 放大 4.49 倍 |
| `noisefilter_清單檢查報告.md` | GCC 與 PeripheralReference 的 delta cosine 0.9953（僅存在於 Markdown，見節點01 後續修正 01） |
| `開發歷程/節點02_*.md` §5.1 | 08 號之後停用；12 號篩選 23.45／100 |
| `開發歷程/CP-003_執行計畫_2026-09-08.md` §6-2 | 主張在多來源下重測，因為 v1 從未在它的設計場景被測過 |
| `資料治理與泛化修復/reports/04_equipment_composition_audit.json` | 來源差異是亮度（HAM 61.42% vs BCN 55.04% 中位數）、飽和度（29.20% vs 16.83%）、解析度與長寬比 |

CP-003 §6-2 的論點成立，但它預設 v1 的四段濾鏡本身沒有問題，只是場景不對。本文件第 2 節的量測顯示這個預設不成立：**如果直接拿 v1 去跑 6-2a，得到負結果時，無法分辨是「前端正規化這條路不行」還是「這個實作會破壞影像」。**

---

## 2. v1 的缺陷診斷（可重現）

量測腳本在 `probes/probe_v1.py`，結果在 `reports/probe_v1.json`。樣本是 27 張跨來源影像（HAM 12、BCN 8、PAD 7，清單見 `probes/probe_images.txt`）加上合成影像。這些都是前處理層級的量測，不涉及任何分類模型。

### D1　LogContrast：黑色孔徑會讓 log 標準差暴增

`LogContrast` 在整張影像上計算 log 亮度的標準差。皮膚鏡黑色孔徑的像素被 clamp 到 1e-4，取 log 後是 −9.2，因此標準差會暴增：

| 影像 | 黑色像素比例 | 全圖 log std | 排除黑色後 log std |
|---|---:|---:|---:|
| BCN_0000009536 | 36.10% | 2.155 | 0.531 |
| BCN_0000014405 | 35.70% | 2.181 | 0.493 |
| BCN_0000018987 | 4.70% | 1.218 | 0.462 |
| 合成（無孔徑） | 0% | 0.315 | — |
| 合成（有孔徑） | 約 29% | 3.422 | — |

校準值是 `target_std=0.3166`，所以帶孔徑的影像會被壓縮成原本對比的約 1/7 到 1/11。在合成影像上，alpha=1 時病灶對比只剩 1.40%（§4.1）。**這個效應只出現在有孔徑的來源（主要是 BCN），等於濾鏡自己製造了一個新的來源指紋**，和它的設計目的正好相反。視覺上的結果見 `reports/probe_visual_compare.png` 右上兩組：孔徑變成灰色，病灶被洗淡。

### D2　IlluminationFlatten：sigma 只有影像寬度的 5%，會把病灶本體當成光照減掉

log 域低通減法本身是正確的物理操作（Land & McCann 的 Retinex）。問題在於分界尺度：病灶本身就是一大塊低頻的暗區。

| 病灶半徑（佔寬度） | 0.05 | 0.10 | 0.18 | 0.28 | 0.38 |
|---|---:|---:|---:|---:|---:|
| alpha=1 後保留的病灶對比 | 64.60% | 33.20% | 17.00% | 11.70% | 11.40% |

HAM 典型病灶的半徑落在 0.1–0.3 之間。另外，這個濾鏡**逐通道**壓平：藍白色病灶（近似藍白面紗）的藍通道占比會從 41.58% 降到 31.98%。藍白面紗是黑色素瘤的指標，這表示濾鏡會直接削弱診斷訊號。設計稽核量到它是單段修正量最大的一段（MAE 0.0398），和第二階段 HAM 乾淨 BA −6.73pp 的方向一致。

> 這是設計層面的**可能原因**，不是已經證實的歸因。要證實需要 §6 的 N2 消融。

### D3　GCC 與 PeripheralReference 冗餘

這次在 27 張**跨來源**影像上重新量測（清單報告原本只用 HAM validation）：

- 兩者修正方向的 cosine：平均 0.9847，最小 0.8504
- PeripheralReference 單獨使用時的修正量是 MAE 0.0508；疊在 GCC 之後只剩 0.0083（16.34%）

兩者都是對角 von Kries 增益，差別只在取樣權重。**這次的數值有機器可讀來源**（`reports/probe_v1.json` 的 `D3_gcc_pr_redundancy`），可以補上節點01 後續修正 01 指出的證據鏈缺口，但注意樣本不同，不能直接取代 0.9953。

### D4　PeripheralReference 的參考白會被大病灶污染

這項在合成影像上的效應不大：病灶偏心且半徑 0.45 時，校正後皮膚偏離中性灰 3.28%。不過 40 張權重圖（`驗證/reports/noisefilter_design/peripheral_weight_maps_contact_sheet.png`）的縮圖**初步目視**顯示，約 7 張（#07、#12、#14、#21、#26、#35、#40）的病灶延伸進高權重環帶，另有 #01、#02、#05 的環帶內有大量毛髮。這只是縮圖目視，不能取代清單 D2 的正式人工檢查。

### D5　整合層的兩個靜默陷阱

1. v1 的 `NormalizedFilterModel` 把輸入寫死成 `[-1,1]`。現行主線（`train_regularized.py`）用的是 ImageNet mean／std；直接沿用的話，濾鏡會收到錯誤的像素值，而且不會報錯。
2. 把濾鏡包在模型外層後，參數名稱會變成 `backbone.features.*`，`parameter_groups_with_layer_decay` 用 `startswith("features.")` 判斷深度，所以所有層都會落到最深層，**layer decay 會靜默失效**。

---

## 3. v2 設計

### 3.1 結構

```
x ──► ReferenceMask ──► 參考權重 w = w_valid × w_spec × w_skin
 │         （孔徑、反光、病灶排除；可接 manifest 的 ROI）
 │
 ├─► ToneNormalize      Δ₁ = s（曝光）［可選：+ (k−1)(L−m)，gamma］
 ├─► ShadingCorrection  Δ₂ = −(二次曲面 − 均值)，只作用在亮度、三通道共用
 └─► SkinReferenceWB    Δ₃ = −log g_c，shades-of-gray p=6，只在皮膚像素上估計
                          
out = x · exp(α₁Δ₁ + α₂Δ₂ + α₃Δ₃)      ← log 域合成，只 clamp 一次
```

所有統計量都在 96×96 上**逐樣本**計算，不使用跨樣本統計，與 CP-003 §6-1 的 LayerNorm 論點一致。參數全部凍結，可訓練參數量和基線相同。

### 3.2 逐項對應

| v1 | 缺陷 | v2 | 依據 |
|---|---|---|---|
| LogContrast | D1 | **ToneNormalize**：統計量只在有效像素上算，用分位數取代標準差。預設只修曝光，修正量限制在 ±0.4（約 ×1.5） | 04 稽核只量到亮度差異，沒有 gamma 差異的證據；27 張樣本中有 15 張的 gamma 估計撞到上下限，顯示離散度的差異主要來自影像內容 |
| IlluminationFlatten | D2 | **ShadingCorrection**：二次多項式曲面，只在皮膚參考像素上用 IRLS（Cauchy 權重）擬合，只修亮度 | Cavalcanti et al. 2010 用 quadric 函數模擬皮膚照片的陰影；Glaister et al. 2013（MSIM）用參數化光照模型並只在皮膚像素上估計 |
| GCC + PeripheralReference | D3、D4 | **SkinReferenceWB**：兩段合成一段，在排除病灶、孔徑、反光後的皮膚像素上做 shades-of-gray；目標色度預設是訓練集皮膚色度的中位數（`canonical`），不是中性灰 | Finlayson & Trezzi 2004；Barata et al. 2015 證明色彩恆常能改善跨系統的皮膚鏡分類；Gessert et al. 2020 的 ISIC 2019 方案沿用 p=6 |
| 像素域 `(1−a)x + a·f(x)` | 多段疊加時每段都 clamp | log 域加總後只 clamp 一次，α 表示修正量的比例 | 三段都是乘性變換，在 log 域可以直接相加 |
| `NormalizedFilterModel` | D5-1 | **FilteredBackbone**：mean／std 必填，缺少就拒絕建構 | 端到端規格 v2 §4 |
| 外層包裝 | D5-2 | 對 `model.backbone` 計算 layer decay 分組 | — |
| — | 大病灶時參考像素不足 | `reference_fraction < 0.15` 時，Shading 和 WB 的強度按比例下修，並在 info 回報 | 對應端到端規格的 `roi_fallback` 精神 |

### 3.3 刻意保留的限制

- **膚色**：WB 會把不同膚色的色度往同一個目標推。在 alpha=1 時，PAD 深色皮膚的樣本明顯變淺、變灰（`reports/probe_visual_compare.png` 左欄倒數第二列）。膚色本身不是雜訊，所以預設 alpha 是 0.5、目標是 `canonical`，而且**必須按 Fitzpatrick 分組回報**（PAD-UFES-20 有這個欄位）。Kinyanjui et al. 2020 用非病灶皮膚的 ITA 估計膚色，本模組的參考權重可以直接拿來做同樣的事。
- **傳統色彩恆常的上限**：Branciforti et al. 2023 指出 Gray World 和 Shades-of-Gray 受統計假設限制。v2 不引入學習式的色彩恆常（例如 DermoCC-GAN），因為那會多出一個需要訓練、可能洩漏的模型。
- **非對角色偏**：相機色彩矩陣（CCM）的差異不是對角增益能完全抵銷的。§4 的相鄰擾動族會量這一點。
- **學習式與對齊式擴充**（`InvarianceLoss`、`ext_align`、`knob`）一行都沒改，本輪也不搭載，理由同 CP-003 §6-2 的注意事項。`IlluminantBankPerturb`（Galdran et al. 2017 的資料驅動光源增強）已實作，但預設不搭載，避免一次改兩個變因。

### 3.4 強度預設（2026-09-17 追加）

預設設定的修正在肉眼上不明顯（`reports/preset_default_filtered_only.png`），所以另外加了兩組更強的預設（`FilterChainV2.from_preset`）。以下數字都在 27 張樣本上量測：

| preset | 設定 | 跨來源色度差 | 飽和度差 | 平均像素改變量 | 病灶對比（r=0.18） |
|---|---|---:|---:|---:|---:|
| 原圖 | — | 0.155 | 13.57% | — | 100.00% |
| `default` | α=0.5、只修曝光 | 0.106 | 9.16% | 0.037 | 100.30% |
| `strong` | α=1、開 gamma、曝光上限 ±0.6 | 0.055 | 4.24% | 0.084 | 120.70% |
| `max` | 再改成灰色目標、放寬所有上限 | 0.055 | 4.89% | 0.097 | 121.60% |

比較圖見 `reports/preset_strong_max_vs_raw.png`。`strong` 的差異肉眼可見，跨來源色度差也降到原本的約 1/3。代價有兩個：一是深色皮膚（PAD）被明顯拉向平均膚色；二是 gamma 會依皮膚紋理放大病灶對比，放大倍率因影像而異。`max` 相對 `strong` 幾乎沒有再縮小來源差距，皮膚卻偏灰，所以只當作極端消融點。兩組已登記為 `N6`、`N7`（seed 17，pilot）。

亮度差距在三組中都沒有明顯縮小，因為這個指標包含 BCN 的黑色孔徑，而濾鏡刻意不改動孔徑。

---

## 4. v1 vs v2 前處理層級量測

腳本：`probes/probe_compare.py`，結果：`reports/probe_compare.json`。v1 使用第二階段的實測校準值；v2 在這 27 張樣本上自我校準（**正式實驗必須改用 train split**，見 `scripts/calibrate.py`）。

### 4.1 保真度：不該被改動的部分有沒有被改動

| 指標 | v1 預設 α | v2 預設 α | v1 α=1 | v2 α=1 |
|---|---:|---:|---:|---:|
| 病灶對比保留（r=0.10） | 67.60% | 100.40% | 48.00% | 100.90% |
| 病灶對比保留（r=0.18） | 52.90% | 100.30% | 17.40% | 100.60% |
| 病灶對比保留（r=0.30） | 48.10% | 99.80% | 8.20% | 99.70% |
| 病灶對比保留（黑色孔徑） | 1.90% | 100.50% | 1.40% | 101.00% |
| 病灶相對色度幅度保留 | 63.50% | 100.00% | 21.60% | 100.00% |
| 高頻能量比（中位數） | 1.34 倍 | 1.00 倍 | 2.45 倍 | 1.00 倍 |

v1 預設 α 是 `[0.25, 0.5, 0.5, 0.5]`，v2 預設 α 是 `[0.5, 0.5, 0.5]`。v1 的高頻能量放大，看起來來自 clamp 後的偽影（`probe_visual_compare.png` 裡 MEL 內部的白色斑點），這點尚未單獨驗證。

### 4.2 同族不變性（只能當 sanity check）

擾動用 `IlluminationPerturb(quadratic=0.25)`，數字是「濾波後殘差 ÷ 原始殘差」的中位數，越低越好。

| v1 預設 | v2 預設 | v1 α=1 | v2 α=1 |
|---:|---:|---:|---:|
| 0.63 | 0.61 | 0.05 | 0.32 |

在預設強度下兩者相當。v1 在 α=1 時幾乎完全抵銷擾動，但代價是 4.1 節的對比只剩 8–48%，也就是**它是靠抹平影像內容來達到不變性**。v2 在 α=1 時放棄了一部分不變性，換到完整的保真度。

### 4.3 獨立擾動族（嚴重度 3，比值越接近 1 越好；小於 1 表示有抵銷）

| 擾動 | 類別 | v1 預設 | v2 預設 |
|---|---|---:|---:|
| JPEG | 正交 | 1.09 | 1.00 |
| 失焦模糊 | 正交 | 1.11 | 1.00 |
| 動態模糊 | 正交 | 1.12 | 1.00 |
| 感光雜訊 | 正交 | 1.04 | 0.99 |
| 降採樣 | 正交 | 1.11 | 1.00 |
| 非對角 CCM | 相鄰 | 0.63 | 0.73 |
| 橫向色差 | 相鄰 | 1.04 | 1.00 |
| 帶色偏暗角 | 相鄰 | 0.74 | 0.55 |

v1 會把和它無關的擾動放大 4–12%，v2 則保持中性。擾動族的分類參考 Hendrycks & Dietterich 2019 與 Maron et al. 2021（SAM-C 的 noise／blur／dermoscopy／digital 四類）。

### 4.4 跨來源統計差距（27 張，僅供示意）

| | 亮度差 | 飽和度差 |
|---|---:|---:|
| 原圖 | 9.23% | 13.57% |
| v1 預設 | 7.87% | 4.96% |
| v2 預設 | 6.90% | 9.16% |
| v2 α=1 | 7.08% | 4.61% |

v2 預設強度縮小飽和度差距的幅度比 v1 小，這是 α=0.5 加上 canonical 目標的直接後果。亮度差距刻意沒有完全抹平（曝光修正上限 ±0.4），因為其中一部分是膚色。

---

## 5. 這些量測能說明什麼、不能說明什麼

**能說明**：在這些樣本上，v2 不會破壞病灶對比、病灶色度或高頻結構，在孔徑影像上也不會壓縮對比（v1 的 D1 問題），而且不會放大正交擾動。因此如果 §6 得到負結果，可以比較乾淨地歸因到「前端正規化在這個設定下沒有幫助」。

**不能說明**：v2 會不會提升跨來源 BA。27 張樣本、合成影像和同族擾動都不構成分類效益的證據（清單 F1、F2）。治理 v1 的 2s 雜訊帶是 3.88pp，前處理的效果很可能落在這個範圍內。

---

## 6. 實驗設計（預先登記，寫在 `config.json`）

基線：治理 v1 三 seed（`資料治理與泛化修復/reports/seed_variance_v1.json`），三來源平均 BA 70.78%，s = 1.94pp。

| 順序 | 代號 | 內容 | seeds | 成本 | 閘門 |
|---|---|---|---|---|---|
| 0 | 校準 | `scripts/calibrate.py`，train split，每來源 800 張 | — | 幾分鐘 | — |
| 1 | **G0** | `scripts/source_probe_input.py`：凍結的 ImageNet ConvNeXt-Tiny 特徵，比較 raw 和 filtered 的來源探針與疾病探針 | — | 幾分鐘，不需訓練 | 來源探針 BA 下降 ≥ 3pp，且疾病探針 BA 下降 ≤ 2pp |
| 2 | N0 pilot | 完整 v2 鏈 | 17 | 1 次訓練 | **G1**：HAM BA 不低於基線 seed 17 減去 HAM 的 1 個 s（3.83pp） |
| 3 | N0 | 完整 v2 鏈 | 42、2026 | 2 次訓練 | **G2**：與基線三 seed 比較；差值要大於較大的 s 才算通過（計畫書 §3.4），大於 2s 才能說「可區分」 |
| 4 | N1–N3 | 逐段消融（拿掉 tone、shading、WB） | 17 | 3 次，pilot | 只用來描述，不作正式結論 |
| 5 | N4、N5 | 低強度 α=0.25；開啟 gamma 正規化 | 17 | 2 次，pilot | 同上 |
| 6 | 擾動評估 | `scripts/eval_corruptions.py`，基線和 N0 各三個 checkpoint | — | 只做推論 | 正交、相鄰、同族分開報告 |

G0 不通過就停止，總成本只有兩次特徵抽取。和 CP-003 原本的 6-2a/b/c 相比，本設計多了 G0 閘門，也把消融改成 v2 的三段（v2 已經沒有 GCC 和 PR 的分別）。

每一組都要同時回報：

1. 逐來源 BA、三來源平均、BCN 加權穩健分數
2. 逐類別 recall（尤其是 DF 和 MEL）
3. **PAD 按 Fitzpatrick 分組的 BA**（§3.3）
4. 校準檔的 `per_source_median_diagnostics`：各來源的曝光、陰影幅度、光源色度、低信心比例
5. `result.json` 內的 `calibration_sha256`、`trainer_base_sha256`、`governance_config_sha256`

---

## 7. 已知風險

| 風險 | 說明 | 處置 |
|---|---|---|
| 增強互相抵銷 | 治理 v1 的 ColorJitter、RandomAutocontrast 在濾鏡之前套用，濾鏡會抵銷一部分增強 | 這本來就是濾鏡的目的；但要在結論中寫明「等效增強強度下降」這個混淆因素 |
| 大病灶外插 | 參考像素只在影像邊緣時，二次曲面向中心外插可能過度修正 | ridge=0.02，並把修正幅度上限設為 0.7；低信心時自動降強度；可接 ROI（`roi_to_skin_weight`） |
| 膚色被正規化 | §3.3 | α≤0.5、canonical 目標、按 Fitzpatrick 分組回報 |
| 校準洩漏 | 用 validation 校準會把驗證來源的簽章帶進來 | `load_calibration` 會檢查 `split_used == "train"`，不符合就拒絕執行 |
| 單 seed 過度解讀 | — | N1–N5 標記為 `pilot: true`，依格式約定不得作為正式結論 |
| 與 ROI 線（端到端規格 v2）交互 | ROI 裁切後參考皮膚變少 | ROI 上線後改用 manifest 的 `roi_*` 產生 `skin_weight`，並重新校準 |

---

## 8. 參考文獻

1. Land, E. H., & McCann, J. J. (1971). Lightness and Retinex theory. *JOSA*, 61(1).
2. Finlayson, G. D., & Trezzi, E. (2004). Shades of gray and colour constancy. *Color Imaging Conference*.
3. Cavalcanti, P. G., Scharcanski, J., & Lopes, C. B. O. (2010). [Shading attenuation in human skin color images](https://link.springer.com/content/pdf/10.1007/978-3-642-17289-2_19.pdf). *ISVC 2010, LNCS*.
4. Glaister, J., Amelard, R., Wong, A., & Clausi, D. A. (2013). [MSIM: Multistage illumination modeling of dermatological photographs for illumination-corrected skin lesion analysis](https://pubmed.ncbi.nlm.nih.gov/23380843/). *IEEE TBME*.
5. Barata, C., Celebi, M. E., & Marques, J. S. (2015). [Improving dermoscopy image classification using color constancy](https://ieeexplore.ieee.org/document/6866131/). *IEEE JBHI*.
6. Galdran, A., et al. (2017). [Data-driven color augmentation techniques for deep skin image analysis](https://arxiv.org/html/1703.03702v1). arXiv:1703.03702.
7. Hendrycks, D., & Dietterich, T. (2019). Benchmarking neural network robustness to common corruptions and perturbations. *ICLR*.
8. Gessert, N., et al. (2020). [Skin lesion classification using ensembles of multi-resolution EfficientNets with meta data](https://www.sciencedirect.com/science/article/pii/S2215016120300832). *MethodsX*.（沿用 SoG p=6，但**沒有**針對這一步做消融）
9. Bissoto, A., Valle, E., & Avila, S. (2020). [Debiasing skin lesion datasets and models? Not so fast](https://openaccess.thecvf.com/content_CVPRW_2020/papers/w42/Bissoto_Debiasing_Skin_Lesion_Datasets_and_Models_Not_So_Fast_CVPRW_2020_paper.pdf). *CVPR Workshops*.
10. Kinyanjui, N. M., et al. (2020). [Fairness of classifiers across skin tones in dermatology](https://krvarshney.github.io/pubs/KinyanjuiOCCPSV_miccai2020.pdf). *MICCAI*.
11. Maron, R. C., et al. (2021). [A benchmark for neural network robustness in skin cancer classification](https://www.sciencedirect.com/science/article/pii/S0959804921004421). *European Journal of Cancer*.（[SAM-C／SAM-P](https://github.com/DBO-DKFZ/SCP-Robustness-Benchmark)）
12. Branciforti, F., et al. (2023). [Impact of artificial intelligence-based color constancy on dermoscopical assessment of skin lesions](https://pmc.ncbi.nlm.nih.gov/articles/PMC10603308/). *Skin Research and Technology*.

**證據強度註記**：文獻 5 與 8 支持「shades-of-gray 在皮膚鏡上常被採用且可能有益」，但文獻 8 沒有做消融，文獻 12 也指出統計式色彩恆常的限制。文獻中沒有「前端物理正規化必然提升跨來源泛化」的共識，所以本設計把它當作待檢驗的假設，而不是已知結論。

---

## 修訂紀錄

| 日期 | 內容 |
|---|---|
| 2026-09-17 | 建立。v1 診斷、v2 設計、前處理層級量測、預先登記實驗 |
| 2026-09-17 | 追加 §3.4 強度預設（strong／max）與 N6、N7 |
