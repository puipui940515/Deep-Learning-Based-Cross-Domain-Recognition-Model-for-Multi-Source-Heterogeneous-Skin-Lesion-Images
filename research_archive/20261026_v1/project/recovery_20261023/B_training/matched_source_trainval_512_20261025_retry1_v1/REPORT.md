# 來源×疾病匹配 Train／Validation 診斷

更新：2026-10-25T12:58:28.564303+08:00；狀態：completed；總耗時：75.453秒。

固定原512 Seed1 best Epoch4、alpha025 Seed1 best Epoch8；同一鎖定清單、512 RGB Validation前處理、AMP float16、batch1/workers0、eval/inference_mode。
本次為使用者明確授權的retry1；沒有訓練、梯度／optimizer／scheduler step、TTA、校準、Test、自動追加重試或網站換模。

|模型|來源|疾病|Train TP/N|Val TP/N|Train−Val pp|預先固定讀法|
|---|---|---|---|---|---|---|
|original512|BCN20000|AKIEC|10/16|7/16|18.75|Train也≤70%|
|original512|BCN20000|BKL|13/16|11/16|12.50|中間／不充分|
|original512|BCN20000|DF|9/10|6/10|30.00|H1有限支持|
|original512|BCN20000|VASC|7/7|4/7|42.86|H1有限支持|
|original512|BCN20000|NV|14/16|15/16|-6.25|gap≤10pp，H1不足|
|original512|BCN20000|MEL|8/16|7/16|6.25|Train也≤70%|
|original512|HAM10000|AKIEC|15/16|13/16|12.50|中間／不充分|
|original512|HAM10000|BKL|16/16|13/16|18.75|中間／不充分|
|original512|HAM10000|DF|11/11|7/11|36.36|H1有限支持|
|original512|HAM10000|VASC|15/15|13/15|13.33|中間／不充分|
|original512|HAM10000|NV|15/16|15/16|0.00|gap≤10pp，H1不足|
|original512|HAM10000|MEL|14/16|7/16|43.75|H1有限支持|
|alpha025|BCN20000|AKIEC|13/16|8/16|31.25|H1有限支持|
|alpha025|BCN20000|BKL|14/16|8/16|37.50|H1有限支持|
|alpha025|BCN20000|DF|9/10|5/10|40.00|H1有限支持|
|alpha025|BCN20000|VASC|7/7|5/7|28.57|中間／不充分|
|alpha025|BCN20000|NV|16/16|14/16|12.50|中間／不充分|
|alpha025|BCN20000|MEL|12/16|8/16|25.00|中間／不充分|
|alpha025|HAM10000|AKIEC|16/16|10/16|37.50|H1有限支持|
|alpha025|HAM10000|BKL|16/16|11/16|31.25|中間／不充分|
|alpha025|HAM10000|DF|11/11|8/11|27.27|中間／不充分|
|alpha025|HAM10000|VASC|15/15|14/15|6.67|gap≤10pp，H1不足|
|alpha025|HAM10000|NV|16/16|15/16|6.25|gap≤10pp，H1不足|
|alpha025|HAM10000|MEL|15/16|9/16|37.50|H1有限支持|

六類等權來源均值、BCN−HAM gap、alpha−原512同圖差與完整預測去向另見SUMMARY.json及各CSV。
逐張七類機率／true logit margin：original512_predictions.jsonl、alpha025_predictions.jsonl；僅留本機，不公開逐圖metadata／原圖。
清單：locked_manifest.csv；抽樣可得group與缺項：selection.json、exclusions.csv；原權重身分／前處理：model_inputs.json。
實際命令／逐模型PID／預算／完成或失敗：launch.json、各model_receipt.json、RECEIPT.json；錯誤另見各stderr.log及failure.json。
limits：最多384不同非Test圖、每模型每圖一次、每模型最多3次warmup、總前向≤774、總時間含載入與保存≤1800秒；不自動重試。

## 證據限制

- Seed1 only; original best epoch4 versus alpha025 best epoch8; no isolated alpha causal effect
- Deterministic convenience groups, not random population sampling; N<=16 and 1 image >=6.25pp
- Available lesion/split groups do not establish patient independence
- Six selected classes and two sources only; not full-source BA or formal Robust
- Diagnostic thresholds are predeclared readings, not significance or adoption criteria

本次只供總控交D依原假說判讀；不是正式採納、不保證根因唯一，不自動追加實驗／新訓練。
## 可重現命令（已執行，不得重複啟動）

```powershell
Set-Location 'D:\SkinDetect_base'
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -u -X utf8 'recovery_20261023\B_training\matched_source_trainval_512_20261025_retry1_v1\diagnose.py'
```
模型子程序完整argv保存於launch.json；原正式訓練來源／Checkpoint均未改。

## B交回總控的觀察摘要（供D判讀，非採納結論）

- 本次完成342個不同非Test影像，兩模型各342筆結果；684正式診斷前向＋6暖機＝690次，總75.453秒含載入／存檔。兩模型strict載入、相同清單／前處理／精度，沒有partial或失敗，沒有再次啟動。原失敗0.953秒／0前向另存，不重複加總。
- **原512的BCN Train也偏低：** AKIEC為10/16（62.5%），Val7/16（43.75%）；MEL為8/16（50%），Val7/16（43.75%）。這兩類不能用「Train都學好、只是Val低」充分解釋。
- **兩模型均有Train高、Val低的BCN DF：** Train均9/10（90%），原512 Val6/10（60%）、alpha Val5/10（50%），gap30／40pp，符合D原先的有限H1讀法。
- **alpha的BCN AKIEC／BKL亦有明顯gap：** AKIEC Train13/16（81.25%）→Val8/16（50%）；BKL Train14/16（87.5%）→Val8/16（50%）。原512 BKL則13/16→11/16（81.25%→68.75%，gap12.5pp），未通過同一H1門檻，列中間／不充分。
- **不能直接視為BCN專屬：** HAM的MEL兩模型也呈Train高、Val低（原14/16→7/16，alpha15/16→9/16）；DF亦有gap。主要弱類的「BCN gap比HAM≥10pp」只見alpha DF（+12.7273pp），沒有在兩模型重現；完整BCN−HAM表須保留。
- 本匹配小樣本BCN BKL由原Train81.25%／Val68.75%變為alpha87.5%／50%，呈現Train未降、Val下降；這僅是已保存同圖比較，不證明alpha的唯一機制。兩個checkpoint的最佳Epoch4與8不同，不能隔離Epoch影響。

每split層實際k為7–16（BCN DF10／VASC7；HAM DF11／VASC15；其他16），一張影響6.25–14.29pp；不是隨機患者樣本、只有Seed1、無患者獨立性保證，不作顯著性、n=3、全Validation或因果外推。六類均值不等同七類BA或正式Robust，不替換原正式分數。

輸出核對：OUTPUT_QA.json確認兩模型record順序／342個可得group一致、684筆機率有限且正規化、分層TP/N與逐張資料吻合、24個model×source×class配對完整；13份原失敗小檔案（包括鎖檔）與CPU預存指紋一致。本次QA只讀既有輸出，沒有再次開圖／載模型／前向或hash大型權重。

後續只交總控供D依原假說判讀；B本次結束，不追加模型、樣本、Seed、實驗或正式訓練，不直接聯絡其他Thread、不改共用研究索引或網站。

必要CPU／輸出核對完整命令亦保存在README.md：

```powershell
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -X utf8 'recovery_20261023\B_training\matched_source_trainval_512_20261025_retry1_v1\prepare_cpu.py'
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -X utf8 'recovery_20261023\B_training\matched_source_trainval_512_20261025_retry1_v1\verify_saved_outputs.py'
```
