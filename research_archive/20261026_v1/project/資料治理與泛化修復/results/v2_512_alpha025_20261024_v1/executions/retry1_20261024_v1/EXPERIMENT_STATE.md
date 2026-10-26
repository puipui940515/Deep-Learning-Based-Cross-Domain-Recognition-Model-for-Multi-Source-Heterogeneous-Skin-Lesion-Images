# V2 512 alpha025 正式訓練狀態

更新：2026-10-24T18:14:33.056968+00:00；status=completed
Seeds1→2→3；3run／最多90完整Epoch；wall_clock_cap_seconds=null（不設時間上限）。
alpha=.25；512／8×8；Min12/Max30/Patience5/Tmax30；不以分數取消Seed3。

|Seed|狀態|Run ID|完整Epoch|最佳輪|
|---|---|---|---:|---:|
|1|completed|21d2aaccb9e5490faba534f6b752fa98|13|8|
|2|completed|88e812db602549c8b6593c29a51e55c4|20|15|
|3|completed|1fc8933da4aa4a25aa902729874cf894|12|5|

完整Epoch區段：45/90；Epoch區段實耗：16928.658秒。
整次嘗試（包含初始化／失敗）耗時見attempts/*.json；與Epoch區段不重複相加。
沿用舊啟動前檢查：Commit>=8GiB／顯存>=6500MiB／GPU利用率<=10%／磁碟>=10GiB及程序衝突。
訓練中資源僅記錄；STOP於完整Epoch邊界處理，保留原整輪非有限值／資料契約／Checkpoint／異常退出。
無自動重試、不改配方、不讀Test、不換網站；persistent workers不保證逐位元恢復。


