from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path


LIBRARY = Path(__file__).resolve().parent
PROJECT_ROOT = LIBRARY.parent
REGISTRY_PATH = LIBRARY / "model_registry.json"
CSV_PATH = LIBRARY / "模型時間排序.csv"
MARKDOWN_PATH = LIBRARY / "模型時間排序.md"


# 首次開發時間以專案時間軸與現存最早 checkpoint 證據交叉核對。
# 此欄不因補 seed、重訓、搬移或同步模型而改變。
DEVELOPED_AT = {
    "stage1_v1": "2026-08-14T09:42:24+08:00",
    "stage2_v5": "2026-08-14T11:29:46+08:00",
    "stage1_v1_noisefilter": "2026-08-14T20:26:14+08:00",
    "stage2_v5_noisefilter": "2026-08-14T21:16:48+08:00",
    "stage2_v6": "2026-08-15T23:25:14+08:00",
    "stage2_v7": "2026-08-16T01:07:32+08:00",
    "stage2_v8": "2026-08-16T04:57:00+08:00",
    "frozen_imagenet": "2026-08-24T07:22:21+08:00",
    "frozen_densepose_true": "2026-08-24T07:47:56+08:00",
    "frozen_densepose_shuffled": "2026-08-24T08:06:32+08:00",
    "parallel_imagenet": "2026-08-24T09:58:30+08:00",
    "parallel_densepose_true": "2026-08-24T10:40:10+08:00",
    "parallel_densepose_shuffled": "2026-08-24T11:13:58+08:00",
    "finetune_imagenet": "2026-08-24T16:15:00+08:00",
    "finetune_densepose_true": "2026-08-24T18:13:47+08:00",
    "stage2_v10": "2026-08-25T10:10:45+08:00",
    "mixed_v1": "2026-08-31T23:18:35+08:00",
    "mixed_convnext": "2026-09-01T01:45:05+08:00",
    "mixed_resnet18": "2026-09-01T15:32:17+08:00",
    "governance_v1_seed17": "2026-09-06T20:30:16+08:00",
    "governance_v2_long_seed17": "2026-09-07T03:33:32+08:00",
    "governance_v3a_seed17": "2026-09-07T18:39:45+08:00",
    "explicit_fusion_seed17": "2026-09-08T02:29:58+08:00",
    "configurable_resnet18_v13_seed17": "2026-09-08T06:18:11+08:00",
    "governance_v1_seed42": "2026-09-08T17:56:19+08:00",
}


SPECIAL_NOTES = {
    "stage2_v8": (
        "首次時間採未被覆寫的 v8 seed 42 checkpoint；"
        "目前 seed 17 checkpoint 是後續補訓／重建版本。"
    ),
}


def source_timestamp(source: str) -> str | None:
    path = PROJECT_ROOT / Path(source)
    if not path.is_file():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds")


def main() -> None:
    payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8-sig"))
    models = payload.get("models", [])
    registry_ids = {item["id"] for item in models}
    expected_ids = set(DEVELOPED_AT)
    missing_dates = sorted(registry_ids - expected_ids)
    missing_models = sorted(expected_ids - registry_ids)
    if missing_dates or missing_models:
        raise RuntimeError(
            "時間映射與模型登錄不一致："
            f"缺日期={missing_dates}；登錄中缺模型={missing_models}"
        )

    for item in models:
        item["developed_at"] = DEVELOPED_AT[item["id"]]
        item["checkpoint_updated_at"] = source_timestamp(item["source"])
        item["chronology_basis"] = "project_timeline_and_earliest_checkpoint"
        item["chronology_note"] = SPECIAL_NOTES.get(item["id"], "")

    models.sort(key=lambda item: (item["developed_at"], item["id"]))
    for index, item in enumerate(models, start=1):
        item["chronological_order"] = index

    payload["models"] = models
    payload["model_order"] = "developed_at_ascending"
    payload["chronology_sorted_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    REGISTRY_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    columns = [
        "chronological_order",
        "developed_at",
        "checkpoint_updated_at",
        "id",
        "name_zh",
        "group",
        "architecture",
        "wrapper",
        "available",
        "runtime_supported",
        "source",
        "chronology_note",
    ]
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(models)

    lines = [
        "# 模型時間排序",
        "",
        "排序依據：首次開發時間，由專案時間軸與現存最早 checkpoint 證據交叉核對。",
        "`checkpoint 更新時間` 只表示目前來源檔案最後修改時間，可能受到補 seed、重訓或重建影響。",
        "",
        "| 順序 | 首次開發時間 | 模型 ID | 模型 | 階段／方法 | 架構 | checkpoint 更新時間 | UI |",
        "|---:|---|---|---|---|---|---|---|",
    ]
    for item in models:
        runtime = "可推論" if item.get("runtime_supported", True) and item.get("available") else "未支援／不可用"
        checkpoint_time = item.get("checkpoint_updated_at") or "檔案不存在"
        lines.append(
            f"| {item['chronological_order']} | {item['developed_at']} | `{item['id']}` | "
            f"{item.get('name_zh', item.get('name', ''))} | {item.get('group', '')} | "
            f"{item.get('architecture', '')} | {checkpoint_time} | {runtime} |"
        )
    lines.extend([
        "",
        "## 特別註記",
        "",
        "- `stage2_v8` 的首次時間採 2026-08-16 的 v8 seed 42 checkpoint；目前 seed 17 檔案於後續補訓／重建時更新，不能拿 2026-09-09 當作模型首次出現時間。",
        "- DensePose 部位預訓練本體不是七分類疾病模型，因此不在疾病模型登錄的 25 筆內；其接續疾病任務的凍結、並行與微調模型已逐一列入。",
        "- 重新執行 `sync_models.py` 後，請再執行 `sort_models_by_time.py`，以恢復時間欄位及排序。",
        "",
    ])
    MARKDOWN_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"已按時間排序 {len(models)} 個模型")
    print(MARKDOWN_PATH)
    print(CSV_PATH)


if __name__ == "__main__":
    main()
