# CP-005 模型改進：執行入口

更新：2026-10-06。依使用者提供的計畫建置，原文快照為 [CP-005_使用者原始計畫.md](CP-005_使用者原始計畫.md)，並依實際 manifest 修訂協定。使用者已同意四來源專用群組切分。正式訓練由使用者啟動。

## 狀態

- 已完成：S0 來源×split×八類盤點、CP-005 專用分割、统一 metrics、R0–R6／三組留一來源設定、八類訓練器、不可覆寫 run 目錄、恢復訓練、P1 溫度與集成／描述性閾值曲線、TTA、三 seed 彙總與中文曲線、G-R1 判定器。
- P0 已完成：四來源各 600 張、共 2,400 張；來源 BA 85.42%，骨幹未更新。
- G-R0 已完成全量 86,534 張量化與固定十張助理目視。回退率 HAM 3.14%、BCN 18.52%、PAD 17.59%、ISIC 13.00%；量化通過，但 S04／S06／S09 錯框暗角／背景／陰影，因此目視未通過、D2 保持鎖定，沒有人工批准。圖見 `reports/R0_固定十張裁切檢查.png`。
- 未完成實驗：所有八類疾病模型訓練、G-R1、P1／P3／P4 的實證結果。
- P5：等待四來源基準與逐項實驗方案，不自動開啟來源對抗、CORAL／MMD 或 NoiseFilter。現有 NoiseFilter G0 未通過的結果仍保留。
- 不變：封存測試集不使用，現行 UI 的模型不替換，第三階段鎖定不解除。

## 協定修正及理由

1. 原計畫的 `validation` 只有 HAM／BCN／PAD，`validation_ext` 只有 ISIC，無法計算四來源選模／評估。新增 `data/cp005_manifest.csv`，原 manifest 不改。以來源內 patient、lesion、既有群組的連通群組保持分割互斥；已有 holdout 的群組保留角色，其餘缺少角色的來源由 train 取固定分層群組折（7 折之一，約 14.3%）。
2. 原本 PAD 的同一病人可能有不同病灶；群組合併後一部分 train 影像移入既有 val_select，故不能宣稱所有歷史切分數量不變。這些影像可能被歷史模型見過，CP-005 val_assess 只對 CP-005 的訓練保留，不宣稱是全專案從未使用的外部測試。
3. 平均來源 BA 是等權平均，不會被 ISIC 的 74% 圖片占比直接主導；原計畫的理由不成立。仍依研究目標保留最差來源 BA 選模。
4. P1 需要八類 checkpoint，必須在 R0 之後。先做 S0／分割／P0 → R0 → P1；裁切審查通過後做 R1／R2。G-R1 需要 R0、R1、R2 各三 seed，不能先用單 seed「通過正式閘門」再補種子。
5. 溫度只在 val_select 擬合一次，val_assess 回報；在 val_assess 最小化 NLL 仍屬擬合，不能稱為完全獨立評估。方法納入決策使用 val_select，所有 val_assess 查閱次數需如實記錄。
6. 舊七類治理結果與新八類／新切分不能直接當成嚴格對照。P3 先建立八類 R0 三 seed 基準；57.9% MEL recall 僅為歷史參考，不能把不同來源組成差異歸因於模型。
7. 原 NoiseFilter G0 是三來源 train 探針，已執行且未通過；P0 是四來源新 val_select，不是同一份量測，必須重新記錄。來源可辨識度高是來源線索的證據，不足以證明泛化必然受限。
8. 原有 `ReferenceMask` 提供孔徑／高亮度權重，沒有完整的標尺／墨水偵測。本輪 D2 重用 `valid()`，另加高飽和藍綠色標記的明確啟發式；不重用排除病灶的 `skin_prior()` 去找病灶。此方法並不能辨識所有標尺。
9. D0 固定中心短邊 0.7，不套 k；D2 才使用 k。裁切越界以邊緣延伸補齊正方形。有效病灶解析度 S/k 只是理想幾何估計，無法補回原图缺失的細節。
10. 正式比較提升須大於兩組 sample standard deviation 中較大者；此為專案啟發式規則，不是顯著性檢定。不得由單 seed 下結論。

## 本輪來源與分割

| 來源 | train | val_select | val_assess |
|---|---:|---:|---:|
| HAM10000 | 6,013 | 1,504 | 994 |
| BCN20000 | 8,759 | 1,712 | 1,462 |
| PAD-UFES-20 | 1,258 | 613 | 221 |
| ISIC_Archive_Expanded | 48,750 | 8,273 | 6,975 |
| 合計 | 64,780 | 12,102 | 9,652 |

來源總數仍為 86,534。ISIC 支援八類，HAM／BCN 支援七類，PAD 支援五類。BA 只平均該次分割實際有樣本的支援類別；缺類別 recall 記為 null，不以零拖低 BA。

## 現在可以執行的訓練

在專案根目錄：

```powershell
# R0 pilot：八類、ImageNet ConvNeXt-Tiny、整張縮放 224
powershell -NoProfile -ExecutionPolicy Bypass -File ".\模型改進\run_cp005.ps1" -Run R0
```

設定：最多 12 epoch、early stopping patience 4、batch size 16、梯度累積 2、有效 batch 32、四來源等權抽樣、來源內平方根類別平衡、ImageNet mean/std、MixUp 0.2、label smoothing 0.1、AdamW。替換式抽樣不保證每個 epoch 每張影像都被使用。每輪實際抽樣數補為 32 的倍數，避免最後一次更新有效 batch 變小。

```powershell
# 確認 pilot 後，一次依序跑三 seed；會建立新的 run，不覆寫 pilot
powershell -NoProfile -ExecutionPolicy Bypass -File ".\模型改進\run_cp005.ps1" -Run R0 -ThreeSeeds
# 精確指定中斷目錄恢復；已完成結果不可恢復或覆寫
& "C:\anaconda3\python.exe" -X utf8 -u ".\模型改進\scripts\train.py" --run R0 --seed 17 --resume ".\模型改進\results\實際run目錄"
```

`run_id` 為 run／設定雜湊／seed。設定雜湊含 git commit、manifest 與使用程式內容指紋；因此未提交改動也不能靜默混用。重跑建立 `_rerunN`。`result.json` 是單 seed pilot 紀錄；只有明確選定三 seed 的彙總檔標示 `pilot:false`。

版本查找不依賴終端 PATH 必須包含 Git：先尋找系統或 Codex 隨附的 Git，再以唯讀方式從 `.git/HEAD`、refs 或 packed-refs 取得真實 commit。若不存在有效 commit 則停止，不產生假版本號。可用 `scripts/train.py --run R0 --seed 17 --check-only` 檢查啟動設定，不建立 run 或訓練。

## 裁切與留一來源

```powershell
# 全量病灶框稽核，會讀取 86,534 張影像；不訓練模型
& "C:\anaconda3\python.exe" -X utf8 -u ".\模型改進\scripts\audit_crops.py" --review-list ".\模型基底篩選_熱力圖10張測試\data\selected_samples.csv"
# R1 中心裁切可獨立跑；R2 需要 G-R0 量化通過和人工目視確認
powershell -NoProfile -ExecutionPolicy Bypass -File ".\模型改進\run_cp005.ps1" -Run R1
# 留一來源 pilot：其 train 和 val_select 都排除該來源
powershell -NoProfile -ExecutionPolicy Bypass -File ".\模型改進\run_cp005.ps1" -Run L-PAD
```

G-R0 回退率任一來源 >20% 時停止 D2；目視不能自動批准。框僅為估計，不是分割真值。R3–R6 入口要求 `reports/G_R1.json` 通過。L-PAD／L-BCN／L-HAM 目前以 R0 整圖設定為對照，結果不得和不同裁切模型混作單變因比較。

2026-10-06 實際判定：量化通過但助理目視未通過。D2 目前會誤選背景／陰影，並在越界補邊時產生明顯延伸紋理，故不得直接解鎖 R2。固定十張沿用原快篩，包含 HAM／BCN／PAD，沒有 ISIC；不可將此目視檢查稱為四來源定位驗證。下一步可先訓練 R0，裁切方法的修訂須另作版本與重跑稽核。

## 評估與彙總

訓練完成後，每個 run 都保存兩份分開的 logits、targets、record_ids，還有逐來源 BA、Accuracy、Macro-F1、ECE、逐類 recall、8×8 混淆矩陣、惡性敏感度／特異度。val_assess 只在最佳 checkpoint 固定後評估一次。

```powershell
# 三個目錄必須同設定、種子為 17／42／2026；請替換實際目錄
& "C:\anaconda3\python.exe" -X utf8 ".\模型改進\scripts\summarize.py" --run-dirs "seed17目錄" "seed42目錄" "seed2026目錄"
# 同一個指令可只給一個目錄作 P1 pilot，三個目錄才形成三 seed 集成
& "C:\anaconda3\python.exe" -X utf8 ".\模型改進\scripts\assess.py" --run-dirs "seed17目錄" "seed42目錄" "seed2026目錄"
& "C:\anaconda3\python.exe" -X utf8 ".\模型改進\scripts\tta.py" --run-dir "實際run目錄"
```

P1 保存全域／逐來源溫度與描述性敏感度–特異度曲線，不宣布臨床建議閾值。TTA 的所有方向使用相同裁切。TTA 和溫度校準分開評估，避免一次改兩個變因。

## 證據

- `reports/S0_source_class_matrix.csv`、`S0_summary.json`：原始治理 v2 盤點。
- `reports/cp005_split.json`：新切分數量、來源支援與指紋。
- `reports/P0_source_probe.json`：四來源探針（完成後產生）。
- `results/<run_id>/config_snapshot.json`、`progress.json`、`result.json`：執行設定、過程、固定結果。
- `tests/`：缺類別 BA、ECE 邊界、群組互斥、結果防覆寫、裁切、八類前向／反向測試。
