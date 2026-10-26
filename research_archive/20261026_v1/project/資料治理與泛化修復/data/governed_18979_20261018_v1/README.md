# 歷史固定切分與去重版本完成紀錄

日期：2026-10-18（Asia/Taipei）。只完成資料準備，未執行訓練。

歷史版本：資料治理與泛化修復\data\historical_18979_20261018_v1

去重版本：資料治理與泛化修復\data\governed_18979_20261018_v1

BCN 解壓位置：dataSets\BCN20000\images\historical_18979_20261018_v1

| 來源 | 歷史 Train | 歷史 Val | 歷史 Test | 去重 Train | 去重 Val | 去重 Test |
|---|---:|---:|---:|---:|---:|---:|
| HAM | 7008 | 1504 | 1503 | 7007 | 1504 | 1502 |
| BCN | 10266 | 1716 | 0 | 10221 | 1712 | 0 |
| PAD | 1705 | 401 | 0 | 1691 | 395 | 0 |
| 合計 | 18979 | 3621 | 1503 | 18919 | 3611 | 1502 |

歷史重現使用同學提供的原始程式；其 SHA-256 為 c04cb936cb4171a7091b9856890d4c5b6916dd15fdcc2a1405f6535a30eea321。
歷史圖片 ID、標籤與 split 身份指紋：e1d994cf3904fc6cf93b0f994d0b1b9b0b2c44888348c734f5a669a648164d7e，與程式參考值一致。歷史版本保留問題列，只用於歷史重現，不冒充去重版。

去重 mixed_manifest.csv 含 Train＋Validation 共 22530 列，使用專案根目錄相對路徑，可找到所有圖片。test.csv 為封存 HAM Test 共 1502 列，training_eligible=false，不在訓練 Manifest 中。兩個 Manifest 保留來源原始診斷、患者／病灶 ID、原始 Metadata JSON 及歷史 split。

歷史成員中排除 71 列：Train 60、Validation 10、Test 1。加上原本七類以外的 SCC，共 694 個不重複排除來源列，詳見 exclusions.csv；原因可重疊，不直接相加。沒有因 PAD 單欄病灶重號額外排除圖片。

患者（有提供者）、來源主要分組、病灶記錄鍵跨 Split 交集為 0；已知重複連通群組沒有跨 Split。全部 24726 張來源圖片已作 SHA-256，去重後無相同位元組內容，跨 Split 相同內容組為 0。這些檢查不代表已檢查所有近重複、不同壓縮版本或已完整解碼每一張圖片；此次只抽樣讀圖 9 張，全部成功。HAM／BCN 缺患者 ID，僅能驗證其病灶級隔離。

BCN 僅解壓七類所需 11982 張，串流讀取至檔尾完成 ZIP CRC 檢查；431 張 SCC 留在原 ZIP。ZIP 前後 SHA-256 一致。原始 Metadata／映射雜湊與先前稽核一致，模型、訓練程式、超參數未修改。

實際執行環境：C:/Program Files/Python312/python.exe；numpy 1.26.4、scikit-learn 1.5.1 從 [USER_HOME]\Documents\Codex\2026-10-18\skindetect-d-skindetect-base-agents-md\work\split-audit-deps 載入。
工作目錄：[USER_HOME]\Documents\Codex\2026-10-18\skindetect-d-skindetect-base-agents-md。實際階段命令為 python 加上 [USER_HOME]\Documents\Codex\2026-10-18\skindetect-d-skindetect-base-agents-md\work\prepare_fixed_split_release_20261018.py，分別使用 --stage extract、--stage historical、--stage governed。歷史程式完整命令與輸入／輸出雜湊另存歷史目錄 provenance.json。

本次適配腳本保存於 資料治理與泛化修復\scripts\prepare_fixed_split_release_20261018.py，只負責解壓、呼叫原重現程式與既定去重／檢查；不另行實作切分。file_hashes.json 驗證核心產物；publication_inventory.json 補錄本次所有發布檔案雜湊。

訓練尚未授權。舊訓練設定／閘門未修改；下一步應明確選定訓練入口並核對新 Manifest 介面、路徑及新的驗證狀態。原 HAM localization 已保留，未猜測新增部位映射；需要部位輔助任務時須另行確認。
