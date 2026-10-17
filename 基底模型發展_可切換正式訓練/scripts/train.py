from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader


STAGE = Path(__file__).resolve().parents[1]
PROJECT = STAGE.parent
sys.path.insert(0, str(STAGE / "src"))
sys.path.insert(0, str(PROJECT / "資料治理與泛化修復" / "scripts"))
sys.path.insert(0, str(PROJECT / "第二階段" / "src"))

from configurable_data import (
    ConfigurableDataset,
    fit_feature_standardizer,
    load_feature_cache,
    read_csv,
)
from configurable_model import build_model
from coverage_sampler import FullCoverageCappedSampler
from train_regularized import stratified_limit, supported_source_metrics
from stage2.engine import seed_everything

try:
    from tqdm.auto import tqdm
except ImportError:  # pragma: no cover
    def tqdm(iterable, **_kwargs):
        return iterable


SUPPORTED_LABELS = {
    "HAM10000": list(range(7)),
    "BCN20000": list(range(7)),
    "PAD-UFES-20": [0, 1, 2, 4, 6],
}

# 可接受的洩漏治理通過標記。原本寫死 v1 的字串，v2 manifest 用的是
# passed_v2_content_and_group_audit，會被誤判為未通過。
# 這裡改成白名單而非略過檢查：沒有列在下面的標記一律仍然拒絕，
# 而且錯誤訊息會印出實際看到的值，方便查是哪一版的資料。
ACCEPTED_LEAKAGE_STATUS = {
    "passed_clean_manifest_v1",
    "passed_v2_content_and_group_audit",
}


def load_config(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    config = json.loads(raw.decode("utf-8-sig"))
    return config, hashlib.sha256(raw).hexdigest()


def validate_data(config: dict) -> list[dict[str, str]]:
    gate_path = PROJECT / config["data"]["governance_gate"]
    if not gate_path.is_file() or not json.loads(gate_path.read_text(encoding="utf-8-sig")).get("passed"):
        raise RuntimeError("資料治理閘門未通過")
    rows = read_csv(PROJECT / config["data"]["manifest"])
    if not rows:
        raise RuntimeError("統一資料清單為空")
    required = {
        "schema_version", "record_id", "source", "split", "image_path", "group_id",
        "label", "label_name", "training_eligible", "leakage_status",
        "anatomical_site_canonical_code",
    }
    missing = required - set(rows[0])
    if missing:
        raise RuntimeError(f"統一資料清單缺少欄位：{sorted(missing)}")
    versions = {row["schema_version"] for row in rows}
    if versions != {config["data"]["required_schema_version"]}:
        raise RuntimeError(f"資料契約版本不一致：{versions}")
    eligible = [row for row in rows if row["training_eligible"].lower() == "true"]
    unknown_status = sorted({
        row["leakage_status"] for row in eligible
        if row["leakage_status"] not in ACCEPTED_LEAKAGE_STATUS
    })
    if unknown_status:
        raise RuntimeError(f"存在未通過重複洩漏治理的訓練列：{unknown_status}")
    train_groups = {row["group_id"] for row in eligible if row["split"] == "train"}
    val_groups = {row["group_id"] for row in eligible if row["split"] == "validation"}
    overlap = train_groups & val_groups
    if overlap:
        raise RuntimeError(f"train/validation group 洩漏：{len(overlap)}")
    missing_images = [row["record_id"] for row in eligible if not (PROJECT / row["image_path"]).is_file()]
    if missing_images:
        raise RuntimeError(f"找不到 {len(missing_images)} 張影像")
    roi = config["data"]["roi"]
    if roi["enabled"]:
        missing_roi_columns = set(roi["columns"]) - set(rows[0])
        if missing_roi_columns:
            raise RuntimeError(f"ROI 已啟用，但 manifest 缺少：{sorted(missing_roi_columns)}")
    return eligible


def make_dataset(
    rows, config, train, feature_cache, feature_names, feature_mean, feature_std,
):
    return ConfigurableDataset(
        PROJECT, rows, config, train,
        feature_cache, feature_names, feature_mean, feature_std,
    )


def mixed_loss(
    logits: torch.Tensor | None,
    targets_a: torch.Tensor,
    targets_b: torch.Tensor,
    lam: float,
    criterion: nn.Module,
    ignore_index: int | None = None,
) -> torch.Tensor:
    if logits is None:
        return torch.zeros((), device=targets_a.device)

    def one(targets: torch.Tensor) -> torch.Tensor:
        if ignore_index is None:
            return criterion(logits, targets)
        valid = targets != ignore_index
        if not bool(valid.any()):
            return torch.zeros((), device=targets.device)
        return criterion(logits[valid], targets[valid])

    return lam * one(targets_a) + (1.0 - lam) * one(targets_b)


def train_epoch(model, loader, optimizer, scaler, scheduler_config, config, device) -> dict:
    model.train()
    training = config["training"]
    disease_criterion = nn.CrossEntropyLoss(label_smoothing=float(training["label_smoothing"]))
    auxiliary_criterion = nn.CrossEntropyLoss()
    accumulation = int(training["gradient_accumulation"])
    mixup_enabled = bool(training["mixup_enabled"])
    mixup_alpha = float(training["mixup_alpha"])
    site_weight = float(config["model"]["site_auxiliary"]["loss_weight"]) if config["model"]["site_auxiliary"]["enabled"] else 0.0
    source_weight = float(config["model"]["source_adversarial"]["loss_weight"]) if config["model"]["source_adversarial"]["enabled"] else 0.0
    optimizer.zero_grad(set_to_none=True)
    sums = {"total": 0.0, "disease": 0.0, "site": 0.0, "source": 0.0}
    seen = 0
    for step, batch in enumerate(tqdm(loader, desc="正式訓練", leave=False, unit="batch"), start=1):
        images, explicit, disease, site, source, _record_ids, _source_names = batch
        images, explicit = images.to(device), explicit.to(device)
        disease, site, source = disease.to(device), site.to(device), source.to(device)
        if mixup_enabled and mixup_alpha > 0:
            lam = float(np.random.beta(mixup_alpha, mixup_alpha))
            permutation = torch.randperm(images.size(0), device=device)
            mixed_images = lam * images + (1.0 - lam) * images[permutation]
            mixed_explicit = lam * explicit + (1.0 - lam) * explicit[permutation] if explicit.numel() else explicit
        else:
            lam = 1.0
            permutation = torch.arange(images.size(0), device=device)
            mixed_images, mixed_explicit = images, explicit
        with torch.amp.autocast(device_type=device.type, enabled=bool(training["amp"]) and device.type == "cuda"):
            outputs = model(mixed_images, mixed_explicit if explicit.numel() else None)
            disease_loss = mixed_loss(outputs["disease"], disease, disease[permutation], lam, disease_criterion)
            site_loss = mixed_loss(outputs["site"], site, site[permutation], lam, auxiliary_criterion, -100)
            source_loss = mixed_loss(outputs["source"], source, source[permutation], lam, auxiliary_criterion)
            total = disease_loss + site_weight * site_loss + source_weight * source_loss
            scaled = total / accumulation
        scaler.scale(scaled).backward()
        should_step = step % accumulation == 0 or step == len(loader)
        if should_step:
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), float(training["gradient_clip_norm"]))
            scaler.step(optimizer)
            scaler.update()
            optimizer.zero_grad(set_to_none=True)
        batch_size = disease.size(0)
        sums["total"] += float(total.detach()) * batch_size
        sums["disease"] += float(disease_loss.detach()) * batch_size
        sums["site"] += float(site_loss.detach()) * batch_size
        sums["source"] += float(source_loss.detach()) * batch_size
        seen += batch_size
    return {key: value / max(seen, 1) for key, value in sums.items()}


@torch.inference_mode()
def evaluate(model, loader, config, device, supported_labels: list[int], description: str) -> dict:
    model.eval()
    criterion = nn.CrossEntropyLoss(label_smoothing=float(config["training"]["label_smoothing"]))
    logits_all, targets_all = [], []
    total_loss, total_seen = 0.0, 0
    site_correct = site_seen = source_correct = source_seen = 0
    for batch in tqdm(loader, desc=description, leave=False, unit="batch"):
        images, explicit, disease, site, source, _record_ids, _source_names = batch
        images, explicit = images.to(device), explicit.to(device)
        disease, site, source = disease.to(device), site.to(device), source.to(device)
        with torch.amp.autocast(device_type=device.type, enabled=bool(config["training"]["amp"]) and device.type == "cuda"):
            outputs = model(images, explicit if explicit.numel() else None)
            loss = criterion(outputs["disease"], disease)
        total_loss += float(loss) * disease.size(0)
        total_seen += disease.size(0)
        logits_all.append(outputs["disease"].float().cpu().numpy())
        targets_all.append(disease.cpu().numpy())
        if outputs["site"] is not None:
            valid = site != -100
            site_correct += int((outputs["site"][valid].argmax(1) == site[valid]).sum())
            site_seen += int(valid.sum())
        if outputs["source"] is not None:
            source_correct += int((outputs["source"].argmax(1) == source).sum())
            source_seen += source.size(0)
    metrics = supported_source_metrics(
        np.concatenate(logits_all), np.concatenate(targets_all), supported_labels
    )
    metrics.update({
        "loss": total_loss / max(total_seen, 1),
        "samples": total_seen,
        "site_accuracy": site_correct / site_seen if site_seen else None,
        "site_labeled_samples": site_seen,
        "source_probe_accuracy": source_correct / source_seen if source_seen else None,
    })
    return metrics


def main():
    parser = argparse.ArgumentParser(description="可切換基底模型正式訓練")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--num-workers", type=int, default=None,
                        help="覆寫 config 的 num_workers；>0 讓資料載入與 GPU 重疊")
    parser.add_argument("--prefetch-factor", type=int, default=4,
                        help="每個 worker 預先準備的 batch 數；僅在 num_workers>0 時生效")
    args = parser.parse_args()
    config_path = args.config.resolve()
    config, config_hash = load_config(config_path)
    rows = validate_data(config)
    train_rows = [row for row in rows if row["split"] == "train"]
    validation_by_source = {
        source: [row for row in rows if row["split"] == "validation" and row["source"] == source]
        for source in SUPPORTED_LABELS
    }
    if args.smoke:
        train_rows = stratified_limit(train_rows, 96, int(config["seed"]) + 1)
        validation_by_source = {
            source: stratified_limit(values, 28, int(config["seed"]) + 2)
            for source, values in validation_by_source.items()
        }

    explicit_config = config["model"]["explicit_features"]
    if explicit_config["enabled"]:
        feature_cache, feature_names = load_feature_cache(PROJECT / config["data"]["explicit_feature_cache"])
        missing_features = [row["record_id"] for row in train_rows if row["record_id"] not in feature_cache]
        if missing_features:
            raise RuntimeError(f"訓練列缺少顯式特徵：{len(missing_features)}")
        feature_mean, feature_std = fit_feature_standardizer(train_rows, feature_cache, feature_names)
    else:
        feature_cache, feature_names = None, tuple()
        feature_mean = feature_std = np.empty(0, dtype=np.float32)

    seed = int(config["seed"])
    seed_everything(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    training = dict(config["training"])
    if args.smoke:
        training["epochs"] = 1
        training["early_stopping_patience"] = 1
        training["monitor_train_samples"] = min(64, len(train_rows))
        config = {**config, "training": training}

    monitor_rows = stratified_limit(
        train_rows, min(int(training["monitor_train_samples"]), len(train_rows)), seed + 3
    )
    workers = int(training["num_workers"]) if args.num_workers is None else int(args.num_workers)
    loader_options = {
        "batch_size": int(training["batch_size"]),
        "num_workers": workers,
        "pin_memory": device.type == "cuda",
    }
    if workers > 0:
        # num_workers>0 時資料增強改由子行程 RNG 產生，與 0 的既有結果
        # 分布相同但序列不同（等同換一個增強亂數流），不是逐位元重現。
        loader_options["persistent_workers"] = True
        loader_options["prefetch_factor"] = int(args.prefetch_factor)
    sampling = config["sampling"]
    if not sampling["enabled"] or sampling["method"] != "full_coverage_capped":
        raise ValueError("目前正式版本只允許關閉取樣或 full_coverage_capped；為確保全資料覆蓋，預設不可用有放回取樣")
    sampler = FullCoverageCappedSampler(
        train_rows,
        class_balance_alpha=float(sampling["class_balance_alpha"]),
        max_repeats=int(sampling["max_repeats_per_sample_per_epoch"]),
        seed=seed + 4,
    ) if sampling["enabled"] else None
    train_loader = DataLoader(
        make_dataset(train_rows, config, True, feature_cache, feature_names, feature_mean, feature_std),
        sampler=sampler, shuffle=sampler is None, **loader_options,
    )
    monitor_loader = DataLoader(
        make_dataset(monitor_rows, config, False, feature_cache, feature_names, feature_mean, feature_std),
        shuffle=False, **loader_options,
    )
    validation_loaders = {
        source: DataLoader(
            make_dataset(values, config, False, feature_cache, feature_names, feature_mean, feature_std),
            shuffle=False, **loader_options,
        ) for source, values in validation_by_source.items()
    }

    model = build_model(config, len(feature_names)).to(device)
    backbone_parameters = list(model.backbone.parameters())
    backbone_ids = {id(parameter) for parameter in backbone_parameters}
    head_parameters = [parameter for parameter in model.parameters() if id(parameter) not in backbone_ids]
    optimizer = torch.optim.AdamW([
        {
            "params": backbone_parameters,
            "lr": float(training["learning_rate"]) * float(training["backbone_learning_rate_multiplier"]),
        },
        {"params": head_parameters, "lr": float(training["learning_rate"])},
    ], weight_decay=float(training["weight_decay"]))
    epochs = int(training["epochs"])
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(epochs, 1), eta_min=1e-6)
    scaler = torch.amp.GradScaler("cuda", enabled=bool(training["amp"]) and device.type == "cuda")

    output_root = PROJECT / config["output"]["smoke_root" if args.smoke else "root"]
    output = output_root / f"{config['experiment_id']}_seed{seed}"
    output.mkdir(parents=True, exist_ok=True)
    best_path, last_path = output / "best.pt", output / "last.pt"
    history, best_score, best_record, patience, start_epoch = [], -math.inf, None, 0, 0
    if args.resume and last_path.is_file():
        state = torch.load(last_path, map_location=device, weights_only=False)
        if state.get("config_sha256") != config_hash:
            raise RuntimeError("續訓設定檔雜湊不一致；請勿用不同 config 覆蓋同一實驗")
        model.load_state_dict(state["model"])
        optimizer.load_state_dict(state["optimizer"])
        scheduler.load_state_dict(state["scheduler"])
        scaler.load_state_dict(state["scaler"])
        history, best_score, best_record = state["history"], state["best_score"], state["best_record"]
        patience, start_epoch = int(state["patience"]), int(state["epoch"])
        if sampler is not None:
            sampler.set_epoch(int(state.get("sampler_epoch", start_epoch)))

    print(f"device={device} experiment={config['experiment_id']} seed={seed}", flush=True)
    print(f"train_unique={len(train_rows)} samples_per_epoch={len(train_loader.sampler)} validation={ {k: len(v.dataset) for k, v in validation_loaders.items()} }", flush=True)
    print("feature_toggles=" + json.dumps({
        "roi": config["data"]["roi"]["enabled"],
        "preserve_aspect": config["input"]["preserve_aspect_ratio"],
        "explicit": explicit_config["enabled"],
        "site_auxiliary": config["model"]["site_auxiliary"]["enabled"],
        "source_adversarial": config["model"]["source_adversarial"]["enabled"],
    }, ensure_ascii=False), flush=True)

    for epoch_index in range(start_epoch, epochs):
        print(f"\nEpoch {epoch_index + 1}/{epochs}", flush=True)
        if sampler is not None:
            sampler.set_epoch(epoch_index)
        losses = train_epoch(model, train_loader, optimizer, scaler, scheduler, config, device)
        monitor = evaluate(model, monitor_loader, config, device, list(range(7)), "訓練監測")
        validation = {
            source: evaluate(model, loader, config, device, SUPPORTED_LABELS[source], f"驗證 {source}")
            for source, loader in validation_loaders.items()
        }
        scores = [metrics["balanced_accuracy"] for metrics in validation.values()]
        mean_score, worst_score = float(np.mean(scores)), float(np.min(scores))
        robust_score = 0.5 * mean_score + 0.5 * worst_score
        record = {
            "epoch": epoch_index + 1,
            "train_losses": losses,
            "train_monitor": monitor,
            "validation_by_source": validation,
            "mean_source_balanced_accuracy": mean_score,
            "worst_source_balanced_accuracy": worst_score,
            "robust_selection_score": robust_score,
            "learning_rates": [group["lr"] for group in optimizer.param_groups],
        }
        history.append(record)
        common_checkpoint = {
            "model": model.state_dict(),
            "config": config,
            "config_sha256": config_hash,
            "feature_names": feature_names,
            "feature_mean": feature_mean,
            "feature_std": feature_std,
            "site_classes": config["model"]["site_auxiliary"]["classes"],
            "source_classes": config["model"]["source_adversarial"]["classes"],
            "seed": seed,
            "test_used": False,
        }
        if robust_score > best_score:
            best_score, best_record, patience = robust_score, record, 0
            torch.save({**common_checkpoint, "epoch": epoch_index + 1, "selection_score": robust_score}, best_path)
        else:
            patience += 1
        scheduler.step()
        torch.save({
            **common_checkpoint,
            "optimizer": optimizer.state_dict(), "scheduler": scheduler.state_dict(), "scaler": scaler.state_dict(),
            "history": history, "best_score": best_score, "best_record": best_record,
            "patience": patience, "epoch": epoch_index + 1,
            "sampler_epoch": getattr(sampler, "epoch", None),
        }, last_path)
        source_text = " ".join(f"{name}_BA={value['balanced_accuracy']:.4f}" for name, value in validation.items())
        print(f"loss={losses['total']:.4f} monitor_BA={monitor['balanced_accuracy']:.4f} {source_text} robust={robust_score:.4f}", flush=True)
        if patience >= int(training["early_stopping_patience"]):
            print(f"提早停止：{patience} 輪未改善", flush=True)
            break

    result = {
        "experiment_id": config["experiment_id"], "seed": seed, "config_sha256": config_hash,
        "architecture": config["model"]["architecture"],
        "train_unique_samples": len(train_rows), "samples_per_epoch": len(train_loader.sampler),
        "validation_samples": {source: len(loader.dataset) for source, loader in validation_loaders.items()},
        "epochs_requested": epochs, "epochs_completed": len(history),
        "stopped_early": len(history) < epochs,
        "best": best_record, "history": history,
        "sampling": sampler.audit() if sampler is not None else {"method": "shuffle"},
        "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
        "test_used": False,
    }
    (output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"訓練完成：{output}", flush=True)


if __name__ == "__main__":
    main()

