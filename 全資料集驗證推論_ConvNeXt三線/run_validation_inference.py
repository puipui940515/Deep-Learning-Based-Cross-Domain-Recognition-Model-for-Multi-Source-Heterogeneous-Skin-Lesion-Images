from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset

Image.MAX_IMAGE_PIXELS = 500_000_000

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
DATASET = PROJECT / "Dataset"
STAGE2 = PROJECT / "第二階段"
sys.path.insert(0, str(STAGE2 / "src"))

from stage2.data import build_transform
from stage2.models import build_model

CLASS_NAMES = {
    0: "AKIEC",
    1: "BCC",
    2: "BKL",
    3: "DF",
    4: "NV",
    5: "VASC",
    6: "MEL",
}

BCN_MAP = {"AK": 0, "BCC": 1, "BKL": 2, "DF": 3, "NV": 4, "VASC": 5, "MEL": 6}
PAD_MAP = {"ACK": 0, "BCC": 1, "SEK": 2, "NEV": 4, "MEL": 6}
ISIC_SPECS = [
    ("basal_cell_carcinoma", "BCC", 1),
    ("melanoma", "MEL", 6),
    ("squamous_cell_carcinoma", "SCC", None),
]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def add_row(rows, source, eval_group, category, image_path, label, label_status, split="validation"):
    resolved = (PROJECT / image_path).resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    rows.append({
        "row_id": len(rows),
        "source": source,
        "eval_group": eval_group,
        "split": split,
        "category": category,
        "image_path": resolved.relative_to(PROJECT).as_posix(),
        "label": int(label),
        "label_name": CLASS_NAMES[int(label)],
        "label_status": label_status,
    })


def build_eval_manifest() -> tuple[list[dict], dict]:
    rows: list[dict] = []
    excluded = defaultdict(int)

    for row in read_csv(STAGE2 / "data/fixed_split.csv"):
        if row["split"] != "val":
            excluded[f"HAM10000_{row['split']}_not_evaluated"] += 1
            continue
        add_row(
            rows,
            "HAM10000",
            "HAM10000_validation",
            row["label"],
            Path("Dataset/HAM10000") / row["image_path"],
            int(row["label"]),
            "native_validation",
        )

    bcn_meta = {r["bcn_filename"]: r for r in read_csv(DATASET / "BCN20000/metadata/available_train.csv")}
    for row in read_csv(PROJECT / "部位預測階段/data/profiles/bcn.csv"):
        if row["split"] != "val":
            continue
        filename = Path(row["image_path"]).name
        meta = bcn_meta.get(filename)
        if meta is None:
            excluded["BCN20000_val_missing_metadata"] += 1
            continue
        diagnosis = meta["diagnosis"]
        if diagnosis not in BCN_MAP:
            excluded[f"BCN20000_val_unmapped_{diagnosis}"] += 1
            continue
        add_row(
            rows,
            "BCN20000",
            "BCN20000_internal_validation_mapped",
            diagnosis,
            Path(row["image_path"]),
            BCN_MAP[diagnosis],
            "internal_validation_mapped",
        )

    pad_index = {p.name: p for p in (DATASET / "PAD-UFES-20/all_images").rglob("*") if p.is_file()}
    for row in read_csv(DATASET / "PAD-UFES-20/metadata.csv"):
        diagnosis = row["diagnostic"]
        if diagnosis not in PAD_MAP:
            excluded[f"PAD-UFES-20_unmapped_{diagnosis}"] += 1
            continue
        path = pad_index.get(row["img_id"])
        if path is None:
            excluded["PAD-UFES-20_missing_image"] += 1
            continue
        add_row(
            rows,
            "PAD-UFES-20",
            "PAD-UFES-20_external_mapped_eval",
            diagnosis,
            path.relative_to(PROJECT),
            PAD_MAP[diagnosis],
            "external_mapped_no_native_validation_split",
            split="external_eval",
        )

    for directory, category, label in ISIC_SPECS:
        paths = sorted(
            p for p in (DATASET / "ISIC_Archive" / directory).rglob("*")
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
        )
        if label is None:
            excluded[f"ISIC_Archive_unmapped_{category}"] += len(paths)
            continue
        for path in paths:
            add_row(
                rows,
                "ISIC_Archive",
                "ISIC_Archive_external_mapped_eval",
                category,
                path.relative_to(PROJECT),
                label,
                "external_query_mapped_no_native_validation_split",
                split="external_eval",
            )

    scin_count = sum(len(read_csv(path)) for path in (DATASET / "SCIN/metadata").glob("*.csv"))
    excluded["SCIN_incompatible_with_HAM10000_7class"] = scin_count
    excluded["DensePose_COCO_body_part_not_skin_disease"] = 1
    excluded["iToBoS2024TBP_body_site_not_HAM10000_7class"] = 1

    out_manifest = ROOT / "validation_eval_manifest.csv"
    with out_manifest.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = ["row_id", "source", "eval_group", "split", "category", "image_path", "label", "label_name", "label_status"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    return rows, dict(excluded)


class EvalDataset(Dataset):
    def __init__(self, rows: list[dict], image_size: int):
        self.rows = rows
        self.transform = build_transform(image_size, train=False)
        self.image_size = image_size

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        with Image.open(PROJECT / row["image_path"]) as image:
            if image.format == "TIFF" and getattr(image, "n_frames", 1) > 1:
                selected = 0
                for frame in range(image.n_frames):
                    image.seek(frame)
                    if min(image.size) >= self.image_size:
                        selected = frame
                    else:
                        break
                image.seek(selected)
            elif image.format == "JPEG":
                image.draft("RGB", (self.image_size, self.image_size))
            tensor = self.transform(image.convert("RGB"))
        return tensor, index


def model_specs(paired_only: bool):
    specs = []
    pure_seeds = [17, 42] if paired_only else [17, 42, 2026]
    imagenet_seeds = [17, 42] if paired_only else [17, 42, 2026]
    anatomy_seeds = [17, 42]
    for seed in pure_seeds:
        specs.append(("pure_convnext_tiny", seed, STAGE2 / f"checkpoints/v10_seed{seed}.pt"))
    for seed in imagenet_seeds:
        specs.append(("imagenet_convnext_tiny", seed, STAGE2 / f"部位權重完整微調正式對照/results/imagenet_init/seed{seed}/best.pt"))
    for seed in anatomy_seeds:
        specs.append(("anatomy_pretrained_convnext_tiny", seed, STAGE2 / f"部位權重完整微調正式對照/results/densepose_true_init/seed{seed}/best.pt"))
    return specs


def load_model(checkpoint_path: Path, device):
    if not checkpoint_path.exists():
        raise FileNotFoundError(checkpoint_path)
    model = build_model("convnext_tiny", False, 7)
    state = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    model.load_state_dict(state["model"])
    return model.to(device).eval()


def balanced_accuracy(y_true, y_pred):
    labels = sorted(set(int(x) for x in y_true))
    if not labels:
        return None
    recalls = []
    for label in labels:
        idx = [i for i, y in enumerate(y_true) if int(y) == label]
        recalls.append(sum(int(y_pred[i]) == label for i in idx) / len(idx))
    return sum(recalls) / len(recalls)


def macro_f1(y_true, y_pred):
    labels = sorted(set(int(x) for x in y_true))
    if not labels:
        return None
    f1s = []
    for label in labels:
        tp = sum(int(t) == label and int(p) == label for t, p in zip(y_true, y_pred))
        fp = sum(int(t) != label and int(p) == label for t, p in zip(y_true, y_pred))
        fn = sum(int(t) == label and int(p) != label for t, p in zip(y_true, y_pred))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return sum(f1s) / len(f1s)


def summarize_metrics(rows: list[dict], predictions: list[dict]) -> list[dict]:
    row_by_id = {int(r["row_id"]): r for r in rows}
    grouped = defaultdict(list)
    for pred in predictions:
        row = row_by_id[int(pred["row_id"])]
        for group in ["ALL_MAPPED", row["eval_group"], row["source"]]:
            grouped[(pred["condition"], pred["seed"], group)].append((row["label"], pred["pred_label"]))
    metric_rows = []
    for (condition, seed, group), pairs in sorted(grouped.items()):
        y_true = [int(a) for a, _ in pairs]
        y_pred = [int(b) for _, b in pairs]
        metric_rows.append({
            "condition": condition,
            "seed": seed,
            "group": group,
            "samples": len(pairs),
            "balanced_accuracy": balanced_accuracy(y_true, y_pred),
            "macro_f1": macro_f1(y_true, y_pred),
            "accuracy": sum(t == p for t, p in zip(y_true, y_pred)) / len(y_true),
        })
    return metric_rows


def write_metrics_summary(metric_rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in metric_rows:
        grouped[(row["condition"], row["group"])].append(row)
    summary = []
    for (condition, group), rows in sorted(grouped.items()):
        for metric in ["balanced_accuracy", "macro_f1", "accuracy"]:
            values = [float(r[metric]) for r in rows if r[metric] is not None]
            if not values:
                continue
            summary.append({
                "condition": condition,
                "group": group,
                "metric": metric,
                "seeds": len(values),
                "mean": float(np.mean(values)),
                "std": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
            })
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-only", action="store_true")
    parser.add_argument("--paired-only", action="store_true", help="只跑共同 seeds 17/42，方便正式三線對照")
    parser.add_argument("--max-rows", type=int, help="煙霧測試用，只取前 N 張")
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()

    rows, excluded = build_eval_manifest()
    if args.max_rows:
        rows = rows[: args.max_rows]
    counts = Counter(r["eval_group"] for r in rows)
    summary = {"total_eval_rows": len(rows), "groups": dict(counts), "excluded": excluded, "test_used": False, "training_performed": False}
    (ROOT / "manifest_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    if args.manifest_only:
        return

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    dataset = EvalDataset(rows, 224)
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=False, num_workers=0, pin_memory=device.type == "cuda")
    predictions = []

    for condition, seed, checkpoint in model_specs(args.paired_only):
        print(f"load condition={condition} seed={seed} checkpoint={checkpoint}", flush=True)
        model = load_model(checkpoint, device)
        done = 0
        with torch.inference_mode():
            for images, indices in loader:
                images = images.to(device, non_blocking=True)
                logits = model(images)
                probs = logits.float().softmax(1).cpu().numpy()
                for local, row_index in enumerate(indices.tolist()):
                    row = rows[row_index]
                    prob = probs[local]
                    pred = int(prob.argmax())
                    rec = {
                        "condition": condition,
                        "seed": seed,
                        "row_id": row["row_id"],
                        "source": row["source"],
                        "eval_group": row["eval_group"],
                        "category": row["category"],
                        "label": row["label"],
                        "label_name": row["label_name"],
                        "pred_label": pred,
                        "pred_name": CLASS_NAMES[pred],
                        "confidence": float(prob[pred]),
                    }
                    for i in range(7):
                        rec[f"p_{CLASS_NAMES[i]}"] = float(prob[i])
                    predictions.append(rec)
                done += len(indices)
                if done % 1024 == 0 or done == len(rows):
                    print(f"condition={condition} seed={seed} images={done}/{len(rows)}", flush=True)
        del model
        if device.type == "cuda":
            torch.cuda.empty_cache()

    pred_path = ROOT / "predictions.csv"
    fields = list(predictions[0].keys()) if predictions else []
    with pred_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(predictions)

    metric_rows = summarize_metrics(rows, predictions)
    with (ROOT / "metrics_by_model.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        fields = ["condition", "seed", "group", "samples", "balanced_accuracy", "macro_f1", "accuracy"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(metric_rows)

    summary_rows = write_metrics_summary(metric_rows)
    with (ROOT / "metrics_summary_by_condition.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        fields = ["condition", "group", "metric", "seeds", "mean", "std"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"saved {pred_path}", flush=True)
    print(f"saved {ROOT / 'metrics_by_model.csv'}", flush=True)
    print(f"saved {ROOT / 'metrics_summary_by_condition.csv'}", flush=True)


if __name__ == "__main__":
    main()
