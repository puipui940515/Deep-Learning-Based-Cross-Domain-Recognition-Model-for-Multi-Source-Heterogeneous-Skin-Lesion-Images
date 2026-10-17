import torch
from torch import nn
class LogitAdjustedCrossEntropy(nn.Module):
    def __init__(self, class_counts, tau=1.0):
        super().__init__()
        counts = torch.as_tensor(class_counts, dtype=torch.float32)
        self.register_buffer("adjustment", tau * (counts / counts.sum()).clamp_min(1e-12).log())
    def forward(self, logits, targets):
        return nn.functional.cross_entropy(logits + self.adjustment, targets)
