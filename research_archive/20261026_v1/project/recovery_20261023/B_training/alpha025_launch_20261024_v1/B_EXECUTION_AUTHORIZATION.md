# B 本輪正式執行授權｜2026-10-24

來源：本 B chat 使用者最新直接指令，非沿用舊實驗授權。以下節錄當次執行範圍；C原AUTHORIZATION／suite保留原配置交付範圍，不改formal_training_authorized=false。

「本指令授權完成必要啟動相容銜接，並執行v2in_res512_alpha025三個新正式run。」

核定模型ConvNeXt V2-Tiny ImageNet、512、原governed Train18919／Val3611、七類不變；唯一改動alpha .5→.25；Seeds1→2→3、微批8×累積8、LR1e-4，其餘依C核定配置。Min12/Max30、Patience5、MinDelta0、Tmax30，每Seed首次最高Validation Robust選模。各Seed獨立釘選ImageNet初始化，不從舊best.pt續訓。

沿用trainer、CheckpointStore及監測，只作新ID／唯一差異驗證／新輪runner、gate、計帳的最小相容修改。保存他人修改、所有舊契約。最多3run／90完整Epoch，wall-clock硬上限明示null；不填極大秒數、移用舊預算或自動無限重試。失敗／初始化及完整Epoch耗時分別保留，不重複加總。

僅做直接相關語法／CPU契約驗證；已完成原資料＋GPU小測沿用，不重跑環境小測、成本測試／GPU benchmark。不安裝或下載。正式啟動前核對訓練衝突、GPU、Commit/RAM、磁碟；Commit至少8GiB，保留必要守護，不關其他程序、不改Windows/pagefile。

契約一致且資源可行後依本授權直接開始，不再要求相同設定核准。完整三Seed，不依前兩分數取消Seed3。OOM、非有限值、資源守護、存檔失敗即停止保存，不自動追加候選或無限重試；異常恢復先回報，不重跑completed。完整Checkpoint同契約正常暫停才有適用Resume。

結果在資料治理與泛化修復/results/v2_512_alpha025_20261024_v1；實際命令／版本／run_inputs／逐Epoch日誌／best／完整Checkpoint／資源與停止紀錄保留。不開Test、不換網站。B交結果，採納交C/D；不得依此執行其他研究。
