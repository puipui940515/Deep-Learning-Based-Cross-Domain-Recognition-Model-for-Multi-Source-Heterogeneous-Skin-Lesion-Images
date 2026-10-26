# SkinDetect 20261026 增量研究保存

本版只新增於research_archive/20261026_v1，不覆寫20261024_v3或main。正式run均引用既有結果，未重訓、推論、重畫圖或開封Test。

`project/`保留專案相對結構；其中scripts/ui_prototype為本輪current source；configs、results及B交接的sources_before/sources_runtime是凍結歷史版本，請用run_inputs的source_hash與manifest追溯，勿混用。run_inputs發布副本移除逐圖成員ID與dispatch token。檔案日期及讀取截點見BACKUP_MANIFEST.json。

包含alpha025、Base/Large初篩與followup、512 ReLU+StageDropout的失敗／30+30+4輪暫停、224單變因的CPU/GPU失敗準備歷史；ampwin目前進行中輪次與快照明確排除。最新狀態請看SNAPSHOT_STATUS.json明確execution路徑，根ACTIVE_EXECUTION可能是舊失敗。JSONL保留原格式且只寫完整行，沒有重新計算指標；所有MONITOR為靜態截點，不是即時監控。

恢復程式：先取本分支及20261024_v3，閱讀AGENTS、PROJECT_STATE與V2歷史，將所需版本的project內容放到新的工作目錄，保留原快照；另行取得缺失資產／相容環境，先核對契約與權重SHA。不得直接執行snapshot中舊launch命令、清STOP或自動Resume。只有適用授權與B驗證後才能啟動模型／訓練。

`report_sources/`含實際使用者MD源稿的去識別副本及Word v4／Meeting逐段XML文字；不含Office媒體與原排版。完整可恢復與否請看RECOVERY_GAPS.md，本次沒有做重建環境／完整恢復演練。

本輪只讀已知專案小型來源範圍，不掃D槽／資料集，不讀大權重、不改執行程序、不改原專案index，不上傳Google Drive。

本次最後核准補入九份MLP／ResNet最佳輪權重，逐檔SHA與用途見WEIGHTS_README.md／WEIGHT_SIZE_AUDIT.json；其餘大型模型、所有完整Resume Checkpoint與資料本體仍缺。
資料集名稱／來源／hash不能保證未來可重取同一批影像或同一切分；精確成員清單未公開，需另行私人保存。
