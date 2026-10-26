# SkinDetect訓練現況 方法結果與問題總整理

版本：20261026_v1。整理者：總控Work。截點：**2026-10-26T03:35:25+08:00（臺北）**。
本批狀態檔最後更新：**2026-10-26T03:35:23+08:00（臺北）**。本檔是固定截點報告，不是自動更新監控表。

這份紀錄回答目前訓練到哪裡、已經試過什麼、數值為什麼沒有持續上升、哪些是真正故障，以及下一輪正在驗證什麼。內容引用已保存的正式結果、D分析與B交接；未重新訓練、推論、載入模型或讀取封存Test。歷史資料缺件、單Seed、不同資料版本及中斷恢復限制均保留，不把假說寫成根因。

## 一 先看目前結論

1. **訓練流程已能正常運作，研究尚未達到可結案採納的程度。** 七類資料、預訓練、GPU實際運算、正式存檔及必要恢復已有相應證據；但跨來源與各疾病的泛化、Seed穩定性仍是實質難點。
2. **已結案的現行六批研究合計34個獨立正式run、529個完整Epoch。** 正常Early Stopping算完成；中斷後Resume同Run不重算獨立run，未提交輪不算完整Epoch。8月／9月的舊資料版本、煙霧測試、診斷前向與本批進行中輪數不混入這個總數。
3. **目前完成run中的最高單模型Validation Robust是Base512 Seed1的69.2906%。** 這只是單Seed的最佳輪，不是三Seed平均、獨立Test或新來源品質保證，也沒有因此換網站模型。
4. **最高分有代價。** 同Seed1，Base相對Tiny512 Robust提高2.1424pp，但合併MEL Recall由59.6838%降至51.7787%，少判對40/506張MEL。總分提高不能直接當作疾病表現全面改善。
5. **Large不只是全面變差。** Large512 1×64的Robust67.7141%低於Base，但合併MEL Recall64.4269%高於Base；它較慢且有其他疾病損失，需按品質與成本一起判斷。
6. **目前唯一已核定後續批次在執行。** 順序為Base Seed2、Base Seed3、Large Seed1 2×32；不得因前一個Seed分數不好取消後一個，也不因節省輪數再追加候選。
7. **Robust80%仍是研究目標，沒有已驗證能保證達成的配方。** 舊文件的HAM單來源BA80%以上、全體Accuracy80%以上，不能當作目前三來源Robust已達80%。

## 二 現在實際跑到哪裡

本批版本：`v2_scale512_followup_20261026_v1`；狀態：`running`。

|工作|Seed|截點狀態|完整Epoch|最佳Epoch|暫存最佳Robust %|Run ID|
|---|---|---|---:|---:|---:|---|
|base_seed2|2|running|9|6|65.2202|5e4892aab71a4cdab15858051da413f2|
|base_seed3|3|pending|0|N/A|N/A|尚未建立|
|large_micro2_seed1|1|pending|0|N/A|N/A|尚未建立|

表中的running／pending依B原狀態保存；**進行中最佳分數不可拿來作正式淘汰／採納或三Seed結論**。未建立Run ID的工作不得提前填成完成。主動觀察不改變原停止規則或授權。

真正即時表：[每15秒更新的MONITOR.md](<資料治理與泛化修復/results/v2_scale512_followup_20261026_v1/MONITOR.md>)。報告附件保存當時MONITOR副本及state必要欄位，之後的進度請以即時表為準。B對話顯示idle不等於外部訓練停止。

### 已完成批次的工作量

|研究批次|完成獨立run數|完整Epoch總數|
|---|---:|---:|
|五組正式基線|15|276|
|第一輪配方篩選|4|51|
|第二輪配方篩選|4|49|
|320／512解析度|6|80|
|512 alpha025|3|45|
|Base／Large初篩|2|28|
|合計|34|529|

320／512列只算新增六run，224基線已在五組基線中計數，不能再加一次。本次追加批次最多三新run／90完整Epoch，未完成者與上述合計分列。

## 三 研究任務與正式資料

### 任務範圍

人類皮膚病灶影像七分類，固定順序為AKIEC／BCC／BKL／DF／NV／VASC／MEL。這不是一般正常皮膚、任意皮膚病、身體部位或病灶分割模型；沒有相容真值時不能自行報正確率。正常皮膚與七類外資料擴充目前暫緩，不是本輪新候選。

|類別|本專案名稱|
|---|---|
|AKIEC|光化性角化症／表皮內癌家族|
|BCC|基底細胞癌|
|BKL|良性角化病灶家族|
|DF|皮膚纖維瘤|
|NV|黑色素細胞痣|
|VASC|血管性病灶|
|MEL|黑色素瘤|

### 實際使用的governed release

資料版本：`governed_18979_20261018_v1`。版本名稱保留歷史18979字樣，**實際Train是18919**，不能從目錄名稱推定數量。

|來源|Train|Validation|用途／限制|
|---|---:|---:|---|
|HAM10000|7007|1504|七類；封存Test另有1502，未開封|
|BCN20000|10221|1712|七類；為目前主要弱來源|
|PAD-UFES-20|1691|395|僅支持AKIEC／BCC／BKL／NV／MEL|
|合計|18919|3611|原Monitor1500另從Train固定監測，不是新增獨立資料|

HAM／BCN為皮膚鏡來源，PAD為手機臨床影像來源，來源差異不能自動當作標註錯誤。PAD沒有DF／VASC支持樣本，相關Recall記N/A，不補0拖低BA。

Manifest SHA256：`5c501ef3cb6c8a73b3a9395383d199212e070abfbc67c782fcfc010576243284`。實際入口以`--manifest-release`、run_inputs與發布契約為準，舊config中的歷史manifest字串不取代它。Test統計僅引用既有摘要，未讀取成員或標籤作研究。

### 抽樣不等於每輪完整看過每張圖

目前三來源期望各占1/3，來源內以class_balance_alpha=.5平滑類別抽樣，使用有放回抽樣。每輪抽樣數18919不保證每張Train都被抽到；期望曝光次數不等於實際不同病灶覆蓋率。不能因一輪抽了18919次，就寫成所有原圖各學一次。

## 四 指標與選模方式

**主指標Robust = 0.5 × 三來源Balanced Accuracy平均 + 0.5 × 最低來源Balanced Accuracy。**

BA是同來源有支持類別的Recall平均；Accuracy看合併後所有圖片正確比例；Macro-F1由三來源合併混淆矩陣計算，兼顧precision與recall，不能用三個來源F1直接平均冒充。

在目前已核對、BCN一直最低的區間：`Robust = (HAM BA + PAD BA + 4×BCN BA) / 6`。因此BCN BA升降1pp，Robust局部變動約0.6667pp；HAM或PAD單獨變動1pp則約0.1667pp。最低來源改變時必須重算，不可無限外推。

這就是「Accuracy升、Robust卻跌」可以同時發生的原因：更多圖片分對，尤其樣本很多的類別變好，並不保證最弱來源的各類Recall也變好。

每Seed以**第一次達到最高Validation Robust**的完整輪保存best。最後輪不等於最佳輪；最佳輪可以早於Min12。Min12限制何時能停止，不是限制從第12輪才開始挑best。研究反覆查看同一Validation有選擇偏差，不能把它當一次獨立最終測試。

## 五 目前主線實際訓練配置

|項目|現行Tiny512對照／Base與Large主線設定|
|---|---|
|架構|官方ConvNeXt V2系列，透過既有套件及共用trainer使用|
|初始化|本機釘選FCMAE ImageNet1K預訓練權重；新七類head；新實驗空optimizer|
|權重來源|Tiny：timm/convnextv2_tiny.fcmae_ft_in1k；Base／Large相同fcmae_ft_in1k類型|
|Tiny revision|508caf1bc24fd02c69d15778b994e808670dbc28|
|Base revision|7b29800e499fdc06de5b612970f3384dc8d29ca5|
|Large revision|774e71d83a0870798b626b0723ce0b6c08746b1b|
|輸入|512 RGB，原完整Train增強與Validation前處理|
|有效Batch|64；Tiny512 8×8，Base2×32，舊Large1×64，新Large2×32|
|LR／Optimizer|初始LR1e-4、AdamW、Weight Decay .05、Layer Decay1.0；原參數分組規則|
|正則化|Label Smoothing .1、MixUp .2、RandomErasing .15、clip norm1|
|精度／載入|AMP；Workers4、prefetch4、persistent workers|
|排程|Cosine Tmax30，eta_min1e-6|
|停止|Min12／Max30、Patience5、MinDelta0；原STOP與整輪非有限／Checkpoint保護|
|時限|目前核定批次無wall-clock硬上限，但仍有run／Epoch數上限|

模型結構與預訓練權重來自官方／公開發布，以上訓練配方是本專案設定，並非每個大小各自調到最佳的官方配方。更換模型時不能接續舊best冒充同一初始化；Resume則相反，必須恢復完整訓練狀態，不能只載best模型。

最近B記錄環境：Windows、RTX5070約12GB專用顯存；D槽Python3.12.10、torch2.11.0+cu128、torchvision0.26.0+cu128、timm1.0.30。驅動重裝後616.92；此為既有B／總控紀錄，本次沒有重新安裝、跑pip check或CUDA測試。

## 六 已經嘗試的方法與結果

### 6.1 五組正式基線與預訓練

這是五個實驗組合，不是五種完全不同的模型架構。各組完整三Seed、共15run／276Epoch。

|模型／初始化|平均Robust % ± 樣本SD pp|判讀|
|---|---|---|
|MLP Random|32.1137 ± 0.8510|像素MLP參考基線|
|ResNet18 Random|48.5391 ± 2.7190|不載預訓練的卷積基線|
|ResNet18 ImageNet|57.3281 ± 2.0396|同架構預訓練明顯有幫助|
|ConvNeXt V2-Tiny Random|44.5802 ± 1.6092|不能聲稱V2架構不論初始化都更強|
|ConvNeXt V2-Tiny ImageNet|64.4987 ± 1.5979|本輪完整配置中最佳主線|

同架構ImageNet−Random平均Robust：ResNet約+8.7890pp，V2約+19.9185pp。MLP、ResNet、V2的解析度、LR、有效Batch、增強與其他配方不同，不能把跨架構差異全說成架構因果。15個基線best的BCN均為最低來源。

### 6.2 第一輪單變因配方篩選

兩候選各自從原224 ImageNet配置出發，不把兩個變更疊加。只完成Seed1／2篩選，未通過後按原規則不跑Seed3，共4run／51Epoch。

|候選|唯一改動|n=2平均Robust %|相對同Seed原基線ΔRobust pp|結論|
|---|---|---:|---:|---|
|LR5e-5|LR1e-4→5e-5|64.7667|-0.3642|不採納|
|LD.9|Layer Decay1.0→.9|64.1814|-0.9495|不採納|

正確配對基線是Seed1／2均值65.1309%，不是完整三Seed64.4987%。不能用不同Seed分母製造提升。LR候選BCN及F1下滑；LD候選BCN下降、部分Seed與疾病保護未過，PAD局部收益不足以通過全條件。這些run本身正常完成，不是程序失敗。

### 6.3 第二輪單變因配方篩選

共4run／49Epoch，仍各只完成Seed1／2篩選，Seed3依規則不執行。

|候選|改動|n=2平均Robust %|同SeedΔRobust pp|結論|
|---|---|---:|---:|---|
|BCN50|HAM／BCN／PAD期望份額改.25／.50／.25|64.6067|-0.5243|不採納|
|RE0|只將RandomErasing.p改0|63.4256|-1.7053|不採納|

BCN50未修復BCN瓶頸，RE0亦未改善主指標；兩者BCN VASC平均Recall均下降約9.5238pp，RE0另有DF損失。不能因此說所有抽樣或增強研究永遠無效，只能說這幾個精確配置未通過原門檻。較長Patience8曾被提出，但沒有已完成正式實驗，不列為成功／失敗結果。

### 6.4 224三Seed逐張錯誤與固定等權Ensemble

歷史上曾完成三Seed各3611張Validation預測與跨Seed錯誤分析；本次只沿用已保存索引與可讀摘要，不重新推論。

- 三Seed皆對2287張（63.33%）；部分錯884張（24.48%）；三Seed全錯440張（12.18%）。
- 全錯中297張三者同一錯誤類別、143張皆錯但去向不同；這是原224三Seed結果，不代表新Base／Large也有相同病例。
- 曾整理26張代表清單，後續D有30張人工觀察記錄；部分原始分析輸出未在現有來源找到，不用摘要重造原措辭或逐圖分數。

固定Ensemble採三模型softmax機率等權平均，沒有搜尋子集、權重或閾值。它是一個固定系統的一次Validation結果：

|Accuracy %|Macro-F1 %|Robust %|HAM BA %|BCN BA %|PAD BA %|
|---:|---:|---:|---:|---:|---:|
|78.6486|71.4591|66.9218|75.6654|62.9338|74.1298|

比各原224 Seed的Robust都高，但有疾病得失。BCN MEL→NV89張，比Seed1／2少、卻比Seed3多16張；297張一致錯誤仍全錯，143張去向不同全錯只救回1張。不能把等權Ensemble當成能修復共同盲點的保證，也不能報三次獨立Ensemble的SD。

### 6.5 解析度224／320／512

224直接引用基線三Seed；新增320及512各三Seed、共6run／80Epoch。沒有這組已完成的128解析度三Seed；舊文件的128有時是驗收樣本數，不能當成第四種正式尺寸。

|解析度|n|平均Robust % ± SD pp|平均Accuracy %|平均Macro-F1 %|HAM BA %|BCN BA %|PAD BA %|
|---|---:|---:|---:|---:|---:|---:|---:|
|224|3|64.4987 ± 1.5979|76.0639|68.3159|73.3011|60.8373|70.3417|
|320|3|65.6747 ± 1.4523|76.3039|70.7296|77.9580|61.4485|70.2962|
|512|3|67.2195 ± 0.0959|76.2854|70.3251|77.8843|62.9780|73.5204|

512比320的平均Robust+1.5448pp，但Macro-F1−0.4045pp；BCN DF／VASC／NV Recall亦下降。512相對224的Robust+2.7208pp，仍不是所有來源疾病全面改善。224／320使用32×2，512使用8×8，MixUp配對池與運算條件不同，不宣稱純解析度因果。

選512作後續研究的理由，是在實際目標尺寸驗證假說、避免低尺寸篩選排名未證明可轉移又增加額外run；224／320仍是有效對照與網站部署參考，並沒有被刪掉或宣告無用。320／512新Ensemble、原四模式30張成本比較，沒有在本報告來源內找到完成收據；不能把其他GPU小測或342圖診斷當成它們已完成。

### 6.6 512降低來源內類別平衡alpha

唯一科學變因class_balance_alpha .5→.25；三Seed從同類預訓練各自新初始化，不接舊best。3run／45Epoch，完成輪數13／20／12，最佳輪8／15／5，正常Early Stopping。

|指標|原Tiny512三Seed均值 %|alpha025三Seed均值 %|差值pp|
|---|---:|---:|---:|
|Robust|67.2195|66.3112|-0.9083|
|Accuracy|76.2854|78.1409|+1.8554|
|Macro-F1|70.3251|71.3678|+1.0427|
|HAM BA|77.8843|78.4477|+0.5634|
|BCN BA|62.9780|61.4010|-1.5770|
|PAD BA|73.5204|73.8154|+0.2950|

三Seed Robust都沒有提升，原31原子條件有7項未過，**正常完成、不採納**。主要代價：BCN BKL Recall58.3794→43.2781%，下降15.1013pp，單項對Robust約−1.4382pp，超過BCN NV／MEL收益；PAD BKL亦下降12.7273pp。這個結果支持改抽樣存在疾病取捨，不是程式訓練失敗或單純需要再多跑幾輪。

成功execution耗時16968.875秒、約4.71小時；第一次未完成首輪的24.779秒另列，不重複加總。原實驗已結案，不自動再調alpha。

### 6.7 Base／Large／Huge模型大小初篩

Tiny只用原512 Seed1作同Seed對照；Base與Large各完成一個新Seed1。兩者均原FCMAE ImageNet1K初始化，其他核定主配方保留，但微批不同。

|模型|微批×累積|最佳／完成Epoch|Robust %|Accuracy %|Macro-F1 %|合併MEL Recall %|
|---|---|---|---:|---:|---:|---:|
|Tiny512 Seed1|8×8|4/12|67.1483|78.5378|72.1627|59.6838|
|Base512 Seed1|2×32|6/12|69.2906|80.2271|74.2208|51.7787|
|Large512 Seed1|1×64|11/16|67.7141|78.1224|72.6731|64.4269|

**Base的收益與代價：** BCN DF14→18/33、VASC13→17/21、NV552→598/682；但BCN BKL101→91/181、MEL197→172/328，HAM MEL101→85/167，PAD BKL39→34/55。Base對Tiny的Robust+2.1424pp幾乎由BCN淨收益貢獻，不能視為普遍疾病進步。

**Large的取捨：** 比Base的BCN BCC／NV／VASC／DF差，但BKL／MEL較好；HAM及BCN MEL分別119/167及203/328，合併326/506。Large仍有研究資訊，尚未證明成本值得或架構本質較差。

**Huge沒有訓練結果：** 七類模型約6.575億參數；原FP32參數、梯度與Adam兩moment約9.7974GiB，加既有foreach必要暫存下界約11.3996GiB，尚未含activation、AMP暫存及CUDA／桌面。當時可用顯存約10.8945GiB，因此按授權估算略過，沒有下載或硬跑，不能寫成Huge實測OOM或品質淘汰。

## 七 微批 累積 MixUp與速度

微批×累積是本專案訓練配置，不是模型層數。8×8、4×16、2×32、1×64都是名目有效Batch64；前者一次送幾張，後者累積幾個微批再更新權重。

**梯度累積主要解決顯存容量，不保證加速。** 有效Batch相同，也不保證完全相同訓練軌跡：MixUp配對池、隨機序列與末組處理不同。

### 已完成的必要預檢

每候選各兩次實際有效Batch64更新，含backward／完整累積／AdamW狀態與backbone變更；下表為第二循環64張，僅短預檢，不是完整長期benchmark。本報告沒有重測。

|模型|微批×累積|張／秒|CUDA張量配置峰值GiB|
|---|---|---:|---:|
|Base|8×8|16.81|10.63|
|Base|4×16|21.82|6.07|
|Base|2×32|24.12|3.77|
|Base|1×64|21.67|2.64|
|Large|8×8|1.04|16.99|
|Large|4×16|13.63|10.17|
|Large|2×32|14.51|6.75|
|Large|1×64|15.06|5.07|

Large8×8實際完成更新，但極慢，配置峰值超過專用顯存容量；不能稱為實測OOM。Windows下CUDA配置峰值不等於純物理專用顯存占用，未量測共享RAM用量，不能直接說借用了多少RAM。顯存有空間不等於GPU仍有同比例算力可用，較大微批不必然較快。

### 已確認的MixUp差異

原程式在每個微批內randperm配對。微批1必然自己配自己，因此雖設定MixUp alpha .2，沒有實際跨圖片混合；梯度累積64次也不會自動把64張集中混合。微批2有1/2機會自身、1/2交換；微批8任一位置非自身的期望比例7/8。這是索引機會，不等於不同疾病的實際混合率。

因此新Large2×32的研究價值是改善這個已知配置差異並觀察得失，不是已證明會加速或必定提高Robust。它還同時改變累積／隨機過程，不能稱純MixUp因果實驗。

### 實際正式耗時

|模型／範圍|已提交完整Epoch總時間|非首輪中位每輪|正式attempt總時間|
|---|---:|---:|---:|
|Tiny512 Seed1（舊對照）|76.881分鐘|6.287分鐘|未在scale controller重建同邊界計帳|
|Base512 Seed1|147.718分鐘|12.181分鐘|147.920分鐘|
|Large512 Seed1|341.900分鐘|20.957分鐘|391.405分鐘|

Tiny原三Seed39輪的result.elapsed_seconds總14256.416秒，平均約6.09分鐘／輪；與上述單Seed非首輪中位數不同，不能當矛盾。早先以官方FLOPs推估Base21分鐘、Large47分鐘、Huge157分鐘／輪只是等效率粗估，Base／Large現在應優先用實測；Huge仍無實測，不能以推估宣稱可在12GB正常跑。

Base＋Large正式attempt總32359.476秒（8.989小時），包含初始化、失敗及成功Resume；完整已提交輪時間約29377.073秒。failed_attempt_seconds19365.831包含Large原先成功的13輪，不能全部叫浪費；Resume成功4118.443秒已在總額內，不再相加。資料等待、批次處理、Monitor、Validation、Checkpoint是輪內分項，也不能與總輪數時間再相加。

## 八 已做過的診斷與能支持的結論

### 8.1 Early Stopping與曲線

224／320六run共81輪的歷史停止邏輯核對未發現計數錯誤。最佳後有震盪或局部反彈，但最後都沒有超過已保存最佳；不能推定未觀測的更晚Epoch一定較好。Patience8只是歷史提案，沒有正式結果。

近期同Seed比較：Base Monitor BA93.76→97.94%，Robust69.29→64.48%；Large Monitor98.56→99.25%，Robust67.71→64.70%。這支持繼續擬合不會自動帶來Validation收益，但混合來源Monitor不能證明BCN每個疾病都已學好。含增強／MixUp的Train loss也不能與無增強的Validation loss當完全同條件比較。

### 8.2 16張有界影像檢查

D曾依metadata固定選16張非Test影像，查看原圖與512幾何處理示意，觀察來源構圖、毛髮、黑視野及觸邊等。部分BCN DF／VASC影像也清楚，不能由少量圖像宣稱全部太難、標錯或裁切就是根因。沒有病灶真值mask，裁切面積比例不是病灶保留率；不據此自動改增強開訓。

### 8.3 匹配來源×疾病Train／Validation診斷

固定原Tiny512 Seed1與alpha025 Seed1兩個best，HAM／BCN×六類×Train／Validation，按可得group每層7–16張，總342張非Test。兩模型各342筆預測，684次正式前向＋6暖機＝690次，75.453秒；未訓練。

|觀察|保存結果|可以說什麼|
|---|---|---|
|原Tiny BCN AKIEC|Train10/16（62.5%）、Val7/16（43.75%）|Train樣本本身亦不高，不能全歸因只在Val失效|
|原Tiny BCN MEL|Train8/16（50%）、Val7/16（43.75%）|同上|
|BCN DF兩模型|Train均9/10；Val原6/10、alpha5/10|有限支持Train高、Val低的泛化落差|
|alpha BCN AKIEC|Train13/16、Val8/16|小樣本有明顯落差|
|alpha BCN BKL|Train14/16、Val8/16|Train未降但Val下降的線索|
|HAM MEL／DF|亦有Train-Val落差|不能直接說是BCN專屬問題|

限制：只有Seed1、便利群組、不保證患者獨立、各層很小、兩權重最佳Epoch4／8不同。一張影響6.25–14.29pp；不能推成全Validation BA、正式Robust、三Seed顯著性或唯一根因。這份Tiny診斷不能直接當Base／Large的Train細類成績。

### 8.4 已查而未見明顯錯誤的項目

- 未找到預訓練根本沒載入、七類head沒重建、只更新head、漏整個stage、Optimizer誤用LR1e-3或類別整體錯位的證據。
- 來源支持類、PAD無樣本N/A、標籤映射及資料身分有既有契約檢查；不能因此保證每張醫學真值都正確。
- 原Normalize符合本任務選定ImageNet mean/std；官方參考bicubic／crop與本專案bilinear方形Resize有差異，尚未證明它是bug或可量化根因。
- 必要GPU預檢已有完整累積／AdamW分配及backbone更新證據，但不表示逐個參數更新量全部有獨立量測。

以上是有限排除與已保存證據，不等於已證明所有軟硬體與研究設計毫無問題。

## 九 真正遇到的程式 資源與恢復問題

|事件|已確認現象／原因|處理與目前狀態|與模型品質的關係|
|---|---|---|---|
|Windows重裝後路徑與環境|舊C槽輸出／部分session與附件缺失、環境重建|主要資產留D；沿用recovery Python／venv，原件與缺口保留|資料與成果管理問題，不等於模型訓練全失效|
|Commit／分頁檔不足|重裝後約5GiB分頁檔、Commit Limit約36.11GiB；部分正式啟動未完成首輪即停|使用者後續設定48GiB分頁檔；既有紀錄Commit Limit約79.11GiB|CPU虛擬記憶體限制；不能拿分頁檔補GPU專用顯存|
|新增強停政策不符使用者要求|alpha025最初新增執行中Commit／RAM4GiB強停，Seed1只跑24.779秒、無完整輪|使用者要求還原舊行為；保留啟動前資源檢查及原STOP／整輪非有限／Checkpoint保護|不是alpha品質淘汰；原零輪嘗試不能Resume|
|中文程序查詢編碼|程序列表曾UnicodeDecodeError|UTF-8相容性修復，不能把查詢錯誤視為無衝突|啟動／守護實作問題|
|診斷首次清單錯誤|Validation IDs是按來源dict，程式set(dict)只取得來源名|0.953秒、0前向停止；修正展平後另授權完成342圖診斷|不證明資料隔離真的失敗，也沒有品質結果|
|Large CUDA中斷|第14輪中CUDA unknown error，13輪已提交；使用者說當時重裝驅動|失敗紀錄保留，重新授權恢復；不能把重裝時間背景當唯一根因實證|不是正常Early Stopping；也不是已證明OOM|
|Large Resume1存檔錯誤|B包裝的實例方法進入scheduler state，不能序列化；第14輪未提交|移除實例方法覆寫、CPU微型完整存檔／載入核對後Resume2|已確認程式問題，與原CUDA錯誤分開|
|Large Resume2成功|同Run由13接14，model／optimizer／scheduler／scaler／RNG等恢復，14–16提交|16輪正常早停，最佳仍原11輪|最佳輪在中斷前，不能把原低分全怪恢復弄壞best|
|監控短暫仍running|錯誤後程序退出與controller更新有先後|需同時看日誌、真實程序與狀態；後已failed、最終Resume結案completed|不把舊畫面當仍在健康訓練|

原生persistent-worker內部RNG不保證中斷後逐位元重播，驅動環境也改變；成功恢復不等於已證明與不中斷軌跡完全相同。正式失敗需按當輪授權處理，不無限自動重試。這些問題與「新配方沒有改善」是不同層次。

## 十 研究上尚未解決的核心問題

|問題|目前證據|尚未證明／不能宣稱|
|---|---|---|
|BCN細類瓶頸|各基線BCN最低；DF／AKIEC／BKL／MEL長期偏弱|不能直接歸因全部標錯、圖片太難或某一模型壞掉|
|疾病間取捨|alpha改善NV卻傷BKL；Base總分升但MEL掉|不能用高Accuracy／Robust取代疾病保護|
|擬合與泛化脫鉤|混合Monitor很高、Validation持續震盪；匹配診斷部分Train也低|不是單一普遍欠擬合，也不能全部定性為同一原因的過擬合|
|Seed穩定性|Base最佳單輪69.29%，但單Seed；當前Seed2未完成|最高一次不等於三Seed可重現改善|
|資料來源／模態與樣本數|三來源影像形態不同，BCN DF33、VASC21、PAD MEL11|小樣本變動大，不等於臨床價值小或可忽略保護|
|評估反覆使用|多輪都看同一Validation選模|不能把多次追分當成獨立泛化證據|
|相容性與比較公平|架構、微批、MixUp與環境差異已記錄|名目Batch相同不等於所有學習條件完全隔離|

### Robust80%的距離

以原Tiny512三Seed為固定錨點，若BCN平均仍62.9780%，即使另外兩來源100%，Robust最多約75.3187%。反過來只將每Seed BCN提升到100%、其他來源各自原值不動，正確處理最低來源切換後平均約78.5656%。這些是固定其他條件的算術情境，**不是本專案或Base模型的絕對上限**。

示例HAM84%、BCN78%、PAD84%會得到Robust80%；它說明需要多來源／多疾病共同改善，並不保證某配方可達。單純換大模型、多跑Epoch、降低LR、增加某來源抽樣，都沒有現成保證。

## 十一 目前已核定後續批次與事前判讀規則

固定順序：Base512 Seed2 2×32 → Base512 Seed3 2×32 → Large512 Seed1 2×32。新run、新head、空optimizer；Base Seed1及Tiny三Seed引用既有結果，不重訓。每個新run按釘選預訓練權重重新初始化，不接原Large1的best／last。

最多3新run／90完整Epoch，正常最少36輪，異常可不足；無時間硬上限。40輪約10.65–11.04小時、90輪23.02–23.74小時是D事前估時，不是保證或強停線。實測估時隨MONITOR更新，不能拿節省輪數追加研究。

### Base三Seed候選

與原Tiny512同Seed配對，mean與sample SD（ddof1）均須列，不能只挑最好Seed。新契約要求完整三Seed、ALL條件通過才供採納判讀：

- 平均ΔRobust≥+1pp、至少2/3 Seed嚴格提升、每SeedΔRobust≥−1pp。
- Accuracy、Macro-F1、BCN BA平均不降；HAM／PAD BA各≥−1pp。
- 三來源NV平均不降，HAM／BCN至少一個嚴格提升。
- BCN DF／BKL／MEL／VASC各≥−3pp，合併MEL≥−1pp，其餘歷史12個支持疾病各≥−5pp。
- 不四捨五入放行、不因Seed2不好取消Seed3、不把此新契約追溯改寫舊scale／alpha025結案。

### Large2單Seed診斷

主比較新Large2×32減原Large1×64，輔助看Base同Seed2×32。ΔRobust≥+1pp且Accuracy／F1不降、合併MEL≥−1pp及事前來源／疾病保護全過，才記為值得進一步驗證；ΔRobust≤0則不支持只改這個配置足以改善此Seed。中間結果或伴隨損失列取捨／未定。

完整保護幅度見本批EVALUATION_CONTRACT.json。即使單Seed通過，也不是正式採納、純MixUp因果或自動補Large Seed2／3的授權。

### 本批實際停止與保存規則

正常按原Early Stopping或Max30停止。CUDA、整輪非有限值、Checkpoint／契約或程序異常則保存並停止本批；不自動重試、Resume、換batch或調配方。不新增訓練中Commit／RAM強停、不干擾F CPU服務。

保存有效配置、完整命令、run_inputs、逐輪metrics、best、雙代Checkpoint、失敗與計帳，交B→總控→D。C只在配置／契約專項需要時介入；E負責正式Word、F網站API、G簡報、H備份，不自行改研究結果。完成不代表換網站模型或開封Test。

## 十二 舊資料夾 缺件與報告限制

8月至9月的第一／二／三階段、部位預訓練、課程學習、NoiseFilter、四來源八類CP005、顯式影像特徵融合等，保存了研究背景、部分摘要／CSV與程式。它們與目前governed七類資料、ConvNeXt V2、Seed1/2/3及Robust目標未必相同，不計入上面的34正式run排名。

本次先前有限盤點發現：舊課程學習第一關未過、部位轉移未證明有益、顯式特徵融合只有smoke證據、十張熱力圖篩選不能取代完整Validation；補邊／來源捷徑稽核可作未來假說線索，但不因此更動現行批次。舊「混合V2」也不能只看名字就當現在的ConvNeXt V2同版本。

以下缺口仍須如實保留，使用者已表示可回收資料到此為止，不再把尋找舊附件設成所有工作的前置：

- 原C部分統計Word／Excel、完整逐張七類Validation與Ensemble分數表及部分圖表原件未在目前指定範圍找到。
- 舊D30張逐圖觀察全文、部分完整診斷與原規格有來源缺口；索引摘要不是原文復原。
- 原B五份分析程式轉錄ZIP與C四份草稿已保全；OCR／轉錄不等於原始位元組或可直接執行的完整程式，不能覆蓋正式trainer。
- 正式訓練結果與權重、各run混淆矩陣仍可用；混淆矩陣不能反推每張圖片機率。重匯出逐圖分數需要另核定推論，不能為補報告自行重跑。
- 舊README若指向目前不存在的results路徑，只能記為原位未找到；實驗紀錄庫／圖表庫尚有部分摘要，沒有由本次證明全磁碟永久遺失。

這份現況稿另存D槽並複製到使用者指定OneDrive本機md資料夾。正式學校Word由E維護；D槽v4已存在結構QA，但本次讀取final_qa仍為visual_pending，因此不在這份報告中宣稱它已完成逐頁視覺驗收／雙份最終交付。

## 十三 系統展示與研究訓練的界線

F既有網頁／API使用原224 Seed1／固定E224，CPU真實上傳與回傳功能已有驗收，不代表模型病灶辨識品質有新增驗證。Base69.29%不代表網站已換Base；GPU API端到端、Docker、私人遠端部署及Grad-CAM以各自正式收據為準，不由本訓練報告推定完成。

醫療原圖、逐圖私人metadata、Checkpoint、大型權重或憑證不得因整理報告自行推公開GitHub。H首次push與完整備份仍按使用者授權與審閱流程，這次沒有雲端上傳或Git操作。

## 十四 從現在開始的具體下一步

1. 讓本批已核定三個run依序執行，透過既有MONITOR看進度；不額外測GPU、不重跑已完成預檢、不因中途分數改配方。
2. 若正常完成，B交完整結果與收據；總控核對狀態及產物後交D作三SeedBase配對與Large2單Seed診斷。
3. D按事前契約同時報總分、MEL／其他疾病保護、Seed穩定性與成本；輸出採納／未採納／未定及唯一下一步，不自動循環研究。
4. E只把已完成且可追溯的結論補入正式Word；進行中與未驗證項明列，不用提案或示意圖當實驗結果。
5. 本批若異常停止，保留run／Checkpoint／預算／日誌與原證據，回報阻礙，等待適用的新指示；不能把對話中斷當外部程序停止而重複開訓。

## 附錄A 六批已結案正式run逐筆清單

Robust為各run按原規則選定best的Validation分數；不是每輪最高值再另選指標。最佳／完成輪分列。這張表引用result，不重新推論或重建原曲線；原比較限制仍適用。

|實驗ID|Seed|最佳／完成Epoch|Robust %|Run ID|原始結果|
|---|---:|---|---:|---|---|
|convnextv2_tiny_imagenet|1|5/12|66.2946|2f10e3e3408242d5ab5e7fc325c228ad|[result](<資料治理與泛化修復/results/baseline_20261019_v1/runs/convnextv2_tiny_imagenet/regularized_seed1/result.json>)|
|convnextv2_tiny_imagenet|2|10/15|63.9673|89dcc59db128411d9d02c884e6f5a067|[result](<資料治理與泛化修復/results/baseline_20261019_v1/runs/convnextv2_tiny_imagenet/regularized_seed2/result.json>)|
|convnextv2_tiny_imagenet|3|8/13|63.2341|224f04b5f8294cd993f1cc371c84a4e1|[result](<資料治理與泛化修復/results/baseline_20261019_v1/runs/convnextv2_tiny_imagenet/regularized_seed3/result.json>)|
|convnextv2_tiny_random|1|11/16|42.7557|a15e5996a9eb40dfb3bf6475c9198577|[result](<資料治理與泛化修復/results/baseline_20261019_v1/runs/convnextv2_tiny_random/regularized_seed1/result.json>)|
|convnextv2_tiny_random|2|15/20|45.1882|fc259a00e0474fe8afdc0414e11bf140|[result](<資料治理與泛化修復/results/baseline_20261019_v1/runs/convnextv2_tiny_random/regularized_seed2/result.json>)|
|convnextv2_tiny_random|3|16/21|45.7968|43e4529c59a4491c8a5592decab2d88a|[result](<資料治理與泛化修復/results/baseline_20261019_v1/runs/convnextv2_tiny_random/regularized_seed3/result.json>)|
|mlp_pixels_random|1|21/26|32.8456|64cb4dedf756464b84dfec629e2f200b|[result](<資料治理與泛化修復/results/baseline_20261019_v1/runs/mlp_pixels_random/regularized_seed1/result.json>)|
|mlp_pixels_random|2|6/12|32.3156|5df6907ca28d4ac29a7e94f873cb0d5a|[result](<資料治理與泛化修復/results/baseline_20261019_v1/runs/mlp_pixels_random/regularized_seed2/result.json>)|
|mlp_pixels_random|3|9/14|31.1799|21ec6022f7654fa2b51363e1aab6d1ca|[result](<資料治理與泛化修復/results/baseline_20261019_v1/runs/mlp_pixels_random/regularized_seed3/result.json>)|
|resnet18_imagenet|1|6/12|55.1209|322c3ade422e4174acd21f7e33fb3c57|[result](<資料治理與泛化修復/results/baseline_20261019_v1/runs/resnet18_imagenet/regularized_seed1/result.json>)|
|resnet18_imagenet|2|13/18|57.7201|cbaabb9e6e6b42388c015f3edb7b177c|[result](<資料治理與泛化修復/results/baseline_20261019_v1/runs/resnet18_imagenet/regularized_seed2/result.json>)|
|resnet18_imagenet|3|16/21|59.1433|351c4dee11a94caa9a88b0ef1f7894e0|[result](<資料治理與泛化修復/results/baseline_20261019_v1/runs/resnet18_imagenet/regularized_seed3/result.json>)|
|resnet18_random|1|28/30|47.9080|a8dce0a2e68746fa9fecfe9e6fd0b0d4|[result](<資料治理與泛化修復/results/baseline_20261019_v1/runs/resnet18_random/regularized_seed1/result.json>)|
|resnet18_random|2|29/30|51.5182|249e7ce923784b1eb300445c71c65d48|[result](<資料治理與泛化修復/results/baseline_20261019_v1/runs/resnet18_random/regularized_seed2/result.json>)|
|resnet18_random|3|11/16|46.1910|a45b0ee0993746399bae2f1a3bb7efbd|[result](<資料治理與泛化修復/results/baseline_20261019_v1/runs/resnet18_random/regularized_seed3/result.json>)|
|v2in_ld09|1|7/12|64.0780|11a15619f2fc4b278f4406993cedba6e|[result](<資料治理與泛化修復/results/v2_optimization_20261020_v1/runs/v2in_ld09/regularized_seed1/result.json>)|
|v2in_ld09|2|10/15|64.2848|12f1133a410c4e76a0857f4b3caf9772|[result](<資料治理與泛化修復/results/v2_optimization_20261020_v1/runs/v2in_ld09/regularized_seed2/result.json>)|
|v2in_lr5e5|1|5/12|65.6091|462f4ff2c69a465fbaf7d387374f62f0|[result](<資料治理與泛化修復/results/v2_optimization_20261020_v1/runs/v2in_lr5e5/regularized_seed1/result.json>)|
|v2in_lr5e5|2|5/12|63.9243|c93e4b2009064909af10435cb289eb75|[result](<資料治理與泛化修復/results/v2_optimization_20261020_v1/runs/v2in_lr5e5/regularized_seed2/result.json>)|
|v2in_r2_bcn50|1|4/12|64.5804|ed6080eac8864954a10ea27ac249fce3|[result](<資料治理與泛化修復/results/v2_optimization_round2_20261020_v1/runs/v2in_r2_bcn50/regularized_seed1/result.json>)|
|v2in_r2_bcn50|2|8/13|64.6329|ce448a1354ae45f6831dbdcb01fad493|[result](<資料治理與泛化修復/results/v2_optimization_round2_20261020_v1/runs/v2in_r2_bcn50/regularized_seed2/result.json>)|
|v2in_r2_re0|1|6/12|63.7780|bd39c9613e7740ac80dcd0388e62fbb0|[result](<資料治理與泛化修復/results/v2_optimization_round2_20261020_v1/runs/v2in_r2_re0/regularized_seed1/result.json>)|
|v2in_r2_re0|2|5/12|63.0733|aa1e89397c5a49b1ab2d92722e134ba4|[result](<資料治理與泛化修復/results/v2_optimization_round2_20261020_v1/runs/v2in_r2_re0/regularized_seed2/result.json>)|
|v2in_res320|1|6/12|64.8939|c7e29f0e5a974d4a9dc62f59273e307f|[result](<資料治理與泛化修復/results/v2_resolution_20261021_v1/runs/v2in_res320/regularized_seed1/result.json>)|
|v2in_res320|2|12/17|64.7798|ca7fe019570f45109279ed9d89e71441|[result](<資料治理與泛化修復/results/v2_resolution_20261021_v1/runs/v2in_res320/regularized_seed2/result.json>)|
|v2in_res320|3|5/12|67.3503|c5e6be6d38dc4e22b25c25c68b79c39c|[result](<資料治理與泛化修復/results/v2_resolution_20261021_v1/runs/v2in_res320/regularized_seed3/result.json>)|
|v2in_res512|1|4/12|67.1483|1e32c15f7f13453983d2552608333e39|[result](<資料治理與泛化修復/results/v2_resolution_20261021_v1/runs/v2in_res512/regularized_seed1/result.json>)|
|v2in_res512|2|10/15|67.3285|596afe643c5e4362bb8332fcad252f9f|[result](<資料治理與泛化修復/results/v2_resolution_20261021_v1/runs/v2in_res512/regularized_seed2/result.json>)|
|v2in_res512|3|7/12|67.1816|16f68c2066fd44b4b280ed9e3760410c|[result](<資料治理與泛化修復/results/v2_resolution_20261021_v1/runs/v2in_res512/regularized_seed3/result.json>)|
|v2in_res512_alpha025|1|8/13|67.0781|21d2aaccb9e5490faba534f6b752fa98|[result](<資料治理與泛化修復/results/v2_512_alpha025_20261024_v1/executions/retry1_20261024_v1/runs/v2in_res512_alpha025/regularized_seed1/result.json>)|
|v2in_res512_alpha025|2|15/20|64.9257|88e812db602549c8b6593c29a51e55c4|[result](<資料治理與泛化修復/results/v2_512_alpha025_20261024_v1/executions/retry1_20261024_v1/runs/v2in_res512_alpha025/regularized_seed2/result.json>)|
|v2in_res512_alpha025|3|5/12|66.9297|1fc8933da4aa4a25aa902729874cf894|[result](<資料治理與泛化修復/results/v2_512_alpha025_20261024_v1/executions/retry1_20261024_v1/runs/v2in_res512_alpha025/regularized_seed3/result.json>)|
|v2in_scale512_base|1|6/12|69.2906|efc7718472e14007be0686800f5183c3|[result](<資料治理與泛化修復/results/v2_scale512_seed1_20261025_v1/runs/v2in_scale512_base/regularized_seed1/result.json>)|
|v2in_scale512_large|1|11/16|67.7141|7c6b140d4ed442389852be8707d8e2c6|[result](<資料治理與泛化修復/results/v2_scale512_seed1_20261025_v1/runs/v2in_scale512_large/regularized_seed1/result.json>)|

## 附錄B 正式來源與重現邊界

下列為本報告直接使用的現有文件與小型數值來源。每份在SOURCE_SNAPSHOT.json中記錄路徑、大小、SHA256；完整34run result另列SHA。沒有重新hash大型模型、資料集或重新執行來源中的驗證程式。歷史來源的QA數字只代表來源作者當時的驗收，不冒稱總控重做。

- [AGENTS.md](<AGENTS.md>)
- [PROJECT_STATE.md](<docs/PROJECT_STATE.md>)
- [V2_EXPERIMENT_HISTORY.md](<docs/V2_EXPERIMENT_HISTORY.md>)
- [summary.json](<資料治理與泛化修復/data/governed_18979_20261018_v1/summary.json>)
- [baseline_results.json](<資料治理與泛化修復/results/baseline_20261019_v1/reports/baseline_results.json>)
- [REPORT.md](<資料治理與泛化修復/results/resolution_decision_20261024_v1/REPORT.md>)
- [COMPARISON.json](<資料治理與泛化修復/results/resolution_decision_20261024_v1/COMPARISON.json>)
- [DECISION.md](<recovery_20261023/D_v2_analysis/resolution_decision_20261024_v1/DECISION.md>)
- [REPORT.md](<recovery_20261023/D_v2_analysis/root_cause_20261025_v1/REPORT.md>)
- [NUMERIC_ANALYSIS.json](<recovery_20261023/D_v2_analysis/root_cause_20261025_v1/NUMERIC_ANALYSIS.json>)
- [REPORT.md](<recovery_20261023/D_v2_analysis/scale512_review_20261026_v1/REPORT.md>)
- [NUMERIC_ANALYSIS.json](<recovery_20261023/D_v2_analysis/scale512_review_20261026_v1/NUMERIC_ANALYSIS.json>)
- [REPORT.md](<recovery_20261023/B_training/matched_source_trainval_512_20261025_retry1_v1/REPORT.md>)
- [FINAL_RESULTS.json](<資料治理與泛化修復/results/v2_scale512_seed1_20261025_v1/FINAL_RESULTS.json>)
- [README.md](<recovery_20261023/B_training/scale512_seed1_20261025_v1/README.md>)
- [README.md](<recovery_20261023/B_training/scale512_followup_20261026_v1/README.md>)
- [EVALUATION_CONTRACT.json](<資料治理與泛化修復/configs/v2_scale512_followup_20261026_v1/EVALUATION_CONTRACT.json>)
- [遺失檔案與可重建項目.md](<recovery_20261024/遺失檔案與可重建項目.md>)
- [歷史資料夾用途盤點_20261026_v1.md](<recovery_20261024/歷史資料夾用途盤點_20261026_v1.md>)
- [state.json](<資料治理與泛化修復/results/v2_scale512_followup_20261026_v1/state.json>)

本次實際工作目錄：D:/SkinDetect_base。整理程式只用Python標準函式庫讀既有JSON／文字，命令如下，**用途僅文件快照整理，與訓練啟動分離**：

```powershell
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -X utf8 'recovery_20261024\training_status_20261026_v1\assemble_status.py'
```

本版已保存，不重複執行覆寫同版本。唯讀查看訓練可用：

```powershell
Get-Content -LiteralPath '資料治理與泛化修復\results\v2_scale512_followup_20261026_v1\MONITOR.md'
```

本報告完成的是來源整併、狀態截點與文件輸出；不是額外研究、全面環境重驗或訓練品質保證。
