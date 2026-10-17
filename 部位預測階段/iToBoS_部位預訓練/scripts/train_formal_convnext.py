from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from formal_site_model import (
    SiteDataset,
    build_model,
    build_transform,
    classification_metrics,
    count_parameters,
    map_body_part,
    parameter_groups_with_layer_decay,
    seed_worker,
    shuffled_labels,
    stratified_split,
    weighted_cross_entropy,
)


def seed_everything(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def load_rows(metadata_path: Path, split: str):
    rows = []
    with metadata_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            site = map_body_part(row["body_part"])
            if row["split"].strip().lower() == split and site is not None:
                rows.append({"image_id": row["image_id"], "site": site})
    if not rows:
        raise RuntimeError(f"split={split} 沒有可用資料")
    return rows


def run_epoch(model, loader, criterion, device, site_classes, accumulation, optimizer=None, scaler=None):
    training = optimizer is not None
    model.train(training)
    total_loss = 0.0
    targets_all, predictions_all, ids_all = [], [], []
    if training:
        optimizer.zero_grad(set_to_none=True)
    for step, (images, targets, image_ids) in enumerate(loader):
        images, targets = images.to(device), targets.to(device)
        with torch.set_grad_enabled(training):
            with torch.amp.autocast(device_type=device.type, enabled=device.type == "cuda"):
                logits = model(images)
                loss = criterion(logits, targets)
            if training:
                scaler.scale(loss / accumulation).backward()
                should_step = (step + 1) % accumulation == 0 or step + 1 == len(loader)
                if should_step:
                    scaler.step(optimizer)
                    scaler.update()
                    optimizer.zero_grad(set_to_none=True)
        total_loss += loss.item() * targets.size(0)
        targets_all.extend(targets.detach().cpu().tolist())
        predictions_all.extend(logits.argmax(dim=1).detach().cpu().tolist())
        ids_all.extend(image_ids)
    metrics = classification_metrics(targets_all, predictions_all, site_classes)
    metrics["loss"] = total_loss / len(loader.dataset)
    return metrics, ids_all, targets_all, predictions_all


def make_loader(rows, images_dir, config, site_classes, training, seed):
    dataset = SiteDataset(
        rows,
        images_dir,
        site_classes,
        build_transform(config, training),
        training,
        config["horizontal_flip"]["probability"] if training else 0.0,
    )
    generator = torch.Generator().manual_seed(seed)
    loader = DataLoader(
        dataset,
        batch_size=config["batch_size"],
        shuffle=training,
        generator=generator,
        num_workers=config["num_workers"],
        pin_memory=torch.cuda.is_available(),
        persistent_workers=config["num_workers"] > 0,
        worker_init_fn=seed_worker,
    )
    return dataset, loader


def save_predictions(path, ids, targets, predictions):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["image_id", "target", "prediction"])
        writer.writerows(zip(ids, targets, predictions))


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["develop", "refit", "test"], required=True)
    parser.add_argument("--label-mode", choices=["true", "shuffled"], required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--refit-epochs", type=int)
    parser.add_argument("--unlock-official-test", default="")
    parser.add_argument(
        "--config",
        default=str(ROOT / "config/formal_convnext_tiny_384_v1.json"),
    )
    return parser.parse_args()


def main():
    args = parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if config["status"] != "approved_for_training":
        raise SystemExit("正式設定尚未經使用者審核：status 不是 approved_for_training")
    if args.seed not in config["seeds"]:
        raise SystemExit(f"seed 必須為 {config['seeds']}")
    seed_everything(args.seed)

    dataset_root = (ROOT / config["dataset_root"]).resolve()
    metadata_path = dataset_root / config["metadata_file"]
    images_dir = dataset_root / config["images_directory"]
    if not metadata_path.exists() or not images_dir.is_dir():
        raise SystemExit(f"資料路徑無效：{dataset_root}")

    site_classes = config["site_classes"]
    train_rows = load_rows(metadata_path, config["training_source_split"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    output_key = f"{args.label_mode}_seed{args.seed}"
    checkpoints = ROOT / "checkpoints" / "formal_v1"
    results = ROOT / "results" / "formal_v1"
    checkpoints.mkdir(parents=True, exist_ok=True)
    results.mkdir(parents=True, exist_ok=True)

    if args.phase == "develop":
        fit_rows, validation_rows = stratified_split(
            train_rows, config["development_validation_fraction"], args.seed
        )
        if args.label_mode == "shuffled":
            fit_rows = shuffled_labels(fit_rows, args.seed)
        epoch_limit = config["max_development_epochs"]
        checkpoint_path = checkpoints / f"develop_{output_key}.pt"
    elif args.phase == "refit":
        if not args.refit_epochs or args.refit_epochs < 1:
            raise SystemExit("refit 必須明確提供已凍結的 --refit-epochs")
        fit_rows, validation_rows = train_rows, None
        if args.label_mode == "shuffled":
            fit_rows = shuffled_labels(fit_rows, args.seed)
        epoch_limit = args.refit_epochs
        checkpoint_path = checkpoints / f"refit_{output_key}.pt"
    else:
        if args.unlock_official_test != "I_UNDERSTAND_TEST_IS_SEALED":
            raise SystemExit("官方 test 仍封存；缺少明確解鎖字串")
        lock = results / f"OFFICIAL_TEST_OPENED_{output_key}.lock"
        if lock.exists():
            raise SystemExit(f"此組官方 test 已經開啟過：{lock}")
        checkpoint_path = checkpoints / f"refit_{output_key}.pt"
        if not checkpoint_path.exists():
            raise SystemExit(f"缺少 refit checkpoint：{checkpoint_path}")
        test_rows = load_rows(metadata_path, config["sealed_test_split"])
        _, test_loader = make_loader(
            test_rows, images_dir, config, site_classes, False, args.seed
        )
        model = build_model(len(site_classes), pretrained=False).to(device)
        state = torch.load(checkpoint_path, map_location=device, weights_only=False)
        model.load_state_dict(state["model"])
        criterion, _, _ = weighted_cross_entropy(train_rows, site_classes, device)
        lock.write_text(
            json.dumps({"opened_at": time.time(), "checkpoint": str(checkpoint_path)}),
            encoding="utf-8",
        )
        metrics, ids, targets, predictions = run_epoch(
            model, test_loader, criterion, device, site_classes, 1
        )
        save_predictions(results / f"official_test_predictions_{output_key}.csv", ids, targets, predictions)
        payload = {
            "phase": "test",
            "label_mode": args.label_mode,
            "seed": args.seed,
            "subject_disjoint": True,
            "single_use_gate": True,
            "metrics": metrics,
            "checkpoint": str(checkpoint_path),
        }
        (results / f"official_test_{output_key}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(metrics, ensure_ascii=False), flush=True)
        return

    fit_set, fit_loader = make_loader(
        fit_rows, images_dir, config, site_classes, True, args.seed
    )
    validation_loader = None
    if validation_rows is not None:
        _, validation_loader = make_loader(
            validation_rows, images_dir, config, site_classes, False, args.seed
        )

    model = build_model(len(site_classes), pretrained=True).to(device)
    groups = parameter_groups_with_layer_decay(
        model,
        config["base_learning_rate"],
        config["weight_decay"],
        config["layer_decay"],
    )
    optimizer = torch.optim.AdamW(groups)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epoch_limit)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    criterion, counts, weights = weighted_cross_entropy(fit_rows, site_classes, device)

    history, best_score, best_epoch, patience = [], -1.0, None, 0
    started = time.time()
    last_metrics = None
    for epoch in range(epoch_limit):
        training_metrics, _, _, _ = run_epoch(
            model,
            fit_loader,
            criterion,
            device,
            site_classes,
            config["gradient_accumulation"],
            optimizer,
            scaler,
        )
        if validation_loader is not None:
            validation_metrics, ids, targets, predictions = run_epoch(
                model, validation_loader, criterion, device, site_classes, 1
            )
            score = validation_metrics["balanced_accuracy"]
            history.append(
                {"epoch": epoch + 1, "train": training_metrics, "validation": validation_metrics}
            )
            if score > best_score:
                best_score, best_epoch, patience = score, epoch + 1, 0
                torch.save(
                    {
                        "model": model.state_dict(),
                        "site_classes": site_classes,
                        "architecture": config["architecture"],
                        "image_size": config["image_size"],
                        "phase": args.phase,
                        "label_mode": args.label_mode,
                        "seed": args.seed,
                        "epoch": epoch + 1,
                    },
                    checkpoint_path,
                )
                save_predictions(
                    results / f"develop_best_predictions_{output_key}.csv",
                    ids,
                    targets,
                    predictions,
                )
            else:
                patience += 1
            print(
                f"phase=develop mode={args.label_mode} seed={args.seed} epoch={epoch+1} "
                f"train_BA={training_metrics['balanced_accuracy']:.4f} val_BA={score:.4f}",
                flush=True,
            )
            if patience >= config["early_stopping_patience"]:
                break
        else:
            last_metrics = training_metrics
            history.append({"epoch": epoch + 1, "train": training_metrics})
            print(
                f"phase=refit mode={args.label_mode} seed={args.seed} epoch={epoch+1} "
                f"train_BA={training_metrics['balanced_accuracy']:.4f}",
                flush=True,
            )
        scheduler.step()

    if args.phase == "refit":
        torch.save(
            {
                "model": model.state_dict(),
                "site_classes": site_classes,
                "architecture": config["architecture"],
                "image_size": config["image_size"],
                "phase": args.phase,
                "label_mode": args.label_mode,
                "seed": args.seed,
                "epoch": epoch_limit,
            },
            checkpoint_path,
        )

    payload = {
        "phase": args.phase,
        "label_mode": args.label_mode,
        "seed": args.seed,
        "architecture": config["architecture"],
        "parameters": count_parameters(model),
        "image_size": config["image_size"],
        "fit_size": len(fit_set),
        "validation_size": 0 if validation_rows is None else len(validation_rows),
        "validation_is_subject_disjoint": False if validation_rows is not None else None,
        "official_test_used": False,
        "best_epoch": best_epoch,
        "best_validation_balanced_accuracy": None if best_epoch is None else best_score,
        "last_train_metrics": last_metrics,
        "class_counts": dict(counts),
        "class_weights": dict(zip(site_classes, weights)),
        "history": history,
        "elapsed_seconds": time.time() - started,
        "checkpoint": str(checkpoint_path),
    }
    (results / f"{args.phase}_{output_key}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()

