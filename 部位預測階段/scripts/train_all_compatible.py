from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
from torchvision.models import ResNet18_Weights, resnet18

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))
from site_stage.data import build_transform
from site_stage.metrics import metrics_from_logits

SITE_CLASSES = ["head_neck", "trunk", "upper_extremity", "lower_extremity", "anogenital"]


class MixedDataset(Dataset):
    def __init__(self, manifest, split, transform):
        self.transform = transform
        with Path(manifest).open("r", encoding="utf-8-sig", newline="") as handle:
            self.rows = [row for row in csv.DictReader(handle) if row["split"] == split]
        if not self.rows:
            raise ValueError(f"沒有 split={split}")

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        with Image.open(PROJECT_ROOT / row["image_path"]) as image:
            image = image.convert("RGB")
        return self.transform(image), int(row["site_label"]), row["isic_id"], row["source"]


def seed_everything(seed):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True; torch.backends.cudnn.benchmark = False


def calculate_metrics(logits, targets, sources):
    overall = metrics_from_logits(logits, targets, len(SITE_CLASSES), SITE_CLASSES)
    by_source = {}
    for source in sorted(set(sources)):
        mask = np.asarray(sources) == source
        current = metrics_from_logits(logits[mask], targets[mask], len(SITE_CLASSES), SITE_CLASSES)
        support = np.asarray(list(current["support_per_class"].values()))
        recalls = np.asarray(list(current["recall_per_class"].values()))
        current["present_class_balanced_accuracy"] = float(recalls[support > 0].mean())
        current["support"] = int(mask.sum())
        by_source[source] = current
    overall["by_source"] = by_source
    overall["macro_source_present_class_balanced_accuracy"] = float(np.mean([
        metrics["present_class_balanced_accuracy"] for metrics in by_source.values()
    ]))
    return overall


def run_epoch(model, loader, criterion, device, optimizer=None, scaler=None):
    training = optimizer is not None
    model.train(training)
    total_loss, all_logits, all_targets, all_sources = 0.0, [], [], []
    if training: optimizer.zero_grad(set_to_none=True)
    for images, targets, _, sources in loader:
        images, targets = images.to(device), targets.to(device)
        with torch.set_grad_enabled(training):
            with torch.amp.autocast(device_type=device.type, enabled=device.type == "cuda"):
                logits = model(images); loss = criterion(logits, targets)
            if training:
                scaler.scale(loss).backward(); scaler.step(optimizer); scaler.update(); optimizer.zero_grad(set_to_none=True)
        total_loss += loss.item() * targets.size(0)
        all_logits.append(logits.detach().float().cpu().numpy()); all_targets.append(targets.cpu().numpy()); all_sources.extend(sources)
    result = calculate_metrics(np.concatenate(all_logits), np.concatenate(all_targets), all_sources)
    result["loss"] = total_loss / len(loader.dataset)
    return result


def normalized_sqrt_inverse(counts, cap):
    reference = max(counts.values())
    raw = {key: min(cap, math.sqrt(reference / value)) for key, value in counts.items()}
    return raw


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--epochs", type=int, default=3)
    args = parser.parse_args()
    audit = json.loads((ROOT / "results/all_compatible_audit.json").read_text(encoding="utf-8"))
    if not audit.get("passed"):
        raise SystemExit("all_compatible 稽核未通過")
    seed_everything(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    manifest = ROOT / "data/profiles/all_compatible.csv"
    train_set = MixedDataset(manifest, "train", build_transform(224, True))
    val_set = MixedDataset(manifest, "val", build_transform(224, False))

    source_counts = Counter(row["source"] for row in train_set.rows)
    source_factors = normalized_sqrt_inverse(source_counts, 3.0)
    sample_weights = [source_factors[row["source"]] for row in train_set.rows]
    generator = torch.Generator().manual_seed(args.seed)
    sampler = WeightedRandomSampler(sample_weights, len(sample_weights), replacement=True, generator=generator)
    train_loader = DataLoader(train_set, batch_size=32, sampler=sampler, num_workers=0, pin_memory=device.type == "cuda")
    val_loader = DataLoader(val_set, batch_size=32, shuffle=False, num_workers=0, pin_memory=device.type == "cuda")

    class_counts = Counter(int(row["site_label"]) for row in train_set.rows)
    class_factors = normalized_sqrt_inverse(class_counts, 3.0)
    class_weight_tensor = torch.tensor([class_factors[index] for index in range(5)], device=device)
    class_weight_tensor /= class_weight_tensor.mean()
    criterion = nn.CrossEntropyLoss(weight=class_weight_tensor).to(device)
    model = resnet18(weights=ResNet18_Weights.DEFAULT)
    model.fc = nn.Linear(model.fc.in_features, 5)
    model = model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.0003, weight_decay=0.0001)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")

    best_score, best_record, history = -1.0, None, []
    checkpoint = ROOT / f"checkpoints/profiles/all_compatible_pilot_seed{args.seed}.pt"
    for epoch in range(args.epochs):
        train_metrics = run_epoch(model, train_loader, criterion, device, optimizer, scaler)
        val_metrics = run_epoch(model, val_loader, criterion, device)
        record = {"epoch": epoch + 1, "train": train_metrics, "validation": val_metrics}
        history.append(record)
        score = val_metrics["balanced_accuracy"]
        if score > best_score:
            best_score, best_record = score, record
            checkpoint.parent.mkdir(parents=True, exist_ok=True)
            torch.save({"model": model.state_dict(), "epoch": epoch, "best_score": score, "seed": args.seed}, checkpoint)
        print(
            f"mixed seed={args.seed} epoch={epoch+1}/{args.epochs} train_BA={train_metrics['balanced_accuracy']:.4f} "
            f"val_BA={score:.4f} macro_source_BA={val_metrics['macro_source_present_class_balanced_accuracy']:.4f}",
            flush=True,
        )
    result = {
        "profile": "all_compatible",
        "sources": dict(source_counts),
        "source_sampling_factors": source_factors,
        "class_counts": {SITE_CLASSES[key]: value for key, value in class_counts.items()},
        "class_loss_weights": dict(zip(SITE_CLASSES, class_weight_tensor.detach().cpu().tolist())),
        "epochs": args.epochs,
        "seed": args.seed,
        "best": best_record,
        "history": history,
        "test_used": False,
        "interpretation_limit": "three-epoch mixed-domain pilot",
    }
    output = ROOT / f"results/profiles/all_compatible_pilot_seed{args.seed}.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved {output}")


if __name__ == "__main__":
    main()
