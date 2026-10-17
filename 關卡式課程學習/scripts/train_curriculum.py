from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.data import DataLoader


STAGE = Path(__file__).resolve().parents[1]
PROJECT = STAGE.parent
BASE = PROJECT / "基底模型發展_可切換正式訓練"
sys.path.insert(0, str(BASE / "src"))
sys.path.insert(0, str(PROJECT / "資料治理與泛化修復" / "scripts"))
sys.path.insert(0, str(PROJECT / "第二階段" / "src"))

from configurable_data import ConfigurableDataset, fit_feature_standardizer, load_feature_cache, read_csv
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


class DiseaseCriterion(nn.Module):
    """平衡交叉熵加上 Brier 機率品質項。"""

    def __init__(self, class_weights, label_smoothing: float, brier_weight: float, num_classes: int):
        super().__init__()
        self.register_buffer("class_weights", class_weights)
        self.label_smoothing = float(label_smoothing)
        self.brier_weight = float(brier_weight)
        self.num_classes = int(num_classes)

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        ce = F.cross_entropy(
            logits, targets, weight=self.class_weights, label_smoothing=self.label_smoothing
        )
        if self.brier_weight <= 0:
            return ce
        target_distribution = F.one_hot(targets, self.num_classes).to(logits.dtype)
        target_distribution = (
            (1.0 - self.label_smoothing) * target_distribution
            + self.label_smoothing / self.num_classes
        )
        per_sample = (logits.softmax(dim=1) - target_distribution).square().sum(dim=1)
        if self.class_weights is None:
            brier = per_sample.mean()
        else:
            weights = self.class_weights[targets]
            brier = (per_sample * weights).sum() / weights.sum().clamp_min(1e-12)
        return ce + self.brier_weight * brier


def load_config(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    return json.loads(raw.decode("utf-8-sig")), hashlib.sha256(raw).hexdigest()


def validate_data(config: dict) -> list[dict[str, str]]:
    gate_path = PROJECT / config["data"]["governance_gate"]
    if not gate_path.is_file() or not json.loads(gate_path.read_text(encoding="utf-8-sig")).get("passed"):
        raise RuntimeError("資料治理閘門未通過")
    rows = read_csv(PROJECT / config["data"]["manifest"])
    if not rows:
        raise RuntimeError("統一資料清單為空")
    required = {
        "schema_version", "record_id", "source", "split", "image_path", "group_id",
        "label", "training_eligible", "leakage_status", "anatomical_site_canonical_code",
    }
    missing = required - set(rows[0])
    if missing:
        raise RuntimeError(f"統一資料清單缺少欄位：{sorted(missing)}")
    versions = {row["schema_version"] for row in rows}
    if versions != {config["data"]["required_schema_version"]}:
        raise RuntimeError(f"資料契約版本不一致：{versions}")
    eligible = [row for row in rows if row["training_eligible"].lower() == "true"]
    if any(row["leakage_status"] != "passed_clean_manifest_v1" for row in eligible):
        raise RuntimeError("存在未通過重複洩漏治理的資料列")
    train_groups = {row["group_id"] for row in eligible if row["split"] == "train"}
    validation_groups = {row["group_id"] for row in eligible if row["split"] == "validation"}
    if train_groups & validation_groups:
        raise RuntimeError("train/validation 存在 group 洩漏")
    missing_images = [row["record_id"] for row in eligible if not (PROJECT / row["image_path"]).is_file()]
    if missing_images:
        raise RuntimeError(f"找不到 {len(missing_images)} 張影像")
    return eligible


def make_class_weights(rows: list[dict], alpha: float, device: torch.device) -> torch.Tensor:
    counts = Counter(int(row["label"]) for row in rows)
    values = np.asarray(
        [counts.get(index, 0) ** (-alpha) if counts.get(index, 0) else 0.0 for index in range(7)],
        dtype=np.float32,
    )
    present = values > 0
    values[present] /= values[present].mean()
    return torch.as_tensor(values, device=device)


def mixed_loss(logits, a, b, lam: float, criterion, ignore_index: int | None = None):
    if logits is None:
        return torch.zeros((), device=a.device)

    def one(targets):
        if ignore_index is None:
            return criterion(logits, targets)
        valid = targets != ignore_index
        if not bool(valid.any()):
            return torch.zeros((), device=targets.device)
        return criterion(logits[valid], targets[valid])

    return lam * one(a) + (1.0 - lam) * one(b)


def train_epoch(model, loader, optimizer, scaler, disease_criterion, config, stage, device):
    model.train()
    training = config["training"]
    auxiliary = nn.CrossEntropyLoss()
    accumulation = int(training["gradient_accumulation"])
    site_weight = float(config["model"]["site_auxiliary"]["loss_weight"])
    source_weight = float(stage["source_adversarial_loss_weight"])
    totals = {"total": 0.0, "disease": 0.0, "site": 0.0, "source": 0.0}
    seen = 0
    optimizer.zero_grad(set_to_none=True)
    for step, batch in enumerate(tqdm(loader, desc=stage["name"], leave=False, unit="batch"), start=1):
        images, explicit, disease, site, source, _ids, _names = batch
        images, explicit = images.to(device), explicit.to(device)
        disease, site, source = disease.to(device), site.to(device), source.to(device)
        if training["mixup_enabled"] and float(training["mixup_alpha"]) > 0:
            alpha = float(training["mixup_alpha"])
            lam = float(np.random.beta(alpha, alpha))
            permutation = torch.randperm(images.size(0), device=device)
            images = lam * images + (1.0 - lam) * images[permutation]
            if explicit.numel():
                explicit = lam * explicit + (1.0 - lam) * explicit[permutation]
        else:
            lam = 1.0
            permutation = torch.arange(images.size(0), device=device)
        with torch.amp.autocast(device_type=device.type, enabled=training["amp"] and device.type == "cuda"):
            outputs = model(images, explicit if explicit.numel() else None)
            disease_loss = mixed_loss(outputs["disease"], disease, disease[permutation], lam, disease_criterion)
            site_loss = mixed_loss(outputs["site"], site, site[permutation], lam, auxiliary, -100)
            source_loss = mixed_loss(outputs["source"], source, source[permutation], lam, auxiliary)
            total = disease_loss + site_weight * site_loss + source_weight * source_loss
        scaler.scale(total / accumulation).backward()
        if step % accumulation == 0 or step == len(loader):
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), float(training["gradient_clip_norm"]))
            scaler.step(optimizer)
            scaler.update()
            optimizer.zero_grad(set_to_none=True)
        count = disease.size(0)
        for name, value in (("total", total), ("disease", disease_loss), ("site", site_loss), ("source", source_loss)):
            totals[name] += float(value.detach()) * count
        seen += count
    return {name: value / max(seen, 1) for name, value in totals.items()}


@torch.inference_mode()
def evaluate(model, loader, criterion, config, device, supported: list[int], description: str):
    model.eval()
    logits_all, targets_all = [], []
    total_loss = total_seen = 0
    for images, explicit, disease, _site, _source, _ids, _names in tqdm(
        loader, desc=description, leave=False, unit="batch"
    ):
        images, explicit, disease = images.to(device), explicit.to(device), disease.to(device)
        with torch.amp.autocast(device_type=device.type, enabled=config["training"]["amp"] and device.type == "cuda"):
            logits = model(images, explicit if explicit.numel() else None)["disease"]
            loss = criterion(logits, disease)
        total_loss += float(loss) * disease.size(0)
        total_seen += disease.size(0)
        logits_all.append(logits.float().cpu().numpy())
        targets_all.append(disease.cpu().numpy())
    logits = np.concatenate(logits_all)
    targets = np.concatenate(targets_all)
    metrics = supported_source_metrics(logits, targets, supported)
    top2 = np.argpartition(logits, kth=-2, axis=1)[:, -2:]
    hits = (top2 == targets[:, None]).any(axis=1)
    class_hits = [float(hits[targets == label].mean()) for label in supported if bool((targets == label).any())]
    recalls = np.asarray(metrics["recall_per_class"], dtype=np.float64)
    metrics.update({
        "loss": total_loss / max(total_seen, 1),
        "samples": total_seen,
        "top2_accuracy": float(hits.mean()),
        "balanced_top2_accuracy": float(np.mean(class_hits)),
        "minimum_supported_class_recall": float(recalls[np.asarray(supported, dtype=np.int64)].min()),
    })
    return metrics


def gate_passed(metrics: dict, gate: dict) -> tuple[bool, dict]:
    checks = {
        "balanced_accuracy": metrics["balanced_accuracy"] >= float(gate["balanced_accuracy"]),
        "balanced_top2_accuracy": metrics["balanced_top2_accuracy"] >= float(gate["balanced_top2_accuracy"]),
        "minimum_class_recall": metrics["minimum_supported_class_recall"] >= float(gate["minimum_class_recall"]),
        "maximum_ece": metrics["ece"] <= float(gate["maximum_ece"]),
    }
    return all(checks.values()), checks


def make_loader(rows, config, train, cache, names, mean, std, device, sampler=None):
    dataset = ConfigurableDataset(PROJECT, rows, config, train, cache, names, mean, std)
    return DataLoader(
        dataset,
        batch_size=int(config["training"]["batch_size"]),
        num_workers=int(config["training"]["num_workers"]),
        pin_memory=device.type == "cuda",
        sampler=sampler,
        shuffle=train and sampler is None,
    )


def save_json(path: Path, value: dict):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def checkpoint_base(model, config, config_hash, feature_names, mean, std):
    return {
        "model": model.state_dict(), "config": config, "config_sha256": config_hash,
        "feature_names": feature_names, "feature_mean": mean, "feature_std": std,
        "test_used": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="皮膚病多來源關卡式課程學習")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    config_path = args.config.resolve()
    config, config_hash = load_config(config_path)
    rows = validate_data(config)
    seed = int(config["seed"])
    seed_everything(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    cache, feature_names = load_feature_cache(PROJECT / config["data"]["explicit_feature_cache"])
    output_root = PROJECT / config["output"]["smoke_root" if args.smoke else "root"]
    output = output_root / f"{config['experiment_id']}_seed{seed}"
    output.mkdir(parents=True, exist_ok=True)
    last_path = output / "last.pt"
    history, stage_summaries = [], []
    start_stage = start_epoch = gate_streak = 0
    resume_state = None
    stages = config["curriculum"]["stages"]
    model = build_model(config, len(feature_names)).to(device)

    if args.resume and last_path.is_file():
        resume_state = torch.load(last_path, map_location=device, weights_only=False)
        if resume_state["config_sha256"] != config_hash:
            raise RuntimeError("續訓設定檔雜湊不一致")
        model.load_state_dict(resume_state["model"])
        history = resume_state["history"]
        stage_summaries = resume_state["stage_summaries"]
        start_stage = int(resume_state["stage_index"])
        start_epoch = int(resume_state["stage_epoch"])
        gate_streak = int(resume_state.get("gate_streak", 0))
        if start_stage >= len(stages):
            print("所有關卡先前已完成。", flush=True)
            return 0

    print(f"device={device} experiment={config['experiment_id']} seed={seed}", flush=True)
    print("最終測試集不參與過關判定。", flush=True)

    for stage_index in range(start_stage, len(stages)):
        stage = dict(stages[stage_index])
        stage_gate = dict(config["curriculum"]["gate"])
        max_epochs = int(stage["max_epochs"])
        if args.smoke:
            max_epochs = 1
            stage_gate.update({
                "balanced_accuracy": 0.0, "balanced_top2_accuracy": 0.0,
                "minimum_class_recall": 0.0, "maximum_ece": 1.0,
                "consecutive_epochs": 1,
            })
        active_sources = set(stage["train_sources"])
        train_rows = [row for row in rows if row["split"] == "train" and row["source"] in active_sources]
        validation_rows = {
            source: [row for row in rows if row["split"] == "validation" and row["source"] == source]
            for source in stage["train_sources"]
        }
        if args.smoke:
            train_rows = stratified_limit(train_rows, 96, seed + 100 + stage_index)
            validation_rows = {
                source: stratified_limit(values, 28, seed + 200 + stage_index)
                for source, values in validation_rows.items()
            }
        missing_features = [row["record_id"] for row in train_rows if row["record_id"] not in cache]
        if missing_features:
            raise RuntimeError(f"訓練列缺少顯式特徵：{len(missing_features)}")
        mean, std = fit_feature_standardizer(train_rows, cache, feature_names)
        sampling = config["sampling"]
        sampler = FullCoverageCappedSampler(
            train_rows,
            class_balance_alpha=float(sampling["class_balance_alpha"]),
            max_repeats=int(sampling["max_repeats_per_sample_per_epoch"]),
            seed=seed + 300 + stage_index,
        ) if sampling["enabled"] else None
        train_loader = make_loader(train_rows, config, True, cache, feature_names, mean, std, device, sampler)
        validation_loaders = {
            source: make_loader(values, config, False, cache, feature_names, mean, std, device)
            for source, values in validation_rows.items()
        }
        balance = config["training"]["class_balanced_loss"]
        weights = make_class_weights(train_rows, float(balance["alpha"]), device) if balance["enabled"] else None
        criterion = DiseaseCriterion(
            weights, config["training"]["label_smoothing"], config["training"]["brier_weight"],
            config["model"]["num_disease_classes"],
        )
        backbone = list(model.backbone.parameters())
        backbone_ids = {id(parameter) for parameter in backbone}
        heads = [parameter for parameter in model.parameters() if id(parameter) not in backbone_ids]
        optimizer = torch.optim.AdamW([
            {
                "params": backbone,
                "lr": float(config["training"]["learning_rate"])
                * float(config["training"]["backbone_learning_rate_multiplier"]),
            },
            {"params": heads, "lr": float(config["training"]["learning_rate"])},
        ], weight_decay=float(config["training"]["weight_decay"]))
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(max_epochs, 1), eta_min=1e-6)
        scaler = torch.amp.GradScaler("cuda", enabled=config["training"]["amp"] and device.type == "cuda")
        stage_epoch_start = start_epoch if stage_index == start_stage else 0
        current_streak = gate_streak if stage_index == start_stage else 0
        best_stage_score, plateau = -math.inf, 0
        if resume_state is not None and stage_index == start_stage and stage_epoch_start > 0:
            optimizer.load_state_dict(resume_state["optimizer"])
            scheduler.load_state_dict(resume_state["scheduler"])
            scaler.load_state_dict(resume_state["scaler"])
            best_stage_score = float(resume_state["best_stage_score"])
            plateau = int(resume_state["plateau"])

        print(f"\n=== {stage['name']} ===", flush=True)
        print(
            f"來源={stage['train_sources']} 唯一樣本={len(train_rows)} "
            f"每輪樣本={len(train_loader.sampler)} 過關來源={stage['gate_source']}", flush=True,
        )
        passed, fail_reason = False, "maximum_epochs"
        for epoch_index in range(stage_epoch_start, max_epochs):
            if sampler is not None:
                sampler.set_epoch(epoch_index)
            losses = train_epoch(model, train_loader, optimizer, scaler, criterion, config, stage, device)
            validation = {
                source: evaluate(model, loader, criterion, config, device, SUPPORTED_LABELS[source], f"驗證 {source}")
                for source, loader in validation_loaders.items()
            }
            gate_metrics = validation[stage["gate_source"]]
            passed_now, checks = gate_passed(gate_metrics, stage_gate)
            current_streak = current_streak + 1 if passed_now else 0
            score = (
                gate_metrics["balanced_accuracy"]
                + 0.25 * gate_metrics["balanced_top2_accuracy"]
                - 0.25 * gate_metrics["ece"]
            )
            common = checkpoint_base(model, config, config_hash, feature_names, mean, std)
            if score > best_stage_score:
                best_stage_score, plateau = score, 0
                torch.save({
                    **common, "stage_index": stage_index, "stage_epoch": epoch_index + 1,
                    "metrics": gate_metrics,
                }, output / f"{stage['id']}_best.pt")
            else:
                plateau += 1
            record = {
                "global_epoch": len(history) + 1, "stage_index": stage_index,
                "stage_id": stage["id"], "stage_name": stage["name"],
                "stage_epoch": epoch_index + 1, "train_sources": stage["train_sources"],
                "gate_source": stage["gate_source"], "train_losses": losses,
                "validation_by_source": validation, "gate_checks": checks,
                "gate_streak": current_streak,
                "gate_required_streak": int(stage_gate["consecutive_epochs"]),
            }
            history.append(record)
            scheduler.step()
            checkpoint = {
                **common, "optimizer": optimizer.state_dict(), "scheduler": scheduler.state_dict(),
                "scaler": scaler.state_dict(), "history": history, "stage_summaries": stage_summaries,
                "stage_index": stage_index, "stage_epoch": epoch_index + 1,
                "gate_streak": current_streak, "best_stage_score": best_stage_score,
                "plateau": plateau,
            }
            torch.save(checkpoint, last_path)
            save_json(output / "progress.json", {
                "status": "running", "current_stage": stage["id"],
                "stage_epoch": epoch_index + 1, "gate_streak": current_streak,
                "gate_required_streak": int(stage_gate["consecutive_epochs"]),
                "latest_gate_metrics": gate_metrics, "history": history, "test_used": False,
            })
            source_text = " ".join(
                f"{source}_BA={metrics['balanced_accuracy']:.4f} Top2={metrics['balanced_top2_accuracy']:.4f}"
                for source, metrics in validation.items()
            )
            print(
                f"epoch={epoch_index + 1}/{max_epochs} loss={losses['total']:.4f} {source_text} "
                f"ECE={gate_metrics['ece']:.4f} 最低召回={gate_metrics['minimum_supported_class_recall']:.4f} "
                f"連續通過={current_streak}/{stage_gate['consecutive_epochs']}", flush=True,
            )
            if current_streak >= int(stage_gate["consecutive_epochs"]):
                passed = True
                torch.save(checkpoint, output / f"{stage['id']}_mastery.pt")
                break
            if plateau >= int(stage["plateau_patience"]):
                fail_reason = "plateau_before_mastery"
                break

        summary = {
            "stage_index": stage_index, "stage_id": stage["id"], "stage_name": stage["name"],
            "passed": passed, "failure_reason": None if passed else fail_reason,
            "epochs_completed": history[-1]["stage_epoch"], "gate_source": stage["gate_source"],
            "last_gate_metrics": history[-1]["validation_by_source"][stage["gate_source"]],
        }
        stage_summaries.append(summary)
        if not passed:
            save_json(output / "result.json", {
                "status": "gate_failed", "failed_stage": stage["id"],
                "failure_reason": fail_reason, "stage_summaries": stage_summaries,
                "history": history, "config_sha256": config_hash, "test_used": False,
            })
            print(f"關卡未通過，流程停止：{stage['name']}（{fail_reason}）", flush=True)
            return 2

        transition = {
            **checkpoint_base(model, config, config_hash, feature_names, mean, std),
            "optimizer": None, "scheduler": None, "scaler": None,
            "history": history, "stage_summaries": stage_summaries,
            "stage_index": stage_index + 1, "stage_epoch": 0,
            "gate_streak": 0, "best_stage_score": -math.inf, "plateau": 0,
        }
        torch.save(transition, last_path)
        print(f"關卡通過：{stage['name']}，進入下一關。", flush=True)
        resume_state = None

    final_checkpoint = checkpoint_base(model, config, config_hash, feature_names, mean, std)
    torch.save({**final_checkpoint, "stage_summaries": stage_summaries}, output / "curriculum_mastery.pt")
    save_json(output / "result.json", {
        "status": "all_stages_passed", "stage_summaries": stage_summaries,
        "history": history, "config_sha256": config_hash,
        "parameter_count": sum(parameter.numel() for parameter in model.parameters()), "test_used": False,
    })
    save_json(output / "progress.json", {
        "status": "all_stages_passed", "stage_summaries": stage_summaries, "test_used": False,
    })
    print(f"全部關卡通過：{output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
