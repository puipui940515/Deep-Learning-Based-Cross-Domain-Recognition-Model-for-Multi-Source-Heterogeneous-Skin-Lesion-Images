from pathlib import Path
import sys
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from metrics import evaluate, source_summary


def test_missing_classes_do_not_reduce_ba():
    p = np.eye(8)[[1, 1, 6]]
    result = evaluate(p, np.array([1, 1, 6]), range(8))
    assert result['balanced_accuracy'] == result['macro_f1'] == 1
    assert result['supported_labels'] == [1, 6]
    assert result['recall_by_class']['SCC'] is None
    assert result['ece'] == 0
    assert result['malignant_specificity'] is None


def test_wrong_predictions_and_malignant_boundary():
    result = evaluate(np.eye(8)[[4, 7, 1, 4]], np.array([6, 1, 4, 4]), [1, 4, 6])
    assert result['accuracy'] == .25
    assert result['balanced_accuracy'] == pytest.approx(1 / 6)
    assert result['malignant_sensitivity'] == .5
    assert result['malignant_specificity'] == .5
    assert result['ece'] == .75


def test_ece_boundary_and_temperature_argmax():
    p = np.array([[.8, .2, 0, 0, 0, 0, 0, 0]])
    assert evaluate(p, np.array([0]), [0])['ece'] == pytest.approx(.2)
    logits = np.array([[0., 1., 2., 3., 4., 5., 6., 7.]])
    for temperature in [.1, 1, 10]:
        q = np.exp((logits - logits.max(1, keepdims=True)) / temperature)
        q /= q.sum(1, keepdims=True)
        assert evaluate(q, np.array([7]), [7])['accuracy'] == 1


def test_missing_source_must_not_be_averaged_away():
    with pytest.raises(ValueError, match='missing'):
        source_summary({'HAM': {'balanced_accuracy': .9}}, ['HAM', 'ISIC'])


def test_undeclared_observed_label_rejected():
    with pytest.raises(ValueError, match='Supported'):
        evaluate(np.eye(8)[[7]], np.array([7]), [0, 1])
