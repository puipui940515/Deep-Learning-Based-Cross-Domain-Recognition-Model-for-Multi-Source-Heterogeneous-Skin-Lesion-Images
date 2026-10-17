from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from torchvision.models import ConvNeXt_Tiny_Weights, convnext_tiny


CLASSES = ["head", "torso", "upper_extremity", "lower_extremity", "hands_feet"]


class PartDataset(Dataset):
    def __init__(self, manifest: Path, image_root: Path, split: str, image_size: int, limit: int | None, sample_seed: int, label_mode: str, label_seed: int):
        if split == "test":
            raise ValueError("DensePose minival test remains sealed")
        with manifest.open("r", encoding="utf-8-sig", newline="") as handle:
            self.rows = [row for row in csv.DictReader(handle) if row["split"] == split]
        if limit and len(self.rows) > limit:
            self.rows = random.Random(sample_seed).sample(self.rows, limit)
        self.root = image_root
        mapping = {name: index for index, name in enumerate(CLASSES)}
        self.targets = [mapping[row["label"]] for row in self.rows]
        if label_mode == "shuffled":
            random.Random(label_seed + (0 if split == "train" else 1)).shuffle(self.targets)
        operations = []
        if split == "train":
            operations.extend([
                transforms.RandomHorizontalFlip(),
                transforms.RandomRotation(10),
                transforms.ColorJitter(brightness=0.1, contrast=0.1, saturation=0.1),
            ])
        operations.extend([
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])
        self.transform = transforms.Compose(operations)

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        with Image.open(self.root / row["image_path"]) as image:
            crop = tuple(int(row[key]) for key in ("x1", "y1", "x2", "y2"))
            tensor = self.transform(image.convert("RGB").crop(crop))
        return tensor, self.targets[index]


def calculate_metrics(logits: np.ndarray, targets: np.ndarray) -> dict[str, object]:
    predictions = logits.argmax(1)
    recalls, f1s = [], []
    confusion = np.zeros((len(CLASSES), len(CLASSES)), dtype=int)
    for actual, predicted in zip(targets, predictions):
        confusion[int(actual), int(predicted)] += 1
    for target in range(len(CLASSES)):
        tp = int(confusion[target, target])
        fn = int(confusion[target].sum() - tp)
        fp = int(confusion[:, target].sum() - tp)
        recall = tp / (tp + fn) if tp + fn else 0.0
        precision = tp / (tp + fp) if tp + fp else 0.0
        recalls.append(recall)
        f1s.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return {
        "accuracy": float(np.mean(predictions == targets)),
        "balanced_accuracy": float(np.mean(recalls)),
        "macro_f1": float(np.mean(f1s)),
        "per_class_recall": dict(zip(CLASSES, recalls)),
        "per_class_f1": dict(zip(CLASSES, f1s)),
        "confusion_matrix": confusion.tolist(),
    }


def run_epoch(model, loader, criterion, device, optimizer=None, scaler=None):
    training = optimizer is not None
    model.train(training)
    all_logits, all_targets, total_loss = [], [], 0.0
    for step, (images, targets) in enumerate(loader, 1):
        images, targets = images.to(device), targets.to(device)
        if training:
            optimizer.zero_grad(set_to_none=True)
        with torch.set_grad_enabled(training), torch.amp.autocast(device_type=device.type, enabled=device.type == "cuda"):
            logits = model(images)
            loss = criterion(logits, targets)
        if training:
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
        total_loss += loss.item() * targets.size(0)
        all_logits.append(logits.detach().float().cpu().numpy())
        all_targets.append(targets.cpu().numpy())
        if training and (step == 1 or step % 50 == 0 or step == len(loader)):
            print(f"batch {step}/{len(loader)} loss={loss.item():.4f}", flush=True)
    result = calculate_metrics(np.concatenate(all_logits), np.concatenate(all_targets))
    result["loss"] = total_loss / len(loader.dataset)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--epochs", type=int, required=True)
    parser.add_argument("--label-mode", choices=("true", "shuffled"), required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--image-size", type=int, default=224)
    parser.add_argument("--max-train-samples", type=int, default=50000)
    parser.add_argument("--max-val-samples", type=int, default=10000)
    parser.add_argument("--sample-seed", type=int, default=20260824)
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_set = PartDataset(args.manifest, args.images, "train", args.image_size, args.max_train_samples, args.sample_seed, args.label_mode, args.seed)
    val_set = PartDataset(args.manifest, args.images, "val", args.image_size, args.max_val_samples, args.sample_seed, args.label_mode, args.seed)
    loader_args = {"batch_size": args.batch_size, "num_workers": args.workers, "pin_memory": device.type == "cuda"}
    generator = torch.Generator().manual_seed(args.seed)
    train_loader = DataLoader(train_set, shuffle=True, generator=generator, **loader_args)
    val_loader = DataLoader(val_set, shuffle=False, **loader_args)

    model = convnext_tiny(weights=ConvNeXt_Tiny_Weights.DEFAULT)
    model.classifier[2] = nn.Linear(model.classifier[2].in_features, len(CLASSES))
    model.to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    args.output.mkdir(parents=True, exist_ok=True)
    history, best_score = [], -1.0
    print(f"device={device} mode={args.label_mode} seed={args.seed} train={len(train_set)} val={len(val_set)}", flush=True)

    for epoch in range(1, args.epochs + 1):
        train_result = run_epoch(model, train_loader, criterion, device, optimizer, scaler)
        val_result = run_epoch(model, val_loader, criterion, device)
        record = {"epoch": epoch, "train": train_result, "validation": val_result}
        history.append(record)
        print(f"epoch={epoch} train_BA={train_result['balanced_accuracy']:.4f} val_BA={val_result['balanced_accuracy']:.4f} val_acc={val_result['accuracy']:.4f} val_F1={val_result['macro_f1']:.4f}", flush=True)
        if val_result["balanced_accuracy"] > best_score:
            best_score = float(val_result["balanced_accuracy"])
            torch.save({"model": model.state_dict(), "classes": CLASSES, "seed": args.seed, "epoch": epoch, "label_mode": args.label_mode}, args.output / f"best_seed{args.seed}.pt")
        result = {
            "task": "DensePose five-class anatomical crop classification",
            "model": "convnext_tiny",
            "loss": "unweighted_cross_entropy",
            "label_mode": args.label_mode,
            "seed": args.seed,
            "sample_seed": args.sample_seed,
            "device": str(device),
            "train_samples": len(train_set),
            "val_samples": len(val_set),
            "test_used": False,
            "history": history,
        }
        (args.output / f"result_seed{args.seed}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
