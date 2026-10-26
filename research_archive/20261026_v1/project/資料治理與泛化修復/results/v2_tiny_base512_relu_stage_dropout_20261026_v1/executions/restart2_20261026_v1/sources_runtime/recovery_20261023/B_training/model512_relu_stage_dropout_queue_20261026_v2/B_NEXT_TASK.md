# B：目前整批正常完成後，接續 Tiny512／Base512 ReLU＋Stage Dropout 各三Seed

版本：model512_relu_stage_dropout_queue_20261026_v2。
工作目錄：D:\SkinDetect_base。
狀態：使用者已要求目前訓練完接續修改，授權總控延後直接交B；使用者指定Seed1～3，模型交由總控依現有Tiny/Base證據推薦。使用者最新追加「那tiny跟base都各跑seed1~3好了」，因此本方案更新為Tiny512與Base512各Seed1～3；取代先前只有Tiny的排程。p=.1沿用前述明示方案。這是新研究批次，最多6個新run／180完整Epoch，無時間硬上限；不挪用舊批預算。總控已向使用者回報選擇Tiny及理由。

## 啟動時機與禁止重複

只有總控在確認目前 v2_scale512_followup_20261026_v1 整批正常完成後，以本版本識別正式交辦，才準備／啟動本批。等待期間不改共用程式、資料、模型、配置或現在控制器，不插入／取代尚待執行的Large，不建第二個GPU輪詢或啟動程序。

先讀AGENTS.md、docs/PROJECT_STATE.md、docs/V2_EXPERIMENT_HISTORY.md最新段落及本檔；唯讀核對舊批state.json status=completed、base_seed2／base_seed3／large_micro2_seed1均completed、FINAL_RESULTS.json與B_HANDOFF.md已交付、STOP／失敗紀錄狀態，且原controller／trainer已退出。不要只以B對話idle或Base三Seed完成判斷整批結束。若舊批failed／paused／異常停止，或新批已有啟動／結果／鎖檔，保存現況並停止，不重複啟動／覆寫／自動Resume。

## 模型、對照與唯一組合變更

- 固定單GPU順序：ConvNeXt V2-Tiny512 Seed1→2→3，再ConvNeXt V2-Base512 Seed1→2→3。每run獨立新run ID、新七類head、空optimizer；不因某Seed品質不佳取消後續Seed。
- 各自以原架構512同Seed為主對照，原結果直接引用，不重訓；Tiny用原resolution三Seed，Base用舊scale Seed1＋本批followup Seed2／3。不要把Tiny與Base之間的micro／MixUp差異當成純架構因果。
- Tiny基準配置：資料治理與泛化修復/configs/v2_resolution_20261021_v1/v2in_res512.json。Base基準配置：資料治理與泛化修復/configs/v2_scale512_followup_20261026_v1/v2in_scale512_base_confirm.json及舊scale同配方；沿既有契約／參考記錄定位正式結果，不全碟掃描。
- 只將Tiny的18個／Base的36個ConvNeXt V2 Block的GELU改成非inplace ReLU，GRN、LayerNorm、深度／寬度、卷積、殘差及head架構不變。
- 四個完整Stage的輸出後各加一個torch.nn.Dropout(p=0.1)，在下個Stage的downsample之前，第四個在原head global average pool之前；一般元素Dropout，不是Dropout2d／DropPath／head dropout，也不是每個Block後都加。train啟用，eval停用。原Block／head Dropout=.0、DropPath=.0保留，避免默默多加另一變因。
- 不加任何額外pooling、不換EfficientNet、不改AdamW、不改LR／alpha／Patience、不附加EMA／TTA／裁切或其他研究。
- 兩項同時更改，只能解釋為組合效果；不宣稱各自的獨立因果。

## 凍結的資料、預訓練與超參數

- governed_18979_20261018_v1；Train18919、原Monitor1500、Validation3611；七類順序AKIEC/BCC/BKL/DF/NV/VASC/MEL。原完整Train／Validation前處理，封存Test不讀。
- manifest SHA256：5c501ef3cb6c8a73b3a9395383d199212e070abfbc67c782fcfc010576243284。
- 原Tiny FCMAE ImageNet1K本機權重，source timm/convnextv2_tiny.fcmae_ft_in1k，revision 508caf1bc24fd02c69d15778b994e808670dbc28，SHA256 fdfb4edfa5abb3b4ea29ab17e6fae5c117dc6cc32ecfb1d0726a156f40a4c1a5。
- 原權重路徑：.venv-skindetect/hf_cache/hub/models--timm--convnextv2_tiny.fcmae_ft_in1k/snapshots/508caf1bc24fd02c69d15778b994e808670dbc28/model.safetensors（總控已確認存在，尚未本次重新hash）。不得下載／換revision／取舊七類best或last作初始化。strict核對除新七類head外的所有backbone鍵／形狀；無參數Dropout的插入不得造成權重名稱偏移而漏載。記錄ReLU改動不改權重形狀，但改變預訓練網路計算。
- Base沿其本機權重：source timm/convnextv2_base.fcmae_ft_in1k，revision 7b29800e499fdc06de5b612970f3384dc8d29ca5，SHA256 ec152f1e375edc2b3dfac7a81155a449b4c5cbb7c5cf0b9494838f6c87518d73；路徑weights/v2_scale512_seed1_20261025_v1/base/7b29800e499fdc06de5b612970f3384dc8d29ca5/model.safetensors。與Tiny相同，只載相容backbone，不換來源／不下載。
- Tiny micro batch8 × accumulation8＝effective64；Base micro batch2 × accumulation32＝effective64，各保留原配方。
- AdamW、LR1e-4、WD.05、LayerDecay1、LS.1、MixUp.2、RandomErasing.15、clip norm1、AMP、Workers4、prefetch4、persistent workers，均沿原實作。
- alpha.5、有放回抽樣、三來源各1/3期望份額。
- Min12／Max30、EarlyStopping Patience5、MinDelta0；Cosine Tmax30、eta_min1e-6；每輪完整評估，首次最高Validation Robust選best。
- 每模型Seed1～3全部完成，不因前兩個Seed數值不好取消第三個；最多6run／180完整Epoch；無時間硬上限，不利用省下輪數追加候選。

## 實作、必要驗證與當下資源

完成舊批後，沿共用trainer／CheckpointStore以最小版本化擴充處理新candidate准入、source snapshot、配置派送、預算與monitor；不要複製另一套trainer，不削弱舊候選契約。確認舊配置仍建原架構，不受新選項污染；在新candidate明確開啟ReLU與Stage Dropout，所有模型變更列入effective config／run_inputs與code snapshot。

只做本次架構／映射／准入／序列化必要CPU檢查，包括Tiny18個／Base36個ReLU、每模型4個指定Stage Dropout=.1、原GRN數及Stage深度、stage與head尺寸不變、eval無隨機Dropout、Checkpoint round trip及舊候選預設不變。已有適用驗證直接引用，不重做benchmark、全資料掃描或全面測試。允許每模型各一次本候選所需的最小單批GPU相容性前檢（Tiny8張、Base2張非Test真實影像，forward／backward／optimizer step，核對有限值與顯存；只暫存模型，不計正式Epoch、不作正式初始權重）；此不另開候選或成本測量，失敗保存並停止、不自動重試。正式6run各重新初始化，不接前檢狀態。

開訓前回報本檔模型、資料、Seed、Epoch、batch、LR與Robust規則；核對當下程序／GPU排程，沿原啟動前資源政策，不干擾F CPU API。不得新增已取消的執行中Commit／RAM強停或每批梯度新政策，不修改Windows／驅動／環境，不安裝下載。

CUDA、非有限值、Checkpoint／契約或程序異常：保存STOP、失敗與實耗後停止整批，不自動重試／Resume／換batch或配方。正常按原early stopping及Max30停止。

## 新版本與交付

新版本ID：v2_tiny_base512_relu_stage_dropout_20261026_v1；新candidate：v2in_tiny512_relu_stage_dropout、v2in_base512_relu_stage_dropout。
新配置：資料治理與泛化修復/configs/v2_tiny_base512_relu_stage_dropout_20261026_v1。
新結果：資料治理與泛化修復/results/v2_tiny_base512_relu_stage_dropout_20261026_v1。
B詳細交接：recovery_20261023/B_training/tiny_base512_relu_stage_dropout_20261026_v1。
以上若已有產物，先讀狀態，保留不覆寫／不重複啟動。

啟動前凍結比較契約：Tiny與Base分別以新三Seed對原架構512同Seed，Robust為主，保存Acc／MacroF1、各來源BA、所有支持來源疾病TP/N／Recall、三Seedmean／sampleSD與配對差值。保留既有保護條件作D後續判讀參考；本指令不擅自放寬或創造新的採納門檻，也不因完成而自動採納／換網站。不作顯著性或Test泛化宣稱。

每15秒更新真實MONITOR.md，主動提供路徑／最後更新時間、各Seed／run ID／狀態／完整及最佳Epoch、實耗與顯存。保存FINAL_RESULTS、B_HANDOFF、實際生效配置、完整命令、run_inputs／metrics、best及雙代Checkpoint、失敗／計帳證據與必要驗證。結案交B→總控→D，停止，不聯絡其他Thread。共用PROJECT_STATE／V2_HISTORY僅由總控追加。

本v2交辦是2026-10-26使用者最新擴充範圍；舊僅Tiny的queue v1保留歷史並已被取代，不得兩份分別開訓。只有同一個接續排程，沒有額外Large新候選。
