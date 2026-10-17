from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader


EXP_ROOT = Path(__file__).resolve().parents[1]
STAGE_ROOT = EXP_ROOT.parent
PROJECT_ROOT = STAGE_ROOT.parent
sys.path.insert(0, str(STAGE_ROOT / "src"))
sys.path.insert(0, str(EXP_ROOT / "vendor"))

from noisefilter import FilterChain, IlluminationPerturb
from stage1.data import HAM10000ManifestDataset, build_transform
from stage1.engine import run_epoch, seed_everything
from stage1.metrics import metrics_from_logits
from stage1.models import build_model, count_parameters


class NormalizedFilterModel(nn.Module):
    def __init__(self, backbone: nn.Module, alpha: list[float]) -> None:
        super().__init__()
        self.filter = FilterChain(alpha_init=alpha, learn_alpha=False)
        self.backbone = backbone

    def calibrate(self, loader: DataLoader) -> dict:
        pixel_batches = ((images + 1.0) * 0.5 for images, _, _ in loader)
        result = self.filter.stages[0].calibrate(pixel_batches)
        for parameter in self.filter.parameters():
            parameter.requires_grad_(False)
        return result

    def apply_calibration(self, result: dict) -> None:
        stage = self.filter.stages[0]
        s = min(max(float(result["measured_std"]), stage.lo + 1e-3), stage.hi - 1e-3)
        m = min(max(float(result["measured_log_mean"]), stage.mlo + 1e-3), stage.mhi - 1e-3)
        with torch.no_grad():
            t = (s - stage.lo) / (stage.hi - stage.lo)
            u = (m - stage.mlo) / (stage.mhi - stage.mlo)
            stage.raw_std.copy_(torch.tensor(math.log(t / (1.0 - t))))
            stage.raw_mean.copy_(torch.tensor(math.log(u / (1.0 - u))))
        for parameter in self.filter.parameters():
            parameter.requires_grad_(False)

    def forward(self, normalized: torch.Tensor) -> torch.Tensor:
        pixels = ((normalized + 1.0) * 0.5).clamp(0.0, 1.0)
        filtered = self.filter(pixels)
        return self.backbone(filtered * 2.0 - 1.0)


@torch.no_grad()
def evaluate_perturbed(model, loader, device, seed: int) -> dict:
    model.eval()
    perturb = IlluminationPerturb().to(device)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    logits_all, targets_all = [], []
    for images, targets, _ in loader:
        pixels = ((images.to(device) + 1.0) * 0.5).clamp(0.0, 1.0)
        changed = perturb(pixels) * 2.0 - 1.0
        logits_all.append(model(changed).detach().cpu().numpy())
        targets_all.append(targets.numpy())
    return metrics_from_logits(np.concatenate(logits_all), np.concatenate(targets_all))


def load_baseline(seed: int, image_size: int, device) -> nn.Module:
    model = build_model("mlp", image_size, 7).to(device)
    state = torch.load(STAGE_ROOT / f"checkpoints/v1_seed{seed}.pt", map_location=device, weights_only=False)
    model.load_state_dict(state["model"])
    return model


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--epochs", type=int)
    args = parser.parse_args()
    config = json.loads((EXP_ROOT / "config.json").read_text(encoding="utf-8"))
    if args.seed not in config["seeds"]:
        raise SystemExit(f"seed 必須為 {config['seeds']}")
    gate = json.loads((PROJECT_ROOT / "驗證/reports/validation_gate.json").read_text(encoding="utf-8"))
    if not gate.get("passed", False):
        raise SystemExit("根目錄驗證閘門未通過")

    seed_everything(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    image_size = 64
    dataset_root = PROJECT_ROOT / "Dataset/HAM10000"
    manifest = STAGE_ROOT / "data/fixed_split.csv"
    train_set = HAM10000ManifestDataset(manifest, dataset_root, "train", build_transform(image_size, True, False))
    calibration_set = HAM10000ManifestDataset(manifest, dataset_root, "train", build_transform(image_size, False, False))
    val_set = HAM10000ManifestDataset(manifest, dataset_root, "val", build_transform(image_size, False, False))
    common = {"batch_size": config["batch_size"], "num_workers": 2, "pin_memory": device.type == "cuda"}
    train_loader = DataLoader(train_set, shuffle=True, generator=torch.Generator().manual_seed(args.seed), **common)
    calibration_loader = DataLoader(calibration_set, shuffle=False, **common)
    val_loader = DataLoader(val_set, shuffle=False, **common)

    model = NormalizedFilterModel(build_model("mlp", image_size, 7), config["alpha"])
    calibration_cache = EXP_ROOT / "results/calibration.json"
    seed17_result = EXP_ROOT / f"results/{config['experiment_id']}_seed17.json"
    if calibration_cache.exists():
        calibration = json.loads(calibration_cache.read_text(encoding="utf-8"))
        model.apply_calibration(calibration)
        print(f"reused calibration: {calibration}", flush=True)
    elif seed17_result.exists():
        calibration = json.loads(seed17_result.read_text(encoding="utf-8"))["calibration"]
        model.apply_calibration(calibration)
        calibration_cache.parent.mkdir(parents=True, exist_ok=True)
        calibration_cache.write_text(json.dumps(calibration, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"cached seed17 calibration: {calibration}", flush=True)
    else:
        calibration = model.calibrate(calibration_loader)
        calibration_cache.parent.mkdir(parents=True, exist_ok=True)
        calibration_cache.write_text(json.dumps(calibration, ensure_ascii=False, indent=2), encoding="utf-8")
    model = model.to(device)
    optimizer = torch.optim.AdamW(
        (p for p in model.parameters() if p.requires_grad),
        lr=config["learning_rate"],
        weight_decay=config["weight_decay"],
    )
    criterion = nn.CrossEntropyLoss()
    checkpoint = EXP_ROOT / f"checkpoints/{config['experiment_id']}_seed{args.seed}.pt"
    history, best_score, patience, best_record = [], -1.0, 0, None
    for epoch in range(args.epochs or config["epochs"]):
        train_metrics = run_epoch(model, train_loader, criterion, device, optimizer)
        val_metrics = run_epoch(model, val_loader, criterion, device)
        record = {"epoch": epoch + 1, "train": train_metrics, "val": val_metrics}
        history.append(record)
        score = val_metrics["balanced_accuracy"]
        if score > best_score:
            best_score, patience, best_record = score, 0, record
            checkpoint.parent.mkdir(parents=True, exist_ok=True)
            torch.save({"epoch": epoch, "model": model.state_dict(), "optimizer": optimizer.state_dict(),
                        "best_score": score, "history": history, "calibration": calibration,
                        "config": config, "seed": args.seed}, checkpoint)
        else:
            patience += 1
        print(f"stage1 noisefilter seed={args.seed} epoch={epoch+1} train_BA={train_metrics['balanced_accuracy']:.4f} val_BA={score:.4f}", flush=True)
        if patience >= config["early_stopping_patience"]:
            break

    state = torch.load(checkpoint, map_location=device, weights_only=False)
    model.load_state_dict(state["model"])
    filtered_clean = run_epoch(model, val_loader, criterion, device)
    filtered_perturbed = evaluate_perturbed(model, val_loader, device, config["perturbation_eval_seed"])
    baseline = load_baseline(args.seed, image_size, device)
    baseline_clean = run_epoch(baseline, val_loader, criterion, device)
    baseline_perturbed = evaluate_perturbed(baseline, val_loader, device, config["perturbation_eval_seed"])

    result = {
        "experiment_id": config["experiment_id"], "seed": args.seed, "device": str(device),
        "baseline_version": "v1", "mounted": config["mounted"], "not_mounted": config["not_mounted"],
        "alpha": config["alpha"], "calibration": calibration,
        "trainable_parameters": count_parameters(model), "epochs_completed": len(history),
        "best_epoch": best_record["epoch"], "history": history, "test_used": False,
        "evaluation": {
            "baseline_clean": baseline_clean, "filtered_clean": filtered_clean,
            "baseline_perturbed": baseline_perturbed, "filtered_perturbed": filtered_perturbed,
            "clean_balanced_accuracy_delta": filtered_clean["balanced_accuracy"] - baseline_clean["balanced_accuracy"],
            "perturbed_balanced_accuracy_delta": filtered_perturbed["balanced_accuracy"] - baseline_perturbed["balanced_accuracy"],
            "baseline_robustness_drop": baseline_clean["balanced_accuracy"] - baseline_perturbed["balanced_accuracy"],
            "filtered_robustness_drop": filtered_clean["balanced_accuracy"] - filtered_perturbed["balanced_accuracy"],
        },
        "checkpoint": str(checkpoint.relative_to(EXP_ROOT)),
    }
    output = EXP_ROOT / f"results/{config['experiment_id']}_seed{args.seed}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["evaluation"], ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
