from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

import torch
from torch.utils.data import DataLoader


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from check_prerequisites import inspect
from stage3.data import V10NullControlDataset, build_site_sampler, build_transform
from stage3.engine import run_epoch, seed_everything
from stage3.losses import LogitAdjustedCrossEntropy
from stage3.models import build_v10_model, count_parameters, load_v9_backbone


def optimizer_groups(model, lr, weight_decay, decay):
    groups = {}
    max_depth = 9
    for name, parameter in model.named_parameters():
        if not parameter.requires_grad:
            continue
        if name.startswith("backbone.features."):
            try:
                depth = int(name.split(".")[2]) + 1
            except (ValueError, IndexError):
                depth = 1
        else:
            depth = max_depth
        no_decay = parameter.ndim == 1 or name.endswith(".bias")
        key = (depth, no_decay)
        groups.setdefault(
            key,
            {
                "params": [],
                "lr": lr * (decay ** (max_depth - depth)),
                "weight_decay": 0.0 if no_decay else weight_decay,
            },
        )["params"].append(parameter)
    return list(groups.values())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--dataset-root", type=Path)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    config = json.loads((ROOT / "config/stage3.json").read_text(encoding="utf-8"))
    if args.seed not in config["seeds"]:
        raise SystemExit(f"seed 必須為 {config['seeds']}")
    gate = inspect()
    if not gate["formal_v10_ready"]:
        (ROOT / "results").mkdir(exist_ok=True)
        (ROOT / "results/prerequisite_gate.json").write_text(
            json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        raise SystemExit("v10 未解鎖：先完成 v9 三種子與根目錄驗證；詳見 results/prerequisite_gate.json")

    spec = config["versions"]["v10"]
    site_config = config["site_labels"]
    seed_everything(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    manifest = ROOT / config["split_manifest"]
    dataset_root = args.dataset_root or (ROOT / config["dataset_root"]).resolve()
    train_set = V10NullControlDataset(
        manifest, dataset_root, "train", build_transform(spec["image_size"], True)
    )
    val_set = V10NullControlDataset(
        manifest, dataset_root, "val", build_transform(spec["image_size"], False)
    )

    loader_args = {
        "batch_size": spec["batch_size"],
        "num_workers": config["num_workers"],
        "pin_memory": device.type == "cuda",
    }
    generator = torch.Generator().manual_seed(args.seed)
    train_sampler, sampler_audit = build_site_sampler(
        train_set, site_config["site_balanced_sampling"], generator
    )
    train_loader = DataLoader(
        train_set,
        shuffle=train_sampler is None,
        sampler=train_sampler,
        generator=generator if train_sampler is None else None,
        **loader_args,
    )
    val_loader = DataLoader(val_set, shuffle=False, **loader_args)

    model = build_v10_model(
        config["num_classes"],
        spec["fusion_hidden_dim"],
        spec["fusion_dropout"],
        spec["gradient_checkpointing"],
    )
    v9_checkpoint = (ROOT / spec["backbone_source"].format(seed=args.seed)).resolve()
    load_v9_backbone(model, v9_checkpoint)
    model.to(device)
    optimizer = torch.optim.AdamW(
        optimizer_groups(
            model, config["base_learning_rate"], config["weight_decay"], config["layer_decay"]
        )
    )
    with manifest.open("r", encoding="utf-8-sig", newline="") as handle:
        counts = Counter(int(row["label"]) for row in csv.DictReader(handle) if row["split"] == "train")
    criterion = LogitAdjustedCrossEntropy(
        [counts[index] for index in range(config["num_classes"])], config["logit_adjustment_tau"]
    ).to(device)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    site_metric_args = {
        "site_names": site_config["groups"],
        "site_min_support": site_config["validation_min_support"],
    }

    checkpoint = ROOT / f"checkpoints/v10_seed{args.seed}.pt"
    best_score, patience, history, best_record, start_epoch = -1.0, 0, [], None, 0
    if args.resume and checkpoint.exists():
        state = torch.load(checkpoint, map_location=device, weights_only=False)
        model.load_state_dict(state["model"])
        optimizer.load_state_dict(state["optimizer"])
        scaler.load_state_dict(state["scaler"])
        best_score = state["best_score"]
        best_record = state.get("best_record")
        history = state.get("history", [])
        start_epoch = state["epoch"] + 1

    for epoch in range(start_epoch, args.epochs or config["epochs"]):
        train = run_epoch(
            model,
            train_loader,
            criterion,
            device,
            optimizer,
            scaler,
            spec["gradient_accumulation"],
            **site_metric_args,
        )
        val = run_epoch(model, val_loader, criterion, device, **site_metric_args)
        record = {"epoch": epoch + 1, "train": train, "val": val}
        history.append(record)
        score = val["balanced_accuracy"]
        if score > best_score:
            best_score, patience, best_record = score, 0, record
            checkpoint.parent.mkdir(parents=True, exist_ok=True)
            torch.save(
                {
                    "epoch": epoch,
                    "model": model.state_dict(),
                    "optimizer": optimizer.state_dict(),
                    "scaler": scaler.state_dict(),
                    "best_score": best_score,
                    "best_record": best_record,
                    "history": history,
                    "version": "v10",
                    "seed": args.seed,
                    "source_v9_checkpoint": str(v9_checkpoint),
                    "site_label_protocol": site_config,
                    "site_sampler_audit": sampler_audit,
                    "test_used": False,
                },
                checkpoint,
            )
        else:
            patience += 1
        print(
            f"v10 seed={args.seed} epoch={epoch + 1} "
            f"train_BA={train['balanced_accuracy']:.4f} val_BA={score:.4f} "
            f"worst_site_BA={val['site_metrics']['worst_known_site_balanced_accuracy']}",
            flush=True,
        )
        if patience >= config["early_stopping_patience"]:
            break

    result = {
        "version": "v10",
        "seed": args.seed,
        "spec": spec,
        "parameters": count_parameters(model),
        "device": str(device),
        "source_v9_checkpoint": str(v9_checkpoint),
        "site_label_protocol": site_config,
        "site_sampler_audit": sampler_audit,
        "best": best_record,
        "history": history,
        "test_used": False,
    }
    output = ROOT / f"results/v10_seed{args.seed}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
