from __future__ import annotations

import numpy as np


def metrics_from_logits(logits, targets, num_classes=7, ece_bins=15):
    logits = np.asarray(logits, dtype=np.float64); targets = np.asarray(targets, dtype=np.int64)
    shifted = logits - logits.max(axis=1, keepdims=True)
    probs = np.exp(shifted); probs /= probs.sum(axis=1, keepdims=True)
    predictions = probs.argmax(axis=1)
    matrix = np.zeros((num_classes, num_classes), dtype=np.int64)
    for target, prediction in zip(targets, predictions): matrix[target, prediction] += 1
    recalls = np.divide(np.diag(matrix), matrix.sum(1), out=np.zeros(num_classes), where=matrix.sum(1) != 0)
    precisions = np.divide(np.diag(matrix), matrix.sum(0), out=np.zeros(num_classes), where=matrix.sum(0) != 0)
    f1 = np.divide(2 * precisions * recalls, precisions + recalls, out=np.zeros(num_classes), where=(precisions + recalls) != 0)
    confidence = probs.max(1); correct = predictions == targets; ece = 0.0
    edges = np.linspace(0, 1, ece_bins + 1)
    for lower, upper in zip(edges[:-1], edges[1:]):
        mask = (confidence > lower) & (confidence <= upper)
        if mask.any(): ece += mask.mean() * abs(correct[mask].mean() - confidence[mask].mean())
    return {"balanced_accuracy": float(recalls.mean()), "macro_f1": float(f1.mean()),
            "accuracy": float(correct.mean()), "ece": float(ece), "recall_per_class": recalls.tolist(),
            "confusion_matrix": matrix.tolist()}

