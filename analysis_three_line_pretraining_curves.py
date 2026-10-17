import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import torch

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "實驗彙整" / "預訓練干預三線對照_2026-08-25"
OUT_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams["font.sans-serif"] = [
    "Microsoft JhengHei",
    "Microsoft YaHei",
    "SimHei",
    "Arial Unicode MS",
    "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False


def load_run(path, fallback_seed=None):
    full = ROOT / path
    if full.suffix == ".pt":
        ckpt = torch.load(full, map_location="cpu")
        return {
            "seed": fallback_seed,
            "history": ckpt["history"],
            "best": ckpt["best_record"],
            "source": path,
        }
    with open(full, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {
        "seed": data.get("seed", fallback_seed),
        "history": data["history"],
        "best": data["best"],
        "source": path,
    }


def metric_at_epoch(run, idx, metric):
    hist = run["history"]
    if idx < len(hist):
        return hist[idx]["val"][metric]
    return None


def mean_curve(paths, metric="balanced_accuracy"):
    runs = [load_run(path, fallback_seed=seed) for seed, path in paths]
    max_len = max(len(r["history"]) for r in runs)
    epochs = []
    means = []
    counts = []
    for idx in range(max_len):
        vals = [metric_at_epoch(r, idx, metric) for r in runs]
        vals = [v for v in vals if v is not None]
        if vals:
            epochs.append(idx + 1)
            means.append(sum(vals) / len(vals))
            counts.append(len(vals))
    return epochs, means, counts, runs


def best_values(runs):
    return [r["best"]["val"]["balanced_accuracy"] for r in runs]


series = [
    {
        "name": "純淨版：ResNet18 隨機初始化",
        "short": "純淨版",
        "paths": [
            (17, "第二階段/results/v5_seed17.json"),
            (42, "第二階段/results/v5_seed42.json"),
            (2026, "第二階段/results/v5_seed2026.json"),
        ],
        "color": "#5b6770",
        "marker": "o",
    },
    {
        "name": "ImageNet：ConvNeXt-Tiny 初始化",
        "short": "ImageNet",
        "paths": [
            (17, "第二階段/部位權重完整微調正式對照/results/imagenet_init/seed17/result.json"),
            (42, "第二階段/部位權重完整微調正式對照/results/imagenet_init/seed42/result.json"),
        ],
        "color": "#2563eb",
        "marker": "s",
    },
    {
        "name": "部位辨識：DensePose 預訓練初始化",
        "short": "部位辨識",
        "paths": [
            (17, "第二階段/部位權重完整微調正式對照/results/densepose_true_init/seed17/result.json"),
            (42, "第二階段/部位權重完整微調正式對照/results/densepose_true_init/seed42/last.pt"),
        ],
        "color": "#dc2626",
        "marker": "^",
    },
]

curves = []
for item in series:
    epochs, means, counts, runs = mean_curve(item["paths"])
    best = best_values(runs)
    item.update(
        {
            "epochs": epochs,
            "means": means,
            "counts": counts,
            "runs": runs,
            "best_mean": sum(best) / len(best),
            "best_values": best,
        }
    )
    curves.append(item)

fig = plt.figure(figsize=(15.5, 6.8), dpi=180)
gs = fig.add_gridspec(1, 2, width_ratios=[2.25, 1], wspace=0.22)
ax = fig.add_subplot(gs[0, 0])
bar_ax = fig.add_subplot(gs[0, 1])

for item in curves:
    ax.plot(
        item["epochs"],
        [v * 100 for v in item["means"]],
        label=f"{item['short']}（最佳平均 {item['best_mean']*100:.1f}%）",
        color=item["color"],
        marker=item["marker"],
        linewidth=2.5,
        markersize=4.0,
        markevery=max(1, len(item["epochs"]) // 8),
    )
    last_x = item["epochs"][-1]
    last_y = item["means"][-1] * 100
    ax.text(last_x + 0.25, last_y, item["short"], color=item["color"], va="center", fontsize=10)

ax.set_title("三種初始化方式的主體模型驗證曲線", fontsize=15, pad=12)
ax.set_xlabel("訓練週期")
ax.set_ylabel("Validation Balanced Accuracy（%）")
ax.set_xlim(1, max(max(i["epochs"]) for i in curves) + 2.5)
ax.set_ylim(35, 85)
ax.grid(True, alpha=0.25)
ax.legend(loc="lower right", frameon=False)
ax.text(
    1,
    36.5,
    "註：純淨版目前只有 ResNet18 隨機初始化紀錄；ImageNet 與部位辨識為 ConvNeXt-Tiny 正式對照。",
    fontsize=9,
    color="#4b5563",
)

names = [i["short"] for i in curves]
values = [i["best_mean"] * 100 for i in curves]
colors = [i["color"] for i in curves]
bars = bar_ax.bar(names, values, color=colors, alpha=0.9)
bar_ax.set_title("最佳結果平均", fontsize=13, pad=12)
bar_ax.set_ylabel("Validation BA（%）")
bar_ax.set_ylim(0, 85)
bar_ax.grid(axis="y", alpha=0.25)
for bar, value in zip(bars, values):
    bar_ax.text(
        bar.get_x() + bar.get_width() / 2,
        value + 1.2,
        f"{value:.1f}%",
        ha="center",
        va="bottom",
        fontsize=11,
        fontweight="bold",
    )
bar_ax.tick_params(axis="x", rotation=0)

fig.suptitle("ImageNet、部位辨識預訓練、純淨主體模型：一眼對照", fontsize=17, y=0.99)
fig.tight_layout(rect=[0, 0, 1, 0.95])
out_png = OUT_DIR / "三線同圖_Validation_BA_直觀對照.png"
fig.savefig(out_png, bbox_inches="tight")
plt.close(fig)

# A curve-only version for slides.
fig2, ax2 = plt.subplots(figsize=(11.5, 6.2), dpi=180)
for item in curves:
    ax2.plot(
        item["epochs"],
        [v * 100 for v in item["means"]],
        label=f"{item['short']}（最佳平均 {item['best_mean']*100:.1f}%）",
        color=item["color"],
        marker=item["marker"],
        linewidth=2.8,
        markersize=4.5,
        markevery=max(1, len(item["epochs"]) // 8),
    )
    ax2.text(item["epochs"][-1] + 0.25, item["means"][-1] * 100, item["short"], color=item["color"], va="center", fontsize=11)
ax2.set_title("Validation Balanced Accuracy 三線對照", fontsize=16, pad=12)
ax2.set_xlabel("訓練週期")
ax2.set_ylabel("Validation Balanced Accuracy（%）")
ax2.set_xlim(1, max(max(i["epochs"]) for i in curves) + 2.5)
ax2.set_ylim(35, 85)
ax2.grid(True, alpha=0.25)
ax2.legend(loc="lower right", frameon=False)
ax2.text(1, 36.5, "純淨版為 ResNet18；ImageNet/部位辨識為 ConvNeXt-Tiny。", fontsize=9, color="#4b5563")
fig2.tight_layout()
out_curve = OUT_DIR / "三線同圖_Validation_BA_曲線版.png"
fig2.savefig(out_curve, bbox_inches="tight")
plt.close(fig2)

csv_path = OUT_DIR / "三線同圖_摘要.csv"
with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["條件", "平均最佳Validation BA", "seed數", "來源說明"])
    for item in curves:
        writer.writerow([item["name"], f"{item['best_mean']:.6f}", len(item["runs"]), "; ".join(r["source"] for r in item["runs"])])

print(out_png)
print(out_curve)
print(csv_path)
