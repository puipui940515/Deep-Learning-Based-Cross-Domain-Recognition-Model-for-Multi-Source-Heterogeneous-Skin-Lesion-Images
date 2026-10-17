from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


LIBRARY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = LIBRARY_DIR.parent
RECORDS_DIR = LIBRARY_DIR / "records"
ALLOWED_SUFFIXES = {".json", ".csv", ".md", ".png"}
EXCLUDED_PARTS = {"__pycache__", "checkpoints", "config", "data", "scripts", "smoke_results", "src"}
MAX_FILE_BYTES = 15 * 1024 * 1024


EXPERIMENTS = [
    {
        "id": "stage1_baseline", "stage": "第一階段", "title": "第一階段基線",
        "summary": "建立固定切分與三種種子基線，保存各種子結果、實驗日誌與版本摘要。",
        "sources": ["第一階段/results"],
        "metrics": [{"label": "v1 Validation BA", "value": "35.37%"}, {"label": "v1 macro-F1", "value": "37.29%"}, {"label": "種子數", "value": "3"}],
    },
    {
        "id": "stage1_noisefilter", "stage": "第一階段", "title": "第一階段 NoiseFilter 搭載",
        "summary": "在第一階段基線加入四種固定影像濾波核心，對照乾淨影像與擾動影像。",
        "sources": ["第一階段/noisefilter搭載實驗"],
        "metrics": [{"label": "基線乾淨 BA", "value": "35.37%"}, {"label": "濾波乾淨 BA", "value": "32.27%"}, {"label": "差值", "value": "-3.09 pp"}],
    },
    {
        "id": "stage2_baseline", "stage": "第二階段", "title": "第二階段主體模型演進",
        "summary": "保存 v5 至 v10 的主體模型結果；已完成版本以三種種子進行比較。",
        "sources": ["第二階段/results"],
        "metrics": [{"label": "v5 Validation BA", "value": "57.28%"}, {"label": "v6 Validation BA", "value": "70.90%"}, {"label": "v7 Validation BA", "value": "77.30%"}],
    },
    {
        "id": "stage2_noisefilter", "stage": "第二階段", "title": "第二階段 NoiseFilter 搭載",
        "summary": "比較第二階段基線與固定濾波核心在乾淨、擾動驗證資料上的表現。",
        "sources": ["第二階段/noisefilter搭載實驗"],
        "metrics": [{"label": "基線乾淨 BA", "value": "57.28%"}, {"label": "濾波乾淨 BA", "value": "50.55%"}, {"label": "濾波穩健性下降", "value": "7.35 pp"}],
    },
    {
        "id": "stage2_site_labels", "stage": "第二階段", "title": "部位標籤搭載先導對照",
        "summary": "比較一般控制組與部位平衡取樣，記錄整體及最差已知部位的結果。",
        "sources": ["第二階段/部位標籤搭載實驗"],
        "metrics": [{"label": "控制組 BA", "value": "75.61%"}, {"label": "部位平衡 BA", "value": "74.79%"}, {"label": "最差部位差值", "value": "+1.47 pp"}],
    },
    {
        "id": "site_prediction", "stage": "部位預測", "title": "部位預測基線與資料組合",
        "summary": "保存部位分類基線、不同資料來源 profile 與資料稽核紀錄。",
        "sources": ["部位預測階段/results"],
        "metrics": [{"label": "Validation BA", "value": "50.20%"}, {"label": "macro-F1", "value": "44.33%"}, {"label": "Accuracy", "value": "55.12%"}],
    },
    {
        "id": "densepose_site_pretraining", "stage": "部位預測", "title": "DensePose 五類部位預訓練",
        "summary": "使用 DensePose 衍生的五類身體部位裁切資料進行先導及夜間訓練。",
        "sources": ["部位預測階段/DensePose_部位預訓練/results"], "metrics": [],
    },
    {
        "id": "itobos_site_pretraining", "stage": "部位預測", "title": "iToBoS 部位預訓練系列",
        "summary": "收錄正式部位預訓練、隨機標籤對照、雜訊遮罩與 label smoothing 紀錄。",
        "sources": ["部位預測階段/iToBoS_部位預訓練"], "metrics": [],
    },
    {
        "id": "stage2_site_transfer", "stage": "第二階段", "title": "部位模型接續實驗",
        "summary": "比較基線、偏差控制、真實部位融合與打亂部位輸入。",
        "sources": ["第二階段/部位模型接續實驗"],
        "metrics": [{"label": "基線 BA", "value": "77.17%"}, {"label": "部位融合 BA", "value": "77.54%"}, {"label": "差值", "value": "+0.36 pp"}],
    },
    {
        "id": "stage2_frozen_backbone", "stage": "第二階段", "title": "凍結部位 Backbone 短訓練",
        "summary": "凍結預訓練 backbone，只訓練疾病分類頭，對照 ImageNet 與部位權重。",
        "sources": ["第二階段/凍結部位Backbone短訓練"],
        "metrics": [{"label": "ImageNet BA", "value": "34.63%"}, {"label": "真實部位 BA", "value": "17.47%"}, {"label": "種子數", "value": "3"}],
    },
    {
        "id": "stage2_parallel_teacher", "stage": "第二階段", "title": "並行凍結部位特徵實驗",
        "summary": "把凍結模型輸出作為獨立輸入，與疾病主體模型並行融合。",
        "sources": ["第二階段/並行凍結部位特徵實驗"],
        "metrics": [{"label": "ImageNet teacher BA", "value": "76.04%"}, {"label": "部位 teacher BA", "value": "76.13%"}, {"label": "推論需 teacher", "value": "是"}],
    },
    {
        "id": "stage2_full_finetune", "stage": "第二階段", "title": "部位權重完整微調正式對照",
        "summary": "在相同資料與訓練尺度下，完整微調 ImageNet 初始化與部位模型初始化。",
        "sources": ["第二階段/部位權重完整微調正式對照"], "metrics": [],
    },
    {
        "id": "stage3_setup", "stage": "第三階段", "title": "第三階段流程建立與前置檢查",
        "summary": "保存部位標籤流程、資料 manifest 稽核、煙霧測試與 prerequisite gate。",
        "sources": ["第三階段/results", "第三階段/README.md"], "metrics": [],
    },
    {
        "id": "all_dataset_quick", "stage": "跨資料集驗證", "title": "全資料集快速測試",
        "summary": "第一、第二階段模型使用當時可用資料進行快速比較。",
        "sources": ["全資料集快速測試"], "metrics": [],
    },
    {
        "id": "all_dataset_formal", "stage": "跨資料集驗證", "title": "全資料集正式測試",
        "summary": "以較正式設定重做第一、第二階段的全資料測試並保存結論。",
        "sources": ["全資料集正式測試"], "metrics": [],
    },
    {
        "id": "three_line_validation", "stage": "跨資料集驗證", "title": "ConvNeXt 三線外部驗證",
        "summary": "比較 ImageNet、部位預訓練與純淨 ConvNeXt 在相關驗證集的輸出。",
        "sources": ["全資料集驗證推論_ConvNeXt三線"], "metrics": [],
    },
    {
        "id": "mixed_source_v1", "stage": "多來源訓練", "title": "HAM10000＋BCN20000 混合訓練",
        "summary": "第一版多來源混合訓練，固定來源平衡取樣並分別驗證 HAM10000 與 BCN20000。",
        "sources": ["多來源混合訓練_第一版"],
        "metrics": [{"label": "訓練樣本", "value": "17,274"}, {"label": "HAM BA", "value": "76.85%"}, {"label": "BCN BA", "value": "60.07%"}],
    },
    {
        "id": "mixed_source_v2", "stage": "多來源訓練", "title": "HAM10000＋BCN20000＋PAD-UFES-20",
        "summary": "第二版加入 PAD-UFES-20，以三來源等比例期望取樣訓練 ConvNeXt-Tiny。",
        "sources": ["多來源混合訓練_第二版"],
        "metrics": [{"label": "訓練樣本", "value": "18,979"}, {"label": "HAM BA", "value": "79.10%"}, {"label": "BCN BA", "value": "57.79%"}],
    },
    {
        "id": "mixed_source_resnet18", "stage": "多來源訓練", "title": "三來源 ResNet18 規模對照",
        "summary": "使用與第二版相同三來源資料及切分，改以 ResNet18 作為較小模型對照。",
        "sources": ["多來源混合訓練_ResNet18對照"],
        "metrics": [{"label": "訓練樣本", "value": "18,979"}, {"label": "HAM BA", "value": "72.04%"}, {"label": "BCN BA", "value": "52.41%"}],
    },
    {
        "id": "governance_v1", "stage": "泛化修復", "title": "資料治理後正式訓練 v1",
        "summary": "統一標籤、隔離重複病灶並固定三來源驗證後的正式基準；目前已有 seed 17 與 42。",
        "sources": ["資料治理與泛化修復/results/formal_v1"],
        "metrics": [{"label": "seed 17 三來源平均 BA", "value": "72.06%"}, {"label": "seed 17 BCN BA", "value": "62.83%"}, {"label": "現有種子數", "value": "2"}],
    },
    {
        "id": "governance_v2_long", "stage": "泛化修復", "title": "資料治理長訓練 v2",
        "summary": "沿用治理 v1 資料協定延長訓練，保存完整曲線與最佳結果。",
        "sources": ["資料治理與泛化修復/results/formal_v2_long"],
        "metrics": [{"label": "三來源平均 BA", "value": "71.81%"}, {"label": "BCN BA", "value": "61.89%"}, {"label": "種子", "value": "17"}],
    },
    {
        "id": "governance_v3a_coverage", "stage": "泛化修復", "title": "資料治理完整覆蓋抽樣 v3a",
        "summary": "使用完整覆蓋抽樣器的治理後訓練，用於檢查來源配額與類別平衡行為。",
        "sources": ["資料治理與泛化修復/results/formal_v3a_coverage", "資料治理與泛化修復/V3A_完整覆蓋抽樣.md", "資料治理與泛化修復/V3A_結果與目前問題特徵_2026-09-07.md"],
        "metrics": [{"label": "三來源平均 BA", "value": "70.41%"}, {"label": "BCN BA", "value": "59.92%"}, {"label": "種子", "value": "17"}],
    },
    {
        "id": "explicit_feature_fusion", "stage": "泛化修復", "title": "顯式影像特徵融合",
        "summary": "把色彩、紋理、品質及中央與邊緣差值等顯式特徵與 ConvNeXt 影像特徵融合。",
        "sources": ["資料治理與泛化修復/顯式影像特徵融合實驗"],
        "metrics": [{"label": "三來源平均 BA", "value": "71.56%"}, {"label": "BCN BA", "value": "65.79%"}, {"label": "現有種子數", "value": "1"}],
    },
    {
        "id": "model_base_screening", "stage": "基底篩選", "title": "十張影像與熱力圖基底篩選",
        "summary": "以十張影像比較候選模型的疾病輸出、Grad-CAM 忠實度與穩定性。",
        "sources": ["模型基底篩選_熱力圖10張測試"],
        "metrics": [],
    },
    {
        "id": "configurable_formal_training", "stage": "基底模型", "title": "可切換功能正式訓練",
        "summary": "以設定檔控制顯式特徵、部位輔助、來源對抗、校準及熱力圖稽核的正式訓練。",
        "sources": ["基底模型發展_可切換正式訓練"],
        "metrics": [{"label": "三來源平均 BA", "value": "64.39%"}, {"label": "BCN BA", "value": "47.95%"}, {"label": "種子", "value": "17"}],
    },
    {
        "id": "experiment_summaries", "stage": "實驗彙整", "title": "預訓練與部位影響匯總圖表",
        "summary": "集中保存三線比較、部位預訓練接續及多來源訓練的中文曲線與摘要。",
        "sources": ["實驗彙整", "plots_export"], "metrics": [],
    },
    {
        "id": "external_web_smoke", "stage": "外部案例", "title": "Wikimedia 六張外部影像煙霧測試",
        "summary": "三類各兩張公開皮膚鏡影像；保存來源授權、七類輸出與命中結果。",
        "sources": ["ui_prototype/external_test_2026-09-05"],
        "metrics": [{"label": "案例數", "value": "6"}, {"label": "命中", "value": "4"}, {"label": "小樣本 Accuracy", "value": "66.7%"}],
    },
]


def iter_record_files(source: Path):
    candidates = [source] if source.is_file() else source.rglob("*")
    for path in candidates:
        if not path.is_file() or path.suffix.lower() not in ALLOWED_SUFFIXES:
            continue
        relative_parts = set(path.relative_to(PROJECT_ROOT).parts)
        if relative_parts & EXCLUDED_PARTS or path.stat().st_size > MAX_FILE_BYTES:
            continue
        yield path


def artifact_priority(record: dict) -> tuple[int, str]:
    name = record["name"].lower()
    if name in {"summary.json", "version_summary.csv", "results.json", "results.csv"}:
        return (0, name)
    if "結論" in name or "實驗記錄" in name or "實驗整理" in name:
        return (1, name)
    if name.endswith(".png"):
        return (2, name)
    return (3, name)


# --- 格式約定 v1：階段受控詞彙對照（見 開發歷程/格式約定.md §2）---
# 既有欄位一律保留以維持 UI 相容；標準欄位為「附加」，不取代。
CANONICAL_STAGE = {
    "泛化修復": "泛化修復階段", "資料治理後模型": "泛化修復階段",
    "基底篩選": "基底篩選階段", "基底模型": "基底模型階段",
    "多來源訓練": "多來源訓練階段", "部位預測": "部位預測階段",
    "跨資料集驗證": "驗證階段", "外部案例": "驗證階段", "實驗彙整": "專案治理",
    "第一階段": "第一階段", "第二階段": "第二階段", "第三階段": "第三階段",
    "驗證階段": "驗證階段", "課程學習階段": "課程學習階段", "專案治理": "專案治理",
}
METHOD_GROUPS = {"並行特徵", "凍結 Backbone", "完整微調", "研究模型（UI 尚未支援）"}
SCHEMA_VERSION = "skindetect-index-v1"


def build_registry() -> dict:
    RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    registry_entries = []
    total_files = 0
    total_bytes = 0

    for definition in EXPERIMENTS:
        copied = []
        seen = set()
        target_root = RECORDS_DIR / definition["id"]
        target_root.mkdir(parents=True, exist_ok=True)
        for source_text in definition["sources"]:
            source = PROJECT_ROOT / source_text
            if not source.exists():
                continue
            for path in iter_record_files(source):
                project_relative = path.relative_to(PROJECT_ROOT)
                key = project_relative.as_posix()
                if key in seen:
                    continue
                seen.add(key)
                destination = target_root / project_relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
                library_relative = destination.relative_to(LIBRARY_DIR)
                size = destination.stat().st_size
                copied.append({
                    "name": destination.name,
                    "kind": destination.suffix.lower().lstrip("."),
                    "size_bytes": size,
                    "source_path": key,
                    "library_path": library_relative.as_posix(),
                    "url": "/experiment-files/" + library_relative.as_posix(),
                })
                total_files += 1
                total_bytes += size
        copied.sort(key=artifact_priority)
        registry_entries.append({
            "id": definition["id"], "stage": definition["stage"], "title": definition["title"],
            "summary": definition["summary"], "metrics": definition["metrics"],
            "source_roots": definition["sources"], "file_count": len(copied), "files": copied,
            # 格式約定 v1 附加欄位（既有欄位不變）
            "stage_canonical": CANONICAL_STAGE.get(definition["stage"], definition["stage"]),
            "name_zh": definition["title"],
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "legacy_schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generator": "實驗紀錄庫/sync_registry.py",
        "authority": "本檔由腳本產生，請勿手動編輯。事件時間軸的權威來源為 開發歷程/時間軸.md。",
        "fixed_folder": LIBRARY_DIR.name,
        "experiment_count": len(registry_entries),
        "file_count": total_files,
        "total_bytes": total_bytes,
        "experiments": registry_entries,
    }


def main() -> None:
    registry = build_registry()
    output = LIBRARY_DIR / "registry.json"
    output.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已建立 {registry['experiment_count']} 組實驗、{registry['file_count']} 個檔案索引")
    print(output)


if __name__ == "__main__":
    main()
