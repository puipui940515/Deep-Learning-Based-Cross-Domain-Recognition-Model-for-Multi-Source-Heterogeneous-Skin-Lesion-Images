# SkinDetect：多來源皮膚病灶影像跨域辨識研究

Deep Learning Based Cross-Domain Recognition Model for Multi-Source Heterogeneous Skin Lesion Images

本專案研究多來源皮膚病灶影像的分類與跨來源泛化，包含階段性模型實驗、部位預訓練對照、資料治理、NoiseFilter 實驗、本機推論 UI，以及中文操作文件。

本儲存庫為 2026-10-17 的程式與文件發布快照。本機原始 Git 歷史保留，沒有改寫。資料集、模型權重、逐圖 manifest、個別病患／病灶紀錄、原始推論輸出、備份、套件目錄及簡報原檔不隨程式公開。

發布版的實驗紀錄庫只保留實際附上的快照連結；Notebook 保留程式與說明，清除執行輸出。本機原始檔案保持不變。

## 專案入口

- [專案架構](PROJECT_STRUCTURE.md)
- [開發時間軸](README_專案開發時間軸.md)
- [實驗譜系](SkinDetect_實驗譜系.html)
- [中文 UI 使用手冊](UI使用手冊.md)
- [圖片版使用手冊（12 張 PNG）](UI使用手冊_圖片版/index.html)
- [資料集來源與下載說明](docs/資料集下載說明.md)
- [模型改進計畫](README_模型改進計畫.md)

## 主要目錄

| 目錄 | 用途 |
|---|---|
| `ui_prototype/` | 模型選擇、單張推論、Grad-CAM、既有訓練控制台 |
| `第一階段/`、`第二階段/`、`第三階段/` | 漸進式模型實驗 |
| `部位預測階段/` | 部位預訓練與相關資料處理程式 |
| `多來源混合訓練_第一版/`、`多來源混合訓練_第二版/` | 混合來源訓練實驗 |
| `資料治理與泛化修復/` | 類別統一、資料洩漏檢查與泛化修復 |
| `模型改進/` | CP-005、輸入前處理、獨立種子排程與安全存檔 |
| `noisefilter_v2強化實驗/` | NoiseFilter v2 校準、訓練與診斷 |
| `模型資產庫/` | 本機模型登錄與同步程式；權重另行取得 |
| `實驗紀錄庫/`、`開發歷程/` | 實驗紀錄整理與歷程文件 |
| `UI使用手冊_圖片版/` | 圖文操作指南與來源署名 |

## 環境與 UI 啟動

開發環境為 Windows、Python 3.12、PyTorch；套件版本見 `requirements.txt`。CUDA 套件需配合實際 GPU 與驅動環境。

```powershell
python -m pip install -r requirements.txt
powershell -NoProfile -ExecutionPolicy Bypass -File ".\start_ui.ps1" -Python "你的Python完整路徑"
```

預設網址為 `http://127.0.0.1:8765/prototype/skin-detect?variant=A`。沒有本機權重時，UI 仍可使用明確標示的展示模式；展示數值不是模型預測。

真實推論需要補回 `模型資產庫/model_registry.json` 對應的權重，以及各架構所需的程式。新訓練權重不會自動成為 UI 預設模型。

## 訓練與資料

資料集需依官方來源及使用條款自行取得，並依各階段 README 建立本機資料清單。此程式發布不授予任何資料集或第三方素材的額外使用權。

目前 UI 的訓練控制台使用既有三來源七分類流程；CP-005 四來源八分類與 NoiseFilter v2 多日排程有獨立設定與入口。不能把 UI 訓練按鈕視為已接入所有新資料與所有實驗。

歷史實驗包含不同資料切分、類別與模型規模，報告中的數字應搭配對應設定閱讀，不宜直接當作同條件排名。`模型改進/` 的正式排程仍保留資料檢查、獨立種子、NoiseFilter v2 對照與非有限值保護。

部分歷史腳本保留原電腦的路徑與本機資料／權重依賴；克隆後不代表可直接重現所有實驗。請先閱讀對應階段文件並準備資產。

## 測試

```powershell
python -m pytest ui_prototype/tests -q
python -m pytest 模型改進/tests noisefilter_v2強化實驗/tests --import-mode=importlib -q
```

部分資料／GPU／完整專案資產相關測試需要本機檔案；純程式快照不包含這些資產。

## 使用與署名

此專案供研究與課程專題使用，輸出不構成醫療診斷。機率分布與 Grad-CAM 分別反映模型分數及相關空間訊息，不是確診機率或病灶分割證據。

圖片手冊的範例素材署名見 [來源說明](UI使用手冊_圖片版/來源說明.md)。第三方程式與素材應遵循各自的原始條款；本次發布沒有自行新增整個專案的開源授權。
