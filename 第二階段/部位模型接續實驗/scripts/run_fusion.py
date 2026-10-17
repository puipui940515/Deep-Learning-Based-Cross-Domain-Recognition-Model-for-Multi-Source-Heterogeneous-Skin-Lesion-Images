from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

ROOT = Path(__file__).resolve().parents[1]
STAGE2_ROOT = ROOT.parent
sys.path.insert(0, str(STAGE2_ROOT / "src"))
from stage2.metrics import metrics_from_logits


def seed_everything(seed):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)


def evaluate(disease_logits, features, targets, head):
    with torch.no_grad():
        fused = disease_logits + head(features)
    return metrics_from_logits(fused.numpy(), targets.numpy()), fused


def train_branch(name, disease_logits, site_features, targets, train_mask, val_mask, seed, config):
    seed_everything(seed + {"bias_control": 0, "site_fusion": 10_000, "shuffled_site": 20_000}[name])
    if name == "bias_control":
        features = torch.zeros_like(site_features)
    elif name == "shuffled_site":
        features = site_features.clone()
        train_indices = torch.where(train_mask)[0]
        val_indices = torch.where(val_mask)[0]
        features[train_indices] = features[train_indices[torch.randperm(len(train_indices))]]
        features[val_indices] = features[val_indices[torch.randperm(len(val_indices))]]
    else:
        features = site_features

    head = nn.Linear(5, 7)
    nn.init.zeros_(head.weight); nn.init.zeros_(head.bias)
    optimizer = torch.optim.AdamW(head.parameters(), lr=config["learning_rate"], weight_decay=config["weight_decay"])
    dataset = TensorDataset(disease_logits[train_mask], features[train_mask], targets[train_mask])
    generator = torch.Generator().manual_seed(seed)
    loader = DataLoader(dataset, batch_size=config["batch_size"], shuffle=True, generator=generator)
    criterion = nn.CrossEntropyLoss()
    best_score, best_epoch, best_state, best_metrics, patience = -1.0, 0, None, None, 0
    history = []
    for epoch in range(config["max_epochs"]):
        head.train()
        for base_logits, batch_features, batch_targets in loader:
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(base_logits + head(batch_features), batch_targets)
            loss.backward(); optimizer.step()
        head.eval()
        metrics, _ = evaluate(disease_logits[val_mask], features[val_mask], targets[val_mask], head)
        history.append({"epoch": epoch + 1, "validation": metrics})
        score = metrics["balanced_accuracy"]
        if score > best_score:
            best_score, best_epoch, best_metrics, patience = score, epoch + 1, metrics, 0
            best_state = {key: value.detach().clone() for key, value in head.state_dict().items()}
        else:
            patience += 1
        if patience >= config["early_stopping_patience"]: break
    head.load_state_dict(best_state)
    train_metrics, _ = evaluate(disease_logits[train_mask], features[train_mask], targets[train_mask], head)
    return {
        "best_epoch": best_epoch,
        "train": train_metrics,
        "validation": best_metrics,
        "history": history,
        "learned_weight": head.weight.detach().tolist(),
        "learned_bias": head.bias.detach().tolist(),
    }


parser = argparse.ArgumentParser()
parser.add_argument("--seed", type=int, required=True)
args = parser.parse_args()
if args.seed not in (17, 42, 2026): raise SystemExit("seed 必須為 17、42 或 2026")
config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))["fusion"]
site = torch.load(ROOT / "cache/site_outputs.pt", map_location="cpu", weights_only=False)
disease = torch.load(ROOT / f"cache/disease_v7_seed{args.seed}.pt", map_location="cpu", weights_only=False)
if site["ids"] != disease["ids"]: raise SystemExit("cache ID 未對齊")
site_features = torch.softmax(site["logits"], dim=1)
disease_logits = disease["logits"]
targets = disease["disease_labels"]
train_mask = torch.tensor([split == "train" for split in disease["splits"]])
val_mask = torch.tensor([split == "val" for split in disease["splits"]])
baseline = metrics_from_logits(disease_logits[val_mask].numpy(), targets[val_mask].numpy())
known_site = site["site_labels"][val_mask] < 5
site_prediction = site_features[val_mask].argmax(1)
site_accuracy_known = float((site_prediction[known_site] == site["site_labels"][val_mask][known_site]).float().mean())

branches = {}
for name in ("bias_control", "site_fusion", "shuffled_site"):
    branches[name] = train_branch(name, disease_logits, site_features, targets, train_mask, val_mask, args.seed, config)
    print(f"seed={args.seed} {name} val_BA={branches[name]['validation']['balanced_accuracy']:.4f}", flush=True)

site_ba = branches["site_fusion"]["validation"]["balanced_accuracy"]
result = {
    "experiment": "stage2_v7_plus_frozen_multisource_site_model",
    "disease_seed": args.seed,
    "baseline": baseline,
    "site_model_known_site_accuracy_on_ham_validation": site_accuracy_known,
    "branches": branches,
    "site_fusion_minus_baseline": {
        key: branches["site_fusion"]["validation"][key] - baseline[key]
        for key in ("balanced_accuracy", "macro_f1", "accuracy", "ece")
    },
    "site_fusion_minus_bias_control_ba": site_ba - branches["bias_control"]["validation"]["balanced_accuracy"],
    "site_fusion_minus_shuffled_site_ba": site_ba - branches["shuffled_site"]["validation"]["balanced_accuracy"],
    "test_used": False,
    "interpretation_limit": "frozen-output fusion pilot; site model selection also observed HAM validation site labels",
}
output = ROOT / f"results/fusion_seed{args.seed}.json"
output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"output": str(output), "delta": result["site_fusion_minus_baseline"]}, ensure_ascii=False, indent=2))
