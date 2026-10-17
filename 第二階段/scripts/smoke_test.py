from __future__ import annotations

import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from stage2.losses import LogitAdjustedCrossEntropy
from stage2.models import build_model

config = json.loads((ROOT / "config/stage2.json").read_text(encoding="utf-8-sig"))
for version, spec in config["versions"].items():
    # smoke test 不下載預訓練權重；只驗證相同架構、尺寸與 loss。
    model = build_model(spec["model"], False, 7)
    batch = 1 if spec["image_size"] == 384 else 2
    x = torch.zeros(batch, 3, spec["image_size"], spec["image_size"])
    y = torch.zeros(batch, dtype=torch.long)
    logits = model(x)
    criterion = LogitAdjustedCrossEntropy([229,360,769,80,4693,98,779]) if version == "v9" else torch.nn.CrossEntropyLoss()
    criterion(logits, y).backward()
    print(version, tuple(logits.shape), "OK")


