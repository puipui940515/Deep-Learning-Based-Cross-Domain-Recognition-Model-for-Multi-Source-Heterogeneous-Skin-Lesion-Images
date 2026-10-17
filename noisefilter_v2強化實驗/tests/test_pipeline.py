"""Pipeline safety checks: train gate, calibration identity, grouped probe."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pipeline
import _common
from source_probe_input import logistic_cv_ba


def test_g1_failure_stops_and_records_reason(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, 'OUT', tmp_path)
    monkeypatch.setattr(pipeline, 'PROJECT', tmp_path)
    (tmp_path / 'N0/seed17').mkdir(parents=True)
    result = {'smoke_test': False, 'summary': {'HAM10000_balanced_accuracy': .6}}
    (tmp_path / 'N0/seed17/result.json').write_text(json.dumps(result))
    baseline = {'candidates': {'governance_v1': {'summary': {'HAM10000_balanced_accuracy':
                {'values_by_seed': {'17': .8}, 'sample_standard_deviation': .04}}}}}
    (tmp_path / 'base.json').write_text(json.dumps(baseline))
    with pytest.raises(RuntimeError, match='G1 failed'):
        pipeline.g1({'baseline': {'seed_variance': 'base.json'}})
    assert pipeline.read(tmp_path / 'G1_pilot.json')['passed'] is False


def test_calibration_rejects_changed_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(_common, 'PROJECT', tmp_path)
    (tmp_path / 'manifest.csv').write_text('changed')
    (tmp_path / 'cal.json').write_text(json.dumps({'split_used': 'train', 'manifest_sha256': 'old'}))
    with pytest.raises(SystemExit, match='manifest'):
        _common.load_calibration({'manifest': 'manifest.csv', 'calibration_file': 'cal.json'})


def test_group_probe_reproducible():
    rng = np.random.default_rng(17)
    y = np.tile([0, 1], 12)
    X = rng.normal(size=(24, 3)).astype(np.float32)
    X[:, 0] += y * 3
    groups = np.array([f'g{i}' for i in range(24)])
    first = logistic_cv_ba(X, y, 3, 17, groups, epochs=12)
    second = logistic_cv_ba(X, y, 3, 17, groups, epochs=12)
    assert first == second
    assert 0 <= first['balanced_accuracy'] <= 1
