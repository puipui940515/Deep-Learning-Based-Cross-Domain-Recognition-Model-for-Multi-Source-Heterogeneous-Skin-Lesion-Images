from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "全資料集驗證推論_ConvNeXt三線" / "metrics_summary_by_condition.csv"
OUT = ROOT / "全資料集驗證推論_ConvNeXt三線"

CONDITION_LABELS = {
    "pure_convnext_tiny": "純淨版",
    "imagenet_convnext_tiny": "ImageNet",
    "anatomy_pretrained_convnext_tiny": "部位辨識",
}

COLORS = {
    "pure_convnext_tiny": "#5b6770",
    "imagenet_convnext_tiny": "#2563eb",
    "anatomy_pretrained_convnext_tiny": "#dc2626",
}

MARKERS = {
    "pure_convnext_tiny": "o",
    "imagenet_convnext_tiny": "s",
    "anatomy_pretrained_convnext_tiny": "^",
}

GROUP_ORDER = [
    ("HAM10000", "HAM10000"),
    ("BCN20000", "BCN20000"),
    ("PAD-UFES-20", "PAD-UFES-20"),
    ("ISIC_Archive", "ISIC Archive"),
    ("ALL_MAPPED", "全部可映射"),
]

METRIC_LABELS = {
    "balanced_accuracy": "Validation Balanced Accuracy（%）",
    "macro_f1": "Validation macro-F1（%）",
    "accuracy": "Validation accuracy（%）",
}


def read_rows() -> list[dict[str, str]]:
    with SRC.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], dict[str, float]]:
    table: dict[tuple[str, str, str], dict[str, float]] = {}
    for row in rows:
        table[(row["condition"], row["group"], row["metric"])] = {
            "mean": float(row["mean"]) * 100.0,
            "std": float(row["std"]) * 100.0,
            "seeds": int(row["seeds"]),
        }
    return table


def configure_fonts() -> None:
    plt.rcParams["font.sans-serif"] = [
        "Microsoft JhengHei",
        "Microsoft YaHei",
        "SimHei",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False


def plot_metric(table, metric: str, path: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(12, 6.4), dpi=180)
    x = list(range(len(GROUP_ORDER)))
    for condition in CONDITION_LABELS:
        means = [table[(condition, group, metric)]["mean"] for group, _ in GROUP_ORDER]
        stds = [table[(condition, group, metric)]["std"] for group, _ in GROUP_ORDER]
        ax.errorbar(
            x,
            means,
            yerr=stds,
            label=CONDITION_LABELS[condition],
            color=COLORS[condition],
            marker=MARKERS[condition],
            linewidth=2.7,
            markersize=7,
            capsize=4,
        )
        ax.text(x[-1] + 0.08, means[-1], CONDITION_LABELS[condition], color=COLORS[condition], va="center")
    ax.set_title(title, fontsize=16, pad=12)
    ax.set_xlabel("驗證資料來源")
    ax.set_ylabel(METRIC_LABELS[metric])
    ax.set_xticks(x)
    ax.set_xticklabels([label for _, label in GROUP_ORDER])
    ax.set_ylim(0, 85)
    ax.set_xlim(-0.2, len(GROUP_ORDER) - 0.55)
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(loc="upper right", frameon=False)
    ax.text(
        0,
        3,
        "誤差棒為 seed 17/42 的樣本標準差；全程只推論，不訓練，不使用 HAM test。",
        fontsize=9,
        color="#4b5563",
    )
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def plot_three_metrics(table, path: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.7), dpi=180, sharex=True)
    x = list(range(len(GROUP_ORDER)))
    for ax, metric in zip(axes, ["balanced_accuracy", "macro_f1", "accuracy"]):
        for condition in CONDITION_LABELS:
            means = [table[(condition, group, metric)]["mean"] for group, _ in GROUP_ORDER]
            ax.plot(
                x,
                means,
                label=CONDITION_LABELS[condition],
                color=COLORS[condition],
                marker=MARKERS[condition],
                linewidth=2.4,
                markersize=5.5,
            )
        ax.set_title(METRIC_LABELS[metric].replace("Validation ", ""), fontsize=13)
        ax.set_xticks(x)
        ax.set_xticklabels([label for _, label in GROUP_ORDER], rotation=18, ha="right")
        ax.set_ylim(0, 90)
        ax.grid(True, axis="y", alpha=0.25)
    axes[0].set_ylabel("分數（%）")
    axes[-1].legend(loc="upper right", frameon=False)
    fig.suptitle("ConvNeXt-Tiny 三線跨資料集驗證指標", fontsize=16, y=1.02)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    configure_fonts()
    rows = read_rows()
    table = lookup(rows)
    plot_metric(
        table,
        "balanced_accuracy",
        OUT / "convnext_validation_ba_three_lines.png",
        "ConvNeXt-Tiny 三線跨資料集驗證：Balanced Accuracy",
    )
    plot_three_metrics(table, OUT / "convnext_validation_three_metrics_lines.png")
    print(OUT / "convnext_validation_ba_three_lines.png")
    print(OUT / "convnext_validation_three_metrics_lines.png")


if __name__ == "__main__":
    main()
