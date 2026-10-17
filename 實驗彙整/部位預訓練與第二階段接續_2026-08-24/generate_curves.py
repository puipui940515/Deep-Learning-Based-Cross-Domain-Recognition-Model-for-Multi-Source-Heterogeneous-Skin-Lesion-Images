from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
PLOTS = HERE / "plots"
PLOTS.mkdir(parents=True, exist_ok=True)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def mean_curve(histories, section="validation", metric="balanced_accuracy", epochs=5):
    values = []
    for history in histories:
        current = []
        for record in history[:epochs]:
            block = record.get(section, record.get("val"))
            current.append(float(block[metric]))
        values.append(current)
    array = np.asarray(values, dtype=float)
    return np.arange(1, array.shape[1] + 1), array.mean(axis=0), array.min(axis=0), array.max(axis=0)


def style_axis(axis, title, y_limits=None):
    axis.set_title(title)
    axis.set_xlabel("訓練週期")
    axis.set_ylabel("驗證集平衡準確率（%）")
    axis.grid(True, alpha=0.25)
    axis.set_xticks(range(1, 9))
    if y_limits:
        axis.set_ylim(*y_limits)


def plot_series(axis, histories, label, color, epochs, section="validation", marker="o"):
    x, mean, low, high = mean_curve(histories, section=section, epochs=epochs)
    axis.plot(x, mean * 100, marker=marker, linewidth=2, label=label, color=color)
    if len(histories) > 1:
        axis.fill_between(x, low * 100, high * 100, alpha=0.14, color=color)
    axis.annotate(f"{mean[-1] * 100:.2f}%", (x[-1], mean[-1] * 100), xytext=(6, 0), textcoords="offset points", va="center", color=color)


def anatomy_curves():
    root = PROJECT / "部位預測階段" / "DensePose_部位預訓練" / "results" / "overnight_2026-08-24"
    true_histories = [read_json(root / f"true_seed{seed}" / f"result_seed{seed}.json")["history"] for seed in (17, 42)]
    shuffled = [read_json(root / "shuffled_seed17" / "result_seed17.json")["history"]]
    fig, axis = plt.subplots(figsize=(8.8, 5.2))
    plot_series(axis, true_histories, "真實部位標籤（實線為平均；色帶為最小至最大值）", "#1f77b4", 8)
    plot_series(axis, shuffled, "隨機打亂標籤", "#d62728", 4, marker="s")
    axis.axhline(90, color="#2ca02c", linestyle="--", linewidth=1.4, label="預先設定的 90% 目標")
    axis.axhline(20, color="#7f7f7f", linestyle=":", linewidth=1.4, label="五類隨機基準（20%）")
    style_axis(axis, "DensePose 人體部位預訓練", (10, 100))
    axis.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(PLOTS / "01_anatomy_pretraining_curves.png", dpi=180)
    plt.close(fig)


def frozen_probe_curves():
    root = PROJECT / "第二階段" / "凍結部位Backbone短訓練" / "results"
    conditions = [
        ("imagenet_frozen", "凍結 ImageNet 骨幹模型", "#1f77b4"),
        ("densepose_true_frozen", "凍結 DensePose 真實標籤骨幹模型", "#2ca02c"),
        ("densepose_shuffled_frozen", "凍結 DensePose 打亂標籤骨幹模型", "#d62728"),
    ]
    fig, axis = plt.subplots(figsize=(8.8, 5.2))
    for condition, label, color in conditions:
        histories = [read_json(root / condition / f"seed{seed}" / "result.json")["history"] for seed in (17, 42, 2026)]
        plot_series(axis, histories, label, color, 5, section="val")
    axis.axhline(100 / 7, color="#7f7f7f", linestyle=":", linewidth=1.4, label="七類隨機基準（14.29%）")
    style_axis(axis, "第二階段：凍結骨幹模型的線性探測", (10, 40))
    axis.set_xticks(range(1, 6))
    axis.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(PLOTS / "02_frozen_linear_probe_curves.png", dpi=180)
    plt.close(fig)


def parallel_curves():
    root = PROJECT / "第二階段" / "並行凍結部位特徵實驗" / "results"
    conditions = [
        ("imagenet_teacher", "並行凍結 ImageNet 教師模型", "#1f77b4"),
        ("densepose_true_teacher", "並行凍結 DensePose 真實標籤教師模型", "#2ca02c"),
        ("densepose_shuffled_teacher", "並行凍結 DensePose 打亂標籤教師模型", "#d62728"),
    ]
    fig, axis = plt.subplots(figsize=(8.8, 5.2))
    for condition, label, color in conditions:
        histories = [read_json(root / condition / f"seed{seed}" / "result.json")["history"] for seed in (17, 42, 2026)]
        plot_series(axis, histories, label, color, 5, section="val")
    v7_histories = [read_json(PROJECT / "第二階段" / "results" / f"v7_seed{seed}.json")["history"] for seed in (17, 42, 2026)]
    plot_series(axis, v7_histories, "既有單分支 v7（前 5 個訓練週期）", "#9467bd", 5, section="val", marker="^")
    style_axis(axis, "第二階段：並行凍結教師模型特徵融合", (50, 82))
    axis.set_xticks(range(1, 6))
    axis.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(PLOTS / "03_parallel_teacher_curves.png", dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Microsoft JhengHei", "Microsoft YaHei", "SimHei", "DejaVu Sans"], "axes.unicode_minus": False, "font.size": 10, "axes.titlesize": 14, "axes.labelsize": 11, "legend.fontsize": 9})
    anatomy_curves()
    frozen_probe_curves()
    parallel_curves()
    print(PLOTS)


