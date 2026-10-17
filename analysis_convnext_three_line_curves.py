import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import torch

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "實驗彙整" / "ConvNeXt純淨三線對照_2026-08-25"
OUT_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams["font.sans-serif"] = [
    "Microsoft JhengHei", "Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"
]
plt.rcParams["axes.unicode_minus"] = False


def load_run(path, seed):
    full = ROOT / path
    if full.suffix == ".pt":
        ckpt = torch.load(full, map_location="cpu")
        return {"seed": seed, "history": ckpt["history"], "best": ckpt["best_record"], "source": path}
    with open(full, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    return {"seed": data.get("seed", seed), "history": data["history"], "best": data["best"], "source": path}


def mean_curve(runs, metric="balanced_accuracy"):
    max_len = max(len(r["history"]) for r in runs)
    epochs, means, counts = [], [], []
    for idx in range(max_len):
        vals = []
        for r in runs:
            if idx < len(r["history"]):
                vals.append(r["history"][idx]["val"][metric])
        if vals:
            epochs.append(idx + 1)
            means.append(sum(vals) / len(vals) * 100)
            counts.append(len(vals))
    return epochs, means, counts


def best_ba(runs):
    return [r["best"]["val"]["balanced_accuracy"] * 100 for r in runs]


def build_plot(series, filename, title, note):
    fig = plt.figure(figsize=(15.5, 6.8), dpi=180)
    gs = fig.add_gridspec(1, 2, width_ratios=[2.25, 1], wspace=0.23)
    ax = fig.add_subplot(gs[0, 0])
    bar_ax = fig.add_subplot(gs[0, 1])

    for item in series:
        epochs, means, counts = mean_curve(item["runs"])
        item["mean_best"] = sum(best_ba(item["runs"])) / len(item["runs"])
        item["last"] = means[-1]
        ax.plot(
            epochs,
            means,
            label=f"{item['label']}（最佳平均 {item['mean_best']:.1f}%）",
            color=item["color"],
            marker=item["marker"],
            linewidth=2.7,
            markersize=4.2,
            markevery=max(1, len(epochs) // 8),
        )
        ax.text(epochs[-1] + 0.25, means[-1], item["label"], color=item["color"], va="center", fontsize=10)

    ax.set_title("Validation Balanced Accuracy 訓練曲線", fontsize=15, pad=12)
    ax.set_xlabel("訓練週期")
    ax.set_ylabel("Validation Balanced Accuracy（%）")
    ax.set_xlim(1, max(max(mean_curve(i["runs"])[0]) for i in series) + 2.5)
    ax.set_ylim(35, 85)
    ax.grid(True, alpha=0.25)
    ax.legend(loc="lower right", frameon=False)
    ax.text(1, 36.5, note, fontsize=9, color="#4b5563")

    bars = bar_ax.bar([i["label"] for i in series], [i["mean_best"] for i in series], color=[i["color"] for i in series], alpha=0.9)
    bar_ax.set_title("各條件最佳 BA 平均", fontsize=13, pad=12)
    bar_ax.set_ylabel("Validation BA（%）")
    bar_ax.set_ylim(0, 85)
    bar_ax.grid(axis="y", alpha=0.25)
    for bar, item in zip(bars, series):
        bar_ax.text(bar.get_x() + bar.get_width()/2, item["mean_best"] + 1.2, f"{item['mean_best']:.1f}%", ha="center", va="bottom", fontsize=11, fontweight="bold")
    bar_ax.tick_params(axis="x", labelrotation=0)

    fig.suptitle(title, fontsize=17, y=0.99)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    out = OUT_DIR / filename
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


pure = {
    "label": "純淨版",
    "color": "#5b6770",
    "marker": "o",
    "paths": [
        (17, "第二階段/results/v10_seed17.json"),
        (42, "第二階段/results/v10_seed42.json"),
        (2026, "第二階段/results/v10_seed2026.json"),
    ],
}

imagenet_v7 = {
    "label": "ImageNet",
    "color": "#2563eb",
    "marker": "s",
    "paths": [
        (17, "第二階段/results/v7_seed17.json"),
        (42, "第二階段/results/v7_seed42.json"),
        (2026, "第二階段/results/v7_seed2026.json"),
    ],
}

imagenet_transfer = {
    "label": "ImageNet",
    "color": "#2563eb",
    "marker": "s",
    "paths": [
        (17, "第二階段/部位權重完整微調正式對照/results/imagenet_init/seed17/result.json"),
        (42, "第二階段/部位權重完整微調正式對照/results/imagenet_init/seed42/result.json"),
    ],
}

anatomy = {
    "label": "部位辨識",
    "color": "#dc2626",
    "marker": "^",
    "paths": [
        (17, "第二階段/部位權重完整微調正式對照/results/densepose_true_init/seed17/result.json"),
        (42, "第二階段/部位權重完整微調正式對照/results/densepose_true_init/seed42/last.pt"),
    ],
}


def with_runs(item, seeds=None):
    selected = item["paths"]
    if seeds is not None:
        selected = [(s, p) for s, p in selected if s in seeds]
    return {**item, "runs": [load_run(p, s) for s, p in selected]}

paired_series = [with_runs(pure, {17, 42}), with_runs(imagenet_transfer, {17, 42}), with_runs(anatomy, {17, 42})]
all_available_series = [with_runs(pure), with_runs(imagenet_v7), with_runs(anatomy)]

paired_png = build_plot(
    paired_series,
    "convnext_three_line_paired_seed17_42.png",
    "ConvNeXt-Tiny 三線同架構對照：paired seeds 17/42",
    "三條線皆為 ConvNeXt-Tiny、224px、CE；使用共同的 seed 17/42。",
)
all_png = build_plot(
    all_available_series,
    "convnext_three_line_all_available.png",
    "ConvNeXt-Tiny 三線對照：可用 seed 全部納入",
    "純淨版與 ImageNet 使用 3 seeds；部位辨識目前使用 2 seeds。",
)

csv_path = OUT_DIR / "convnext_three_line_summary.csv"
with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["圖表版本", "條件", "seed", "最佳週期", "最佳Validation BA", "最佳macro-F1", "最佳accuracy", "來源"])
    for chart_name, series in [("paired_seed17_42", paired_series), ("all_available", all_available_series)]:
        for item in series:
            for r in item["runs"]:
                b = r["best"]["val"]
                w.writerow([chart_name, item["label"], r["seed"], r["best"]["epoch"], f"{b['balanced_accuracy']:.6f}", f"{b['macro_f1']:.6f}", f"{b['accuracy']:.6f}", r["source"]])

for path in [paired_png, all_png, csv_path]:
    print(path)
