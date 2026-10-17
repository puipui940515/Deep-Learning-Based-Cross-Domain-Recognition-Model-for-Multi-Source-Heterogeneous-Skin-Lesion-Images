"""在「治理 v1」正式訓練設定上搭載 noisefilter v2（CP-003 §6-2 的強化版）。

與 資料治理與泛化修復/scripts/train_regularized.py 的差異**只有**：
  1. 模型前面接凍結的 FilterChainV2（FilteredBackbone，ImageNet mean/std 必填）
  2. 濾鏡在 MixUp **之前**套用（對混合後的影像估計光照沒有物理意義）
  3. layer decay 參數分組改對 backbone 計算（包一層後名稱變成 backbone.features.*，
     直接沿用原函式會讓所有層落到最深層、layer decay 靜默失效）
  4. 輸出路徑、result.json 的濾鏡與校準欄位

資料、抽樣、增強、optimizer、scheduler、選模公式與治理 v1 完全相同，
因此可直接與 資料治理與泛化修復/reports/seed_variance_v1.json 比較。

    python "noisefilter_v2強化實驗/scripts/train_nf2.py" --run N0 --seed 17
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import random
import sys

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, WeightedRandomSampler

from _common import (EXP_ROOT, GOV_ROOT, PROJECT, apply_calibration, build_chain,
                     load_calibration, load_config, sha256_file)

sys.path.insert(0, str(GOV_ROOT / "scripts"))
import train_regularized as base  # noqa: E402  沿用治理 v1 的資料與評估程式碼
from noisefilter_v2 import FilteredBackbone  # noqa: E402

IMAGENET_MEAN = tuple(base.IMAGENET_MEAN)
IMAGENET_STD = tuple(base.IMAGENET_STD)


def train_epoch(model: FilteredBackbone, loader, criterion, optimizer, scaler, device,
                accumulation, mixup_alpha, clip):
    model.train()
    model.filter.eval()
    optimizer.zero_grad(set_to_none=True)
    total_loss, total_seen = 0.0, 0
    for step, (images, targets, _src) in enumerate(base.tqdm(loader, desc="訓練", leave=False, unit="batch")):
        images, targets = images.to(device), targets.to(device)
        with torch.no_grad():
            images = model.filtered_normalized(images)          # 先濾波、再 MixUp
        if mixup_alpha > 0:
            lam = float(np.random.beta(mixup_alpha, mixup_alpha))
            perm = torch.randperm(images.size(0), device=device)
            mixed, target_b = lam * images + (1 - lam) * images[perm], targets[perm]
        else:
            lam, mixed, target_b = 1.0, images, targets
        with torch.amp.autocast(device_type=device.type, enabled=device.type == "cuda"):
            logits = model.backbone(mixed)
            loss = lam * criterion(logits, targets) + (1 - lam) * criterion(logits, target_b)
        scaler.scale(loss / accumulation).backward()
        if (step + 1) % accumulation == 0 or step + 1 == len(loader):
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.backbone.parameters(), clip)
            scaler.step(optimizer)
            scaler.update()
            optimizer.zero_grad(set_to_none=True)
        total_loss += loss.item() * targets.size(0)
        total_seen += targets.size(0)
    return total_loss / total_seen


def main() -> None:
    cfg = load_config()
    ap = argparse.ArgumentParser(description="治理 v1 設定 + noisefilter v2")
    ap.add_argument("--run", choices=sorted(cfg["runs"]), required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--epochs", type=int)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--num-workers", type=int)
    ap.add_argument("--prefetch-factor", type=int, default=4)
    ap.add_argument("--max-train-samples", type=int, help="僅供 smoke test")
    ap.add_argument("--max-val-samples-per-source", type=int, help="僅供 smoke test")
    ap.add_argument("--no-pretrained", action="store_true", help="僅供離線 smoke test")
    ap.add_argument("--uncalibrated", action="store_true", help="僅供 smoke test")
    args = ap.parse_args()
    smoke = bool(args.max_train_samples or args.max_val_samples_per_source or args.no_pretrained or args.uncalibrated)

    run = cfg["runs"][args.run]
    if args.seed not in run["seeds"] and not args.max_train_samples:
        raise SystemExit(f"{args.run} 預先登記的 seeds 為 {run['seeds']}")
    run_cfg = copy.deepcopy(cfg)
    run_cfg["filter"]["stages"] = run["stages"]
    run_cfg["filter"]["alpha"] = run["alpha"]
    run_cfg["filter"]["normalize_gamma"] = run.get("normalize_gamma", False)
    run_cfg["filter"]["preset"] = run.get("preset", "default")

    gov_cfg_path = GOV_ROOT / "config.json"
    gov_cfg = json.loads(gov_cfg_path.read_text(encoding="utf-8-sig"))
    tc = dict(gov_cfg["training"])
    if args.epochs:
        tc["epochs"] = args.epochs
    if tc.get("normalization") != "imagenet_mean_std":
        raise SystemExit(f"治理設定的 normalization 為 {tc.get('normalization')}，與 wrapper 假設不符")
    gate = GOV_ROOT / "reports" / "pipeline_gate.json"
    if not gate.exists() or not json.loads(gate.read_text(encoding="utf-8-sig")).get("passed"):
        raise SystemExit("資料治理閘門未通過")

    manifest = PROJECT / cfg["manifest"]
    rows = base.read_csv(manifest)
    if {r["schema_version"] for r in rows} != {"skindetect-data-contract-v1.0"}:
        raise SystemExit("資料契約版本不一致")
    rows = [r for r in rows if r["training_eligible"].lower() == "true"]
    train_rows = base.stratified_limit([r for r in rows if r["split"] == "train"], args.max_train_samples, args.seed + 1)
    val_by_source = {
        s: base.stratified_limit([r for r in rows if r["split"] == "validation" and r["source"] == s],
                                 args.max_val_samples_per_source, args.seed + 2)
        for s in gov_cfg["sources"]
    }
    monitor_rows = base.stratified_limit(train_rows, min(1500, len(train_rows)), args.seed + 3)

    base.seed_everything(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    workers = tc["num_workers"] if args.num_workers is None else args.num_workers
    loader_args = {"batch_size": tc["batch_size"], "num_workers": workers, "pin_memory": device.type == "cuda"}
    if workers > 0:
        loader_args.update(persistent_workers=True, prefetch_factor=args.prefetch_factor)
    sampler_gen = torch.Generator().manual_seed(args.seed + 4)
    weights, sampling_audit = base.sample_weights(train_rows, tc["class_balance_alpha"])
    sampler = WeightedRandomSampler(torch.tensor(weights, dtype=torch.double), len(train_rows),
                                    replacement=True, generator=sampler_gen)
    sampling_audit["method"] = "source_balanced_class_smoothed_weighted_replacement"
    train_loader = DataLoader(base.SkinDataset(train_rows, tc["image_size"], True), sampler=sampler, **loader_args)
    monitor_loader = DataLoader(base.SkinDataset(monitor_rows, tc["image_size"], False), shuffle=False, **loader_args)
    val_loaders = {s: DataLoader(base.SkinDataset(v, tc["image_size"], False), shuffle=False, **loader_args)
                   for s, v in val_by_source.items()}

    calibration = None if args.uncalibrated else load_calibration(cfg)
    chain = build_chain(run_cfg)
    if calibration is not None:
        apply_calibration(chain, calibration)
    backbone = base.build_model(tc["model"], pretrained=not args.no_pretrained, num_classes=7)
    model = FilteredBackbone(backbone, chain, mean=IMAGENET_MEAN, std=IMAGENET_STD).to(device)
    optimizer = torch.optim.AdamW(base.parameter_groups_with_layer_decay(
        model.backbone, tc["learning_rate"], tc["weight_decay"], tc["layer_decay"]))
    criterion = nn.CrossEntropyLoss(label_smoothing=tc["label_smoothing"]).to(device)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    epochs = tc["epochs"]
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(epochs, 1), eta_min=1e-6)

    suffix = "_smoke" if smoke else ""
    output = EXP_ROOT / "results" / f"{args.run}{suffix}" / f"seed{args.seed}"
    output.mkdir(parents=True, exist_ok=True)
    best_path, last_path = output / "best.pt", output / "last.pt"
    if last_path.exists() and not args.resume:
        raise SystemExit("已有 checkpoint；請使用 --resume，避免覆寫結果")
    history, best_score, best_record, patience, start = [], -math.inf, None, 0, 0
    if args.resume and last_path.exists():
        st = torch.load(last_path, map_location=device, weights_only=False)
        model.load_state_dict(st["model"]); optimizer.load_state_dict(st["optimizer"])
        scaler.load_state_dict(st["scaler"]); scheduler.load_state_dict(st["scheduler"])
        sampler_gen.set_state(st["sampler_generator_state"].cpu())
        history, best_score, best_record = st["history"], st["best_score"], st["best_record"]
        patience, start = st["patience"], st["epoch"]
        if "rng" in st:
            random.setstate(st["rng"]["python"])
            np.random.set_state(st["rng"]["numpy"])
            torch.set_rng_state(st["rng"]["torch"].cpu())
            if device.type == "cuda" and st["rng"]["cuda"] is not None:
                torch.cuda.set_rng_state_all([v.cpu() for v in st["rng"]["cuda"]])

    filter_desc = model.filter.describe()
    print(f"run={args.run} seed={args.seed} device={device} train={len(train_rows)} filter={json.dumps(filter_desc, ensure_ascii=False)}", flush=True)
    for epoch in range(start, epochs):
        if patience >= tc["early_stopping_patience"]:
            break
        print(f"\nEpoch {epoch + 1}/{epochs}", flush=True)
        loss = train_epoch(model, train_loader, criterion, optimizer, scaler, device,
                           tc["gradient_accumulation"], tc["mixup_alpha"], tc["gradient_clip_norm"])
        monitor = base.evaluate(model, monitor_loader, criterion, device, list(range(7)), "訓練監測")
        validation = {s: base.evaluate(model, dl, criterion, device, gov_cfg["sources"][s]["supported_labels"], f"驗證 {s}")
                      for s, dl in val_loaders.items()}
        scores = [v["balanced_accuracy"] for v in validation.values()]
        mean_s, worst_s = float(np.mean(scores)), float(np.min(scores))
        robust = 0.5 * mean_s + 0.5 * worst_s
        record = {
            "epoch": epoch + 1, "train_loss": loss, "train_monitor": monitor,
            "validation_by_source": validation, "mean_source_balanced_accuracy": mean_s,
            "worst_source_balanced_accuracy": worst_s, "robust_selection_score": robust,
            "train_validation_gap": {s: monitor["balanced_accuracy"] - v["balanced_accuracy"] for s, v in validation.items()},
            "learning_rate": optimizer.param_groups[-1]["lr"],
        }
        history.append(record)
        if robust > best_score:
            best_score, best_record, patience = robust, record, 0
            torch.save({"model": model.state_dict(), "seed": args.seed, "epoch": epoch + 1,
                        "architecture": "noisefilter_v2+convnext_tiny_7_class", "initialization": "imagenet",
                        "normalization": {"mean": list(IMAGENET_MEAN), "std": list(IMAGENET_STD)},
                        "filter": filter_desc, "run": args.run, "selection_score": robust,
                        "test_used": False}, best_path)
        else:
            patience += 1
        scheduler.step()
        torch.save({"model": model.state_dict(), "optimizer": optimizer.state_dict(), "scaler": scaler.state_dict(),
                    "scheduler": scheduler.state_dict(), "history": history, "best_score": best_score,
                    "best_record": best_record, "patience": patience, "epoch": epoch + 1,
                    "sampler_generator_state": sampler_gen.get_state(),
                    "rng": {"python": random.getstate(), "numpy": np.random.get_state(),
                            "torch": torch.get_rng_state(),
                            "cuda": torch.cuda.get_rng_state_all() if device.type == "cuda" else None}}, last_path)
        print(" ".join(f"{s}_BA={v['balanced_accuracy']:.4f}" for s, v in validation.items())
              + f" robust={robust:.4f}", flush=True)
        if patience >= tc["early_stopping_patience"]:
            print(f"提早停止：{patience} epoch 未改善", flush=True)
            break

    best = best_record or {}
    vbs = best.get("validation_by_source", {})
    summary = {f"{s}_balanced_accuracy": v["balanced_accuracy"] for s, v in vbs.items()}
    if vbs:
        summary["mean_source_balanced_accuracy"] = best["mean_source_balanced_accuracy"]
        if "BCN20000" in vbs:
            summary["BCN_weighted_robust_score"] = 0.5 * best["mean_source_balanced_accuracy"] + 0.5 * vbs["BCN20000"]["balanced_accuracy"]
    result = {
        "schema_version": "skindetect-index-v1", "generator": "noisefilter_v2強化實驗/scripts/train_nf2.py",
        "experiment_id": cfg["experiment_id"], "run": args.run, "run_purpose": run["purpose"],
        "seed": args.seed, "seeds": [args.seed], "pilot": len(run["seeds"]) == 1 or bool(args.max_train_samples),
        "smoke_test": smoke,
        "baseline": cfg["baseline"], "manifest": cfg["manifest"], "manifest_sha256": sha256_file(manifest),
        "trainer_base_sha256": sha256_file(GOV_ROOT / "scripts" / "train_regularized.py"),
        "governance_config_sha256": sha256_file(gov_cfg_path),
        "filter": filter_desc,
        "calibration_file": None if calibration is None else cfg["calibration_file"],
        "calibration_sha256": None if calibration is None else sha256_file(PROJECT / cfg["calibration_file"]),
        "filter_applied_before_mixup": True,
        "training": tc, "sampling": sampling_audit,
        "train_samples": len(train_rows),
        "validation_samples": {s: len(v.dataset) for s, v in val_loaders.items()},
        "epochs_completed": len(history), "best_epoch": best.get("epoch"),
        "summary": summary, "best": best_record, "history": history,
        "test_used": False,
    }
    (output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已儲存：{output / 'result.json'}", flush=True)


if __name__ == "__main__":
    main()
