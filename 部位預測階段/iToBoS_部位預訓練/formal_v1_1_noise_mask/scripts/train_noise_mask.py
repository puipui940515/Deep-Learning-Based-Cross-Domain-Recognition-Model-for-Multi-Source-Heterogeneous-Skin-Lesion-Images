from __future__ import annotations

import sys
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
BASE_ROOT = EXPERIMENT_ROOT.parent
sys.path.insert(0, str(BASE_ROOT / "scripts"))
sys.path.insert(0, str(BASE_ROOT / "src"))
sys.path.insert(0, str(EXPERIMENT_ROOT / "src"))

import train_formal_convnext as base_training
from noise_mask_transform import build_transform


# 沿用已審核的 v1 訓練流程，只替換 train transform 與輸出根目錄。
base_training.ROOT = EXPERIMENT_ROOT
base_training.build_transform = build_transform


if __name__ == "__main__":
    base_training.main()

