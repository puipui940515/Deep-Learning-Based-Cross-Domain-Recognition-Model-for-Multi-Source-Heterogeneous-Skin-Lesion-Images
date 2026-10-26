# V2 512 alpha025 正式訓練狀態

更新：2026-10-24T11:30:29.805401+00:00；status=failed
Seeds1→2→3；3run／最多90完整Epoch；wall_clock_cap_seconds=null（不設時間上限）。
alpha=.25；512／8×8；Min12/Max30/Patience5/Tmax30；不以分數取消Seed3。

|Seed|狀態|Run ID|完整Epoch|最佳輪|
|---|---|---|---:|---:|
|1|failed|d87cb2eef21d47fc8a408aa16b70e641|0|N/A|
|2|pending|N/A|0|N/A|
|3|pending|N/A|0|N/A|

完整Epoch區段：0/90；Epoch區段實耗：13.761秒。
整次嘗試（包含初始化／失敗）耗時見attempts/*.json；與Epoch區段不重複相加。
STOP保留；異常／OOM／非有限／Commit<8GiB／RAM<4GiB／磁碟不足／GPU衝突或存檔失敗即停止。
無自動重試、不改配方、不讀Test、不換網站；persistent workers不保證逐位元恢復。

resource_guard_commit8_or_ram4
