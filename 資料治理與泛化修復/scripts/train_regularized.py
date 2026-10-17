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
from torchvision import transforms


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
sys.path.insert(0, str(PROJECT / "第二階段" / "src"))

from stage2.engine import seed_everything
from stage2.metrics import metrics_from_logits
from stage2.models import build_model, parameter_groups_with_layer_decay
from coverage_sampler import FullCoverageCappedSampler

try:
    from tqdm.auto import tqdm
except ImportError:  # pragma: no cover
    def tqdm(iterable, **_kwargs):
        return iterable


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def build_transform(image_size: int, train: bool):
    if not train:
        return transforms.Compose([
            transforms.Resize((image_size, image_size)), transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ])
    return transforms.Compose([
        transforms.RandomResizedCrop(image_size, scale=(0.70, 1.0), ratio=(0.75, 1.33)),
        transforms.RandomHorizontalFlip(), transforms.RandomVerticalFlip(),
        transforms.RandomRotation(25),
        transforms.RandomApply([
            transforms.ColorJitter(brightness=0.22, contrast=0.22, saturation=0.20, hue=0.03)
        ], p=0.8),
        transforms.RandomGrayscale(p=0.05),
        transforms.RandomApply([transforms.GaussianBlur(3, sigma=(0.1, 1.5))], p=0.15),
        transforms.RandomAutocontrast(p=0.10),
        transforms.ToTensor(), transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        transforms.RandomErasing(p=0.15, scale=(0.02, 0.10), ratio=(0.3, 3.3), value="random"),
    ])


class SkinDataset(Dataset):
    def __init__(self, rows: list[dict], image_size: int, train: bool):
        self.rows = rows
        self.transform = build_transform(image_size, train)

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index: int):
        row = self.rows[index]
        with Image.open(PROJECT / row["image_path"]) as image:
            tensor = self.transform(image.convert("RGB"))
        return tensor, int(row["label"]), row["source"]


def stratified_limit(rows: list[dict], limit: int | None, seed: int) -> list[dict]:
    if not limit or limit >= len(rows):
        return rows
    groups = defaultdict(list)
    for row in rows:
        groups[(row["source"], int(row["label"]))].append(row)
    rng = np.random.default_rng(seed)
    for items in groups.values():
        rng.shuffle(items)
    selected, keys = [], sorted(groups)
    while len(selected) < limit:
        progressed = False
        for key in keys:
            if groups[key] and len(selected) < limit:
                selected.append(groups[key].pop())
                progressed = True
        if not progressed:
            break
    return selected


def sample_weights(rows: list[dict], alpha: float) -> tuple[list[float], dict]:
    counts = Counter((row["source"], int(row["label"])) for row in rows)
    sources = sorted({row["source"] for row in rows})
    normalizers = {
        source: sum(n * n ** (-alpha) for (candidate, _), n in counts.items() if candidate == source)
        for source in sources
    }
    weights = [counts[(row["source"], int(row["label"]))] ** (-alpha) / normalizers[row["source"]] for row in rows]
    total = sum(weights)
    return weights, {
        "expected_source_share": {
            source: sum(w for w, row in zip(weights, rows) if row["source"] == source) / total
            for source in sources
        },
        "source_class_counts": {f"{s}:{c}": n for (s, c), n in sorted(counts.items())},
    }


def supported_source_metrics(logits: np.ndarray, targets: np.ndarray, supported: list[int]) -> dict:
    # 類別數改由 logits 寬度推導，不再寫死 7。
    # 七類模型 logits.shape[1] == 7，行為與改動前逐位元相同；
    # 八類（v2 資料含 SCC）時混淆矩陣才容得下 label 7。
    # balanced_accuracy 仍只對 supported 內的類別取平均，
    # 因此 SUPPORTED_LABELS 維持七類時，數字與舊結果可比。
    num_classes = int(np.asarray(logits).shape[1])
    metrics = metrics_from_logits(logits, targets, num_classes=num_classes)
    matrix = np.asarray(metrics["confusion_matrix"], dtype=np.float64)
    recalls = np.divide(np.diag(matrix), matrix.sum(1), out=np.zeros(num_classes), where=matrix.sum(1) != 0)
    precisions = np.divide(np.diag(matrix), matrix.sum(0), out=np.zeros(num_classes), where=matrix.sum(0) != 0)
    f1 = np.divide(2 * precisions * recalls, precisions + recalls, out=np.zeros(num_classes), where=(precisions + recalls) != 0)
    labels = np.asarray(supported, dtype=np.int64)
    metrics["balanced_accuracy"] = float(recalls[labels].mean())
    metrics["macro_f1"] = float(f1[labels].mean())
    metrics["metric_labels"] = supported
    return metrics


@torch.inference_mode()
def evaluate(model, loader, criterion, device, supported: list[int], description: str) -> dict:
    model.eval()
    total_loss, logits_all, targets_all = 0.0, [], []
    for images, targets, _sources in tqdm(loader, desc=description, leave=False, unit="batch"):
        images, targets = images.to(device), targets.to(device)
        with torch.amp.autocast(device_type=device.type, enabled=device.type == "cuda"):
            logits = model(images)
            loss = criterion(logits, targets)
        total_loss += loss.item() * targets.size(0)
        logits_all.append(logits.float().cpu().numpy())
        targets_all.append(targets.cpu().numpy())
    metrics = supported_source_metrics(np.concatenate(logits_all), np.concatenate(targets_all), supported)
    metrics["loss"] = total_loss / len(loader.dataset)
    metrics["samples"] = len(loader.dataset)
    return metrics


def train_epoch(model, loader, criterion, optimizer, scaler, device, accumulation: int, mixup_alpha: float, clip: float) -> float:
    model.train()
    optimizer.zero_grad(set_to_none=True)
    total_loss, total_seen = 0.0, 0
    for step, (images, targets, _sources) in enumerate(tqdm(loader, desc="訓練", leave=False, unit="batch")):
        images, targets = images.to(device), targets.to(device)
        if mixup_alpha > 0:
            lam = float(np.random.beta(mixup_alpha, mixup_alpha))
            permutation = torch.randperm(images.size(0), device=device)
            mixed = lam * images + (1 - lam) * images[permutation]
            target_b = targets[permutation]
        else:
            lam, mixed, target_b = 1.0, images, targets
        with torch.amp.autocast(device_type=device.type, enabled=device.type == "cuda"):
            logits = model(mixed)
            loss = lam * criterion(logits, targets) + (1 - lam) * criterion(logits, target_b)
        scaler.scale(loss / accumulation).backward()
        if (step + 1) % accumulation == 0 or step + 1 == len(loader):
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), clip)
            scaler.step(optimizer)
            scaler.update()
            optimizer.zero_grad(set_to_none=True)
        total_loss += loss.item() * targets.size(0)
        total_seen += targets.size(0)
    return total_loss / total_seen


def main() -> None:
    parser = argparse.ArgumentParser(description="清理後三來源、抗過擬合與設備差異正式訓練")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--learning-rate", type=float)
    parser.add_argument("--weight-decay", type=float)
    parser.add_argument("--label-smoothing", type=float)
    parser.add_argument("--mixup-alpha", type=float)
    parser.add_argument("--early-stopping-patience", type=int)
    parser.add_argument(
        "--sampling-method",
        choices=["weighted_replacement", "full_coverage_capped"],
        default="weighted_replacement",
        help="完整覆蓋模式會讓每筆訓練資料每 epoch 至少出現一次，再有限補抽。",
    )
    parser.add_argument("--max-repeats-per-epoch", type=int, default=2)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-train-samples", type=int, help="僅供 smoke test")
    parser.add_argument("--max-val-samples-per-source", type=int, help="僅供 smoke test")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--num-workers", type=int, default=None,
                        help="覆寫 config 的 num_workers；>0 讓資料載入與 GPU 重疊")
    parser.add_argument("--prefetch-factor", type=int, default=4,
                        help="每個 worker 預先準備的 batch 數；僅在 num_workers>0 時生效")
    args = parser.parse_args()

    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8-sig"))
    train_config = dict(config["training"])
    overrides = {
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "weight_decay": args.weight_decay,
        "label_smoothing": args.label_smoothing,
        "mixup_alpha": args.mixup_alpha,
        "early_stopping_patience": args.early_stopping_patience,
    }
    train_config.update({key: value for key, value in overrides.items() if value is not None})
    gate_path = ROOT / "reports" / "pipeline_gate.json"
    if not gate_path.exists() or not json.loads(gate_path.read_text(encoding="utf-8-sig")).get("passed"):
        raise RuntimeError("資料治理閘門未通過；請先執行 scripts/run_pipeline.py")
    manifest_path = ROOT / "data" / "unified_manifest_v1.csv"
    if not manifest_path.exists():
        raise RuntimeError("找不到統一資料清單；請先執行 scripts/run_pipeline.py")
    rows = read_csv(manifest_path)
    required_contract_columns = {
        "schema_version", "record_id", "source", "split", "image_path", "group_id",
        "diagnosis_original", "diagnosis_canonical_code", "label", "label_name",
        "training_eligible", "image_modality", "leakage_status",
    }
    missing_contract_columns = required_contract_columns - set(rows[0] if rows else [])
    if missing_contract_columns:
        raise RuntimeError(f"統一資料清單缺少欄位：{sorted(missing_contract_columns)}")
    if {row["schema_version"] for row in rows} != {"skindetect-data-contract-v1.0"}:
        raise RuntimeError("資料契約版本不一致")
    rows = [row for row in rows if row["training_eligible"].lower() == "true"]
    train_rows = stratified_limit([row for row in rows if row["split"] == "train"], args.max_train_samples, args.seed + 1)
    val_by_source = {
        source: stratified_limit(
            [row for row in rows if row["split"] == "validation" and row["source"] == source],
            args.max_val_samples_per_source, args.seed + 2,
        )
        for source in config["sources"]
    }
    monitor_rows = stratified_limit(train_rows, min(1500, len(train_rows)), args.seed + 3)
    seed_everything(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    workers = train_config["num_workers"] if args.num_workers is None else args.num_workers
    loader_args = {
        "batch_size": train_config["batch_size"], "num_workers": workers,
        "pin_memory": device.type == "cuda",
    }
    if workers > 0:
        # num_workers>0 時資料增強改由子行程 RNG 產生，與 0 的既有結果
        # 分布相同但序列不同（等同換一個增強亂數流），不是逐位元重現。
        loader_args["persistent_workers"] = True
        loader_args["prefetch_factor"] = args.prefetch_factor
    sampler_generator = torch.Generator().manual_seed(args.seed + 4)
    if args.sampling_method == "full_coverage_capped":
        sampler = FullCoverageCappedSampler(
            train_rows,
            class_balance_alpha=train_config["class_balance_alpha"],
            max_repeats=args.max_repeats_per_epoch,
            seed=args.seed + 4,
        )
        sampling_audit = sampler.audit()
    else:
        weights, sampling_audit = sample_weights(train_rows, train_config["class_balance_alpha"])
        sampler = WeightedRandomSampler(
            torch.tensor(weights, dtype=torch.double), len(train_rows), replacement=True,
            generator=sampler_generator,
        )
        sampling_audit["method"] = "source_balanced_class_smoothed_weighted_replacement"
        sampling_audit["unique_samples"] = len(train_rows)
        sampling_audit["samples_per_epoch"] = len(train_rows)
        sampling_audit["coverage_guarantee"] = "無；有放回抽樣"
        sampling_audit["max_repeats_per_sample_per_epoch"] = None
    train_loader = DataLoader(SkinDataset(train_rows, train_config["image_size"], True), sampler=sampler, **loader_args)
    monitor_loader = DataLoader(SkinDataset(monitor_rows, train_config["image_size"], False), shuffle=False, **loader_args)
    val_loaders = {
        source: DataLoader(SkinDataset(items, train_config["image_size"], False), shuffle=False, **loader_args)
        for source, items in val_by_source.items()
    }

    model = build_model(train_config["model"], pretrained=True, num_classes=7).to(device)
    optimizer = torch.optim.AdamW(parameter_groups_with_layer_decay(
        model, train_config["learning_rate"], train_config["weight_decay"], train_config["layer_decay"]
    ))
    criterion = nn.CrossEntropyLoss(label_smoothing=train_config["label_smoothing"]).to(device)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    epochs = train_config["epochs"]
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(epochs, 1), eta_min=1e-6)
    output = (args.output_root or ROOT / "results") / f"regularized_seed{args.seed}"
    output.mkdir(parents=True, exist_ok=True)
    best_path, last_path = output / "best.pt", output / "last.pt"
    history, best_score, best_record, patience, start_epoch = [], -math.inf, None, 0, 0
    if args.resume and last_path.exists():
        state = torch.load(last_path, map_location=device, weights_only=False)
        model.load_state_dict(state["model"]); optimizer.load_state_dict(state["optimizer"])
        scaler.load_state_dict(state["scaler"]); scheduler.load_state_dict(state["scheduler"])
        history, best_score, best_record = state["history"], state["best_score"], state["best_record"]
        patience, start_epoch = state["patience"], state["epoch"]
        saved_sampling_method = state.get("sampling_method", "weighted_replacement")
        if saved_sampling_method != args.sampling_method:
            raise RuntimeError(
                f"續跑抽樣模式不一致：checkpoint={saved_sampling_method}, current={args.sampling_method}"
            )
        if isinstance(sampler, FullCoverageCappedSampler):
            sampler.set_epoch(int(state.get("sampler_epoch", start_epoch)))
        else:
            sampler_generator.set_state(state["sampler_generator_state"])

    print(f"device={device} train={len(train_rows)} monitor={len(monitor_rows)} seed={args.seed}", flush=True)
    print("抽樣設定=" + json.dumps(sampling_audit, ensure_ascii=False), flush=True)
    for epoch_index in range(start_epoch, epochs):
        print(f"\nEpoch {epoch_index + 1}/{epochs}", flush=True)
        train_loss = train_epoch(
            model, train_loader, criterion, optimizer, scaler, device,
            train_config["gradient_accumulation"], train_config["mixup_alpha"], train_config["gradient_clip_norm"],
        )
        monitor = evaluate(model, monitor_loader, criterion, device, list(range(7)), "訓練監測")
        validation = {
            source: evaluate(model, loader, criterion, device, config["sources"][source]["supported_labels"], f"驗證 {source}")
            for source, loader in val_loaders.items()
        }
        scores = [item["balanced_accuracy"] for item in validation.values()]
        mean_score, worst_score = float(np.mean(scores)), float(np.min(scores))
        robust_score = 0.5 * mean_score + 0.5 * worst_score
        gaps = {source: monitor["balanced_accuracy"] - item["balanced_accuracy"] for source, item in validation.items()}
        record = {
            "epoch": epoch_index + 1, "train_loss": train_loss, "train_monitor": monitor,
            "validation_by_source": validation, "mean_source_balanced_accuracy": mean_score,
            "worst_source_balanced_accuracy": worst_score, "robust_selection_score": robust_score,
            "train_validation_gap": gaps, "learning_rate": optimizer.param_groups[-1]["lr"],
        }
        history.append(record)
        if robust_score > best_score:
            best_score, best_record, patience = robust_score, record, 0
            torch.save({
                "model": model.state_dict(), "seed": args.seed, "epoch": epoch_index + 1,
                "architecture": "convnext_tiny_7_class", "initialization": "imagenet",
                "training_pipeline": config["pipeline_id"], "selection_score": robust_score,
                "normalization": train_config["normalization"],
                "sampling_method": args.sampling_method, "test_used": False,
            }, best_path)
        else:
            patience += 1
        scheduler.step()
        torch.save({
            "model": model.state_dict(), "optimizer": optimizer.state_dict(), "scaler": scaler.state_dict(),
            "scheduler": scheduler.state_dict(), "history": history, "best_score": best_score,
            "best_record": best_record, "patience": patience, "epoch": epoch_index + 1,
            "sampling_method": args.sampling_method,
            "sampler_epoch": getattr(sampler, "epoch", None),
            "sampler_generator_state": sampler_generator.get_state(),
        }, last_path)
        text = " ".join(f"{source}_BA={item['balanced_accuracy']:.4f}" for source, item in validation.items())
        print(f"train_loss={train_loss:.4f} monitor_BA={monitor['balanced_accuracy']:.4f} {text} robust={robust_score:.4f}", flush=True)
        if patience >= train_config["early_stopping_patience"]:
            print(f"提早停止：{patience} epoch 未改善", flush=True)
            break

    result = {
        "experiment_id": config["pipeline_id"], "seed": args.seed,
        "architecture": "convnext_tiny_7_class", "training_sources": sorted(val_loaders),
        "train_samples": len(train_rows), "validation_samples": {s: len(v.dataset) for s, v in val_loaders.items()},
        "samples_per_epoch": len(sampler),
        "epochs_requested": epochs, "epochs_completed": len(history),
        "stopped_early": len(history) < epochs,
        "regularization": train_config, "sampling": sampling_audit, "best": best_record,
        "history": history, "test_used": False,
    }
    (output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已儲存：{output / 'result.json'}", flush=True)


if __name__ == "__main__":
    main()
