from __future__ import annotations

import csv
import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
ARCHIVE = PROJECT / "檔案室" / "圖表資料庫"
ALLOWED = {".png", ".jpg", ".jpeg", ".svg", ".csv", ".json", ".md"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg"}
EXCLUDED_PARTS = {
    "smoke_results", "__pycache__", "scripts", "rendered", "final-render",
    "qa-render", "template-starter-preview", "ppt_inspect_cp001",
}


@dataclass(frozen=True)
class Collection:
    order: int
    date: str
    stage: str
    task: str
    description: str
    sources: tuple[tuple[str, str], ...]

    @property
    def folder_name(self) -> str:
        return f"{self.order:02d}_{self.stage}_{self.task}"


COLLECTIONS = (
    Collection(
        1, "2026-08-15", "驗證階段", "NoiseFilter設計稽核",
        "周邊權重圖與接觸表，用來檢查濾波器是否壓低影像邊緣干擾。",
        (("noisefilter設計", "驗證/reports/noisefilter_design"),),
    ),
    Collection(
        2, "2026-08-24", "部位預測階段", "部位預訓練與第二階段接續",
        "部位預訓練、凍結線性探測與並行教師模型的訓練曲線。",
        (
            ("實驗彙整", "實驗彙整/部位預訓練與第二階段接續_2026-08-24"),
            ("中文圖表", "experiment_plots_zh"),
        ),
    ),
    Collection(
        3, "2026-08-24", "第二階段", "部位權重完整微調正式對照",
        "DensePose 部位預訓練與 ImageNet 初始化的完整微調對照。",
        (("正式對照", "第二階段/部位權重完整微調正式對照"),),
    ),
    Collection(
        4, "2026-08-25", "第二階段", "預訓練干預對照",
        "主體模型在不同預訓練干預條件下的曲線與摘要。",
        (("干預對照", "實驗彙整/預訓練干預對照_2026-08-25"),),
    ),
    Collection(
        5, "2026-08-25", "第二階段", "ImageNet部位辨識純淨版三線比較",
        "ImageNet、部位辨識預訓練與純淨版本的同圖比較。",
        (("三線比較", "實驗彙整/預訓練干預三線對照_2026-08-25"),),
    ),
    Collection(
        6, "2026-08-25", "第二階段", "ConvNeXt純淨三線對照",
        "ConvNeXt-Tiny 條件下三種初始化版本的可用與配對比較。",
        (("ConvNeXt對照", "實驗彙整/ConvNeXt純淨三線對照_2026-08-25"),),
    ),
    Collection(
        7, "2026-08-25", "驗證階段", "全部資料集只推論驗證",
        "不訓練，只在全部相容驗證資料上比較 ConvNeXt 三種條件。",
        (("全資料驗證", "全資料集驗證推論_ConvNeXt三線"),),
    ),
    Collection(
        8, "2026-09-01", "多來源訓練", "混合訓練第一版",
        "HAM10000 與 BCN20000 混合訓練的曲線、前後比較及各類召回率。",
        (("第一版", "多來源混合訓練_第一版"),),
    ),
    Collection(
        9, "2026-09-01", "多來源訓練", "混合訓練第二版",
        "加入 PAD-UFES-20 後的三來源曲線、版本比較與直覺版圖表。",
        (("第二版", "多來源混合訓練_第二版"),),
    ),
    Collection(
        10, "2026-09-06", "泛化修復階段", "資料治理後正式訓練v1",
        "資料定義與洩漏治理後的三來源曲線、治理前後比較與疾病召回率。",
        (("formal_v1", "資料治理與泛化修復/results/formal_v1/regularized_seed17"),),
    ),
    Collection(
        11, "2026-09-07", "泛化修復階段", "較長正式訓練v2",
        "短版與長版正式訓練的穩健分數曲線及最佳結果比較。",
        (("formal_v2_long", "資料治理與泛化修復/results/formal_v2_long/regularized_seed17"),),
    ),
    Collection(
        12, "2026-09-08", "基底篩選階段", "十張影像熱力圖模型比較",
        "各候選模型的十張影像預測、Grad-CAM 忠實度、穩定性與總覽。",
        (("基底篩選", "模型基底篩選_熱力圖10張測試"),),
    ),
    Collection(
        13, "2026-09-08", "基底模型階段", "可切換功能正式訓練",
        "可切換基底模型的正式訓練曲線、校準結果與十張熱力圖稽核。",
        (("正式訓練", "基底模型發展_可切換正式訓練"),),
    ),
    Collection(
        14, "2026-09-07", "泛化修復階段", "完整覆蓋抽樣v3a",
        "完整覆蓋抽樣設定、訓練結果及目前問題特徵。",
        (("formal_v3a_coverage", "資料治理與泛化修復/results/formal_v3a_coverage"),),
    ),
    Collection(
        15, "2026-09-08", "泛化修復階段", "顯式影像特徵融合",
        "顯式色彩、紋理與品質特徵的單獨及融合實驗結果。",
        (("顯式特徵融合", "資料治理與泛化修復/顯式影像特徵融合實驗"),),
    ),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def kind_for(path: Path) -> tuple[str, str]:
    if path.suffix.lower() in IMAGE_EXTENSIONS:
        return "圖表", "圖表"
    if path.suffix.lower() == ".md":
        return "說明", "說明文件"
    return "數值資料", "數值或設定資料"


def display_label(collection: Collection, source_alias: str, path: Path) -> str:
    clean_name = path.stem.replace("_", " ").replace("-", " ")
    return f"{collection.stage}｜{collection.task}｜{source_alias}｜{clean_name}"


def eligible_files(root: Path):
    if not root.exists():
        return []
    return [
        path for path in root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in ALLOWED
        and not any(part in EXCLUDED_PARTS for part in path.parts)
    ]


def main() -> None:
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    manifest_rows: list[dict[str, str]] = []
    collection_summaries: list[dict] = []

    for collection in COLLECTIONS:
        destination_root = ARCHIVE / collection.date / collection.folder_name
        chart_labels: list[dict[str, str]] = []
        copied = 0
        for source_alias, source_relative in collection.sources:
            source_root = PROJECT / source_relative
            for source_path in eligible_files(source_root):
                relative_inside_source = source_path.relative_to(source_root)
                kind_folder, kind_label = kind_for(source_path)
                destination = destination_root / kind_folder / source_alias / relative_inside_source
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, destination)
                modified = datetime.fromtimestamp(source_path.stat().st_mtime).isoformat(timespec="seconds")
                label = display_label(collection, source_alias, source_path)
                row = {
                    "日期": collection.date,
                    "階段": collection.stage,
                    "任務": collection.task,
                    "標籤": label,
                    "檔案類型": kind_label,
                    "原始路徑": source_path.relative_to(PROJECT).as_posix(),
                    "收藏路徑": destination.relative_to(PROJECT).as_posix(),
                    "原始修改時間": modified,
                    "SHA256": sha256(source_path),
                }
                manifest_rows.append(row)
                copied += 1
                if source_path.suffix.lower() in IMAGE_EXTENSIONS:
                    chart_labels.append({
                        "圖表檔名": destination.name,
                        "中文標籤": label,
                        "原始路徑": row["原始路徑"],
                        "收藏路徑": row["收藏路徑"],
                    })

        label_metadata = {
            "日期": collection.date,
            "順序": collection.order,
            "階段": collection.stage,
            "任務": collection.task,
            "說明": collection.description,
            "來源資料夾": [source for _alias, source in collection.sources],
            "收錄檔案數": copied,
            "圖表數": len(chart_labels),
            "原始檔處理": "僅複製，未移動、未修改原始檔",
        }
        destination_root.mkdir(parents=True, exist_ok=True)
        (destination_root / "_標籤.json").write_text(
            json.dumps(label_metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        with (destination_root / "圖表標籤.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["圖表檔名", "中文標籤", "原始路徑", "收藏路徑"])
            writer.writeheader()
            writer.writerows(chart_labels)
        readme = (
            f"# {collection.task}\n\n"
            f"- 日期：{collection.date}\n"
            f"- 階段：{collection.stage}\n"
            f"- 任務：{collection.task}\n"
            f"- 說明：{collection.description}\n"
            f"- 圖表數：{len(chart_labels)}\n"
            f"- 配套檔案總數：{copied}\n"
            "- 保存方式：僅複製，原始實驗檔未移動、未修改。\n\n"
            "圖表的逐檔中文標籤與原始位置請查看 `圖表標籤.csv`；"
            "JSON、CSV 等曲線依據集中在 `數值資料`。\n"
        )
        (destination_root / "README.md").write_text(readme, encoding="utf-8")
        collection_summaries.append(label_metadata)

    fieldnames = ["日期", "階段", "任務", "標籤", "檔案類型", "原始路徑", "收藏路徑", "原始修改時間", "SHA256"]
    with (ARCHIVE / "總索引.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted(manifest_rows, key=lambda row: (row["日期"], row["階段"], row["任務"], row["收藏路徑"])))

    lines = [
        "# 過往圖表資料庫", "",
        "本資料庫按日期排列，再以階段與任務分組。所有內容均由原始位置複製，未移動或修改原始實驗資料。", "",
        "| 日期 | 階段 | 任務 | 圖表 | 配套檔案 |", "|---|---|---|---:|---:|",
    ]
    for item in collection_summaries:
        folder = next(c.folder_name for c in COLLECTIONS if c.date == item["日期"] and c.task == item["任務"])
        link = f"{item['日期']}/{folder}/README.md"
        lines.append(
            f"| {item['日期']} | {item['階段']} | [{item['任務']}]({link}) | "
            f"{item['圖表數']} | {item['收錄檔案數']} |"
        )
    lines.extend([
        "", "## 收錄規則", "",
        "- 收錄正式彙總圖、曲線、熱力圖稽核，以及支撐圖表的 CSV、JSON、Markdown。",
        "- 排除模型權重、原始 Dataset、UI 素材、簡報渲染圖、煙霧測試輸出及重複匯出資料夾。",
        "- `總索引.csv` 提供逐檔原始路徑、收藏路徑、標籤、修改時間與 SHA-256。",
    ])
    (ARCHIVE / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "collections": len(collection_summaries),
        "files": len(manifest_rows),
        "charts": sum(item["圖表數"] for item in collection_summaries),
        "archive": str(ARCHIVE),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
