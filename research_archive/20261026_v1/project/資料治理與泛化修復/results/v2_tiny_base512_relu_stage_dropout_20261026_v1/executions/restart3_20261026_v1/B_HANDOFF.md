本批狀態：paused。Tiny512三Seed後Base512三Seed，僅ReLU＋四Stage後Dropout=.1組合變更。RunID／完整與最佳輪／停止原因／指標見FINAL_RESULTS；各模型對原架構同Seed的mean/sampleSD與TP/N/Recall見TINY_COMPARISON及BASE_COMPARISON（若齊全）。完整命令／配置／架構audit／run_inputs／metrics／best／雙代Checkpoint／失敗與計帳均保留。交總控供D判讀，不自動採納或追加研究，不作獨立因果／Test宣稱。
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
