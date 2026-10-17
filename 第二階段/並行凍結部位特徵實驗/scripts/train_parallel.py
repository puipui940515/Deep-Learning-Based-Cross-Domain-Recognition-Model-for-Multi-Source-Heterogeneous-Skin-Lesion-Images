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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def feature_vector(model, images):
    values = model.features(images)
    values = model.avgpool(values)
    values = model.classifier[0](values)
    return model.classifier[1](values)


class ParallelFrozenTeacher(nn.Module):
    def __init__(self, student, teacher, num_classes: int, head_seed: int):
        super().__init__()
        self.student = student
        self.teacher = teacher
        for parameter in self.teacher.parameters():
            parameter.requires_grad = False
        torch.manual_seed(head_seed)
        self.fusion_head = nn.Linear(768 * 2, num_classes)
        self.register_buffer("imagenet_mean", torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1))
        self.register_buffer("imagenet_std", torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1))
        self.teacher.eval()

    def train(self, mode: bool = True):
        super().train(mode)
        self.teacher.eval()
        return self

    def forward(self, stage2_images):
        student_features = feature_vector(self.student, stage2_images)
        pixels_01 = stage2_images * 0.5 + 0.5
        teacher_images = (pixels_01 - self.imagenet_mean) / self.imagenet_std
        with torch.no_grad():
            teacher_features = feature_vector(self.teacher, teacher_images)
        return self.fusion_head(torch.cat([student_features, teacher_features], dim=1))


def load_teacher(condition: str, config: dict):
    asset_info = None
    if condition == "imagenet_teacher":
        return convnext_tiny(weights=ConvNeXt_Tiny_Weights.DEFAULT), asset_info
    asset_info = config["assets"][condition]
    path = (ROOT / asset_info["path"]).resolve()
    actual = sha256(path)
    if actual != asset_info["sha256"]:
        raise RuntimeError(f"Asset checksum mismatch: {path}\n{actual}")
    teacher = convnext_tiny(weights=None)
    teacher.classifier[2] = nn.Linear(teacher.classifier[2].in_features, 5)
    state = torch.load(path, map_location="cpu", weights_only=False)
    teacher.load_state_dict(state["model"], strict=True)
    return teacher, asset_info


def parameter_groups(model, base_lr: float, weight_decay: float, decay: float):
    max_depth = 9
    groups = {}
    for name, parameter in model.named_parameters():
        if not parameter.requires_grad:
            continue
        if name.startswith("student.features."):
            try:
                depth = int(name.split(".")[2]) + 1
            except (ValueError, IndexError):
                depth = 1
        else:
            depth = max_depth
        learning_rate = base_lr * decay ** (max_depth - depth)
        no_decay = parameter.ndim == 1 or name.endswith(".bias")
        key = (depth, no_decay)
        groups.setdefault(key, {"params": [], "lr": learning_rate, "weight_decay": 0.0 if no_decay else weight_decay})["params"].append(parameter)
    return list(groups.values())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--max-train-samples", type=int)
    parser.add_argument("--max-val-samples", type=int)
    parser.add_argument("--output-root", type=Path)
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
    sample_generator = torch.Generator().manual_seed(20260824)
    if args.max_train_samples and args.max_train_samples < len(train_set):
        train_set = Subset(train_set, torch.randperm(len(train_set), generator=sample_generator)[:args.max_train_samples].tolist())
    if args.max_val_samples and args.max_val_samples < len(val_set):
        val_set = Subset(val_set, torch.randperm(len(val_set), generator=sample_generator)[:args.max_val_samples].tolist())
    loader_args = {"batch_size": config["batch_size"], "num_workers": config["num_workers"], "pin_memory": device.type == "cuda"}
    train_loader = DataLoader(train_set, shuffle=True, generator=torch.Generator().manual_seed(args.seed), **loader_args)
    val_loader = DataLoader(val_set, shuffle=False, **loader_args)

    torch.manual_seed(args.seed + 100000)
    student = convnext_tiny(weights=ConvNeXt_Tiny_Weights.DEFAULT)
    teacher, asset_info = load_teacher(args.condition, config)
    model = ParallelFrozenTeacher(student, teacher, config["num_classes"], args.seed + 700000).to(device)
    teacher_trainable = sum(parameter.numel() for parameter in model.teacher.parameters() if parameter.requires_grad)
    if teacher_trainable != 0:
        raise RuntimeError(f"Teacher is not frozen: {teacher_trainable} trainable parameters")
    trainable_parameters = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    optimizer = torch.optim.AdamW(parameter_groups(model, config["learning_rate"], config["weight_decay"], config["layer_decay"]))
    criterion = nn.CrossEntropyLoss().to(device)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    output_root = (args.output_root or (ROOT / "results")).resolve()
    output_dir = output_root / args.condition / f"seed{args.seed}"
    output_dir.mkdir(parents=True, exist_ok=True)
    epochs = args.epochs or config["epochs"]
    history, best_score, best_record = [], -1.0, None
    print(f"condition={args.condition} seed={args.seed} device={device} train={len(train_set)} val={len(val_set)} trainable={trainable_parameters} teacher_trainable={teacher_trainable}", flush=True)
    for epoch in range(epochs):
        train_metrics = run_epoch(model, train_loader, criterion, device, optimizer, scaler, config["gradient_accumulation"])
        val_metrics = run_epoch(model, val_loader, criterion, device)
        record = {"epoch": epoch + 1, "train": train_metrics, "val": val_metrics}
        history.append(record)
        if val_metrics["balanced_accuracy"] > best_score:
            best_score, best_record = val_metrics["balanced_accuracy"], record
            torch.save({"model": model.state_dict(), "condition": args.condition, "seed": args.seed, "epoch": epoch + 1, "teacher_frozen": True}, output_dir / "best.pt")
        print(f"epoch={epoch+1}/{epochs} train_BA={train_metrics['balanced_accuracy']:.4f} val_BA={val_metrics['balanced_accuracy']:.4f} val_acc={val_metrics['accuracy']:.4f}", flush=True)

    result = {
        "comparison_id": config["comparison_id"], "condition": args.condition, "seed": args.seed,
        "architecture": "parallel_convnext_tiny_student_plus_frozen_convnext_tiny_teacher",
        "student_initialization": "ImageNet", "teacher_feature_dimension": 768,
        "student_feature_dimension": 768, "fusion_dimension": 1536,
        "fusion_head": "linear_1536_to_7", "image_size": config["image_size"],
        "batch_size": config["batch_size"], "gradient_accumulation": config["gradient_accumulation"],
        "loss": "cross_entropy", "teacher_frozen": True, "teacher_trainable_parameters": 0,
        "trainable_parameters": trainable_parameters,
        "total_parameters": sum(parameter.numel() for parameter in model.parameters()),
        "teacher_input_normalization": "ImageNet", "student_input_normalization": "stage2_mean_std_0.5",
        "asset": asset_info, "train_samples": len(train_set), "val_samples": len(val_set),
        "best": best_record, "history": history, "test_used": False,
        "teacher_required_at_inference": True,
        "direct_comparison_valid": args.condition != "densepose_shuffled_teacher",
        "notes": "Shuffled teacher is exploratory because saved pretraining epoch differs from true teacher." if args.condition == "densepose_shuffled_teacher" else "Controlled parallel frozen-teacher feature fusion."
    }
    (output_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
