# 本輪模型大小初篩核定與執行授權
2026-10-25使用者明確授權Base→Large→Huge，各512、Seed1新初始化一完整正式run，順序不並行。Tiny只引用原512 alpha.5，不重訓。
原governed_18979_20261018_v1 Train18919/Val3611、七類及前處理；同類型FCMAE ImageNet1K初始化，釘選來源/revision/SHA，重建七類head，不接舊best或隨機/22K替代。權重允許下載D槽。
科學配方繼承原512，alpha.5 LR1e-4 AdamW WD.05 LayerDecay1 LS.1 MixUp.2 RE.15 AMP Workers4；有效Batch64，允許8x8/4x16/2x32/1x64，正式前依必要預檢實測吞吐與顯存選定，不把GPU100%當唯一目標。記錄MixUp配對改變，micro1退化為自身配對；不是純架構隔離因果。
Min12 Max30 Patience5 MinDelta0 CosineTmax30 eta_min1e-6，首次最高Robust選best；最大3run/90完整Epoch、不設wall-clock上限、不追加Seed，正式失敗不自動重試。
必要CPU契約/最小GPU相容驗收含backward/累積/optimizer狀態分配，預檢獨立暫存模型，正式重新初始化。預檢可按核准微批降檔，不開完整benchmark。Huge先估顯存，不可行記錄略過；不得凍結/offload/改optimizer或新記憶體策略。某模型權重/介面未解可停止該模型，其餘合格者繼續。
沿用原啟動前資源政策與已還原STOP/Checkpoint/整輪非有限處理，不增執行中強停門檻、不改Windows/正式配方/資料/Test、不干擾F服務。
使用者補充：必要預檢與正式run順便記錄資料等待、訓練運算、Validation、存檔、圖片吞吐及峰值顯存；首個完整Epoch後更新時間估計與首輪初始化限制。不得減資料/解析度/Validation/Checkpoint保護以加速；正式啟動後只觀察，不中途改設定。
正式前主動摘要後依本授權直接開始，不重問同範圍核准。每15秒更新監控表列模型/Seed/RunID/狀態/完整Epoch；最終指標/疾病/耗時/顯存交總控供D判讀，單Seed初篩不自動採納/換網站。不改共用索引、不聯絡其他chat。
