使用者2026-10-26本B對話明確授權：
「請一次完成Windows保存路徑修復與原定訓練接續。本訊息授權必要修復、CPU存檔驗證，以及修復後一次新的Seed1替代啟動，接續其餘五個Run。」
只修正Checkpoint檔案IO，優先縮短同目錄暫存名稱，保留fsync／原子替換／雙代／原恢復保護，不改Windows或科學參數。
在涵蓋六run最長正式路徑的隔離位置以微型CPU payload驗寫入、替換、index／best／雙代與讀回；不覆寫正式Checkpoint。
沿用既有適用CPU與原train_epoch GPU更新證據，不再GPU前檢／benchmark。
Tiny Seed1無Checkpoint，授權一次新Run ID／原預訓練／新head及空optimizer替代啟動，之後Tiny2/3、Base1/2/3依序。
原失敗Run額外列帳，新增一次替代啟動；原六模型Seed任務及最多180已提交Epoch維持，無時間硬上限。
只ReLU＋四Stage後一般Dropout.1；全部原AdamW／LR／資料／Batch／累積／AMP／Scheduler／早停不變。
保留全部失敗、STOP、來源與實耗；新execution restart3_20261026_v1，不假作Resume。
原資源政策、15秒MONITOR；無新門檻／安裝／下載／Windows或網站變更／Test。新真正異常即保存停止，不無限重試。
