"""相容入口：修正第三階段 metrics_by_site 的關鍵字名稱後執行 A/B。"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "第三階段" / "src"))

import stage3.metrics as site_metrics

_metrics_by_site = site_metrics.metrics_by_site


def _compatible_metrics_by_site(
    logits,
    targets,
    site_labels,
    *,
    site_groups=None,
    site_names=None,
    num_classes=7,
    min_support=20,
):
    names = site_names if site_names is not None else site_groups
    return _metrics_by_site(
        logits,
        targets,
        site_labels,
        names,
        num_classes=num_classes,
        min_support=min_support,
    )


site_metrics.metrics_by_site = _compatible_metrics_by_site
runpy.run_path(str(Path(__file__).with_name("run_pilot.py")), run_name="__main__")
