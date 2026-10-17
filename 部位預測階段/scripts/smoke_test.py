from __future__ import annotations

import json
import sys
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader
from torchvision.models import resnet18

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from site_stage.data import SiteDataset, build_transform
from site_stage.metrics import metrics_from_logits

config = json.loads((ROOT / "config/site_stage.json").read_text(encoding="utf-8"))
dataset_root = (ROOT / config["dataset_root"]).resolve()
dataset = SiteDataset(ROOT / config["manifest"], dataset_root, "train", build_transform(64, False), config["site_classes"])
images, targets, ids = next(iter(DataLoader(dataset, batch_size=4, shuffle=False)))
model = resnet18(weights=None)
model.fc = nn.Linear(model.fc.in_features, len(config["site_classes"]))
with torch.no_grad():
    logits = model(images)
metrics = metrics_from_logits(logits.numpy(), targets.numpy(), len(config["site_classes"]), config["site_classes"])
result = {
    "batch_shape": list(images.shape),
    "target_shape": list(targets.shape),
    "logit_shape": list(logits.shape),
    "sample_ids": list(ids),
    "train_class_counts": dataset.class_counts(),
    "metric_keys": list(metrics.keys()),
    "test_split_loaded": False,
    "passed": list(logits.shape) == [4, 5] and len(set(targets.tolist())) >= 1,
}
output = ROOT / "results/smoke_test.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(0 if result["passed"] else 2)
