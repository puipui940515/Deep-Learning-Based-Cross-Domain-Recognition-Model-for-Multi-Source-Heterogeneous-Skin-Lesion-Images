# RECOVERY GAPS

這是公開程式與研究紀錄快照，加九份已完成MLP／ResNet小型best.pt，不是完整電腦或完整可重現資產備份。

可取得：最新程式／網站原始碼、各實驗凍結sources、核定與生效配置、逐輪數值、結果／混淆矩陣、失敗／暫停／實耗證據、既有分析與兩份已看過的數據圖、去識別正式報告文字及實際使用者MD源稿。

仍缺：完整dataset與Train／Validation／Test逐張清單、醫療影像、預訓練與訓練權重／完整Optimizer Checkpoint、venv與外部runtime／驅動、私人服務／登入備份、Word v4與Meeting PPT的原生格式與媒體。原C/D歷史遺失分析／逐張分數仍缺，OCR轉錄不能當原件；不重新產生研究結果。

缺權重與資料時，不能靠本庫直接重現推論或恢復訓練。保留的Checkpoint index SHA僅既有引用，沒有本輪重新hash大型權重；source manifest hash不提供成員資料。環境requirements不是已重建環境的證明。

正在訓練檔案只保存讀取時完整JSONL行／可解析JSON，逐檔時間列manifest。跨檔不是原子快照，已排除目前224 ampwin的state/metrics/輪次；歷史running字樣仍可能來自舊凍結來源，狀態與指標可能不同步；不能把部分Epoch當完整結果或自動Resume。源碼可能在B作業時更新，source_sha與已凍結snapshot區分，不能把current程式說成每個舊run的實際版本。

Google Drive僅已建目的資料夾，完整備份尚未上傳或驗證。所有外部資料／私有內容需另行授權的私人備份；不因這次公開Git增量推送自行執行。

excluded清單說明原件未上傳原因，未對原醫療媒體做視覺檢查。Word/PPT以ZIP metadata與正文XML審閱，文字副本遮蔽封面個人姓名與私人路徑；原件未更動。原上游QA hash指正式原件，不能直接驗證sanitize後發布副本；兩種hash見manifest。

本次最後核准補入九份MLP／ResNet最佳輪權重，逐檔SHA與用途見WEIGHTS_README.md／WEIGHT_SIZE_AUDIT.json；其餘大型模型、所有完整Resume Checkpoint與資料本體仍缺。
資料集名稱／來源／hash不能保證未來可重取同一批影像或同一切分；精確成員清單未公開，需另行私人保存。
