from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from stage1.data import HAM10000ManifestDataset, build_transform
from stage1.engine import run_epoch
from stage1.models import build_model

parser = argparse.ArgumentParser(description="v1/v2 平移 8 像素壓力測試；預設只用 validation。")
parser.add_argument("--version", choices=["v1", "v2"], required=True)
parser.add_argument("--seed", type=int, required=True)
args = parser.parse_args()
config = json.loads((ROOT / "config/stage1.json").read_text(encoding="utf-8"))
spec = config["versions"][args.version]
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
dataset_root = (ROOT / config["dataset_root"]).resolve()
dataset = HAM10000ManifestDataset(ROOT / config["split_manifest"], dataset_root, "val", build_transform(64, False, False, 8))
loader = DataLoader(dataset, batch_size=config["batch_size"], shuffle=False, num_workers=config["num_workers"])
model = build_model(spec["model"], 64, 7).to(device)
state = torch.load(ROOT / f"checkpoints/{args.version}_seed{args.seed}.pt", map_location=device, weights_only=False)
model.load_state_dict(state["model"])
result = run_epoch(model, loader, nn.CrossEntropyLoss(), device)
out = ROOT / f"results/{args.version}_seed{args.seed}_translate8_val.json"
out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))

