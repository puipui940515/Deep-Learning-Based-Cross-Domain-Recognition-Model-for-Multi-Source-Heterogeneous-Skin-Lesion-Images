"""SkinDetect 單一權威時間軸產生器。

事件清單維護在本檔的 EVENTS 常數，執行後同時輸出：
  開發歷程/timeline.json  機器可讀
  開發歷程/時間軸.md      人類可讀

兩份輸出由同一份來源產生，因此不可能互相漂移。
新增事件請只改 EVENTS，然後重新執行本腳本。

    python "開發歷程/build_timeline.py"
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

HISTORY = Path(__file__).resolve().parent
PROJECT = HISTORY.parent

SCHEMA_VERSION = "skindetect-index-v1"

# 受控詞彙：階段。任何索引檔的 stage 欄位只能使用這些值。
STAGES = {
    "DATA": "資料建置階段",
    "VAL": "驗證階段",
    "S1": "第一階段",
    "S2": "第二階段",
    "S3": "第三階段",
    "SITE": "部位預測階段",
    "MIX": "多來源訓練階段",
    "GOV": "泛化修復階段",
    "SCR": "基底篩選階段",
    "BASE": "基底模型階段",
    "CUR": "課程學習階段",
    "META": "專案治理",
}

# 受控詞彙：狀態。
STATUSES = [
    "已完成",       # 執行完畢且結果已記錄
    "進行中",       # 已開始，尚未完成
    "未開始",       # 已規劃
    "已結案",       # 負面結果，正式停止投入
    "已鎖定",       # 前置條件未達成而暫停
    "已停用",       # 不再使用
]

# event 欄位：date, stage, title, status, summary, evidence, archived(檔案室任務編號或 None), seeds
EVENTS = [
    dict(date="2026-08-13", stage="DATA", title="ISIC 授權篩選子集與 collection 212 快照建立", status="已完成",
         summary="依病理確認與 CC-0／CC-BY 條件建立 7,886 張 ISIC 子集；HAM10000 以影像 ID 對 collection 212 快照精確篩選。",
         evidence=["README.md", "Dataset/DATA_PROVENANCE.md"], archived=None, seeds=None),
    dict(date="2026-08-14", stage="DATA", title="來源優先目錄重整", status="已完成",
         summary="Dataset 第一層改為來源優先；刪除 2,298 張 PAD-UFES-20 疾病式重複副本，釋放 3,606,533,669 bytes；HAM10000 路徑未動。",
         evidence=["Dataset/SOURCE_LAYOUT_MIGRATION_2026-08-14.json", "Dataset/README.md"], archived=None, seeds=None),
    dict(date="2026-08-15", stage="VAL", title="NoiseFilter 設計稽核", status="已完成",
         summary="量測四段濾鏡的實際貢獻與 PeripheralReference 權重圖。GCC 與 PeripheralReference 平均 delta cosine 0.9953，為最明確的設計風險。",
         evidence=["noisefilter_清單檢查報告.md", "驗證/reports/noisefilter_design/design_audit.json"], archived="01", seeds=None),
    dict(date="2026-08-15", stage="META", title="匯總節點 CP-001：首次匯總", status="已完成",
         summary="涵蓋專案建立至資料整理、v1、v5、noisefilter 與首次完整稽核。判定 noisefilter 固定核心鏈不納入正式架構。",
         evidence=["開發歷程/節點01_首次匯總_2026-08-15.md"], archived=None, seeds=None),
    dict(date="2026-08-23", stage="SITE", title="iToBoS 部位預訓練 formal v1 與兩次精修", status="已結案",
         summary="formal v1 true-site 驗證 BA 57.53%（亂標 20.00%），train-val 落差 35.60pp。v1.1 雜訊遮蔽 −1.70pp、v1.2 label smoothing −1.13pp，兩者皆未通過事先宣告的 +2pp 閘門，依規則停止。官方 test 維持封存。",
         evidence=["部位預測階段/iToBoS_部位預訓練/results/formal_v1/develop_seed17_gate.json"], archived=None, seeds=[17]),
    dict(date="2026-08-24", stage="SITE", title="DensePose 部位預訓練與第二階段接續", status="已結案",
         summary="部位任務本身學得成功（BA 91.48%±0.06%，亂標 20.00%）。但凍結線性探測 17.47% vs ImageNet 34.63%（−17.16pp）、並行 teacher 僅 +0.10pp 且 seed 方向不一致。",
         evidence=["實驗彙整/部位預訓練與第二階段接續_2026-08-24/實驗整理.md"], archived="02", seeds=[17, 42]),
    dict(date="2026-08-24", stage="S2", title="部位權重完整微調正式對照", status="已結案",
         summary="ImageNet 三 seed 平均 77.50%；DensePose 真實部位初始化 seed 17 為 68.61%（−8.89pp）。summary.json 的 complete=false：真實部位組僅 seed 17，C 組亂標負對照從未完成。",
         evidence=["第二階段/部位權重完整微調正式對照/results/summary.json"], archived="03", seeds=[17, 42, 2026]),
    dict(date="2026-08-25", stage="S2", title="預訓練干預對照、三線比較、ConvNeXt 純淨三線", status="已完成",
         summary="ResNet18 隨機 57.28% → ImageNet 70.90%；ConvNeXt ImageNet 77.78%、部位預訓練 69.64%、純淨版 46.04%。確立 ImageNet 初始化為主線。",
         evidence=["檔案室/圖表資料庫/2026-08-25/"], archived="04,05,06", seeds=[17, 42, 2026]),
    dict(date="2026-08-25", stage="VAL", title="全部資料集只推論驗證", status="已完成",
         summary="ConvNeXt 三線跨資料集推論。ImageNet 版 HAM 74.83%、BCN 34.85%、PAD 與 ISIC 皆低於 30%，首次量化跨來源崩潰。",
         evidence=["全資料集驗證推論_ConvNeXt三線/"], archived="07", seeds=[17, 42]),
    dict(date="2026-09-01", stage="MIX", title="多來源混合訓練第一版（HAM＋BCN）", status="已完成",
         summary="BCN 由 35.50% 升至 60.07%（+24.57pp），HAM 未退步。本專案至今最大的單次真實增益。",
         evidence=["多來源混合訓練_第一版/results/imagenet_seed17/result.json"], archived="08", seeds=[17]),
    dict(date="2026-09-01", stage="MIX", title="多來源混合訓練第二版（＋PAD）", status="已完成",
         summary="PAD 由 39.76% 升至 71.21%（+31.45pp），BCN 微降 2.28pp。三來源平均 69.37%。訓練 BA 95.79% 與 BCN 驗證 57.79% 落差 38.00pp。",
         evidence=["多來源混合訓練_第二版/results/imagenet_seed17/result.json"], archived="09", seeds=[17]),
    dict(date="2026-09-05", stage="META", title="實驗紀錄庫與模型資產庫首次同步", status="已完成",
         summary="建立 UI 讀取的固定實驗紀錄入口與模型資產入口。",
         evidence=["實驗紀錄庫/registry.json", "模型資產庫/model_registry.json"], archived=None, seeds=None),
    dict(date="2026-09-06", stage="GOV", title="資料治理管線與統一資料合約", status="已完成",
         summary="四階段稽核通過。22,600 列 → 22,536 列，隔離 64 列；完全重複 56 組、標籤衝突 8 組、近重複待人工複核 112 筆。正式輸入改為 unified_manifest_v1.csv。",
         evidence=["資料治理與泛化修復/reports/pipeline_gate.json"], archived=None, seeds=None),
    dict(date="2026-09-06", stage="GOV", title="治理後正式訓練 v1", status="已完成",
         summary="三來源平均 72.06%、最差來源（BCN）62.83%、Robust 67.45%。抽樣為 weighted_replacement。至今最佳的三來源平均。",
         evidence=["資料治理與泛化修復/results/formal_v1/regularized_seed17/result.json"], archived="10", seeds=[17, 42]),
    dict(date="2026-09-07", stage="GOV", title="較長正式訓練 v2", status="已結案",
         summary="三來源平均 71.81%（−0.25pp）。非單變因：同時改 epochs 8→30、lr 1e-4→5e-5、mixup 0.2→0.3、patience 4→10。標記 multi-variable non-attributable。",
         evidence=["資料治理與泛化修復/results/formal_v2_long/regularized_seed17/result.json"], archived="11", seeds=[17]),
    dict(date="2026-09-07", stage="GOV", title="完整覆蓋抽樣 v3a", status="已結案",
         summary="三來源平均 70.41%（−1.65pp）、最差來源 59.92%（−2.91pp）。改用 full_coverage_capped，該路徑下 BCN 與 PAD 的類別平衡失效。",
         evidence=["資料治理與泛化修復/results/formal_v3a_coverage/regularized_seed17/result.json"], archived="14", seeds=[17]),
    dict(date="2026-09-08", stage="GOV", title="顯式影像特徵融合", status="已完成",
         summary="fusion：三來源平均 71.56%、最差來源 65.79%、Robust 68.68%（至今最佳最差來源與 Robust）。feature_only（58 維統計量、6,203 參數）達 43.63／32.06／52.18，遠高於 14.29% 隨機基準。",
         evidence=["資料治理與泛化修復/顯式影像特徵融合實驗/results/fusion_seed17/result.json"], archived="15", seeds=[17]),
    dict(date="2026-09-08", stage="SCR", title="十張影像熱力圖模型比較", status="已完成",
         summary="24 個模型、21 個可完成 Grad-CAM 全測試。暫定第一名混合 V2 ResNet18（篩選分數 93.81）。同文件記載完整驗證下 ConvNeXt 三來源平均高 3.14pp。",
         evidence=["模型基底篩選_熱力圖10張測試/results/model_summary.csv"], archived="12", seeds=[17]),
    dict(date="2026-09-08", stage="BASE", title="可切換功能正式訓練 v13", status="已完成",
         summary="三來源平均 64.39%（−7.67pp）、最差來源 47.95%。同時變動八個因素，無法歸因。溫度校準 ECE 0.0433→0.0285。",
         evidence=["基底模型發展_可切換正式訓練/results/base_resnet18_full_features_v1_seed17/result.json"], archived="13", seeds=[17]),
    dict(date="2026-09-08", stage="CUR", title="關卡式課程學習 v1", status="已結案",
         summary="第一關（HAM10000）即未過閘門：20 epoch 後 BA 74.91%，未達 80% 門檻，failure_reason=maximum_epochs，依規則停止未降低門檻。尚未進入任何索引或匯總節點。",
         evidence=["關卡式課程學習/results/curriculum_probability_v1_seed17/result.json"], archived=None, seeds=[17]),
    dict(date="2026-09-08", stage="META", title="匯總節點 CP-002：多來源泛化與資料治理匯總", status="已完成",
         summary="記錄十項瓶頸與四條負面結果路線。後續登錄 9 筆修正（C01–C09）。",
         evidence=["開發歷程/節點02_多來源泛化與資料治理匯總_2026-09-08.md"], archived=None, seeds=None),
    dict(date="2026-09-08", stage="META", title="CP-003 執行計畫建立並執行階段 0", status="進行中",
         summary="計畫涵蓋階段 0–6 共 28 次訓練。階段 0 已完成：敏感檔移出、兩份 registry 同步、歸檔規則補洞（新增任務 14、15）、過期文件標記。",
         evidence=["開發歷程/CP-003_執行計畫_2026-09-08.md"], archived=None, seeds=None),
    dict(date="2026-09-08", stage="GOV", title="CP-003 階段 1 完成：兩候選各三 seed 的變異報告", status="已完成",
         summary="治理 v1 三來源平均 70.78%（s=1.94pp，2s=3.88pp）；顯式特徵 fusion 70.74%（s=0.84pp，2s=1.67pp）。兩者差 −0.04pp，遠低於任一 2s，判定為並列不可區分。關鍵副產物：fusion 的種子變異遠小於治理 v1（HAM 上 s 由 3.83pp 降到 0.82pp）。以治理 v1 的 2s=3.88pp 回看，CP-002 比較表中僅 v13（−7.67pp）超出雜訊帶，連「資料治理帶來 +2.69pp」本身都落在帶內。",
         evidence=["資料治理與泛化修復/reports/seed_variance_v1.json"], archived=None, seeds=[17, 42, 2026]),
    dict(date="2026-09-08", stage="META", title="全專案格式統一與單一時間軸建立", status="已完成",
         summary="建立 開發歷程/格式約定.md 與由腳本產生的單一權威時間軸；18 份實驗 README 插入標準狀態區（原文未動）；兩支 sync 腳本改用統一 schema 命名空間並附加 stage_canonical／method_group／name_zh（既有欄位保留，UI 相容）；新增索引漂移檢查器。",
         evidence=["開發歷程/格式約定.md", "開發歷程/時間軸.md", "開發歷程/check_consistency.py"], archived=None, seeds=None),
    dict(date="2026-09-08", stage="S2", title="發現 v8（ConvNeXt-Tiny 384）HAM validation BA 已達 80.35／80.24", status="進行中",
         summary="查證第二階段全部版本後發現 v8 兩個 seed 皆超過 0.80，較 v7 三 seed 平均（77.30%）高 3.00pp，約為 v7 標準差的 6 倍；主因是 MEL recall 由 59.7% 升至 74.6%，解掉最大的 MEL→NV 混淆。v8 從未補第三個 seed，且在檔案室任務 12 的十張篩選中僅得 58.93 分而被略過。已建立 HAM10000_突破0.80_實驗排程.md。HAM validation 在第二階段與治理版切分下逐張相同（1,504 張），數字可直接比較。",
         evidence=["第二階段/results/v8_seed17.json", "開發歷程/HAM10000_突破0.80_實驗排程.md"], archived=None, seeds=[17, 42]),
    dict(date="2026-09-08", stage="META", title="修復 CP-003 階段 1 launcher 的輸出路徑缺陷", status="已完成",
         summary="run_cp003_stage1.py 的 governance 步驟漏傳 --output-root，訓練成功但結果落在 資料治理與泛化修復/results/regularized_seed2026 而非 .../results/formal_v1/regularized_seed2026，導致報告腳本判定缺結果而失敗。已將目錄搬回正確位置並在 launcher 補上參數與註解。",
         evidence=["資料治理與泛化修復/scripts/run_cp003_stage1.py"], archived=None, seeds=None),
    dict(date="2026-09-08", stage="S2", title="W0 完成：v8 補齊三 seed，HAM BA 平均 80.97%", status="已完成",
         summary="v8 seed 2026 為 82.32%，三 seed 平均 80.97%、s=1.17pp、最低 seed 80.24% —— 三個 seed 全部單獨超過 0.80。腳本判定 not_passed 僅因 s 超過預設的 1.0pp 上限；該條件被寫成對稱標準差上限而非下限條件，屬閘門設計缺陷，判定保留不追認。另量化出 BA 的種子變異大半來自小樣本類別（DF 僅 18 張，一張影像即影響 BA 0.79pp）。",
         evidence=["第二階段/results/W0_v8_gate.json", "第二階段/results/v8_seed2026.json"], archived=None, seeds=[17, 42, 2026]),
    dict(date="2026-09-08", stage="META", title="訓練資料載入吞吐優化（三支訓練程式）", status="已完成",
         summary="三支訓練程式加入 --num-workers／--prefetch-factor CLI（預設等同改動前），num_workers>0 時另開 persistent_workers。第二階段/scripts/train.py 另做結構重構：原為 module-level 程式碼，Windows spawn 會無限遞迴生 process，因此該支在改動前 num_workers>0 必定失敗；已包進 main() 並加 __main__ 保護，主體邏輯逐行未改。三份 config 完全未動，config_sha256 與 --resume 檢查不受影響。**重要**：num_workers>0 時資料增強改由子行程 RNG 產生，與既有結果分布相同但序列不同，單次 run 不可逐位元重現；三 seed 平均仍可比較。備份與還原說明見 _備份/2026-09-08_吞吐優化前/。",
         evidence=["_備份/2026-09-08_吞吐優化前/還原說明.md", "第二階段/scripts/train.py"], archived=None, seeds=None),
    dict(date="2026-09-09", stage="DATA", title="ISIC 擴充授權策略改為納入 CC-BY-NC，並完成下載規劃", status="已完成",
         summary="原策略（2026-08-13）排除 CC-BY-NC 以保留商業彈性，但 HAM10000 全部 10,015 張本身即為 CC-BY-NC 且是主訓練集，該保護在 HAM 納入時即已失效。使用者以「學校畢業專題、不考慮商業應用、只要沒有法律風險就都可以」為前提，決定新建的擴充集納入 CC-0／CC-BY／CC-BY-NC。既有的 isic_cc0_ccby_histopathology（7,886 張）維持不含 NC，兩者為獨立 source ID。依全 Archive metadata 快照（553,019 列）產生 17 項下載計畫，並與 HAM10000 逐 isic_id 比對出重疊量作為洩漏風險下界。",
         evidence=["Dataset/DATA_PROVENANCE.md", "Dataset/SOURCE_INCIDENTS.md", "Dataset/ISIC_Archive_擴充_2026-09-09/盤點報告.md"], archived=None, seeds=None),
    dict(date="2026-09-10", stage="DATA", title="ISIC 擴充下載完成 85,679 張；一項 metadata 缺失，稽核未通過", status="進行中",
         summary="17 項全數下載，影像 85,679 張，與 HAM10000 同 isic_id 重疊 8,774 張需在 manifest 階段排除。isic_expand.ps1 在實測中暴露五個缺陷：JSON 陣列展開、原生 exe 雙引號逸出（13 個含空格診斷全部 exit 2）、數量上限未生效（NV 實下 49,966、BCC 12,449）、工作目錄以日期命名產生孤兒目錄，前四項已修復；第五項「完成判定把 attribution.txt 與 .isic-partial 暫存檔算成影像」尚未修復，使 MEL/Melanoma Invasive 被誤判完成，缺 3 張影像且完全沒有 metadata.csv／attribution.txt／licenses/。因此逐張授權統計只涵蓋 83,973 張（CC-BY-NC 44,012、CC-BY 21,619、CC-0 18,342），與 85,679 差 1,706，缺口恰為該目錄影像數。補齊前無法履行逐張 attribution 義務，本來源不得用於對外發布結果，兩項重疊稽核亦尚未通過。",
         evidence=["Dataset/SOURCE_INCIDENTS.md", "Dataset/isic_expand.ps1", "Dataset/ISIC_Archive_擴充_2026-09-09/download_state.json"], archived=None, seeds=None),
    dict(date="2026-09-10", stage="META", title="建立 ISIC 擴充後的訓練排程（A–F 六階段、13 次訓練）", status="未開始",
         summary="階段 A 資料就緒（0 次訓練，含重建驗證集使 DF／VASC 各達 150 張以上，為最高優先）、B 基線重建（3 次）、C 修既有缺陷（3 次）、D MEL 專項（1 次）、E LOSO（3 次）、F 384 確認（3 次）。計算策略為在 224 探索、在 384 確認。所有訓練以階段 A 的兩項重疊稽核通過為前置條件。",
         evidence=["開發歷程/訓練排程_ISIC擴充後_2026-09-10.md"], archived=None, seeds=None),
]


def build() -> dict:
    for e in EVENTS:
        assert e["stage"] in STAGES, f"未知階段：{e['stage']}"
        assert e["status"] in STATUSES, f"未知狀態：{e['status']}"
        datetime.strptime(e["date"], "%Y-%m-%d")
    events = sorted(EVENTS, key=lambda e: (e["date"], e["stage"]))
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generator": "開發歷程/build_timeline.py",
        "authority": "本檔為專案事件時間的唯一權威來源；其他索引不得重複維護時間軸。",
        "stage_vocabulary": STAGES,
        "status_vocabulary": STATUSES,
        "event_count": len(events),
        "events": events,
    }


def render(doc: dict) -> str:
    lines = [
        "# SkinDetect 專案時間軸",
        "",
        "> **本檔由 `開發歷程/build_timeline.py` 產生，請勿手動編輯。**",
        "> 新增事件請修改該腳本的 `EVENTS`，再重新執行。",
        "> 機器可讀版本：`開發歷程/timeline.json`。",
        "",
        f"產生時間：{doc['generated_at']}　事件數：{doc['event_count']}",
        "",
        "## 唯一權威聲明",
        "",
        "本檔是專案**事件時間**的唯一權威來源。其他索引各司其職，不重複維護時間軸：",
        "",
        "| 索引 | 職責 | 不負責 |",
        "|---|---|---|",
        "| `開發歷程/時間軸.md`（本檔） | 什麼時候發生了什麼 | 檔案清單、模型清單 |",
        "| `開發歷程/checkpoints.json` | 匯總節點與其修正紀錄 | 個別實驗事件 |",
        "| `檔案室/圖表資料庫/總索引.csv` | 圖表與配套檔案的逐檔索引 | 事件敘述 |",
        "| `實驗紀錄庫/registry.json` | UI 讀取的實驗檔案索引 | 事件敘述、結論 |",
        "| `模型資產庫/model_registry.json` | UI 讀取的可推論模型清單 | 實驗歷程 |",
        "",
        "## 受控詞彙",
        "",
        "**階段**：" + "、".join(f"`{k}` {v}" for k, v in STAGES.items()),
        "",
        "**狀態**：" + "、".join(f"`{s}`" for s in STATUSES),
        "",
        "## 時間軸",
        "",
        "| 日期 | 階段 | 事件 | 狀態 | seeds | 歸檔 |",
        "|---|---|---|---|---|---|",
    ]
    for e in doc["events"]:
        seeds = "／".join(str(s) for s in e["seeds"]) if e["seeds"] else "—"
        arch = f"任務 {e['archived']}" if e["archived"] else "未歸檔"
        lines.append(f"| {e['date']} | {STAGES[e['stage']]} | {e['title']} | {e['status']} | {seeds} | {arch} |")
    lines += ["", "## 事件明細", ""]
    current = None
    for e in doc["events"]:
        if e["date"] != current:
            current = e["date"]
            lines += [f"### {current}", ""]
        lines += [
            f"**{e['title']}**　`{STAGES[e['stage']]}`　`{e['status']}`",
            "",
            e["summary"],
            "",
            "證據：" + "、".join(f"`{p}`" for p in e["evidence"]),
            "",
        ]
    return "\n".join(lines)


def main() -> None:
    doc = build()
    (HISTORY / "timeline.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (HISTORY / "時間軸.md").write_text(render(doc) + "\n", encoding="utf-8")
    print(f"已產生 {doc['event_count']} 筆事件：開發歷程/timeline.json、開發歷程/時間軸.md")


if __name__ == "__main__":
    main()
