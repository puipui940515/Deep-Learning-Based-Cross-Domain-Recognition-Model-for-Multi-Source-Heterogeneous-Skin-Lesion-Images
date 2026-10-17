from __future__ import annotations

from collections import Counter, defaultdict


SITE_GROUPS = (
    "head_neck",
    "trunk",
    "upper_extremity",
    "lower_extremity",
    "anogenital",
    "unknown",
)
SITE_TO_LABEL = {name: index for index, name in enumerate(SITE_GROUPS)}
RAW_SITE_TO_GROUP = {
    "Head and neck": "head_neck",
    "Trunk": "trunk",
    "Upper extremity": "upper_extremity",
    "Lower extremity": "lower_extremity",
    "Anogenital region": "anogenital",
    "": "unknown",
}


def normalize_ham_site(raw_site: str | None) -> str:
    value = (raw_site or "").strip()
    if value not in RAW_SITE_TO_GROUP:
        raise ValueError(f"未支援的 HAM10000 anatom_site_1：{value!r}")
    return RAW_SITE_TO_GROUP[value]


def site_label(group: str) -> int:
    try:
        return SITE_TO_LABEL[group]
    except KeyError as error:
        raise ValueError(f"未知的 site_group：{group!r}") from error


def build_within_diagnosis_site_weights(
    rows,
    *,
    power: float = 0.5,
    max_weight: float = 4.0,
    min_group_count: int = 10,
):
    """建立疾病內部的部位平衡權重，不改變各疾病的總抽樣質量。"""
    rows = list(rows)
    if not 0.0 <= power <= 1.0:
        raise ValueError("power 必須介於 0 與 1")
    if max_weight < 1.0:
        raise ValueError("max_weight 不得小於 1")
    if min_group_count < 1:
        raise ValueError("min_group_count 必須至少為 1")

    joint_counts = Counter((int(row["label"]), row["site_group"]) for row in rows)
    reference_counts = defaultdict(lambda: 1)
    for (diagnosis, group), count in joint_counts.items():
        if group != "unknown":
            reference_counts[diagnosis] = max(reference_counts[diagnosis], count)

    weights = []
    for row in rows:
        diagnosis = int(row["label"])
        group = row["site_group"]
        count = joint_counts[(diagnosis, group)]
        if group == "unknown":
            factor = 1.0
        else:
            effective_count = max(count, min_group_count)
            factor = (reference_counts[diagnosis] / effective_count) ** power
        weights.append(min(max_weight, factor))

    by_diagnosis = defaultdict(list)
    for index, row in enumerate(rows):
        by_diagnosis[int(row["label"])].append(index)
    diagnosis_weight_means = {}
    for diagnosis, indices in by_diagnosis.items():
        mean = sum(weights[index] for index in indices) / len(indices)
        diagnosis_weight_means[str(diagnosis)] = mean
        if mean > 0:
            for index in indices:
                weights[index] /= mean

    audit = {
        "definition": "疾病總抽樣質量不變；只緩和疾病內部的部位不平衡",
        "power": power,
        "max_weight": max_weight,
        "min_group_count": min_group_count,
        "joint_counts": {
            f"{diagnosis}:{group}": count
            for (diagnosis, group), count in sorted(joint_counts.items())
        },
        "pre_normalization_diagnosis_means": diagnosis_weight_means,
        "weight_min": min(weights) if weights else None,
        "weight_max": max(weights) if weights else None,
    }
    return weights, audit
