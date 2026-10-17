from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path


LIBRARY = Path(__file__).resolve().parent
ROOT = LIBRARY.parent
MODELS_DIR = LIBRARY / "models"


MODELS = [
    {"id": "stage1_v1", "group": "第一階段", "name": "第一階段 v1／MLP／seed 17", "architecture": "mlp", "image_size": 64, "wrapper": "standard", "source": "第一階段/checkpoints/v1_seed17.pt"},
    {"id": "stage1_v1_noisefilter", "group": "第一階段", "name": "第一階段 v1＋NoiseFilter／seed 17", "architecture": "mlp", "image_size": 64, "wrapper": "noisefilter", "alpha": [0.25, 0.5, 0.5, 0.5], "vendor": "第一階段/noisefilter搭載實驗/vendor", "source": "第一階段/noisefilter搭載實驗/checkpoints/stage1_v1_noisefilter_core_fixed_seed17.pt"},
    {"id": "stage2_v5", "group": "第二階段", "name": "第二階段 v5／ResNet18 從零訓練／seed 17", "architecture": "resnet18", "image_size": 224, "wrapper": "standard", "source": "第二階段/checkpoints/v5_seed17.pt"},
    {"id": "stage2_v6", "group": "第二階段", "name": "第二階段 v6／ResNet18 ImageNet／seed 17", "architecture": "resnet18", "image_size": 224, "wrapper": "standard", "source": "第二階段/checkpoints/v6_seed17.pt"},
    {"id": "stage2_v7", "group": "第二階段", "name": "第二階段 v7／ConvNeXt-Tiny ImageNet 224／seed 17", "architecture": "convnext_tiny", "image_size": 224, "wrapper": "standard", "source": "第二階段/checkpoints/v7_seed17.pt"},
    {"id": "stage2_v8", "group": "第二階段", "name": "第二階段 v8／ConvNeXt-Tiny ImageNet 384／seed 17", "architecture": "convnext_tiny", "image_size": 384, "wrapper": "standard", "source": "第二階段/checkpoints/v8_seed17.pt"},
    {"id": "stage2_v10", "group": "第二階段", "name": "第二階段 v10／ConvNeXt-Tiny 純淨版／seed 17", "architecture": "convnext_tiny", "image_size": 224, "wrapper": "standard", "source": "第二階段/checkpoints/v10_seed17.pt"},
    {"id": "stage2_v5_noisefilter", "group": "第二階段", "name": "第二階段 v5＋NoiseFilter／seed 17", "architecture": "resnet18", "image_size": 224, "wrapper": "noisefilter", "alpha": [0.25, 0.5, 0.5, 0.5], "vendor": "第二階段/noisefilter搭載實驗/vendor", "source": "第二階段/noisefilter搭載實驗/checkpoints/stage2_v5_noisefilter_core_fixed_seed17.pt"},
    {"id": "frozen_imagenet", "group": "凍結 Backbone", "name": "凍結 Backbone／ImageNet／seed 17", "architecture": "convnext_tiny", "image_size": 224, "wrapper": "standard", "source": "第二階段/凍結部位Backbone短訓練/results/imagenet_frozen/seed17/best.pt"},
    {"id": "frozen_densepose_true", "group": "凍結 Backbone", "name": "凍結 Backbone／真實部位預訓練／seed 17", "architecture": "convnext_tiny", "image_size": 224, "wrapper": "standard", "source": "第二階段/凍結部位Backbone短訓練/results/densepose_true_frozen/seed17/best.pt"},
    {"id": "frozen_densepose_shuffled", "group": "凍結 Backbone", "name": "凍結 Backbone／打亂部位對照／seed 17", "architecture": "convnext_tiny", "image_size": 224, "wrapper": "standard", "source": "第二階段/凍結部位Backbone短訓練/results/densepose_shuffled_frozen/seed17/best.pt"},
    {"id": "parallel_imagenet", "group": "並行特徵", "name": "並行特徵／ImageNet teacher／seed 17", "architecture": "parallel_convnext", "image_size": 224, "wrapper": "parallel", "teacher_classes": 1000, "source": "第二階段/並行凍結部位特徵實驗/results/imagenet_teacher/seed17/best.pt"},
    {"id": "parallel_densepose_true", "group": "並行特徵", "name": "並行特徵／真實部位 teacher／seed 17", "architecture": "parallel_convnext", "image_size": 224, "wrapper": "parallel", "teacher_classes": 5, "source": "第二階段/並行凍結部位特徵實驗/results/densepose_true_teacher/seed17/best.pt"},
    {"id": "parallel_densepose_shuffled", "group": "並行特徵", "name": "並行特徵／打亂部位 teacher／seed 17", "architecture": "parallel_convnext", "image_size": 224, "wrapper": "parallel", "teacher_classes": 5, "source": "第二階段/並行凍結部位特徵實驗/results/densepose_shuffled_teacher/seed17/best.pt"},
    {"id": "finetune_imagenet", "group": "完整微調", "name": "完整微調／ImageNet 初始化／seed 17", "architecture": "convnext_tiny", "image_size": 224, "wrapper": "standard", "source": "第二階段/部位權重完整微調正式對照/results/imagenet_init/seed17/best.pt"},
    {"id": "finetune_densepose_true", "group": "完整微調", "name": "完整微調／真實部位初始化／seed 17", "architecture": "convnext_tiny", "image_size": 224, "wrapper": "standard", "source": "第二階段/部位權重完整微調正式對照/results/densepose_true_init/seed17/best.pt"},
    {"id": "mixed_v1", "group": "多來源訓練", "name": "HAM10000＋BCN20000／ConvNeXt-Tiny", "architecture": "convnext_tiny", "image_size": 224, "wrapper": "standard", "source": "多來源混合訓練_第一版/results/imagenet_seed17/best.pt"},
    {"id": "mixed_convnext", "group": "多來源訓練", "name": "HAM10000＋BCN20000＋PAD-UFES-20／ConvNeXt-Tiny", "architecture": "convnext_tiny", "image_size": 224, "wrapper": "standard", "source": "多來源混合訓練_第二版/results/imagenet_seed17/best.pt"},
    {"id": "mixed_resnet18", "group": "多來源訓練", "name": "HAM10000＋BCN20000＋PAD-UFES-20／ResNet18", "architecture": "resnet18", "image_size": 224, "wrapper": "standard", "source": "多來源混合訓練_ResNet18對照/results/imagenet_seed17/best.pt"},
    {"id": "governance_v1_seed17", "group": "資料治理後模型", "name": "治理 v1／ConvNeXt-Tiny／seed 17", "architecture": "convnext_tiny", "image_size": 224, "wrapper": "standard", "normalization": {"mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225]}, "source": "資料治理與泛化修復/results/formal_v1/regularized_seed17/best.pt"},
    {"id": "governance_v1_seed42", "group": "資料治理後模型", "name": "治理 v1／ConvNeXt-Tiny／seed 42", "architecture": "convnext_tiny", "image_size": 224, "wrapper": "standard", "normalization": {"mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225]}, "source": "資料治理與泛化修復/results/formal_v1/regularized_seed42/best.pt"},
    {"id": "governance_v2_long_seed17", "group": "資料治理後模型", "name": "治理 v2 長訓練／ConvNeXt-Tiny／seed 17", "architecture": "convnext_tiny", "image_size": 224, "wrapper": "standard", "normalization": {"mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225]}, "source": "資料治理與泛化修復/results/formal_v2_long/regularized_seed17/best.pt"},
    {"id": "governance_v3a_seed17", "group": "資料治理後模型", "name": "治理 v3a 完整覆蓋／ConvNeXt-Tiny／seed 17", "architecture": "convnext_tiny", "image_size": 224, "wrapper": "standard", "normalization": {"mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225]}, "source": "資料治理與泛化修復/results/formal_v3a_coverage/regularized_seed17/best.pt"},
    {"id": "explicit_fusion_seed17", "group": "研究模型（UI 尚未支援）", "name": "顯式特徵 Fusion／seed 17", "architecture": "convnext_tiny", "image_size": 224, "wrapper": "explicit_fusion", "runtime_supported": False, "source": "資料治理與泛化修復/顯式影像特徵融合實驗/results/fusion_seed17/best.pt"},
    {"id": "configurable_resnet18_v13_seed17", "group": "研究模型（UI 尚未支援）", "name": "可切換全功能 ResNet18／seed 17", "architecture": "resnet18", "image_size": 224, "wrapper": "configurable_full", "runtime_supported": False, "source": "基底模型發展_可切換正式訓練/results/base_resnet18_full_features_v1_seed17/best.pt"},
]


# --- 格式約定 v1：階段受控詞彙對照（見 開發歷程/格式約定.md §2）---
# 既有欄位一律保留以維持 UI 相容；標準欄位為「附加」，不取代。
CANONICAL_STAGE = {
    "泛化修復": "泛化修復階段", "資料治理後模型": "泛化修復階段",
    "基底篩選": "基底篩選階段", "基底模型": "基底模型階段",
    "多來源訓練": "多來源訓練階段", "部位預測": "部位預測階段",
    "跨資料集驗證": "驗證階段", "外部案例": "驗證階段", "實驗彙整": "專案治理",
    "第一階段": "第一階段", "第二階段": "第二階段", "第三階段": "第三階段",
    "驗證階段": "驗證階段", "課程學習階段": "課程學習階段", "專案治理": "專案治理",
}
METHOD_GROUPS = {"並行特徵", "凍結 Backbone", "完整微調", "研究模型（UI 尚未支援）"}
SCHEMA_VERSION = "skindetect-index-v1"


def link_or_copy(source: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if os.path.samefile(source, destination):
            return "hardlink"
        raise RuntimeError(f"固定位置已有不同檔案：{destination}")
    try:
        os.link(source, destination)
        return "hardlink"
    except OSError:
        shutil.copy2(source, destination)
        return "copy"


def main() -> None:
    entries = []
    for definition in MODELS:
        source = ROOT / definition["source"]
        destination = MODELS_DIR / definition["id"] / "model.pt"
        available = source.is_file()
        runtime_supported = bool(definition.get("runtime_supported", True))
        storage = "missing"
        if available:
            storage = link_or_copy(source, destination)
        entries.append({
            **definition,
            "checkpoint": destination.relative_to(LIBRARY).as_posix(),
            "available": available and destination.is_file() and runtime_supported,
            "runtime_supported": runtime_supported,
            "storage": storage,
            "size_bytes": source.stat().st_size if available else 0,
            # 格式約定 v1 附加欄位（既有欄位不變）
            "stage_canonical": (
                None if definition["group"] in METHOD_GROUPS
                else CANONICAL_STAGE.get(definition["group"], definition["group"])
            ),
            "method_group": definition["group"] if definition["group"] in METHOD_GROUPS else None,
            "name_zh": definition["name"],
        })
    payload = {
        "schema_version": SCHEMA_VERSION,
        "legacy_schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generator": "模型資產庫/sync_models.py",
        "authority": "本檔由腳本產生，請勿手動編輯。事件時間軸的權威來源為 開發歷程/時間軸.md。",
        "default_model": "mixed_convnext",
        "class_order": ["AKIEC", "BCC", "BKL", "DF", "NV", "VASC", "MEL"],
        "normalization": {"mean": [0.5, 0.5, 0.5], "std": [0.5, 0.5, 0.5]},
        "models": entries,
    }
    (LIBRARY / "model_registry.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    hardlinks = sum(item["storage"] == "hardlink" for item in entries)
    print(f"模型登錄完成：{len(entries)} 個；硬連結 {hardlinks} 個")


if __name__ == "__main__":
    main()
