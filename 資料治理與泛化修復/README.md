# 資料治理與泛化修復

<!-- skindetect:status v1 -->
| 欄位 | 值 |
|---|---|
| 階段 | 泛化修復階段 |
| 首次執行 | 2026-09-06 |
| 狀態 | 進行中 |
| seeds | 17／42 |
| 主要指標 | 治理 v1 三來源平均 72.06%（seed 17）／68.55%（seed 42）；n=2 標準差 2.48pp |
| 正式輸入 | `資料治理與泛化修復/data/unified_manifest_v1.csv` |
| 結果證據 | `資料治理與泛化修復/results/formal_v1/` |
| 歸檔 | `檔案室` 任務 10、11、14、15 |
| 時間軸 | [`開發歷程/時間軸.md`](../開發歷程/時間軸.md) |
| 格式約定 | [`開發歷程/格式約定.md`](../開發歷程/格式約定.md) |
<!-- /skindetect:status -->

本資料夾依指定順序處理：

1. **來源差異**：驗證來源、授權、標籤映射、影像存在性與拍攝模態。
2. **資料重複洩漏**：以患者／病灶群組、SHA-256、pHash 與 dHash 檢查跨切分重複；不修改原始資料，只將有問題的訓練列放入 `data/quarantine.csv`。
3. **過擬合**：先量化既有訓練—驗證落差；新訓練加入 label smoothing、MixUp、weight decay、梯度裁切、來源／類別平衡抽樣及提早停止。
4. **設備與構圖差異**：統計各來源解析度、長寬比、亮度、飽和度與邊緣量；訓練時加入尺度、長寬比、顏色、模糊、自動對比與隨機擦除擾動。

## 安全原則

- 原始影像和原始 manifest 不會被刪除或覆寫。
- `data/clean_manifest.csv` 會再依 `schema/data_contract_v1.json` 轉換為
  `data/unified_manifest_v1.csv`；正式訓練只能讀取後者。
- 疾病和部位都同時保留原始值與統一值，不用統一值覆蓋來源標籤。
- `AKIEC／AK／ACK` 及 `BKL／SEK` 是家族級映射，不宣稱為完全同義。
- 缺少的患者屬性維持空白或 `unknown`，不得由影像推測。
- 若訓練資料與驗證資料重複，優先保留驗證列並隔離訓練列；驗證集內的完全重複圖每組只保留一張。
- 完全相同影像若對應不同疾病標籤，整組隔離，不用猜測其中哪個標籤正確。
- 感知雜湊只有在同標籤且 pHash、dHash 都極接近時才自動隔離；較寬鬆的候選只列入人工檢查。
- 不使用 test split 選模。

## 執行順序

先執行資料管線：

```powershell
python ".\資料治理與泛化修復\scripts\run_pipeline.py"
```

管線通過後再進行煙霧測試：

```powershell
python ".\資料治理與泛化修復\scripts\train_regularized.py" --seed 17 --epochs 1 --max-train-samples 280 --max-val-samples-per-source 70 --output-root ".\資料治理與泛化修復\smoke_results"
```

正式訓練指令：

```powershell
python ".\資料治理與泛化修復\scripts\train_regularized.py" --seed 17
```

中斷後可續跑：

```powershell
python ".\資料治理與泛化修復\scripts\train_regularized.py" --seed 17 --resume
```

## 主要產物

- `reports/00_data_definition_v1.json`
- `reports/01_source_audit.json`
- `reports/02_leakage_audit.json`
- `reports/03_overfit_baseline.json`
- `reports/04_equipment_composition_audit.json`
- `reports/pipeline_gate.json`
- `data/clean_manifest.csv`
- `data/unified_manifest_v1.csv`（正式訓練輸入）
- `data/quarantine.csv`
- `data/image_fingerprints.csv`（下次重跑會快很多）
- `schema/data_contract_v1.json`
- `schema/disease_mapping_v1.csv`
- `schema/anatomical_site_mapping_v1.csv`

正式訓練尚未由資料管線自動開始，避免在未確認稽核結果前耗用 GPU。
