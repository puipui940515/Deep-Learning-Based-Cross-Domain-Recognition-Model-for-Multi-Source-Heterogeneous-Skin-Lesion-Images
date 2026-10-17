import numpy as np


def metrics_from_logits(logits, targets, num_classes=7, ece_bins=15, present_classes_only=False):
    logits = np.asarray(logits, dtype=np.float64)
    targets = np.asarray(targets, dtype=np.int64)
    probs = np.exp(logits - logits.max(1, keepdims=True))
    probs /= probs.sum(1, keepdims=True)
    predictions = probs.argmax(1)
    matrix = np.zeros((num_classes, num_classes), dtype=np.int64)
    for target, prediction in zip(targets, predictions):
        matrix[target, prediction] += 1
    support = matrix.sum(1)
    recalls = np.divide(np.diag(matrix), support, out=np.zeros(num_classes), where=support != 0)
    precisions = np.divide(
        np.diag(matrix), matrix.sum(0), out=np.zeros(num_classes), where=matrix.sum(0) != 0
    )
    f1 = np.divide(
        2 * precisions * recalls,
        precisions + recalls,
        out=np.zeros(num_classes),
        where=(precisions + recalls) != 0,
    )
    confidence = probs.max(1)
    correct = predictions == targets
    ece = 0.0
    edges = np.linspace(0, 1, ece_bins + 1)
    for lower, upper in zip(edges[:-1], edges[1:]):
        mask = (confidence > lower) & (confidence <= upper)
        if mask.any():
            ece += mask.mean() * abs(correct[mask].mean() - confidence[mask].mean())
    supported = support != 0
    average_mask = supported if present_classes_only else np.ones(num_classes, dtype=bool)
    return {
        "balanced_accuracy": float(recalls[average_mask].mean()),
        "macro_f1": float(f1[average_mask].mean()),
        "accuracy": float(correct.mean()),
        "ece": float(ece),
        "recall_per_class": recalls.tolist(),
        "confusion_matrix": matrix.tolist(),
        "supported_classes": np.flatnonzero(supported).tolist(),
    }


def metrics_by_site(logits, targets, site_labels, site_names, num_classes=7, min_support=20):
    logits = np.asarray(logits)
    targets = np.asarray(targets, dtype=np.int64)
    site_labels = np.asarray(site_labels, dtype=np.int64)
    if not (len(logits) == len(targets) == len(site_labels)):
        raise ValueError("logits、targets 與 site_labels 長度必須一致")
    sites = {}
    eligible_known_scores = []
    for site_id, site_name in enumerate(site_names):
        mask = site_labels == site_id
        current_support = int(mask.sum())
        disease_support = np.bincount(targets[mask], minlength=num_classes).tolist()
        entry = {"site_label": site_id, "support": current_support, "disease_support": disease_support}
        if current_support >= min_support:
            entry.update(
                metrics_from_logits(
                    logits[mask], targets[mask], num_classes=num_classes, present_classes_only=True
                )
            )
            if site_name != "unknown":
                eligible_known_scores.append(entry["balanced_accuracy"])
        else:
            entry["excluded_from_summary"] = f"support<{min_support}"
        sites[site_name] = entry
    return {
        "definition": "各部位只平均該部位實際出現的疾病類別",
        "min_support": min_support,
        "sites": sites,
        "worst_known_site_balanced_accuracy": min(eligible_known_scores) if eligible_known_scores else None,
    }
