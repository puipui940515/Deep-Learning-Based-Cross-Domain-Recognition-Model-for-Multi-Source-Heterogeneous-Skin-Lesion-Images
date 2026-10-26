# 唯一下一步：512來源×疾病匹配Train／Validation診斷（提案，未授權執行）

## 要區分的主要假說

H1：BCN的目標疾病在Train已被良好擬合，但在同前處理的Validation表現明顯較差；低Robust主要反映類別條件的來源內泛化落差，並非整個模型普遍沒有學到Train。

H2：BCN相同疾病在Train也低；混合Train monitor的高BA掩蓋了來源內擬合不足／曝光／表徵或標籤語意問題。此時「BCN已學會、只是Val域差」不能作充分解釋。

現有1500張混合monitor不能區分兩者。以下是一次固定權重的分層評估，不是新訓練、不是驗證80%可達性、不是恢復原逐張CSV或全量預測。

## 給B的可完整複製指令

> 在D:\SkinDetect_base，先讀AGENTS.md、docs\PROJECT_STATE.md、docs\V2_EXPERIMENT_HISTORY.md、recovery_20261023\D_v2_analysis\root_cause_20261025_v1\REPORT.md與本B_DIAGNOSTIC_TASK.md。本段只有使用者明確核定後才生效；本輪D沒有執行或代發。
>
> 只作一次有界、無梯度的來源×疾病匹配Train/Validation評估。固定原512 Seed1最佳輪4與alpha025 retry1 Seed1最佳輪8兩份best.pt：
> 1. 資料治理與泛化修復/results/v2_resolution_20261021_v1/runs/v2in_res512/regularized_seed1/best.pt。
> 2. 資料治理與泛化修復/results/v2_512_alpha025_20261024_v1/executions/retry1_20261024_v1/runs/v2in_res512_alpha025/regularized_seed1/best.pt。
> 身分、run_id、前處理與已通過載入收據沿用各原run_inputs與B artifacts，不先重做模型hash、CPU/GPU合成小測或原資料小測。兩權重是已知不同選模Epoch的既有系統，不把它們的差異當成只改alpha且完全隔離Epoch的機制證明；固定Seed1避免再依結果挑Seed，不將單Seed診斷冒充n=3結論。
>
> 只從governed_18979_20261018_v1的Train+Validation mixed_manifest挑HAM10000及BCN20000的AKIEC/BKL/DF/VASC/NV/MEL，共12個source×class層。每層Train與Validation各取相同k個不同可得split_group，k=min(16,Train可用group數,Validation可用group數)，每group最多1圖；按source/class/split/group/record_id固定排序，在讀圖或看分數前鎖定清單。患者ID缺失時只稱病灶／可得group，不能說患者獨立。保留所有缺group、缺檔與解碼失敗，不用模型正確性替換樣本，不為湊數重複group；無法安全組成某層時列N/A並回報。
>
> 最高24個split層×16=384張不同非Test影像，兩權重用完全同一批，每權重每圖僅1次前向；最多768次計時外正式診斷前向。必要warm-up每權重最多3次，使用已鎖定清單第一張、從評估統計排除；總前向最多774。這個未執行的未來範圍須使用者另核定，不能拿D本輪24張影像檢視授權直接執行它。不要開test.csv或Test影像，不使用PAD或Train原始頻率加權，不重建全量3611張預測。
>
> 模型eval/inference_mode、全程無梯度／反向／optimizer／scheduler step，512 RGB及各正式Validation Resize/Normalize，無隨機Train增強、無MixUp、無TTA／校準／閾值搜尋；batch1、workers0、逐模型獨立程序，只佔單GPU一個模型。精度沿用既有正式AMP契約並明示，不為提高分數切精度。單次既有forward檢查不重跑；診斷的兩份權重載入本身屬此任務必要推論，不新增訓練驗收前置。
>
> 保存每source/class/split的TP/N/Recall、每模型各來源的六類等權Recall平均、Train−Val各類與均值差、HAM與BCN差異，以及BKL到NV/MEL/AKIEC、DF到BCC、MEL到NV等本小樣本的真實去向。可保存每張七類機率與真類margin作診斷來源，但只留本機，不公開逐圖metadata。保留來源與清單，不能將此次子集分數取代原正式Validation指標、重新選Epoch或作採納。
>
> 執行前一次確認當前B排程／程序、GPU／RAM／Commit與輸出磁碟metadata，沿用當次使用者已核定且適用的資源政策；不干預F CPU服務或普通應用，不為此改Windows／pagefile，不擅自恢復已被使用者撤銷的執行中資源強停。新診斷工作量上限是上述2模型／384影像／774前向，另建1800秒含初始化與存檔的診斷硬上限（待核定，非恢復一小時訓練上限）；逾時保存partial與未完成項，不自動重試／增加樣本／換Seed。OOM、NaN/Inf、類別／資料／權重／前處理契約不符、I/O或清單隔離失敗立即停止並保留失敗收據，不能跳過失敗宣稱完成。沒有現在執行此任務的授權時，只回報待核定，不啟模型。
>
> 新產物只放recovery_20261023/B_training/matched_source_trainval_512_20261025_v1（已存在則新版本），包含鎖定清單、兩權重／原run身分、有效前處理、完整命令、每圖本地分數、分層表、程序／資源／前向計數與時間、partial或完成收據。不得改正式資料、配置、Checkpoint、舊結果或共用入口，不安裝／下載，不發其他chat。完成後按B→總控→D交回，不開訓、不自動增廣實驗或新Ensemble。

## 預先約定的可觀察現象／否定方法

- **支持H1的有限證據：** 主要弱類（BKL/DF/AKIEC）BCN Train Recall高於或等於80%、Val低於或等於65%，且Train−Val≥20pp；若相同類的BCN gap比HAM至少大10pp，增加「BCN特定來源／病例分布落差」的支持。需展示逐類TP/N，不用混合monitor替代。兩checkpoint方向相同才稱重現於這一Seed的兩個系統。
- **否定H1作為充分解釋：** 主要弱類BCN Train也≤70%，或matched Train−Val≤10pp；轉而優先查來源內擬合、有效曝光與類別表徵／語意，不能繼續說BCN已學會只是Val太難。介於兩界則明標不充分，不能強分勝負。
- **區分alpha變化：** 若alpha BKL的Train、Val皆下降，較支持來源內曝光／擬合／決策邊界重分配；若Train維持高而Val下降，較支持泛化落差。NV與MEL是否同時上升、BKL錯分去向是否集中須以本任務真實配對表支持；這些仍不證明唯一因果。
- N≤16時1張即至少6.25pp，閾值只是事先固定的診斷讀法，不是統計顯著性或模型採納門檻。只取一Seed／便利分層不能外推全部患者。即使H1獲支持，仍需另訂能改變它的單因素研究；本任務不自動授權後續訓練。

**唯一任務只選上述matched source Train/Val。** 不同時加入梯度／權重更新、幾何TTA、增強消融、測速或Patience實驗；本次其他子報告中的未執行診斷線索不另列並行工作。
