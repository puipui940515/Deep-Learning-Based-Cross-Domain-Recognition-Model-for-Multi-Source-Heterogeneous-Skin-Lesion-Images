# 上一批512訓練完成結果整理

日期：2026-10-26臺北。範圍：v2_scale512_followup_20261026_v1。總控直接整理B已保存的FINAL_RESULTS、BASE_CONFIRMATION_SUMMARY及LARGE_MICRO2_DIAGNOSTIC；未重跑訓練、推論、完整Validation、權重hash或D研究分析。這批仍是原GELU架構；後續ReLU＋Stage Dropout研究另案計帳，不混入本批結果。

## 結論

本批3個新run全數正常Early Stopping完成，共37完整Epoch、正式attempt耗時35057.7291689秒（約9.74小時）、失敗attempt耗時0。Base Seed1沿用既有成果，未重訓；Tiny三Seed與Large舊1×64亦只引用。

Base補齊三Seed後，平均Robust67.1042%，原Tiny512為67.2195%，差−0.1153個百分點；Base Seed1最高69.2906%未在其他Seed重現。Base的Robust跨Seed sample SD為2.0520個百分點，Tiny為0.0959個百分點（均n=3，不能把三次標準差視為所有未來訓練波動保證）。Base的Accuracy與Macro-F1提高，但合併MEL Recall平均下降9.2885個百分點，未達本批原開訓前凍結的採納比較條件。

Large改2×32後單SeedRobust提高0.3824個百分點，合併MEL Recall提高5.9289個百分點；BCN DF／VASC及PAD BKL等則下降。這是有取捨的單Seed訊號，不足宣稱全面改善或正式採納；不能把差異全部歸因於MixUp。

## Base／Tiny同Seed Robust

|Seed|原Tiny512|Base512|Base減Tiny（百分點）|
|---|---:|---:|---:|
|1|67.1483%|69.2906%|+2.1424|
|2|67.3285%|65.2202%|−2.1083|
|3|67.1816%|66.8016%|−0.3799|
|三Seed平均|67.2195%|67.1042%|−0.1153|
|sample SD（百分點）|0.0959|2.0520|—|

## Base／Tiny三Seed平均完整主要指標

|指標|原Tiny512|Base512|Base減Tiny（百分點）|
|---|---:|---:|---:|
|Robust|67.2195%|67.1042%|−0.1153|
|Accuracy|76.2854%|79.1747%|+2.8893|
|Macro-F1|70.3251%|73.0776%|+2.7525|
|HAM BA|77.8843%|78.2018%|+0.3175|
|BCN BA|62.9780%|63.0897%|+0.1117|
|PAD BA|73.5204%|72.0644%|−1.4560|
|合併MEL Recall|65.1515%|55.8630%|−9.2885|
|HAM MEL Recall|71.2575%|59.6806%|−11.5768|
|BCN MEL Recall|62.5000%|54.3699%|−8.1301|
|BCN DF Recall|41.4141%|47.4747%|+6.0606|
|BCN VASC Recall|69.8413%|71.4286%|+1.5873|
|BCN BKL Recall|58.3794%|54.8803%|−3.4991|

白話：Base整體答對張數及平均類別F1增加，但來源間的類別平衡表現沒有同步上升，MEL辨識還有損失。Robust看各來源BA的平均與最弱來源，與整體Accuracy衡量方式不同，兩者可以往不同方向變動。以上屬已保存結果的算術解讀，尚未判定其訓練機制根因。

BASE_CONFIRMATION_SUMMARY既有31項數值檢核中10項未通過：robust_mean、robust_seed_count、robust_seed2、PAD BA、BCN BKL／MEL、合併MEL、HAM MEL、BCN AKIEC、PAD MEL。這些是本批開訓前凍結的比較／採納條件，不是本次新增的訓練強停門檻；不回頭放寬、不自動採納或換網站。

## Large Seed1：只改micro1×累積64為micro2×累積32

|指標|舊Large1×64|新Large2×32|新減舊（百分點）|
|---|---:|---:|---:|
|Robust|67.7141%|68.0964%|+0.3824|
|Accuracy|78.1224%|78.9809%|+0.8585|
|Macro-F1|72.6731%|73.1450%|+0.4719|
|合併MEL Recall|64.4269%|70.3557%|+5.9289|
|HAM BA|77.3710%|81.2875%|+3.9166|
|BCN BA|64.1252%|63.2671%|−0.8581|
|PAD BA|72.4129%|74.2228%|+1.8099|
|BCN DF Recall|51.5152%|39.3939%|−12.1212|
|BCN VASC Recall|66.6667%|57.1429%|−9.5238|

另PAD BKL Recall −14.5455個百分點、HAM NV −2.6839個百分點、PAD NV −6.25個百分點。既有Large單Seed保護檢核6項未通過，Robust增幅亦未達原+1pp訊號條件，所以numeric_signal_for_further_validation=false；具體研究結案由D判讀，不說Large永遠無用。

兩者effective batch都是64，但microbatch大小會影響MixUp配對與隨機歷程；舊Large1×64亦有驅動重裝／恢復背景。故這次只能比較兩個已保存執行結果，不能宣稱純MixUp因果或多Seed穩定提升。Large新配置只有Seed1，不自動追加Seed2／3。

## 本批新run與計帳

|新run|Run ID|完成／最佳Epoch|Robust|正式attempt秒數|
|---|---|---:|---:|---:|
|Base Seed2|5e4892aab71a4cdab15858051da413f2|12／6|65.2202%|10163.830506|
|Base Seed3|8001e75b4f034432bd4750a9cac48d4b|13／8|66.8016%|9983.525697|
|Large Seed1 2×32|8a97e53c4da04749b98e24ec721bb117|12／5|68.0964%|14910.372965|

正式attempt時間含本run初始化及各phase，不將Epoch或phase再次加總。總額不含舊Base Seed1／舊Large／Tiny基準及ReLU研究前檢；本批failed_attempt_seconds=0。01:22:39啟動、11:06:59臺北結案（2026-10-26），正常完成不代表研究方案自動採納。

## 固定條件與界線

Train18919／原Monitor1500／Validation3611，governed_18979_20261018_v1，七類順序／前處理／釘選FCMAE ImageNet1K權重沿原契約；AdamW、LR1e-4、WD.05、alpha.5、LS.1、MixUp.2、RE.15、AMP、有效batch64及Min12Max30Patience5等均保留。Base只補Seed；Large只變micro及accumulation。封存Test未使用。

Base三Seed現在齊全；Large仍只有單Seed。既有B算術已完成，D尚未針對本批作正式完整判讀。本摘要未另提新配方、未變更ReLU研究或啟動其他Thread。

## 直接來源

- 資料治理與泛化修復/results/v2_scale512_followup_20261026_v1/FINAL_RESULTS.json
- 資料治理與泛化修復/results/v2_scale512_followup_20261026_v1/BASE_CONFIRMATION_SUMMARY.json
- 資料治理與泛化修復/results/v2_scale512_followup_20261026_v1/LARGE_MICRO2_DIAGNOSTIC.json
- 資料治理與泛化修復/results/v2_scale512_followup_20261026_v1/B_HANDOFF.md
- 資料治理與泛化修復/configs/v2_scale512_followup_20261026_v1/EVALUATION_CONTRACT.json

MONITOR最後更新11:06:59臺北，控制器已結束，現在僅是已結案快照；不要把README啟動時的「尚未生成結果」當作最新狀態。未修改B原README或正式result。