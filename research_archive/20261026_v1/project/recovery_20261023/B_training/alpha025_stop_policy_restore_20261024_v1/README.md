# alpha025 額外停止行為還原｜2026-10-24 v1

依本B chat使用者最新指令，對照原 `資料治理與泛化修復/scripts/run_v2_resolution.py` 與 `recovery_20261023/B_training/alpha025_launch_20261024_v1/before/train_regularized.py`。本輪只做停止政策還原與必要UTF-8相容修復，沒有啟動／重試／Resume、模型／GPU小測、benchmark、安裝或Windows變更。工作目錄 `D:\SkinDetect_base`。

## 實際修改

僅改兩個正式來源：

1. `資料治理與泛化修復\scripts\run_v2_alpha025.py`
   - 啟動前回到舊controller條件：程序衝突、RTX5070／利用率<=10%／可用顯存>=6500MiB、Commit餘裕>=8GiB、輸出磁碟>=10GiB。刪除alpha025額外新增的RAM4GiB門檻；RAM仍可記錄，不據此拒絕。
   - 刪除執行中Commit／RAM數值判斷、RESOURCE_STOP寫入及因此強制終止程序樹的分支。
   - 刪除額外執行中的程序衝突、磁碟門檻及重複gate停止檢查；原data/config gate仍在每Seed啟動前、trainer入口及Checkpoint契約中，不移除一致性保護。
   - 每15秒保留被動資源／狀態紀錄，不因Commit/RAM/GPU數值中斷訓練；不增加新的停止門檻。監測寫檔等異常依原controller方式設STOP並等待完整Epoch邊界，保留一般異常清理及退出處理。
   - 程序清單僅作必要中文相容修復：PowerShell Console.OutputEncoding／OutputEncoding明確UTF-8，Python端encoding='utf-8'、errors='strict'；查詢／解碼／JSON解析失敗照例拋錯，不冒充空清單。普通應用未新增拒絕規則；保留舊正式啟動程序條件及新controller身分辨識。
2. `資料治理與泛化修復\scripts\train_regularized.py`
   - 移除alpha025新增的每批Loss `isfinite`及gradient norm `isfinite`停止檢查。
   - 梯度裁剪恢復原 `torch.nn.utils.clip_grad_norm_(model.parameters(), clip)`，原AMP Scaler step/update／Optimizer zero_grad順序不變。
   - 原整輪Train／Monitor／Validation loss非有限檢查、Robust停止函式、STOP、CheckpointStore及異常退出計帳保留。
   - 先前被授權的純資料等待／batch耗時計數保留，不增加停止條件。排除這些純計時敘述後，train_epoch整個計算流程AST與before版完全一致。

新ID／alpha025註冊與gate、Seed1→2→3、512、8×8及所有C核定科學參數未改。`v2_alpha025_contract.py`未修改；`wall_clock_cap_seconds=null`、3run／90完整Epoch不變，沒有恢復舊秒數預算。

## 直接相關的必要核對

`check_restore.py`僅標準函式庫與測試替身，不import torch／模型，不讀影像或Test。

- 原啟動前Commit8GiB／GPU10%／顯存6500MiB／磁碟10GiB／程序衝突測項通過；用RAM0.1GiB的純替身輸入確認**沒有新增RAM4GiB判斷**，不是實際低記憶體負載測試。
- AST確認執行中迴圈無Commit／RAM比較、無程序／磁碟／gate停止檢查、無資源強殺呼叫。
- 每批Loss／梯度計算（排除純計時）與before AST一致；原整輪非有限檢查AST及STOP檢查保留。
- 非ASCII假程序命令可辨識，解碼／JSON失敗不被當空清單；Windows PowerShell實際只輸出固定中文文字的UTF-8往返通過，沒有查GPU或啟動其他程序工作。
- 語法／未設時間上限核對通過，torch沒有被匯入。

12項核對最後皆通過：首輪11項通過，AST比較的測試正規化器未遞迴剔除迴圈內純計時，造成1項測試工具失敗；修正僅該測試工具後，只重測失敗的1項並通過，沒有重跑其餘11項或任何GPU工作。原失敗log保留 `CPU_CHECKS.log`，針對性重測 `CPU_CHECKS_retest.log`。沒有藉此移除實際計算或保護來過測試。

實際命令：

```powershell
Set-Location 'D:\SkinDetect_base'
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -X utf8 'recovery_20261023\B_training\alpha025_stop_policy_restore_20261024_v1\check_restore.py'
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -X utf8 'recovery_20261023\B_training\alpha025_stop_policy_restore_20261024_v1\check_restore.py' RestoreTests.test_train_epoch_calculations_equal_before_excluding_passive_timing
```

## 原失敗／STOP／設定保護

- `protected_before.json`／`protected_after.json`：44份小型保護檔SHA逐一一致，涵蓋原失敗root（包括state／RESOURCE_STOP／STOP／lock／attempt／budget／run_inputs／logs／原gate與source snapshot）、C核定配置全部檔案、原run_v2_resolution.py、training_state.py與其餘既有tracked修改。未hash模型／權重。
- 修正前兩個程式完整副本在本目錄before，沒有覆寫第一次啟動的歷史snapshot。
- 原Run ID d87cb2eef21d47fc8a408aa16b70e641仍failed、零完整Epoch、無Checkpoint；Seed2／3仍pending。STOP及24.779秒失敗attempt／13.761秒Epoch區段全部保留，不清零、不改歷史失敗原因，不把本次政策修訂追寫成原run當時的行為。
- 新來源SHA與修訂身分見 `REVISION.json`。**原EXECUTION_GATE.json未重綁**，其中記錄的舊來源SHA與本次修改後不同，這是保留歷史來源的正常版本差異；不能以原gate聲稱現在程式已獲同一失敗run的Resume相容性。

後續只有取得明確「一次新初始化重試」授權後，才能準備適用的新execution修訂／gate與失敗保留政策。這次沒有發出該授權、沒有重啟或假作Resume，也沒有自行刪STOP。無完整Checkpoint的原失敗run不能Resume。本次只交還原結果，完成即停止；未改共用索引、跨角色或傳訊其他Thread。
