# SkinDetect 網站文字編號清單

範圍：目前 root start_frontend.ps1 的 showcase_v1 展示頁；舊 A/B/C 歷史原型不在本輪修改範圍。

開發編號網址：`http://127.0.0.1:8766/index.html?textids=1`。一般展示網址沒有此參數，不產生工具或編號。

開發頁右下「關閉編號／開啟編號」切換；開啟時點文字或編號查看內容與來源，點選不執行原按鈕。關閉後恢復原有操作。Escape可關閉編號。可輸入ID定位；隱藏／尚無結果的文字先切換到該情境。

ID固定寫在HTML的data-text-id或app.js類別映射中；不是執行時按DOM順序、文字雜湊、行號或機率名次產生。修改文字／刷新／移動元素保留ID。新增只使用未使用ID；刪除記為停用且不重用。Markdown行號僅為此版本查找提示，data-text-id才是穩定定位。

動態文字ID定位的是輸出欄位；例如提示可有多種狀態，修改時請同時說明情境。檔名、機率、預測類別是資料，不可為修改文案而偽造數值。醫療免責與七類/API映射保留，變更須另核對。

所有程式路徑根目錄：`ui_prototype/static/showcase_v1/`；core.py位於`ui_prototype/v2_inference/`。

|編號|頁面／區塊|現有文字／欄位|程式定位|
|---|---|---|---|
|F-001|showcase_v1/index.html / 頁首／首頁|SkinDetect 皮膚影像辨識研究展示：探索影像、七分類分布與模型研究流程。第一版使用明確標示的模擬資料。|`index.html:7`；`[data-text-id="F-001"]`；屬性 content|
|F-002|showcase_v1/index.html / 頁首／首頁|SkinDetect｜皮膚影像研究展示|`index.html:11`；`[data-text-id="F-002"]`|
|F-003|showcase_v1/index.html / 頁首／首頁|跳到主要內容|`index.html:23`；`[data-text-id="F-003"]`|
|F-004|showcase_v1/index.html / 頁首／首頁|關於專題|`index.html:28`；`[data-text-id="F-004"]`|
|F-005|showcase_v1/index.html / 頁首／首頁|影像展示|`index.html:28`；`[data-text-id="F-005"]`|
|F-006|showcase_v1/index.html / 頁首／首頁|模型與流程|`index.html:28`；`[data-text-id="F-006"]`|
|F-007|showcase_v1/index.html / 頁首／首頁|RESEARCH PROJECT|`index.html:30`；`[data-text-id="F-007"]`|
|F-008|showcase_v1/index.html / 頁首／首頁|SKIN IMAGE RESEARCH / 01|`index.html:36`；`[data-text-id="F-008"]`|
|F-009|showcase_v1/index.html / 頁首／首頁|從一張影像，看見模型如何判讀。|`index.html:37`；`[data-text-id="F-009"]`|
|F-010|showcase_v1/index.html / 頁首／首頁|讓皮膚影像辨識的過程更清楚。從分類分布到研究方法，一起理解模型的判斷與限制。|`index.html:38`；`[data-text-id="F-010"]`|
|F-011|showcase_v1/index.html / 頁首／首頁|探索影像展示 ↗|`index.html:40`；`[data-text-id="F-011"]`|
|F-012|showcase_v1/index.html / 頁首／首頁|看看研究流程 →|`index.html:40`；`[data-text-id="F-012"]`|
|F-013|showcase_v1/index.html / 頁首／首頁|學生專題・研究展示用途・不提供醫療診斷|`index.html:42`；`[data-text-id="F-013"]`|
|F-014|showcase_v1/index.html / 頁首／首頁|研究觀察筆記|`index.html:47`；`[data-text-id="F-014"]`|
|F-015|showcase_v1/index.html / 頁首／首頁|概念圖解|`index.html:47`；`[data-text-id="F-015"]`|
|F-016|showcase_v1/index.html / 頁首／首頁|01 / IMAGE|`index.html:51`；`[data-text-id="F-016"]`|
|F-017|showcase_v1/index.html / 頁首／首頁|抽象皮膚影像示意，非臨床影像|`index.html:51`；`[data-text-id="F-017"]`；屬性 alt|
|F-018|showcase_v1/index.html / 頁首／首頁|觀察影像特徵|`index.html:51`；`[data-text-id="F-018"]`|
|F-019|showcase_v1/index.html / 頁首／首頁|02 / PATTERNS|`index.html:55`；`[data-text-id="F-019"]`|
|F-020|showcase_v1/index.html / 頁首／首頁|學習特徵表示|`index.html:59`；`[data-text-id="F-020"]`|
|F-021|showcase_v1/index.html / 頁首／首頁|從特徵，到可讀的輸出|`index.html:64`；`[data-text-id="F-021"]`|
|F-022|showcase_v1/index.html / 頁首／首頁|辨識之外，也理解限制。|`index.html:64`；`[data-text-id="F-022"]`|
|F-023|showcase_v1/index.html / 頁首／首頁|ConvNeXt V2-Tiny 本專題目前主模型|`index.html:68`；`[data-text-id="F-023"]`|
|F-024|showcase_v1/index.html / 頁首／首頁|本專題目前主模型|`index.html:69`；`[data-text-id="F-024"]`|
|F-025|showcase_v1/index.html / about|THE RESEARCH|`index.html:76`；`[data-text-id="F-025"]`|
|F-026|showcase_v1/index.html / about|我們關注的，不只是一個答案。|`index.html:77`；`[data-text-id="F-026"]`|
|F-027|showcase_v1/index.html / about|01|`index.html:81`；`[data-text-id="F-027"]`|
|F-028|showcase_v1/index.html / about|辨識什麼？|`index.html:82`；`[data-text-id="F-028"]`|
|F-029|showcase_v1/index.html / about|以 HAM 七分類為研究範圍，觀察不同皮膚病灶影像的分類分布。|`index.html:83`；`[data-text-id="F-029"]`|
|F-030|showcase_v1/index.html / about|7 個研究類別|`index.html:84`；`[data-text-id="F-030"]`|
|F-031|showcase_v1/index.html / about|02|`index.html:87`；`[data-text-id="F-031"]`|
|F-032|showcase_v1/index.html / about|換個來源，還可靠嗎？|`index.html:88`；`[data-text-id="F-032"]`|
|F-033|showcase_v1/index.html / about|比較 HAM、BCN、PAD 不同來源的表現，研究資料差異對模型的影響。|`index.html:89`；`[data-text-id="F-033"]`|
|F-034|showcase_v1/index.html / about|跨資料來源泛化|`index.html:90`；`[data-text-id="F-034"]`|
|F-035|showcase_v1/index.html / about|03|`index.html:93`；`[data-text-id="F-035"]`|
|F-036|showcase_v1/index.html / about|怎麼讀懂判斷？|`index.html:94`；`[data-text-id="F-036"]`|
|F-037|showcase_v1/index.html / about|用機率條與簡短說明呈現輸出，並預留後續視覺解釋的位置。|`index.html:95`；`[data-text-id="F-037"]`|
|F-038|showcase_v1/index.html / about|讓結果更容易理解|`index.html:96`；`[data-text-id="F-038"]`|
|F-039|showcase_v1/index.html / workspace|INTERACTIVE DEMO|`index.html:104`；`[data-text-id="F-039"]`|
|F-040|showcase_v1/index.html / workspace|一張影像，一次探索。|`index.html:105`；`[data-text-id="F-040"]`|
|F-041|showcase_v1/index.html / workspace|上傳影像或載入示意圖，體驗完整的結果閱讀流程。|`index.html:106`；`[data-text-id="F-041"]`|
|F-042|showcase_v1/index.html / workspace|研究推論 · 檢查服務|`index.html:108；app.js 中 service-badge／對應函式`；`[data-text-id="F-042"]`|
|F-043|showcase_v1/index.html / workspace|01|`index.html:114`；`[data-text-id="F-043"]`|
|F-044|showcase_v1/index.html / workspace|準備一張影像|`index.html:115`；`[data-text-id="F-044"]`|
|F-045|showcase_v1/index.html / workspace|INPUT|`index.html:116`；`[data-text-id="F-045"]`|
|F-046|showcase_v1/index.html / workspace|選擇模型版本|`index.html:120`；`[data-text-id="F-046"]`|
|F-047|showcase_v1/index.html / workspace|原 V2／224 ImageNet · Seed 1 原 V2／224 · Seed 1／2／3 等權 Ensemble Mock · 固定示範資料|`index.html:121；app.js 中 model-select／對應函式`；`[data-text-id="F-047"]`|
|F-048|showcase_v1/index.html / workspace|原 V2／224 ImageNet · Seed 1|`index.html:122`；`[data-text-id="F-048"]`|
|F-049|showcase_v1/index.html / workspace|原 V2／224 · Seed 1／2／3 等權 Ensemble|`index.html:123`；`[data-text-id="F-049"]`|
|F-050|showcase_v1/index.html / workspace|Mock · 固定示範資料|`index.html:124`；`[data-text-id="F-050"]`|
|F-051|showcase_v1/index.html / workspace|正在確認本機服務；不會載入模型。|`index.html:126；app.js 中 mode-help／對應函式`；`[data-text-id="F-051"]`|
|F-052|showcase_v1/index.html / input-scope|請選擇清楚的人類皮膚病灶近照|`index.html:130`；`[data-text-id="F-052"]`|
|F-053|showcase_v1/index.html / input-scope|單張、單一病灶為主，避免模糊、遮擋或過暗。符合檔案格式，不代表已確認適合模型。|`index.html:131`；`[data-text-id="F-053"]`|
|F-054|showcase_v1/index.html / input-scope|本版只能檢查檔案是否可讀；無法可靠辨識正常皮膚、非皮膚或七類以外疾病，也不能據此排除疾病。|`index.html:132`；`[data-text-id="F-054"]`|
|F-055|showcase_v1/index.html / workspace|選擇皮膚影像|`index.html:135；app.js 中 file-input／對應函式`；`[data-text-id="F-055"]`；屬性 aria-label|
|F-056|showcase_v1/index.html / workspace|已選擇的影像預覽|`index.html:138；app.js 中 image-preview／對應函式`；`[data-text-id="F-056"]`；屬性 alt|
|F-057|showcase_v1/index.html / workspace|〔動態填入〕|`index.html:144；app.js 中 file-name／對應函式`；`[data-text-id="F-057"]`|
|F-058|showcase_v1/index.html / workspace|〔動態填入〕|`index.html:144；app.js 中 file-meta／對應函式`；`[data-text-id="F-058"]`|
|F-059|showcase_v1/index.html / workspace|×|`index.html:146；app.js 中 clear-button／對應函式`；`[data-text-id="F-059"]`|
|F-060|showcase_v1/index.html / workspace|真實推論時才傳至本機服務；不保存影像。|`index.html:148；app.js 中 privacy-text／對應函式`；`[data-text-id="F-060"]`|
|F-061|showcase_v1/index.html / workspace|〔動態填入〕|`index.html:150；app.js 中 upload-error／對應函式`；`[data-text-id="F-061"]`|
|F-062|showcase_v1/index.html / workspace|執行研究推論 →|`index.html:152；app.js 中 run-button／對應函式`；`[data-text-id="F-062"]`|
|F-063|showcase_v1/index.html / workspace|還沒有影像？|`index.html:154`；`[data-text-id="F-063"]`|
|F-064|showcase_v1/index.html / workspace|載入示意影像（Mock） ↗|`index.html:155；app.js 中 sample-button／對應函式`；`[data-text-id="F-064"]`|
|F-065|showcase_v1/index.html / workspace|等待選擇影像|`index.html:157；app.js 中 status／對應函式`；`[data-text-id="F-065"]`|
|F-066|showcase_v1/index.html / result-panel|02|`index.html:162`；`[data-text-id="F-066"]`|
|F-067|showcase_v1/index.html / result-panel|閱讀預測結果|`index.html:163`；`[data-text-id="F-067"]`|
|F-068|showcase_v1/index.html / result-panel|OUTPUT|`index.html:164`；`[data-text-id="F-068"]`|
|F-069|showcase_v1/index.html / result-panel|結果，會從這裡開始。|`index.html:171`；`[data-text-id="F-069"]`|
|F-070|showcase_v1/index.html / result-panel|選擇模型與影像後，執行研究推論。你將看到分類分布、簡短解釋與視覺化預留區。|`index.html:172`；`[data-text-id="F-070"]`|
|F-071|showcase_v1/index.html / result-panel|目前尚無結果|`index.html:173`；`[data-text-id="F-071"]`|
|F-072|showcase_v1/index.html / result-panel|七類中最高分 待推論|`index.html:179`；`[data-text-id="F-072"]`|
|F-073|showcase_v1/index.html / result-panel|待推論|`index.html:179；app.js 中 result-kind／對應函式`；`[data-text-id="F-073"]`|
|F-074|showcase_v1/index.html / result-panel|〔動態填入〕|`index.html:180；app.js 中 prediction-label／對應函式`；`[data-text-id="F-074"]`|
|F-075|showcase_v1/index.html / result-panel|〔動態填入〕|`index.html:181；app.js 中 prediction-code／對應函式`；`[data-text-id="F-075"]`|
|F-076|showcase_v1/index.html / result-panel|〔動態填入〕|`index.html:184；app.js 中 prediction-score／對應函式`；`[data-text-id="F-076"]`|
|F-077|showcase_v1/index.html / result-panel|未校準分數|`index.html:184；app.js 中 score-kind／對應函式`；`[data-text-id="F-077"]`|
|F-078|showcase_v1/index.html / result-panel|〔動態填入〕|`index.html:187；app.js 中 result-model-info／對應函式`；`[data-text-id="F-078"]`|
|F-079|showcase_v1/index.html / result-panel|分類分布|`index.html:190`；`[data-text-id="F-079"]`|
|F-080|showcase_v1/index.html / result-panel|視覺解釋 預留|`index.html:191`；`[data-text-id="F-080"]`|
|F-081|showcase_v1/index.html / result-panel|研究類別|`index.html:196`；`[data-text-id="F-081"]`|
|F-082|showcase_v1/index.html / result-panel|相對機率（未校準）|`index.html:196；app.js 中 distribution-kind／對應函式`；`[data-text-id="F-082"]`|
|F-083|showcase_v1/index.html / result-panel|七類分數總和為 100% · 不等於疾病確診機率|`index.html:200`；`[data-text-id="F-083"]`|
|F-084|showcase_v1/index.html / result-panel|讓模型關注的區域，也能被看見。|`index.html:206`；`[data-text-id="F-084"]`|
|F-085|showcase_v1/index.html / result-panel|這裡預留 Grad-CAM 疊圖與原圖比較。尚未串接，不以模擬熱力圖代替實際解釋。|`index.html:207`；`[data-text-id="F-085"]`|
|F-086|showcase_v1/index.html / result-panel|後續擴充 · GRAD-CAM|`index.html:208`；`[data-text-id="F-086"]`|
|F-087|showcase_v1/index.html / result-panel|如何閱讀這個結果？|`index.html:215`；`[data-text-id="F-087"]`|
|F-088|showcase_v1/index.html / result-panel|〔動態填入〕|`index.html:216；app.js 中 explanation-text／對應函式`；`[data-text-id="F-088"]`|
|F-089|showcase_v1/index.html / result-panel|研究用途；分數尚未校準，不代表醫療診斷機率。真實模型執行預設關閉，請依本機服務狀態啟用。|`index.html:220；app.js 中 result-notice／對應函式`；`[data-text-id="F-089"]`|
|F-090|showcase_v1/index.html / workspace|請啟用 JavaScript 以使用本機影像預覽及 mock 展示；專題介紹與流程仍可閱讀。|`index.html:225`；`[data-text-id="F-090"]`|
|F-091|showcase_v1/index.html / model|BEHIND THE MODEL|`index.html:232`；`[data-text-id="F-091"]`|
|F-092|showcase_v1/index.html / model|目前的主模型。|`index.html:233`；`[data-text-id="F-092"]`|
|F-093|showcase_v1/index.html / model|先了解模型，再理解它的輸出。|`index.html:235`；`[data-text-id="F-093"]`|
|F-094|showcase_v1/index.html / model|研究主模型|`index.html:240`；`[data-text-id="F-094"]`|
|F-095|showcase_v1/index.html / model|MODEL / 01|`index.html:240`；`[data-text-id="F-095"]`|
|F-096|showcase_v1/index.html / model|ConvNeXtV2-Tiny|`index.html:242`；`[data-text-id="F-096"]`|
|F-097|showcase_v1/index.html / model|ImageNet 預訓練初始化|`index.html:243`；`[data-text-id="F-097"]`|
|F-098|showcase_v1/index.html / model|研究任務|`index.html:246`；`[data-text-id="F-098"]`|
|F-099|showcase_v1/index.html / model|皮膚病灶七分類|`index.html:246`；`[data-text-id="F-099"]`|
|F-100|showcase_v1/index.html / model|網站連接狀態|`index.html:249`；`[data-text-id="F-100"]`|
|F-101|showcase_v1/index.html / model|待 GPU 驗證|`index.html:249；app.js 中 model-connection／對應函式`；`[data-text-id="F-101"]`|
|F-102|showcase_v1/index.html / model|已建立原 Seed1／三 Seed 等權推論介面；權重只由本機服務依核定模式載入。|`index.html:252`；`[data-text-id="F-102"]`|
|F-103|showcase_v1/index.html / model|七個類別，是研究範圍。|`index.html:258`；`[data-text-id="F-103"]`|
|F-104|showcase_v1/index.html / model|AKIEC、BCC、BKL、DF、NV、VASC、MEL。未納入的疾病與正常皮膚，也可能被分到既有類別。|`index.html:259`；`[data-text-id="F-104"]`|
|F-105|showcase_v1/index.html / model|預訓練，是學習的起點。|`index.html:265`；`[data-text-id="F-105"]`|
|F-106|showcase_v1/index.html / model|先從 ImageNet 學習通用影像特徵，再進行本專題的分類訓練；不代表已具備臨床診斷能力。|`index.html:266`；`[data-text-id="F-106"]`|
|F-107|showcase_v1/index.html / model|信心高，不等於判斷正確。|`index.html:272`；`[data-text-id="F-107"]`|
|F-108|showcase_v1/index.html / model|影像品質、資料來源與類別涵蓋範圍都會影響輸出。這個展示頁不提供臨床效能主張。|`index.html:273`；`[data-text-id="F-108"]`|
|F-109|showcase_v1/index.html / workflow|THE RESEARCH PROCESS|`index.html:283`；`[data-text-id="F-109"]`|
|F-110|showcase_v1/index.html / workflow|SkinDetect，實際怎麼訓練？|`index.html:284`；`[data-text-id="F-110"]`|
|F-111|showcase_v1/index.html / workflow|把資料、學習與評估分開，讓每一步都有清楚的用途。|`index.html:285`；`[data-text-id="F-111"]`|
|F-112|showcase_v1/index.html / workflow|01|`index.html:290`；`[data-text-id="F-112"]`|
|F-113|showcase_v1/index.html / workflow|整理與切分資料|`index.html:291`；`[data-text-id="F-113"]`|
|F-114|showcase_v1/index.html / workflow|統一類別、檢查重複影像，區分 Train、Validation 與 Test。|`index.html:292`；`[data-text-id="F-114"]`|
|F-115|showcase_v1/index.html / workflow|資料治理|`index.html:293`；`[data-text-id="F-115"]`|
|F-116|showcase_v1/index.html / workflow|02|`index.html:296`；`[data-text-id="F-116"]`|
|F-117|showcase_v1/index.html / workflow|用訓練集學習|`index.html:297`；`[data-text-id="F-117"]`|
|F-118|showcase_v1/index.html / workflow|模型從訓練影像更新參數，學習影像特徵與類別之間的關係。|`index.html:298`；`[data-text-id="F-118"]`|
|F-119|showcase_v1/index.html / workflow|模型訓練|`index.html:299`；`[data-text-id="F-119"]`|
|F-120|showcase_v1/index.html / workflow|03|`index.html:302`；`[data-text-id="F-120"]`|
|F-121|showcase_v1/index.html / workflow|用驗證集選模|`index.html:303`；`[data-text-id="F-121"]`|
|F-122|showcase_v1/index.html / workflow|依驗證表現選擇模型，觀察跨來源差異；Test 保留作最終評估。|`index.html:304`；`[data-text-id="F-122"]`|
|F-123|showcase_v1/index.html / workflow|Validation ≠ Test|`index.html:305`；`[data-text-id="F-123"]`|
|F-124|showcase_v1/index.html / workflow|04|`index.html:308`；`[data-text-id="F-124"]`|
|F-125|showcase_v1/index.html / workflow|呈現與理解輸出|`index.html:309`；`[data-text-id="F-125"]`|
|F-126|showcase_v1/index.html / workflow|顯示七類分布與限制，支援原 Seed1 及三 Seed 等權集成；GPU 一致性驗證另行記錄。|`index.html:310`；`[data-text-id="F-126"]`|
|F-127|showcase_v1/index.html / workflow|本版展示位置|`index.html:311`；`[data-text-id="F-127"]`|
|F-128|showcase_v1/index.html / 頁尾／其他|A NOTE BEFORE YOU GO|`index.html:321`；`[data-text-id="F-128"]`|
|F-129|showcase_v1/index.html / 頁尾／其他|用來理解研究，不能代替診斷。|`index.html:322`；`[data-text-id="F-129"]`|
|F-130|showcase_v1/index.html / 頁尾／其他|SkinDetect 是學生專題與研究展示，輸出不構成醫療建議。若對皮膚狀況有疑慮，請諮詢合格醫療專業人員。|`index.html:323`；`[data-text-id="F-130"]`|
|F-131|showcase_v1/index.html / 頁尾／其他|請使用有權使用且已去識別化的影像。Mock 影像留在瀏覽器；真實推論才傳至這台電腦的本機服務，不保存影像或個案紀錄。分數尚未校準，不代表醫療診斷機率。|`index.html:324`；`[data-text-id="F-131"]`|
|F-132|showcase_v1/index.html / 頁尾／其他|SkinDetect讓研究，被清楚看見。|`index.html:330`；`[data-text-id="F-132"]`|
|F-133|showcase_v1/index.html / 頁尾／其他|學生專題 / FRONTEND V1|`index.html:330`；`[data-text-id="F-133"]`|
|F-134|showcase_v1/index.html / 頁尾／其他|回到頂端 ↑|`index.html:330`；`[data-text-id="F-134"]`|
|F-135|showcase_v1/index.html / 頁首品牌|SkinDetect 皮膚影像辨識研究|`index.html:26`；`[data-text-id="F-135"]`|
|F-301|showcase_v1/index.html / 動態七類結果／AKIEC|日光性角化症／表皮內癌|`app.js:renderResult；core.py:CLASS_LABELS／mock-predictor.js:classes`；`[data-text-id="F-301"]`|
|F-302|showcase_v1/index.html / 動態七類結果／AKIEC|AKIEC|`app.js:renderResult；core.py:CLASS_LABELS／mock-predictor.js:classes`；`[data-text-id="F-302"]`|
|F-303|showcase_v1/index.html / 動態七類結果／AKIEC|〔模型／Mock機率，畫面格式0.0%〕|`app.js:renderResult；core.py:CLASS_LABELS／mock-predictor.js:classes`；`[data-text-id="F-303"]`|
|F-304|showcase_v1/index.html / 動態七類結果／BCC|基底細胞癌|`app.js:renderResult；core.py:CLASS_LABELS／mock-predictor.js:classes`；`[data-text-id="F-304"]`|
|F-305|showcase_v1/index.html / 動態七類結果／BCC|BCC|`app.js:renderResult；core.py:CLASS_LABELS／mock-predictor.js:classes`；`[data-text-id="F-305"]`|
|F-306|showcase_v1/index.html / 動態七類結果／BCC|〔模型／Mock機率，畫面格式0.0%〕|`app.js:renderResult；core.py:CLASS_LABELS／mock-predictor.js:classes`；`[data-text-id="F-306"]`|
|F-307|showcase_v1/index.html / 動態七類結果／BKL|良性角化症樣病灶|`app.js:renderResult；core.py:CLASS_LABELS／mock-predictor.js:classes`；`[data-text-id="F-307"]`|
|F-308|showcase_v1/index.html / 動態七類結果／BKL|BKL|`app.js:renderResult；core.py:CLASS_LABELS／mock-predictor.js:classes`；`[data-text-id="F-308"]`|
|F-309|showcase_v1/index.html / 動態七類結果／BKL|〔模型／Mock機率，畫面格式0.0%〕|`app.js:renderResult；core.py:CLASS_LABELS／mock-predictor.js:classes`；`[data-text-id="F-309"]`|
|F-310|showcase_v1/index.html / 動態七類結果／DF|皮膚纖維瘤|`app.js:renderResult；core.py:CLASS_LABELS／mock-predictor.js:classes`；`[data-text-id="F-310"]`|
|F-311|showcase_v1/index.html / 動態七類結果／DF|DF|`app.js:renderResult；core.py:CLASS_LABELS／mock-predictor.js:classes`；`[data-text-id="F-311"]`|
|F-312|showcase_v1/index.html / 動態七類結果／DF|〔模型／Mock機率，畫面格式0.0%〕|`app.js:renderResult；core.py:CLASS_LABELS／mock-predictor.js:classes`；`[data-text-id="F-312"]`|
|F-313|showcase_v1/index.html / 動態七類結果／NV|黑色素細胞痣|`app.js:renderResult；core.py:CLASS_LABELS／mock-predictor.js:classes`；`[data-text-id="F-313"]`|
|F-314|showcase_v1/index.html / 動態七類結果／NV|NV|`app.js:renderResult；core.py:CLASS_LABELS／mock-predictor.js:classes`；`[data-text-id="F-314"]`|
|F-315|showcase_v1/index.html / 動態七類結果／NV|〔模型／Mock機率，畫面格式0.0%〕|`app.js:renderResult；core.py:CLASS_LABELS／mock-predictor.js:classes`；`[data-text-id="F-315"]`|
|F-316|showcase_v1/index.html / 動態七類結果／VASC|血管性病灶|`app.js:renderResult；core.py:CLASS_LABELS／mock-predictor.js:classes`；`[data-text-id="F-316"]`|
|F-317|showcase_v1/index.html / 動態七類結果／VASC|VASC|`app.js:renderResult；core.py:CLASS_LABELS／mock-predictor.js:classes`；`[data-text-id="F-317"]`|
|F-318|showcase_v1/index.html / 動態七類結果／VASC|〔模型／Mock機率，畫面格式0.0%〕|`app.js:renderResult；core.py:CLASS_LABELS／mock-predictor.js:classes`；`[data-text-id="F-318"]`|
|F-319|showcase_v1/index.html / 動態七類結果／MEL|黑色素瘤|`app.js:renderResult；core.py:CLASS_LABELS／mock-predictor.js:classes`；`[data-text-id="F-319"]`|
|F-320|showcase_v1/index.html / 動態七類結果／MEL|MEL|`app.js:renderResult；core.py:CLASS_LABELS／mock-predictor.js:classes`；`[data-text-id="F-320"]`|
|F-321|showcase_v1/index.html / 動態七類結果／MEL|〔模型／Mock機率，畫面格式0.0%〕|`app.js:renderResult；core.py:CLASS_LABELS／mock-predictor.js:classes`；`[data-text-id="F-321"]`|

## 動態文字與所有狀態的來源

下列是本次版本的完整字串／模板來源逐行索引，保留原文。使用上表的輸出欄位ID提出修改，再指明下列情境，不另產生會隨狀態變動的編號。

### app.js

|位置|原始文字／模板（含狀態與錯誤）|
|---|---|
|app.js:36|$("service-badge").textContent = mock ? "MOCK 固定展示資料" : model?.available ? "研究推論 · 未校準" : verified ? "研究推論 · 預覽模式" : "研究推論 · 待 GPU 驗證";|
|app.js:38|$("mode-help").textContent = mock ? "固定示範分數，不依影像計算，也不會呼叫模型。" :|
|app.js:39|state.serviceError \|\| model?.reason \|\| (state.mode === "v2_imagenet_seed1" ? "使用原 Seed1 best.pt。分數未校準；GPU 輸出一致性狀態見驗證紀錄。" : "每個 Seed 的 softmax 機率各占 1/3，不平均 logits；尚未校準。");|
|app.js:40|$("privacy-text").textContent = mock ? "Mock 影像留在瀏覽器，不傳送至服務。" : "執行時才傳至這台電腦的本機服務；不保存影像。";|
|app.js:41|$("model-connection").textContent = model?.available ? "本機真實推論已開啟" : verified ? "GPU 已驗證 · 模型待啟動" : "介面已建立 · GPU 待驗證";|
|app.js:43|run.textContent = mock ? "產生展示結果 →" : "執行研究推論 →";|
|app.js:48|run.textContent = busy ? (state.mode === "demo" ? "正在準備展示結果…" : "本機模型推論中…") : (state.mode === "demo" ? "產生展示結果 →" : "執行研究推論 →");|
|app.js:72|$("result-notice").textContent = state.mode === "demo" ? "固定 Mock 僅供展示，不依影像內容計算。" :|
|app.js:73|"研究用途；七類分數尚未校準，不代表醫療診斷機率。請依本機服務狀態執行。";|
|app.js:97|setStatus("已清除影像與結果，可重新選擇。");|
|app.js:105|image.onerror = () => reject(new Error("無法讀取影像，檔案可能已損毀，請重新選擇。"));|
|app.js:122|image = { name: "研究示意影像（非臨床影像）", bytes: 0, isSample: true };|
|app.js:124|if (files.length !== 1) throw new Error("一次請只選擇一張影像。");|
|app.js:126|if (!TYPES.has(file.type)) throw new Error("請選擇 JPG、PNG 或 WebP 影像，不支援此檔案格式。");|
|app.js:127|if (!file.size) throw new Error("檔案是空的，請重新選擇。");|
|app.js:128|if (file.size > MAX_BYTES) throw new Error("影像超過 20 MB，請縮小後再選擇。");|
|app.js:133|setStatus("正在讀取影像…");|
|app.js:138|throw new Error("影像尺寸無效或超過 6,400 萬像素，請先縮小尺寸。");|
|app.js:145|preview.alt = isSample ? "研究示意圖，非臨床影像" : "已選擇的影像預覽";|
|app.js:152|$("file-meta").textContent = \`${dimensions.width} × ${dimensions.height} px · ${isSample ? "內建示意圖 · 非臨床影像" : size}\`;|
|app.js:153|setStatus(state.mode === "demo" ? "影像已準備好。可產生固定 mock 展示結果。" : "檔案已可讀；適用性尚未自動確認。真實推論需本機服務開啟模型。");|
|app.js:158|setStatus(state.image ? "新影像未載入，保留原影像。" : "請重新選擇影像。");|
|app.js:194|meter.setAttribute("aria-label", item.label + (mock ? " mock 相對機率" : " 未校準相對機率"));|
|app.js:205|$("result-kind").textContent = mock ? "模擬資料" : "真實模型 · 未校準";|
|app.js:206|$("score-kind").textContent = mock ? "展示分數" : "未校準相對機率";|
|app.js:207|$("distribution-kind").textContent = mock ? "相對機率（mock）" : "相對機率（未校準）";|
|app.js:208|$("result-model-info").textContent = mock ? "固定 mock 範例，不使用模型權重。" :|
|app.js:209|result.model_label + " · " + result.members.map(member => \`Seed ${member.seed}（最佳輪 ${member.best_epoch}，權重 ${member.weight === 1 ? "1" : "1/3"}）\`).join("／");|
|app.js:210|$("result-notice").textContent = mock ? "本次是固定示範數值，不依影像內容計算，並非 ConvNeXt V2-Tiny 實際推論。" :|
|app.js:211|"本次為原 V2 模型輸出；分數未校準，不代表醫療診斷機率。本版未驗證圖片適用性，不能判定正常皮膚或排除七類以外疾病。";|
|app.js:212|$("explanation-text").textContent = mock ? "這份固定範例將「黑色素細胞痣」設為最高分，用來示範七類分布的閱讀方式。它不依你的影像計算，也不代表健康狀況；高分不等於確診。" :|
|app.js:213|\`在模型已學習的七個類別中，「${top.label}」的相對分數最高。${result.members.length === 3 ? "本結果由三個 Seed 的 softmax 機率各占 1/3 平均。" : "本結果使用原 ImageNet Seed1。"}分數尚未校準，高分不等於診斷正確；這是限定七類中的比較，未確認影像適用性；模糊、正常皮膚或七類外影像也可能得到高分，不能據此判定正常或排除其他疾病。\`;|
|app.js:234|setStatus(state.image?.isSample && state.mode !== "demo" ? "示意圖不能作真實推論，請選擇 JPG、PNG 或 WebP。" : "模型版本已切換，前份結果已清除。");|
|app.js:262|setStatus(mode === "demo" ? "正在準備固定 mock 展示。" : "正在本機執行原 V2 推論；首次載入權重可能較久。");|
|app.js:268|setStatus(mode === "demo" ? "展示完成。固定模擬數值，非真實推論。" : "真實推論完成。分數未校準，僅供研究。");|
|app.js:273|setStatus("本次沒有取得模型結果，不會自動改用 mock。");|
|app.js:295|state.serviceError = error.message + "；仍可選擇 Mock 展示。";|
### inference-client.js

|位置|原始文字／模板（含狀態與錯誤）|
|---|---|
|inference-client.js:6|const labels = ["日光性角化症／表皮內癌", "基底細胞癌", "良性角化症樣病灶", "皮膚纖維瘤", "黑色素細胞痣", "血管性病灶", "黑色素瘤"];|
|inference-client.js:13|throw new Error("服務回應與選定的原 V2 模型契約不符，未顯示結果。");|
|inference-client.js:21|throw new Error("服務的七類分數或等權 Seed 成員不符，未顯示結果。");|
|inference-client.js:36|catch { throw new Error("本機服務回應無效；請確認使用的是新版前端服務，而非舊靜態伺服器。"); }|
|inference-client.js:37|if (!response.ok) throw new Error(result.error \|\| \`本機服務失敗（HTTP ${response.status}）。\`);|
|inference-client.js:40|if (expired) throw new Error("推論等待逾時；本機已送出的工作可能仍會完成，請勿連續重送。");|
|inference-client.js:42|if (error instanceof TypeError) throw new Error("無法連線到本機 V2 服務，請確認已使用新版 start_frontend.ps1 啟動。");|
|inference-client.js:55|reader.onerror = () => { finish(); reject(new Error("無法讀取上傳影像。")); };|
|inference-client.js:56|reader.onabort = () => { finish(); reject(new DOMException("已取消", "AbortError")); };|
|inference-client.js:57|if (signal?.aborted) { reject(new DOMException("已取消", "AbortError")); return; }|
|inference-client.js:66|if (catalog.api_version !== "v2-ensemble-v1" \|\| !Array.isArray(catalog.models)) throw new Error("不是新版 V2 推論服務。");|
### mock-predictor.js

|位置|原始文字／模板（含狀態與錯誤）|
|---|---|
|mock-predictor.js:10|{ code: "AKIEC", label: "日光性角化症／表皮內癌", probability: .048 },|
|mock-predictor.js:11|{ code: "BCC", label: "基底細胞癌", probability: .091 },|
|mock-predictor.js:12|{ code: "BKL", label: "良性角化症樣病灶", probability: .132 },|
|mock-predictor.js:13|{ code: "DF", label: "皮膚纖維瘤", probability: .027 },|
|mock-predictor.js:14|{ code: "NV", label: "黑色素細胞痣", probability: .624 },|
|mock-predictor.js:15|{ code: "VASC", label: "血管性病灶", probability: .018 },|
|mock-predictor.js:16|{ code: "MEL", label: "黑色素瘤", probability: .060 },|
|mock-predictor.js:26|model_label: "固定 mock 資料（非 ConvNeXt V2-Tiny 推論）",|
|mock-predictor.js:32|heatmap: { requested: false, available: false, method: "Grad-CAM", overlay_data_url: "", notice: "尚未串接；不產生模擬熱力圖。" },|
|mock-predictor.js:33|medical_notice: "研究展示用模擬資料，不構成醫療診斷。",|

API的錯誤與類名原文另由`v2_inference/core.py`、`runtime.py`及`ensemble_server.py`產生；畫面錯誤插槽對應`#upload-error`固定ID，模式說明對應`#mode-help`，本輪不改API文字或契約。

共 156 個固定ID（HTML 135、類別結果21）；2026-10-25初版。
