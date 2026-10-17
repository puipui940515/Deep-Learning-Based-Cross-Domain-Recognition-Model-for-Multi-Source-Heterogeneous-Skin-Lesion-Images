from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))
from stage2.data import ManifestDataset, build_transform
from stage2.engine import append_log, run_epoch, seed_everything
from stage2.losses import LogitAdjustedCrossEntropy
from stage2.models import build_model, count_parameters, parameter_groups_with_layer_decay



def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", choices=["v5","v6","v7","v8","v9","v10"], required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--dataset-root", type=Path)
    parser.add_argument("--resume", action="store_true", help="從同版本、同 seed 的最佳 checkpoint 繼續")
    parser.add_argument("--num-workers", type=int, default=None,
                        help="覆寫 config 的 num_workers。>0 可讓資料載入與 GPU 重疊，"
                             "但會改變資料增強的隨機序列（見下方註解）")
    parser.add_argument("--prefetch-factor", type=int, default=4,
                        help="每個 worker 預先準備的 batch 數；僅在 num_workers>0 時生效")
    args = parser.parse_args()
    config = json.loads((ROOT / "config/stage2.json").read_text(encoding="utf-8-sig"))
    if args.seed not in config["seeds"]: raise SystemExit(f"seed 必須為 {config['seeds']}")
    gate_path = PROJECT_ROOT / "驗證/reports/validation_gate.json"
    if not gate_path.exists() or not json.loads(gate_path.read_text(encoding="utf-8-sig")).get("passed", False):
        raise SystemExit("根目錄驗證閘門未通過")
    spec = config["versions"][args.version]
    manifest = ROOT / config["split_manifest"]
    dataset_root = args.dataset_root or (ROOT / config["dataset_root"]).resolve()
    seed_everything(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_set = ManifestDataset(manifest, dataset_root, "train", build_transform(spec["image_size"], True))
    val_set = ManifestDataset(manifest, dataset_root, "val", build_transform(spec["image_size"], False))
    # 吞吐設定。num_workers>0 時，資料增強改由子行程的 RNG 產生，
    # 因此與 num_workers=0 的既有結果「不是逐位元相同」——分布相同、序列不同，
    # 效果等同換一個增強亂數流。跨此設定比較單次 run 前請先看 開發歷程/時間軸.md 的說明。
    workers = config["num_workers"] if args.num_workers is None else args.num_workers
    loader_args = {"batch_size": spec["batch_size"], "num_workers": workers,
                   "pin_memory": device.type == "cuda"}
    if workers > 0:
        loader_args["persistent_workers"] = True
        loader_args["prefetch_factor"] = args.prefetch_factor
    generator = torch.Generator().manual_seed(args.seed)
    train_loader = DataLoader(train_set, shuffle=True, generator=generator, **loader_args)
    val_loader = DataLoader(val_set, shuffle=False, **loader_args)
    model = build_model(spec["model"], spec["pretrained"], config["num_classes"]).to(device)
    if spec["layer_decay"]:
        groups = parameter_groups_with_layer_decay(model, config["base_learning_rate"], config["weight_decay"], config["layer_decay"])
        optimizer = torch.optim.AdamW(groups)
    else:
        optimizer = torch.optim.AdamW(model.parameters(), lr=config["base_learning_rate"], weight_decay=config["weight_decay"])
    with manifest.open("r", encoding="utf-8-sig", newline="") as handle:
        counts = Counter(int(r["label"]) for r in csv.DictReader(handle) if r["split"] == "train")
    criterion = (LogitAdjustedCrossEntropy([counts[i] for i in range(7)], config["logit_adjustment_tau"])
                 if spec["loss"] == "logit_adjusted_ce" else nn.CrossEntropyLoss()).to(device)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    checkpoint = ROOT / f"checkpoints/{args.version}_seed{args.seed}.pt"
    best_score, patience, history, best_record = -1.0, 0, [], None
    start_epoch = 0
    if args.resume and checkpoint.exists():
        state = torch.load(checkpoint, map_location=device, weights_only=False)
        model.load_state_dict(state["model"])
        optimizer.load_state_dict(state["optimizer"])
        if "scaler" in state:
            scaler.load_state_dict(state["scaler"])
        best_score = state["best_score"]
        best_record = state.get("best_record")
        history = state.get("history", [])
        start_epoch = state["epoch"] + 1
        print(f"resume {args.version} seed={args.seed} from epoch={start_epoch}", flush=True)
    for epoch in range(start_epoch, args.epochs or config["epochs"]):
        train_metrics = run_epoch(model, train_loader, criterion, device, optimizer, scaler, spec["gradient_accumulation"])
        val_metrics = run_epoch(model, val_loader, criterion, device)
        record = {"epoch": epoch + 1, "train": train_metrics, "val": val_metrics}; history.append(record)
        score = val_metrics["balanced_accuracy"]
        if score > best_score:
            best_score, patience, best_record = score, 0, record
            checkpoint.parent.mkdir(parents=True, exist_ok=True)
            torch.save({"epoch": epoch, "model": model.state_dict(), "optimizer": optimizer.state_dict(),
                        "scaler": scaler.state_dict(), "best_score": best_score,
                        "best_record": best_record, "history": history,
                        "version": args.version, "seed": args.seed}, checkpoint)
        else: patience += 1
        print(f"{args.version} seed={args.seed} epoch={epoch+1} train_BA={train_metrics['balanced_accuracy']:.4f} val_BA={score:.4f}", flush=True)
        if patience >= config["early_stopping_patience"]: break
    result = {"version": args.version, "seed": args.seed, "spec": spec, "parameters": count_parameters(model),
              "device": str(device), "best": best_record, "history": history, "test_used": False,
              "num_workers": workers,
              "prefetch_factor": args.prefetch_factor if workers > 0 else None}
    (ROOT / "results").mkdir(parents=True, exist_ok=True)
    (ROOT / f"results/{args.version}_seed{args.seed}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    append_log(ROOT / "results/experiment_log.csv", {"version": args.version,"seed": args.seed,"model": spec["model"],
               "pretrained": spec["pretrained"],"image_size": spec["image_size"],"loss": spec["loss"],
               "parameters": result["parameters"],"epochs_completed": len(history),"best_epoch": best_record["epoch"],
               "train_balanced_accuracy": best_record["train"]["balanced_accuracy"],
               "val_balanced_accuracy": best_record["val"]["balanced_accuracy"],
               "train_val_gap": best_record["train"]["balanced_accuracy"]-best_record["val"]["balanced_accuracy"],
               "val_macro_f1": best_record["val"]["macro_f1"],"val_ece": best_record["val"]["ece"],
               "best_checkpoint": str(checkpoint.relative_to(ROOT)),"notes":"test split 未使用"})


if __name__ == "__main__":
    main()
