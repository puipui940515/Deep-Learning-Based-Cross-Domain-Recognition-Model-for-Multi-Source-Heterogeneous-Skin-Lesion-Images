# 新增 ISIC 資料治理 v2（2026-09-11）

這一版完成新加入 `ISIC_Archive_擴充_2026-09-09` 的來源登記、標籤統一、部位統一、影像完整性檢查、跨來源去重、群組切分與正式 manifest 建立。處理過程沒有刪除或移動原始影像，也沒有啟動模型訓練。

## 最終可用資料

| 項目 | 數量 |
|---|---:|
| 新 ISIC 原始影像／metadata | 85,682 |
| 新 ISIC 通過治理後 | 63,998 |
| 保留的治理 v1 歷史資料 | 22,536 |
| v2 正式 manifest | **86,534** |
| 隔離紀錄 | **21,684** |

正式資料依切分為 train 75,945、歷史 validation 3,614、新 `validation_ext` 6,975。舊 validation 保留不動，方便與既有實驗比較；新增驗證集依 patient／lesion 群組切分，兩者不得混成一個數字回報。

## 統一分類

沿用原七類的 ID，不改變歷史模型的類別順序，另新增 SCC：

| ID | 代碼 | 中文 |
|---:|---|---|
| 0 | AKIEC | 光化性角化症／表皮內癌家族 |
| 1 | BCC | 基底細胞癌 |
| 2 | BKL | 良性角化病灶家族 |
| 3 | DF | 皮膚纖維瘤 |
| 4 | NV | 黑色素細胞痣 |
| 5 | VASC | 血管性病灶 |
| 6 | MEL | 黑色素瘤 |
| 7 | SCC | 鱗狀細胞癌 |

原始診斷字串仍保留在 manifest；正式標籤由 `schema/disease_mapping_v2.csv` 決定。SCC in situ 依既有任務定義歸入 AKIEC，侵襲性或未特指 SCC 歸入新增 SCC 類。

部位同時保留原始字串與統一代碼，映射表位於 `schema/anatomical_site_mapping_v2.csv`。缺失的病患、病灶、部位、膚色或族群資料保持 `unknown`／空白，不從圖片外觀推測。

## 隔離原因

| 原因 | 數量 |
|---|---:|
| 與 HAM10000 相同 `isic_id` | 8,774 |
| 與既有來源嚴格近重複 | 12,616 |
| train 與 `validation_ext` 嚴格近重複 | 220 |
| 超大 TIFF 無法在安全限制內解碼／產生指紋 | 74 |
| 合計 | **21,684** |

74 張 TIFF 並未被判定為惡意或永久損壞，只是像素數超過 Pillow 的安全上限；為避免記憶體風險，先隔離且保留原檔。較寬鬆的近重複候選只記錄供人工檢查，沒有自動刪除。

## 驗證結果

最終 manifest 已確認：

- 86,534 個影像路徑全部存在。
- 每列都有成功的 SHA-256、pHash 與 dHash 指紋。
- `record_id` 唯一，SHA-256 內容唯一。
- 同來源的 patient／lesion 群組沒有跨 split。
- 標籤 ID、代碼與 v2 映射一致。
- manifest 只含 `training_eligible=true` 的列。

資料閘門結果為通過。來源池本身有 74 張安全解碼失敗，但它們已全部隔離，所以「來源原始完整性」為否、「正式訓練 manifest 完整性」為是，兩者不可混淆。

## 檔案位置

- 正式輸入：`data/unified_manifest_v2.csv`
- 隔離清單：`data/quarantine_v2.csv`
- 影像指紋：`data/image_fingerprints_v2.csv`
- 資料契約：`schema/data_contract_v2.json`
- 疾病映射：`schema/disease_mapping_v2.csv`
- 部位映射：`schema/anatomical_site_mapping_v2.csv`
- 來源登記：`../Dataset/SOURCE_REGISTRY.json`
- 本次版本登記：`../Dataset/DATA_RELEASE_REGISTRY_v2.json`
- 原始盤點：`reports/05_isic_v2_inventory.json`
- 影像完整性：`reports/06_image_integrity_v2.json`
- 去重與切分：`reports/07_isic_v2_dedup_and_split.json`
- 最終驗證：`reports/08_manifest_validation_v2.json`
- 資料閘門：`reports/data_gate_v2.json`
- 後續接線設定：`config_v2.json`

## 後續訓練限制

v2 是八分類，而現有部分訓練腳本仍是七分類，不能直接把 v2 manifest 塞入舊模型。正式訓練前必須把輸出頭調整為 8 類、接受 JPG／PNG／TIFF，並明確讀取 `train`；`validation` 與 `validation_ext` 應分開評估。這個資料處理任務沒有替使用者啟動訓練。

本版含 CC-BY-NC，因此只按非商業學術用途管理；公開論文、模型或程式時仍須保留逐張授權與 attribution，且不建議重新散布原始影像。
