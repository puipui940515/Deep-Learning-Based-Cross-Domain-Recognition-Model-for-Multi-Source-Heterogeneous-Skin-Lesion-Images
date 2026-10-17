from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader

STAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STAGE_ROOT / "src"))
from stage1.data import HAM10000ManifestDataset, build_transform
from stage1.engine import append_experiment_log, run_epoch, save_json, seed_everything
from stage1.models import build_model, count_parameters


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", choices=["v1", "v2", "v3", "v4"], required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--dataset-root", type=Path)
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    config = json.loads((STAGE_ROOT / "config/stage1.json").read_text(encoding="utf-8"))
    if args.seed not in config["seeds"]:
        raise SystemExit(f"seed 必須為固定集合 {config['seeds']}")
    spec = config["versions"][args.version]
    dataset_root = args.dataset_root or (STAGE_ROOT / config["dataset_root"]).resolve()
    manifest = STAGE_ROOT / config["split_manifest"]
    gate_path = STAGE_ROOT.parent / "驗證/reports/validation_gate.json"
    if not gate_path.exists():
        raise SystemExit("請先執行根目錄的 驗證/run_all.py")
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    if not gate.get("passed", False):
        raise SystemExit("驗證閘門未通過，禁止開始實驗")

    seed_everything(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_set = HAM10000ManifestDataset(manifest, dataset_root, "train", build_transform(spec["image_size"], True, spec["augmentation"]))
    val_set = HAM10000ManifestDataset(manifest, dataset_root, "val", build_transform(spec["image_size"], False, False))
    loader_args = {"batch_size": args.batch_size or config["batch_size"], "num_workers": config["num_workers"], "pin_memory": device.type == "cuda"}
    generator = torch.Generator().manual_seed(args.seed)
    train_loader = DataLoader(train_set, shuffle=True, generator=generator, **loader_args)
    val_loader = DataLoader(val_set, shuffle=False, **loader_args)

    model = build_model(spec["model"], spec["image_size"], config["num_classes"]).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=config["learning_rate"], weight_decay=config["weight_decay"])
    criterion = nn.CrossEntropyLoss()
    checkpoint = STAGE_ROOT / f"checkpoints/{args.version}_seed{args.seed}.pt"
    start_epoch, best_score, patience = 0, -1.0, 0
    history = []
    if args.resume and checkpoint.exists():
        state = torch.load(checkpoint, map_location=device, weights_only=False)
        model.load_state_dict(state["model"]); optimizer.load_state_dict(state["optimizer"])
        start_epoch = state["epoch"] + 1; best_score = state["best_score"]
        history = state.get("history", [])

    epochs = args.epochs or config["epochs"]
    best_train, best_val = None, None
    for epoch in range(start_epoch, epochs):
        train_metrics = run_epoch(model, train_loader, criterion, device, optimizer)
        val_metrics = run_epoch(model, val_loader, criterion, device)
        history.append({"epoch": epoch + 1, "train": train_metrics, "val": val_metrics})
        score = val_metrics["balanced_accuracy"]
        if score > best_score:
            best_score, patience, best_train, best_val = score, 0, train_metrics, val_metrics
            checkpoint.parent.mkdir(parents=True, exist_ok=True)
            torch.save({"epoch": epoch, "model": model.state_dict(), "optimizer": optimizer.state_dict(),
                        "best_score": best_score, "history": history, "version": args.version, "seed": args.seed}, checkpoint)
        else:
            patience += 1
        print(f"{args.version} seed={args.seed} epoch={epoch+1} train_BA={train_metrics['balanced_accuracy']:.4f} val_BA={score:.4f}")
        if patience >= config["early_stopping_patience"]:
            break

    if best_train is None:
        state = torch.load(checkpoint, map_location="cpu", weights_only=False)
        best = max(state["history"], key=lambda item: item["val"]["balanced_accuracy"])
        best_train, best_val, history = best["train"], best["val"], state["history"]
    result = {"version": args.version, "seed": args.seed, "spec": spec, "parameters": count_parameters(model),
              "device": str(device), "best_train": best_train, "best_validation": best_val, "history": history}
    save_json(STAGE_ROOT / f"results/{args.version}_seed{args.seed}.json", result)
    append_experiment_log(STAGE_ROOT / "results/experiment_log.csv", {
        "version": args.version, "seed": args.seed, "model": spec["model"], "image_size": spec["image_size"],
        "augmentation": spec["augmentation"], "parameters": result["parameters"], "epochs_completed": len(history),
        "train_balanced_accuracy": best_train["balanced_accuracy"], "val_balanced_accuracy": best_val["balanced_accuracy"],
        "train_val_gap": best_train["balanced_accuracy"] - best_val["balanced_accuracy"],
        "val_macro_f1": best_val["macro_f1"], "val_ece": best_val["ece"],
        "best_checkpoint": str(checkpoint.relative_to(STAGE_ROOT)), "notes": "test split 未使用",
    })


if __name__ == "__main__":
    main()

