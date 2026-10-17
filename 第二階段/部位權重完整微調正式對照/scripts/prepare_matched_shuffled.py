from __future__ import annotations

import hashlib
import importlib.util
import json
import random
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader
from torchvision.models import ConvNeXt_Tiny_Weights, convnext_tiny


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parents[1]


def load_densepose_training_module():
    path = PROJECT_ROOT / "部位預測階段/DensePose_部位預訓練/scripts/train_overnight.py"
    spec = importlib.util.spec_from_file_location("densepose_train_overnight", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def main():
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    cfg = config["negative_control_pretraining"]
    module = load_densepose_training_module()
    manifest = (ROOT / cfg["manifest"]).resolve()
    images = (ROOT / cfg["images"]).resolve()
    output = (ROOT / cfg["output"]).resolve()
    provenance_path = (ROOT / cfg["provenance"]).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    seed = cfg["seed"]
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_set = module.PartDataset(manifest, images, "train", cfg["image_size"], cfg["max_train_samples"],
                                   cfg["sample_seed"], "shuffled", seed)
    val_set = module.PartDataset(manifest, images, "val", cfg["image_size"], cfg["max_val_samples"],
                                 cfg["sample_seed"], "shuffled", seed)
    loader_args = {"batch_size": cfg["batch_size"], "num_workers": 0, "pin_memory": device.type == "cuda"}
    train_loader = DataLoader(train_set, shuffle=True, generator=torch.Generator().manual_seed(seed), **loader_args)
    val_loader = DataLoader(val_set, shuffle=False, **loader_args)

    model = convnext_tiny(weights=ConvNeXt_Tiny_Weights.DEFAULT)
    model.classifier[2] = nn.Linear(model.classifier[2].in_features, len(module.CLASSES))
    model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=cfg["learning_rate"], weight_decay=cfg["weight_decay"])
    criterion = nn.CrossEntropyLoss()
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    history, start_epoch = [], 0
    if output.exists():
        state = torch.load(output, map_location=device, weights_only=False)
        if state.get("label_mode") == "shuffled" and state.get("checkpoint_selection") == "final_epoch":
            model.load_state_dict(state["model"])
            if "optimizer" in state: optimizer.load_state_dict(state["optimizer"])
            if "scaler" in state: scaler.load_state_dict(state["scaler"])
            history = state.get("history", [])
            start_epoch = int(state.get("epoch", 0))
    if start_epoch >= cfg["epochs"] and provenance_path.exists():
        print("相同訓練量的打亂標籤負對照已完成。", flush=True)
        return

    print(f"準備正式負對照：device={device} train={len(train_set)} val={len(val_set)} epoch={start_epoch + 1}..{cfg['epochs']}", flush=True)
    for epoch_index in range(start_epoch, cfg["epochs"]):
        train_metrics = module.run_epoch(model, train_loader, criterion, device, optimizer, scaler)
        val_metrics = module.run_epoch(model, val_loader, criterion, device)
        history.append({"epoch": epoch_index + 1, "train": train_metrics, "validation": val_metrics})
        torch.save({
            "model": model.state_dict(), "optimizer": optimizer.state_dict(), "scaler": scaler.state_dict(),
            "classes": module.CLASSES, "seed": seed, "epoch": epoch_index + 1,
            "label_mode": "shuffled", "checkpoint_selection": "final_epoch", "history": history,
        }, output)
        print(f"負對照 epoch={epoch_index + 1}/{cfg['epochs']} val_BA={val_metrics['balanced_accuracy']:.4f}", flush=True)

    digest = sha256(output)
    provenance = {
        "asset": str(output), "sha256": digest, "architecture": "convnext_tiny_5_class",
        "initialization": "ImageNet", "label_mode": "shuffled", "seed": seed,
        "sample_seed": cfg["sample_seed"], "epochs_completed": cfg["epochs"],
        "checkpoint_selection": "final_epoch", "train_samples": len(train_set),
        "val_samples": len(val_set), "image_size": cfg["image_size"],
        "batch_size": cfg["batch_size"], "learning_rate": cfg["learning_rate"],
        "weight_decay": cfg["weight_decay"], "test_used": False, "complete": True,
    }
    provenance_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"正式負對照資產完成：{output}\nSHA-256={digest}", flush=True)


if __name__ == "__main__":
    main()
