from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler

EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
STAGE2_ROOT = EXPERIMENT_ROOT.parent
PROJECT_ROOT = STAGE2_ROOT.parent
sys.path.insert(0, str(STAGE2_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "第三階段" / "src"))

from stage2.data import build_transform
from stage2.engine import seed_everything
from stage2.metrics import metrics_from_logits
from stage2.models import build_model, parameter_groups_with_layer_decay
from stage3.metrics import metrics_by_site
from stage3.site_labels import SITE_GROUPS, build_within_diagnosis_site_weights


class SiteDataset(Dataset):
    def __init__(self, manifest: Path, dataset_root: Path, split: str, transform) -> None:
        self.dataset_root = dataset_root
        self.transform = transform
        with manifest.open("r", encoding="utf-8-sig", newline="") as handle:
            self.rows = [row for row in csv.DictReader(handle) if row["split"] == split]
        if not self.rows:
            raise ValueError(f"manifest 中沒有 split={split}")

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        with Image.open(self.dataset_root / row["image_path"]) as image:
            image = image.convert("RGB")
        return (
            self.transform(image),
            int(row["label"]),
            row["isic_id"],
            int(row["site_label"]),
        )


def run_epoch(model, loader, criterion, device, min_site_support, optimizer=None, scaler=None, accumulation=1):
    training = optimizer is not None
    model.train(training)
    total_loss = 0.0
    all_logits, all_targets, all_sites = [], [], []
    if training:
        optimizer.zero_grad(set_to_none=True)
    for step, (images, targets, _, sites) in enumerate(loader):
        images, targets = images.to(device), targets.to(device)
        with torch.set_grad_enabled(training):
            with torch.amp.autocast(device_type=device.type, enabled=device.type == "cuda"):
                logits = model(images)
                loss = criterion(logits, targets)
            if training:
                scaler.scale(loss / accumulation).backward()
                if (step + 1) % accumulation == 0 or step + 1 == len(loader):
                    scaler.step(optimizer)
                    scaler.update()
                    optimizer.zero_grad(set_to_none=True)
        total_loss += loss.item() * targets.size(0)
        all_logits.append(logits.detach().float().cpu().numpy())
        all_targets.append(targets.cpu().numpy())
        all_sites.append(sites.numpy())
    logits = np.concatenate(all_logits)
    targets = np.concatenate(all_targets)
    sites = np.concatenate(all_sites)
    result = metrics_from_logits(logits, targets)
    result["loss"] = total_loss / len(loader.dataset)
    result["by_site"] = metrics_by_site(
        logits,
        targets,
        sites,
        site_groups=SITE_GROUPS,
        min_support=min_site_support,
    )
    return result


def build_optimizer(model, stage2_config):
    groups = parameter_groups_with_layer_decay(
        model,
        stage2_config["base_learning_rate"],
        stage2_config["weight_decay"],
        stage2_config["layer_decay"],
    )
    return torch.optim.AdamW(groups)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--epochs", type=int)
    args = parser.parse_args()

    config = json.loads((EXPERIMENT_ROOT / "config.json").read_text(encoding="utf-8"))
    stage2_config = json.loads((STAGE2_ROOT / "config/stage2.json").read_text(encoding="utf-8"))
    if args.seed not in config["seeds"]:
        raise SystemExit(f"seed 必須為 {config['seeds']}")
    epochs = args.epochs or config["pilot_epochs"]
    manifest = EXPERIMENT_ROOT / config["manifest"]
    dataset_root = (EXPERIMENT_ROOT / config["dataset_root"]).resolve()
    source_checkpoint = STAGE2_ROOT / f"checkpoints/v7_seed{args.seed}.pt"
    if not source_checkpoint.exists():
        raise SystemExit(f"缺少來源 checkpoint：{source_checkpoint}")

    spec = stage2_config["versions"]["v7"]
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_set = SiteDataset(manifest, dataset_root, "train", build_transform(spec["image_size"], True))
    val_set = SiteDataset(manifest, dataset_root, "val", build_transform(spec["image_size"], False))
    loader_args = {
        "batch_size": spec["batch_size"],
        "num_workers": stage2_config["num_workers"],
        "pin_memory": device.type == "cuda",
    }
    val_loader = DataLoader(val_set, shuffle=False, **loader_args)
    criterion = nn.CrossEntropyLoss().to(device)
    source_state = torch.load(source_checkpoint, map_location=device, weights_only=False)

    baseline_model = build_model("convnext_tiny", False, stage2_config["num_classes"]).to(device)
    baseline_model.load_state_dict(source_state["model"])
    baseline = run_epoch(
        baseline_model,
        val_loader,
        criterion,
        device,
        config["validation_min_site_support"],
    )
    del baseline_model
    if device.type == "cuda":
        torch.cuda.empty_cache()

    weights, weight_audit = build_within_diagnosis_site_weights(
        train_set.rows,
        **config["site_sampler"],
    )
    branches = {}
    for branch in ("control", "site_balanced"):
        seed_everything(args.seed + 100_000)
        model = build_model("convnext_tiny", False, stage2_config["num_classes"]).to(device)
        model.load_state_dict(source_state["model"])
        optimizer = build_optimizer(model, stage2_config)
        optimizer.load_state_dict(source_state["optimizer"])
        scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
        if "scaler" in source_state:
            scaler.load_state_dict(source_state["scaler"])

        generator = torch.Generator().manual_seed(args.seed + 100_000)
        if branch == "control":
            train_loader = DataLoader(train_set, shuffle=True, generator=generator, **loader_args)
        else:
            sampler = WeightedRandomSampler(
                weights,
                num_samples=len(weights),
                replacement=True,
                generator=generator,
            )
            train_loader = DataLoader(train_set, sampler=sampler, **loader_args)

        train_history = []
        for epoch in range(epochs):
            metrics = run_epoch(
                model,
                train_loader,
                criterion,
                device,
                config["validation_min_site_support"],
                optimizer,
                scaler,
                spec["gradient_accumulation"],
            )
            train_history.append(metrics)
            print(
                f"seed={args.seed} branch={branch} epoch={epoch + 1}/{epochs} "
                f"train_BA={metrics['balanced_accuracy']:.4f}",
                flush=True,
            )
        validation = run_epoch(
            model,
            val_loader,
            criterion,
            device,
            config["validation_min_site_support"],
        )
        branches[branch] = {
            "train": train_history,
            "validation": validation,
            "delta_vs_start": {
                "balanced_accuracy": validation["balanced_accuracy"] - baseline["balanced_accuracy"],
                "macro_f1": validation["macro_f1"] - baseline["macro_f1"],
                "ece": validation["ece"] - baseline["ece"],
            },
        }
        print(
            f"seed={args.seed} branch={branch} val_BA={validation['balanced_accuracy']:.4f} "
            f"val_F1={validation['macro_f1']:.4f}",
            flush=True,
        )
        del model, optimizer, scaler, train_loader
        if device.type == "cuda":
            torch.cuda.empty_cache()

    comparison = {
        "balanced_accuracy": branches["site_balanced"]["validation"]["balanced_accuracy"]
        - branches["control"]["validation"]["balanced_accuracy"],
        "macro_f1": branches["site_balanced"]["validation"]["macro_f1"]
        - branches["control"]["validation"]["macro_f1"],
        "ece": branches["site_balanced"]["validation"]["ece"]
        - branches["control"]["validation"]["ece"],
        "worst_known_site_balanced_accuracy": branches["site_balanced"]["validation"]["by_site"]["worst_known_site_balanced_accuracy"]
        - branches["control"]["validation"]["by_site"]["worst_known_site_balanced_accuracy"],
    }
    result = {
        "experiment": "v7_site_label_pilot",
        "seed": args.seed,
        "epochs_per_branch": epochs,
        "source_checkpoint": str(source_checkpoint.relative_to(PROJECT_ROOT)),
        "device": str(device),
        "baseline": baseline,
        "branches": branches,
        "site_balanced_minus_control": comparison,
        "weight_audit": weight_audit,
        "test_split_used": False,
        "interpretation_limit": "短程 A/B 先導測試；不得取代從頭訓練的正式三 seed 結果",
    }
    output = EXPERIMENT_ROOT / f"results/seed{args.seed}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "comparison": comparison}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
