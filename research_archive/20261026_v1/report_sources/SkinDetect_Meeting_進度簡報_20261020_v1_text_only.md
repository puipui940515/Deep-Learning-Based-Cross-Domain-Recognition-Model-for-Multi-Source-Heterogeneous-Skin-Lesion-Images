# Office文字擷取發布副本

原件未公開；不含圖片／版面／Word欄位，可恢復正文文字但不能還原原生格式。原研究時態與版本截點保留，不重寫成目前狀態。

## ppt/slides/slide1.xml

SkinDetect 專題進度

正式基線與 V2 第一輪最佳化

指導教授:[PERSON_REDACTED]

成員:[PERSON_REDACTED]、[PERSON_REDACTED]、[PERSON_REDACTED]

Meeting　2026.10.20

15 次基線訓練完成

第一輪 4 次訓練完成，兩候選未採納

## ppt/slides/slide2.xml

資料與版本

正式資料已完成治理，三來源共用固定切分

研究用途，不構成醫療診斷

02

HAM 七分類，共用版本 governed_18979_20261018_v1

來源

Train

Validation

HAM10000

7,007

1,504

BCN20000

10,221

1,712

PAD-UFES-20

1,691

395

合計

18,919

3,611

已完成

統一標籤與病灶分組

跨切分已知重複檢查

固定 Manifest 供所有正式組使用

Test 1,502 張持續封存

HAM／BCN 缺患者 ID，病灶級隔離仍有限制；PAD 的 DF／VASC 無樣本，評估記為 N/A

來源：正式 release README、C baseline snapshot_20261020_v1。版本名稱保留歷史數字，實際 Train 為 18,919。

## ppt/slides/slide3.xml

正式基線

五組、15 次正式訓練，V2 ImageNet 為目前最佳基線

研究用途，不構成醫療診斷

03

64.50%

Robust，n=3

樣本 SD 1.60pp

Accuracy　76.06%

Macro-F1　68.32%

BCN BA　60.84%

後續以此組為優先基線

來源：C 正式基線統計與原圖（15 runs，Seeds 1／2／3）。R＝Random，IN＝ImageNet。配方不同，屬整套流程比較。

## ppt/slides/slide4.xml

V2 第一輪設計

第一輪以單一變因檢驗後期表現回落

研究用途，不構成醫療診斷

04

觀察依據：基線最佳輪後，Train monitor Loss 降、Validation Loss 升，Robust 回落

候選

唯一變更

要檢驗的假設

降低 LR

1e−4 改為 5e−5

減小更新幅度是否改善後期退步

Layer Decay

1.0 改為 0.9

較早層用較小 LR 是否保留預訓練表徵

兩候選各自從原始基線設定出發，沒有疊加

每組先跑 Seed 1、2，通過既定門檻才進入 Seed 3

實際完成 4 次正式訓練、51 Epoch，程序均正常結束

來源：B 正式配置／EXPERIMENT_STATE.md、C 第一輪結案分析。Layer Decay 指逐層 LR 衰減，Weight Decay 維持 0.05。

## ppt/slides/slide5.xml

V2 第一輪結果

兩個候選均未通過相同 Seed 的採納門檻

研究用途，不構成醫療診斷

05

全部限定 Seed 1、2（n=2），取各 Seed 最佳 Validation Robust 輪；括號為候選－配對基線

組別（n=2）

Robust

Accuracy

Macro-F1

BCN BA

PAD BA

原基線

65.13%

76.61%

69.36%

61.91%

70.74%

LR 5e−5

64.77%

(-0.36pp)

76.31%

(-0.30pp)

67.95%

(-1.41pp)

60.70%

(-1.21pp)

72.28%

(+1.53pp)

Layer Decay .9

64.18%

(-0.95pp)

76.99%

(+0.37pp)

68.53%

(-0.83pp)

59.45%

(-2.46pp)

74.95%

(+4.21pp)

兩組的 Robust、BCN BA、Macro-F1 均未達主要門檻

額外未過保護條件：LR 的 BCN BKL；Layer Decay 的單 Seed Robust、BCN DF、合併 MEL

來源：C 基線 n=3 與配對 n=2 分列統計、原門檻逐項核對。篩選未過，兩候選 Seed 3 均未執行。

## ppt/slides/slide6.xml

來源瓶頸

PAD 改善，但 BCN 下降抵銷了效益

研究用途，不構成醫療診斷

06

三來源 BA 的配對平均差（候選－相同 Seed 原基線，pp，n=2）

BCN 是最低來源

15 個基線最佳模型

皆呈現相同來源瓶頸

BCN 對 ΔRobust 的貢獻

LR：−0.81pp

Layer Decay：−1.64pp

Robust＝0.5 × 三來源 BA 平均 ＋ 0.5 × 最低來源 BA

來源：C 同 Seed 配對差異、Robust 差異來源分解、正式基線分析。BA 為各來源支援類別的 Recall 平均。

## ppt/slides/slide7.xml

訓練曲線

Layer Decay 減少後期回落，未提高最佳成績

研究用途，不構成醫療診斷

07

正式 Robust 曲線，只比較同 Seed 原基線與 Layer Decay 候選

Seed 1

峰值至停止回落：基線 4.29pp／候選 0.20pp

Seed 2

峰值至停止回落：基線 2.00pp／候選 0.22pp

後期較平穩，仍未提高最佳 Robust 或修復 BCN

來源：C 完整逐輪資料.csv、最佳輪至停止輪診斷.csv。最佳輪及觀察長度不同，未推測停止後表現。

## ppt/slides/slide8.xml

弱類別分析

疾病層級的平均值可能掩蓋 Seed 間得失

研究用途，不構成醫療診斷

08

Δ命中數＝候選－同 Seed 基線；兩 Seed 使用相同 Validation 病例

疾病／範圍

支持數／Seed

LR 5e−5

Seed 1／2

Layer Decay .9

Seed 1／2

DF（BCN）

33

−1 ／ 0

−4 ／ −1

BKL（BCN）

181

+15 ／ −28

+13 ／ −13

MEL（BCN）

328

0 ／ −4

+12 ／ −30

MEL（三來源合併）

506

+4 ／ +2

+18 ／ −43

BKL 的 Layer Decay 平均變化為 0，實際是 +13 與 −13 抵銷

DF 僅 33 例，少量命中差便影響 Recall；目前沒有逐張配對預測可定位錯分病例

來源：C 來源疾病 TP／支持數／Recall、來源疾病同 Seed 配對差異。此處為總命中數差，非獨立病例新增數。

## ppt/slides/slide9.xml

進度與後續方向

下一步聚焦 BCN，第二輪方案仍待核定

研究用途，不構成醫療診斷

09

已完成，保留正式結果

資料治理與固定 Manifest

五組基線，15 次正式訓練

第一輪兩候選，4 次訓練與結案

保留原 V2 ImageNet 三 Seed 基線

第二輪提案，待核定／未執行

優先候選：提高 BCN 抽樣份額

HAM／BCN／PAD：.25／.50／.25

另一獨立候選：RandomErasing .15 改 0

候選、門檻與新預算皆待核定

尚待釐清：DF→BCC、MEL→NV 的分類瓶頸與錯分原因

會議討論：是否同意以 BCN 為主問題，審閱第二輪方案後再決定執行？

狀態來源：V2_EXPERIMENT_HISTORY.md R0／R1／P2，2026-10-20。第二輪僅為研究方向，沒有改善成績。