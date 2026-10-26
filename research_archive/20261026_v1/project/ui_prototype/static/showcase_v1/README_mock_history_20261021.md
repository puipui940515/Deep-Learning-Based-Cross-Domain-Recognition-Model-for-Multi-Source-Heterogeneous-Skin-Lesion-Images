# SkinDetect 網站第一版前端｜showcase_v1

2026-10-21。範圍：本機前端展示、上傳預覽、固定 mock 結果。無正式推論、訓練或部署。

## 盤點與沿用

- 已讀專案根目錄 AGENTS.md、docs/PROJECT_STATE.md、docs/V2_EXPERIMENT_HISTORY.md。docs/WORK_ALLOCATION.md 不存在。
- 原網站是 `ui_prototype/static/index.html` + 原生 JS/CSS，後端是 Python 標準庫 HTTP server。
- 已讀 `ui_prototype/README.md`、`server.py`、`model_runtime.py`、舊 `app.js`、根目錄 `start_ui.ps1`，並檢視模型登錄檔的預設模型與架構。
- 沿用既有七分類 code/中文標籤及回應的 `disease`、`image`、`heatmap` 欄位結構。本版為獨立展示入口，保留舊 A/B/C 原型、API、訓練控制與資產庫。
- 既有 `model_runtime.py` 的基底模型分支只有 MLP、ResNet18、ConvNeXt-Tiny，未支援 ConvNeXt V2。不能把既有 `mixed_convnext` 當成本版 V2 模型。
- 本版主模型資訊依使用者指定顯示 ConvNeXt V2-Tiny（ImageNet 初始化），清楚標示尚未串接。未讀影像資料集、Manifest、checkpoint payload 或封存 Test。

## 啟動（不需安裝套件）

在 `D:\SkinDetect_base`：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_frontend.ps1
```

預設使用 `python`，可指定可用 Python：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_frontend.ps1 -Python 'C:\anaconda3\python.exe' -Port 8766
```

或直接用標準函式庫啟動：

```powershell
python -m http.server 8766 --bind 127.0.0.1 --directory 'ui_prototype\static\showcase_v1'
```

開啟 http://127.0.0.1:8766/ 。只服務 showcase_v1 的靜態目錄，不啟動舊後端、PyTorch、CUDA 或訓練管理器。關閉該視窗／Ctrl+C 即停止。若已有舊後端，可直接訪問 `/showcase_v1/index.html`；不需為本版啟動舊後端。

## 檔案與元件

| 檔案 | 用途 |
|---|---|
| index.html | Hero 概念板、研究卡、上傳/結果雙欄、模型卡、四步流程、免責聲明 |
| styles.css | 米白/鼠尾草綠/淡杏色設計，桌面/平板/手機響應式、焦點與減少動態偏好 |
| app.js | 選檔/拖放、解碼與預覽、錯誤/等待/完成狀態、清除、分類/視覺解釋頁籤 |
| mock-predictor.js | 獨立固定 mock fixture，保留後續 adapter 可沿用的既有回應欄位 |
| assets/mark.svg | 原生向量識別圖示 |
| assets/study.svg | 自製抽象研究示意圖，非臨床影像，不取用研究/測試資料 |

此版本用原生 HTML/CSS/JavaScript，無外部字型、CDN、建置器或 npm 相依套件；可直接擴充現有網站，不另建框架。

## 輸入／輸出與界線

- 一次一張 JPEG/PNG/WebP，最多 20 MiB、6,400 萬像素；拒絕空檔、損毀檔、不支援格式與多檔。格式限制與既有服務一致。
- 上傳以 object URL 暫存在瀏覽器，不使用 localStorage、不讀取其他檔案、不發送 API。移除/換圖會釋放 object URL。
- 任何有效影像都得到同一份 fixture：NV 62.4%、BKL 13.2%、BCC 9.1%、MEL 6.0%、AKIEC 4.8%、DF 2.7%、VASC 1.8%，總和 100%。不是影像分析或正式結果。
- `model_id: demo`、`is_mock: true`；未宣稱這是 V2 預測。UI 等待時間不表示推論效能。
- 切換影像清除前份結果；清除可取消待顯示的 mock 結果。所有輸入檔名以 textContent 呈現。
- Grad-CAM 只做預留面板，不產生假熱力圖；沒有假病灶遮罩、定位或診斷解釋。
- CSP 的 `connect-src 'none'` 刻意禁止此版本連線。未來 API 串接時須審核修改為指定同源/端點，不能只移除限制。

## 後續最推薦的三項

1. **確認 V2 推論契約**：模型 ID、正式採用 checkpoint、前處理、七類順序、回應/錯誤結構與 CPU/GPU 使用方式；先不載入權重，避免干擾 B。
2. **串接真實推論與失敗處理**：契約核定、資源允許並取得推論授權後，新增 adapter；保留 mock 標示與實測追溯、timeout、取消與拒判/不支援情境。
3. **串接真實視覺解釋**：確認 V2 可用的 Grad-CAM 層與輸出，接上預留面板；解釋限制需保留，再做手機/鍵盤端到端驗收。

本版無登入、個案儲存、機率校準、真實 Grad-CAM、公開部署或臨床驗證；均不在本輪範圍。

## 驗證

實際完成的瀏覽器與靜態檢查記錄見同目錄 `QA.md`。原始研究結果保持原樣；前端工作不需要在研究實驗索引新增實驗結果。


## 自己修改網站：從這裡開始（2026-10-21 補充）

**正式修改位置是 `ui_prototype\static\showcase_v1`。**
`D:\SkinDetect\frontend_showcase_work` 是製作暫存，修改它不會更新現在展示的網站；上層 `ui_prototype/static/app.js` 是舊 A/B/C 原型，也不是本版入口。

建議用程式編輯器開啟 showcase_v1 資料夾，先從 index.html 和 styles.css 練習。
檔案已補上繁體中文功能註解，CSS 也從壓縮單行展開為多行。註解只供讀程式，不會顯示在網站畫面。

| 想改什麼 | 檔案／搜尋關鍵字 | 修改方式 |
|---|---|---|
| 瀏覽器頁籤名稱 | index.html：`<title>` | 改標籤之間的文字 |
| 首頁大標題／介紹 | index.html：`hero-title`、`hero-intro` | 直接改內文；`<br>` 表示換行 |
| 三張專題介紹卡 | index.html：`about`、`info-card` | 每個 article 是一張卡片 |
| 模型卡／流程／免責文字 | index.html：`model`、`workflow`、`disclaimer` | 改對應段落，不會切換真正模型 |
| 全站主色／背景 | styles.css：`:root` | `--green` 是主綠色，`--paper` 是背景，`--ink` 是主文字；部分區塊另有獨立色碼 |
| 字級與空間 | styles.css：`h1`、`.hero`、`.info-card` | font-size 字級、padding 內距、margin 外距、gap 間距 |
| 上傳／結果欄寬 | styles.css：`.workspace-card` | 調整 grid-template-columns，例如兩個 fr 數字控制寬度比例 |
| 手機／平板版 | styles.css：`@media` | ≤800px 平板、≤620px 手機、≤360px 窄手機；同時檢查桌面與手機覆寫 |
| 按鈕狀態／上傳錯誤文字 | app.js：`setBusy`、`chooseFile` | 改顯示文字；事件與 id 有對應關係 |
| 結果說明文字 | app.js：`explanation-text` | 在 renderResult 內修改 textContent |
| 七類展示分數 | mock-predictor.js：`classes` | probability 介於 0～1，七類合計 1；仍須保留 mock 標示 |
| 品牌圖示／示意圖 | assets/mark.svg、assets/study.svg | 原生 SVG 圖形；study 是抽象示意圖，非臨床資料 |
| 啟動網址的 port | 專案根目錄 start_frontend.ps1：`Port` | 可用 -Port 傳入，不必直接改預設值 |

### 修改後怎麼看到效果

1. 若預覽服務仍開著，儲存檔案後重新整理 `http://127.0.0.1:8766/index.html`；這裡沒有自動熱更新。
2. 若顏色或文字看起來沒變，可使用瀏覽器的強制重新整理／清除快取重新載入。
3. 若顯示無法連線，代表要先確認本機服務是否開著；在專案根目錄使用上方啟動指令。關閉服務終端機就會停止預覽。
4. 改 HTML/CSS/JS 不需要重新訓練，也不必重新安裝套件；重新整理會清掉當次選圖與 mock 結果。

### 三個適合先練習的小修改

- 改首頁 `hero-title` 的一句話，觀察 `<br>` 對換行的影響。
- 改 `:root` 的 `--green`，觀察主按鈕與連結的配色。
- 改 `.info-card` 的 padding，觀察卡片文字與邊框之間的距離。

id、class、檔名、script 載入順序和 aria-controls 彼此有連動，改名時須同步調整引用。若只是改文字與配色，保留這些名稱即可。

### 註解版驗證範圍

本次只補註解與展開排版，不變更版面設定值、互動邏輯或 mock 分數。
已比對 HTML 標籤/屬性/有效文字、CSS 非註解內容及 JS/PowerShell 非註解程式碼與修改前一致，並以 Node --check 檢查兩份 JS。
未重新執行先前完整瀏覽器測試；原始互動實測與限制仍見 QA.md。
