from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
NEW_PATH = ROOT / "results/formal_v1/regularized_seed17/result.json"
OLD_PATH = PROJECT / "多來源混合訓練_第二版/results/imagenet_seed17/result.json"
OUTPUT = ROOT / "results/formal_v1/regularized_seed17/圖表與摘要"
SOURCES = ["HAM10000", "BCN20000", "PAD-UFES-20"]
SOURCE_ZH = {"HAM10000": "HAM10000", "BCN20000": "BCN20000", "PAD-UFES-20": "PAD-UFES-20"}
CLASS_ZH = ["光化性角化症／表皮內癌", "基底細胞癌", "良性角化病變", "皮膚纖維瘤", "黑色素細胞痣", "血管性病變", "黑色素瘤"]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def setup_chinese_font() -> None:
    preferred = ["Microsoft JhengHei", "Microsoft YaHei", "Noto Sans CJK TC", "SimHei"]
    installed = {font.name: font.fname for font in font_manager.fontManager.ttflist}
    for name in preferred:
        if name in installed:
            plt.rcParams["font.family"] = name
            break
    plt.rcParams["axes.unicode_minus"] = False


def percent_axis(axis) -> None:
    axis.yaxis.set_major_formatter(lambda value, _position: f"{value * 100:.0f}%")
    axis.grid(axis="y", alpha=0.22)


def plot_curves(new: dict) -> None:
    history = new["history"]
    epochs = [row["epoch"] for row in history]
    colors = {"HAM10000": "#1f77b4", "BCN20000": "#d95f02", "PAD-UFES-20": "#2ca02c"}
    fig, ax = plt.subplots(figsize=(10.5, 6.2))
    for source in SOURCES:
        values = [row["validation_by_source"][source]["balanced_accuracy"] for row in history]
        ax.plot(epochs, values, marker="o", linewidth=2.4, label=SOURCE_ZH[source], color=colors[source])
    mean_values = [row["mean_source_balanced_accuracy"] for row in history]
    worst_values = [row["worst_source_balanced_accuracy"] for row in history]
    ax.plot(epochs, mean_values, marker="s", linewidth=2.5, linestyle="--", color="#6a3d9a", label="三來源平均")
    ax.plot(epochs, worst_values, marker="D", linewidth=2.2, linestyle=":", color="#333333", label="最差來源")
    best_epoch = new["best"]["epoch"]
    ax.axvline(best_epoch, color="#d62728", alpha=0.65, linestyle="--", label=f"最佳 epoch：{best_epoch}")
    ax.set_title("統一資料定義與正則化訓練：驗證平衡準確率")
    ax.set_xlabel("訓練 epoch")
    ax.set_ylabel("平衡準確率")
    ax.set_xticks(epochs)
    ax.set_ylim(0.45, 0.85)
    percent_axis(ax)
    ax.legend(ncol=2, frameon=False)
    fig.tight_layout()
    fig.savefig(OUTPUT / "01_三來源驗證平衡準確率曲線.png", dpi=180)
    plt.close(fig)


def plot_before_after(new: dict, old: dict) -> list[dict]:
    old_metrics = old["best"]["validation_by_source"]
    new_metrics = new["best"]["validation_by_source"]
    old_values = [old_metrics[source]["balanced_accuracy"] for source in SOURCES]
    new_values = [new_metrics[source]["balanced_accuracy"] for source in SOURCES]
    old_mean, new_mean = float(np.mean(old_values)), float(np.mean(new_values))
    old_worst, new_worst = float(np.min(old_values)), float(np.min(new_values))
    labels = SOURCES + ["三來源平均", "最差來源"]
    old_all = old_values + [old_mean, old_worst]
    new_all = new_values + [new_mean, new_worst]
    x = np.arange(len(labels))
    width = 0.36
    fig, ax = plt.subplots(figsize=(11.5, 6.2))
    left = ax.bar(x - width / 2, old_all, width, color="#9aa6b2", label="治理前既有紀錄")
    right = ax.bar(x + width / 2, new_all, width, color="#2878b5", label="統一定義＋正則化")
    for bars in (left, right):
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.008, f"{bar.get_height()*100:.1f}%", ha="center", va="bottom", fontsize=9)
    ax.set_title("治理前後的最佳驗證平衡準確率（seed 17）")
    ax.set_ylabel("平衡準確率")
    ax.set_xticks(x, labels)
    ax.set_ylim(0.45, 0.86)
    percent_axis(ax)
    ax.legend(frameon=False)
    fig.text(0.5, 0.01, "注意：治理後移除洩漏與衝突資料；舊、新驗證筆數略有不同，因此此圖是歷史參考比較，不是嚴格單變量消融。", ha="center", fontsize=9, color="#555555")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(OUTPUT / "02_治理前後最佳驗證結果.png", dpi=180)
    plt.close(fig)

    rows = []
    for label, before, after in zip(labels, old_all, new_all):
        rows.append({"項目": label, "治理前": before, "統一定義與正則化": after, "差異_百分點": (after - before) * 100})
    return rows


def plot_class_recalls(new: dict) -> None:
    metrics = new["best"]["validation_by_source"]
    x = np.arange(len(CLASS_ZH))
    width = 0.25
    fig, ax = plt.subplots(figsize=(13, 6.7))
    colors = ["#1f77b4", "#d95f02", "#2ca02c"]
    for offset, source, color in zip([-1, 0, 1], SOURCES, colors):
        supported = set(metrics[source]["metric_labels"])
        recall = metrics[source]["recall_per_class"]
        values = [recall[index] if index in supported else np.nan for index in range(7)]
        ax.bar(x + offset * width, values, width, label=source, color=color)
    ax.set_title("最佳模型在各來源的疾病召回率（epoch 4）")
    ax.set_ylabel("召回率")
    ax.set_xticks(x, CLASS_ZH, rotation=18, ha="right")
    ax.set_ylim(0, 1.06)
    percent_axis(ax)
    ax.legend(frameon=False)
    fig.text(0.5, 0.01, "PAD-UFES-20 不提供皮膚纖維瘤與血管性病變，圖中不以 0% 表示。", ha="center", fontsize=9, color="#555555")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(OUTPUT / "03_最佳模型各疾病召回率.png", dpi=180)
    plt.close(fig)


def write_outputs(new: dict, old: dict, comparison: list[dict]) -> None:
    with (OUTPUT / "治理前後指標比較.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(comparison[0]))
        writer.writeheader()
        writer.writerows(comparison)

    new_best = new["best"]
    old_best = old["best"]
    source_lines = []
    for source in SOURCES:
        before = old_best["validation_by_source"][source]
        after = new_best["validation_by_source"][source]
        source_lines.append(
            f"| {source} | {before['balanced_accuracy']*100:.2f}% | {after['balanced_accuracy']*100:.2f}% | "
            f"{(after['balanced_accuracy']-before['balanced_accuracy'])*100:+.2f} | "
            f"{before['macro_f1']*100:.2f}% | {after['macro_f1']*100:.2f}% |"
        )
    old_values = [old_best["validation_by_source"][source]["balanced_accuracy"] for source in SOURCES]
    report = f"""# seed 17 結果摘要

## 訓練狀態

- 架構：ConvNeXt-Tiny，ImageNet 初始化，七分類。
- 正式輸入：`unified_manifest_v1.csv`。
- 訓練 8 個 epoch 後由 Early Stopping 結束。
- 最佳模型：epoch {new_best['epoch']}。
- 模型選擇分數：`0.5 × 三來源平均 BA + 0.5 × 最差來源 BA`。
- test split：未使用。

## 最佳結果

| 指標 | 結果 |
|---|---:|
| 三來源平均 Balanced Accuracy | {new_best['mean_source_balanced_accuracy']*100:.2f}% |
| 最差來源 Balanced Accuracy | {new_best['worst_source_balanced_accuracy']*100:.2f}% |
| Robust selection score | {new_best['robust_selection_score']*100:.2f}% |
| 訓練監測 Balanced Accuracy | {new_best['train_monitor']['balanced_accuracy']*100:.2f}% |

## 與治理前既有 seed 17 紀錄比較

| 來源 | 舊 BA | 新 BA | BA 差異（百分點） | 舊 macro-F1 | 新 macro-F1 |
|---|---:|---:|---:|---:|---:|
{chr(10).join(source_lines)}
| 三來源平均 | {np.mean(old_values)*100:.2f}% | {new_best['mean_source_balanced_accuracy']*100:.2f}% | {(new_best['mean_source_balanced_accuracy']-np.mean(old_values))*100:+.2f} | — | — |
| 最差來源 | {np.min(old_values)*100:.2f}% | {new_best['worst_source_balanced_accuracy']*100:.2f}% | {(new_best['worst_source_balanced_accuracy']-np.min(old_values))*100:+.2f} | — | — |

## 簡單結論

統一資料定義與正則化後，HAM10000 的 Balanced Accuracy 小幅下降，但 BCN20000 與 PAD-UFES-20 都提高，三來源平均與最差來源表現同步改善。這表示模型較不集中於 HAM10000，而朝跨來源平衡移動。不過 BCN20000 仍是最差來源，且最佳 epoch 的訓練監測 BA 與 BCN 驗證 BA 相差約 {(new_best['train_monitor']['balanced_accuracy']-new_best['validation_by_source']['BCN20000']['balanced_accuracy'])*100:.2f} 個百分點，過擬合／領域差異仍未解決。

治理前後的驗證筆數略有差異：新流程排除了洩漏與標籤衝突資料，因此這是歷史參考比較，不是嚴格的單變量消融。正式論文結論至少需要 seed 42 與 2026，並以三次平均及樣本標準差報告。
"""
    (OUTPUT / "seed17_結果摘要.md").write_text(report, encoding="utf-8")


def main() -> None:
    setup_chinese_font()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    new, old = read_json(NEW_PATH), read_json(OLD_PATH)
    plot_curves(new)
    comparison = plot_before_after(new, old)
    plot_class_recalls(new)
    write_outputs(new, old, comparison)
    print(f"已輸出：{OUTPUT}")


if __name__ == "__main__":
    main()
