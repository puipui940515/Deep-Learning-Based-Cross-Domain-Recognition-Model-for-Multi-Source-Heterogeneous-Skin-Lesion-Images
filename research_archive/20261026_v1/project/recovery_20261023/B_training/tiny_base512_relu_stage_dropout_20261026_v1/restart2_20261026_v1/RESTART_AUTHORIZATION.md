使用者2026-10-26本B對話明確授權一次修正後驗證與既定六run啟動，非無限重試：
「請修正前檢與原訓練流程不一致的問題，完成必要驗證後重新執行既定六個Run。本訊息授權一次修正後的驗證與啟動，不包含無限重試。」
GPU前檢直接呼叫共用train_epoch：loss÷累積、原AMP／clip／optimizer流程。撤回新增AMP處理前梯度強停，不忽略真正異常或偽造更新。
只保留GELU→非inplace ReLU及四Stage後一般Dropout.1；所有原AdamW、LR、資料、釘選預訓練、batch／累積／AMP／Scheduler／停止不變。
Tiny512 Seeds1/2/3 8×8，再Base512 Seeds1/2/3 2×32；最多6正式run／180完整Epoch，無wall-clock上限。每run重新初始化，不接best/last。
原啟動資源政策、STOP、Checkpoint／CUDA／Loss非有限與契約處理、15秒監控保留；本次真異常即保存停止、不自動重試或Resume。
沿用已通過CPU Tiny/Base架構／mapping／Checkpoint，不重跑。兩次舊失敗與STOP全部保留，新execution restart2_20261026_v1，無Test／安裝／下載／Windows或網站變更。
