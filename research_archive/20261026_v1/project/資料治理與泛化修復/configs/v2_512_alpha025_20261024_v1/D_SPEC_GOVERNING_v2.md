## 2026-10-24 v2｜512單一抽樣變因正式改良提案（待一次核定）

### 最新目標與取代範圍

本節依使用者最新選擇：繼續V2正式改良、保留大部分超參數、只選一個主要變因；撤銷一小時訓練限制。前述v1/v1.1「暫不訓練、成本先行」是先前目標下的歷史建議，不再作本輪前置。CPU／GPU及B原資料最小GPU檢查已通過，不重測；不要求先測成本或重新取得舊C/D原件。

本次只提出並保存方案，沒有執行訓練、推論、建立配置、修改正式參數或替使用者核定。接受本方案後才由總控分別交C落盤、B作必要版本相容並執行；不直接Resume已completed的任何舊run。

### 1. 唯一推薦

**以ConvNeXt V2-Tiny ImageNet／512×512為主線，唯一研究變因為來源內類別平衡抽樣指數 class_balance_alpha：0.50 → 0.25。** 三來源期望份額仍HAM/BCN/PAD各1/3；同一512配方的已完成Seeds1/2/3為主要配對對照，224／320既有三Seed作次要脈絡對照，不重訓任何對照、不建立新Ensemble或更換網站模型。

研究問題：在512較大尺寸配方保留既有Robust收益的同時，較弱的來源內類別再平衡，能否改善三來源NV Recall／整體Macro-F1的損失，而不破壞BCN及重要少數疾病？

**證據與假說分開：** C既有比較記載512對224 Robust +2.7208pp、BCN MEL +5.5894pp，但HAM/BCN/PAD NV平均Recall分別下降5.5335／8.1623／13.8889pp，BCN VASC亦下降4.7619pp。512相對320 Robust仍+1.5448pp，Macro-F1卻−0.4045pp。這足以提出「調整訓練曝光的權衡」研究問題，但沒有證明抽樣造成損失，亦沒有證明0.25最佳；本候選是一個預先固定的、有風險的消融，不能保證改善。

本機train_regularized.py的sample_weights已實作：來源s類別c有n_sc筆，每張權重為 n_sc^(−alpha) / Σ_k n_sk^(1−alpha)。因此來源總質量相同；在來源內，類別質量正比 n_sc^(1−alpha)。由0.5改0.25會使抽樣分布較接近原始類別組成，增加該來源內較多樣本類別相對曝光，同時減少稀有類別相對曝光。這是程式公式的直接推論，不是新的資料分析或實測效果。NV在各來源的實際曝光變化須C於核定後依Train既有計數列出，不用Validation調參。

0.25選為原0.5與不作來源內類別補償的0之間的單一中間值；本輪不搜尋0、0.1、0.75或其他alpha。其風險正是DF／VASC／MEL可能因曝光降低而受損，故必須保留全疾病與嚴格Robust判讀，不可只以NV上升宣布成功。

### 2. 已淘汰候選核對與不原樣重試

本輪直接讀C existing_decisions.json所引用的四份原screen決策，均passed=false、各只有Seed1/2；不重新計分或補Seed3。

|舊候選|原唯一改動|原淘汰重點|本提案避免重試|
|---|---|---|---|
|v2in_lr5e5|LR1e-4→5e-5|Robust、BCN BA、Macro-F1、BCN BKL未過|LR保留1e-4|
|v2in_ld09|LayerDecay1→0.9|Robust、BCN BA、Macro-F1、單SeedRobust、BCN DF、合併MEL未過|LayerDecay保留1|
|v2in_r2_bcn50|來源HAM/BCN/PAD各1/3→.25/.50/.25|Robust、BCN BA、Macro-F1、Accuracy、單SeedRobust、BCN VASC未過|來源各1/3不變；本次改來源內類別指數，不改BCN份額|
|v2in_r2_re0|RandomErasing p=.15→0|Robust、BCN BA、Macro-F1、單SeedRobust、BCN DF/VASC未過|RandomErasing p=.15保留|

四個舊候選是在224配方篩選失敗，不外推為在所有解析度必然無效；本次仍不重試它們，因有其他未測因素可作單一可追溯消融。Patience8只有歷史未執行建議，沒有涵蓋512的有效性證據；本次Patience維持5，不延長Max／Tmax。

### 3. 完整候選配方與差異

提議研究版本：v2_512_alpha025_20261024_v1；候選ID：v2in_res512_alpha025。名稱是未建立的預定位置，不是既有配置或執行結果。

唯一科學配方差異：training.class_balance_alpha=0.25。其餘以下均取現有v2in_res512.json、512 run_inputs及對應trainer/model_profiles實作，新增研究ID／路徑／授權／當次環境證據屬必要版本metadata，不是假稱原版本繼續運行。

|項目|本次具體建議（均待核定）|
|---|---|
|架構|真正ConvNeXt V2-Tiny，7輸出，timm convnextv2_tiny.fcmae_ft_in1k；不改GRN／stage／classifier形式或模型預設正則化|
|解析度|Train 512×512；Validation直接Resize 512×512，RGB|
|資料|governed_18979_20261018_v1；Train18919、Validation3611（HAM1504/BCN1712/PAD395）；既有切分不變、不開封Test|
|Manifest身分|5c501ef3cb6c8a73b3a9395383d199212e070abfbc67c782fcfc010576243284；使用manifest-release/run_inputs，不能用舊unified_manifest字串代替|
|類別|AKIEC/BCC/BKL/DF/NV/VASC/MEL；PAD DF/VASC無支持為N/A|
|Seed政策|固定1→2→3，3個新獨立run；全三Seed完成比較，不用前兩Seed品質取消第三個，異常仍停止。無其他候選、自動追加Seed或重跑對照|
|初始化|各Seed從同一釘選ImageNet backbone初始化，七類head依同Seed新建，空Optimizer；不從任何224/320/512 best.pt續訓、不用smoke權重|
|預訓練身分|timm/convnextv2_tiny.fcmae_ft_in1k，revision508caf1bc24fd02c69d15778b994e808670dbc28；SHA fdfb4edfa5abb3b4ea29ab17e6fae5c117dc6cc32ecfb1d0726a156f40a4c1a5；沿用本機原快取，不下載|
|Batch|micro-batch8×gradient accumulation8，名目有效64；最後不滿累積窗的行為沿用原trainer，不擅改drop_last或重標為另一有效Batch|
|抽樣|WeightedRandomSampler、有放回、每Epoch18919次抽取；來源各1/3，唯一alpha=.25；無完整覆蓋保證，Train monitor固定原Seed規則1500張，不更換資料|
|LR／Optimizer|LR1e-4；AdamW；betas(.9,.999)、eps1e-8、amsgrad=False；WeightDecay=.05，原parameter_groups對1D/bias為0；LayerDecay1.0；foreach/fused維持既有預設None，不自行改fused或加速路徑|
|Loss|CrossEntropy、LabelSmoothing=.1；MixUp alpha=.2；gradient clip norm1.0|
|Epoch／Scheduler|Min12、Max30；CosineAnnealingLR T_max=30、eta_min1e-6，原每Epoch評估及停止判定後step順序不變；不能依實際停止輪重設Tmax|
|EarlyStopping|啟用，Patience5、MinDelta0；以Robust嚴格大於歷史最佳改善，同分保留首次最佳，bad_epochs從第一輪累計；Min12只限停止時機。epoch≥30停止，否則epoch≥12且bad_epochs≥5停止|
|選模|每Seed取首次最高Validation Robust的best.pt；最小Epoch不限制最佳輪必須≥12；不用最後輪權重替代best，不按Macro-F1二次挑Epoch|
|正規化|ImageNet mean [.485,.456,.406]、std [.229,.224,.225]|
|Train增強|原regularized_native：RandomResizedCrop scale(.7,1)、ratio(.75,1.33)；H/VFlip各p=.5；Rotation±25°；ColorJitter(.22,.22,.20,.03)以p=.8；Grayscale .05；GaussianBlur3/sigma(.1,1.5)以p=.15；Autocontrast .10；Normalize後RandomErasing p=.15、scale(.02,.10)、ratio(.3,3.3)、value=random|
|Validation增強|僅原Resize→ToTensor→ImageNet Normalize；無TTA／校準／閾值搜尋|
|執行|CUDA必要、AMP=True、workers4、pin_memory=True、persistent_workers=True、prefetch_factor4；不改worker數、微批或AMP以追GPU利用率；沿用RNG隔離與原抽樣generator（seed+4）、monitor seed+3、loader seed+100+index|
|環境|既有tools/Python312、.venv-skindetect-recovery-20261023；沿用已通過收據。舊run記載Python3.12.10、torch2.11.0+cu128、torchvision.26.0+cu128、numpy1.26.4、Pillow10.4.0、timm1.0.30，C/B只記錄當次實際相符性，不重新import小測或安裝|

模型／Optimizer未明設的其他既有預設，沿用釘選套件與同一builder，由C在生效契約明列，不自行為「完整」而新增不同設定；發現歷史與本機預設不一致時列具體差異交總控，不默改。AdamW上列betas/eps/amsgrad係本輪唯讀核對現有torch/optim/adamw.py預設；沒有匯入torch或啟動模型。

persistent workers增強RNG不保證中斷後逐位元重播；本次同Seed比較支持配方差異，不能宣稱完全隔離抽樣後所有亂數路徑。既有同版本歷史對照可沿用，但重置環境／新增相容程式的版本差異仍需記錄，不宣稱跨時間完全無偏。

### 4. 評估與成功／停止判準（新候選專用，待核定）

Robust仍為0.5×三來源BA平均＋0.5×最低來源BA。候選減同Seed原512是主對照；224／320只用現有C結果作次要比較，不重新選模型或改閾值。各Seed與n=3 mean/sample SD（ddof=1）、同Seed差值均保留，三次Seed不增加獨立Validation病例數。

**為了區分「跑完」與「值得採納」，提議三Seed完成後須同時滿足以下預先固定條件，才列下一步候選；不等於正式／臨床／網站自動採納：**

1. 主指標：相對原512平均ΔRobust≥+1.0pp；至少2/3 Seed嚴格提升；每SeedΔRobust≥−1.0pp。
2. 整體／來源：平均ΔMacro-F1≥0、ΔAccuracy≥0、ΔBCN BA≥0；HAM/PAD平均BA各≥−1.0pp。
3. 本假說目標：三來源NV各自平均ΔRecall≥0，且至少一來源嚴格提升；不只報合併NV或靠不同來源互相抵銷。
4. 重要疾病保護：BCN DF/BKL/MEL/VASC各平均ΔRecall≥−3.0pp；三來源合併MEL平均ΔRecall≥−1.0pp。其他有支持的來源疾病各平均ΔRecall≥−5.0pp。PAD DF/VASC維持N/A，不補0；小支持數造成的一張影響仍如實列出，不事後放寬。
5. 各來源／各疾病保存TP/N/Recall及三Seed得失，沿用已有混淆矩陣可讀MEL→NV、DF→BCC總量；沒有逐張分數不宣稱同病例修正或互補性。Validation反覆使用屬探索，不報獨立泛化、統計顯著或Test成效。

這些是本新候選的待核定判準，不追溯評判既有512為「新門檻淘汰」。若NV改善而Robust／疾病保護未過，記為局部改善但不採納；若全三Seed結果未通過，結束此唯一候選，不自動回調alpha或開下一組。

品質判讀在完成後進行，不以Seed1/2品質提前取消Seed3；訓練內選模／早停仍只用原Robust規則。正常上限3runs／90完整Epoch，Min12可早停；異常、資源或指紋問題則立即停止／完整邊界安全暫停，不能跳下一Seed掩蓋失敗。

### 5. 時間、預算與效率

**新輪不設wall-clock時間上限**，不把舊3600秒、25920秒或解析度61560秒餘額移入，也不因取消時限而刪STOP/lock/ledger。工作量仍有限：1個候選×3Seed、每Seed≤30Epoch，總≤90完整Epoch；失敗嘗試實耗也記錄，不自動無限重試、重啟或訓練到目標分數才停。

估時僅引用原512規劃約6.5分鐘/Epoch、三Seed90Epoch含原緩衝約11.7小時，作排程參考而非硬上限。原512實際12/15/12輪共39完整Epoch，訓練預算記錄14255.958秒；停止時機與現時I/O不同，不保證本次相同耗時或GPU100%。不拿最小前向秒數估訓練速度、不另加吞吐benchmark作前置。

在核定的新run內保存原有Train／Monitor／Validation／Checkpoint耗時、GPU等待／峰值等既有監測，發現GPU空轉先以這些證據定位，不自動改LR、Batch、workers、cache／資料。持續資源壓力、OOM、NaN/Inf、資料／類別／權重／程式指紋衝突、存檔失敗、GPU衝突保留原停止條件；Commit8GiB守護不放寬。任何需改配方或Windows／資源政策的處理另交總控，取消一小時限制不構成這些改動授權。

### 6. 給C的設定落盤完整指令（核定後才下達）

> 在D:\SkinDetect_base先讀AGENTS、兩共用入口、C的resolution_decision_20261024_v1/REPORT.md、本DECISION v2及既有C配置稽核。目標是唯一新候選v2in_res512_alpha025；主對照為原512 Seeds1/2/3，224/320歷史結果保留。以configs/v2_resolution_20261021_v1/v2in_res512.json和對應run_inputs為基底，只改科學參數training.class_balance_alpha=.25；維持本v2表中其餘全部配方與實作。新ID／路徑／授權／無時間硬上限政策另明列metadata差異，不沿用舊approval或authorization SHA。
>
> 核定後新增資料治理與泛化修復/configs/v2_512_alpha025_20261024_v1：候選JSON、suite、使用者核定原文AUTHORIZATION.md及差異／來源說明；同名存在則新版本，禁止覆寫歷史。Seeds固定[1,2,3]、完整三Seed、不按兩Seed品質取消第三；Max30/Min12/Patience5/Tmax30，總3run/90完整Epoch，wall_clock_cap明示null/未設上限而非複製舊budget或用極大數假裝。保留實際耗時計帳與異常停止，不預先寫completed/passed。
>
> 完整列出各模型／初始化、有效training、預處理、類別／release／Manifest身分、對照路徑、本v2採納判準；確認原sample_weights讓來源各1/3，僅alpha改變來源內類別質量。可用既有Train來源類別計數推導新期望份額並列為新抽樣契約，不能用Validation調參或讀影像／Test，不重算已完成比較。若參數、程式或資料定義不一致，列衝突停止，不自行選值。
>
> 現有model_profiles只接受既有候選，且新ID預設會被32×2鎖拒絕；v2_resolution_contract只核定原兩個ID與舊秒數上限。本C不可沿舊v2in_res512 ID直接改alpha或填成舊gate通過。將新ID／512的8×8／alpha唯一差異與無秒數上限的明確相容需求交B，以最小新版本契約銜接原trainer／CheckpointStore。C只管設定／契約，不代B改啟動器或執行GPU。
>
> 交付以新JSON的唯一科學差異、完整欄位、三Seed／工作量／選模／疾病保護、預訓練來源與對照可追溯為驗收；未完成的B相容／資源條件如實列出，不假寫已就緒。交付後停止，不訓練、推論、測成本、下載、安裝或向其他chat發訊息。兩共用入口由總控記錄；本指令僅在使用者正式核定本方案後生效。

### 7. 給B的正式執行完整指令（使用者同意整份方案後才下達）

> 在D:\SkinDetect_base，閱讀AGENTS、兩共用入口、本DECISION v2、C新落盤v2_512_alpha025_20261024_v1全份配置／核定／差異與既有startup_repair、minimal_realdata_gpu、runtime/artifacts收據。核對研究目標僅alpha .5→.25，模型512、Seeds1/2/3、微批8×累積8、LR1e-4、AdamW WD.05/LD1、LS.1/MixUp.2/RE.15、Max30/Min12/Patience5/Tmax30與本表完全一致。核定後執行一個候選的三個新run；不重跑29個completed、不補四個淘汰Seed3、不跑成本、不開Test。
>
> 先保存與自己改動相關來源before／版本，保留他人既有tracked修改。沿用train_regularized、training_state與CheckpointStore等共用實作，僅為新候選註冊適用profile／唯一差異驗證及新輪runner/gate／ledger路徑；原baseline/解析度契約與固定budget不改寫成新規格。新契約嚴格限定v2in_res512_alpha025的512/8×8/alpha.25及其餘原值。無wall-clock上限須作顯式可驗證的未設上限模式，保留3run/90完整Epoch、計時與守護，不能任意填大秒數、清budget或繞過gate。
>
> 使用既有.venv-skindetect-recovery-20261023/Scripts/python.exe及本機釘選預訓練快取。初始化各Seed從原ImageNet backbone＋同Seed新七類head、空optimizer獨立開始，不載原512 best.pt當初始化。若新id／契約最小實作必要，可作與修改直接相關的語法、CPU結構／唯一差異及啟動拒絕條件檢查；既有CPU/GPU合成與原資料小測已過，不重跑它們，也不先做成本／全量Loader／GPU benchmark或完整模型hash。現有可用身分收據沿用，若檔案metadata或契約有新差異才補必要核對，衝突就停止。
>
> 真正啟動前一次唯讀核對程序／GPU排程、Commit/RAM/磁碟與新輸出位置，依正式訓練適用守護處理，不因舊小測而放寬、不干擾其他程序、不輪詢到剛好放行；不把歷史快照當現在資源。B原資料小測僅驗過前向，不能宣稱反向／optimizer／完整負載已通過；在本次核定新run中按原guard監控並保存首個完整Epoch／checkpoint，而不是額外先重做另一套研究。若已知資源或實作契約無法安全開始，列具體阻礙交總控，不自行改Batch／workers／pagefile或拿smoke當正式結果。
>
> 新結果根目錄資料治理與泛化修復/results/v2_512_alpha025_20261024_v1，各run單獨regularized_seed1～3，保存run_id、實際命令、有效設定／來源指紋／環境差異、run_inputs、每Epochhistory/metrics、best.pt、完整Checkpoint雙代與索引、資源／失敗／耗時計帳及狀態。先向使用者摘要生效模型、資料、Seed、Epoch、Batch、LR及評估規則，再依已核定指令開始；不要求重複核准相同設定，也不越過未解衝突。
>
> 依Seed1→2→3各自完整跑到原EarlyStopping或30Epoch；不以中途分數切換候選／改alpha，不挑seed。OOM／非有限值／Commit守護／資料或權重身分不符／GPU衝突／存檔失敗立即停止，記錄原因與可恢復完整邊界；不因時間無上限而自動重試失敗或一直Resume。只對本輪尚未完成且原核定／完整Resume契約適用的run，才可依原授權在安全邊界恢復，不能動completed舊輪；未明確涵蓋的異常恢復先回報總控。
>
> 完成三Seed後輸出B正式結果與狀態，不代D宣稱採納；交C整理候選減同Seed原512及次要224/320的Robust、Accuracy、Macro-F1、三來源BA、所有疾病TP/N/Recall、保存的MEL→NV/DF→BCC總量與成本；C不重跑舊模型，D依本v2事先規則判讀。不新建Ensemble、不以Test回頭選模，不自動追加第二候選。共用入口由總控追加，B只交完整產物與完成／未完成／下一步後停止。

以上是完整可交辦的執行規格，不虛構尚未建立的新runner CLI。B須在其實際交付中保存可複製的啟動／查狀態／適用Resume命令；目前舊Start-V2Resolution指向completed研究，不能把它當新候選可直接執行命令。

### 8. 本輪來源／修改及驗收

本輪重新讀最新AGENTS、PROJECT_STATE、V2_EXPERIMENT_HISTORY、C REPORT及既有D全文；另唯讀核對C existing_decisions對應四個screen=false、原512 JSON/run_inputs、train_regularized.sample_weights與transform/loader、model_profiles的註冊／Optimizer/Scheduler/初始化、v2_resolution_contract的舊ID／budget限制，以及現有torch AdamW預設來源。未讀Train/Test逐筆成員或影像、未匯入模型／Python、未重算預測／既有比較或執行測試。一次唯讀組合命令因PowerShell空pipe語法失敗，修正後只讀所需欄位，沒有任何研究程序啟動。

工作目錄D:/SkinDetect_base；PowerShell Get-Content、Select-String、ConvertFrom-Json與.NET AppendAllText。本輪唯一修改是追加本DECISION v2；不建立新配置／runner／報告，不修改C結果／舊研究或兩共用入口。已保留前文歷史並核對新增前原bytes前綴不變。此為有證據支撐的單候選假說提案，不是保證提升、已核定配方或正式執行收據；本次完成停止。
#### v2補充｜Train計數已確認的作用方向與風險（同輪核定前澄清）

在本輪最終交付前另只讀原512 Seed1 result.json → sampling.source_class_counts，沒有重讀Manifest或重新統計：HAM NV4692、BCC360、DF80、VASC98、MEL779；BCN NV3514、BCC2448、DF91、VASC90、MEL2519；PAD NV195、BCC688、AKIEC588、BKL179、MEL41。以上是Train各來源既有計數，不是Validation支持數。

這使假說更精確：較弱類別補償主要測試HAM／BCN的大類NV與少數類得失，**不能宣稱PAD NV的曝光也提高**；PAD NV低於BCC／AKIEC，降低alpha反而存在相對曝光下滑風險，PAD MEL也可能受損。故本提案是可被否證的單因素權衡研究，不是對三來源NV損失已找到一致根因。若使用者要求保證同時改善所有疾病，現證據不支持該要求，本輪不能作此保證。

核定時第4節目標條件明確解讀為：HAM／BCN NV平均Recall各不降，且至少一者嚴格提升；PAD NV平均Recall亦不得下降，作必要外來源保護。其餘Robust／Macro-F1／Accuracy／來源BA／BCN DF/BKL/MEL/VASC／合併MEL與其他疾病門檻全部保留。這是本候選提出前已知風險下的固定判讀，不能等結果出來才放寬。若PAD或少數類退步，結案不採納，而非自動追加第二候選。

C核定後仍須依此原Train計數與現有sample_weights公式明列alpha=.25的期望曝光，以確認唯一變因落實；那是新配置抽樣契約，不是重新分析既有預測。以上數值核對僅PowerShell讀取既有sampling欄位，本D未計算任何新模型品質或修改配方JSON。
<!-- MASTER-V2-512-ONLY-RATIONALE:20261024:v1 -->
### 2026-10-24 v2.1｜總控補記：本輪只新增512、保留224／320的理由與E引用

依使用者要求補齊研究設計可追溯性，完整理由／品質與實際耗時來源／可供E報告引用段落已追加至 docs/V2_EXPERIMENT_HISTORY.md 的「V2-512-ALPHA｜本輪只新增512訓練的理由與報告引用｜2026-10-24 v1」（marker MASTER-V2-512-ONLY-RATIONALE:20261024:v1）。本輪直接在目標512驗證唯一alpha候選，沒有經驗證的低尺寸排名轉移，不額外增加224／320篩選；原224／320不是淘汰，128不是這組已完成尺寸。新候選完整配方及採納規則仍沿用本v2第3/4節與v2末尾補充，不修改原提案內容。

目前新配置／新runner未建立，總控僅提供可貼給C→B的完整設定／執行指令，未代發C/B或開訓。C設定／B啟動相容與當下正式資源確認是實作前提，不能直接啟動舊completed launcher。主線選擇不宣稱新配方已有效／512全面勝出或網站已換模。原文件前文保留；本段由總控追加，不代D重算研究或修改其數值／判準。