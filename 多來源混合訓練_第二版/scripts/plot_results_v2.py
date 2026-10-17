from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import PercentFormatter


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
OUTPUT = ROOT / "圖表"
EXPORT = PROJECT / "plots_export"
V1_RESULT = PROJECT / "多來源混合訓練_第一版/results/imagenet_seed17/result.json"
V2_RESULT = ROOT / "results/imagenet_seed17/result.json"
V1_PAD = ROOT / "analysis/v1_best_on_v2_pad_validation.json"
CLASS_NAMES = ["AKIEC", "BCC", "BKL", "DF", "NV", "VASC", "MEL"]
SOURCES = ["HAM10000", "BCN20000", "PAD-UFES-20"]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def percent_axis(axis, low=0.0, high=1.0) -> None:
    axis.set_ylim(low, high)
    axis.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    axis.grid(axis="y", alpha=0.25, linewidth=0.8)


def comparison_data(v1: dict, v2: dict, v1_pad: dict) -> tuple[dict, dict]:
    old = {
        "HAM10000": v1["best"]["validation_by_source"]["HAM10000"],
        "BCN20000": v1["best"]["validation_by_source"]["BCN20000"],
        "PAD-UFES-20": v1_pad["metrics"],
    }
    new = {source: v2["best"]["validation_by_source"][source] for source in SOURCES}
    return old, new


def plot_curves(v2: dict) -> Path:
    history = v2["history"]
    epochs = [row["epoch"] for row in history]
    series = {
        "混合訓練集": [row["train"]["balanced_accuracy"] for row in history],
        "HAM10000 驗證集": [row["validation_by_source"]["HAM10000"]["balanced_accuracy"] for row in history],
        "BCN20000 驗證集": [row["validation_by_source"]["BCN20000"]["balanced_accuracy"] for row in history],
        "PAD-UFES-20 驗證集": [row["validation_by_source"]["PAD-UFES-20"]["balanced_accuracy"] for row in history],
        "三來源等權平均": [row["selection_mean_source_balanced_accuracy"] for row in history],
    }
    markers = ["o", "s", "^", "v", "D"]
    fig, ax = plt.subplots(figsize=(11.5, 6.6), constrained_layout=True)
    for (label, values), marker in zip(series.items(), markers):
        style = "--" if label == "三來源等權平均" else "-"
        width = 2.7 if label == "三來源等權平均" else 2.1
        ax.plot(epochs, values, marker=marker, linestyle=style, linewidth=width, label=label)
    best_epoch = int(v2["best"]["epoch"])
    best_mean = float(v2["best"]["selection_mean_source_balanced_accuracy"])
    ax.axvline(best_epoch, color="0.35", linestyle=":", linewidth=1.5)
    ax.annotate(
        f"最佳模型：第 {best_epoch} 輪\n平均 {best_mean:.1%}",
        xy=(best_epoch, best_mean), xytext=(best_epoch + 0.25, best_mean + 0.10),
        arrowprops={"arrowstyle": "->", "color": "0.35"}, fontsize=11,
    )
    ax.set_title("HAM＋BCN＋PAD 三來源混合訓練：平衡準確率曲線", fontsize=16)
    ax.set_xlabel("訓練輪次（epoch）")
    ax.set_ylabel("平衡準確率")
    ax.set_xticks(epochs)
    percent_axis(ax, 0.45, 1.0)
    ax.legend(ncol=2, frameon=False, loc="lower right")
    path = OUTPUT / "01_第二版三來源平衡準確率曲線.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def plot_version_comparison(old: dict, new: dict) -> Path:
    metrics = ["balanced_accuracy", "macro_f1", "accuracy"]
    metric_names = ["平衡準確率", "Macro-F1", "一般準確率"]
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.7), sharey=True, constrained_layout=True)
    x = np.arange(3)
    width = 0.35
    for ax, source in zip(axes, SOURCES):
        old_values = [old[source][metric] for metric in metrics]
        new_values = [new[source][metric] for metric in metrics]
        bars_old = ax.bar(x - width / 2, old_values, width, label="第一版：HAM＋BCN")
        bars_new = ax.bar(x + width / 2, new_values, width, label="第二版：HAM＋BCN＋PAD")
        ax.set_title(f"{source} 驗證集")
        ax.set_xticks(x, metric_names)
        percent_axis(ax, 0.25, 0.9)
        for bars in (bars_old, bars_new):
            ax.bar_label(bars, labels=[f"{bar.get_height():.1%}" for bar in bars], padding=3, fontsize=9)
    axes[0].set_ylabel("指標值")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside upper center", ncol=2, frameon=False)
    fig.suptitle("增加 PAD-UFES-20 前後：相同 seed 17、相同驗證清單", fontsize=16)
    path = OUTPUT / "02_第一版與第二版三來源比較.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def plot_ba_change(old: dict, new: dict) -> Path:
    labels = SOURCES + ["三來源平均"]
    old_values = [old[source]["balanced_accuracy"] for source in SOURCES]
    new_values = [new[source]["balanced_accuracy"] for source in SOURCES]
    old_values.append(float(np.mean(old_values)))
    new_values.append(float(np.mean(new_values)))
    changes = [(after - before) * 100 for before, after in zip(old_values, new_values)]

    fig, ax = plt.subplots(figsize=(10.5, 5.8), constrained_layout=True)
    x = np.arange(len(labels))
    colors = ["#2ca02c" if value >= 0 else "#d62728" for value in changes]
    bars = ax.bar(x, changes, color=colors)
    ax.axhline(0, color="0.35", linewidth=1)
    ax.set_title("加入 PAD-UFES-20 後的平衡準確率變化", fontsize=16)
    ax.set_xlabel("驗證來源")
    ax.set_ylabel("變化（百分點）")
    ax.set_xticks(x, labels)
    ax.grid(axis="y", alpha=0.25, linewidth=0.8)
    ax.bar_label(bars, labels=[f"{value:+.2f}" for value in changes], padding=3, fontsize=11)
    low = min(-5, min(changes) - 3)
    high = max(5, max(changes) + 3)
    ax.set_ylim(low, high)
    path = OUTPUT / "03_加入PAD後平衡準確率變化.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def plot_recall(v2: dict) -> Path:
    best = v2["best"]["validation_by_source"]
    recalls = {source: np.asarray(best[source]["recall_per_class"], dtype=float) for source in SOURCES}
    pad_supported = set(best["PAD-UFES-20"].get("metric_labels", [0, 1, 2, 4, 6]))
    for label in range(7):
        if label not in pad_supported:
            recalls["PAD-UFES-20"][label] = np.nan

    x = np.arange(7)
    width = 0.25
    fig, ax = plt.subplots(figsize=(12, 6.3), constrained_layout=True)
    offsets = [-width, 0, width]
    for source, offset in zip(SOURCES, offsets):
        bars = ax.bar(x + offset, recalls[source], width, label=source)
        labels = ["" if np.isnan(value) else f"{value:.0%}" for value in recalls[source]]
        ax.bar_label(bars, labels=labels, padding=2, fontsize=8)
    for label in [3, 5]:
        ax.text(x[label] + width, 0.025, "不適用", ha="center", va="bottom", fontsize=8, rotation=90)
    ax.set_title("第二版最佳模型（第 6 輪）：各疾病類別召回率", fontsize=16)
    ax.set_xlabel("疾病類別")
    ax.set_ylabel("召回率")
    ax.set_xticks(x, CLASS_NAMES)
    percent_axis(ax, 0.0, 1.0)
    ax.legend(frameon=False, ncol=3)
    path = OUTPUT / "04_第二版最佳模型各類召回率.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def write_summary(v1: dict, v2: dict, old: dict, new: dict) -> None:
    rows = []
    for source in SOURCES:
        for metric, name in [
            ("balanced_accuracy", "Balanced Accuracy"),
            ("macro_f1", "Macro-F1"),
            ("accuracy", "Accuracy"),
        ]:
            rows.append({
                "驗證來源": source,
                "指標": name,
                "第一版_seed17": old[source][metric],
                "第二版_seed17": new[source][metric],
                "變化_百分點": (new[source][metric] - old[source][metric]) * 100,
            })
    with (OUTPUT / "第二版結果數值摘要.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    plt.rcParams["font.family"] = "Microsoft JhengHei"
    plt.rcParams["axes.unicode_minus"] = False
    OUTPUT.mkdir(parents=True, exist_ok=True)
    EXPORT.mkdir(parents=True, exist_ok=True)
    v1, v2, v1_pad = load_json(V1_RESULT), load_json(V2_RESULT), load_json(V1_PAD)
    old, new = comparison_data(v1, v2, v1_pad)
    outputs = [
        plot_curves(v2),
        plot_version_comparison(old, new),
        plot_ba_change(old, new),
        plot_recall(v2),
    ]
    write_summary(v1, v2, old, new)
    export_names = [
        "mixed_v2_ba_curves.png",
        "mixed_v1_v2_comparison.png",
        "mixed_v2_ba_change.png",
        "mixed_v2_recall_by_class.png",
    ]
    for source_path, name in zip(outputs, export_names):
        (EXPORT / name).write_bytes(source_path.read_bytes())
    print(f"Saved {len(outputs)} charts to {OUTPUT}")


if __name__ == "__main__":
    main()
