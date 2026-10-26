# 512原配方／alpha025逐輪診斷｜2026-10-25

本輪只整理保存的84個完整Epoch數字：原512三Seed39輪、新alpha025三Seed45輪。未重算任何預測、混淆矩陣或既有停止規則；沒有模型載入、GPU、推論、Train/Test影像存取。原224／320的81輪診斷不重做。

## 核心結論

六個run在被選最佳輪後，混合Train monitor BA繼續上升、monitor loss繼續下降，而Validation Robust全部下降；BCN BA也全部下降。這支持「已觀察區段的訓練樣本擬合持續、Validation尤其BCN未跟隨」；沒有支持整個模型連Train都學不起來的普遍欠擬合解釋。

**但現有monitor是混合來源、按來源×疾病輪流抽取的1500筆Train子集，不是各來源內Train指標。** 因此巨大的monitor−BCN Validation差距不能單獨證明BCN域偏移、完整Train全部擬合良好、或特定少數疾病被記住；需要一個來源×疾病匹配的Train/Validation診斷才能判別。

## 保存數值：最佳輪到停止輪

表中BA／Robust為%，差值為pp。monitor是確定性eval視圖，仍含Label Smoothing loss；不是訓練增強／MixUp下train_loss。

|配方/Seed|最佳→停止|monitor BA最佳→停止|Robust最佳→停止|ΔBCN BA|monitor loss最佳→停止|ΔBCN Val loss|
|---|---|---|---|---:|---|---:|
|alpha050 S1|4→12|92.6005→98.3506|67.1483→64.5490|-3.9221|0.6302→0.4906|0.1319|
|alpha050 S2|10→15|97.6167→99.1667|67.3285→66.1672|-1.6887|0.5089→0.4704|-0.0537|
|alpha050 S3|7→12|95.3161→97.6238|67.1816→61.4675|-6.9248|0.5570→0.5075|0.0060|
|alpha025 S1|8→13|95.4829→98.6157|67.0781→62.9342|-4.9043|0.5533→0.4902|0.0396|
|alpha025 S2|15→20|98.9371→99.5665|64.9257→63.8795|-1.0094|0.4778→0.4635|0.0117|
|alpha025 S3|5→12|93.0153→98.0197|66.9297→62.4545|-6.7303|0.6167→0.5011|0.0781|

六run的84輪中BCN每輪均為最低BA來源；不只是最後選定best才呈現這個瓶頸。各來源局部最高BA出現於不同輪，不能事後各挑一個Epoch拼成不存在的模型；本報告仍只引用原Robust選定best，不重新選模。

## 最佳輪時的Train monitor與來源Validation

|配方/Seed|monitor BA|HAM Val BA|BCN Val BA|PAD Val BA|monitor−BCN（pp）|BCN最低loss輪|Robust最佳輪|
|---|---:|---:|---:|---:|---:|---:|---:|
|alpha050 S1|92.6005|78.6289|63.0332|72.1279|29.5673|4|4|
|alpha050 S2|97.6167|76.7333|62.4831|77.3055|35.1336|4|10|
|alpha050 S3|95.3161|78.2907|63.4177|71.1277|31.8984|3|7|
|alpha025 S1|95.4829|82.1015|62.2214|71.4817|33.2615|2|8|
|alpha025 S2|98.9371|77.1296|59.2387|75.4701|39.6984|3|15|
|alpha025 S3|93.0153|76.1120|62.7429|74.4945|30.2724|3|5|

BCN最低Validation loss在新alpha三Seed為2／3／3輪，Robust最佳輪為8／15／5；原512最低loss輪為4／4／3，Robust最佳輪為4／10／7。Loss的最小值與Robust最佳不同，是訓練／評估目標不等價的實際例子，不是停止規則bug。新Seed2從較早loss最低後仍到15輪才取得最好Robust，也反駁「只要Val loss回升就立即停，必可提高Robust」的簡單策略。

## Loss、monitor及LR的實際語意

必要靜態來源為資料治理與泛化修復/scripts/train_regularized.py：stratified_limit（153–170）、monitor_rows（約410）、DataLoader（約458）、criterion（535）、evaluate（216–230）、MixUp train_epoch（234–269）、每輪評估／record（614–645）。準確行號可依當前檔Select-String定位；歷史runtime版本／source hash一致性由本次static_audit子報告核對，不用當前源碼自動替代歷史證據。

- monitor_rows = stratified_limit(train_rows, min(1500,len(train_rows)), seed+3)。它按(source,label)分組後循環取樣，並非Train原始頻率，也不是新alpha sampler抽出的同一分布。
- monitor_loader以train=False、val_transform、shuffle=False；evaluate使用model.eval/inference_mode。沒有隨機Train crop、ColorJitter或MixUp。monitor和Validation的前處理相同，但成員、來源組成及類別權重不同。
- monitor與Validation共用CrossEntropyLoss(label_smoothing=.1)，所以它們都是LS eval loss；training train_loss額外含Train增強、model.train及MixUp混合目標，不能直接以二者數值差判定欠擬合或過擬合。
- 現有train_validation_gap = 混合monitor BA − 各來源Validation BA。這不是來源內Train/Val差，不能把欄位名稱當已取得域偏移證據。
- 新alpha最佳輪LR約8.7286e-5／5.5674e-5／9.5721e-5；停止輪約6.5796e-5／3.0367e-5／7.0633e-5。LR不是0；尚未觀測到Cosine最後低LR區段，不能推定未來必然恢復、也不能證明延長沒有可能。此事本身不構成Patience8或改LR的有效性證據。

## 對可干預原因的限制與反證

|解釋|既有曲線支持程度|反證／未確認部分|
|---|---|---|
|普遍欠擬合／模型完全沒有學到Train|不支持：monitor在最佳輪已約93–99%，停止輪約98–99.6%|monitor只有混合1500筆、來源內Train未保存；不能排除BCN某疾病自身Train仍差。|
|訓練樣本擬合與Validation脫鉤／過擬合表現|六run都觀察到monitor繼續改善、Robust與BCN BA變差|這是趨勢描述，不證明是某一增強、LR或標註造成；部分來源loss下降而BA變差，不能全概括成loss單調上升。|
|BCN共同瓶頸／來源落差|BCN是全部84輪最低BA，且best時Val BA遠低於混合monitor|來源內Train BA、類別匹配與Group條件缺失，尚不能把差距全部歸因域偏移或圖像難度。|
|只是多跑Epoch即可達80|沒有直接證據，全部best後觀測Robust回落|尚未觀測的Epoch不能臆測；不能以未觀測的可能性替代可否證診斷。|
|alpha=.25修復來源問題|不支持：新三run的BCN仍始終最低；主品質配對由主報告結案|不能從曲線推定alpha是唯一根因，或對所有其他alpha均無效。|

## 建議交父報告整合的一項B診斷

使用既有原512 Seed1 best.pt，對來源×疾病分層的已見Train與未見Validation匹配子集，用完全相同eval前處理作一次有界推論；無訓練、無Test、不按預測挑樣。BCN每類可固定20 Train與20 Validation，HAM/PAD每有支持類固定10+10，完整指令／預算由主報告統一決定，不由本子報告另行執行或授權。

可觀察現象：若BCN的Train DF/BKL/MEL/VASC已高而其Val顯著較低，支持來源內泛化／病例分布不匹配優先；若相同疾病Train和Val都低，且HAM同類能學好，優先查BCN表徵／標籤語意／曝光或前處理，而不是一律增加Patience。若各來源匹配Train/Val都接近，現有混合monitor差的組成效應是重要反證。這是樣本層級診斷，不用小子集作新正式績效、顯著性或80%可達性宣稱。

## 產物與實際執行

- CURVE_DIAGNOSIS.json：全部六run的來源SHA、best/first/last、source minima與已保存數字的必要算術。
- curves_84_epochs.csv：本輪必要的84輪小型數字表，非逐張預測。
- curves_512_alpha025.png/.svg：已實際視覺檢查，標注新舊最佳輪，不重做舊224/320圖。
- analyze_curves.py、write_report.py：本輪僅標準庫JSON/CSV與既有Matplotlib CPU繪圖；沒有torch匯入。

工作目錄D:/SkinDetect_base；執行命令：

```powershell
.\.venv-skindetect-recovery-20261023\Scripts\python.exe -B -X utf8 .\recovery_20261023\D_v2_analysis\root_cause_20261025_v1\curves\analyze_curves.py
.\.venv-skindetect-recovery-20261023\Scripts\python.exe -B -X utf8 .\recovery_20261023\D_v2_analysis\root_cause_20261025_v1\curves\write_report.py
```

只寫本curves子目錄，不改共用索引、配置、原result/metrics/權重或其他角色產物。完成停止。

### 同輪補充：BKL曲線證據與更聚焦的下一個診斷

讀保存best.train_monitor.recall_per_class：原512三Seed混合Train monitor BKL Recall為90.5350/97.5309/97.5309%，新alpha為87.6543/99.1770/88.8889%；同時新BCN Validation BKL只有38.1215/51.9337/39.7790%。新Train monitor VASC仍99.3827/100/97.5309%。這提供反對「整個BKL/VASC完全沒有擬合能力」的更直接證據；但依然是跨來源聚合，不能代替BCN各自的Train Recall。原值另存monitor_class_details.json，未由預測重新計算。

與父報告瓶頸合併後，單項B診斷可更聚焦為：**固定原512 Seed1與alpha025 Seed1的兩個best.pt，在HAM/BCN兩來源的BKL/VASC/NV/MEL，以相同eval前處理對匹配Train／Validation作一次對照**。每來源類別先限定16個不同可得group、每group一圖；N_s,c=min(16,該來源類別Train/Validation可用group數)，Train/Val各取同N。最大2來源×4類×16×2split=256張不同影像、兩checkpoint共最多512次前向。按固定hash/record排序選group，不看分數／錯誤選樣；病例ID缺失、group不等於完整患者隔離的限制必須保留。此聚焦建議取代上節較寬的三來源範圍，避免本輪產生第二項任務。

預先診斷方向（不是正式採納門檻或統計顯著性）：若BCN BKL Train≥80%、Val明顯較低且gap≥20pp，HAM匹配差距較小，支持BCN來源內泛化／病例分布問題為下一個主要假說；若BCN Train也低，或Train/Val差≤10pp，反對「BCN已學會但只是Val域差」足以解釋，需優先查表徵／語意／曝光。N16一張就是6.25pp，必須同報TP/N、不得用小子集宣稱普遍因果。alpha相對原512若BKL Train維持而Val降、NV兩split升，偏向泛化／邊界交換；Train也降才較支持曝光／擬合不足。完整預算／停止／命令由父報告統一，不在子工作執行或下發。