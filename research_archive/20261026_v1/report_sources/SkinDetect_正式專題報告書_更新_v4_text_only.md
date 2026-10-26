# Office文字擷取發布副本

原件未公開；不含圖片／版面／Word欄位，可恢復正文文字但不能還原原生格式。原研究時態與版本截點保留，不重寫成目前狀態。

## word/document.xml

中 國 文 化 大 學

資 訊 工 程 學 系

資 訊 系 統 專 題

SkinDetect 皮膚病灶分類

學    生：[PERSON_REDACTED]

          [PERSON_REDACTED]

          [PERSON_REDACTED]

指導教授：[PERSON_REDACTED]

中華民國115年10月

SkinDetect 多來源皮膚病灶影像分類研究

學生：[PERSON_REDACTED]、[PERSON_REDACTED]、[PERSON_REDACTED]

指導教授：[PERSON_REDACTED] 博士

中國文化大學 資訊工程學系

摘要

本研究以 HAM10000、BCN20000 與 PAD-UFES-20 進行七類皮膚病灶分類。經標籤映射、分組隔離與精確去重，Train 為 18,919 張、Validation 為 3,611 張，另封存 Test 1,502 張。MLP 隨機、ResNet-18 隨機／ImageNet、ConvNeXt V2-Tiny 隨機／ImageNet 五組各執行三個 Seed，共完成 15 次正式基線訓練。

Robust Score 將三來源 Balanced Accuracy 的平均與最低值各加權一半。V2 ImageNet 基線平均64.4987%，兩輪各兩候選均未通過n=2篩選。Tiny 320／512三Seed平均為65.6747%／67.2195%；alpha025雖提高Accuracy／Macro-F1，Robust降至66.3112%，不採納。512 Base／Large單Seed為69.2906%／67.7141%，伴隨疾病取捨，尚未採納。342張匹配診斷僅提供局部線索；結果限於Validation，Test與臨床效能未評估。

關鍵詞：皮膚病灶分類、資料治理、遷移學習

指導教授              （簽名）

SkinDetect Multi-source Skin Lesion Image Classification

Student:Wu Szu-Wei, Wu Kun-Zhe, and Liang Xing-Ming

Advisor: Prof. Shih-Sung Lin

Department of Computer Science and Information Engineering

Chinese Culture University

ABSTRACT

This study evaluates seven-class skin lesion classification using HAM10000, BCN20000, and PAD-UFES-20. Label harmonization, group isolation, and exact deduplication yielded 18,919 training and 3,611 validation images; 1,502 test images remained sealed. Five groups with three seeds each completed 15 baseline runs: a random multilayer perceptron, and ResNet-18 and ConvNeXt V2-Tiny with random or ImageNet initialization.

Selection used a Robust Score equally weighting mean and minimum source-level balanced accuracy. Baseline means were 0.3211, 0.4854, 0.5733, 0.4458, and 0.6450. Both optimization rounds rejected their two candidates after paired two-seed screening. Tiny at 224/320/512 achieved three-seed mean Robust Scores of 64.4987%, 65.6747%, and 67.2195%. Alpha025 improved accuracy and macro-F1 but reduced Robust to 66.3112% and was not adopted. Single-seed Base/Large screening at 512 reached 69.2906%/67.7141% with disease trade-offs; neither was adopted. A matched 342-image diagnostic provided limited fitting/generalization evidence. All findings concern validation-based selection; final Test and clinical effectiveness remain unevaluated.

Keywords: skin lesion classification, data governance, transfer learning, multi-source evaluation, ConvNeXt V2

目 錄

摘要I

ABSTRACTII

第1章 研究動機與目的1

1.1 研究動機1

1.2 研究目的1

第2章 文獻探討2

2.1 皮膚病灶分類與公開影像資料集2

2.2 殘差網路與 ResNet-182

2.3 ConvNeXt V2 與 ImageNet 遷移學習3

2.4 資料不平衡與多來源分類評估3

第3章 研究內容、方法與工作項目5

3.1 研究流程與執行環境5

3.1.1 系統硬體與運算資源5

3.1.2 軟體環境與可重現設定5

3.1.3 資料與成果的追溯流程6

3.2 資料治理與正式切分6

3.2.1 來源標籤與七類映射6

3.2.2 重複影像與分組隔離7

3.2.3 Manifest 版本與資料用途8

3.3 基線模型與初始化設計9

3.3.1 像素式 MLP 基線9

3.3.2 ResNet-18 對照模型9

3.3.3 ConvNeXt V2-Tiny 對照模型9

3.3.4 初始化配對與權重來源9

3.4 訓練與評估設計10

3.4.1 前處理、資料增強與抽樣10

3.4.2 優化設定、選模與停止規則11

3.4.3 評估指標與三 Seed 統計12

3.5 網站與 API 實作14

3.5.1 上傳至結果呈現的流程14

3.5.2 三個 API 入口與輸入輸出15

3.6 後續實驗與匹配診斷設計16

第4章 模型比較與實驗結果17

4.1 實驗完成狀態與整體比較17

4.2 來源差異與各類 Recall20

4.3 同架構初始化的配對比較24

4.4 訓練曲線與停止行為分析24

4.5 訓練時間與比較限制30

4.6 網站與 API 的 CPU 功能驗收33

4.7 第二輪最佳化結案34

4.8 Tiny 解析度與 E224 既有結果35

4.9 alpha025 三 Seed 結果與不採納決策36

4.10 342 張匹配 Train 與 Validation 診斷36

4.11 512 模型大小單 Seed 初篩與疾病取捨37

4.12 後續確認批次的狀態截點41

第5章 結論與研究限制42

5.1 已完成研究的結論42

5.1.1 版本化資料治理與一致類別定義42

5.1.2 五組三 Seed 正式基線比較42

5.1.3 來源與訓練行為的實證觀察42

5.2 研究限制43

5.2.1 資料隔離與來源涵蓋限制43

5.2.2 配方差異與驗證集選擇偏差43

5.2.3 小樣本、亂數變異與恢復限制43

5.2.4 研究結論的應用範圍43

第6章 參考文獻44

第7章 專題工作配置與完成紀錄46

7.1 已完成工作與成果位置46

7.2 完成時程與追溯方式47

表 目 錄

表3.1 七類定義與正式資料分布7

表3.2 各來源正式切分與用途8

表3.3 各架構的正式優化配方11

表3.4 正規化、抽樣及正則化條件12

表4.1 五組模型的三 Seed 整體 Validation 結果17

表4.2 15 次正式訓練的最佳輪與停止紀錄18

表4.3 三來源 Validation Balanced Accuracy20

表4.4 合併 Validation 各類 Recall（一，%）21

表4.5 合併 Validation 各類 Recall（二，%）21

表4.6 ImageNet − Random 的同 Seed Robust 差24

表4.7 各組實際累計訓練時間30

表4.8 第一輪四次正式訓練的最佳 Validation 結果31

表4.9 第一輪與相同 Seed 基線的篩選統計31

表4.10 第一輪原定篩選門檻與實際判定32

表4.11 第二輪相同 Seed 配對差（n=2，pp ）34

表4.12 Tiny 各尺寸三 Seed Validation 結果（%，SD為pp ）35

表4.13 alpha025 與原512比較（n=3，%，Δ為pp ）36

表4.14 匹配診斷的代表性 TP/N（Seed1 ）37

表4.15 512 單 Seed 最佳 Validation 結果（% ）38

表4.16 512 單 Seed 三來源 BA（% ）38

表4.17 512 單 Seed 重要疾病命中（每欄為TP ，支持數固定）39

表4.18 512 已提交輪與正式 attempt  耗時（分鐘）40

表7.1 本稿使用的已完成研究產物46

圖 目 錄

圖4.1 五組模型的 Validation Robust Score 比較18

圖4.2 五組模型的三來源 Balanced Accuracy20

圖4.3 五模型各類 Recall 與跨 Seed 變異22

圖4.4 ConvNeXt V2-Tiny ImageNet 的分來源各類 Recall22

圖4.5 ConvNeXt V2-Tiny ImageNet 的三來源平均混淆矩陣23

圖4.6 同 Seed 的初始化配對差異24

圖4.7 MLP Random 三 Seed 訓練曲線25

圖4.8 ResNet-18 Random 三 Seed 訓練曲線26

圖4.9 ResNet-18 ImageNet 三 Seed 訓練曲線27

圖4.10 ConvNeXt V2-Tiny Random 三 Seed 訓練曲線28

圖4.11 ConvNeXt V2-Tiny ImageNet 三 Seed 訓練曲線29

圖4.12 正式訓練時間與完成輪數30

圖4.13 Tiny／Base／Large 單 Seed  比較與已保存曲線40

研究動機與目的

研究動機

皮膚病灶影像的色澤、紋理與形態，可作為影像分類模型學習的資訊。Esteva 等人的研究展示深度神經網路應用於皮膚影像辨識的可行性[1]，但既有文獻的資料條件與評估情境不等於本專題的實驗條件。SkinDetect 因此以可追溯的資料處理與模型比較為研究核心，檢視固定七分類任務中，不同模型及初始化方案所呈現的實際表現。

資料來自不同拍攝方式與收集情境時，整體正確率可能掩蓋來源間差異。HAM10000 與 BCN20000 主要提供皮膚鏡影像，PAD-UFES-20 則提供智慧型手機臨床照片[2][3][4]。本研究將三來源同時納入訓練與驗證，觀察同一受控切分中各來源的分類表現；此設計是多來源混合資料比較，並非未見來源的外部泛化驗證。

模型比較須同時記錄架構與訓練流程。本專題保留有效設定、逐輪紀錄及三個 Seed 的變異，以區分整套基線的實際差異與其解釋限制。

研究目的

本研究第一項目的為建立一致的七類定義及版本化 Manifest，保留原始標籤、來源、分組鍵、排除原因與資料用途，並在既有固定切分上處理精確重複，降低已知資料洩漏風險。第二項目的為完成五組模型各三個 Seed 的正式基線，以同一資料成員及評估規則進行比較。

第三項目的為分析 Accuracy、Macro-F1、三來源 BA、各類 Recall 及曲線，並記錄 V2 第一輪的實際篩選結果。第四項目的為區分 Validation 選模與最終 Test；本稿不宣稱臨床診斷能力。

文獻探討

本章依研究實際使用的資料與方法整理文獻。文獻提供資料背景、模型設計與評估方法的依據；本地樣本數、超參數及實驗成績則以本專題的正式 Manifest 與 C 成果為準，不以論文數字代替本機結果。

皮膚病灶分類與公開影像資料集

HAM10000 由 Tschandl、Rosendahl 與 Kittler 發布，包含 10,015 張皮膚鏡影像及七個診斷類別；同一病灶可能具有多張影像，因此切分時須留意病灶成員關係[2]。本研究沿用其七類輸出概念，但將其他資料來源映射至此分類框架時，仍保留原始診斷及映射關係，避免把疾病家族對應描述為完全相同的病理標籤。

BCN20000 的正式資料論文說明資料包含不同部位、低色素及難以完整納入皮膚鏡視野的病灶。2024 年出版版本記載 18,946 張影像，且詳細診斷主要提供於訓練部分[3]。本研究採用本地具有相容標籤的資料成員，而不直接把資料集名稱或論文總張數視為實際訓練量；其既有未標示診斷的測試資料沒有強行加入本次監督式七分類。

PAD-UFES-20 由 Pacheco 等人發布，結合患者資訊與智慧型手機拍攝的臨床照片[4]。與皮膚鏡影像相比，拍攝情境不同，因而有必要分來源報告指標。本研究僅使用已核定可映射至七分類的五個標籤；PAD 無 DF、VASC 支持樣本時，對應 Recall 及來源 BA 計算均依適用類別處理。

殘差網路與 ResNet-18

He 等人提出殘差學習，讓網路學習相對於輸入的殘差映射，基本形式可表示為 y = F(x) + x；當維度不一致時，可使用投影捷徑使維度相容。此設計改善深層網路的優化問題[5]。本專題採 ResNet-18 作為卷積基線，將最終分類層對應至七類輸出，分別比較隨機與 ImageNet 初始化。

這兩組 ResNet 使用相同的本地訓練配方，且同一 Seed 的新分類 head 具有相同初始指紋，因此可進行較直接的初始化方案比較。此處比較的是實際載入的預訓練 backbone 與隨機 backbone，不表示兩條訓練路徑在每輪皆具有相同隨機增強序列，也不構成對所有資料集的普遍結論。

ConvNeXt V2 與 ImageNet 遷移學習

ConvNeXt V2 同時設計卷積架構與 masked autoencoder 預訓練，使用全卷積遮罩自編碼器（FCMAE），並引入 GRN 以調整通道間特徵反應[6]。本研究使用真正的 V2-Tiny：階段深度為 [3, 3, 9, 3]，含 18 個 GRN，分類 head 為七類；此模型不等同於舊版 ConvNeXt-Tiny。

ImageNet 是影像資料庫與預訓練來源，而不是本專題的第六個模型[7]。Yosinski 等人討論特徵由一般性轉為任務特定性的過程，指出遷移效益受來源與目標任務差異及優化條件影響[8]。本研究使用 ResNet-18 的 torchvision IMAGENET1K_V1，以及 timm 的 convnextv2_tiny.fcmae_ft_in1k；兩者預訓練流程不同，不能把各自的分數增益直接解釋成架構間的遷移效率差。

資料不平衡與多來源分類評估

Buda 等人以系統性實驗研究卷積網路的類別不平衡問題，顯示類別分布與重抽樣策略應納入模型評估[9]。本研究保留各來源自然分布的 Validation；訓練端則明確區分 MLP／ResNet 的不放回 shuffle，與 V2 的來源平衡、類別次方平滑之有放回抽樣。該設計的效果須與其餘配方共同解讀，本輪未將抽樣方式單獨作消融實驗。

Accuracy 依影像數加權，可能受多數類別主導。Balanced Accuracy 透過各類 Recall 的平均降低此影響[10]；本研究將其依實際支持類別推廣至多分類來源評估，並另報 Macro-F1。Robust Score 則是本專題預先使用的選模規則，並非宣稱由上述文獻提出的通用標準。

Torralba 與 Efros 指出資料集本身可能帶有偏差，單一資料集中的高分不足以保證跨資料集表現[11]。因此，本研究以三來源 BA 與弱類別支持數補充整體成績。但三來源皆已參與訓練與選模，本輪只能觀察來源間落差，不能據此宣稱已驗證未見醫院、設備或族群的外部泛化。

研究內容、方法與工作項目

研究流程依序為來源與標籤稽核、固定切分的去重發布、模型與初始化設定凍結、三 Seed 基線訓練，以及來源／類別與曲線分析；其後針對 V2 ImageNet 基線進行第一輪單因子最佳化篩選。基線及第一輪各保留獨立實驗版本、原始結果、有效設定與權重路徑。報告修訂沿用已發布成果，未重新啟動訓練或推論。

研究流程與執行環境

系統硬體與運算資源

正式訓練前的執行紀錄標示 CUDA 裝置為 NVIDIA GeForce RTX 5070。硬體型號用於交代本輪執行背景；本稿沒有重新量測 GPU 吞吐、顯示記憶體峰值或推論延遲，因此不據此提出效能結論。影像與正式結果位於 D:\SkinDetect_base，原始 dataSets 與版本化衍生產物分開保存。

軟體環境與可重現設定

run_inputs.json 保存的執行版本為 Python 3.12.10、PyTorch 2.11.0+cu128、torchvision 0.26.0+cu128、NumPy 1.26.4、Pillow 10.4.0 及 timm 1.0.30。正式入口及共用模型、訓練器與指標程式的雜湊均記錄於 contract。這些是該訓練執行的版本紀錄，不表示只憑同一套件版本即可在任意硬體達成逐位元相同結果。

每次訓練保存有效設定、資料版本與 Seed。Checkpoint 保留模型、Optimizer、Scheduler、AMP scaler、最佳分數、早停計數及主要亂數狀態；恢復以原 Run ID 接續。MLP Seed 1 的兩次執行嘗試合計只計為一次正式訓練。恢復限制為 Epoch 級，且 persistent workers 內部增強 RNG 不保證逐位元重播。

資料與成果的追溯流程

正式 Manifest 的 SHA-256 為 5c501ef3cb6c8a73b3a9395383d199212e070abfbc67c782fcfc010576243284。C 的結果快照為 snapshot_20261020_v1，補充混淆矩陣與 Recall 圖為 cross_analysis_20261020_v1。正文比較表以 C 未四捨五入的 CSV／JSON 為來源，再依顯示需求統一小數位；圖像直接使用 C 發布的 12 張 PNG，沒有以簡報圖形估讀數字。

第一輪實驗 ID 為 v2_optimization_20261020_v1；新增數值引用 C「V2第一輪最佳化結案分析_20261020_v1」的完整精度 JSON 及配對 CSV，採納與否則與 B decisions 原始檔對照。既有 12 張 C 正式 PNG 與基線數值保持原樣，未另繪第二套研究結果。

初稿 v1 已核對 15 份基線 result.json 的 Seed、最佳輪、完成輪、Robust、來源 BA、Manifest 雜湊與 Test 未使用旗標。本次沿用該成果，新增查核 C 第一輪結案 JSON／CSV、B 原始篩選決策及最新研究狀態；未重做基線分析，亦未載入模型權重。各次文件核對範圍分別記錄於產物旁的來源清單。

資料治理與正式切分

來源標籤與七類映射

七類順序固定為 AKIEC、BCC、BKL、DF、NV、VASC、MEL，對應輸出索引 0 至 6。映射保留原始診斷與疾病家族的對應程度；BCN 的 AK、PAD 的 ACK 對應 AKIEC 家族，PAD 的 SEK 對應 BKL 家族，NEV 對應 NV。SCC 不屬既定七類，不將其強行併入其他類別。

表3.1 七類定義與正式資料分布

索引／代碼

類別定義

Train

Validation

0 / AKIEC

光化性角化症／表皮內癌光譜

1433

297

1 / BCC

基底細胞癌

3496

577

2 / BKL

良性角化病變群

1891

401

3 / DF

皮膚纖維瘤

171

51

4 / NV

黑色素細胞痣

8401

1736

5 / VASC

血管性病變

188

43

6 / MEL

黑色素瘤

3339

506

資料來源：disease_mapping_v1.csv、governed_18979_20261018_v1/mixed_manifest.csv；Test 不列入此分布表。

重複影像與分組隔離

資料準備保留既有歷史 split 身份，不為增加張數重新抽樣。依發布摘要，24,726 張來源影像已建立 SHA-256；同內容且同標籤的非代表列與標籤衝突列依核定政策排除。歷史成員共排除 71 列：Train 60、Validation 10、Test 1；連同原先七類以外的 SCC，排除來源列共有 694 筆。排除原因可重疊，不能把各原因筆數直接相加當作獨立總數。

PAD 以 patient_id 分組，病灶記錄鍵使用 patient_id 與 lesion_id 的組合，避免不同患者的局部病灶編號重用造成錯誤排除。HAM 與 BCN 缺患者識別，僅能核對已提供的病灶／群組隔離。發布紀錄中的可用患者鍵、來源分組鍵、病灶記錄鍵與已知精確重複連通群組，跨 split 交集均為零。

精確雜湊相同只代表位元組內容相同；此治理不保證排除不同壓縮、裁切或近似影像，也不等同完整人工品質審查。發布階段只抽樣解碼 9 張且皆可讀，不能寫成已逐張完成影像解碼驗證。原始影像、metadata 與來源檔案均保留。

Manifest 版本與資料用途

正式版本為 governed_18979_20261018_v1。版本名稱保留歷史 18979 數字，實際去重後 Train 為 18,919，不能用版本名代替樣本數。mixed_manifest.csv 僅含 Train 與 Validation，共 22,530 列，保存專案相對影像路徑、原始標籤、分組資訊、影像雜湊及資料角色。來源張數如表3.2。

表3.2 各來源正式切分與用途

來源

Train

Validation

封存 Test

HAM10000

7,007

1,504

1,502

BCN20000

10,221

1,712

0

PAD-UFES-20

1,691

395

0

合計

18,919

3,611

1,502

資料來源：正式 release 的 summary.json、README.md；封存 Test 張數僅取發布摘要，E 未讀取 test.csv 或 Test 圖片。

Train 用於參數更新，Validation 用於每輪評估、最佳權重選擇與早停。1,502 張 Test 均為 HAM 保留影像，尚未進行最終評估；該 Test 並不涵蓋三來源的完整外部測試情境。SCIN 及其他未納入本輪七類正式 Manifest 的資料，不列入此訓練與成績表。

基線模型與初始化設計

像素式 MLP 基線

MLP Random 將 64×64 RGB 像素展平後輸入全連接網路，結構為 Flatten → 512／ReLU／Dropout(0.3) → 256／ReLU → 7。此基線直接使用像素，不引入卷積的局部共享權重機制。它提供在目前資料與低解析度設定下，簡單分類器的對照，而不是與高解析度 CNN 完全等條件的架構消融。

ResNet-18 對照模型

ResNet-18 的兩組實驗皆輸入 224×224 影像，七類分類 head 與本輪類別順序一致。Random 組由 Seed 決定初始化；ImageNet 組只載入形狀相容的預訓練 backbone，再使用同 Seed 初始化的新七類 head。兩組採相同的本地增強、正規化、Optimizer、抽樣與停止規則。

ConvNeXt V2-Tiny 對照模型

ConvNeXt V2-Tiny 的 Random 與 ImageNet 組共用相同 V2 架構、224×224 輸入與七類 head。ImageNet 權重識別為 timm/convnextv2_tiny.fcmae_ft_in1k，revision 為 508caf1bc24fd02c69d15778b994e808670dbc28；Random 組不讀取該預訓練權重。兩組皆採本輪核定的 regularized_native 訓練流程。

初始化配對與權重來源

ResNet ImageNet 權重為 torchvision/ResNet18_Weights.IMAGENET1K_V1，檔名 resnet18-f37072fd.pth；C 保存 SHA-256 為 f37072fd47e89c5e827621c5baffa7500819f7896bbacec160b1a16c560e07ec。V2 ImageNet 的 model.safetensors 原紀錄 SHA-256 為 fdfb4edfa5abb3b4ea29ab17e6fae5c117dc6cc32ecfb1d0726a156f40a4c1a5。本稿引用原紀錄身分，未重新雜湊權重內容。

每組皆執行 Seed 1、2、3，各次訓練由獨立初始模型與空 Optimizer 開始。同架構、同 Seed 的兩種初始化，其新分類 head 初始指紋相同；因此以同 Seed 配對呈現 ImageNet − Random 差值。不同架構保留各自基線，故不以配對差推導單一架構因果效果。

訓練與評估設計

前處理、資料增強與抽樣

MLP 不使用隨機影像增強，以 mean／std 各為 0.5 正規化。ResNet 使用翻轉、0／90／180／270 度旋轉及隨機裁切，正規化同樣為各通道 mean=0.5、std=0.5；即使載入 ImageNet 權重，亦沿用本輪相同設定。Validation 僅調整大小與正規化，不採隨機增強。

V2 使用 ImageNet mean=[0.485, 0.456, 0.406]、std=[0.229, 0.224, 0.225]。訓練影像採 RandomResizedCrop（scale 0.70–1.0、ratio 0.75–1.33）、水平／垂直翻轉、25 度旋轉、ColorJitter、灰階、GaussianBlur、Autocontrast 與 RandomErasing；Validation 為固定 Resize 與相同正規化。

MLP 與 ResNet 採不放回 shuffle；V2 採來源平衡、類別平滑的有放回抽樣。對來源 s、類別 c 的樣本數 n(s,c)，單張權重為 n(s,c)^(−α)／Σk n(s,k)^(1−α)，α=0.5；各來源的總權重相等。每輪抽 18,919 次，但不保證每張影像各出現一次，因此相同 Epoch 數不等於相同唯一樣本覆蓋。

優化設定、選模與停止規則

五組皆使用 AdamW、CrossEntropyLoss 與 AMP。各模型配方如表3.3及表3.4；完整累積步的名目有效 Batch 為 batch×accumulation，末批不足時沿用原訓練器更新方式。每個 DataLoader 的 Workers=4，pin_memory=True、persistent_workers=True、prefetch_factor=4；這是每個 Loader 的設定，不代表全程只有四個背景工作程序。

表3.3 各架構的正式優化配方

設定

MLP R

ResNet R／IN

V2 R／IN

輸入

64×64

224×224

224×224

Batch×累積

64×1

32×1

32×2

有效 Batch

64

32

64

Learning Rate

0.001

0.0003

0.0001

Weight Decay

0.0001

0.0001

0.05

Scheduler

無

無

Cosine

最低 LR

不適用

不適用

0.000001

Layer Decay

不適用

不適用

1.0

表3.4 正規化、抽樣及正則化條件

設定

MLP R

ResNet R／IN

V2 R／IN

Label Smoothing

0

0

0.1

MixUp α

0

0

0.2

梯度裁剪

無

無

1.0

抽樣

shuffle

shuffle

加權有放回

參數衰減

統一

統一

bias／1D 不衰減

影像正規化

0.5／0.5

0.5／0.5

ImageNet

訓練增強

無

原生增強

原生正則增強

來源：五份正式 JSON 與各 Run 的 effective_training_config；R=Random，IN=ImageNet。

訓練最多 30 輪、最少 12 輪、Patience=5、Min Delta=0。只有 Robust 嚴格大於歷史最佳才算改善，相等亦累計未改善。Patience 自第 1 輪起累計，改善時歸零；第 12 輪起若未改善次數至少 5 即早停，否則最遲第 30 輪停止。Min Epoch 限制停止時間，不限制保存最佳權重，因此最佳輪可早於第 12 輪。

V2 的 18 個參數群組初始 LR 均為 0.0001，Layer Decay=1.0；bias 與一維參數不做 Weight Decay。CosineAnnealingLR 的 T_max=30、eta_min=1e−6，實際早停可能先於 Cosine 走完。各 Run 採首次達到最高 Robust Score 的 best.pt，不以最低 Validation Loss 或最後一輪取代。

評估指標與三 Seed 統計

令混淆矩陣 C 的列為真實類別、欄為預測類別，類別 c 的支持數為 Nc=Σj Ccj。Recall(c)=Ccc／Nc；Accuracy=Σc Ccc／Σc Nc。F1(c)=2TPc／(2TPc+FPc+FNc)，Macro-F1 為指定類別集合的 F1 平均。整體 Accuracy、Macro-F1 與 Recall 由三來源混淆矩陣相加後計算，並非三個來源指標直接平均。

來源 s 的 BA(s)=Σc∈Ls Recall(s,c)／|Ls|，Ls 為該來源有真值支持的類別集合。HAM／BCN 的集合為七類；PAD 為 AKIEC、BCC、BKL、NV、MEL 五類。PAD 的 DF／VASC 為不適用，不能以零 Recall 加入分母。若模型把 PAD 影像誤判為這兩類，原混淆矩陣仍保留該錯誤，並非刪除誤分類樣本。

本研究 Robust Score = 0.5×[BA(HAM)+BA(BCN)+BA(PAD)]／3 + 0.5×min{BA(HAM), BA(BCN), BA(PAD)}。此分數同時關注平均來源與最弱來源；它不是一般 Accuracy，也不是合併七類 BA。當 BCN 為最弱來源時，代數上可寫為 BA(HAM)／6 + BA(PAD)／6 + 2BA(BCN)／3，但這是評分權重，不是生物或訓練因果效果。

基線各組平均與樣本標準差由 Seed 1、2、3 計算；第一輪候選僅有 Seed 1、2，另列 n=2 篩選統計並與相同 Seed 基線配對。SD 分母皆為 n−1（ddof=1）。這些數值反映固定切分下的訓練亂數變異，不是患者母群信賴區間或跨切分驗證；本研究只作描述性比較。Train objective、分層 1,500 張 Train monitor 與自然分布 Validation Loss 的條件不同，僅連同指標判讀趨勢。

第一輪以原 V2 ImageNet 為共同對照，兩候選分別只將基礎學習率由 1e−4 降至 5e−5（v2in_lr5e5），或只將 Layer Decay 由 1.0 改為 0.9（v2in_ld09）。兩者各自由原 ImageNet 權重開始，不疊加變更，也不由另一候選接續微調；同 Seed 對應原基線。

共同條件沿用 224×224、Batch 32×累積 2、AdamW、Weight Decay 0.05、Label Smoothing 0.1、MixUp 0.2、原來源平衡抽樣與增強、Cosine 最低 LR=1e−6，以及最多 30／最少 12 輪、Patience 5。第一階段只執行 Seed 1、2；所有預定門檻同時成立才可進入 Seed 3 與完整三 Seed 採納階段。

第一階段檢查 Robust、BCN、Macro-F1 與 Accuracy，並保護單 Seed Robust、HAM／PAD BA、BCN DF／BKL／MEL 及合併 MEL Recall；原定 11 項條件完整列於表4.10。未通過即結束該候選；Seed 3 未執行與程序失敗須分開記錄，不以較佳單項或單 Seed 取代原門檻。

網站與 API 實作

上傳至結果呈現的流程

截至 2026 年 10 月 25 日，本機網站已串接原 ConvNeXt V2-Tiny ImageNet 的 224×224 推論。流程依序為網頁選取或拖放影像並預覽、API 接收請求、影像前處理、V2 推論、JSON 回傳及網頁呈現七類分數。此流程沿用既有權重與類別契約，與後續訓練候選的研究進度分開管理。

前端以 HTML、CSS 與 JavaScript 實作；使用者選擇模式後，將影像編為 Base64 data URL，連同 model_id 與 image_name，以同源 JSON 請求送至後端。後端使用 Python 內建 http.server 的 ThreadingHTTPServer 與 BaseHTTPRequestHandler，同時提供靜態網頁和 API；推論由 PyTorch 執行，沒有採用 Flask 或 FastAPI。服務僅綁定 127.0.0.1，本次驗收網址為 http://127.0.0.1:8766/index.html。

API 檢查模式、JSON、影像格式及大小，解碼 JPG、PNG 或 WebP 後轉為 RGB。前處理沿用正式 Validation 轉換：雙線性縮放至 224×224、antialias、張量轉換，再以 ImageNet 的 mean（0.485、0.456、0.406）與 std（0.229、0.224、0.225）正規化；不另加 EXIF 旋轉、裁切或測試增強。單張影像上限為 20 MiB 與 6,400 萬像素，網站請求 batch 為 1。

原 Seed1 模式使用最佳輪 5 的權重；E224 使用原 Seed1／2／3 最佳輪 5／10／8，各成員權重為 1/3。模型以 eval 與 inference_mode 執行，各成員 logits 轉為 float32 CPU 後進行 softmax；E224 對七類機率作等權平均。固定類序為 AKIEC、BCC、BKL、DF、NV、VASC、MEL，512 候選並未接入這兩種網站模式。

三個 API 入口與輸入輸出

GET /api/v2/health：不需影像輸入，用於確認執行開關、metadata 契約與模式可用性；回傳 JSON 包含 execution_enabled、artifacts_metadata_ok、class_order、preprocessing 與 models。該入口與 models 共用目錄回應，HTTP 200 本身不等於完成模型推論或 GPU 驗收。

GET /api/v2/models：不需影像輸入，用於讓前端取得可選模式、成員 Seed、權重、前處理與用途限制。兩種現有 model_id 分別為 v2_imagenet_seed1 與 v2_imagenet_ensemble123；它們對應原 224 Seed1 與 E224，不是新訓練模型的自動註冊入口。

POST /api/v2/predict：接受 application/json，輸入 model_id、image_name 與 image_data_url。成功時回傳 is_mock=false、device、class_order、disease 七類分數、members 成員及最佳輪／權重、checkpoint_version、member_probabilities 與 timing；calibrated=false 表示分數尚未校準，heatmap.available=false 表示未串接 Grad-CAM。

前端 adapter 驗證真實回應及七類有限機率後，呈現七條分數、成員資訊與研究用途提醒。無效輸入或執行失敗時，API 以 HTTP 4xx／5xx 及 code、error 回報，不以 Mock 冒充成功。七類中最高分不等於正常皮膚判定、輸入適用性確認或醫療診斷。

後續實驗與匹配診斷設計

本版接續既有基線，整合兩輪最佳化、Tiny 解析度、alpha025、匹配診斷與模型大小初篩。全部使用 governed_18979_20261018_v1 七類及既定 Validation；原 224 結果、網站 CPU 驗收與來源作者保留，沒有將新模型自動替換網站。三 Seed 比較報平均與樣本 SD（ddof=1），單 Seed 初篩及單一 E224 系統各自分列。

第二輪獨立提高 BCN 抽樣期望份額至 0.50（HAM／PAD 各 0.25），或僅停用 RandomErasing；兩者均從原 ImageNet 獨立初始化，先以 Seed1／2 篩選。解析度研究固定 Tiny／ImageNet、Seeds1／2／3；224／320 微批 32×累積2、512 為8×8，只有名目有效 Batch 同為64，不能當完全純解析度因果對照。

alpha025 只把來源內類別平滑抽樣 alpha 由0.5改0.25，三來源期望份額仍各1/3；512、8×8與其餘原配方保持。三 Seed 最佳輪8／15／5，完成13／20／12輪。匹配診斷另固定原512 Seed1最佳4輪與alpha025 Seed1最佳8輪，在 HAM／BCN、六個指定疾病的 Train／Validation 匹配小樣本，以相同512 Validation前處理、batch1、eval／inference_mode作一次既有診斷；不同最佳Epoch與便利樣本均限制因果解釋。

模型大小初篩只比較 Tiny／Base／Large 的512 Seed1既有最佳結果。三者採釘選 FCMAE ImageNet1K backbone及新七類head；Base 2×32、Large 1×64，LR1e-4、AdamW、WD0.05、alpha0.5、MixUp0.2及Min12／Max30／Patience5等沿用各正式契約。Large微批1的MixUp排列只能自配對，沒有跨圖混合；有效Batch64並未使其等同Tiny8或Base2的配對池。這是實用配置初篩，並非純架構消融。

模型比較與實驗結果

實驗完成狀態與整體比較

五組各三個 Seed，共 15／15 次正式訓練完成，合計 276 輪。13 次依早停規則正常結束；ResNet-18 Random 的 Seed 1、2 達 30 輪上限。MLP Seed 1 曾安全暫停後以同 Run ID 恢復，兩次嘗試未重算為兩個獨立 Seed。以下數據皆取各 Run 的最佳 Validation Robust Score 輪次。

表4.1 五組模型的三 Seed 整體 Validation 結果

模型

Robust

Accuracy %

Macro-F1 %

MLP R

0.3211 ± 0.0085

60.05 ± 0.60

36.29 ± 1.58

ResNet R

0.4854 ± 0.0272

68.81 ± 2.32

54.41 ± 4.50

ResNet IN

0.5733 ± 0.0204

74.61 ± 0.66

63.98 ± 1.47

V2 R

0.4458 ± 0.0161

63.59 ± 1.17

48.94 ± 0.87

V2 IN

0.6450 ± 0.0160

76.06 ± 1.12

68.32 ± 1.98

數值為平均 ± 樣本 SD，n=3。MLP R=MLP Random；ResNet=ResNet-18；V2=ConvNeXt V2-Tiny。

ConvNeXt V2-Tiny ImageNet 的平均 Robust 為 0.644987 ± 0.015979，為本輪最高；合併 Validation Accuracy 為 76.06% ± 1.12%、Macro-F1 為 68.32% ± 1.98%。MLP 的 Robust SD 最小，但平均亦最低，故變異小不等於分類效果最好。V2 Random 低於 ResNet Random，亦說明本輪結果不能只用架構新舊解釋。

圖4.1 五組模型的 Validation Robust Score 比較

如圖4.1，柱狀為三 Seed 平均、誤差棒為樣本 SD、黑點為獨立 Seed。差異應連同配方表解讀：MLP 使用較低解析度，ResNet 與 V2 的有效 Batch、抽樣、正規化及正則化不同。此表可比較已完成的整套基線流程，不能作為完全等條件的純架構排名。

表4.2 15 次正式訓練的最佳輪與停止紀錄

模型

Seed

最佳/完成

Robust

Train Loss

Val Loss

停止

MLP R

1

21/26

0.3285

0.9214

1.1280

早停

MLP R

2

6/12

0.3232

1.0846

1.1158

早停

MLP R

3

9/14

0.3118

1.0415

1.0892

早停

ResNet R

1

28/30

0.4791

0.6416

0.8950

上限

ResNet R

2

29/30

0.5152

0.6242

0.8716

上限

ResNet R

3

11/16

0.4619

0.8542

0.8995

早停

ResNet IN

1

6/12

0.5512

0.5886

0.7697

早停

ResNet IN

2

13/18

0.5772

0.4219

0.7605

早停

ResNet IN

3

16/21

0.5914

0.3573

0.8292

早停

V2 R

1

11/16

0.4276

1.3896

1.1793

早停

V2 R

2

15/20

0.4519

1.3452

1.2151

早停

V2 R

3

16/21

0.4580

1.3313

1.1807

早停

V2 IN

1

5/12

0.6629

0.9002

0.9520

早停

V2 IN

2

10/15

0.6397

0.7841

0.9739

早停

V2 IN

3

8/13

0.6323

0.8267

1.0089

早停

Train Loss 為含該配方增強／正則化的訓練 objective；Val Loss 按來源樣本數加權；早停為正常完成。

在上述 15 次基線之外，第一輪兩候選各完成 Seed 1、2，另有 4 次正式訓練、51 輪。四次均以 early_stopping 正常完成並保存最佳模型，但兩候選未通過研究篩選，沒有執行 Seed 3 或進入第二階段採納。以下基線表仍為 n=3；第一輪 n=2 結果另列於本章末段，避免混合分母。

來源差異與各類 Recall

表4.3 三來源 Validation Balanced Accuracy

模型

HAM %

BCN %

PAD %

MLP R

34.16 ± 1.26

29.39 ± 0.84

40.97 ± 0.68

ResNet R

59.17 ± 5.16

44.50 ± 2.67

54.07 ± 2.66

ResNet IN

68.64 ± 3.61

52.29 ± 2.39

66.15 ± 0.89

V2 R

54.69 ± 4.70

38.54 ± 1.27

58.63 ± 2.72

V2 IN

73.30 ± 2.49

60.84 ± 2.43

70.34 ± 1.35

全部 15 個最佳輪中，BCN 均為最低 BA 來源。V2 ImageNet 的 BCN 為 60.84%，低於 HAM 的 73.30% 與 PAD 的 70.34%。HAM 與 BCN 使用相同七類集合，兩者比較較直接；PAD 只評估五個支援類別，因此不能僅由 PAD 與其他來源 BA 大小推定拍攝域難度。

圖4.2 五組模型的三來源 Balanced Accuracy

整體各類 Recall 以合併混淆矩陣為基礎。為避免過寬表格壓縮範本 14 點字型，表4.4與表4.5分組列出七類；兩表的支持數均來自同一份 3,611 張 Validation，不是三 Seed 的張數加總。

表4.4 合併 Validation 各類 Recall（一，%）

模型

AKIEC

BCC

BKL

DF

MLP R

32.21 ± 8.11

72.85 ± 4.80

7.23 ± 4.35

0.65 ± 1.13

ResNet R

49.61 ± 4.39

79.15 ± 5.81

28.68 ± 9.41

20.26 ± 16.33

ResNet IN

64.31 ± 3.97

81.28 ± 5.87

40.15 ± 13.73

45.10 ± 5.88

V2 R

55.33 ± 1.08

61.81 ± 1.68

25.27 ± 2.45

24.18 ± 4.53

V2 IN

69.70 ± 1.75

78.22 ± 4.42

53.37 ± 3.43

47.06 ± 3.92

支持數（張）

297

577

401

51

表4.5 合併 Validation 各類 Recall（二，%）

模型

NV

VASC

MEL

MLP R

83.54 ± 1.32

20.93 ± 4.65

32.35 ± 1.14

ResNet R

83.47 ± 5.11

67.44 ± 9.30

54.81 ± 0.41

ResNet IN

90.26 ± 0.58

68.22 ± 6.71

50.20 ± 5.31

V2 R

82.05 ± 6.88

58.91 ± 11.93

41.90 ± 15.92

V2 IN

87.40 ± 3.00

80.62 ± 4.84

58.96 ± 3.03

支持數（張）

1736

43

506

來源：正式實驗結果總表.csv 與三Seed統計.csv；各值為三 Seed 平均 ± SD，支持數為固定切分的真值張數。

圖4.3 五模型各類 Recall 與跨 Seed 變異

V2 ImageNet 的 BCN 弱類別包括 DF、BKL、AKIEC 與 MEL。其 Recall 分別為 32.32% ± 6.31、46.22% ± 5.86、54.87% ± 3.54 與 56.91% ± 3.68 個百分點；支持數分別為 33、181、113、328。DF 平均較低但樣本少，不能僅憑少量樣本的單類峰值判定改善已穩定。

圖4.4 ConvNeXt V2-Tiny ImageNet 的分來源各類 Recall

PAD 的 MEL 只有 11 張，三 Seed 都命中 5 張，Recall 同為 45.45%。一張即影響 9.09 個百分點，因此 SD=0 僅表示同一固定小樣本上命中總數相同，不能證明命中影像相同或對其他患者穩定。PAD 的 DF／VASC 無真值支持，圖中不適用標示不能當作模型 Recall 為零。

圖4.5 ConvNeXt V2-Tiny ImageNet 的三來源平均混淆矩陣

混淆矩陣依 C 圖中標示的真值／預測方向解讀，三 Seed 平均與其標準化方式依原圖保留。錯誤分布可用於描述本輪誤分類現象，但未進行逐例品質或標籤人工複核，不能由矩陣直接確認影像品質、標籤錯誤或設備差異是原因。BCN 在 Robust 中的瓶頸作用屬評分公式下的觀察，不是本稿已完成的因果驗證。

第一輪結果進一步顯示，四次候選在相同 Seed 配對下均為 PAD BA 改善、BCN BA 下降。LR 候選平均 ΔBCN BA=−1.2118pp、ΔPAD BA=+1.5331pp；Layer Decay 分別為 −2.4645pp、+4.2056pp。當 BCN 持續為最弱來源時，其 BA 對 Robust 的權重為 2／3，HAM 與 PAD 各為 1／6；PAD 的正向貢獻不足以補償 BCN 的負向貢獻。pp 表示百分點，Δ 均為候選減相同 Seed 原基線。

疾病層級亦有 Seed 間抵銷。LR 的 BCN BKL 命中數差為 +15／−28（各 Seed 支持 181）；Layer Decay 的 BCN DF 為 −4／−1（支持 33），合併 MEL 為 +18／−43（支持 506）。Layer Decay 的 BCN VASC 命中差 −4／0（支持 21），平均 Recall 下降 9.5238pp；這是補充診斷，並非事後加入第一輪淘汰規則。沒有逐張對應預測，不能判定哪些病例獲改善，也未證實來源外觀、增強或抽樣是根因。

同架構初始化的配對比較

表4.6 ImageNet − Random 的同 Seed Robust 差

架構

配對數

差值（百分點）

ResNet-18

3

+8.789 ± 3.641

V2-Tiny

3

+19.918 ± 3.206

ResNet-18 的平均配對差為 +8.789 個百分點，V2-Tiny 為 +19.918 個百分點，均為本輪固定資料與同架構配方下的描述性結果。如圖4.6，三對 Seed 可觀察初始化差異的方向；由於兩架構的預訓練流程不同，不能把兩個差值大小當成純架構的預訓練效率排名。

圖4.6 同 Seed 的初始化配對差異

訓練曲線與停止行為分析

以下五張圖各含三個 Seed。左欄為 Train objective、Train monitor 與合併 Validation Loss，中欄為 Robust，右欄為三來源 BA；黑點與虛線標出選定最佳輪。曲線只畫實際已完成輪次，未向 30 輪上限外推，也不以訓練曲線估算 Test 表現。

MLP Random 的最佳／完成輪分別為 21／26、6／12、9／14。Seed 2 的最佳輪早於最少停止輪數，仍符合最佳權重保存規則。三 Seed 並未一致出現最佳輪後 Val Loss 上升，因此不宜一概描述為嚴重過擬合；低 Robust 與少數類別 Recall 是本輪直接觀察。

圖4.7 MLP Random 三 Seed 訓練曲線

ResNet-18 Random 的 Seed 1、2 最佳輪位於 28、29，均跑到 30 輪；Seed 3 最佳 11 輪、完成 16 輪。接近上限的最佳輪顯示停止預算會影響可觀察範圍，但尚不能證明增加輪數必然提高 Robust。

圖4.8 ResNet-18 Random 三 Seed 訓練曲線

ResNet-18 ImageNet 的最佳／完成輪為 6／12、13／18、16／21。C 的曲線交叉判讀顯示部分最佳輪後 Train monitor Loss 下降而 Val Loss 上升，符合後期過擬合跡象；此現象不足以單獨判定學習率、正則化或某項增強是原因。

圖4.9 ResNet-18 ImageNet 三 Seed 訓練曲線

V2 Random 的最佳輪為 11、15、16，完成 16、20、21 輪。最佳輪後 Train 及 Train monitor Loss 仍下降，Val Loss 亦小幅下降，但 Robust 未再突破前高，於 Cosine 原排 30 輪結束前早停。降低交叉熵與改善分類決策不等價，故不能直接宣稱已證明未收斂，或延長後必勝過 ImageNet。

圖4.10 ConvNeXt V2-Tiny Random 三 Seed 訓練曲線

V2 ImageNet 的最佳輪為 5、10、8，完成 12、15、13 輪。最佳至最終輪的 Train monitor Loss 由 0.627／0.533／0.561 降至 0.490／0.485／0.491，Val Loss 由 0.952／0.974／1.009 升至 1.001／1.038／1.021，Robust 分別下降 4.287／1.999／4.625 個百分點。這些相反趨勢支持最佳輪後的過擬合判讀，但沒有驗證其具體成因。

圖4.11 ConvNeXt V2-Tiny ImageNet 三 Seed 訓練曲線

V2 的訓練 objective 含 MixUp 與 Label Smoothing，且訓練影像採增強與加權抽樣；Train monitor 為分層 1,500 張訓練子集，Validation 為全量自然分布。因此三條 Loss 的絕對值不在完全相同的分布與目標上。此處以同一條曲線的前後趨勢與 Robust／來源 BA 一併判讀，避免把 Loss 差值過度解釋。

第一輪 LR 候選最佳輪均為第 5 輪；Seed 1 仍呈 Train monitor Loss 下降而 Validation Loss 上升，Seed 2 的 Validation Loss 略降，但 Robust 回落。Layer Decay 的最佳至停止 Robust 回落為 0.2029／0.2176pp，小於配對基線的 4.2873／1.9985pp，然而最佳 Robust 均值更低。此觀察僅支持後期變動較小，不能稱已消除過擬合或提升最佳分類能力；觀測輪次亦不完全等長。

訓練時間與比較限制

表4.7 各組實際累計訓練時間

模型

分鐘／Run

秒／輪

平均完成輪

MLP R

16.42 ± 8.38

55.8 ± 3.9

17.33

ResNet R

35.05 ± 7.72

85.6 ± 13.1

25.33

ResNet IN

32.19 ± 10.57

112.4 ± 7.6

17.00

V2 R

42.40 ± 4.39

134.4 ± 5.6

19.00

V2 IN

25.27 ± 2.37

113.9 ± 2.4

13.33

圖4.12 正式訓練時間與完成輪數

時間含 Validation 與 Checkpoint，排除初始化及停機。V2 ImageNet 平均 25.27 分鐘，比 Random 的 42.40 分鐘少 17.13 分鐘，但完成輪數亦由 19.00 降為 13.33。資料載入、資源占用與儲存狀態均可能影響計時；本輪未量測純 GPU 吞吐或推論成本，故不以總時間差宣稱效率優勢。

第一輪最佳化的個別最佳輪結果列於表4.8。LR 代表基礎學習率 5e−5，LD 代表 Layer Decay 0.9；其餘設定沿用原 V2 ImageNet。四次均為正常早停，未採納是研究篩選決策。

表4.8 第一輪四次正式訓練的最佳 Validation 結果

候選

Seed

最佳／停止輪

Robust%

BCN BA%

PAD BA%

LR

1

5／12

65.6091

61.5918

72.4168

LR

2

5／12

63.9243

59.8139

72.1365

LD

1

7／12

64.0780

59.1001

75.1465

LD

2

10／15

64.2848

59.8002

74.7519

來源：C 第一輪完整配對分析 JSON 的 runs；四次狀態均 completed，停止原因皆為 early_stopping。

篩選須採相同 Seed 分母，如表4.9。LR 的 Robust 64.7667% 雖高於完整三 Seed 基線 64.4987%，但其相同 Seed 基線為 65.1309%，實際平均配對差為 −0.3642pp；直接混用 n=2 與 n=3 會改變比較結論。

表4.9 第一輪與相同 Seed 基線的篩選統計

組別

Robust %

Accuracy %

Macro-F1 %

BCN BA %

原基線

65.1309± 1.6457

76.6131± 0.8420

69.3612± 1.1437

61.9146± 2.1992

LR

64.7667± 1.1914

76.3085± 1.2337

67.9509± 1.7479

60.7029± 1.2572

LD

64.1814± 0.1462

76.9870± 1.0574

68.5322± 0.2713

59.4502± 0.4950

Seed 1／2、n=2；平均 ± 樣本 SD（pp）。來源：C 第一輪結案統計 CSV。

表4.10 第一輪原定篩選門檻與實際判定

指標

門檻（pp）

LR 實測／判定

LD 實測／判定

平均 ΔRobust

> 0

-0.3642未通過

-0.9495未通過

平均 ΔBCN BA

> 0

-1.2118未通過

-2.4645未通過

平均 ΔMacro-F1

≥ 0

-1.4103未通過

-0.8290未通過

平均 ΔAccuracy

≥ -0.5

-0.3046通過

+0.3739通過

每 Seed ΔRobust

各 ≥ -1

-0.6855／-0.0430通過

-2.2166／+0.3175未通過

平均 ΔHAM BA

≥ -1

+1.1285通過

-0.0449通過

平均 ΔPAD BA

≥ -1

+1.5331通過

+4.2056通過

BCN DF ΔRecall

≥ -3

-1.5152通過

-7.5758未通過

BCN BKL ΔRecall

≥ -3

-3.5912未通過

+0.0000通過

BCN MEL ΔRecall

≥ -3

-0.6098通過

-2.7439通過

合併 MEL ΔRecall

≥ -1

+0.5929通過

-2.4704未通過

Δ=候選−相同 Seed 基線；除單 Seed 保護外，均為 Seed 1、2 平均差。數值顯示四位小數，原判定使用完整精度。來源：C 原門檻逐項核對.csv、B 兩份 decisions 篩選 JSON。

LR 未通過 Robust、BCN BA、Macro-F1、BCN BKL 四項；Layer Decay 未通過 Robust、BCN BA、Macro-F1、單 Seed Robust 保護、BCN DF、合併 MEL 六項。兩候選因此不採納，Seed 3 依門檻未執行，第二階段判定不適用。此結論只適用於本輪確切配方，不能概括所有較低學習率或 Layer Decay 均無效。

第一輪預算事件實耗 4,904.637565 秒（約 81.744 分鐘），包含 Train、Validation、Checkpoint 與指標提交，排除初始化及停機，並非純 GPU 核心時間。四個 Run 合計 51 輪，沒有 Resume。較短時間、較小 SD 或單一來源進步均未取代原定分類門檻；目前保留原 ImageNet 三 Seed 基線整組。

網站與 API 的 CPU 功能驗收

2026 年 10 月 25 日的本機功能驗收使用一張自製 320×240 幾何色塊 PNG，沒有病灶診斷真值。先確認首頁、樣式、選圖預覽及 GET health／models；兩個 GET 均回應 HTTP 200，execution_enabled 與 artifacts_metadata_ok 為 true，提供原 224 Seed1 與 E224。

同一張圖共執行兩次真實 POST，各模式一次且沒有重試：Seed1 直接呼叫 API；E224 由瀏覽器選圖後按下執行。Seed1 回應 HTTP 200、is_mock=false、device=cpu，七類機率皆為有限且介於 0 與 1，總和約為 1。E224 前端請求亦為 HTTP 200，既有 adapter 接受真實回應，畫面呈現七條機率及最佳輪 5／10／8、各權重 1/3 的三成員資訊。

驗收來源為 cpu_local_20261025_v1 的 REPORT.md、QA.json、api_qa.json 及 browser_qa.json。Seed1 原始回應保存於 seed1_response.json；E224 保存畫面 cpu_result.png 與七個完整精度 DOM value 屬性，未另存 E224 原始 HTTP JSON，因此 DOM 紀錄不能當成完整原回應。瀏覽器 error／warning 清單為空，當次視窗沒有水平溢出。

這兩次請求支持影像接收、正式權重載入、前處理、推論、JSON 契約與前端呈現的端到端功能；合成圖無真值，不能據其輸出回報辨識正確率、疾病 Recall、校準品質或正常皮膚辨識能力。此次沒有暖身、benchmark 或全量評估，也未以 CPU 功能通過推論 GPU 效能或新環境 GPU 一致性。

本次僅完成 localhost 的 CPU 功能驗收，尚未部署 Docker 或私人遠端連線。新環境 GPU 端到端、Grad-CAM、分數校準、正常皮膚／七類外疾病或輸入適用性判定及公開部署均未驗收完成；新 512 訓練成果不代表網站已換模。

第二輪最佳化結案

第二輪四個run共49完整Epoch，均正常早停；BCN50及RE0各完成Seed1／2但未通過原篩選，Seed3依決策未執行，不是訓練失敗。表4.11為候選減相同兩Seed基線，不能混用完整三Seed平均。

表4.11 第二輪相同 Seed 配對差（n=2，pp ）

候選

ΔRobust

ΔBCN BA

ΔAcc

ΔF1

BCN50

-0.5243

-1.0673

-0.9139

-0.5131

RE0

-1.7053

-2.4481

-0.4846

-0.7721

兩候選均未通過Robust、BCN BA、Macro-F1及單Seed保護；BCN50另未過Accuracy，RE0另未過DF。兩者BCN VASC平均Recall皆下降9.5238pp；RE0 DF下降3.0303pp，以完整精度未達−3pp底線。結論只適用於本輪配方，不能泛化為增加BCN曝光或取消擦除永遠無效。來源：第二輪 FINAL_RESULTS、decisions及研究歷史R2A；原C槽詳細報告缺件仍保留為追溯限制。

Tiny 解析度與 E224 既有結果

表4.12 Tiny 各尺寸三 Seed Validation 結果（%，SD為pp ）

尺寸

Robust

Accuracy

Macro-F1

224

64.4987 ± 1.5979

76.0639 ± 1.1223

68.3159 ± 1.9829

320

65.6747 ± 1.4523

76.3039 ± 1.8395

70.7296 ± 0.7801

512

67.2195 ± 0.0959

76.2854 ± 1.9524

70.3251 ± 1.6214

512−224平均Robust +2.7208pp、BCN BA +2.1407pp，但BCN VASC／NV及PAD NV Recall分別下降4.7619／8.1623／13.8889pp。512−320 Robust +1.5448pp，Accuracy／Macro-F1卻為−0.0185／−0.4045pp。512總分SD僅0.0959pp，合併MEL SD仍7.6652pp；小支持類別與疾病取捨不能被總分穩定掩蓋。全部沿用C完整九run比較與D判讀，未重計預測。

E224以原224三Seed最佳輪5／10／8，各類softmax機率固定各1/3平均，是一個固定系統的單次Validation結果，沒有三個獨立Ensemble Seed或SD。研究歷史V0ENS保存Accuracy78.6486%、Macro-F1 71.4591%、Robust66.9218%；來源HAM／BCN／PAD BA為75.6654／62.9338／74.1298%。相對Seed1，BCN BA下降0.5359pp、DF13→11/33、VASC18→16/21，不能宣稱各病種全面改善或已修復BCN瓶頸。原逐張CSV／完整JSON缺失未解除，本版引用已保存正式摘要，不重建其逐張結果。

alpha025 三 Seed 結果與不採納決策

表4.13 alpha025 與原512比較（n=3，%，Δ為pp ）

指標

原512

alpha025

平均Δ

Robust

67.2195 ± 0.0959

66.3112 ± 1.2021

-0.9083

Accuracy

76.2854 ± 1.9524

78.1409 ± 0.8898

+1.8554

Macro-F1

70.3251 ± 1.6214

71.3678 ± 0.4372

+1.0427

BCN BA

62.9780 ± 0.4698

61.4010 ± 1.8907

-1.5770

alpha025三Seed均正常完成，共45完整Epoch，但31個預定條件有7項未過，故不採納。三Seed Robust差為−0.0702／−2.4028／−0.2519pp，0/3提升；Accuracy +1.8554pp、Macro-F1 +1.0427pp的收益仍保留，不改作採納主目標。BCN BKL平均Recall−15.1013pp、VASC−3.1746pp、PAD BKL−12.7273pp，原門檻未放寬。

六個512／alpha最佳輪均以BCN為最低來源；此範圍內Robust=(HAM BA+PAD BA+4×BCN BA)/6。D已分解alpha差為HAM +0.0939pp、BCN−1.0514pp、PAD +0.0492pp，合計−0.9083pp。這確認指標的數值瓶頸，尚未證明造成BCN下降的單一訓練根因。來源：D root_cause_20261025_v1的完整數值、固定規則與100項既有QA。

342 張匹配 Train 與 Validation 診斷

既有retry1完成342個不同非Test影像，兩模型各342筆診斷，共684正式前向及6暖機；總75.453秒含載入與保存。原失敗0.953秒／0前向另存，不重複加總。本版只引用已完成輸出，未再讀研究影像或啟動模型。小樣本每層7–16張、只含HAM／BCN六類，六類平均不是正式七類BA或Robust。

表4.14 匹配診斷的代表性 TP/N（Seed1 ）

模型／來源／疾病

Train TP/N

Val TP/N

原512 BCN AKIEC

10/16

7/16

原512 BCN MEL

8/16

7/16

原512 BCN DF

9/10

6/10

alpha025 BCN DF

9/10

5/10

原512 HAM MEL

14/16

7/16

alpha025 HAM MEL

15/16

9/16

原512的BCN AKIEC與MEL在Train也只有62.5%及50%，不足以用「Train都學好，只是Val差」解釋。BCN DF兩模型Train皆90%，Val60%／50%，才有有限泛化落差線索；HAM MEL亦有明顯gap，不能直接當BCN專屬。BCN−HAM gap至少10pp未在兩權重主要弱類一致重現。這些為固定便利分組、Seed1與不同最佳Epoch的局部觀察，不保證患者獨立、不作顯著性或純alpha因果結論，更不能當Base／Large的Train細類證據。來源：B matched_source_trainval_512_20261025_retry1_v1及D後續解讀。

512 模型大小單 Seed 初篩與疾病取捨

Base與Large均已completed／early_stopping，共28完整Epoch：Base最佳6／完成12輪，Large最佳11／完成16輪；Tiny引用原512 Seed1最佳4／完成12輪。Huge僅依顯存估算略過，沒有實測品質、實測OOM或淘汰結果。下表是三個模型各一個Seed，不是n=3架構穩定性排名。

表4.15 512 單 Seed 最佳 Validation 結果（% ）

模型

Robust

Accuracy

Macro-F1

Tiny

67.1483

78.5378

72.1627

Base

69.2906

80.2271

74.2208

Large

67.7141

78.1224

72.6731

表4.16 512 單 Seed 三來源 BA（% ）

來源（N）

Tiny

Base

Large

HAM（1504）

78.6289

79.1411

77.3710

BCN（1712）

63.0332

66.2271

64.1252

PAD（395）

72.1279

71.6944

72.4129

Base對Tiny Robust +2.1424pp，其中BCN數值貢獻+2.1292pp；Accuracy／Macro-F1也升，但合併MEL命中302→262/506，Recall59.6838%→51.7787%（−7.9051pp）。Large對Base Robust−1.5765pp，合併MEL卻升至326/506（64.4269%）。Base是優先確認的實用配置，仍有疾病代價，尚未正式採納。

表4.17 512 單 Seed 重要疾病命中（每欄為TP ，支持數固定）

來源／疾病

N

Tiny

Base

Large

HAM MEL

167

101

85

119

BCN BKL

181

101

91

104

BCN DF

33

14

18

17

BCN NV

682

552

598

542

BCN VASC

21

13

17

14

BCN MEL

328

197

172

203

PAD BKL

55

39

34

41

PAD NV

48

41

39

38

PAD MEL

11

4

5

4

Base在BCN DF14→18/33、VASC13→17/21及NV552→598/682有收益，BKL101→91/181、MEL197→172/328與PAD BKL39→34/55卻下降；不能僅留總分而省略損失。PAD DF／VASC仍N/A；小支持數的單張影響不可當作患者母群穩定效益。完整21個來源×疾病TP/N及Recall均見D正式表，未將三模型合併成更多獨立病例。

圖4.13 Tiny／Base／Large 單 Seed  比較與已保存曲線

圖4.13 直接沿用D scale512_review_20261026_v1的comparison.png，涵蓋最佳輪指標、來源、BCN疾病及逐輪曲線；圖中Large恢復線不表示恢復造成最佳分數差，最佳輪11先於中斷。Base最佳後monitor仍改善但Robust回落4.8114pp，Large回落3.0126pp，並不能證明延長訓練必能改善。

表4.18 512 已提交輪與正式 attempt  耗時（分鐘）

模型

完整輪總時

attempt總時

配置峰值GiB

Tiny

76.881

N/A

4.8465

Base

147.718

147.920

3.7698

Large

341.900

391.405

5.0720

完整輪總時來自已提交metrics；attempt含初始化、退出及未提交工作，不可相加。Base與Large正式attempt合計32359.476秒；其中failed_attempt_seconds19365.831秒含Large已完成13輪，不能全稱浪費。配置峰值為torch CUDA allocated，非整卡占用或純實體專用顯存；Base較小峰值與微批不同有關，不能推論大模型省顯存。成本只引用D既有計帳，不新增測速。

Large在第14輪發生CUDA unknown error，使用者重裝驅動是時間背景，尚未證明唯一故障原因。第一次Resume另遇scheduler包裝函式不可序列化，該14輪未提交；Resume2修復存檔銜接後，同Run由完整13輪接14–16輪正常早停。原中斷、失敗attempt及恢復紀錄均保留；最佳11輪先於中斷，不能將Large低於Base直接歸因恢復破壞best。Persistent-worker RNG及驅動環境差異不保證未中斷反事實或逐位元重播。來源：B FINAL_RESULTS／B_HANDOFF及D NUMERIC_ANALYSIS／242項既有QA；本版未獨立重載Checkpoint驗收。

後續確認批次的狀態截點

2026 年 10 月 26 日本版來源核對時，v2_scale512_followup_20261026_v1正式state為running，active為Base Seed2；Base Seed3與Large Seed1 2×32仍待順序執行。這已超過D草案當時「待核定」的歷史狀態，但尚非完成研究。只記進度，不摘中途分數，不補Base三Seed平均、Large2成績或採納判定。後續狀態以正式state／MONITOR為準，文件截點不作即時監控。

結論與研究限制

已完成研究的結論

版本化資料治理與一致類別定義

本研究完成三來源七類資料定義，保留原始診斷與映射限制，並發布精確去重後的固定切分 Manifest。Train 18,919、Validation 3,611，封存 Test 1,502。可用分組與精確重複內容的跨 split 檢查支持已知規則下的資料隔離，但不擴大宣稱為完整患者隔離或近重複已全數排除。

五組三 Seed 正式基線比較

15次正式基線及其有效設定與逐輪紀錄均已保存；同架構ImageNet初始化在既定配方下有較高平均Robust。兩輪共四候選皆未通過原n=2篩選；原Tiny三Seed解析度平均Robust隨224／320／512為64.4987／65.6747／67.2195%，仍有NV等疾病取捨。alpha025三Seed正常完成但不採納。512 Base單Seed69.2906%值得確認，卻伴隨MEL代價，尚未採納或換入網站；不能將其與Tiny三Seed平均當配對排名。

來源與訓練行為的實證觀察

BCN持續為主要最低來源；Accuracy或Macro-F1進步未必提高Robust。342張匹配診斷發現部分弱類Train也偏低，部分類有Train／Val落差，HAM亦有gap，尚未鎖定單一根因。Base／Large的單Seed、微批MixUp及恢復環境限制仍須保留。

研究限制

資料隔離與來源涵蓋限制

HAM／BCN 缺 patient ID，現有隔離主要依病灶與既有群組；精確去重未涵蓋所有感知近重複。PAD 與其他來源的影像模態及類別支持集合亦不同。三來源皆參與訓練，本輪沒有以全新來源作外部驗證，因此不能把來源 BA 比較當成已完成的跨醫院泛化驗收。

配方差異與驗證集選擇偏差

跨架構的輸入尺寸、名目有效 Batch、抽樣與優化方式未完全一致，難以將差異單獨歸因於架構。第一輪雖為同基線的單因子變更，候選僅完成 n=2 篩選。Validation 同時用於最佳 Epoch、早停、比較及候選篩選，反覆使用可能累積選擇偏差；Test 持續封存，本稿沒有最終 Test 成績。

小樣本、亂數變異與恢復限制

三 Seed SD 只反映固定切分下的訓練變異，並未估計資料分割或患者母群的不確定性。PAD MEL 等小樣本的百分比容易受單張影像影響。Checkpoint 保留 Epoch 級恢復資訊，但 persistent workers 增強 RNG 不保證逐位元重播，不能將可恢復等同於所有執行軌跡完全一致。

研究結論的應用範圍

網站於 2026-10-21 為 Mock，2026-10-25 原 224 模式通過 CPU 功能驗收；不代表辨識品質、GPU 端到端、臨床或部署驗證。

參考文獻

[1] Esteva, A., Kuprel, B., Novoa, R. A., Ko, J., Swetter, S. M., Blau, H. M., & Thrun, S. (2017). Dermatologist-level classification of skin cancer with deep neural networks. Nature, 542, 115–118. https://doi.org/10.1038/nature21056

[2] Tschandl, P., Rosendahl, C., & Kittler, H. (2018). The HAM10000 dataset, a large collection of multi-source dermatoscopic images of common pigmented skin lesions. Scientific Data, 5, 180161. https://doi.org/10.1038/sdata.2018.161

[3] Hernández-Pérez, C., Combalia, M., Podlipnik, S., et al. (2024). BCN20000: Dermoscopic Lesions in the Wild. Scientific Data, 11, 641. https://doi.org/10.1038/s41597-024-03387-w

[4] Pacheco, A. G. C., Lima, G. R., Salomão, A. S., et al. (2020). PAD-UFES-20: A skin lesion dataset composed of patient data and clinical images collected from smartphones. Data in Brief, 32, 106221. https://doi.org/10.1016/j.dib.2020.106221

[5] He, K., Zhang, X., Ren, S., & Sun, J. (2016). Deep Residual Learning for Image Recognition. Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition (CVPR), 770–778. https://arxiv.org/abs/1512.03385

[6] Woo, S., Debnath, S., Hu, R., Chen, X., Liu, Z., Kweon, I. S., & Xie, S. (2023). ConvNeXt V2: Co-Designing and Scaling ConvNets With Masked Autoencoders. Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR), 16133–16142. https://arxiv.org/abs/2301.00808

[7] Deng, J., Dong, W., Socher, R., Li, L.-J., Li, K., & Fei-Fei, L. (2009). ImageNet: A Large-Scale Hierarchical Image Database. 2009 IEEE Conference on Computer Vision and Pattern Recognition, 248–255. https://doi.org/10.1109/CVPR.2009.5206848

[8] Yosinski, J., Clune, J., Bengio, Y., & Lipson, H. (2014). How transferable are features in deep neural networks?. Advances in Neural Information Processing Systems, 27, 3320–3328. https://proceedings.neurips.cc/paper_files/paper/2014/hash/532a2f85b6977104bc93f8580abbb330-Abstract.html

[9] Buda, M., Maki, A., & Mazurowski, M. A. (2018). A systematic study of the class imbalance problem in convolutional neural networks. Neural Networks, 106, 249–259. https://doi.org/10.1016/j.neunet.2018.07.011

[10] Brodersen, K. H., Ong, C. S., Stephan, K. E., & Buhmann, J. M. (2010). The Balanced Accuracy and Its Posterior Distribution. 2010 20th International Conference on Pattern Recognition, 3121–3124. https://doi.org/10.1109/ICPR.2010.764

[11] Torralba, A., & Efros, A. A. (2011). Unbiased Look at Dataset Bias. 2011 IEEE Conference on Computer Vision and Pattern Recognition, 1521–1528. https://people.csail.mit.edu/torralba/publications/datasets_cvpr11.pdf

專題工作配置與完成紀錄

已完成工作與成果位置

表7.1保留v2／v3的歷史產物列；網站列為2026年10月21日截點。第二輪結案及後續實驗／診斷已另補第4章，當前網站仍為原224模式，不能從研究進度推定自動換模。

表7.1 本稿使用的已完成研究產物

工作項目

正式產物與用途

資料準備

governed_18979_20261018_v1：映射、去重、固定切分與發布摘要

模型訓練

baseline_20261019_v1：五組、15 次訓練與設定快照

C 成果整理

snapshot_20261020_v1：統計工作簿、CSV、10 張比較／曲線圖

C 補充分析

cross_analysis_20261020_v1：混淆矩陣與 Recall 穩定性圖

E 報告製作

本 Word 初稿、範本格式稽核與來源清單

第一輪最佳化

v2_optimization_20261020_v1：4 次／51 輪；兩候選完成但未採納

C 第一輪結案

V2第一輪最佳化結案分析_20261020_v1：完整配對 JSON、原門檻與疾病 TP／Recall

網站前端展示

showcase_v1：預覽與固定 mock；尚未串接正式 V2 推論

歷史截點：2026年10月21日01:33時，第二輪BCN抽樣Seed1仍執行中；其後四run均已正常結束，兩候選篩選未通過、Seed3未執行。原running紀錄保留作時間追溯，不代表現況。

網站歷史截點（2026 年 10 月 21 日 01:33）：showcase_v1 已有選檔／拖放、預覽與結果頁籤，但只有固定 Mock，未連線正式 API／V2，也未串接 Grad-CAM；當時尚無整體瀏覽器驗收證據。

網站目前進度（2026 年 10 月 25 日）：Python 內建 HTTP 服務與 PyTorch 已接上原 224 Seed1／E224；一張自製圖完成兩次真實 CPU 請求，各模式一次。三個 API 用途見第 3 章，驗收見第 4 章及 cpu_local_20261025_v1，僅支持功能，不代表辨識品質。

服務限 localhost；Docker、私人遠端連線、公開部署、新環境 GPU 端到端與 Grad-CAM 尚未完成。網站維持原 224 權重，512 訓練不等於網站換模。

完成時程與追溯方式

2026 年 10 月 18 日完成本輪資料發布與訓練前置紀錄；10 月 19 日啟動五組基線，MLP Seed 1 暫停後恢復；10 月 20 日基線完成，C 發布快照與補充分析。同日第一輪最佳化完成四個新 Run，兩候選均依門檻淘汰，C 發布結案研究分析。10 月 21 日依最新紀錄更新本報告；這些是實際紀錄，不是未來進度計畫。

v2 保存的動態狀態截點為 2026 年 10 月 21 日 01:33（臺北時間）：第二輪記錄為 running；當時網站展示頁已有原始檔，但未取得正式 V2 串接或完整驗收證據。資料與第一輪數據來源及雜湊仍沿用 v2 隨稿來源清單，Test 維持封存。

v3 於 2026 年 10 月 25 日補入網站實作與 CPU 功能驗收，來源為現有程式及當日 QA。未重執行 API、推論、訓練或 Test，訓練數值、圖表與文獻維持 v2。

v4於2026年10月26日整合第二輪、Tiny解析度與E224、alpha025、342張診斷及Base／Large單Seed比較，來源與版本見隨稿對照。後續Base2／3及Large2配置批次仍進行中，不列完成成績。