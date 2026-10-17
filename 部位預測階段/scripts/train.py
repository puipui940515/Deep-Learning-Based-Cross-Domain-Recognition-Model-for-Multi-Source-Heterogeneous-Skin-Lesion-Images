from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader
from torchvision.models import ResNet18_Weights, resnet18

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from site_stage.data import SiteDataset, build_transform
from site_stage.engine import run_epoch, seed_everything


def class_weights(counts, maximum: float, normalize_mean: bool):
    reference = max(counts)
    values = [min(maximum, math.sqrt(reference / count)) for count in counts]
    if normalize_mean:
        mean = sum(values) / len(values)
        values = [value / mean for value in values]
    return values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    config = json.loads((ROOT / "config/site_stage.json").read_text(encoding="utf-8"))
    if args.seed not in config["seeds"]:
        raise SystemExit(f"seed 必須為 {config['seeds']}")
    audit_path = ROOT / "results/data_audit.json"
    if not audit_path.exists() or not json.loads(audit_path.read_text(encoding="utf-8")).get("passed"):
        raise SystemExit("資料稽核尚未通過")

    seed_everything(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    manifest = ROOT / config["manifest"]
    dataset_root = (ROOT / config["dataset_root"]).resolve()
    train_set = SiteDataset(manifest, dataset_root, "train", build_transform(config["image_size"], True), config["site_classes"])
    val_set = SiteDataset(manifest, dataset_root, "val", build_transform(config["image_size"], False), config["site_classes"])
    loader_args = {
        "batch_size": config["batch_size"],
        "num_workers": config["num_workers"],
        "pin_memory": device.type == "cuda",
    }
    generator = torch.Generator().manual_seed(args.seed)
    train_loader = DataLoader(train_set, shuffle=True, generator=generator, **loader_args)
    val_loader = DataLoader(val_set, shuffle=False, **loader_args)

    weights = ResNet18_Weights.DEFAULT if config["pretrained"] else None
    model = resnet18(weights=weights)
    model.fc = nn.Linear(model.fc.in_features, len(config["site_classes"]))
    model = model.to(device)
    raw_counts = train_set.class_counts()
    loss_weights = class_weights(raw_counts, config["class_weighting"]["max_weight"], config["class_weighting"]["normalize_mean"])
    criterion = nn.CrossEntropyLoss(weight=torch.tensor(loss_weights, device=device)).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=config["learning_rate"], weight_decay=config["weight_decay"])
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")

    checkpoint = ROOT / f"checkpoints/site_resnet18_seed{args.seed}.pt"
    best_score, best_record, history, patience, start_epoch = -1.0, None, [], 0, 0
    if args.resume and checkpoint.exists():
        state = torch.load(checkpoint, map_location=device, weights_only=False)
        model.load_state_dict(state["model"])
        optimizer.load_state_dict(state["optimizer"])
        scaler.load_state_dict(state["scaler"])
        best_score, best_record = state["best_score"], state["best_record"]
        history, start_epoch = state["history"], state["epoch"] + 1
        print(f"resume seed={args.seed} from epoch={start_epoch + 1}", flush=True)

    for epoch in range(start_epoch, args.epochs or config["epochs"]):
        train_metrics = run_epoch(model, train_loader, criterion, device, config["site_classes"], optimizer, scaler)
        val_metrics = run_epoch(model, val_loader, criterion, device, config["site_classes"])
        record = {"epoch": epoch + 1, "train": train_metrics, "validation": val_metrics}
        history.append(record)
        score = val_metrics["balanced_accuracy"]
        if score > best_score:
            best_score, best_record, patience = score, record, 0
            checkpoint.parent.mkdir(parents=True, exist_ok=True)
            torch.save({
                "epoch": epoch,
                "model": model.state_dict(),
                "optimizer": optimizer.state_dict(),
                "scaler": scaler.state_dict(),
                "best_score": best_score,
                "best_record": best_record,
                "history": history,
                "seed": args.seed,
                "site_classes": config["site_classes"],
            }, checkpoint)
        else:
            patience += 1
        print(
            f"site seed={args.seed} epoch={epoch + 1} "
            f"train_BA={train_metrics['balanced_accuracy']:.4f} "
            f"val_BA={score:.4f} val_acc={val_metrics['accuracy']:.4f}",
            flush=True,
        )
        if patience >= config["early_stopping_patience"]:
            break

    result = {
        "task": "HAM10000 anatomical site classification",
        "seed": args.seed,
        "model": config["model"],
        "pretrained": config["pretrained"],
        "site_classes": config["site_classes"],
        "excluded": config["excluded_site_classes"],
        "train_class_counts": dict(zip(config["site_classes"], raw_counts)),
        "loss_weights": dict(zip(config["site_classes"], loss_weights)),
        "device": str(device),
        "best": best_record,
        "history": history,
        "test_used": False,
    }
    output = ROOT / f"results/site_resnet18_seed{args.seed}.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved {output}", flush=True)


if __name__ == "__main__":
    main()
