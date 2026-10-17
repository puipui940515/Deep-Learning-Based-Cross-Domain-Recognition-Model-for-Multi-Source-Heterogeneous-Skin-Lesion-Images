"""CP-005 eight-class metrics, all machine-readable values are fractions."""
import numpy as np

CLASS_NAMES = ('AKIEC', 'BCC', 'BKL', 'DF', 'NV', 'VASC', 'MEL', 'SCC')
MALIGNANT = (1, 6, 7)


def evaluate(probabilities, targets, supported_labels):
    p = np.asarray(probabilities, dtype=np.float64)
    y = np.asarray(targets)
    if p.ndim != 2 or p.shape[1] != 8 or y.shape != (len(p),) or len(y) == 0:
        raise ValueError('Expected nonempty N x 8 probabilities and N targets')
    if not np.issubdtype(y.dtype, np.integer) or np.any((y < 0) | (y >= 8)):
        raise ValueError('Targets must be integer IDs 0..7')
    if not np.isfinite(p).all() or (p < 0).any() or not np.allclose(p.sum(1), 1, atol=1e-6):
        raise ValueError('Expected finite normalized probabilities')
    supported = sorted(set(supported_labels))
    if not set(np.unique(y)).issubset(supported) or any(k not in range(8) for k in supported):
        raise ValueError('Supported labels must include every observed target')
    pred = p.argmax(1)
    cm = np.zeros((8, 8), dtype=np.int64)
    np.add.at(cm, (y, pred), 1)
    active = [k for k in supported if cm[k].sum() > 0]
    recalls = {CLASS_NAMES[k]: float(cm[k, k] / cm[k].sum()) if cm[k].sum() else None for k in range(8)}
    f1 = [float(2 * cm[k, k] / (cm[k].sum() + cm[:, k].sum())) for k in active]
    confidence = p.max(1)
    correct = pred == y
    ece = 0.0
    for lower, upper in zip(np.linspace(0, 1, 16)[:-1], np.linspace(0, 1, 16)[1:]):
        mask = (confidence > lower) & (confidence <= upper)
        if mask.any():
            ece += mask.mean() * abs(correct[mask].mean() - confidence[mask].mean())
    true_mal = np.isin(y, MALIGNANT)
    pred_mal = np.isin(pred, MALIGNANT)
    return {
        'samples': len(y), 'supported_labels': active,
        'accuracy': float(correct.mean()),
        'balanced_accuracy': float(np.mean([recalls[CLASS_NAMES[k]] for k in active])),
        'macro_f1': float(np.mean(f1)), 'ece': float(ece), 'ece_bins': 15,
        'recall_by_class': recalls, 'confusion_matrix': cm.tolist(),
        'malignant_sensitivity': float(pred_mal[true_mal].mean()) if true_mal.any() else None,
        'malignant_specificity': float((~pred_mal[~true_mal]).mean()) if (~true_mal).any() else None,
    }


def source_summary(by_source, required_sources):
    if set(by_source) != set(required_sources):
        raise ValueError('Cannot compute source summary with missing or unexpected sources')
    values = [by_source[s]['balanced_accuracy'] for s in required_sources]
    return {'worst_source_balanced_accuracy': float(min(values)),
            'mean_source_balanced_accuracy': float(np.mean(values))}
