from __future__ import annotations

import numpy as np


def metrics_from_logits(logits, targets, num_classes: int, class_names):
    logits = np.asarray(logits, dtype=np.float64)
    targets = np.asarray(targets, dtype=np.int64)
    shifted = logits - logits.max(axis=1, keepdims=True)
    probabilities = np.exp(shifted)
    probabilities /= probabilities.sum(axis=1, keepdims=True)
    predictions = probabilities.argmax(axis=1)
    matrix = np.zeros((num_classes, num_classes), dtype=np.int64)
    for target, prediction in zip(targets, predictions):
        matrix[target, prediction] += 1
    support = matrix.sum(axis=1)
    recall = np.divide(np.diag(matrix), support, out=np.zeros(num_classes), where=support != 0)
    predicted = matrix.sum(axis=0)
    precision = np.divide(np.diag(matrix), predicted, out=np.zeros(num_classes), where=predicted != 0)
    f1 = np.divide(2 * precision * recall, precision + recall, out=np.zeros(num_classes), where=(precision + recall) != 0)
    confidence = probabilities.max(axis=1)
    correct = predictions == targets
    ece = 0.0
    edges = np.linspace(0.0, 1.0, 16)
    for lower, upper in zip(edges[:-1], edges[1:]):
        mask = (confidence > lower) & (confidence <= upper)
        if mask.any():
            ece += mask.mean() * abs(correct[mask].mean() - confidence[mask].mean())
    return {
        "balanced_accuracy": float(recall.mean()),
        "macro_f1": float(f1.mean()),
        "accuracy": float(correct.mean()),
        "ece": float(ece),
        "support_per_class": dict(zip(class_names, support.tolist())),
        "recall_per_class": dict(zip(class_names, recall.tolist())),
        "precision_per_class": dict(zip(class_names, precision.tolist())),
        "f1_per_class": dict(zip(class_names, f1.tolist())),
        "confusion_matrix": matrix.tolist(),
    }
