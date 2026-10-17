from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler


EXPERIMENT = Path(__file__).resolve().parents[1]
GENERAL_ROOT = EXPERIMENT.parent
PROJECT = GENERAL_ROOT.parent
sys.path.insert(0, str(EXPERIMENT / "src"))
sys.path.insert(0, str(GENERAL_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT / "第二階段" / "src"))

from explicit_features import (
    AUDIT_ONLY_FEATURE_NAMES,
    FEATURE_NAMES,
    FEATURE_VERSION,
    MODEL_FEATURE_NAMES,
    FeatureStandardizer,
)
from fusion_model import build_experiment_model
from stage2.models import parameter_groups_with_layer_decay
from train_regularized import build_transform, read_csv, sample_weights, stratified_limit, supported_source_metrics

try:
    from tqdm.auto import tqdm
except ImportError:  # pragma: no cover
    def tqdm(iterable, **_kwargs):
        return iterable


def read_feature_cache(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise RuntimeError(f"特徵快取是空的：{path}")
    missing = set(FEATURE_NAMES) - set(rows[0])
    if missing:
        raise RuntimeError(f"特徵快取缺少欄位：{sorted(missing)}")
    versions = {row["feature_version"] for row in rows}
    if versions != {FEATURE_VERSION}:
        raise RuntimeError(f"特徵版本不一致：{sorted(versions)}")
    result = {row["record_id"]: row for row in rows}
    if len(result) != len(rows):
        raise RuntimeError("特徵快取有重複 record_id")
    return result


def vector(feature_row: dict[str, str]) -> np.ndarray:
    values = np.asarray([float(feature_row[name]) for name in MODEL_FEATURE_NAMES], dtype=np.float32)
    if not np.isfinite(values).all():
        raise RuntimeError(f'特徵包含非有限值：{feature_row["record_id"]}')
    return values


def join_manifest(
    manifest_rows: list[dict[str, str]],
    cache: dict[str, dict[str, str]],
    allow_partial: bool,
) -> list[dict[str, str]]:
    eligible = [row for row in manifest_rows if row["training_eligible"].lower() == "true"]
    missing = [row["record_id"] for row in eligible if row["record_id"] not in cache]
    if missing and not allow_partial:
        raise RuntimeError(
            f"正式模式要求完整特徵快取，目前少 {len(missing)} 筆；"
            "先執行 extract_features.py，煙霧測試才可使用 --allow-partial-cache。"
        )
    joined = [row for row in eligible if row["record_id"] in cache]
    for row in joined:
        cached = cache[row["record_id"]]
        expected = (row["source"], row["split"], row["label"])
        observed = (cached["source"], cached["split"], cached["label"])
        if expected != observed:
            raise RuntimeError(f'特徵快取 metadata 不一致：{row["record_id"]}')
    return joined


class FusionDataset(Dataset):
    def __init__(
        self,
        rows: list[dict[str, str]],
        cache: dict[str, dict[str, str]],
        standardizer: FeatureStandardizer,
        image_size: int,
        train: bool,
        load_images: bool,
    ):
        self.rows = rows
        self.cache = cache
        self.standardizer = standardizer
        self.transform = build_transform(image_size, train)
        self.load_images = load_images

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int):
        row = self.rows[index]
        features = torch.from_numpy(self.standardizer.transform(vector(self.cache[row["record_id"]])))
        if self.load_images:
            with Image.open(PROJECT / row["image_path"]) as image:
                image_tensor = self.transform(image.convert("RGB"))
        else:
            image_tensor = torch.empty(0, dtype=torch.float32)
        return image_tensor, features, int(row["label"]), row["source"]


@torch.inference_mode()
def evaluate(model, loader, criterion, device, supported: list[int], description: str) -> dict:
    model.eval()
    total_loss, logits_all, targets_all = 0.0, [], []
    for images, features, targets, _sources in tqdm(loader, desc=description, leave=False, unit="batch"):
        images = images.to(device)
        features = features.to(device)
        targets = targets.to(device)
        with torch.amp.autocast(device_type=device.type, enabled=device.type == "cuda"):
            logits = model(images, features)
            loss = criterion(logits, targets)
        total_loss += loss.item() * targets.size(0)
        logits_all.append(logits.float().cpu().numpy())
        targets_all.append(targets.cpu().numpy())
    metrics = supported_source_metrics(np.concatenate(logits_all), np.concatenate(targets_all), supported)
    metrics["loss"] = total_loss / len(loader.dataset)
    metrics["samples"] = len(loader.dataset)
    return metrics


def train_epoch(model, loader, criterion, optimizer, scaler, device, mixup_alpha: float, clip: float) -> float:
    model.train()
    total_loss, total_seen = 0.0, 0
    for images, features, targets, _sources in tqdm(loader, desc="訓練", leave=False, unit="batch"):
        images = images.to(device)
        features = features.to(device)
        targets = targets.to(device)
        optimizer.zero_grad(set_to_none=True)
        if mixup_alpha > 0:
            lam = float(np.random.beta(mixup_alpha, mixup_alpha))
            permutation = torch.randperm(targets.size(0), device=device)
            mixed_images = lam * images + (1.0 - lam) * images[permutation]
            mixed_features = lam * features + (1.0 - lam) * features[permutation]
            target_b = targets[permutation]
        else:
            lam, mixed_images, mixed_features, target_b = 1.0, images, features, targets
        with torch.amp.autocast(device_type=device.type, enabled=device.type == "cuda"):
            logits = model(mixed_images, mixed_features)
            loss = lam * criterion(logits, targets) + (1.0 - lam) * criterion(logits, target_b)
        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), clip)
        scaler.step(optimizer)
        scaler.update()
        total_loss += loss.item() * targets.size(0)
        total_seen += targets.size(0)
    return total_loss / max(total_seen, 1)


def optimizer_for(model, mode: str, config: dict, learning_rate: float):
    weight_decay = config["weight_decay"]
    if mode == "feature_only":
        return torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
    groups = parameter_groups_with_layer_decay(
        model.image_backbone,
        learning_rate,
        weight_decay,
        config["layer_decay"],
    )
    groups.append({
        "params": list(model.explicit_branch.parameters()) + list(model.fusion_head.parameters()),
        "lr": learning_rate,
        "weight_decay": weight_decay,
    })
    return torch.optim.AdamW(groups)


def main() -> None:
    parser = argparse.ArgumentParser(description="顯式影像特徵小模型／ConvNeXt 融合實驗")
    parser.add_argument("--mode", choices=["feature_only", "fusion"], required=True)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--learning-rate", type=float)
    parser.add_argument("--features", type=Path, default=EXPERIMENT / "data" / "explicit_features_v1.csv")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--max-train-samples", type=int, help="只供煙霧測試")
    parser.add_argument("--max-val-samples-per-source", type=int, help="只供煙霧測試")
    parser.add_argument("--allow-partial-cache", action="store_true", help="只供煙霧測試")
    parser.add_argument("--no-pretrained", action="store_true", help="只供離線結構測試")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    config = json.loads((GENERAL_ROOT / "config.json").read_text(encoding="utf-8-sig"))
    train_config = dict(config["training"])
    epochs = args.epochs or (30 if args.mode == "feature_only" else train_config["epochs"])
    batch_size = args.batch_size or (256 if args.mode == "feature_only" else train_config["batch_size"])
    learning_rate = args.learning_rate or (1e-3 if args.mode == "feature_only" else train_config["learning_rate"])

    manifest = read_csv(GENERAL_ROOT / "data" / "unified_manifest_v1.csv")
    cache = read_feature_cache(args.features)
    rows = join_manifest(manifest, cache, args.allow_partial_cache)
    train_rows = stratified_limit([row for row in rows if row["split"] == "train"], args.max_train_samples, args.seed + 1)
    val_by_source = {
        source: stratified_limit(
            [row for row in rows if row["split"] == "validation" and row["source"] == source],
            args.max_val_samples_per_source,
            args.seed + 2,
        )
        for source in config["sources"]
    }
    if not train_rows or any(not values for values in val_by_source.values()):
        raise RuntimeError("訓練或某個來源驗證資料為空；煙霧快取需涵蓋每個 split/source/label。")

    train_feature_matrix = np.stack([vector(cache[row["record_id"]]) for row in train_rows])
    standardizer = FeatureStandardizer.fit(train_feature_matrix)
    monitor_rows = stratified_limit(train_rows, min(1500, len(train_rows)), args.seed + 3)

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    load_images = args.mode == "fusion"
    loader_args = {"batch_size": batch_size, "num_workers": 0, "pin_memory": device.type == "cuda"}
    weights, sampling_audit = sample_weights(train_rows, train_config["class_balance_alpha"])
    sampler_generator = torch.Generator().manual_seed(args.seed + 4)
    sampler = WeightedRandomSampler(
        torch.tensor(weights, dtype=torch.double),
        len(train_rows),
        replacement=True,
        generator=sampler_generator,
    )
    train_loader = DataLoader(
        FusionDataset(train_rows, cache, standardizer, train_config["image_size"], True, load_images),
        sampler=sampler,
        **loader_args,
    )
    monitor_loader = DataLoader(
        FusionDataset(monitor_rows, cache, standardizer, train_config["image_size"], False, load_images),
        shuffle=False,
        **loader_args,
    )
    val_loaders = {
        source: DataLoader(
            FusionDataset(items, cache, standardizer, train_config["image_size"], False, load_images),
            shuffle=False,
            **loader_args,
        )
        for source, items in val_by_source.items()
    }

    model = build_experiment_model(args.mode, len(MODEL_FEATURE_NAMES), 7, not args.no_pretrained).to(device)
    optimizer = optimizer_for(model, args.mode, train_config, learning_rate)
    criterion = nn.CrossEntropyLoss(label_smoothing=train_config["label_smoothing"]).to(device)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(epochs, 1), eta_min=1e-6)
    output = args.output_root or EXPERIMENT / "results" / f"{args.mode}_seed{args.seed}"
    output.mkdir(parents=True, exist_ok=True)
    last_path, best_path = output / "last.pt", output / "best.pt"
    history, best_score, best_record, patience, start_epoch = [], -math.inf, None, 0, 0
    if args.resume and last_path.exists():
        state = torch.load(last_path, map_location=device, weights_only=False)
        if state["mode"] != args.mode or state["feature_version"] != FEATURE_VERSION:
            raise RuntimeError("checkpoint 的模式或特徵版本不同，不能續跑。")
        model.load_state_dict(state["model"])
        optimizer.load_state_dict(state["optimizer"])
        scheduler.load_state_dict(state["scheduler"])
        scaler.load_state_dict(state["scaler"])
        history, best_score, best_record = state["history"], state["best_score"], state["best_record"]
        patience, start_epoch = state["patience"], state["epoch"]
        sampler_generator.set_state(state["sampler_generator_state"])

    print(
        f"device={device} mode={args.mode} train={len(train_rows)} "
        f"val={{{', '.join(f'{key}:{len(value)}' for key, value in val_by_source.items())}}}",
        flush=True,
    )
    for epoch_index in range(start_epoch, epochs):
        print(f"\nEpoch {epoch_index + 1}/{epochs}", flush=True)
        train_loss = train_epoch(
            model,
            train_loader,
            criterion,
            optimizer,
            scaler,
            device,
            train_config["mixup_alpha"],
            train_config["gradient_clip_norm"],
        )
        monitor = evaluate(model, monitor_loader, criterion, device, list(range(7)), "訓練監測")
        validation = {
            source: evaluate(
                model,
                loader,
                criterion,
                device,
                config["sources"][source]["supported_labels"],
                f"驗證 {source}",
            )
            for source, loader in val_loaders.items()
        }
        scores = [metrics["balanced_accuracy"] for metrics in validation.values()]
        mean_score, worst_score = float(np.mean(scores)), float(np.min(scores))
        robust_score = 0.5 * mean_score + 0.5 * worst_score
        record = {
            "epoch": epoch_index + 1,
            "train_loss": train_loss,
            "train_monitor": monitor,
            "validation_by_source": validation,
            "mean_source_balanced_accuracy": mean_score,
            "worst_source_balanced_accuracy": worst_score,
            "robust_selection_score": robust_score,
            "train_validation_gap": {
                source: monitor["balanced_accuracy"] - metrics["balanced_accuracy"]
                for source, metrics in validation.items()
            },
            "learning_rate": scheduler.get_last_lr()[0],
        }
        history.append(record)
        improved = robust_score > best_score
        if improved:
            best_score, best_record, patience = robust_score, record, 0
            torch.save({
                "model": model.state_dict(),
                "mode": args.mode,
                "feature_version": FEATURE_VERSION,
                "feature_names": MODEL_FEATURE_NAMES,
                "audit_only_feature_names": AUDIT_ONLY_FEATURE_NAMES,
                "feature_mean": standardizer.mean,
                "feature_std": standardizer.std,
                "record": record,
            }, best_path)
        else:
            patience += 1
        scheduler.step()
        state = {
            "epoch": epoch_index + 1,
            "model": model.state_dict(),
            "optimizer": optimizer.state_dict(),
            "scheduler": scheduler.state_dict(),
            "scaler": scaler.state_dict(),
            "history": history,
            "best_score": best_score,
            "best_record": best_record,
            "patience": patience,
            "sampler_generator_state": sampler_generator.get_state(),
            "mode": args.mode,
            "feature_version": FEATURE_VERSION,
        }
        torch.save(state, last_path)
        print(
            f"train_BA={monitor['balanced_accuracy']:.4f} mean_BA={mean_score:.4f} "
            f"worst_BA={worst_score:.4f} robust={robust_score:.4f}",
            flush=True,
        )
        if patience >= train_config["early_stopping_patience"]:
            print("early stopping", flush=True)
            break

    result = {
        "experiment": "explicit_image_feature_fusion_v1",
        "mode": args.mode,
        "seed": args.seed,
        "feature_version": FEATURE_VERSION,
        "cache_feature_count": len(FEATURE_NAMES),
        "model_feature_count": len(MODEL_FEATURE_NAMES),
        "model_feature_names": MODEL_FEATURE_NAMES,
        "audit_only_feature_names": AUDIT_ONLY_FEATURE_NAMES,
        "feature_scope": "全圖色彩/紋理/品質，加中央與邊緣差值代理；尚未使用病灶分割",
        "feature_normalization": "只以實際訓練切分估計 mean/std",
        "source_device_artifact_as_disease_input": False,
        "pretrained": not args.no_pretrained if args.mode == "fusion" else None,
        "train_samples": len(train_rows),
        "validation_samples": {source: len(items) for source, items in val_by_source.items()},
        "sampling": sampling_audit,
        "epochs_requested": epochs,
        "epochs_completed": len(history),
        "best": best_record,
        "history": history,
        "test_used": False,
        "interpretation_limit": "煙霧或顯式特徵實驗；中央區域不是經驗證的病灶遮罩。",
    }
    (output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"結果：{output / 'result.json'}", flush=True)


if __name__ == "__main__":
    main()
