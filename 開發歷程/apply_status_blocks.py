"""在各實驗 README 的一級標題後插入／更新標準狀態區（格式約定 §4）。

原有內文完全不動；狀態區以 HTML 註解標記包夾，可重複執行覆蓋。

    python "開發歷程/apply_status_blocks.py"          # 實際寫入
    python "開發歷程/apply_status_blocks.py" --dry-run # 只預覽
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

HISTORY = Path(__file__).resolve().parent
PROJECT = HISTORY.parent
OPEN, CLOSE = "<!-- skindetect:status v1 -->", "<!-- /skindetect:status -->"

# 資料夾 -> 狀態欄位。與 開發歷程/timeline.json 的事件對應。
SPECS: dict[str, dict[str, str]] = {
    "驗證": dict(階段="驗證階段", 首次執行="2026-08-14", 狀態="已完成", seeds="—",
        主要指標="majority baseline BA = 1/7；lesion_id 三方交集 0",
        正式輸入="`Dataset/HAM10000/`",
        結果證據="`驗證/reports/validation_gate.json`", 歸檔="—"),
    "第一階段": dict(階段="第一階段", 首次執行="2026-08-14", 狀態="已結案", seeds="17／42／2026",
        主要指標="v1 validation BA 35.37%±2.66%；v2–v4 未完成",
        正式輸入="`第一階段/data/fixed_split.csv`",
        結果證據="`第一階段/results/experiment_log.csv`", 歸檔="—"),
    "第二階段": dict(階段="第二階段", 首次執行="2026-08-14", 狀態="已結案", seeds="17／42／2026",
        主要指標="v5 隨機 57.28%、v6 ImageNet 70.90%、v7 ConvNeXt 77.30%、v8 384 80.97%（三 seed 平均）；v9 未完成",
        正式輸入="`第二階段/data/fixed_split.csv`",
        結果證據="`第二階段/results/`", 歸檔="`檔案室` 任務 03–06"),
    "第三階段": dict(階段="第三階段", 首次執行="2026-08-22", 狀態="已鎖定", seeds="—",
        主要指標="尚未訓練；前置條件 v9 三 seed 未完成",
        正式輸入="`第三階段/data/fixed_split_with_site.csv`",
        結果證據="—", 歸檔="—"),
    "部位預測階段": dict(階段="部位預測階段", 首次執行="2026-08-23", 狀態="已結案", seeds="17／42／2026",
        主要指標="HAM 部位五類 BA 約 50.1%；DensePose 91.48%，但轉移至疾病分類三種接法皆為負",
        正式輸入="`Dataset/HAM10000/`、iToBoS、DensePose",
        結果證據="`部位預測階段/results/summary.json`", 歸檔="`檔案室` 任務 02"),
    "多來源混合訓練_第一版": dict(階段="多來源訓練階段", 首次執行="2026-09-01", 狀態="已完成", seeds="17",
        主要指標="BCN 由 35.50% 升至 60.07%（+24.57pp）",
        正式輸入="`多來源混合訓練_第一版/data/mixed_manifest.csv`",
        結果證據="`多來源混合訓練_第一版/results/imagenet_seed17/result.json`", 歸檔="`檔案室` 任務 08"),
    "多來源混合訓練_第二版": dict(階段="多來源訓練階段", 首次執行="2026-09-01", 狀態="已完成", seeds="17",
        主要指標="三來源平均 BA 69.37%；train-val 落差 BCN 38.00pp",
        正式輸入="`多來源混合訓練_第二版/data/mixed_manifest.csv`",
        結果證據="`多來源混合訓練_第二版/results/imagenet_seed17/result.json`", 歸檔="`檔案室` 任務 09"),
    "多來源混合訓練_ResNet18對照": dict(階段="多來源訓練階段", 首次執行="2026-09-01", 狀態="已完成", seeds="17",
        主要指標="三來源平均 BA 66.23%（ConvNeXt 對照為 69.37%）",
        正式輸入="`多來源混合訓練_第二版/data/mixed_manifest.csv`",
        結果證據="`多來源混合訓練_ResNet18對照/results/imagenet_seed17/result.json`", 歸檔="—"),
    "資料治理與泛化修復": dict(階段="泛化修復階段", 首次執行="2026-09-06", 狀態="進行中", seeds="17／42",
        主要指標="治理 v1 三來源平均 72.06%（seed 17）／68.55%（seed 42）；n=2 標準差 2.48pp",
        正式輸入="`資料治理與泛化修復/data/unified_manifest_v1.csv`",
        結果證據="`資料治理與泛化修復/results/formal_v1/`", 歸檔="`檔案室` 任務 10、11、14、15"),
    "模型基底篩選_熱力圖10張測試": dict(階段="基底篩選階段", 首次執行="2026-09-08", 狀態="已完成", seeds="17",
        主要指標="24 個模型；暫定第一名混合 V2 ResNet18，篩選分數 93.81",
        正式輸入="`模型基底篩選_熱力圖10張測試/data/selected_samples.csv`",
        結果證據="`模型基底篩選_熱力圖10張測試/results/model_summary.csv`", 歸檔="`檔案室` 任務 12"),
    "基底模型發展_可切換正式訓練": dict(階段="基底模型階段", 首次執行="2026-09-08", 狀態="已完成", seeds="17",
        主要指標="三來源平均 BA 64.39%、最差來源 47.95%（相對治理 v1 −7.67pp）",
        正式輸入="`資料治理與泛化修復/data/unified_manifest_v1.csv`",
        結果證據="`基底模型發展_可切換正式訓練/results/base_resnet18_full_features_v1_seed17/result.json`",
        歸檔="`檔案室` 任務 13"),
    "關卡式課程學習": dict(階段="課程學習階段", 首次執行="2026-09-08", 狀態="已結案", seeds="17",
        主要指標="第一關即未過閘門：HAM BA 74.91% < 80% 門檻，failure_reason=maximum_epochs",
        正式輸入="`資料治理與泛化修復/data/unified_manifest_v1.csv`",
        結果證據="`關卡式課程學習/results/curriculum_probability_v1_seed17/result.json`", 歸檔="—"),
    "全資料集快速測試": dict(階段="驗證階段", 首次執行="2026-08-14", 狀態="已完成", seeds="17／42／2026",
        主要指標="五來源固定抽樣快速推論；不重新訓練",
        正式輸入="`全資料集快速測試/manifest.csv`",
        結果證據="`全資料集快速測試/第二階段/results.json`", 歸檔="—"),
    "全資料集驗證推論_ConvNeXt三線": dict(階段="驗證階段", 首次執行="2026-08-25", 狀態="已完成", seeds="17／42",
        主要指標="ImageNet 版 HAM 74.83%、BCN 34.85%；首次量化跨來源崩潰",
        正式輸入="`全資料集驗證推論_ConvNeXt三線/validation_eval_manifest.csv`",
        結果證據="`全資料集驗證推論_ConvNeXt三線/metrics_summary_by_condition.csv`", 歸檔="`檔案室` 任務 07"),
    "實驗紀錄庫": dict(階段="專案治理", 首次執行="2026-09-05", 狀態="進行中", seeds="—",
        主要指標="UI 讀取的實驗檔案索引；目前 27 個實驗、286 檔",
        正式輸入="各實驗資料夾", 結果證據="`實驗紀錄庫/registry.json`", 歸檔="—"),
    "模型資產庫": dict(階段="專案治理", 首次執行="2026-09-05", 狀態="進行中", seeds="—",
        主要指標="UI 讀取的可推論模型清單",
        正式輸入="各實驗 checkpoint", 結果證據="`模型資產庫/model_registry.json`", 歸檔="—"),
    "開發歷程": dict(階段="專案治理", 首次執行="2026-08-15", 狀態="進行中", seeds="—",
        主要指標="目前節點 CP-002；CP-003 執行計畫進行中",
        正式輸入="—", 結果證據="`開發歷程/checkpoints.json`", 歸檔="—"),
    "ui_prototype": dict(階段="專案治理", 首次執行="2026-09-05", 狀態="進行中", seeds="—",
        主要指標="A／B／C 三版型原型；疾病模型與 Grad-CAM 已接上",
        正式輸入="`模型資產庫/model_registry.json`", 結果證據="—", 歸檔="—"),
}

FIELDS = ["階段", "首次執行", "狀態", "seeds", "主要指標", "正式輸入", "結果證據", "歸檔"]


def block(folder: str, spec: dict[str, str]) -> str:
    depth = "../" * len(Path(folder).parts)
    rows = "\n".join(f"| {k} | {spec[k]} |" for k in FIELDS)
    return (
        f"{OPEN}\n| 欄位 | 值 |\n|---|---|\n{rows}\n"
        f"| 時間軸 | [`開發歷程/時間軸.md`]({depth}開發歷程/時間軸.md) |\n"
        f"| 格式約定 | [`開發歷程/格式約定.md`]({depth}開發歷程/格式約定.md) |\n{CLOSE}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    written = skipped = 0
    for folder, spec in SPECS.items():
        readme = PROJECT / folder / "README.md"
        if not readme.is_file():
            print(f"[跳過] 找不到 {folder}/README.md")
            skipped += 1
            continue
        text = readme.read_text(encoding="utf-8")
        new_block = block(folder, spec)
        if OPEN in text:
            updated = re.sub(re.escape(OPEN) + r".*?" + re.escape(CLOSE), new_block, text, flags=re.S)
            action = "更新"
        else:
            match = re.search(r"^(#[^\n]*\n)", text)
            if not match:
                print(f"[跳過] {folder}/README.md 沒有一級標題")
                skipped += 1
                continue
            head = match.group(1)
            updated = text.replace(head, head + "\n" + new_block + "\n", 1)
            action = "插入"
        if updated == text:
            continue
        if not args.dry_run:
            readme.write_text(updated, encoding="utf-8")
        print(f"[{action}] {folder}/README.md")
        written += 1
    print(f"\n完成：{written} 份{'（dry-run，未寫入）' if args.dry_run else ''}，跳過 {skipped} 份")


if __name__ == "__main__":
    main()
