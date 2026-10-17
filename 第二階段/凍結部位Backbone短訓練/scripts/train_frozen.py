from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader, Subset
from torchvision.models import ConvNeXt_Tiny_Weights, convnext_tiny


ROOT = Path(__file__).resolve().parents[1]
STAGE2_ROOT = ROOT.parent
PROJECT_ROOT = STAGE2_ROOT.parent
sys.path.insert(0, str(STAGE2_ROOT / "src"))
from stage2.data import ManifestDataset, build_transform
from stage2.engine import run_epoch, seed_everything


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def build_frozen_model(condition: str, config: dict, seed: int):
    asset_info = None
    if condition == "imagenet_frozen":
        model = convnext_tiny(weights=ConvNeXt_Tiny_Weights.DEFAULT)
    else:
        asset_info = config["assets"][condition]
        asset_path = (ROOT / asset_info["path"]).resolve()
        actual_hash = sha256(asset_path)
        if actual_hash != asset_info["sha256"]:
            raise RuntimeError(f"Asset checksum mismatch: {asset_path}\n{actual_hash}")
        model = convnext_tiny(weights=None)
        model.classifier[2] = nn.Linear(model.classifier[2].in_features, 5)
        checkpoint = torch.load(asset_path, map_location="cpu", weights_only=False)
        model.load_state_dict(checkpoint["model"], strict=True)

    for parameter in model.parameters():
        parameter.requires_grad = False
    torch.manual_seed(seed + 700000)
    model.classifier[2] = nn.Linear(model.classifier[2].in_features, config["num_classes"])
    trainable_names = [name for name, parameter in model.named_parameters() if parameter.requires_grad]
    if trainable_names != ["classifier.2.weight", "classifier.2.bias"]:
        raise RuntimeError(f"Unexpected trainable parameters: {trainable_names}")
    return model, asset_info, trainable_names


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--max-train-samples", type=int)
    parser.add_argument("--max-val-samples", type=int)
    args = parser.parse_args()
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    if args.condition not in config["conditions"]:
        raise SystemExit(f"condition must be one of {config['conditions']}")
    if args.seed not in config["seeds"]:
        raise SystemExit(f"seed must be one of {config['seeds']}")
    gate = PROJECT_ROOT / "驗證/reports/validation_gate.json"
    if not gate.exists() or not json.loads(gate.read_text(encoding="utf-8")).get("passed", False):
        raise SystemExit("Root validation gate has not passed")

    seed_everything(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    manifest = (ROOT / config["split_manifest"]).resolve()
    dataset_root = (ROOT / config["dataset_root"]).resolve()
    train_set = ManifestDataset(manifest, dataset_root, "train", build_transform(config["image_size"], True))
    val_set = ManifestDataset(manifest, dataset_root, "val", build_transform(config["image_size"], False))
    generator = torch.Generator().manual_seed(20260824)
    if args.max_train_samples and args.max_train_samples < len(train_set):
        indices = torch.randperm(len(train_set), generator=generator)[:args.max_train_samples].tolist()
        train_set = Subset(train_set, indices)
    if args.max_val_samples and args.max_val_samples < len(val_set):
        indices = torch.randperm(len(val_set), generator=generator)[:args.max_val_samples].tolist()
        val_set = Subset(val_set, indices)
    loader_args = {"batch_size": config["batch_size"], "num_workers": config["num_workers"], "pin_memory": device.type == "cuda"}
    shuffle_generator = torch.Generator().manual_seed(args.seed)
    train_loader = DataLoader(train_set, shuffle=True, generator=shuffle_generator, **loader_args)
    val_loader = DataLoader(val_set, shuffle=False, **loader_args)

    model, asset_info, trainable_names = build_frozen_model(args.condition, config, args.seed)
    model.to(device)
    trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
    optimizer = torch.optim.AdamW(trainable, lr=config["learning_rate"], weight_decay=config["weight_decay"])
    criterion = nn.CrossEntropyLoss().to(device)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    output_dir = ROOT / "results" / args.condition / f"seed{args.seed}"
    output_dir.mkdir(parents=True, exist_ok=True)
    history, best_score, best_record = [], -1.0, None
    epochs = args.epochs or config["epochs"]
    print(f"condition={args.condition} seed={args.seed} device={device} train={len(train_set)} val={len(val_set)} trainable={sum(p.numel() for p in trainable)}", flush=True)
    for epoch in range(epochs):
        train_metrics = run_epoch(model, train_loader, criterion, device, optimizer, scaler, config["gradient_accumulation"])
        val_metrics = run_epoch(model, val_loader, criterion, device)
        record = {"epoch": epoch + 1, "train": train_metrics, "val": val_metrics}
        history.append(record)
        if val_metrics["balanced_accuracy"] > best_score:
            best_score, best_record = val_metrics["balanced_accuracy"], record
            torch.save({"model": model.state_dict(), "condition": args.condition, "seed": args.seed, "epoch": epoch + 1, "backbone_frozen": True}, output_dir / "best.pt")
        print(f"epoch={epoch+1}/{epochs} train_BA={train_metrics['balanced_accuracy']:.4f} val_BA={val_metrics['balanced_accuracy']:.4f} val_acc={val_metrics['accuracy']:.4f}", flush=True)

    result = {
        "comparison_id": config["comparison_id"], "condition": args.condition, "seed": args.seed,
        "architecture": "convnext_tiny", "image_size": config["image_size"], "batch_size": config["batch_size"],
        "gradient_accumulation": config["gradient_accumulation"], "loss": "cross_entropy",
        "backbone_frozen": True, "trainable_parameter_names": trainable_names,
        "trainable_parameters": sum(p.numel() for p in trainable),
        "total_parameters": sum(p.numel() for p in model.parameters()),
        "asset": asset_info, "train_samples": len(train_set), "val_samples": len(val_set),
        "best": best_record, "history": history, "test_used": False,
        "direct_comparison_valid": args.condition != "densepose_shuffled_frozen",
        "notes": "Shuffled asset is exploratory because its saved pretraining epoch differs from true asset." if args.condition == "densepose_shuffled_frozen" else "Controlled frozen-backbone short training."
    }
    (output_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
