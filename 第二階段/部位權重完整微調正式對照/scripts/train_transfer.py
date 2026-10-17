from __future__ import annotations

import argparse
import hashlib
import json
import sys
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
from stage2.models import parameter_groups_with_layer_decay


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def validate_asset(condition: str, config: dict) -> tuple[Path, dict]:
    info = config["assets"][condition]
    path = (ROOT / info["path"]).resolve()
    if not path.exists():
        raise FileNotFoundError(f"找不到初始化資產：{path}")
    actual_hash = sha256(path)
    if condition == "densepose_true_init":
        if actual_hash != info["sha256"]:
            raise RuntimeError(f"真實部位資產 SHA-256 不符：{actual_hash}")
    else:
        provenance_path = (ROOT / info["provenance"]).resolve()
        if not provenance_path.exists():
            raise FileNotFoundError("缺少同訓練量負對照 provenance，請先執行 prepare_matched_shuffled.py")
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        required = {
            "label_mode": info["label_mode"],
            "epochs_completed": info["pretraining_epochs"],
            "checkpoint_selection": info["checkpoint_selection"],
            "complete": True,
        }
        for key, expected in required.items():
            if provenance.get(key) != expected:
                raise RuntimeError(f"負對照 provenance 不合格：{key}={provenance.get(key)!r}，預期 {expected!r}")
        if provenance.get("sha256", "").upper() != actual_hash:
            raise RuntimeError("負對照資產與 provenance 的 SHA-256 不一致")
    return path, {**info, "actual_sha256": actual_hash}


def build_transfer_model(condition: str, config: dict, head_seed: int):
    asset_info = None
    if condition == "imagenet_init":
        model = convnext_tiny(weights=ConvNeXt_Tiny_Weights.DEFAULT)
    else:
        asset_path, asset_info = validate_asset(condition, config)
        model = convnext_tiny(weights=None)
        model.classifier[2] = nn.Linear(model.classifier[2].in_features, 5)
        state = torch.load(asset_path, map_location="cpu", weights_only=False)
        model.load_state_dict(state["model"], strict=True)
    torch.manual_seed(head_seed)
    model.classifier[2] = nn.Linear(model.classifier[2].in_features, config["num_classes"])
    for parameter in model.parameters():
        parameter.requires_grad = True
    return model, asset_info


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--max-train-samples", type=int)
    parser.add_argument("--max-val-samples", type=int)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    if args.condition not in config["conditions"]:
        raise SystemExit(f"condition 必須是 {config['conditions']}")
    if args.seed not in config["seeds"]:
        raise SystemExit(f"seed 必須是 {config['seeds']}")
    gate = PROJECT_ROOT / "驗證/reports/validation_gate.json"
    if not gate.exists() or not json.loads(gate.read_text(encoding="utf-8")).get("passed", False):
        raise SystemExit("根目錄驗證閘門未通過")

    seed_everything(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    manifest = (ROOT / config["split_manifest"]).resolve()
    dataset_root = (ROOT / config["dataset_root"]).resolve()
    train_set = ManifestDataset(manifest, dataset_root, "train", build_transform(config["image_size"], True))
    val_set = ManifestDataset(manifest, dataset_root, "val", build_transform(config["image_size"], False))
    subset_generator = torch.Generator().manual_seed(20260824)
    if args.max_train_samples and args.max_train_samples < len(train_set):
        train_set = Subset(train_set, torch.randperm(len(train_set), generator=subset_generator)[:args.max_train_samples].tolist())
    if args.max_val_samples and args.max_val_samples < len(val_set):
        val_set = Subset(val_set, torch.randperm(len(val_set), generator=subset_generator)[:args.max_val_samples].tolist())
    loader_args = {
        "batch_size": config["batch_size"],
        "num_workers": config["num_workers"],
        "pin_memory": device.type == "cuda",
    }
    train_loader = DataLoader(train_set, shuffle=True, generator=torch.Generator().manual_seed(args.seed), **loader_args)
    val_loader = DataLoader(val_set, shuffle=False, **loader_args)

    model, asset_info = build_transfer_model(args.condition, config, args.seed + 700000)
    model.to(device)
    trainable_parameters = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    total_parameters = sum(parameter.numel() for parameter in model.parameters())
    if trainable_parameters != total_parameters:
        raise RuntimeError("正式完整微調實驗不允許凍結參數")
    optimizer = torch.optim.AdamW(parameter_groups_with_layer_decay(
        model, config["learning_rate"], config["weight_decay"], config["layer_decay"]
    ))
    criterion = nn.CrossEntropyLoss().to(device)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")

    output_root = (args.output_root or (ROOT / "results")).resolve()
    output_dir = output_root / args.condition / f"seed{args.seed}"
    output_dir.mkdir(parents=True, exist_ok=True)
    last_checkpoint = output_dir / "last.pt"
    best_checkpoint = output_dir / "best.pt"
    history, best_score, best_record, patience, start_epoch = [], -1.0, None, 0, 0
    if args.resume and last_checkpoint.exists():
        state = torch.load(last_checkpoint, map_location=device, weights_only=False)
        model.load_state_dict(state["model"])
        optimizer.load_state_dict(state["optimizer"])
        scaler.load_state_dict(state["scaler"])
        history = state["history"]
        best_score = state["best_score"]
        best_record = state["best_record"]
        patience = state["patience"]
        start_epoch = state["epoch"]
        print(f"續訓：condition={args.condition} seed={args.seed}，從 epoch {start_epoch + 1} 開始", flush=True)

    epochs = args.epochs or config["epochs"]
    print(
        f"condition={args.condition} seed={args.seed} device={device} "
        f"train={len(train_set)} val={len(val_set)} trainable={trainable_parameters}/{total_parameters}",
        flush=True,
    )
    for epoch_index in range(start_epoch, epochs):
        train_metrics = run_epoch(model, train_loader, criterion, device, optimizer, scaler, config["gradient_accumulation"])
        val_metrics = run_epoch(model, val_loader, criterion, device)
        record = {"epoch": epoch_index + 1, "train": train_metrics, "val": val_metrics}
        history.append(record)
        if val_metrics["balanced_accuracy"] > best_score:
            best_score, best_record, patience = val_metrics["balanced_accuracy"], record, 0
            torch.save({"model": model.state_dict(), "condition": args.condition, "seed": args.seed,
                        "epoch": epoch_index + 1, "full_finetune": True}, best_checkpoint)
        else:
            patience += 1
        torch.save({
            "model": model.state_dict(), "optimizer": optimizer.state_dict(), "scaler": scaler.state_dict(),
            "history": history, "best_score": best_score, "best_record": best_record,
            "patience": patience, "epoch": epoch_index + 1,
        }, last_checkpoint)
        print(
            f"epoch={epoch_index + 1}/{epochs} train_BA={train_metrics['balanced_accuracy']:.4f} "
            f"val_BA={val_metrics['balanced_accuracy']:.4f} val_F1={val_metrics['macro_f1']:.4f} "
            f"val_acc={val_metrics['accuracy']:.4f} val_loss={val_metrics['loss']:.4f}",
            flush=True,
        )
        if patience >= config["early_stopping_patience"]:
            print(f"提前停止：連續 {patience} 個 epoch 未改善", flush=True)
            break

    result = {
        "comparison_id": config["comparison_id"], "condition": args.condition, "seed": args.seed,
        "architecture": "single_convnext_tiny_7_class", "initialization": args.condition,
        "initialization_asset": asset_info, "classifier_head_seed": args.seed + 700000,
        "full_backbone_finetune": True, "trainable_parameters": trainable_parameters,
        "total_parameters": total_parameters, "image_size": config["image_size"],
        "batch_size": config["batch_size"], "gradient_accumulation": config["gradient_accumulation"],
        "loss": "cross_entropy", "optimizer": "AdamW_with_layerwise_lr_decay",
        "train_samples": len(train_set), "val_samples": len(val_set),
        "best": best_record, "history": history, "test_used": False,
    }
    (output_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
