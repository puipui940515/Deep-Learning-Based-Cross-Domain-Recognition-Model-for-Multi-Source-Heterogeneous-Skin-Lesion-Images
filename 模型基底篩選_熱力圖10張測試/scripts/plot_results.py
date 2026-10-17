from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


STAGE = Path(__file__).resolve().parents[1]
PROJECT = STAGE.parent
RESULTS = STAGE / "results"
CHARTS = STAGE / "圖表"
CHARTS.mkdir(parents=True, exist_ok=True)

plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Microsoft YaHei", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def pct(value):
    return f"{value * 100:.1f}%"


def main():
    summary = pd.read_csv(RESULTS / "model_summary.csv")
    detail = pd.read_csv(RESULTS / "per_image_results.csv")
    eligible = summary[summary["heatmap_available_rate"] >= 0.999].copy()
    eligible = eligible.sort_values("screening_score", ascending=True)

    fig, axes = plt.subplots(1, 4, figsize=(23, max(10, len(eligible) * 0.48)), sharey=True)
    panels = [
        ("balanced_accuracy", "十張平衡準確率", 100),
        ("faithfulness_margin", "熱區忠實度差", 100),
        ("flip_top20_iou", "翻轉熱區 IoU", 100),
        ("screening_score", "綜合篩選分數", 1),
    ]
    y = np.arange(len(eligible))
    for axis, (column, title, factor) in zip(axes, panels):
        values = eligible[column].to_numpy(float) * factor
        axis.barh(y, values, color="#2878B5")
        axis.set_title(title)
        axis.set_xlabel("百分比／分數")
        axis.grid(axis="x", alpha=0.22)
        for index, value in enumerate(values):
            axis.text(value, index, f" {value:.1f}", va="center", fontsize=8)
    axes[0].set_yticks(y, eligible["model_name"])
    fig.suptitle("基底模型十張分類與 Grad-CAM 快速篩選", fontsize=17)
    fig.tight_layout()
    fig.savefig(CHARTS / "01_全模型綜合比較.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 8))
    categories = eligible["category"].drop_duplicates().tolist()
    colors = plt.cm.tab10(np.linspace(0, 1, max(len(categories), 1)))
    for color, category in zip(colors, categories):
        part = eligible[eligible["category"] == category]
        ax.scatter(part["balanced_accuracy"] * 100, part["faithfulness_margin"] * 100,
                   s=55 + part["flip_top20_iou"] * 260, alpha=0.82, label=category, color=color)
        for _, row in part.iterrows():
            ax.annotate(row["model_name"], (row["balanced_accuracy"] * 100, row["faithfulness_margin"] * 100),
                        xytext=(4, 4), textcoords="offset points", fontsize=8)
    ax.axhline(0, color="#555555", linewidth=1)
    ax.set_xlabel("十張 Balanced Accuracy（%）")
    ax.set_ylabel("高熱區遮擋 − 低熱區遮擋的機率下降（百分點）")
    ax.set_title("分類表現與熱力圖忠實度")
    ax.grid(alpha=0.22)
    ax.legend(title="初始化／特徵來源", fontsize=8)
    fig.tight_layout()
    fig.savefig(CHARTS / "02_分類與熱力圖忠實度.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    top_ids = eligible.sort_values("screening_score", ascending=False).head(5)["model_id"].tolist()
    matrix = detail[detail["model_id"].isin(top_ids)].copy()
    order = eligible.sort_values("screening_score", ascending=False).head(5)["model_name"].tolist()
    samples = detail.drop_duplicates("sample_id").sort_values("sample_id")
    fig, ax = plt.subplots(figsize=(14, 5.8))
    values = np.zeros((len(order), len(samples)))
    labels = [["" for _ in range(len(samples))] for _ in range(len(order))]
    for i, model_name in enumerate(order):
        for j, sample_id in enumerate(samples["sample_id"]):
            row = matrix[(matrix["model_name"] == model_name) & (matrix["sample_id"] == sample_id)].iloc[0]
            values[i, j] = row["correct"]
            labels[i][j] = row["prediction_name"]
    ax.imshow(values, cmap=plt.matplotlib.colors.ListedColormap(["#E07A5F", "#59A14F"]), vmin=0, vmax=1, aspect="auto")
    for i in range(len(order)):
        for j in range(len(samples)):
            ax.text(j, i, labels[i][j], ha="center", va="center", fontsize=8, color="white")
    xlabels = [f"{row.sample_id}\n{row.source}\n真值 {row.target_name}" for row in samples.itertuples()]
    ax.set_xticks(range(len(samples)), xlabels, rotation=35, ha="right")
    ax.set_yticks(range(len(order)), order)
    ax.set_title("綜合前五名：十張逐圖預測（綠＝正確，紅＝錯誤）")
    fig.tight_layout()
    fig.savefig(CHARTS / "03_前五名逐圖預測.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    pairs = [
        ("frozen_imagenet", "frozen_densepose_true", "凍結 Backbone"),
        ("parallel_imagenet", "parallel_densepose_true", "並行特徵"),
        ("finetune_imagenet", "finetune_densepose_true", "完整微調"),
    ]
    metrics = [("balanced_accuracy", "平衡準確率"), ("faithfulness_margin", "熱力圖忠實度差"), ("flip_top20_iou", "翻轉熱區 IoU")]
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    for axis, (metric, title) in zip(axes, metrics):
        x = np.arange(len(pairs)); width = 0.36
        imagenet = [float(summary.loc[summary.model_id == a, metric].iloc[0]) * 100 for a, _, _ in pairs]
        body = [float(summary.loc[summary.model_id == b, metric].iloc[0]) * 100 for _, b, _ in pairs]
        axis.bar(x - width / 2, imagenet, width, label="ImageNet", color="#4E79A7")
        axis.bar(x + width / 2, body, width, label="部位預訓練", color="#F28E2B")
        axis.set_xticks(x, [label for _, _, label in pairs], rotation=18)
        axis.set_title(title)
        axis.set_ylabel("%／百分點")
        axis.grid(axis="y", alpha=0.22)
        for pos, value in zip(x - width / 2, imagenet): axis.text(pos, value, f"{value:.1f}", ha="center", va="bottom", fontsize=8)
        for pos, value in zip(x + width / 2, body): axis.text(pos, value, f"{value:.1f}", ha="center", va="bottom", fontsize=8)
    axes[0].legend()
    fig.suptitle("ImageNet 與部位預訓練的相同結構配對比較")
    fig.tight_layout()
    fig.savefig(CHARTS / "04_ImageNet與部位預訓練.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    top = summary[summary["heatmap_available_rate"] >= 0.999].sort_values("screening_score", ascending=False).head(5)
    sample_rows = detail.drop_duplicates("sample_id").sort_values("sample_id")
    thumb = 150
    canvas = Image.new("RGB", (thumb * 5, thumb * 2 * len(top)), "white")
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msjh.ttc", 14)
        small = ImageFont.truetype("C:/Windows/Fonts/msjh.ttc", 11)
    except OSError:
        font = small = ImageFont.load_default()
    for model_index, model in enumerate(top.itertuples()):
        model_rows = detail[detail["model_id"] == model.model_id].sort_values("sample_id")
        for sample_index, row in enumerate(model_rows.itertuples()):
            image = Image.open(PROJECT / sample_rows.iloc[sample_index]["image_path"]).convert("RGB").resize((thumb, thumb))
            overlay = Image.open(STAGE / row.overlay_path).convert("RGB").resize((thumb, thumb))
            column = sample_index % 5
            block = sample_index // 5
            base_y = (model_index * 2 + block) * thumb
            blended = Image.blend(image, overlay, 0.72)
            canvas.paste(blended, (column * thumb, base_y))
            draw.rectangle((column * thumb, base_y, column * thumb + thumb, base_y + 35), fill=(255, 255, 255))
            draw.text((column * thumb + 3, base_y + 2), f"{model.model_name}", fill=(20, 20, 20), font=small)
            draw.text((column * thumb + 3, base_y + 18), f"{row.sample_id} 真{row.target_name}／預{row.prediction_name}", fill=(20, 20, 20), font=small)
    canvas.save(CHARTS / "05_前五名十張熱力圖總覽.jpg", quality=90, optimize=True)

    winner = summary[summary["heatmap_available_rate"] >= 0.999].sort_values("screening_score", ascending=False).iloc[0]
    baseline = summary[summary["model_id"] == "mixed_convnext"].iloc[0] if (summary["model_id"] == "mixed_convnext").any() else None
    report = [
        "# 十張模型與熱力圖快速篩選結果",
        "",
        f"- 成功測試模型：{int((summary['samples'].fillna(0) > 0).sum())} 個。",
        f"- 可完成 Grad-CAM 全測試：{int((summary['heatmap_available_rate'].fillna(0) >= 0.999).sum())} 個。",
        f"- 本輪暫定第一名：**{winner['model_name']}**，篩選分數 {winner['screening_score']:.2f}。",
        f"- 第一名十張 Balanced Accuracy：{pct(winner['balanced_accuracy'])}；Accuracy：{pct(winner['accuracy'])}。",
        f"- 第一名熱力圖忠實度差：{winner['faithfulness_margin'] * 100:.2f} 個百分點；翻轉熱區 IoU：{pct(winner['flip_top20_iou'])}。",
        "",
        "## 判讀限制",
        "",
        "這是十張快速篩選，不是正式最終選模。沒有病灶遮罩，因此本輪只驗證 Grad-CAM 對模型輸出的忠實度與穩定度，不能宣稱熱區等於病灶位置。正式採用前需擴大樣本、加入病灶遮罩定位指標並至少重複三個 seeds。",
        "",
        "## 輸出",
        "",
        "- `results/model_summary.csv`：模型彙總。",
        "- `results/per_image_results.csv`：逐模型逐影像結果。",
        "- `results/heatmaps/`：每個模型的逐圖熱力圖。",
        "- `圖表/`：中文比較圖。",
    ]
    (STAGE / "結果摘要.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"winner={winner['model_id']} score={winner['screening_score']:.2f}")


if __name__ == "__main__":
    main()

