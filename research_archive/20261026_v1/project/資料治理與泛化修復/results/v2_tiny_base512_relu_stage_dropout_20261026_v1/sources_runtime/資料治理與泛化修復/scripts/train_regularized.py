from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import time
import uuid
import platform
import importlib.metadata
import os
from datetime import datetime, timezone
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler, RandomSampler
from torchvision import transforms


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
sys.path.insert(0, str(PROJECT / "第二階段" / "src"))

from stage2.engine import seed_everything
from stage2.metrics import metrics_from_logits
from stage2.models import build_model, parameter_groups_with_layer_decay
from coverage_sampler import FullCoverageCappedSampler
from training_state import (
    CheckpointStore, advance_stopping, atomic_json, capture_rng, export_best,
    file_sha256, restore_rng, run_directory,
)

try:
    from tqdm.auto import tqdm
except ImportError:  # pragma: no cover
    def tqdm(iterable, **_kwargs):
        return iterable


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_governed_release(directory: Path, config: dict) -> tuple[Path, list[dict], dict]:
    """Select an immutable fixed-split release without reusing the historical gate."""
    directory = directory.resolve()
    hashes = json.loads((directory / "file_hashes.json").read_text(encoding="utf-8-sig"))
    for name in ("mixed_manifest.csv", "summary.json", "data_definition_audit.json", "duplicate_audit.json"):
        if hashlib.sha256((directory / name).read_bytes()).hexdigest() != hashes.get(name):
            raise RuntimeError(f"資料發布檔案指紋不符：{name}")
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8-sig"))
    audit = json.loads((directory / "data_definition_audit.json").read_text(encoding="utf-8-sig"))
    required_flags = (
        "data_preparation_completed", "historical_reference_verified", "split_assignments_preserved",
        "available_patient_and_scoped_lesion_isolation_passed", "test_excluded_from_training_manifest",
        "all_manifest_image_paths_exist", "original_metadata_and_mapping_hashes_unchanged",
    )
    if (summary.get("release_id") != directory.name or not audit.get("passed")
            or not all(summary.get(key) is True for key in required_flags)
            or summary.get("exact_duplicate_content_cross_split") != 0
            or summary.get("same_content_remaining_after_dedup") != 0
            or not summary.get("after_group_checks")
            or any(summary["after_group_checks"].values())):
        raise RuntimeError("固定切分發布驗證未通過")
    path = directory / "mixed_manifest.csv"
    rows = read_csv(path)
    counts, ids, content, groups = Counter(), set(), set(), {}
    for row in rows:
        source, split, label = row["source"], row["split"], int(row["label"])
        if (source not in config["sources"] or split not in {"train", "validation"}
                or row["training_eligible"].lower() != "true"
                or label not in config["sources"][source]["supported_labels"]
                or row["label_name"] != config["class_names"][label]
                or row["diagnosis_canonical_code"] != config["class_names"][label]
                or row["schema_version"] != config["data_definition"]["schema_version"]
                or row["leakage_status"] != "passed_fixed_split_sha256_group_audit_20261018"):
            raise RuntimeError(f"發布列不符合七類訓練契約：{row['record_id']}")
        if row["record_id"] in ids or not row["sha256"] or row["sha256"].lower() in content:
            raise RuntimeError("發布清單含重複識別碼或圖片 SHA256")
        ids.add(row["record_id"]); content.add(row["sha256"].lower())
        keys = [(source, "split", row["split_group_id"]), (source, "lesion", row["lesion_record_key"])]
        if row["patient_id"]:
            keys.append((source, "patient", row["patient_id"]))
        for key in keys:
            if not key[2] or (key in groups and groups[key] != split):
                raise RuntimeError(f"發布群組跨 Split 或缺少識別資訊：{key}")
            groups[key] = split
        image = (PROJECT / row["image_path"]).resolve()
        if not image.is_relative_to(PROJECT.resolve()) or not image.is_file():
            raise RuntimeError(f"圖片路徑不存在或不在專案內：{image}")
        counts[(source, split)] += 1
    expected = Counter({(source, split): values[split]
                        for source, values in summary["after_counts"].items()
                        for split in ("train", "validation")})
    if counts != expected or len(rows) != audit["total_rows"]:
        raise RuntimeError("發布清單數量與治理報告不一致")
    provenance = {"release_id": summary["release_id"], "manifest": str(path),
                  "manifest_sha256": hashes["mixed_manifest.csv"], "summary_sha256": hashes["summary.json"],
                  "class_names": config["class_names"], "limitations": summary["limitations"]}
    return path, rows, provenance


IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def build_transform(image_size: int, train: bool, random_erasing_p: float = 0.15):
    if not math.isfinite(random_erasing_p) or not 0 <= random_erasing_p <= 1:
        raise RuntimeError('Invalid RandomErasing probability')
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
        transforms.RandomErasing(p=random_erasing_p, scale=(0.02, 0.10), ratio=(0.3, 3.3), value="random"),
    ])


class SkinDataset(Dataset):
    def __init__(self, rows: list[dict], image_size: int, train: bool, transform_override=None):
        self.rows = rows
        self.transform = transform_override if transform_override is not None else build_transform(image_size, train)

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


def sample_weights(rows: list[dict], alpha: float, source_shares: dict | None = None) -> tuple[list[float], dict]:
    counts = Counter((row["source"], int(row["label"])) for row in rows)
    sources = sorted({row["source"] for row in rows})
    normalizers = {
        source: sum(n * n ** (-alpha) for (candidate, _), n in counts.items() if candidate == source)
        for source in sources
    }
    weights = [counts[(row["source"], int(row["label"]))] ** (-alpha) / normalizers[row["source"]] for row in rows]
    if source_shares is not None:
        if (set(source_shares) != set(sources)
                or any(not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in source_shares.values())
                or not math.isclose(sum(source_shares.values()), 1.0, abs_tol=1e-12, rel_tol=0)):
            raise RuntimeError('Source shares must be finite, nonnegative, contain exactly the training sources, and sum to one')
        weights = [w * source_shares[row['source']] for w, row in zip(weights, rows)]
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
def evaluate(model, loader, criterion, device, supported: list[int], description: str, amp_enabled=True) -> dict:
    model.eval()
    total_loss, logits_all, targets_all = 0.0, [], []
    for images, targets, _sources in tqdm(loader, desc=description, leave=False, unit="batch"):
        images, targets = images.to(device), targets.to(device)
        with torch.amp.autocast(device_type=device.type, enabled=device.type == "cuda" and amp_enabled):
            logits = model(images)
            loss = criterion(logits, targets)
        total_loss += loss.item() * targets.size(0)
        logits_all.append(logits.float().cpu().numpy())
        targets_all.append(targets.cpu().numpy())
    metrics = supported_source_metrics(np.concatenate(logits_all), np.concatenate(targets_all), supported)
    metrics["loss"] = total_loss / len(loader.dataset)
    metrics["samples"] = len(loader.dataset)
    return metrics


def train_epoch(model, loader, criterion, optimizer, scaler, device, accumulation: int, mixup_alpha: float, clip: float | None, amp_enabled=True, timing=None) -> float:
    model.train()
    optimizer.zero_grad(set_to_none=True)
    total_loss, total_seen = 0.0, 0
    last_batch_end = time.perf_counter() if timing is not None else None
    for step, (images, targets, _sources) in enumerate(tqdm(loader, desc="訓練", leave=False, unit="batch")):
        if timing is not None:
            batch_started = time.perf_counter()
            timing['data_wait_including_iterator_tqdm_seconds'] += batch_started - last_batch_end
        images, targets = images.to(device), targets.to(device)
        if mixup_alpha > 0:
            lam = float(np.random.beta(mixup_alpha, mixup_alpha))
            permutation = torch.randperm(images.size(0), device=device)
            mixed = lam * images + (1 - lam) * images[permutation]
            target_b = targets[permutation]
        else:
            lam, mixed, target_b = 1.0, images, targets
        with torch.amp.autocast(device_type=device.type, enabled=device.type == "cuda" and amp_enabled):
            logits = model(mixed)
            loss = lam * criterion(logits, targets) + (1 - lam) * criterion(logits, target_b)
        scaler.scale(loss / accumulation).backward()
        if (step + 1) % accumulation == 0 or step + 1 == len(loader):
            scaler.unscale_(optimizer)
            if clip is not None:
                torch.nn.utils.clip_grad_norm_(model.parameters(), clip)
            scaler.step(optimizer)
            scaler.update()
            optimizer.zero_grad(set_to_none=True)
        total_loss += loss.item() * targets.size(0)
        total_seen += targets.size(0)
        if timing is not None:
            last_batch_end = time.perf_counter()
            timing['batch_processing_seconds_with_existing_loss_sync'] += last_batch_end - batch_started
            timing['batches'] += 1
    return total_loss / total_seen


def parse_args():
    parser = argparse.ArgumentParser(description="清理後三來源、抗過擬合與設備差異正式訓練")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--learning-rate", type=float)
    parser.add_argument("--weight-decay", type=float)
    parser.add_argument("--label-smoothing", type=float)
    parser.add_argument("--mixup-alpha", type=float)
    parser.add_argument("--early-stopping-patience", type=int)
    parser.add_argument("--config", type=Path, default=ROOT / "config.json")
    parser.add_argument("--min-epochs", type=int)
    parser.add_argument("--min-delta", type=float)
    parser.add_argument("--early-stopping", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--formal", action="store_true", help="鎖定核定的正式資料與設定，拒絕 smoke 限量")
    parser.add_argument("--stop-after-epoch", type=int,
                        help="僅供小型驗收：保存指定完整 epoch 後暫停；不改 scheduler 總長度")
    parser.add_argument(
        "--sampling-method",
        choices=["weighted_replacement", "full_coverage_capped", "shuffle"],
        default=None,
        help="完整覆蓋模式會讓每筆訓練資料每 epoch 至少出現一次，再有限補抽。",
    )
    parser.add_argument("--max-repeats-per-epoch", type=int, default=2)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-train-samples", type=int, help="僅供 smoke test")
    parser.add_argument("--max-val-samples-per-source", type=int, help="僅供 smoke test")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--manifest-release", type=Path, help="明確指定已發布、含指紋與驗證報告的固定切分目錄")
    parser.add_argument("--require-cuda", action="store_true", help="CUDA 不可用時停止，不降級至 CPU")
    parser.add_argument("--num-workers", type=int, default=None,
                        help="覆寫 config 的 num_workers；>0 讓資料載入與 GPU 重疊")
    parser.add_argument("--prefetch-factor", type=int, default=4,
                        help="每個 worker 預先準備的 batch 數；僅在 num_workers>0 時生效")
    return parser.parse_args()


def run_training(args, output):
    attempt_started = time.perf_counter()
    config = json.loads(args.config.read_text(encoding="utf-8-sig"))
    is_profile = config.get('profile_version') == 1
    profile = None
    if is_profile:
        import model_profiles as profile
        profile.validate_profile(config, formal=args.formal)
    optimization = None
    if 'optimization' in config:
        if config['optimization'].get('version') == 'v2_tiny_base512_relu_stage_dropout_20261026_v1':
            import v2_relu_dropout_contract as optimization
        elif config['optimization'].get('version') == 'v2_scale512_followup_20261026_v1':
            import v2_scale_followup_contract as optimization
        elif config['optimization'].get('version') == 'v2_scale512_seed1_20261025_v1':
            import v2_scale_contract as optimization
        elif config['optimization'].get('version') == 'v2_512_alpha025_20261024_v1':
            import v2_alpha025_contract as optimization
        elif config['optimization'].get('version') == 'v2_resolution_20261021_v1':
            import v2_resolution_contract as optimization
        elif config['optimization'].get('version') == 'v2_optimization_round2_20261020_v1':
            import v2_round2_contract as optimization
        else:
            import v2_opt_contract as optimization
        optimization.validate_execution(config, args)
    train_config = dict(config["training"])
    overrides = {
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "weight_decay": args.weight_decay,
        "label_smoothing": args.label_smoothing,
        "mixup_alpha": args.mixup_alpha,
        "early_stopping_patience": args.early_stopping_patience,
        "min_epochs": args.min_epochs,
        "min_delta": args.min_delta,
        "early_stopping": args.early_stopping,
        "num_workers": args.num_workers,
    }
    train_config.update({key: value for key, value in overrides.items() if value is not None})
    train_config.setdefault("min_epochs", 1)
    train_config.setdefault("early_stopping", True)
    train_config.setdefault("min_delta", 0.0)
    args.sampling_method = args.sampling_method or train_config.get('sampling_method', 'weighted_replacement')
    amp_enabled = train_config.get('amp', True)
    epochs = train_config["epochs"]
    if (not 1 <= train_config["min_epochs"] <= epochs
            or train_config["early_stopping_patience"] < 1
            or not math.isfinite(train_config["min_delta"]) or train_config["min_delta"] < 0
            or train_config['num_workers'] < 0 or args.prefetch_factor < 1):
        raise RuntimeError('Invalid epoch/early-stopping/loader configuration')
    if args.stop_after_epoch is not None and not 1 <= args.stop_after_epoch <= epochs:
        raise RuntimeError('Invalid --stop-after-epoch')
    if args.formal and is_profile:
        if (train_config != config['training'] or args.seed not in [1, 2, 3]
                or args.max_train_samples is not None or args.max_val_samples_per_source is not None
                or args.stop_after_epoch is not None or not args.require_cuda
                or args.sampling_method != train_config['sampling_method'] or args.prefetch_factor != 4
                or not args.manifest_release
                or args.manifest_release.resolve() != (ROOT / 'data/governed_18979_20261018_v1').resolve()
                or file_sha256(ROOT / 'config.json') != config['formal_suite']['baseline_config_sha256']):
            raise RuntimeError('Formal profile differs from its frozen model-specific config')
    if args.formal and not is_profile:
        baseline = json.loads((ROOT / 'config.json').read_text(encoding='utf-8-sig'))
        expected = dict(baseline['training'])
        expected.update(epochs=30, min_epochs=12, early_stopping=True,
                        early_stopping_patience=5, min_delta=0.0, num_workers=4)
        if (file_sha256(ROOT / 'config.json') != config.get('formal_suite', {}).get('baseline_config_sha256')
                or train_config != expected or config['class_names'] != baseline['class_names']
                or config['sources'] != baseline['sources'] or args.seed not in [1, 2, 3]
                or args.max_train_samples is not None or args.max_val_samples_per_source is not None
                or args.stop_after_epoch is not None or not args.require_cuda
                or args.sampling_method != 'weighted_replacement' or args.prefetch_factor != 4
                or not args.manifest_release
                or args.manifest_release.resolve() != (ROOT / 'data/governed_18979_20261018_v1').resolve()):
            raise RuntimeError('Formal run differs from approved training contract')
    if args.manifest_release:
        manifest_path, rows, data_provenance = load_governed_release(args.manifest_release, config)
    else:
        gate_path = ROOT / "reports" / "pipeline_gate.json"
        if not gate_path.exists() or not json.loads(gate_path.read_text(encoding="utf-8-sig")).get("passed"):
            raise RuntimeError("資料治理閘門未通過；請先執行 scripts/run_pipeline.py")
        manifest_path = ROOT / "data" / "unified_manifest_v1.csv"
        if not manifest_path.exists():
            raise RuntimeError("找不到統一資料清單；請先執行 scripts/run_pipeline.py")
        rows = read_csv(manifest_path)
        data_provenance = {"manifest": str(manifest_path),
                           "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest()}
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
    if args.formal and (len(train_rows) != 18919 or sum(map(len, val_by_source.values())) != 3611):
        raise RuntimeError('Formal row counts differ')
    seed_everything(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if args.require_cuda and device.type != "cuda":
        raise RuntimeError("本次測試要求 CUDA，但 CUDA 不可用")
    workers = train_config["num_workers"]
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
    elif args.sampling_method == 'shuffle':
        sampler = RandomSampler(train_rows, generator=sampler_generator)
        sampling_audit = {'method': 'shuffle_without_replacement', 'unique_samples': len(train_rows),
                          'samples_per_epoch': len(train_rows), 'coverage_guarantee': 'every row once'}
    else:
        weights, sampling_audit = sample_weights(train_rows, train_config["class_balance_alpha"],
                                                train_config.get('source_sampling_shares'))
        if optimization and hasattr(optimization, 'sampling_expectations'):
            sampling_audit.update(optimization.sampling_expectations(train_rows, weights))
        sampler = WeightedRandomSampler(
            torch.tensor(weights, dtype=torch.double), len(train_rows), replacement=True,
            generator=sampler_generator,
        )
        sampling_audit["method"] = "source_balanced_class_smoothed_weighted_replacement"
        sampling_audit["unique_samples"] = len(train_rows)
        sampling_audit["samples_per_epoch"] = len(train_rows)
        sampling_audit["coverage_guarantee"] = "無；有放回抽樣"
        sampling_audit["max_repeats_per_sample_per_epoch"] = None
    # Isolate iterator base-seed draws from model/MixUp RNG on process restart.
    loader_generators = {name: torch.Generator().manual_seed(args.seed + 100 + index)
                         for index, name in enumerate(['train', 'monitor', *val_by_source])}
    train_transform = profile.transform(config, True) if is_profile else None
    val_transform = profile.transform(config, False) if is_profile else None
    if 'augmentation_overrides' in train_config:
        train_transform = build_transform(train_config['image_size'], True,
                                          train_config['augmentation_overrides']['random_erasing_p'])
    train_loader = DataLoader(SkinDataset(train_rows, train_config["image_size"], True, train_transform), sampler=sampler,
                              generator=loader_generators['train'], **loader_args)
    monitor_loader = DataLoader(SkinDataset(monitor_rows, train_config["image_size"], False, val_transform), shuffle=False,
                                generator=loader_generators['monitor'], **loader_args)
    val_loaders = {
        source: DataLoader(SkinDataset(items, train_config["image_size"], False, val_transform), shuffle=False,
                           generator=loader_generators[source], **loader_args)
        for source, items in val_by_source.items()
    }

    inputs_path = output / 'run_inputs.json'
    if args.resume:
        if not inputs_path.is_file():
            raise RuntimeError('Resume requires original run_inputs.json; refusing restart')
        original_inputs = json.loads(inputs_path.read_text(encoding='utf-8'))
        run_id = original_inputs['contract']['run_id']
    else:
        run_id = uuid.uuid4().hex
    source_paths = [Path(__file__), ROOT / 'scripts/training_state.py', ROOT / 'scripts/coverage_sampler.py',
                    PROJECT / '第二階段/src/stage2/models.py', PROJECT / '第二階段/src/stage2/engine.py',
                    PROJECT / '第二階段/src/stage2/metrics.py']
    if is_profile:
        source_paths += profile.source_paths(config)
        weight_identity = profile.weight_identity(config)
        pretrained_sha256 = weight_identity['sha256'] if weight_identity else None
    else:
        weights_path = Path(torch.hub.get_dir()) / 'checkpoints/convnext_tiny-983f1562.pth'
        if not weights_path.is_file():
            raise RuntimeError(f'Expected cached ImageNet weights missing; no automatic download: {weights_path}')
        pretrained_sha256 = file_sha256(weights_path)
        weight_identity = {'sha256': pretrained_sha256, 'type': 'torchvision_convnext_v1'}
        if args.formal and pretrained_sha256 != config['formal_suite']['pretrained_sha256']:
            raise RuntimeError('ImageNet pretrained weight fingerprint differs')
    contract = {
        'version': 1, 'run_id': run_id, 'seed': args.seed, 'architecture': train_config['model'] + '_7_class',
        'initialization': train_config['initialization'],
        'data': data_provenance, 'training': train_config, 'class_names': config['class_names'],
        'sources': config['sources'], 'config_sha256': file_sha256(args.config),
        'sampling_method': args.sampling_method, 'max_repeats': args.max_repeats_per_epoch,
        'max_train_samples': args.max_train_samples, 'max_val_samples_per_source': args.max_val_samples_per_source,
        'prefetch_factor': args.prefetch_factor, 'device_type': device.type,
        'source_hashes': {str(p.relative_to(PROJECT)): file_sha256(p) for p in source_paths},
        'versions': {name: importlib.metadata.version(name) for name in ['torch', 'torchvision', 'numpy', 'Pillow']},
        'python': platform.python_version(),
        'pretrained_sha256': pretrained_sha256,
        'weight_identity': weight_identity,
        'worker_rng_policy': 'native_persistent_workers_not_bitwise_replayable_v1',
    }
    if is_profile:
        contract['experiment_id'] = config['experiment']['id']
        contract['profile_approval_status'] = config['experiment']['approval_status']
        if train_config['model'].startswith('convnextv2_'):
            contract['versions']['timm'] = importlib.metadata.version('timm')
    if optimization:
        contract['optimization'] = optimization.runtime_contract(config)
        contract['effective_transforms'] = {'train': repr(train_loader.dataset.transform),
                                            'validation': repr(monitor_loader.dataset.transform)}
    if args.resume and original_inputs['contract'] != contract:
        raise RuntimeError('Original run identity/configuration mismatch')
    store = CheckpointStore(output)
    state = store.load(contract) if args.resume else None
    if store.recovery_warning:
        print('WARNING: ' + store.recovery_warning, flush=True)
    if is_profile:
        model = profile.construct_model(config, restore=args.resume).to(device)
        # Epoch overrides for a separate smoke run must also bound its scheduler.
        runtime_config = dict(config, training=train_config)
        optimizer, scheduler = profile.optimizer_and_scheduler(model, runtime_config)
    else:
        model = build_model(train_config["model"], pretrained=not args.resume, num_classes=7).to(device)
        optimizer = torch.optim.AdamW(parameter_groups_with_layer_decay(
            model, train_config["learning_rate"], train_config["weight_decay"], train_config["layer_decay"]
        ))
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(epochs, 1), eta_min=1e-6)
    criterion = nn.CrossEntropyLoss(label_smoothing=train_config["label_smoothing"]).to(device)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda" and amp_enabled)
    if optimization:
        optimizer_groups = optimization.describe_groups(model, optimizer)
    history, best_score, best_record, patience, start_epoch = [], -math.inf, None, 0, 0
    best_model, stop_reason, prior_elapsed = None, None, 0.0
    if state is not None:
        model.load_state_dict(state["model"]); optimizer.load_state_dict(state["optimizer"])
        scaler.load_state_dict(state["scaler"]); scheduler.load_state_dict(state["scheduler"])
        history, best_score, best_record = state["history"], state["best_score"], state["best_record"]
        patience, start_epoch = state["bad_epochs"], state["epoch"]
        best_model, stop_reason, prior_elapsed = state['best_model'], state['stop_reason'], state['elapsed_seconds']
        # A checkpoint cannot contain the duration of writing itself. Recover the
        # matching committed timing row if it was flushed before interruption.
        for log_path in output.glob('metrics_*.jsonl'):
            for line in log_path.read_text(encoding='utf-8').splitlines():
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if (row.get('run_id') == run_id
                        and row.get('checkpoint') == store.loaded_descriptor['file']
                        and row.get('checkpoint_sha256') == store.loaded_descriptor['sha256']):
                    prior_elapsed = max(prior_elapsed, row['elapsed_seconds'])
        if isinstance(sampler, FullCoverageCappedSampler):
            sampler.set_epoch(int(state['sampler_epoch']))
        else:
            sampler_generator.set_state(state["sampler_generator_state"].cpu())
        for name, generator in loader_generators.items():
            generator.set_state(state['loader_generator_states'][name].cpu())
        export_best(output, state)
        restore_rng(state['rng'])
    else:
        atomic_json(inputs_path, {
        'contract': contract, 'run_id': run_id,
        'initial_classifier_sha256': hashlib.sha256(
            (profile.classifier(model, train_config['model']) if is_profile else model.classifier[2]).weight.detach().cpu().numpy().tobytes()).hexdigest(),
        'initial_optimizer_state_entries': len(optimizer.state),
        "data": data_provenance, "effective_training_config": train_config, "seed": args.seed,
        "device": str(device), "command": sys.argv, "test_used": False,
        "selected_train_record_ids": [row["record_id"] for row in train_rows],
        "selected_validation_record_ids": {s: [row["record_id"] for row in items] for s, items in val_by_source.items()},
        **({'optimizer_groups': optimizer_groups} if optimization else {}),
        **({'architecture_audit': optimization.model_audit(model, config)} if optimization and hasattr(optimization, 'model_audit') else {}),
        **({'sampling_audit': sampling_audit} if optimization and hasattr(optimization, 'sampling_expectations') else {}),
        })
        if optimization and hasattr(optimization, 'verify_initialization'):
            optimization.verify_initialization(json.loads(inputs_path.read_text(encoding='utf-8')))
    attempt_id = uuid.uuid4().hex
    atomic_json(output / f'attempt_{attempt_id}.json', {
        'run_id': run_id, 'seed': args.seed, 'resume': args.resume, 'start_epoch': start_epoch,
        'command': sys.argv, 'started_utc': datetime.now(timezone.utc).isoformat(),
        'recovery_warning': store.recovery_warning,
    })
    # Each attempt owns its log. Earlier (possibly uncommitted) records are retained.
    metrics_path = output / f'metrics_{attempt_id}.jsonl'
    attempt_started = time.perf_counter()
    print(f"device={device} train={len(train_rows)} monitor={len(monitor_rows)} seed={args.seed}", flush=True)
    print("抽樣設定=" + json.dumps(sampling_audit, ensure_ascii=False), flush=True)
    budget = optimization.EpochBudget(config, args.seed, run_id) if optimization else None
    for epoch_index in range(start_epoch, epochs):
        if stop_reason is not None:
            break
        if budget and not budget.begin(epoch_index + 1):
            print('預算安全邊界暫停；不開始下一輪', flush=True)
            break
        if optimization and getattr(optimization, 'TRACK_GPU_MEMORY', False) and device.type == 'cuda':
            torch.cuda.reset_peak_memory_stats(device)
        epoch_started = time.perf_counter()
        print(f"\nEpoch {epoch_index + 1}/{epochs}", flush=True)
        batch_timing = ({'data_wait_including_iterator_tqdm_seconds': 0.0,
                         'batch_processing_seconds_with_existing_loss_sync': 0.0, 'batches': 0}
                        if optimization and getattr(optimization, 'TRACK_DATA_WAIT', False) else None)
        train_loss = train_epoch(
            model, train_loader, criterion, optimizer, scaler, device,
            train_config["gradient_accumulation"], train_config["mixup_alpha"], train_config["gradient_clip_norm"],
            amp_enabled=amp_enabled, **({'timing': batch_timing} if batch_timing is not None else {}),
        )
        train_seconds = time.perf_counter() - epoch_started
        evaluation_started = time.perf_counter()
        phase_timing = optimization and getattr(optimization, 'TRACK_PHASE_TIMING', False)
        monitor_started = time.perf_counter() if phase_timing else None
        monitor = evaluate(model, monitor_loader, criterion, device, list(range(7)), "訓練監測", amp_enabled)
        monitor_seconds = time.perf_counter() - monitor_started if phase_timing else None
        validation_started = time.perf_counter() if phase_timing else None
        validation = {
            source: evaluate(model, loader, criterion, device, config["sources"][source]["supported_labels"], f"驗證 {source}", amp_enabled)
            for source, loader in val_loaders.items()
        }
        validation_seconds = time.perf_counter() - validation_started if phase_timing else None
        scores = [item["balanced_accuracy"] for item in validation.values()]
        mean_score, worst_score = float(np.mean(scores)), float(np.min(scores))
        robust_score = 0.5 * mean_score + 0.5 * worst_score
        if not all(math.isfinite(float(value)) for value in
                   [train_loss, monitor['loss'], *[v['loss'] for v in validation.values()]]):
            raise RuntimeError('Non-finite training/validation loss; previous checkpoint retained')
        gaps = {source: monitor["balanced_accuracy"] - item["balanced_accuracy"] for source, item in validation.items()}
        record = {
            "epoch": epoch_index + 1, "train_loss": train_loss, "train_monitor": monitor,
            "validation_by_source": validation, "mean_source_balanced_accuracy": mean_score,
            "worst_source_balanced_accuracy": worst_score, "robust_selection_score": robust_score,
            "train_validation_gap": gaps, "learning_rate": optimizer.param_groups[-1]["lr"],
            'train_seconds': train_seconds,
            'evaluation_seconds': time.perf_counter() - evaluation_started,
            'epoch_seconds_before_checkpoint': time.perf_counter() - epoch_started,
        }
        if optimization:
            record['learning_rates'] = [group['lr'] for group in optimizer.param_groups]
        if batch_timing is not None:
            record['batch_timing'] = batch_timing
        if optimization and getattr(optimization, 'TRACK_GPU_MEMORY', False) and device.type == 'cuda':
            record.update(cuda_allocated_peak_bytes=torch.cuda.max_memory_allocated(device),
                          cuda_reserved_peak_bytes=torch.cuda.max_memory_reserved(device))
        if phase_timing:
            record.update(train_monitor_seconds=monitor_seconds, validation_seconds=validation_seconds)
        history.append(record)
        best_score, patience, improved, stop_reason = advance_stopping(
            robust_score, best_score, patience, epoch_index + 1, train_config['min_epochs'], epochs,
            train_config['early_stopping'], train_config['early_stopping_patience'], train_config['min_delta'])
        if improved:
            best_record = record
            best_model = {name: value.detach().cpu().clone() for name, value in model.state_dict().items()}
        record.update(bad_epochs=patience, best_score=best_score, best_epoch=best_record['epoch'])
        scheduler.step()
        state = {
            'format_version': 1, 'contract': contract, 'run_id': run_id,
            "model": model.state_dict(), "optimizer": optimizer.state_dict(), "scaler": scaler.state_dict(),
            "scheduler": scheduler.state_dict(), "history": history, "best_score": best_score,
            "best_record": best_record, 'best_model': best_model, "bad_epochs": patience, "epoch": epoch_index + 1,
            'stop_reason': stop_reason, 'rng': capture_rng(),
            'loader_generator_states': {name: g.get_state() for name, g in loader_generators.items()},
            'elapsed_seconds': prior_elapsed + time.perf_counter() - attempt_started,
            "sampling_method": args.sampling_method,
            "sampler_epoch": getattr(sampler, "epoch", None),
            "sampler_generator_state": sampler_generator.get_state(),
            "data_provenance": data_provenance,
        }
        checkpoint_started = time.perf_counter()
        descriptor = store.commit(state)
        if improved:
            export_best(output, state)
        checkpoint_seconds = time.perf_counter() - checkpoint_started
        durable_record = dict(record, run_id=run_id, seed=args.seed, attempt_id=attempt_id,
                              checkpoint=descriptor['file'], checkpoint_sha256=descriptor['sha256'],
                              checkpoint_seconds=checkpoint_seconds,
                              epoch_seconds=time.perf_counter() - epoch_started,
                              elapsed_seconds=prior_elapsed + time.perf_counter() - attempt_started,
                              stop_reason=stop_reason)
        with metrics_path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(durable_record, ensure_ascii=False, allow_nan=False) + '\n')
            handle.flush()
            os.fsync(handle.fileno())
        if budget:
            budget.finish(descriptor)
        text = " ".join(f"{source}_BA={item['balanced_accuracy']:.4f}" for source, item in validation.items())
        print(f"train_loss={train_loss:.4f} monitor_BA={monitor['balanced_accuracy']:.4f} {text} robust={robust_score:.4f} bad_epochs={patience} epoch_seconds={durable_record['epoch_seconds']:.2f}", flush=True)
        if stop_reason:
            print(f"停止：{stop_reason}，bad_epochs={patience}", flush=True)
            break
        suite_stop = os.environ.get('SKINDETECT_SUITE_STOP_FILE')
        if ((output.parent / 'STOP').exists() or (output / 'STOP').exists()
                or (suite_stop and Path(suite_stop).is_file())
                or args.stop_after_epoch == epoch_index + 1):
            print('暫停於完整 epoch；使用 --resume 接續同一實驗', flush=True)
            break

    result = {
        "experiment_id": config.get('experiment', {}).get('id', config["pipeline_id"]), "seed": args.seed,
        "architecture": contract['architecture'], 'initialization': train_config['initialization'], "training_sources": sorted(val_loaders),
        "train_samples": len(train_rows), "validation_samples": {s: len(v.dataset) for s, v in val_loaders.items()},
        "samples_per_epoch": len(sampler),
        "epochs_requested": epochs, "epochs_completed": len(history),
        "stopped_early": stop_reason == 'early_stopping',
        'run_id': run_id, 'status': 'completed' if stop_reason else 'paused', 'stop_reason': stop_reason,
        'last_checkpoint': store.loaded_descriptor,
        'elapsed_seconds': prior_elapsed + time.perf_counter() - attempt_started,
        "regularization": train_config, "sampling": sampling_audit, "best": best_record,
        "history": history, "test_used": False,
        "data_provenance": data_provenance, "device": str(device),
    }
    atomic_json(output / 'result.json', result)
    print(f"已儲存：{output / 'result.json'}", flush=True)


def main():
    args = parse_args()
    output = (args.output_root or ROOT / 'results').resolve() / f'regularized_seed{args.seed}'
    with run_directory(output, args.resume):
        run_training(args, output)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        if os.environ.get('SKINDETECT_OPT_TOKEN'):
            if os.environ.get('SKINDETECT_OPT_VERSION') == 'v2_tiny_base512_relu_stage_dropout_20261026_v1':
                from v2_relu_dropout_contract import close_failed_segment
            elif os.environ.get('SKINDETECT_OPT_VERSION') == 'v2_scale512_followup_20261026_v1':
                from v2_scale_followup_contract import close_failed_segment
            elif os.environ.get('SKINDETECT_OPT_VERSION') == 'v2_scale512_seed1_20261025_v1':
                from v2_scale_contract import close_failed_segment
            elif os.environ.get('SKINDETECT_OPT_VERSION') == 'v2_512_alpha025_20261024_v1':
                from v2_alpha025_contract import close_failed_segment
            elif os.environ.get('SKINDETECT_OPT_VERSION') == 'v2_optimization_round2_20261020_v1':
                from v2_round2_contract import close_failed_segment
            else:
                from v2_opt_contract import close_failed_segment
            close_failed_segment(os.environ['SKINDETECT_OPT_TOKEN'], 'trainer_exception')
        raise
