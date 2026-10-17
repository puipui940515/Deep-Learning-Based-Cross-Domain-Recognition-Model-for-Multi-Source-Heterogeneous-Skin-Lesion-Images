from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader
from torchvision.models import ResNet18_Weights, resnet18

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))
from site_stage.data import SiteDataset, build_transform
from site_stage.engine import run_epoch, seed_everything


def class_weights(counts, maximum=5.0):
    reference = max(counts)
    values = [min(maximum, math.sqrt(reference / count)) for count in counts]
    mean = sum(values) / len(values)
    return [value / mean for value in values]


def source_counts(manifest: Path, split: str):
    with manifest.open("r", encoding="utf-8-sig", newline="") as handle:
        return dict(Counter(row["source"] for row in csv.DictReader(handle) if row["split"] == split))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=["ham", "bcn", "ham_bcn"], required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--smoke", action="store_true", help="只做單一 batch forward，不訓練或寫 checkpoint")
    args = parser.parse_args()

    base = json.loads((ROOT / "config/site_stage.json").read_text(encoding="utf-8"))
    profiles = json.loads((ROOT / "config/dataset_profiles.json").read_text(encoding="utf-8"))
    audit_path = ROOT / "results/dataset_profiles_audit.json"
    if not audit_path.exists() or not json.loads(audit_path.read_text(encoding="utf-8")).get("passed"):
        raise SystemExit("dataset profile 稽核尚未通過")
    if args.seed not in base["seeds"]:
        raise SystemExit(f"seed 必須為 {base['seeds']}")

    manifest = ROOT / profiles["profiles"][args.profile]["manifest"]
    site_classes = profiles["target_schema"]
    seed_everything(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_set = SiteDataset(manifest, PROJECT_ROOT, "train", build_transform(base["image_size"], True), site_classes)
    val_set = SiteDataset(manifest, PROJECT_ROOT, "val", build_transform(base["image_size"], False), site_classes)
    loader_args = {
        "batch_size": base["batch_size"],
        "num_workers": base["num_workers"],
        "pin_memory": device.type == "cuda",
    }
    generator = torch.Generator().manual_seed(args.seed)
    train_loader = DataLoader(train_set, shuffle=True, generator=generator, **loader_args)
    val_loader = DataLoader(val_set, shuffle=False, **loader_args)

    model = resnet18(weights=ResNet18_Weights.DEFAULT if base["pretrained"] else None)
    model.fc = nn.Linear(model.fc.in_features, len(site_classes))
    model = model.to(device)
    if args.smoke:
        images, targets, ids = next(iter(train_loader))
        with torch.no_grad():
            logits = model(images.to(device))
        print(json.dumps({
            "profile": args.profile,
            "train_rows": len(train_set),
            "val_rows": len(val_set),
            "train_source_counts": source_counts(manifest, "train"),
            "batch_shape": list(images.shape),
            "logit_shape": list(logits.shape),
            "sample_ids": list(ids[:3]),
            "test_loaded": False,
            "passed": list(logits.shape) == [len(images), len(site_classes)],
        }, ensure_ascii=False, indent=2))
        return

    counts = train_set.class_counts()
    loss_weights = class_weights(counts, base["class_weighting"]["max_weight"])
    criterion = nn.CrossEntropyLoss(weight=torch.tensor(loss_weights, device=device)).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=base["learning_rate"], weight_decay=base["weight_decay"])
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    checkpoint = ROOT / f"checkpoints/profiles/{args.profile}_resnet18_seed{args.seed}.pt"
    best_score, best_record, history, patience, start_epoch = -1.0, None, [], 0, 0
    if args.resume and checkpoint.exists():
        state = torch.load(checkpoint, map_location=device, weights_only=False)
        model.load_state_dict(state["model"])
        optimizer.load_state_dict(state["optimizer"])
        scaler.load_state_dict(state["scaler"])
        best_score, best_record = state["best_score"], state["best_record"]
        history, start_epoch = state["history"], state["epoch"] + 1

    for epoch in range(start_epoch, args.epochs or base["epochs"]):
        train_metrics = run_epoch(model, train_loader, criterion, device, site_classes, optimizer, scaler)
        val_metrics = run_epoch(model, val_loader, criterion, device, site_classes)
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
                "profile": args.profile,
                "seed": args.seed,
            }, checkpoint)
        else:
            patience += 1
        print(
            f"profile={args.profile} seed={args.seed} epoch={epoch + 1} "
            f"train_BA={train_metrics['balanced_accuracy']:.4f} "
            f"val_BA={score:.4f} val_acc={val_metrics['accuracy']:.4f}",
            flush=True,
        )
        if patience >= base["early_stopping_patience"]:
            break

    result = {
        "task": "conditional-profile anatomical site classification",
        "profile": args.profile,
        "profile_status": profiles["profiles"][args.profile]["status"],
        "image_domain": profiles["profiles"][args.profile]["image_domain"],
        "seed": args.seed,
        "site_classes": site_classes,
        "train_rows": len(train_set),
        "validation_rows": len(val_set),
        "train_source_counts": source_counts(manifest, "train"),
        "validation_source_counts": source_counts(manifest, "val"),
        "train_class_counts": dict(zip(site_classes, counts)),
        "loss_weights": dict(zip(site_classes, loss_weights)),
        "best": best_record,
        "history": history,
        "test_used": False,
    }
    output = ROOT / f"results/profiles/{args.profile}_resnet18_seed{args.seed}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved {output}", flush=True)


if __name__ == "__main__":
    main()
