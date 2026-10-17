from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import PercentFormatter


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
OUTPUT = ROOT / "圖表_直覺版"
EXPORT = PROJECT / "plots_export"
SOURCES = ["HAM10000", "BCN20000", "PAD-UFES-20"]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def percent_axis(ax, low=0.0, high=1.0):
    ax.set_ylim(low, high)
    ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.grid(axis="y", alpha=0.25, linewidth=0.8)


def plot_train_validation(source_eval: dict) -> Path:
    values = source_eval["metrics_by_source_split"]
    train = [values[source]["train"]["balanced_accuracy"] for source in SOURCES]
    validation = [values[source]["validation"]["balanced_accuracy"] for source in SOURCES]
    x = np.arange(len(SOURCES))
    width = 0.36

    fig, ax = plt.subplots(figsize=(10.5, 6.2), constrained_layout=True)
    train_bars = ax.bar(x - width / 2, train, width, label="Train：模型看過的資料")
    val_bars = ax.bar(x + width / 2, validation, width, label="Validation：模型沒看過的資料")
    ax.bar_label(train_bars, labels=[f"{value:.1%}" for value in train], padding=3, fontsize=11)
    ax.bar_label(val_bars, labels=[f"{value:.1%}" for value in validation], padding=3, fontsize=11)
    for index, (train_value, val_value) in enumerate(zip(train, validation)):
        midpoint = (train_value + val_value) / 2
        gap = (train_value - val_value) * 100
        ax.text(index, midpoint, f"落差 {gap:.1f} pp", ha="center", va="center", fontsize=10)
    ax.set_title("第二版最佳模型：每個資料來源的 Train 與 Validation", fontsize=16)
    ax.set_xlabel("資料來源")
    ax.set_ylabel("平衡準確率")
    ax.set_xticks(x, SOURCES)
    percent_axis(ax, 0.45, 1.05)
    ax.legend(frameon=False, ncol=2, loc="lower left")
    path = OUTPUT / "01_各來源Train與Validation平衡準確率.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def plot_versions(v1: dict, v2: dict, v1_pad: dict) -> Path:
    old = [
        v1["best"]["validation_by_source"]["HAM10000"]["balanced_accuracy"],
        v1["best"]["validation_by_source"]["BCN20000"]["balanced_accuracy"],
        v1_pad["metrics"]["balanced_accuracy"],
    ]
    new = [v2["best"]["validation_by_source"][source]["balanced_accuracy"] for source in SOURCES]
    old.append(float(np.mean(old)))
    new.append(float(np.mean(new)))
    labels = SOURCES + ["三來源平均"]
    x = np.arange(len(labels))
    width = 0.36

    fig, ax = plt.subplots(figsize=(11, 6.2), constrained_layout=True)
    old_bars = ax.bar(x - width / 2, old, width, label="第一版：HAM＋BCN 訓練")
    new_bars = ax.bar(x + width / 2, new, width, label="第二版：HAM＋BCN＋PAD 訓練")
    ax.bar_label(old_bars, labels=[f"{value:.1%}" for value in old], padding=3, fontsize=10)
    ax.bar_label(new_bars, labels=[f"{value:.1%}" for value in new], padding=3, fontsize=10)
    for index, (before, after) in enumerate(zip(old, new)):
        delta = (after - before) * 100
        top = max(before, after) + 0.075
        ax.text(index, top, f"{delta:+.1f} pp", ha="center", va="bottom", fontsize=10)
    ax.set_title("增加 PAD 前後：各來源 Validation 平衡準確率", fontsize=16)
    ax.set_xlabel("驗證資料來源")
    ax.set_ylabel("平衡準確率")
    ax.set_xticks(x, labels)
    percent_axis(ax, 0.3, 0.95)
    ax.legend(frameon=False, ncol=2, loc="lower left")
    path = OUTPUT / "02_第一版第二版Validation直覺比較.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def plot_validation_curves(v2: dict) -> Path:
    history = v2["history"]
    epochs = [row["epoch"] for row in history]
    series = {
        "HAM10000 Validation": [row["validation_by_source"]["HAM10000"]["balanced_accuracy"] for row in history],
        "BCN20000 Validation": [row["validation_by_source"]["BCN20000"]["balanced_accuracy"] for row in history],
        "PAD-UFES-20 Validation": [row["validation_by_source"]["PAD-UFES-20"]["balanced_accuracy"] for row in history],
        "三來源平均": [row["selection_mean_source_balanced_accuracy"] for row in history],
    }
    fig, ax = plt.subplots(figsize=(11, 6.3), constrained_layout=True)
    markers = ["s", "^", "v", "D"]
    for (label, values), marker in zip(series.items(), markers):
        ax.plot(
            epochs, values, marker=marker, linewidth=2.5,
            linestyle="--" if label == "三來源平均" else "-", label=label,
        )
    best_epoch = int(v2["best"]["epoch"])
    best_mean = float(v2["best"]["selection_mean_source_balanced_accuracy"])
    ax.axvline(best_epoch, color="0.35", linestyle=":", linewidth=1.5)
    ax.annotate(
        f"最佳 checkpoint\n第 {best_epoch} 輪，平均 {best_mean:.1%}",
        xy=(best_epoch, best_mean), xytext=(best_epoch + 0.25, best_mean + 0.09),
        arrowprops={"arrowstyle": "->", "color": "0.35"}, fontsize=11,
    )
    ax.set_title("第二版訓練過程：只看未參與訓練的 Validation", fontsize=16)
    ax.set_xlabel("訓練輪次（epoch）")
    ax.set_ylabel("平衡準確率")
    ax.set_xticks(epochs)
    percent_axis(ax, 0.45, 0.9)
    ax.legend(frameon=False, ncol=2, loc="lower left")
    path = OUTPUT / "03_只顯示Validation的訓練曲線.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def main() -> None:
    plt.rcParams["font.family"] = "Microsoft JhengHei"
    plt.rcParams["axes.unicode_minus"] = False
    OUTPUT.mkdir(parents=True, exist_ok=True)
    EXPORT.mkdir(parents=True, exist_ok=True)
    source_eval = load(ROOT / "analysis/v2_best_train_validation_by_source.json")
    v1 = load(PROJECT / "多來源混合訓練_第一版/results/imagenet_seed17/result.json")
    v2 = load(ROOT / "results/imagenet_seed17/result.json")
    v1_pad = load(ROOT / "analysis/v1_best_on_v2_pad_validation.json")
    charts = [
        plot_train_validation(source_eval),
        plot_versions(v1, v2, v1_pad),
        plot_validation_curves(v2),
    ]
    names = [
        "intuitive_train_vs_validation.png",
        "intuitive_v1_v2_validation.png",
        "intuitive_validation_curves.png",
    ]
    for chart, name in zip(charts, names):
        (EXPORT / name).write_bytes(chart.read_bytes())
    print(f"Saved {len(charts)} intuitive charts")


if __name__ == "__main__":
    main()
