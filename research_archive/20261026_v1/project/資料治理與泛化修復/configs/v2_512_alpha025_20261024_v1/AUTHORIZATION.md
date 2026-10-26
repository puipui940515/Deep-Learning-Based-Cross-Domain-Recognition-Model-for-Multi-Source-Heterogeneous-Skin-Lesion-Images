# v2_512_alpha025_20261024_v1：本次核定來源

來源：本 C chat 使用者 2026-10-24 的直接指派。以下原文保存，為本輪新來源，不沿用舊授權SHA。

核定並請落盤本輪唯一候選：v2in_res512_alpha025。
工作目錄 D:\SkinDetect_base。先讀AGENTS.md、docs\PROJECT_STATE.md、docs\V2_EXPERIMENT_HISTORY.md最新段落，以及：
recovery_20261023\D_v2_analysis\resolution_decision_20261024_v1\DECISION.md
以其v2完整配方、第4節採納規則、末尾v2補充及v2.1為準。
以原configs\v2_resolution_20261021_v1\v2in_res512.json及原512 run_inputs為基底，唯一科學差異為class_balance_alpha：0.5→0.25。維持512、Seeds1/2/3、微批8×累積8、LR1e-4、AdamW、WD.05、LD1、LS.1、MixUp.2、RE.15、AMP、Workers4、Min12/Max30、Patience5、MinDelta0、Cosine Tmax30及原Robust選模規則。各Seed從同一釘選ImageNet backbone獨立初始化，不接續舊best.pt。
新增版本化configs\v2_512_alpha025_20261024_v1，保存候選JSON、suite、核定來源、唯一差異、完整生效與評估契約；同名已有則先核對，禁止覆寫。工作量一候選、三Seed、最多90完整Epoch，不設時間硬上限，不移用舊預算或授權SHA。
沿用原governed release與七類契約。依原Train計數確認來源份額仍各1/3，列出alpha改動的期望曝光；不讀影像或Test、不重新分析品質。採納規則包含HAM/BCN NV各不降且至少一者提升、PAD NV不降，以及D既定其他保護條件。
只作JSON、來源與差異核對，不啟模型或GPU。新ID尚未註冊、runner尚未支持等事項列為交B處理的相容需求，不冒稱啟動已通過，也不因此拒絕交付配置。不要改B程式或正式舊配置。
完成後直接回報配置絕對路徑、唯一差異、給B的相容清單，然後停止。

## 授權界線

候選配方、三Seed工作量與評估規則已核定。本次C只獲配置落盤／CPU JSON核對授權，未獲本輪模型或GPU執行授權；suite的formal_training_authorized=false表示此執行界線，不表示候選配方尚待核定。B須依其當次適用執行指派處理新版本相容、當下資源與執行紀錄；不能把本文件SHA當舊gate已通過。
