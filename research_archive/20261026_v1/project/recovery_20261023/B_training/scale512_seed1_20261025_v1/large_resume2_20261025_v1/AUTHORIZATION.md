# Large存檔修復後一次同Run Resume

本對話使用者2026-10-25在B說明「Large尚未完成、Resume驗收包裝造成第14輪Checkpoint序列化失敗、須修復及新的一次Resume授權」後明確指示：**「那請繼續訓練」**。本文件記錄此次必要存檔相容修復及一次同Run接續授權，不沿用已消耗的Resume1一次啟動資格。

唯一對象為ConvNeXt V2-Large，Run ID 7c6b140d4ed442389852be8707d8e2c6；最新有效完整Checkpoint13接續14，不從零、不從best.pt初始化、不退回12、不改Run ID。恢復模型／AdamW／scheduler／scaler／RNG／sampler與loader generators／history／best／早停計數。原最佳11、bad_epochs2；persistent worker狀態不保證逐位元重播。

科學條件保持512、Seed1、micro1×accum64、effective64、alpha.5、LR1e-4、AdamW WD.05、LayerDecay1、LS.1／MixUp.2／RE.15、AMP、Workers4、原governed Train18919／Val3611七類及原前處理。Min12/Max30、Patience5、MinDelta0、Tmax30、eta_min1e-6，首次最高Robust選best。Large最多30完整輪、全研究最多3run/90完整輪，不設wall-clock上限，不增加候選／Seed。不重跑Base、Tiny或Huge，不讀Test。

只在此新版本修正Resume1對模型／optimizer／scheduler實例方法的驗收覆寫，改用原trainer恢復後的唯讀觀察；原frozen trainer、CheckpointStore、配置與gate不變。允許直接相關CPU微型Checkpoint序列化／恢復檢查，不重做GPU小張量、批次預檢或benchmark，不安裝／下載／改Windows。真正訓練前沿用原啟動程序／GPU／Commit及磁碟政策，不新增執行中資源或每批強停門檻。

保留原CUDA失敗attempt及Resume1存檔失敗的來源、授權、STOP、日誌及全部計帳。此版本獨立PERMIT／token／LAUNCH_ONCE，核對failed與Checkpoint後移存現有STOP，未來新STOP維持原作用。一次啟動失敗即保存並停止，不自動再試或另建run；不得重用舊啟動標記／刪失敗證據。監控沿用原MONITOR.md每15秒更新，需如實區分啟動、批次前進、第14輪Checkpoint提交與最終訓練完成。

僅B交接與原結果運行狀態可更新，共用研究入口留總控管理；不聯絡其他對話、不干擾F服務或採納／網站模型。
