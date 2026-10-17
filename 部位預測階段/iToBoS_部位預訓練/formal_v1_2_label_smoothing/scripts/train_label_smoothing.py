from __future__ import annotations

import json
import sys
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
BASE_ROOT = EXPERIMENT_ROOT.parent
sys.path.insert(0, str(BASE_ROOT / "scripts"))
sys.path.insert(0, str(BASE_ROOT / "src"))
sys.path.insert(0, str(EXPERIMENT_ROOT / "src"))

import train_formal_convnext as base_training
from smoothed_weighted_loss import build_loss


config_path = EXPERIMENT_ROOT / "config/formal_v1_2_label_smoothing.json"
config = json.loads(config_path.read_text(encoding="utf-8"))

# 沿用已審核的 formal v1，只替換 loss factory 與輸出根目錄。
base_training.ROOT = EXPERIMENT_ROOT
base_training.weighted_cross_entropy = build_loss(config)


if __name__ == "__main__":
    base_training.main()

