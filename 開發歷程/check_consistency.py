"""SkinDetect 索引一致性檢查（唯讀，不修改任何檔案）。

    python "開發歷程/check_consistency.py"

依 開發歷程/格式約定.md 第七節檢查各索引之間的漂移。
"""
from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

HISTORY = Path(__file__).resolve().parent
PROJECT = HISTORY.parent

# 既有詞彙 → 權威階段名稱。格式約定 §2 的相容對照表。
STAGE_ALIASES = {
    "泛化修復": "泛化修復階段", "資料治理後模型": "泛化修復階段",
    "基底篩選": "基底篩選階段", "基底模型": "基底模型階段",
    "多來源訓練": "多來源訓練階段", "部位預測": "部位預測階段",
    "跨資料集驗證": "驗證階段", "外部案例": "驗證階段", "實驗彙整": "專案治理",
}
# 模型資產庫的方法別分組，不是階段
METHOD_GROUPS = {"並行特徵", "凍結 Backbone", "完整微調", "研究模型（UI 尚未支援）"}

findings: list[tuple[str, str]] = []


def note(level: str, message: str) -> None:
    findings.append((level, message))


def load_json(rel: str):
    path = PROJECT / rel
    if not path.is_file():
        note("ERROR", f"找不到 {rel}")
        return None
    return json.loads(path.read_text(encoding="utf-8-sig"))


def check_timeline_and_vocab(timeline: dict) -> None:
    canonical = set(timeline["stage_vocabulary"].values())

    for rel, field, extractor in [
        ("實驗紀錄庫/registry.json", "stage", lambda d: [e["stage"] for e in d["experiments"]]),
        ("模型資產庫/model_registry.json", "group", lambda d: [m["group"] for m in d["models"]]),
    ]:
        doc = load_json(rel)
        if doc is None:
            continue
        for value in sorted(set(extractor(doc))):
            if value in canonical or value in METHOD_GROUPS:
                continue
            mapped = STAGE_ALIASES.get(value)
            if mapped:
                note("INFO", f"{rel} 的 {field}=「{value}」以相容對照映射到「{mapped}」")
            else:
                note("WARN", f"{rel} 的 {field}=「{value}」不在受控詞彙也不在對照表")

    index = PROJECT / "檔案室/圖表資料庫/總索引.csv"
    if index.is_file():
        rows = list(csv.DictReader(index.open(encoding="utf-8-sig")))
        for value in sorted({r["階段"] for r in rows}):
            if value not in canonical and value not in STAGE_ALIASES:
                note("WARN", f"檔案室/總索引.csv 的階段「{value}」不在受控詞彙也不在對照表")
    else:
        note("ERROR", "找不到 檔案室/圖表資料庫/總索引.csv")


def check_archive_claims(timeline: dict) -> None:
    root = PROJECT / "檔案室/圖表資料庫"
    if not root.is_dir():
        note("ERROR", "找不到 檔案室/圖表資料庫")
        return
    existing = set()
    for day in root.iterdir():
        if day.is_dir():
            for task in day.iterdir():
                if task.is_dir() and "_" in task.name:
                    existing.add(task.name.split("_", 1)[0])
    for event in timeline["events"]:
        claimed = event["archived"]
        if claimed:
            for number in str(claimed).split(","):
                if number.strip() not in existing:
                    note("ERROR", f"時間軸宣稱「{event['title']}」歸檔為任務 {number.strip()}，但檔案室沒有該編號")


def check_evidence_paths(timeline: dict) -> None:
    for event in timeline["events"]:
        for rel in event["evidence"]:
            if not (PROJECT / rel).exists():
                note("ERROR", f"時間軸事件「{event['title']}」的證據路徑不存在：{rel}")


def check_corrections_pairing() -> None:
    checkpoints = load_json("開發歷程/checkpoints.json")
    if checkpoints is None:
        return
    for entry in checkpoints["checkpoints"]:
        document = PROJECT / entry["summary_document"]
        json_count = len(entry.get("corrections", []))
        if not document.is_file():
            note("ERROR", f"{entry['id']} 的 summary_document 不存在：{entry['summary_document']}")
            continue
        markdown_count = len(re.findall(r"^### 修正 \d+", document.read_text(encoding="utf-8"), re.M))
        if json_count != markdown_count:
            note("WARN", f"{entry['id']}：checkpoints.json 有 {json_count} 筆 corrections，"
                         f"但 {document.name} 的後續修正區有 {markdown_count} 筆")


def check_freshness() -> None:
    now = datetime.now(timezone.utc)
    for rel in ["開發歷程/timeline.json", "實驗紀錄庫/registry.json", "模型資產庫/model_registry.json"]:
        doc = load_json(rel)
        if not doc or "generated_at" not in doc:
            note("WARN", f"{rel} 缺少 generated_at")
            continue
        stamp = doc["generated_at"].replace("Z", "+00:00")
        try:
            age = (now - datetime.fromisoformat(stamp)).days
        except ValueError:
            note("WARN", f"{rel} 的 generated_at 非 ISO 8601：{doc['generated_at']}")
            continue
        level = "WARN" if age > 3 else "OK"
        note(level, f"{rel} 產生於 {age} 天前")


def check_readme_status_blocks() -> None:
    marker = "<!-- skindetect:status v1 -->"
    missing = []
    for readme in sorted(PROJECT.glob("*/README.md")):
        if readme.parent.name.startswith((".", "_")) or readme.parent.name == "Dataset":
            continue
        if marker not in readme.read_text(encoding="utf-8"):
            missing.append(str(readme.relative_to(PROJECT)))
    if missing:
        note("INFO", f"{len(missing)} 份 README 尚無標準狀態區：" + "、".join(missing))


def main() -> None:
    timeline = load_json("開發歷程/timeline.json")
    if timeline is None:
        raise SystemExit("時間軸不存在，請先執行 開發歷程/build_timeline.py")
    check_timeline_and_vocab(timeline)
    check_archive_claims(timeline)
    check_evidence_paths(timeline)
    check_corrections_pairing()
    check_freshness()
    check_readme_status_blocks()

    order = {"ERROR": 0, "WARN": 1, "INFO": 2, "OK": 3}
    print("SkinDetect 索引一致性檢查")
    print("=" * 60)
    for level, message in sorted(findings, key=lambda f: order[f[0]]):
        print(f"[{level:5s}] {message}")
    counts = {k: sum(1 for level, _ in findings if level == k) for k in order}
    print("=" * 60)
    print("　".join(f"{k}={counts[k]}" for k in order))
    raise SystemExit(1 if counts["ERROR"] else 0)


if __name__ == "__main__":
    main()
