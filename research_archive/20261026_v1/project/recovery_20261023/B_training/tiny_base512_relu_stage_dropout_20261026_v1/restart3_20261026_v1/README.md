# restart3：Windows Checkpoint IO修復與一次替代啟動

2026-10-26臺北；使用者直接授權本次必要純IO修復、CPU真實路徑驗證，以及Tiny Seed1一次新初始化替代啟動，再依序完成其餘五job。完整授權RESTART_AUTHORIZATION.md；不是Resume、不挪用舊資格、不自動無限重試。

結果及15秒活監控：`資料治理與泛化修復\results\v2_tiny_base512_relu_stage_dropout_20261026_v1\executions\restart3_20261026_v1`。原root／restart1／restart2的失敗、STOP、來源、gate、計帳與Run ID全部保留，沒有覆寫任何正式Checkpoint；本次使用獨立execution及一次啟動標記。

## 修復與必要驗證

training_state.py唯一IO變更：同目錄暫存名稱由「完整目標檔名＋UUID＋.tmp」改為 `.atomic-<32位UUID>.tmp`。同目錄、exclusive create、flush／fsync、os.replace、finally清理不變；CheckpointStore格式／雙代／CRC／index commit point／原恢復與契約保護完全不改，未改Windows設定。IO修復前來源保留before，初始化程式逐字比較確認僅這一行差異。

IO_VALIDATION.json實際通過6個隔離位置，逐一對應六job正式路徑，位置比正式目錄更深14字元；只使用微型CPU tensor完整狀態payload，不建模型、不讀圖、不碰正式Checkpoint。原最長暫存名稱266字元；修復後最長隔離暫存241字元，正式暫存更短。共78次真實fsync與78次同目錄atomic replace；測試覆寫、寫入中斷仍保留舊target、三代輪替只留3/2、index、best匯出與覆寫／讀回、完整CPU payload讀回、契約不符拒絕及刻意損壞小型fixture後回退上一代，再原子還原fixture。舊正式文件沒有被覆寫。CPU測試約1.849秒。

Tiny／Base既有CPU架構、預訓練映射、eval與Checkpoint結構證據，及restart2原train_epoch實際GPU更新證據，均透過REUSED_EVIDENCE.json引用，SHA／套件版本與模型／原訓練來源適用性確認；**本次未重跑任何GPU前檢、模型測試或benchmark**。只新增以上必要純IO驗證及新execution准入／計帳。

新gate SHA：**1769708696f2673eaa253de60c926dc1df77c9c1c4c02ccaf46e14b7922c74f3**；配置／比較契約／有效來源與證據已凍結，副本在sources_runtime（沿用已處理的Windows延伸路徑封存IO）。正式運行中不更換來源或科學設定。

## 生效配方與預算

仍只ReLU＋四個完整Stage後一般Dropout .1；Tiny18／Base36 Block、GRN／尺寸／原七類head結構不變。原governed Train18919／Monitor1500／Val3611、512 RGB、完整原前處理及七類順序；釘選本機FCMAE ImageNet1K／revision／SHA不變。AdamW LR1e-4 WD.05 LD1、alpha.5、來源各1/3期望份額有放回、LS.1 MixUp.2 RE.15 clip1 AMP、Workers4／prefetch4／persistent不變。Tiny8×8、Base2×32。

單GPU Tiny S1→S2→S3，再Base S1→S2→S3。各新Run ID、新建指定Seed七類head、空optimizer／新scheduler／scaler；不接舊best／last或前檢權重。同Seed新head SHA可與原初始化相同，代表可重現初始化，不是Resume。Min12 Max30 Patience5 MinDelta0 CosineTmax30 eta_min1e-6，首次最高Validation Robust，無時間硬上限。

REPLACEMENT_ACCOUNTING.json明列原失敗正式Run **9b38f8536746431b84a42f25d307569b**，完整提交0輪、attempt534.1421076999977秒另帳；其未提交Epoch425.7672619819641秒包含其中，不再相加。此次明確增加1次Tiny1替代啟動；原6模型／Seed任務及最多180**已提交**Epoch不增加。含原失敗最多7次歷史正式啟動；本新execution只准6次各job一次，沒有任意新retry。FINAL_RESULTS會分列原失敗與本次attempt，以及不重複加總的歷史合計。

## 真正啟動與查詢

13:30:43啟動控制器。Tiny Seed1新Run ID：**f49f7c0aa4644917839363f44e3d1d3d**；已讀真正run_inputs確認CUDA與initial_optimizer_state_entries=0、原預訓練及新head。實際trainer PID **5336**（venv外層7532），controller PID **23192**（venv外層4080）；PID可被Windows重用，應與本Run／命令／父子關係一起判讀。13:31:14狀態running、其餘5job pending、當時完整Epoch0，首輪正式Checkpoint仍待提交，不把啟動當完成。

真正開訓前原資源政策通過：Commit餘裕62.19997GiB、RAM可用17.9724GiB、GPU1%、空閒10910MiB、D可用385.2868GiB，無衝突；每job啟動前仍原檢查並保存attempt。沒有新的資源／RAM／每批梯度強停，不干擾F CPU、不安裝下載、不改Windows／網站或讀Test。原train_epoch之loss÷累積／AMP／clip／更新流程不動。

工作目錄D:\SkinDetect_base，已執行命令：

```powershell
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -X utf8 'recovery_20261023\B_training\tiny_base512_relu_stage_dropout_20261026_v1\restart3_20261026_v1\initialize_io_restart.py'
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -X utf8 'recovery_20261023\B_training\tiny_base512_relu_stage_dropout_20261026_v1\restart3_20261026_v1\validate_checkpoint_io.py'
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -X utf8 'recovery_20261023\B_training\tiny_base512_relu_stage_dropout_20261026_v1\restart3_20261026_v1\finalize_io_gate.py'
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -u -X utf8 '資料治理與泛化修復\scripts\run_v2_relu_dropout.py'
```

以上已執行，**不要重跑啟動**。LAUNCH_ONCE／state／study及run鎖防重複。Tiny1 token f431d0973f6a49d691f9c21993e3559d，完整argv／stdout／stderr在state及attempts，原失敗字節保留。唯讀查詢：

```powershell
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -X utf8 '資料治理與泛化修復\scripts\run_v2_relu_dropout.py' --status
Get-Content -LiteralPath '資料治理與泛化修復\results\v2_tiny_base512_relu_stage_dropout_20261026_v1\executions\restart3_20261026_v1\MONITOR.md' -Encoding UTF8
```

MONITOR每15秒真實更新六job／Run ID／狀態／完整及最佳輪／即時批次、分段耗時／顯存。首輪後才有完整實測耗時／估時／峰值，首輪初始化限制明列。各run依原流程保存有效配置／run_inputs／逐輪metrics／best及雙代Checkpoint；比較僅各模型三Seed對原同架構同Seed，mean/sampleSD／來源疾病TP/N/Recall交總控供D，不自動採納或追加研究。

新真正執行異常照原CUDA／整輪非有限／Checkpoint／契約／程序規則保存STOP／完整原因及實耗後停止，不自動重試、Resume、換batch或配方。正常結束保存FINAL_RESULTS／B_HANDOFF；沒有完成前不得把本啟動文當訓練結案。對話中斷先讀當前execution狀態與Run ID，不因聊天idle重啟外部程序。B不聯絡其他Thread、不改共用索引，結案後停止。

## 首個完整Epoch與正式保存確認

2026-10-26 13:38臺北：Tiny Seed1 Run f49f7c0aa4644917839363f44e3d1d3d已實際提交Epoch1，進入Epoch2。checkpoints/index.json、Epoch1完整Checkpoint、best.pt、逐輪metrics及budget committed=true一致；只讀保存的JSON與檔案大小，未重新hash或載入大型權重。首輪訓練366.685秒、Monitor18.723秒、Validation50.111秒、Checkpoint0.811秒、整輪436.360秒；資料等待12.494秒含於訓練，CUDA配置峰值4.197GiB／保留4.457GiB。首輪數值含初始化影響，尚不能當穩態平均。詳細收據FIRST_EPOCH_CHECKPOINT.json。

本輪僅1個完整Epoch，六Run尚未完成；既有controller持續依核定順序執行其餘工作，MONITOR每15秒更新。不得因對話結束重啟或重跑本次一次啟動入口。

## 2026-10-26 使用者主動暫停（非六Run完成）

總控轉達使用者「可以先暫停訓練吧？Robust掉了很多，也請一起幫我看會是什麼原因造成的。」並於19:52:37建立本execution STOP。B沿原STOP機制等待當輪完成，沒有kill或改來源／配方；Tiny Seed3第4輪與完整Validation、metrics／Checkpoint／budget均提交後，trainer於2026-10-26T19:56:33.701583+08:00已exit0，state原值paused／active=null，19:56:55首次唯讀確認controller23192／4080、trainer5640／25688及原20個workers全數退出。GPU模型已釋放（快照NVIDIA GeForce RTX 5070, 0 %, 1115 MiB, 12227 MiB）；不干擾F／普通桌面程序。

|Run|原生狀態|Run ID|完整／最佳Epoch|最佳Robust|原因|
|---|---|---|---|---|---|
|tiny_seed1|completed|f49f7c0aa4644917839363f44e3d1d3d|30/28|48.266341%|max_epochs|
|tiny_seed2|completed|951d46aece144af2a7aa9dc6b0b0f145|30/28|55.765803%|max_epochs|
|tiny_seed3|paused|d920dd58fbc144ea96ab652d8eac526c|4/1|15.238095%|user_requested_pause_at_complete_epoch|
|base_seed1|pending|未建立|0/—|—|未啟動；後續派送授權已撤回|
|base_seed2|pending|未建立|0/—|—|未啟動；後續派送授權已撤回|
|base_seed3|pending|未建立|0/—|—|未啟動；後續派送授權已撤回|

三個Tiny保留best與雙代：Seed1輪30/29（best28）、Seed2輪30/29（best28）、Seed3輪4/3（best1）；具體檔名、完整路徑／大小／原生descriptor、run_inputs／metrics在USER_PAUSE_RECEIPT_20261026_v1.json，未hash或反序列化大型權重，不宣稱已驗證Resume。Base三Seed沒有run資料夾／Run ID／attempt。完整提交合計64輪，未提交／active輪0，沒有浪費中的部分輪。

本成功execution三次attempt實耗23147.763552秒；本次機械failed_attempt_seconds=0。Tiny3人工暫停attempt 1508.351795秒，trainer內elapsed另見收據，為包含關係不得相加。原restart2失敗Run9b38f8536746431b84a42f25d307569b、534.142108秒／0提交Epoch／原STOP及來源仍獨立保留；歷史合計23681.905660秒。所有phase／epoch耗時含於attempt，不重複加總。

FINAL_RESULTS與原B_HANDOFF由controller自然產生，狀態paused，原值未改寫；這是使用者主動暫停，非CUDA／Loss／Checkpoint故障，不是六Run完成。Tiny3僅4輪未達Min12，不與兩個完整Seed混作正式三Seed結案。MONITOR現在為終止快照，不再稱每15秒活更新。B只核對保存與退出，完整原因分析由總控讀既有證據處理，未新增推論／訓練／評估／benchmark。

STOP保留；後續訓練／派送授權已撤回。等待使用者新指示，不自行Resume、重試、刪STOP或開Base。不修改共用研究索引、不聯絡其他Thread。
