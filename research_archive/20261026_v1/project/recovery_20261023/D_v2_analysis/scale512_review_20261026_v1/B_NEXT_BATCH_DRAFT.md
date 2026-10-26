# 給 B 的完整可貼指令草案｜512 模型大小後續 v1

日期：2026-10-26（臺北）。**本文件是 D 提案，不含新的訓練／GPU執行授權。使用者須明確核定以下整套設定及3 run／90 Epoch預算後，B才可開始；先前scale／Resume授權已結案，不能沿用為新工作授權。** 不需再經C固定統計中繼。

---

請依使用者對本草案的明確核定，執行唯一一套後續研究：**Base Seed2 → Base Seed3 → Large Seed1 2×32**，單GPU順序、各新初始化一次。先確認本任務是否已落盤／啟動／完成；有既有產物就承接狀態，不重複啟動。沒有明確新核定就只保存準備狀態，不開GPU。

## 工作位置、必讀與可改範圍

工作目錄 `D:\SkinDetect_base`。先讀AGENTS、docs\PROJECT_STATE.md、docs\V2_EXPERIMENT_HISTORY.md最新段落，以及：

1. `recovery_20261023\D_v2_analysis\scale512_review_20261026_v1\REPORT.md`、NUMERIC_ANALYSIS.json及本指令。
2. `資料治理與泛化修復\results\v2_scale512_seed1_20261025_v1\FINAL_RESULTS.json`、B_HANDOFF及原Base／Large run_inputs、metrics／result。
3. 對應configs三配置、WEIGHT_SPECS、原AUTHORIZATION；B的scale README、large_resume2恢復／序列化證據。舊授權只作歷史來源。
4. D root_cause_20261025_v1及B matched_source_trainval_512_20261025_retry1_v1已完成報告，直接引用；不重跑診斷、29個舊run或任何已通過且適用的micro2預檢。
5. 舊alpha025的EVALUATION_CONTRACT.json：只作以下前瞻Base數值保護條件的逐條來源，不把舊alpha結案改寫為已採納。

核定後新產物落在：

- `資料治理與泛化修復\configs\v2_scale512_followup_20261026_v1`
- `資料治理與泛化修復\results\v2_scale512_followup_20261026_v1`
- `recovery_20261023\B_training\scale512_followup_20261026_v1`

若已存在，不覆寫；先查明完成／執行狀態，確需新版本才另編版本並記錄。原資料、配置、結果、權重、frozen source、gate、Resume歷史與網站全部保留。只作新版本設定／准入／監控／計帳必要銜接，科學訓練與評估計算不變；本草案不授權安裝、下載、Windows／pagefile／驅動變更或換網站模型。

**舊v2_scale_contract.py限定Seed1／舊VERSION／舊結果root，舊入口拒絕completed study，不能直接重跑Start-V2Scale512.ps1或直接把Seed改成2。** B應沿用現有共用trainer、CheckpointStore及監控，為核定的三個job建立可追溯新版本契約／gate／controller，只准入下表，保留一次啟動、每run鎖、STOP、預算及Test隔離，不以關閉驗證或冒用舊token繞過。若需修改共用派送介面，只做必要最小相容改動、保留既有差異，通過CPU檢查；如與核定契約衝突則停止回報，不自行改研究條件。

## 三個job、初始化及對照

|執行順序／新candidate ID|Seed|模型|micro×accumulation|主對照／用途|
|---|---|---|---|---|
|1：v2in_scale512_base_confirm|2|convnextv2_base|2×32|原Tiny512 Seed2；補Base穩定性|
|2：v2in_scale512_base_confirm|3|convnextv2_base|2×32|原Tiny512 Seed3；補Base穩定性|
|3：v2in_scale512_large_micro2|1|convnextv2_large|2×32|原Large512 Seed1 1×64；診斷micro／累積配置|

各自新run ID、head按指定Seed新建、空AdamW／新scheduler／scaler，不接Base／Large best或last、不接預檢權重、不Resume舊run。Base Seed1直接引用舊scale的efc7718472e14007be0686800f5183c3，不重訓；Tiny Seed1/2/3只引用原v2_resolution_20261021_v1。Large原對照run為7c6b140d4ed442389852be8707d8e2c6（最佳輪11、中斷前），輔助比較新Large與既有Base Seed1同2×32；不宣稱完全隔離架構／MixUp因果。

新准入核對須區分Seed：舊Seed1預檢head SHA不能拿來要求Base Seed2／3相同；新run保存指定Seed、初始化來源、初始head SHA與空optimizer，沿用確切同Seed的初始化邏輯。Large新Seed1可沿用已保存的Seed1獨立初始化head預期身分，不新增預檢。

Base權重沿用本機：`weights/v2_scale512_seed1_20261025_v1/base/7b29800e499fdc06de5b612970f3384dc8d29ca5/model.safetensors`，來源timm/convnextv2_base.fcmae_ft_in1k，SHA256 `ec152f1e375edc2b3dfac7a81155a449b4c5cbb7c5cf0b9494838f6c87518d73`。

Large權重沿用本機：`weights/v2_scale512_seed1_20261025_v1/large/774e71d83a0870798b626b0723ce0b6c08746b1b/model.safetensors`，來源timm/convnextv2_large.fcmae_ft_in1k，SHA256 `193dfc02aebad3774dc16f7bcc8a24d3bd68f5e3da7a44a2269010010cb976d3`。固定FCMAE／ImageNet1K類型與revision，七類head重建；不換22K／隨機初始化／新權重。

## 全部固定設定及差異

直接複製舊scale Base／Large配置中的科學設定，僅改新版本metadata／candidate／Seed清單，以及**Large batch_size 1→2、gradient_accumulation 64→32**。Base科學設定完全不改，只補Seed2、3。

- 資料：governed_18979_20261018_v1，manifest SHA256 `5c501ef3cb6c8a73b3a9395383d199212e070abfbc67c782fcfc010576243284`；Train18919、原Monitor1500、Validation3611（HAM1504／BCN1712／PAD395），七類順序AKIEC/BCC/BKL/DF/NV/VASC/MEL。只用Train／Validation，Test封存；沿用loader篩選，不另開Test檔案或影像。
- 512 RGB，ImageNet mean[.485,.456,.406]/std[.229,.224,.225]；原regularized_native Train與Validation完整transform逐字沿用run_inputs.contract.effective_transforms，不切換官方crop／插值。
- 原Train：RRC scale .7–1、ratio .75–1.33／bilinear；H/V flip各.5；rotation±25（原nearest）；ColorJitter原p.8及原幅度；grayscale .05、blur .15、autocontrast .1、RandomErasing .15及原scale／ratio。Validation為512方形bilinear Resize、ToTensor、原Normalize。
- 三來源各1/3期望份額、有放回平滑抽樣alpha .5，samples_per_epoch18919；不改BCN50或alpha025。
- effective Batch64，micro2×accum32；LR1e-4，AdamW、WD.05、LayerDecay1，原bias／一維參數WD0分組；原AdamW預設betas(.9,.999)、eps1e-8、amsgrad false及原實作路徑；全參數可訓練，不凍結／offload／換optimizer。
- CrossEntropy label smoothing .1、原microbatch-local MixUp alpha .2、gradient clip norm1、AMP；不改成跨累積MixUp，不另加DropPath或其他模型選項。
- Workers4、prefetch4、persistent workers及原Seed／loader策略。
- Max30／Min12、EarlyStopping true／Patience5／MinDelta0；Cosine T_max30、eta_min1e-6；每輪完整原Monitor＋Validation，**首次最高Robust**選best，不按F1／MEL另選輪。
- Robust=.5×三來源BA平均+.5×最弱來源BA；BA只平均該來源有支持類別，PAD DF/VASC為N/A；Accuracy／Macro-F1沿用合併混淆矩陣語意。保留原完整雙代Checkpoint與best。

Large micro2恢復跨圖配對機會，但兩張randperm仍有1/2機會整批自配對；它與Tiny micro8不等效。此變因同時改累積步數、配對與隨機序列，不把結果單獨歸因MixUp。不能為純因果再自行新增MixUp0或其他run。

## 預算、排程與必要檢查

**上限3個新run、各最多30、合計最多90完整Epoch；正常早停最少各12（總36），異常停止可不足。無wall-clock硬上限，不恢復舊一小時限制。** 不因省下Epoch追加run／Seed／Huge／Tiny重訓／自動重試或Resume。

現有整輪依據：Base非首輪中位12.181分；Large1非首輪20.957分，驅動重裝後輪15/16約22.34分。Large2只將訓練段按既有短預檢15.0620/14.5142=1.03774倍外推、評估與存檔保持，情境約21.68–23.12分/輪。這是計畫估值，不是量測或保證：

- 36輪情境約9.21–9.50小時；若Base各12、Large16共40輪約10.65–11.04小時。
- 全90輪情境約23.02–23.74小時，另加初始化／排程／可能異常；不把24小時當硬停止政策。
- Base正式配置／保留峰值3.770/3.832GiB；Large2既有短預檢6.747/6.877GiB，非完整run顯存保證。無電價／雲端單價，不編造金額，不先做成本benchmark。

啟動前核對新核定範圍、當下本輪程序／資源／排程與輸出鎖，沿用原啟動前Commit≥8GiB、GPU≤10%、空閒顯存≥6500MiB、磁碟≥10GiB及程序衝突政策；這些只准入，不新增執行中資源強停。沿用既有micro2實際累積／backward／optimizer狀態分配／backbone更新預檢與Resume2序列化驗收，不重測；只對新版本准入、Seed／設定／輸出／預算派送補CPU必要檢查。若軟硬體／程式已改到舊證據不適用，先保存差異及缺口，不自行加GPU測試或換配置。

每run正式前回報模型、資料、Seed、Max／Min、Batch、LR、選模及已核定預算。啟用真實持續更新的`results/v2_scale512_followup_20261026_v1/MONITOR.md`（每15秒），列最後更新時間／candidate／Seed／runID／狀態／完整與最佳Epoch／即時批次／分段耗時與顯存；初期未生成者標pending。保存完整實際命令、有效配置、版本／來源身分、run_inputs、result、metrics、attempt／budget、初始化、best及雙代Checkpoint。不要重用已消耗的舊LAUNCH_ONCE／token，也不要將以下草案描述成已存在的可啟動入口。

## 事前判讀及停止規則

**Base是可重現性確認，不是看到Seed2不好便取消Seed3。** 三Seed全部完成後，由D比較各自原Tiny512同Seed，算mean／sample SD(ddof1)及配對差；Seed1用舊Base結果。若執行前使用者核定本提案，將歷史alpha025契約的數值條款原值複製成新Base前瞻契約，來源／用途分開保存：

- Robust平均Δ≥+1pp、至少2/3 Seed嚴格提升、每SeedΔ≥−1pp。
- 平均Accuracy／Macro-F1／BCN BA不得降，HAM／PAD BA各不得低於−1pp。
- 三來源NV平均Δ均≥0，HAM／BCN至少一個嚴格>0。
- BCN DF/BKL/MEL/VASC平均Δ各≥−3pp，合併MEL平均Δ≥−1pp；其餘12個有支持疾病按舊完整清單各≥−5pp。ALL且三Seed齊全，無四捨五入放行。

這是新Base候選待核定的前瞻採納條件，**不是原scale單Seed已預註冊同一契約、不是把n1套成n3失敗、也不改舊alpha不採納。** 本輪Base Seed1 MEL−7.9051pp只是警訊；若要三Seed平均≥−1pp，Seed2/3同SeedMEL收益平均須至少+2.4526pp。未通過則保留局部收益、候選不採納，不能改指標／門檻或追加救援訓練。即使全過，仍交總控確認，不自動更換網站。

**Large2為單Seed配置診斷，不能正式採納。** 固定主要差為新Large2−原Large1 Seed1，不比較最後輪、不重選舊epoch；輔助列與Base1同micro2、Tiny1差。事前實用訊號讀法（屬新提案，不追改舊門檻）：若Robust≥+1pp、Accuracy／Macro-F1不降、合併MEL不低於−1pp且無新增超出上述來源／疾病保護幅度的損失，記為支持micro配置值得進一步驗證；不等同n3採納。若Robust≤0pp，否定「僅改2×32足以提升本Seed Robust」；介於0與1pp或收益伴隨保護損失，列小收益／取捨或未定，不宣稱修復。若新Large仍低於Base同micro2，這組對照下「全因micro1」的充分解釋不成立；仍非純架構結論。無論好壞，本批結案後不自動補Large2/3。

上述Large診斷的「保護幅度」明定為新Large2減舊Large1的單Seed差：BCN BA≥0、HAM/PAD BA各≥−1pp、三來源NV各≥0、BCN DF/BKL/MEL/VASC各≥−3pp、舊清單其餘12疾病各≥−5pp；另有合併MEL≥−1pp及Accuracy／Macro-F1≥0。此處不要求NV OR嚴格改善，也沒有n3 Seed計數／SD；完整數值與是否有代價一併交D，不將通過這個診斷訊號稱為通過舊31條件。

這些是本單Seed實用配置對照的操作性支持／反證，不是總體統計／因果否定；同Seed也未完全控制驅動環境與隨機軌跡，結果不單獨歸因MixUp。

正常停止按原Min12／Max30／Patience5／STOP完整Epoch邊界；CUDA/OOM／非有限值、Checkpoint存檔或契約失敗、程序異常按既有流程保存並停止本批，不自動重試、Resume、改batch／配方／降資料或跳過故障繼續。保留最後已提交輪與attempt實耗，未提交輪不算完整；如要恢復，另核對同Run剩餘預算並取得新授權。只記錄執行中資源，不新增RAM／Commit kill，不中斷F CPU服務。

## 完成交付

保存新FINAL_RESULTS、B_HANDOFF及B README：三job完成／未完成、runID、最佳／停止輪、完整指標與全來源疾病TP/N/Recall、實耗／顯存、計帳包含關係、失敗及恢復限制、Test false。Large2計畫估值要由其實際輪時間取代，不先重測成本。正式模型判讀交B→總控→D；共用索引由總控追加。B不自行聯絡其他Thread、不自行改網站、不自動展開新候選。任務完成或異常結案後停止。
