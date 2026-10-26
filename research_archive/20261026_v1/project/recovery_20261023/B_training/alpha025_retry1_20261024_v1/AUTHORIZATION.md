# Seed1 一次全新初始化重試授權｜2026-10-24

來源：本 B chat 使用者最新直接指令：「現在明確授權：以已還原的舊停止政策，重新初始化Seed1再試一次；成功後依序完成Seed2、Seed3。不是Resume。」

僅允許 execution revision `retry1_20261024_v1`：Seed1一次全新ImageNet初始化重試；正常完成後Seed2／Seed3各新初始化一次。不得再開retry2、任意重試、跳過失敗Seed或假作Resume。再次失敗則保存停止。本輪起始不使用任何Resume旗標或既有best.pt。

完整保留原失敗Run ID d87cb2eef21d47fc8a408aa16b70e641、STOP／來源／日誌／gate／失敗計帳；不覆寫或刪除。本次獨立輸出為原研究root下 executions/retry1_20261024_v1，父失敗與實耗均追溯，不變更研究或候選ID。

科學配置完全依C：alpha .25、512、Seeds1→2→3、微批8×累積8、LR1e-4、其餘配置不變；各Seed從原釘選ImageNet backbone與同Seed新七類head獨立初始化，空Optimizer。Min12/Max30、Patience5、MinDelta0、Tmax30；每Seed首次最高Validation Robust選模，最多三個完整run／90完整Epoch，不設wall-clock上限。

沿用已還原的原啟動前檢查；無執行中Commit/RAM強停、RAM4GiB門檻／每批Loss梯度新增停止、執行中程序或磁碟門檻。保留STOP完整Epoch邊界、Checkpoint、整輪非有限及異常處理。只補本修訂的授權／來源／重試邊界核對，已通過CPU／GPU小測及整套CPU驗證不重做、不加benchmark。

真正啟動前依舊流程核對當下資源與衝突；摘要生效設定後直接開訓，不再要求相同配方核准。不改Windows、超參數、資料、權重或Test。三Seed不按前兩分數取消後續，不換網站模型，不自動增加候選。
