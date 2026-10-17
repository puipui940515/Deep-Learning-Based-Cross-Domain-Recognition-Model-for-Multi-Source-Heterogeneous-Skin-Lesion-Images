from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager


ROOT = Path(__file__).resolve().parents[1]
SHORT_PATH = ROOT / "results/formal_v1/regularized_seed17/result.json"
LONG_PATH = ROOT / "results/formal_v2_long/regularized_seed17/result.json"
OUTPUT = ROOT / "results/formal_v2_long/regularized_seed17/圖表與摘要"
SOURCES = ["HAM10000", "BCN20000", "PAD-UFES-20"]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def setup_font() -> None:
    installed = {font.name for font in font_manager.fontManager.ttflist}
    for candidate in ["Microsoft JhengHei", "Microsoft YaHei", "Noto Sans CJK TC", "SimHei"]:
        if candidate in installed:
            plt.rcParams["font.family"] = candidate
            break
    plt.rcParams["axes.unicode_minus"] = False


def as_percent(axis) -> None:
    axis.yaxis.set_major_formatter(lambda value, _position: f"{value * 100:.0f}%")
    axis.grid(axis="y", alpha=0.22)


def plot_robust_curves(short: dict, long: dict) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 6.0))
    for result, label, color in [
        (short, "上一版：12 epoch 設定", "#8b9aa9"),
        (long, "長訓練：30 epoch 設定", "#2878b5"),
    ]:
        epochs = [row["epoch"] for row in result["history"]]
        values = [row["robust_selection_score"] for row in result["history"]]
        ax.plot(epochs, values, marker="o", markersize=3.5, linewidth=2.2, label=label, color=color)
        best = result["best"]
        ax.scatter([best["epoch"]], [best["robust_selection_score"]], s=85, zorder=5, color=color, edgecolor="black")
    ax.set_title("短版與長版訓練的穩健選模分數曲線（seed 17）")
    ax.set_xlabel("訓練 epoch")
    ax.set_ylabel("穩健選模分數")
    ax.set_ylim(0.54, 0.71)
    as_percent(ax)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUTPUT / "01_短版與長版穩健分數曲線.png", dpi=180)
    plt.close(fig)


def plot_best_comparison(short: dict, long: dict) -> None:
    labels = SOURCES + ["三來源平均", "最差來源"]
    short_values = [short["best"]["validation_by_source"][source]["balanced_accuracy"] for source in SOURCES]
    long_values = [long["best"]["validation_by_source"][source]["balanced_accuracy"] for source in SOURCES]
    short_values += [short["best"]["mean_source_balanced_accuracy"], short["best"]["worst_source_balanced_accuracy"]]
    long_values += [long["best"]["mean_source_balanced_accuracy"], long["best"]["worst_source_balanced_accuracy"]]
    x = np.arange(len(labels))
    width = 0.36
    fig, ax = plt.subplots(figsize=(11.5, 6.2))
    bars_short = ax.bar(x - width / 2, short_values, width, color="#8b9aa9", label="上一版最佳 epoch 4")
    bars_long = ax.bar(x + width / 2, long_values, width, color="#2878b5", label="長訓練最佳 epoch 25")
    for bars in [bars_short, bars_long]:
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.006, f"{bar.get_height()*100:.1f}%", ha="center", fontsize=9)
    ax.set_title("相同資料下：上一版與長訓練最佳結果")
    ax.set_ylabel("Balanced Accuracy")
    ax.set_xticks(x, labels)
    ax.set_ylim(0.55, 0.82)
    as_percent(ax)
    ax.legend(frameon=False)
    fig.text(0.5, 0.01, "兩者使用相同統一資料；長版同時改變學習率、MixUp、epoch 與 patience，因此只能比較整體訓練方案。", ha="center", fontsize=9, color="#555555")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(OUTPUT / "02_短版與長版最佳結果.png", dpi=180)
    plt.close(fig)


def write_summary(short: dict, long: dict) -> None:
    short_best, long_best = short["best"], long["best"]
    rows = []
    for source in SOURCES:
        before = short_best["validation_by_source"][source]
        after = long_best["validation_by_source"][source]
        rows.append(
            f"| {source} | {before['balanced_accuracy']*100:.2f}% | {after['balanced_accuracy']*100:.2f}% | "
            f"{(after['balanced_accuracy']-before['balanced_accuracy'])*100:+.2f} | "
            f"{before['macro_f1']*100:.2f}% | {after['macro_f1']*100:.2f}% |"
        )
    text = f"""# 長訓練 seed 17 結果摘要

## 實際執行情況

- 訓練資料：18,922 筆；驗證資料：HAM 1,504、BCN 1,712、PAD 398。
- 實際完成：30 epochs。
- 最佳模型：epoch {long_best['epoch']}。
- Early Stopping：未觸發，因為最佳點出現在 epoch 25，距離結束只有 5 epochs。
- test split：未使用。
- 原始 `result.json` 的 `regularization.epochs=12` 是舊版紀錄程式未同步命令列覆寫造成；實際 history 有 30 筆。程式已修正，模型權重不受影響。

## 與上一版相同 seed、相同資料比較

| 來源 | 上一版 BA | 長版 BA | BA 差異（百分點） | 上一版 macro-F1 | 長版 macro-F1 |
|---|---:|---:|---:|---:|---:|
{chr(10).join(rows)}
| 三來源平均 | {short_best['mean_source_balanced_accuracy']*100:.2f}% | {long_best['mean_source_balanced_accuracy']*100:.2f}% | {(long_best['mean_source_balanced_accuracy']-short_best['mean_source_balanced_accuracy'])*100:+.2f} | — | — |
| 最差來源 | {short_best['worst_source_balanced_accuracy']*100:.2f}% | {long_best['worst_source_balanced_accuracy']*100:.2f}% | {(long_best['worst_source_balanced_accuracy']-short_best['worst_source_balanced_accuracy'])*100:+.2f} | — | — |
| Robust score | {short_best['robust_selection_score']*100:.2f}% | {long_best['robust_selection_score']*100:.2f}% | {(long_best['robust_selection_score']-short_best['robust_selection_score'])*100:+.2f} | — | — |

## 結論

長訓練沒有改善跨來源核心指標。HAM10000 略升，但 BCN20000、PAD-UFES-20、三來源平均、最差來源與 Robust score 都略降。長版最佳 epoch 的訓練監測 BA 為 {long_best['train_monitor']['balanced_accuracy']*100:.2f}%，BCN 驗證 BA 為 {long_best['validation_by_source']['BCN20000']['balanced_accuracy']*100:.2f}%，差距達 {(long_best['train_monitor']['balanced_accuracy']-long_best['validation_by_source']['BCN20000']['balanced_accuracy'])*100:.2f} 個百分點。結果不支持單純增加訓練時間；下一步應改變泛化策略，而不是再增加 epochs。
"""
    (OUTPUT / "長訓練_seed17_結果摘要.md").write_text(text, encoding="utf-8")


def main() -> None:
    setup_font()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    short, long = load(SHORT_PATH), load(LONG_PATH)
    plot_robust_curves(short, long)
    plot_best_comparison(short, long)
    write_summary(short, long)
    print(f"已輸出：{OUTPUT}")


if __name__ == "__main__":
    main()
