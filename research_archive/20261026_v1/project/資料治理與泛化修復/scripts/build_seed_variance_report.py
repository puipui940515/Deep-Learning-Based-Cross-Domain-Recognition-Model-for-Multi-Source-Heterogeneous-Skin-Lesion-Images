from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
SEEDS = (17, 42, 2026)
SOURCES = ("HAM10000", "BCN20000", "PAD-UFES-20")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="建立 CP-003 階段 1 的三 seed 變異報告")
    parser.add_argument("--allow-partial", action="store_true", help="允許缺少 seed，只供執行前檢查")
    return parser.parse_args()


def candidate_paths() -> dict[str, dict[int, Path]]:
    return {
        "governance_v1": {
            seed: ROOT / "results" / "formal_v1" / f"regularized_seed{seed}" / "result.json"
            for seed in SEEDS
        },
        "explicit_feature_fusion": {
            seed: ROOT / "顯式影像特徵融合實驗" / "results" / f"fusion_seed{seed}" / "result.json"
            for seed in SEEDS
        },
    }


def read_metrics(path: Path) -> dict[str, float | int]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    best = payload["best"]
    validation = best["validation_by_source"]
    return {
        "seed": int(payload["seed"]),
        "best_epoch": int(best["epoch"]),
        "HAM10000_balanced_accuracy": float(validation["HAM10000"]["balanced_accuracy"]),
        "BCN20000_balanced_accuracy": float(validation["BCN20000"]["balanced_accuracy"]),
        "PAD-UFES-20_balanced_accuracy": float(validation["PAD-UFES-20"]["balanced_accuracy"]),
        "mean_source_balanced_accuracy": float(best["mean_source_balanced_accuracy"]),
        "BCN_weighted_robust_score": float(best["robust_selection_score"]),
    }


def summarize(rows: list[dict[str, float | int]]) -> dict:
    metric_names = [
        "HAM10000_balanced_accuracy",
        "BCN20000_balanced_accuracy",
        "PAD-UFES-20_balanced_accuracy",
        "mean_source_balanced_accuracy",
        "BCN_weighted_robust_score",
    ]
    summary = {}
    for name in metric_names:
        values = [float(row[name]) for row in rows]
        sample_std = statistics.stdev(values) if len(values) >= 2 else None
        summary[name] = {
            "mean": statistics.fmean(values),
            "sample_standard_deviation": sample_std,
            "two_s_threshold": 2.0 * sample_std if sample_std is not None else None,
            "values_by_seed": {str(row["seed"]): float(row[name]) for row in rows},
        }
    return summary


def main() -> None:
    args = parse_args()
    candidates = {}
    missing = []
    for candidate, paths in candidate_paths().items():
        rows = []
        for seed, path in paths.items():
            if path.is_file():
                rows.append(read_metrics(path))
            else:
                missing.append({"candidate": candidate, "seed": seed, "path": path.relative_to(ROOT.parent).as_posix()})
        if rows:
            candidates[candidate] = {
                "available_seeds": sorted(int(row["seed"]) for row in rows),
                "runs": rows,
                "summary": summarize(rows),
            }

    if missing and not args.allow_partial:
        details = ", ".join(f"{item['candidate']} seed {item['seed']}" for item in missing)
        raise SystemExit(f"缺少結果，無法建立正式三 seed 報告：{details}")

    comparison = None
    if all(len(candidates.get(name, {}).get("available_seeds", [])) == 3 for name in candidate_paths()):
        governance = candidates["governance_v1"]["summary"]
        fusion = candidates["explicit_feature_fusion"]["summary"]
        comparison = {}
        for metric in governance:
            difference = fusion[metric]["mean"] - governance[metric]["mean"]
            comparison[metric] = {
                "fusion_minus_governance_v1": difference,
                "governance_v1_two_s": governance[metric]["two_s_threshold"],
                "fusion_two_s": fusion[metric]["two_s_threshold"],
                "exceeds_both_two_s_thresholds": abs(difference) > max(
                    governance[metric]["two_s_threshold"], fusion[metric]["two_s_threshold"]
                ),
            }

    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "plan": "CP-003_stage_1",
        "required_seeds": list(SEEDS),
        "metric_units": "fraction_0_to_1",
        "selection_metric_name": "BCN 加權穩健分數",
        "selection_metric_formula": "0.5 * mean_source_balanced_accuracy + 0.5 * BCN20000_balanced_accuracy",
        "candidates": candidates,
        "comparison": comparison,
        "missing": missing,
        "formal_report_complete": not missing,
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    output = REPORTS / ("seed_variance_v1.partial.json" if missing else "seed_variance_v1.json")
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)
    print("正式三 seed 報告完成" if not missing else f"部分報告：尚缺 {len(missing)} 個 run")


if __name__ == "__main__":
    main()
