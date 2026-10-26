# restart1：CPU已通過，Tiny GPU前檢非有限梯度停止

日期2026-10-26臺北。使用者於本B對話明確要求「請重新開始任務」，故本次在原六run完整範圍內重新授權準備及一次啟動；不是沿用失敗派送資格、不從正式Checkpoint Resume。授權全文與範圍在RESTART_AUTHORIZATION.md。

新執行根目錄為 `資料治理與泛化修復\results\v2_tiny_base512_relu_stage_dropout_20261026_v1\executions\restart1_20261026_v1`。原版本root的CPU失敗、STOP、狀態／gate／來源／收據完全保留；科學配置與比較契約不改寫。ACTIVE_EXECUTION.json是新建的定位入口，指向本次已停止執行，不是自動Resume。

## 本次完成的修正及CPU驗證

修正架構helper與CPU檢查：透過本機timm.get_act_layer('gelu')識別實際自訂GELU；只替換真正ConvNeXtBlock的mlp.act。新模型名在契約／best metadata使用relu_stage_dropout01識別，避免同鍵名權重被誤當成原GELU架構。metadata變更不改張量形狀或訓練配方。

CPU_tiny.json：passed、3.669122699997388秒；CPU_base.json：passed、5.114852200000314秒。已實際核對Tiny18／Base36個非inplace ReLU及原GRN數、4個Stage後一般Dropout.1、stage／head尺寸與全部參數鍵／形狀不變、原候選仍為GELU且無新Dropout、原FCMAE ImageNet1K全部backbone鍵形狀映射、eval確定性與Dropout train/eval行為、原CheckpointStore commit/load及best匯出。CPU使用64×64合成張量只驗結構，GPU才用核定512；沒有把CPU小張量說成正式資料結果。兩模型CPU均已完成，不需從零重做它們。

## 實際GPU失敗

沿原啟動資源檢查後，只執行Tiny一次新候選GPU前檢，讀governed Train8張，RTX5070、8×3×512×512，原Train前處理／AMP／MixUp／LS。preflight/tiny.json記錄實際record ID及初始head，未公開原圖。

已完成1次模型前向，輸出形狀8×7、logits與Loss的有限值斷言通過；執行1次AMP backward與unscale後，在gpu_compatibility.py第46行檢查到至少一個非有限梯度，AssertionError。**Optimizer step尚未執行，更新0次。** Base GPU未開始，正式六run全部未啟動，無Run ID／正式Epoch／best／正式Checkpoint。模型temporary狀態未作正式初始化。

失敗發生前未將實際Loss數值、非有限梯度層名／數量或峰值顯存寫入收據，故這些欄位為未取得；不重跑GPU補測或捏造。沒有OOM／CUDA unknown error訊息，不能斷言顯存不足或硬體故障。

另以來源唯讀比較確認：本次自寫前檢用了`scaler.scale(loss).backward()`，而原正式train_epoch使用`scaler.scale(loss / accumulation).backward()`；Tiny accumulation=8。這是B前檢未完全沿用原縮放的程式差異，未改到正式trainer的原數學。它可能影響AMP溢出，但沒有對照重試，**尚未證明是唯一根因**；也不能由此斷言核定ReLU＋Dropout正式配方不可訓練。原GradScaler在正式路徑會自行處理overflow，本次前檢在step之前檢查即停止，不能聲稱已觀察到scaler正常調整後仍失敗。

## 停止與證據

依原交辦有限值／程序異常即停止、不自動重試規則，Tiny前檢失敗後立即保留新execution STOP，未再執行任何GPU前檢或訓練。GPU EXIT收據為一次程序12.477808199997526秒，worker11.852585599990562秒包含在內；CPU與GPU前檢另帳，正式耗時0秒，原CPU失敗8.4981436秒獨立保留，不重複相加。

STOPPED_RECEIPT.json包含上述界線與失敗traceback；GPU_LAUNCH_tiny.json／GPU_EXIT_tiny.json及GPU_tiny.stdout/stderr.log保存命令／當下資源及退出；新結果FINAL_RESULTS、state、B_HANDOFF明示failed_gpu_preflight與0run/0Epoch。MONITOR是靜態停止收據，沒有活控制器，不稱每15秒即時更新。

失敗時全部新來源、配置與驗證腳本／收據已封存於本execution sources_runtime。封存後只撤回本次共用trainer／model_profiles的接入與metadata變更；ROLLBACK_RECEIPT證明兩個live檔與本次before逐位元SHA相同，舊候選行為與其他人的既有修改恢復原樣。已通過的修正helper與新版本草稿及所有CPU證據保留，但正式共用入口不再接入未通過GPU前檢的候選；gate.execution_authorized=false，不能直接啟動。沒有安裝／下載／Windows變更、Test、網站模型變動、共用索引修改或其他Thread訊息；停止後未見Python訓練程序。

## 實際命令與未完成項

工作目錄D:\SkinDetect_base，既有recovery venv：

```powershell
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -X utf8 'recovery_20261023\B_training\tiny_base512_relu_stage_dropout_20261026_v1\restart1_20261026_v1\initialize_restart.py'
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -X utf8 'recovery_20261023\B_training\tiny_base512_relu_stage_dropout_20261026_v1\restart1_20261026_v1\cpu_architecture.py' --size tiny
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -X utf8 'recovery_20261023\B_training\tiny_base512_relu_stage_dropout_20261026_v1\restart1_20261026_v1\cpu_architecture.py' --size base
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -u -X utf8 'recovery_20261023\B_training\tiny_base512_relu_stage_dropout_20261026_v1\restart1_20261026_v1\run_gpu_checks.py'
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -X utf8 'recovery_20261023\B_training\tiny_base512_relu_stage_dropout_20261026_v1\restart1_20261026_v1\close_restart_failure.py'
```

以上已執行，不重跑／覆寫。不執行formal controller、不刪STOP／舊gate、不把CPU微型Checkpoint當成可Resume的正式run。

後續最小範圍是先使臨時GPU前檢直接沿用共用train_epoch的原loss/累積及AMP更新路徑，避免額外改變尺度或把新的梯度拒絕政策套入正式run。保留本次證據，再取得一次明確驗證／啟動授權，才能補Tiny／Base各核定單批GPU檢查；不擅自降低正式scaler／更換精度、LR、batch、資料或增強，也不追加benchmark／長期診斷。架構與原CPU實作未變時優先沿用本次CPU通過證據。六正式run仍待啟動，總6run／180輪與所有原條件不擴大。本次保存完成後停止。
