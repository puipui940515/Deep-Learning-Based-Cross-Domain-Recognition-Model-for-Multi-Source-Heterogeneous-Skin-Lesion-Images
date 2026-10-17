from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
STAGE2 = PROJECT / "第二階段"
sys.path.insert(0, str(STAGE2 / "src"))

from stage2.data import build_transform
from stage2.engine import seed_everything
from stage2.metrics import metrics_from_logits
from stage2.models import build_model, parameter_groups_with_layer_decay

try:
    from tqdm.auto import tqdm
except ImportError:  # pragma: no cover
    def tqdm(iterable, **_kwargs):
        return iterable


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def stratified_limit(rows: list[dict], limit: int | None, seed: int) -> list[dict]:
    if not limit or limit >= len(rows):
        return rows
    groups = defaultdict(list)
    for row in rows:
        groups[(row["source"], int(row["label"]))].append(row)
    generator = np.random.default_rng(seed)
    for items in groups.values():
        generator.shuffle(items)
    selected = []
    keys = sorted(groups)
    while len(selected) < limit:
        progressed = False
        for key in keys:
            if groups[key] and len(selected) < limit:
                selected.append(groups[key].pop())
                progressed = True
        if not progressed:
            break
    return selected


class MixedDataset(Dataset):
    def __init__(self, rows: list[dict], image_size: int, train: bool):
        self.rows = rows
        self.transform = build_transform(image_size, train=train)

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int):
        row = self.rows[index]
        with Image.open(PROJECT / row["image_path"]) as image:
            tensor = self.transform(image.convert("RGB"))
        return tensor, int(row["label"]), row["image_id"], row["source"]


def source_class_weights(rows: list[dict], alpha: float) -> tuple[list[float], dict]:
    counts = Counter((row["source"], int(row["label"])) for row in rows)
    sources = sorted({row["source"] for row in rows})
    source_normalizers = {}
    for source in sources:
        source_normalizers[source] = sum(
            count * (count ** (-alpha))
            for (candidate, _label), count in counts.items()
            if candidate == source
        )
    weights = []
    for row in rows:
        source = row["source"]
        count = counts[(source, int(row["label"]))]
        weights.append((count ** (-alpha)) / source_normalizers[source])
    total = sum(weights)
    expected_source_share = {
        source: sum(weight for weight, row in zip(weights, rows) if row["source"] == source) / total
        for source in sources
    }
    audit = {
        "class_balance_alpha": alpha,
        "source_class_counts": {
            f"{source}:{label}": count for (source, label), count in sorted(counts.items())
        },
        "expected_source_share": expected_source_share,
    }
    return weights, audit


def run_train_epoch(model, loader, criterion, device, optimizer, scaler, accumulation: int):
    model.train()
    optimizer.zero_grad(set_to_none=True)
    total_loss, logits_all, targets_all = 0.0, [], []
    progress = tqdm(loader, desc="訓練", leave=False, unit="batch")
    for step, (images, targets, _image_ids, _sources) in enumerate(progress):
        images = images.to(device, non_blocking=True)
        targets = targets.to(device, non_blocking=True)
        with torch.amp.autocast(device_type=device.type, enabled=device.type == "cuda"):
            logits = model(images)
            loss = criterion(logits, targets)
        scaler.scale(loss / accumulation).backward()
        if (step + 1) % accumulation == 0 or step + 1 == len(loader):
            scaler.step(optimizer)
            scaler.update()
            optimizer.zero_grad(set_to_none=True)
        total_loss += loss.item() * targets.size(0)
        logits_all.append(logits.detach().float().cpu().numpy())
        targets_all.append(targets.detach().cpu().numpy())
        if hasattr(progress, "set_postfix"):
            progress.set_postfix(loss=f"{loss.item():.4f}")
    metrics = metrics_from_logits(np.concatenate(logits_all), np.concatenate(targets_all), num_classes=7)
    metrics["loss"] = total_loss / len(loader.dataset)
    return metrics


@torch.inference_mode()
def run_validation(model, loader, criterion, device, source: str):
    model.eval()
    total_loss, logits_all, targets_all = 0.0, [], []
    progress = tqdm(loader, desc=f"驗證 {source}", leave=False, unit="batch")
    for images, targets, _image_ids, _sources in progress:
        images = images.to(device, non_blocking=True)
        targets = targets.to(device, non_blocking=True)
        with torch.amp.autocast(device_type=device.type, enabled=device.type == "cuda"):
            logits = model(images)
            loss = criterion(logits, targets)
        total_loss += loss.item() * targets.size(0)
        logits_all.append(logits.float().cpu().numpy())
        targets_all.append(targets.cpu().numpy())
    metrics = metrics_from_logits(np.concatenate(logits_all), np.concatenate(targets_all), num_classes=7)
    metrics["loss"] = total_loss / len(loader.dataset)
    metrics["samples"] = len(loader.dataset)
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="HAM10000 + BCN20000 多來源混合訓練")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--max-train-samples", type=int, help="只供 smoke test 使用")
    parser.add_argument("--max-val-samples-per-source", type=int, help="只供 smoke test 使用")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8-sig"))
    seed_everything(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    manifest_path = ROOT / config["manifest"]
    if not manifest_path.exists():
        raise FileNotFoundError(f"缺少 {manifest_path}，請先執行 build_manifest.py")
    rows = read_csv(manifest_path)
    train_rows = stratified_limit(
        [row for row in rows if row["split"] == "train"], args.max_train_samples, args.seed + 1000
    )
    validation_rows = {}
    for source in sorted({row["source"] for row in rows if row["split"] == "validation"}):
        source_rows = [row for row in rows if row["split"] == "validation" and row["source"] == source]
        validation_rows[source] = stratified_limit(
            source_rows, args.max_val_samples_per_source, args.seed + 2000
        )

    train_set = MixedDataset(train_rows, config["image_size"], train=True)
    weights, sampling_audit = source_class_weights(train_rows, config["sampling"]["class_balance_alpha"])
    sampler_generator = torch.Generator().manual_seed(args.seed + 3000)
    sampler = WeightedRandomSampler(
        torch.as_tensor(weights, dtype=torch.double),
        num_samples=len(train_set), replacement=True, generator=sampler_generator,
    )
    loader_args = {
        "batch_size": config["batch_size"],
        "num_workers": config["num_workers"],
        "pin_memory": device.type == "cuda",
    }
    train_loader = DataLoader(train_set, sampler=sampler, **loader_args)
    validation_loaders = {
        source: DataLoader(MixedDataset(source_rows, config["image_size"], train=False), shuffle=False, **loader_args)
        for source, source_rows in validation_rows.items()
    }

    model = build_model(config["model"], pretrained=True, num_classes=config["num_classes"]).to(device)
    optimizer = torch.optim.AdamW(parameter_groups_with_layer_decay(
        model, config["learning_rate"], config["weight_decay"], config["layer_decay"]
    ))
    criterion = nn.CrossEntropyLoss().to(device)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")

    output_root = (args.output_root or (ROOT / "results")).resolve()
    output_dir = output_root / f"imagenet_seed{args.seed}"
    output_dir.mkdir(parents=True, exist_ok=True)
    best_path, last_path = output_dir / "best.pt", output_dir / "last.pt"
    history, best_score, best_record, patience, start_epoch = [], -math.inf, None, 0, 0
    if args.resume and last_path.exists():
        state = torch.load(last_path, map_location=device, weights_only=False)
        model.load_state_dict(state["model"])
        optimizer.load_state_dict(state["optimizer"])
        scaler.load_state_dict(state["scaler"])
        history = state["history"]
        best_score = state["best_score"]
        best_record = state["best_record"]
        patience = state["patience"]
        start_epoch = state["epoch"]
        if "sampler_generator_state" in state:
            sampler_generator.set_state(state["sampler_generator_state"])
        print(f"續訓：從 epoch {start_epoch + 1} 開始", flush=True)

    epochs = args.epochs or config["epochs"]
    print(
        f"device={device} model={config['model']} initialization=ImageNet seed={args.seed} "
        f"train={len(train_set)} validation="
        + ",".join(f"{source}:{len(loader.dataset)}" for source, loader in validation_loaders.items()),
        flush=True,
    )
    print("預期來源抽樣比例：" + json.dumps(sampling_audit["expected_source_share"], ensure_ascii=False), flush=True)

    for epoch_index in range(start_epoch, epochs):
        print(f"\nEpoch {epoch_index + 1}/{epochs}", flush=True)
        train_metrics = run_train_epoch(
            model, train_loader, criterion, device, optimizer, scaler, config["gradient_accumulation"]
        )
        val_metrics = {
            source: run_validation(model, loader, criterion, device, source)
            for source, loader in validation_loaders.items()
        }
        selection_score = float(np.mean([m["balanced_accuracy"] for m in val_metrics.values()]))
        record = {
            "epoch": epoch_index + 1,
            "train": train_metrics,
            "validation_by_source": val_metrics,
            "selection_mean_source_balanced_accuracy": selection_score,
        }
        history.append(record)
        if selection_score > best_score:
            best_score, best_record, patience = selection_score, record, 0
            torch.save({
                "model": model.state_dict(), "seed": args.seed, "epoch": epoch_index + 1,
                "architecture": "convnext_tiny_7_class", "initialization": "imagenet",
                "mixed_sources": ["HAM10000", "BCN20000"],
                "selection_score": selection_score, "test_used": False,
            }, best_path)
        else:
            patience += 1
        torch.save({
            "model": model.state_dict(), "optimizer": optimizer.state_dict(), "scaler": scaler.state_dict(),
            "history": history, "best_score": best_score, "best_record": best_record,
            "patience": patience, "epoch": epoch_index + 1,
            "sampler_generator_state": sampler_generator.get_state(),
        }, last_path)
        source_text = " ".join(
            f"{source}_BA={metrics['balanced_accuracy']:.4f}"
            for source, metrics in val_metrics.items()
        )
        print(
            f"train_BA={train_metrics['balanced_accuracy']:.4f} {source_text} "
            f"mean_source_BA={selection_score:.4f}", flush=True,
        )
        if patience >= config["early_stopping_patience"]:
            print(f"提前停止：連續 {patience} 個 epoch 未改善", flush=True)
            break

    result = {
        "experiment_id": config["experiment_id"],
        "seed": args.seed,
        "architecture": "convnext_tiny_7_class",
        "initialization": "imagenet",
        "training_sources": ["HAM10000", "BCN20000"],
        "train_samples": len(train_set),
        "validation_samples": {source: len(loader.dataset) for source, loader in validation_loaders.items()},
        "sampling": sampling_audit,
        "selection_metric": config["selection_metric"],
        "best": best_record,
        "history": history,
        "test_used": False,
    }
    (output_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"完成：{output_dir / 'result.json'}", flush=True)


if __name__ == "__main__":
    main()
