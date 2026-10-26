# Large同Run一次Resume授權

2026-10-25使用者原文：「因為我剛剛重裝驅動，可以直接繼續執行沒關係」。總控Thread 01a16a74-3356-7701-acf2-12096d5c2599依明確代辦授權交本B續行；共用PROJECT_STATE／V2歷史MASTER-LARGE-RESUME-AUTHORIZED:20261025:v1有同一來源。不是另一個模型或新初始化授權。

唯一對象：v2_scale512_seed1_20261025_v1／v2in_scale512_large／Seed1，Run ID 7c6b140d4ed442389852be8707d8e2c6。最新完整且有效Checkpoint第13輪接續第14輪；不使用best.pt僅載模型、不換run_id、不重置已完成13輪／最佳11輪／bad_epochs2。最新13不符或完整性／契約衝突則停止，不擅自退到12或從零。

保持Large512、1×64、alpha.5、LR1e-4及全部原資料／增強／AMP／Optimizer／Cosine／Robust規則；Min12 Max30 Patience5 MinDelta0 Tmax30 eta_min1e-6、首次最高Robust；總Large最多30完整Epoch，不設時間硬上限。不改2×32、不追加Seed／候選、不重跑已完成Base、不跑Huge／Test或已通過GPU微批預檢。

允許必要當下排程／CUDA恢復最小確認、原Checkpoint checksum與完整Resume契約核對、一次可追溯Resume啟動／監控／計帳銜接。沿用原train_regularized.py --resume、CheckpointStore及model/optimizer/scheduler/scaler/RNG/sampler/loader/best/early-stopping恢復；persistent worker不保證逐位元重播。

保留原failed state／attempt／STOP／日誌／gate／來源、未完成14輪及全部實耗。只有本次授權／failed狀態／完整性核對通過後，把root STOP原檔移存到版本化歷史，不能刪原失敗證據。僅新啟動與監控適配可變；不修改舊frozen source/config/gate或放寬資料／Checkpoint檢查。失敗即保存停止，沒有自動第二次Resume或重新初始化。

沿用原啟動資源政策、原STOP／整輪非有限／Checkpoint保護，不新增執行中資源門檻，不改套件、驅動或Windows、不干擾F CPU服務。重裝驅動為使用者提供原因背景，不當成已證明的唯一根因。

開始後確認實際batch前進，恢復同root每15秒MONITOR.md；回報同Run ID、checkpoint13、起始14、PID／日誌／最後時間。B只更新自己的既有工作目錄；兩共用入口由總控處理。成功啟動後由外部程序按剩餘原run執行，不追加研究。
