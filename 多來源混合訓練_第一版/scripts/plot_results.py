from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import PercentFormatter


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
RESULT_PATH = ROOT / "results/imagenet_seed17/result.json"
BASELINE_PATH = PROJECT / "全資料集驗證推論_ConvNeXt三線/metrics_by_model.csv"
OUTPUT = ROOT / "圖表"
CLASS_NAMES = ["AKIEC", "BCC", "BKL", "DF", "NV", "VASC", "MEL"]


def setup_chinese_font() -> None:
    plt.rcParams["font.family"] = [
        "Microsoft JhengHei", "Microsoft YaHei", "SimHei", "Noto Sans CJK TC", "DejaVu Sans"
    ]
    plt.rcParams["axes.unicode_minus"] = False


def load_baseline() -> dict[str, dict[str, float]]:
    selected = {}
    with BASELINE_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["condition"] != "imagenet_convnext_tiny" or row["seed"] != "17":
                continue
            if row["group"] not in {"HAM10000", "BCN20000"}:
                continue
            selected[row["group"]] = {
                "balanced_accuracy": float(row["balanced_accuracy"]),
                "macro_f1": float(row["macro_f1"]),
                "accuracy": float(row["accuracy"]),
            }
    if set(selected) != {"HAM10000", "BCN20000"}:
        raise RuntimeError("找不到 seed 17 的 HAM-only ImageNet 基準結果")
    return selected


def percent_axis(axis, lower=0.0, upper=1.0) -> None:
    axis.set_ylim(lower, upper)
    axis.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    axis.grid(axis="y", alpha=0.25, linewidth=0.8)


def plot_learning_curves(result: dict) -> None:
    history = result["history"]
    epochs = [row["epoch"] for row in history]
    train_ba = [row["train"]["balanced_accuracy"] for row in history]
    ham_ba = [row["validation_by_source"]["HAM10000"]["balanced_accuracy"] for row in history]
    bcn_ba = [row["validation_by_source"]["BCN20000"]["balanced_accuracy"] for row in history]
    mean_ba = [row["selection_mean_source_balanced_accuracy"] for row in history]
    best_epoch = int(result["best"]["epoch"])
    best_mean = float(result["best"]["selection_mean_source_balanced_accuracy"])

    fig, ax = plt.subplots(figsize=(11, 6.4), constrained_layout=True)
    ax.plot(epochs, train_ba, marker="o", linewidth=2.2, label="混合訓練集")
    ax.plot(epochs, ham_ba, marker="s", linewidth=2.2, label="HAM10000 驗證集")
    ax.plot(epochs, bcn_ba, marker="^", linewidth=2.2, label="BCN20000 驗證集")
    ax.plot(epochs, mean_ba, marker="D", linewidth=2.6, linestyle="--", label="兩來源等權平均")
    ax.axvline(best_epoch, color="0.35", linestyle=":", linewidth=1.5)
    ax.annotate(
        f"最佳模型：第 {best_epoch} 輪\n平均 {best_mean:.1%}",
        xy=(best_epoch, best_mean), xytext=(best_epoch + 0.35, best_mean + 0.08),
        arrowprops={"arrowstyle": "->", "color": "0.35"}, fontsize=11,
    )
    ax.set_title("HAM10000＋BCN20000 混合訓練：平衡準確率曲線", fontsize=16)
    ax.set_xlabel("訓練輪次（epoch）")
    ax.set_ylabel("平衡準確率")
    ax.set_xticks(epochs)
    percent_axis(ax, 0.45, 1.0)
    ax.legend(ncol=2, frameon=False, loc="lower right")
    fig.savefig(OUTPUT / "01_混合訓練平衡準確率曲線.png", dpi=180)
    plt.close(fig)


def plot_before_after(result: dict, baseline: dict) -> None:
    best = result["best"]["validation_by_source"]
    metrics = ["balanced_accuracy", "macro_f1", "accuracy"]
    labels = ["平衡準確率", "Macro-F1", "一般準確率"]
    sources = ["HAM10000", "BCN20000"]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.8), sharey=True, constrained_layout=True)
    x = np.arange(len(metrics))
    width = 0.34
    for ax, source in zip(axes, sources):
        old = [baseline[source][metric] for metric in metrics]
        new = [best[source][metric] for metric in metrics]
        bars_old = ax.bar(x - width / 2, old, width, label="僅 HAM10000 訓練")
        bars_new = ax.bar(x + width / 2, new, width, label="HAM＋BCN 混合訓練")
        ax.set_title(f"{source} 驗證集")
        ax.set_xticks(x, labels)
        percent_axis(ax, 0.25, 0.9)
        for bars in (bars_old, bars_new):
            ax.bar_label(bars, labels=[f"{bar.get_height():.1%}" for bar in bars], padding=3, fontsize=10)
    axes[0].set_ylabel("指標值")
    handles, legend_labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, legend_labels, loc="outside upper center", ncol=2, frameon=False)
    fig.suptitle("加入 BCN20000 前後的同一 seed 驗證比較", fontsize=16)
    fig.savefig(OUTPUT / "02_混合訓練前後驗證比較.png", dpi=180)
    plt.close(fig)


def plot_recall_by_class(result: dict) -> None:
    best = result["best"]["validation_by_source"]
    ham = best["HAM10000"]["recall_per_class"]
    bcn = best["BCN20000"]["recall_per_class"]
    x = np.arange(len(CLASS_NAMES))
    width = 0.36

    fig, ax = plt.subplots(figsize=(11, 6.2), constrained_layout=True)
    bars_ham = ax.bar(x - width / 2, ham, width, label="HAM10000 驗證集")
    bars_bcn = ax.bar(x + width / 2, bcn, width, label="BCN20000 驗證集")
    ax.set_title("最佳模型（第 4 輪）：各疾病類別召回率", fontsize=16)
    ax.set_xlabel("疾病類別")
    ax.set_ylabel("召回率")
    ax.set_xticks(x, CLASS_NAMES)
    percent_axis(ax, 0.0, 1.0)
    ax.legend(frameon=False, ncol=2)
    for bars in (bars_ham, bars_bcn):
        ax.bar_label(bars, labels=[f"{bar.get_height():.0%}" for bar in bars], padding=2, fontsize=9)
    fig.savefig(OUTPUT / "03_最佳模型各類召回率.png", dpi=180)
    plt.close(fig)


def write_summary(result: dict, baseline: dict) -> None:
    best = result["best"]
    rows = []
    for source in ["HAM10000", "BCN20000"]:
        for metric, label in [
            ("balanced_accuracy", "Balanced Accuracy"),
            ("macro_f1", "Macro-F1"),
            ("accuracy", "Accuracy"),
        ]:
            old = baseline[source][metric]
            new = best["validation_by_source"][source][metric]
            rows.append({
                "驗證來源": source,
                "指標": label,
                "僅HAM訓練_seed17": old,
                "HAM_BCN混合訓練_seed17": new,
                "變化_百分點": (new - old) * 100,
            })
    with (OUTPUT / "結果數值摘要.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    if not RESULT_PATH.exists():
        raise FileNotFoundError(RESULT_PATH)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    setup_chinese_font()
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8-sig"))
    baseline = load_baseline()
    plot_learning_curves(result)
    plot_before_after(result, baseline)
    plot_recall_by_class(result)
    write_summary(result, baseline)
    print(f"圖表已輸出：{OUTPUT}")


if __name__ == "__main__":
    main()
