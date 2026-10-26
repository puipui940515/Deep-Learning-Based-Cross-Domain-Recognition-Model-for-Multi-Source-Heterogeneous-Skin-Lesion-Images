"""重播既有 C 分數驗證 adapter 數學；不是重跑 C 分析或模型推論。"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from .contract import ModelContract, sha256
from .core import CLASS_CODES, SINGLE, ENSEMBLE, combine_probabilities, ranked_probabilities


def reference_tables(contract):
    references = contract.spec["references"]
    for key in ("seed_predictions", "ensemble_predictions", "seed_provenance"):
        if sha256(references[key]["path"]) != references[key]["sha256"]:
            raise RuntimeError(f"既有 C/B 參照來源指紋不同：{key}")
    grouped = {}
    with Path(references["seed_predictions"]["path"]).open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["split"] != "validation":
                raise RuntimeError("參照資料必須全部是 Validation")
            seed = int(row["seed"])
            key = (row["source"], row["record_id"])
            if seed not in (1, 2, 3) or seed in grouped.setdefault(key, {}):
                raise RuntimeError("重複或未知 Seed")
            if int(row["best_epoch"]) != contract.spec["members"][str(seed)]["best_epoch"]:
                raise RuntimeError("參照最佳輪不符")
            grouped[key][seed] = row
    ensemble = {}
    with Path(references["ensemble_predictions"]["path"]).open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["split"] != "validation":
                raise RuntimeError("集成參照必須全部是 Validation")
            key = (row["source"], row["record_id"])
            if key in ensemble:
                raise RuntimeError("集成參照重複影像")
            ensemble[key] = row
    if len(grouped) != 3611 or set(grouped) != set(ensemble):
        raise RuntimeError("參照集合不符合既有 3611 張 Validation")
    return grouped, ensemble


def scores(row):
    return [float(row["score_" + code]) for code in CLASS_CODES]


def check_reference(contract):
    contract.validate((1, 2, 3), weights=False)
    grouped, ensemble = reference_tables(contract)
    maximum, checked, cases = 0.0, 0, []
    per_source_cases = {}
    for key, triplet in grouped.items():
        if set(triplet) != {1, 2, 3}:
            raise RuntimeError("缺少完整三 Seed")
        first = triplet[1]
        if any((row["image_path"], row["true_label"], row["true_label_id"]) !=
               (first["image_path"], first["true_label"], first["true_label_id"]) for row in triplet.values()):
            raise RuntimeError("三 Seed 圖片或真值未對齊")
        vectors = {seed: scores(row) for seed, row in triplet.items()}
        single = combine_probabilities(SINGLE, {1: vectors[1]})
        combined = combine_probabilities(ENSEMBLE, vectors)
        expected = [float(ensemble[key]["ensemble_score_" + code]) for code in CLASS_CODES]
        maximum = max(maximum, max(abs(a - b) for a, b in zip(combined, expected)))
        if single != tuple(vectors[1]) or ranked_probabilities(single)[0]["code"] != first["predicted_label"]:
            raise RuntimeError("Seed1 adapter 與既有紀錄不同")
        if maximum > 1e-12 or ranked_probabilities(combined)[0]["code"] != ensemble[key]["ensemble_prediction"]:
            raise RuntimeError("等權 adapter 與 C 紀錄不同")
        if per_source_cases.get(key[0], 0) < 2:
            per_source_cases[key[0]] = per_source_cases.get(key[0], 0) + 1
            cases.append(dict(source=key[0], record_id=key[1], image_path=first["image_path"], split="validation",
                              seed_probabilities={str(seed): vector for seed, vector in vectors.items()},
                              ensemble_probabilities=expected))
        checked += 1
    return dict(status="passed", stage="stored_score_adapter_replay", created_at=datetime.now(timezone.utc).isoformat(),
                unique_validation_images=checked, seed_prediction_rows=checked * 3,
                single_top1_matches=checked, ensemble_top1_matches=checked,
                max_probability_absolute_error=maximum, tolerance=1e-12,
                model_loaded=False, torch_imported=False, gpu_used=False, test_read=False,
                limitation="僅證明既有分數的串接／等權公式一致；尚未證明新 API 從影像像素產生的輸出一致。",
                reference_sha256={key:value["sha256"] for key,value in contract.spec["references"].items()},
                gpu_validation_cases=cases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("驗證產物已存在，請沿用既有紀錄，不重跑／覆寫。")
    result = check_reference(ModelContract(args.project))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({key:value for key,value in result.items() if key != "gpu_validation_cases"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
