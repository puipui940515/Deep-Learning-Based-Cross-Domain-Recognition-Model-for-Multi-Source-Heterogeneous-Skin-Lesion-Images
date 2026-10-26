# D 靜態實作／有效契約診斷｜2026-10-25

範圍：alpha025 retry1三Seed對原512；只讀既有B/C驗收、run_inputs、source文字及既有抽樣期望。非模型重新驗收，不讀PT、不import torch、不推論／GPU／Train/Test影像，不重跑29run稽核。此處不重算主品質值。

## 結論

**沒有找到足以解釋低Robust的已確認初始化／head／Optimizer／標籤映射實作錯誤。** 新候選的alpha改變在實際契約中生效，且程式與保存source hash相符。最有力的可驗證方向是抽樣曝光與來源泛化／前處理的交互，而不是假設預訓練沒有載入。兩者仍不能由本靜態檢查定因果。

**重要的新診斷限制：現存train_validation_gap不是同來源Train–Val gap。** 它將全來源合併1500張Train monitor BA減各來源Val BA；不能單憑該欄把BCN差距歸因過擬合，需日後一個同來源／同類別、同無增強前處理的有界評估來判別（本輪不執行）。

## 已確認／可排除到何種程度

|疑點|現存證據與定位|結論與限制|
|---|---|---|
|載入錯模型或預訓練根本未載|model_profiles.py:76–111：建立7類真V2Tiny，GRN18／stage[3,3,9,3]檢查；ImageNet路徑只去除head.fc.weight/bias，missing只能為這兩key；預訓練身分沿用B closeout|B已記錄三Seedbackbone/head身分、空Optimizer全true；沒有載錯／從舊best續訓的證據。靜態程式與收據不等於本輪獨立讀encoder張量驗證|
|head沒有重建或被固定|new run_inputs的initial_classifier_sha256；B CLOSEOUT_CHECKS已有對原512同Seed head hash相同，initial_optimizer_state_entries=0；optimizer names有head.fc.weight/bias|同Seed新初始化策略與原512一致，head在Optimizer中；不宣稱已量測每參數實際梯度／更新量|
|backbone被意外凍結／未納入Optimizer|stage2/models.py:29–55只略過requires_grad=False者；run_inputs三Seed每個都有200個唯一參數tensor名稱、18groups，stem/stages0–3/head均在，無重複名字；未見freeze指令|不支持「只有head訓練／整個stage遺漏」；200是已保存tensor名稱數，不是numel，更不證明各tensor每step更新皆非零|
|AdamW/LR錯用預設1e-3|model_profiles.py:151–168使用帶lr的parameter groups；run_inputs每group initial_lr=1e-4，WD0/.05；head.fc.weight=.05、bias0；Cosine T_max取30|全層同1e-4是LayerDecay1.0的預期，不是忽略layer decay。主訓練紀錄的逐輪learning_rates由父分析處理，不在此重演|
|新候選誤改多個科學因素|C STATIC_QA／DIFF_AND_SOURCES、B CLOSEOUT_CHECKS的scientific_training_diff只alpha .5→.25；B三Seed effective config、transforms、版本、資料身分true|沿用既有B核對，不重跑；新run來源10個小型程式SHA本輪只核對與保存值相同，沒有大型模型hash|
|label順序／PAD無樣本類別|load_governed_release trainer:52–106檢查label_name/canonical等於class_names[label]、來源supported labels、Train/Val split等；supported_source_metrics:197–214重算BA只取supported|沒有類別整體錯位或把PAD無DF/VASC當零進Robust的證據；原始醫學標籤本身是否正確不是程式身分檢查能證明，本輪未逐圖專業審核|
|Macro-F1和Robust方向不同是算錯|v2_opt_contract.py:180–211的best_metrics先合併三來源矩陣再算全體Macro-F1/Accuracy；trainer:618–620計Robust為來源BA平均與最低來源|分母／加權不同，方向可不同。主結果應保留兩者而非改主指標；沒有新計分重算|
|ImageNet Normalize不符|trainer:110–134的mean/std與timm models/convnext.py:724–733 _cfgv2之IMAGENET_DEFAULT_MEAN/STD一致|不是漏Normalize／用.5 Normalize。timm預設驗證是bicubic及crop_pct .875，而本專案選擇bilinear方形Resize；這是已知自訂前處理差異、非已證明bug，且Train/Val採各自既定流程；需圖像／有界實際評估才知道影響|

## 抽樣曝光：直接引用既有SAMPLING_EXPOSURE，未重算

來源configs/v2_512_alpha025_20261024_v1/SAMPLING_EXPOSURE.json。每Epoch18919次有放回，期望來源均1/3；下表為期望抽取次數，不是實際每Epoch計數或影像覆蓋率。

|來源／類別|Train N|alpha .5期望|alpha .25期望|
|---|---:|---:|---:|
|HAM NV|4692|2439.28|3373.39|
|HAM DF|80|318.51|159.17|
|HAM VASC|98|352.53|185.34|
|HAM MEL|779|993.92|877.41|
|BCN NV|3514|1601.00|1902.98|
|BCN DF|91|257.64|122.85|
|BCN VASC|90|256.22|121.83|
|BCN MEL|2519|1355.52|1482.53|
|BCN BKL|943|829.37|709.52|
|BCN AKIEC|616|670.32|515.55|
|PAD NV|195|1045.57|886.85|
|PAD MEL|41|479.43|275.37|

由此能確認alpha025不是單純「少數類曝光不變、只多看NV」：它明顯削減BCN DF/VASC等的期望曝光，同時增加BCN NV/MEL。實際品質是否與之同向要用父報告的配對Recall與錯分結果，不由期望曝光推定個別病例／因果。PAD NV並非大類、期望反而下降；不能把三來源NV結果都機械歸因為曝光增加。

WeightedRandomSampler本身無每Epoch完整覆蓋保證；sampling_audit的unique_samples=18919指訓練池大小，不代表每Epoch真看了18919個不同個案。B沒有保存每Epoch實際抽樣個案清單，因此本輪不能證明特定病灶從未曝光或重複記憶；這是明確量測缺口，不是已確認根因。

## Train monitor／Loss與前處理語意

- trainer:409 `stratified_limit(train_rows,1500,seed+3)`固定Train monitor，全來源／類別輪流抽取；trainer:463使用無增強Validation transform且shuffle=False。
- trainer:535 criterion帶LabelSmoothing .1；train_epoch:234以model.train＋隨機增強＋MixUp .2訓練，trainer:614 monitor則model.eval、無MixUp／無隨機增強。因此train_loss與monitor/Val loss不是同條件，不以差值直接證明過／欠擬合。
- monitor與Val雖都同LabelSmoothing criterion／無增強／eval，來源與類別組成仍不同。trainer:623 `gaps={source: monitor['balanced_accuracy'] - item['balanced_accuracy']}`是混合Train monitor減單來源Val；**不能當matched BCN Train-Val落差**。
- stronger_train_augment與Val square resize之間存在可干預的視圖落差，RandomResizedCrop只保證裁切面積70–100%，不保證保留病灶；沒有mask不宣稱病灶裁切率／IoU。Rotation/Jitter/Blur/Erasing同時作用的品質影響尚未定量，需父工作中的有限圖像視圖與日後有界模型診斷；RE0已淘汰不能據此說全增強都已證明合適。

## 最小未解實作問題

沒有逐tensor梯度／更新範數或matched source Train-Val既有報告。若後續B做診斷，優先沿用原512 best權重，用固定同來源同類別Train與Validation子集、相同無增強前處理取得matched分層指標，再對同圖核定訓練視圖做一次有界對照，才能區分表徵／來源落差與增強視圖破壞；具體唯一B任務由父D統整，不在本子工作另起實驗。若matched Train BCN也低，不能再把BCN差距簡稱泛化／過擬合；若Train高Val低而視圖差小，則單靠改增強缺乏優先證據。

## 產物、命令與限制

EVIDENCE.json保存三Seed原契約、Optimizer group摘要、B核對直接引用、10個小型source identity與精確行號。inspect_static.py僅Python標準函式庫文字/JSON/hashlib，不import torch／專案程式。

執行：工作目錄D:/SkinDetect_base；`tools/Python312/python.exe -B -X utf8 recovery_20261023/D_v2_analysis/root_cause_20261025_v1/static_audit/inspect_static.py`。前期一個預想contract檔名不存在，改讀run_inputs中實際v2_alpha025_contract.py，沒有重建原檔；兩次只讀PowerShell foreach管線語法不合後修正，沒有研究程序執行。

僅本static_audit目錄新增檔案；沒有修改共用入口／原配置／權重／Checkpoint或B/C結果。無GPU／模型載入／推論／訓練／影像／Test／安裝／下載，完成後停止。
