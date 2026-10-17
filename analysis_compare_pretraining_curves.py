import json
from pathlib import Path

import matplotlib.pyplot as plt
import torch


ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "實驗彙整" / "預訓練干預對照_2026-08-25"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_history(path):
    full_path = ROOT / path
    if full_path.suffix == ".pt":
        checkpoint = torch.load(full_path, map_location="cpu")
        data = {
            "seed": 42,
            "best": checkpoint["best_record"],
            "history": checkpoint["history"],
        }
    else:
        with open(full_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    rows = []
    for item in data["history"]:
        val = item.get("val", {})
        rows.append(
            {
                "epoch": item["epoch"],
                "balanced_accuracy": val.get("balanced_accuracy"),
                "macro_f1": val.get("macro_f1"),
                "accuracy": val.get("accuracy"),
                "loss": val.get("loss"),
            }
        )
    best = data["best"]["val"]
    return data, rows, best


def mean_by_epoch(paths, metric):
    per_seed = []
    max_len = 0
    for path in paths:
        _, rows, _ = load_history(path)
        vals = [(r["epoch"], r[metric]) for r in rows if r.get(metric) is not None]
        per_seed.append(vals)
        max_len = max(max_len, len(vals))
    epochs, means = [], []
    for idx in range(max_len):
        values = []
        epoch = idx + 1
        for vals in per_seed:
            if idx < len(vals):
                epoch = vals[idx][0]
                values.append(vals[idx][1])
        if values:
            epochs.append(epoch)
            means.append(sum(values) / len(values))
    return epochs, means


def best_summary(label, paths):
    vals = []
    for path in paths:
        data, _, best = load_history(path)
        vals.append(
            {
                "label": label,
                "path": path,
                "seed": data["seed"],
                "best_epoch": data["best"]["epoch"],
                "balanced_accuracy": best["balanced_accuracy"],
                "macro_f1": best["macro_f1"],
                "accuracy": best["accuracy"],
                "loss": best["loss"],
            }
        )
    return vals


groups = {
    "ResNet18 隨機初始化（純淨）": [
        "第二階段/results/v5_seed17.json",
        "第二階段/results/v5_seed42.json",
        "第二階段/results/v5_seed2026.json",
    ],
    "ResNet18 ImageNet 初始化": [
        "第二階段/results/v6_seed17.json",
        "第二階段/results/v6_seed42.json",
        "第二階段/results/v6_seed2026.json",
    ],
    "ConvNeXt ImageNet 初始化": [
        "第二階段/部位權重完整微調正式對照/results/imagenet_init/seed17/result.json",
        "第二階段/部位權重完整微調正式對照/results/imagenet_init/seed42/result.json",
    ],
    "ConvNeXt 部位預訓練初始化": [
        "第二階段/部位權重完整微調正式對照/results/densepose_true_init/seed17/result.json",
        "第二階段/部位權重完整微調正式對照/results/densepose_true_init/seed42/last.pt",
    ],
}


plt.rcParams["font.sans-serif"] = [
    "Microsoft JhengHei",
    "Microsoft YaHei",
    "SimHei",
    "Arial Unicode MS",
    "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False

fig, axes = plt.subplots(1, 2, figsize=(14, 5.2), dpi=180)

for label in ["ResNet18 隨機初始化（純淨）", "ResNet18 ImageNet 初始化"]:
    epochs, means = mean_by_epoch(groups[label], "balanced_accuracy")
    axes[0].plot(epochs, means, marker="o", linewidth=2.0, markersize=3.5, label=label)
axes[0].set_title("同架構對照：ImageNet 是否幫助 ResNet18 主體模型")
axes[0].set_xlabel("訓練週期")
axes[0].set_ylabel("驗證平衡準確率")
axes[0].grid(True, alpha=0.25)
axes[0].legend()

for label in ["ConvNeXt ImageNet 初始化", "ConvNeXt 部位預訓練初始化"]:
    epochs, means = mean_by_epoch(groups[label], "balanced_accuracy")
    axes[1].plot(epochs, means, marker="o", linewidth=2.0, markersize=3.5, label=label)
axes[1].set_title("同架構對照：部位預訓練是否優於 ImageNet")
axes[1].set_xlabel("訓練週期")
axes[1].set_ylabel("驗證平衡準確率")
axes[1].grid(True, alpha=0.25)
axes[1].legend()

fig.suptitle("主體皮膚病分類模型的預訓練干預對比", fontsize=15)
fig.tight_layout(rect=[0, 0, 1, 0.94])
fig.savefig(OUT_DIR / "主體模型_預訓練干預對比曲線.png", bbox_inches="tight")

summary = []
for label, paths in groups.items():
    summary.extend(best_summary(label, paths))

with open(OUT_DIR / "主體模型_預訓練干預對比摘要.csv", "w", encoding="utf-8-sig") as f:
    f.write("條件,seed,最佳週期,Validation Balanced Accuracy,Validation macro-F1,Validation accuracy,Validation loss,來源檔案\n")
    for row in summary:
        f.write(
            f"{row['label']},{row['seed']},{row['best_epoch']},"
            f"{row['balanced_accuracy']:.6f},{row['macro_f1']:.6f},"
            f"{row['accuracy']:.6f},{row['loss']:.6f},{row['path']}\n"
        )

print(OUT_DIR / "主體模型_預訓練干預對比曲線.png")
print(OUT_DIR / "主體模型_預訓練干預對比摘要.csv")

