from __future__ import annotations
import torch
from torch import nn
from torch.utils.checkpoint import checkpoint
from torchvision.models import convnext_tiny

class ConvNeXtFeatureBackbone(nn.Module):
    def __init__(self, model):
        super().__init__()
        self.features, self.avgpool = model.features, model.avgpool
        self.norm, self.flatten = model.classifier[0], model.classifier[1]
        self.output_dim = model.classifier[2].in_features
    def forward(self, image):
        return self.flatten(self.norm(self.avgpool(self.features(image))))

class MultiViewConvNeXt(nn.Module):
    def __init__(self, classifier_model, num_classes=7, num_views=4, fusion_hidden_dim=768,
                 fusion_dropout=0.1, gradient_checkpointing=True):
        super().__init__()
        self.backbone = ConvNeXtFeatureBackbone(classifier_model)
        self.num_views, self.gradient_checkpointing = num_views, gradient_checkpointing
        dim = self.backbone.output_dim
        self.view_embeddings = nn.Parameter(torch.zeros(num_views, dim))
        nn.init.normal_(self.view_embeddings, std=0.02)
        self.fusion = nn.Sequential(nn.Linear(num_views * dim, fusion_hidden_dim), nn.GELU(),
                                    nn.Dropout(fusion_dropout), nn.Linear(fusion_hidden_dim, num_classes))
    def forward(self, views):
        if len(views) != self.num_views:
            raise ValueError(f"預期 {self.num_views} 個視角，收到 {len(views)} 個")
        encoded = []
        for index, view in enumerate(views):
            feature = checkpoint(self.backbone, view, use_reentrant=False) if self.training and self.gradient_checkpointing else self.backbone(view)
            encoded.append(feature + self.view_embeddings[index])
        return self.fusion(torch.cat(encoded, dim=1))

def build_v10_model(num_classes=7, fusion_hidden_dim=768, fusion_dropout=0.1, gradient_checkpointing=True):
    base = convnext_tiny(weights=None)
    base.classifier[2] = nn.Linear(base.classifier[2].in_features, num_classes)
    return MultiViewConvNeXt(base, num_classes, 4, fusion_hidden_dim, fusion_dropout, gradient_checkpointing)

def load_v9_backbone(model, checkpoint_path, device="cpu"):
    state = torch.load(checkpoint_path, map_location=device, weights_only=False)
    source, target, mapped = state["model"], model.backbone.state_dict(), {}
    for key in target:
        if key.startswith("norm."): source_key = "classifier.0." + key.removeprefix("norm.")
        elif key.startswith("flatten."): source_key = "classifier.1." + key.removeprefix("flatten.")
        else: source_key = key
        if source_key in source: mapped[key] = source[source_key]
    missing = sorted(set(target) - set(mapped))
    if missing: raise RuntimeError(f"v9 checkpoint 缺少骨幹參數：{missing[:5]}")
    model.backbone.load_state_dict(mapped, strict=True)
    return state

def count_parameters(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)
