from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from torchvision.models import ResNet18_Weights, resnet18


ROOT = Path(__file__).resolve().parents[1]


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def map_body_part(raw: str) -> str | None:
    value = raw.strip().lower()
    if value == "torso":
        return "torso"
    if value.startswith("left arm"):
        return "left_arm"
    if value.startswith("right arm"):
        return "right_arm"
    if value.startswith("left leg"):
        return "left_leg"
    if value.startswith("right leg"):
        return "right_leg"
    return None


def load_rows(metadata_path: Path, source_split: str) -> list[dict[str, str]]:
    with metadata_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = []
        for row in csv.DictReader(handle):
            site = map_body_part(row["body_part"])
            if row["split"].strip().lower() == source_split and site is not None:
                rows.append({"image_id": row["image_id"], "site": site})
    if not rows:
        raise RuntimeError("找不到可用的 iToBoS 部位資料")
    return rows


def stratified_split(
    rows: list[dict[str, str]], validation_fraction: float, seed: int
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["site"]].append(row)
    rng = random.Random(seed)
    train_rows, validation_rows = [], []
    for site in sorted(groups):
        group = sorted(groups[site], key=lambda item: item["image_id"])
        rng.shuffle(group)
        validation_count = max(1, round(len(group) * validation_fraction))
        validation_rows.extend(group[:validation_count])
        train_rows.extend(group[validation_count:])
    rng.shuffle(train_rows)
    validation_rows.sort(key=lambda item: item["image_id"])
    return train_rows, validation_rows


def apply_label_mode(
    rows: list[dict[str, str]], label_mode: str, seed: int
) -> list[dict[str, str]]:
    copied = [dict(row) for row in rows]
    if label_mode == "shuffled":
        labels = [row["site"] for row in copied]
        random.Random(seed + 100_003).shuffle(labels)
        for row, label in zip(copied, labels):
            row["site"] = label
    return copied


def build_transform(image_size: int, training: bool):
    if training:
        operations = [
            transforms.RandomRotation(10),
            transforms.RandomResizedCrop(
                image_size, scale=(0.85, 1.0), ratio=(0.9, 1.1)
            ),
            transforms.ColorJitter(brightness=0.1, contrast=0.1, saturation=0.1),
        ]
    else:
        operations = [transforms.Resize((image_size, image_size))]
    operations.extend(
        [
            transforms.ToTensor(),
            transforms.Normalize(
                [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]
            ),
        ]
    )
    return transforms.Compose(operations)


class IToBoSSiteDataset(Dataset):
    def __init__(self, rows, images_dir: Path, site_classes, transform):
        self.rows = rows
        self.images_dir = images_dir
        self.site_to_target = {
            name: index for index, name in enumerate(site_classes)
        }
        self.transform = transform

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        image_path = self.images_dir / f"{row['image_id']}.png"
        with Image.open(image_path) as image:
            image = image.convert("RGB")
        return (
            self.transform(image),
            self.site_to_target[row["site"]],
            row["image_id"],
        )


def class_weights(rows, site_classes):
    counts = Counter(row["site"] for row in rows)
    reference = max(counts.values())
    values = [math.sqrt(reference / counts[name]) for name in site_classes]
    mean = sum(values) / len(values)
    return [value / mean for value in values], counts


def metrics_from_predictions(targets, predictions, site_classes):
    targets = np.asarray(targets)
    predictions = np.asarray(predictions)
    recalls, f1_values, per_class = [], [], {}
    for index, name in enumerate(site_classes):
        true_positive = int(((targets == index) & (predictions == index)).sum())
        false_negative = int(((targets == index) & (predictions != index)).sum())
        false_positive = int(((targets != index) & (predictions == index)).sum())
        recall = true_positive / max(1, true_positive + false_negative)
        precision = true_positive / max(1, true_positive + false_positive)
        f1 = 2 * precision * recall / max(1e-12, precision + recall)
        recalls.append(recall)
        f1_values.append(f1)
        per_class[name] = {
            "recall": recall,
            "precision": precision,
            "f1": f1,
            "support": int((targets == index).sum()),
        }
    return {
        "accuracy": float((targets == predictions).mean()),
        "balanced_accuracy": float(np.mean(recalls)),
        "macro_f1": float(np.mean(f1_values)),
        "per_class": per_class,
    }


def run_epoch(model, loader, criterion, device, site_classes, optimizer=None, scaler=None):
    training = optimizer is not None
    model.train(training)
    total_loss = 0.0
    all_targets, all_predictions, all_ids = [], [], []
    if training:
        optimizer.zero_grad(set_to_none=True)
    for images, targets, image_ids in loader:
        images, targets = images.to(device), targets.to(device)
        with torch.set_grad_enabled(training):
            with torch.amp.autocast(
                device_type=device.type, enabled=device.type == "cuda"
            ):
                logits = model(images)
                loss = criterion(logits, targets)
            if training:
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad(set_to_none=True)
        total_loss += loss.item() * targets.size(0)
        all_targets.extend(targets.detach().cpu().tolist())
        all_predictions.extend(logits.argmax(dim=1).detach().cpu().tolist())
        all_ids.extend(image_ids)
    result = metrics_from_predictions(all_targets, all_predictions, site_classes)
    result["loss"] = total_loss / len(loader.dataset)
    return result, all_ids, all_targets, all_predictions


def write_manifest(path: Path, train_rows, validation_rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image_id", "site", "pilot_split"])
        writer.writeheader()
        for split, rows in (("train", train_rows), ("validation", validation_rows)):
            for row in rows:
                writer.writerow({**row, "pilot_split": split})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label-mode", choices=["true", "shuffled"], required=True)
    parser.add_argument("--config", default=str(ROOT / "config/pilot_resnet18.json"))
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    seed = int(config["seed"])
    seed_everything(seed)
    dataset_root = (ROOT / config["dataset_root"]).resolve()
    metadata_path = dataset_root / config["metadata_file"]
    images_dir = dataset_root / config["images_directory"]
    if not metadata_path.exists() or not images_dir.is_dir():
        raise SystemExit(f"iToBoS 尚未正確解壓：{dataset_root}")

    source_rows = load_rows(metadata_path, config["source_split"])
    train_rows, validation_rows = stratified_split(
        source_rows, float(config["validation_fraction"]), seed
    )
    train_rows = apply_label_mode(train_rows, args.label_mode, seed)
    manifest_path = ROOT / "data" / f"pilot_manifest_{args.label_mode}_seed{seed}.csv"
    write_manifest(manifest_path, train_rows, validation_rows)

    site_classes = config["site_classes"]
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_set = IToBoSSiteDataset(
        train_rows, images_dir, site_classes, build_transform(config["image_size"], True)
    )
    validation_set = IToBoSSiteDataset(
        validation_rows,
        images_dir,
        site_classes,
        build_transform(config["image_size"], False),
    )
    loader_args = {
        "batch_size": config["batch_size"],
        "num_workers": config["num_workers"],
        "pin_memory": device.type == "cuda",
    }
    train_loader = DataLoader(
        train_set,
        shuffle=True,
        generator=torch.Generator().manual_seed(seed),
        **loader_args,
    )
    validation_loader = DataLoader(validation_set, shuffle=False, **loader_args)

    weights = ResNet18_Weights.DEFAULT if config["pretrained"] else None
    model = resnet18(weights=weights)
    model.fc = nn.Linear(model.fc.in_features, len(site_classes))
    model = model.to(device)
    loss_weights, counts = class_weights(train_rows, site_classes)
    criterion = nn.CrossEntropyLoss(
        weight=torch.tensor(loss_weights, dtype=torch.float32, device=device)
    )
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config["learning_rate"],
        weight_decay=config["weight_decay"],
    )
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")

    history = []
    started = time.time()
    for epoch in range(int(config["epochs"])):
        train_metrics, _, _, _ = run_epoch(
            model,
            train_loader,
            criterion,
            device,
            site_classes,
            optimizer,
            scaler,
        )
        validation_metrics, ids, targets, predictions = run_epoch(
            model, validation_loader, criterion, device, site_classes
        )
        record = {
            "epoch": epoch + 1,
            "train": train_metrics,
            "validation": validation_metrics,
        }
        history.append(record)
        print(
            f"mode={args.label_mode} epoch={epoch + 1} "
            f"train_BA={train_metrics['balanced_accuracy']:.4f} "
            f"val_BA={validation_metrics['balanced_accuracy']:.4f} "
            f"val_acc={validation_metrics['accuracy']:.4f}",
            flush=True,
        )

    checkpoint_dir = ROOT / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = checkpoint_dir / f"resnet18_{args.label_mode}_seed{seed}_pilot.pt"
    torch.save(
        {
            "model": model.state_dict(),
            "architecture": "resnet18",
            "site_classes": site_classes,
            "label_mode": args.label_mode,
            "seed": seed,
            "config": config,
            "pilot_only": True,
        },
        checkpoint_path,
    )

    results_dir = ROOT / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    prediction_path = results_dir / f"validation_predictions_{args.label_mode}_seed{seed}.csv"
    with prediction_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["image_id", "target", "prediction"])
        writer.writerows(zip(ids, targets, predictions))

    result = {
        "task": "iToBoS anatomical site classification pilot",
        "label_mode": args.label_mode,
        "pilot_only": True,
        "official_test_used": False,
        "validation_is_subject_disjoint": False,
        "validation_limitation": (
            "Public metadata has no patient identifier; pilot validation is an "
            "image-level split of the official training set."
        ),
        "dataset_version": 6,
        "dataset_doi": "10.6084/m9.figshare.28452545.v6",
        "model": "resnet18",
        "initialization": "ImageNet" if config["pretrained"] else "random",
        "device": str(device),
        "seed": seed,
        "epochs": config["epochs"],
        "site_classes": site_classes,
        "train_size": len(train_set),
        "validation_size": len(validation_set),
        "train_class_counts": dict(counts),
        "loss_weights": dict(zip(site_classes, loss_weights)),
        "history": history,
        "elapsed_seconds": time.time() - started,
        "checkpoint": str(checkpoint_path),
        "manifest": str(manifest_path),
    }
    result_path = results_dir / f"resnet18_{args.label_mode}_seed{seed}_pilot.json"
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"saved={result_path}", flush=True)


if __name__ == "__main__":
    main()
