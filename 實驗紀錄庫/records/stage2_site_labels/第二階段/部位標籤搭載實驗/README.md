# 第二階段部位標籤搭載先導實驗

以第二階段已完成的 v7 三個最佳 checkpoint 為共同起點，進行短程配對 A/B：

- control：一般 shuffle。
- site_balanced：只改成「疾病內部位平衡抽樣」。部位不是模型輸入，也不加入 loss。
- 兩組使用相同 checkpoint、模型、CE loss、影像尺寸、optimizer state、訓練 epoch 與 validation split。
- test split 完全不載入。

此實驗用來快速判斷部位標籤是否值得進入後續正式版本。因為是從既有 checkpoint 短程續訓，結果只能稱為先導效果，不能取代從頭訓練的正式三 seed 比較。

## 執行

```powershell
python "第二階段/部位標籤搭載實驗/scripts/run_pilot.py" --seed 17
python "第二階段/部位標籤搭載實驗/scripts/run_pilot.py" --seed 42
python "第二階段/部位標籤搭載實驗/scripts/run_pilot.py" --seed 2026
python "第二階段/部位標籤搭載實驗/scripts/summarize.py"
```
