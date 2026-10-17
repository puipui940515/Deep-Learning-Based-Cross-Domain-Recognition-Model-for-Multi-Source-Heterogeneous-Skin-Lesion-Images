# 全資料集快速測試

<!-- skindetect:status v1 -->
| 欄位 | 值 |
|---|---|
| 階段 | 驗證階段 |
| 首次執行 | 2026-08-14 |
| 狀態 | 已完成 |
| seeds | 17／42／2026 |
| 主要指標 | 五來源固定抽樣快速推論；不重新訓練 |
| 正式輸入 | `全資料集快速測試/manifest.csv` |
| 結果證據 | `全資料集快速測試/第二階段/results.json` |
| 歸檔 | — |
| 時間軸 | [`開發歷程/時間軸.md`](../開發歷程/時間軸.md) |
| 格式約定 | [`開發歷程/格式約定.md`](../開發歷程/格式約定.md) |
<!-- /skindetect:status -->

本測試不重新訓練，使用既有第一階段 v1、第二階段 v5，以及各自三個 noisefilter 搭載 checkpoint，對目前五個本地資料來源做固定分層抽樣推論。

## 涵蓋來源

- HAM10000：只抽 validation，不使用封存 test。
- SCIN：所有疾病類別均抽樣；因影像型態及診斷語意不同，只計算推論穩定性。
- PAD-UFES-20：ACK、BCC、SEK、NEV、MEL 映射到 HAM 類別；SCC 只做穩定性。
- ISIC Archive 子集：BCC、Melanoma 映射到 HAM 類別；SCC 只做穩定性。
- BCN20000：train 的 AK、BCC、BKL、DF、NV、VASC、MEL 映射到 HAM 類別；SCC 與無標籤 test 只做穩定性。

每個來源類別最多固定抽 32 張，種子為 20260814。這是快速外部分布測試，不等同全量正式外部驗證。

## 輸出

```text
全資料集快速測試/
├─ manifest.csv
├─ 第一階段/
│  ├─ results.json
│  ├─ metrics_by_seed.csv
│  └─ 結論.md
├─ 第二階段/
│  ├─ results.json
│  ├─ metrics_by_seed.csv
│  └─ 結論.md
└─ run.py
```

分類指標只使用可可靠映射的資料；所有抽樣影像均計算乾淨／合成光照擾動之預測一致率與機率漂移。
