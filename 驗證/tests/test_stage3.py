import sys, unittest
from pathlib import Path
import torch
from torch import nn
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT/"第三階段/src"))
from stage3.data import V10NullControlDataset
from stage3.models import MultiViewConvNeXt
class TinyClassifier(nn.Module):
    def __init__(self):
        super().__init__(); self.features=nn.Sequential(nn.Conv2d(3,8,3,padding=1),nn.ReLU()); self.avgpool=nn.AdaptiveAvgPool2d(1); self.classifier=nn.Sequential(nn.Identity(),nn.Flatten(1),nn.Linear(8,7))
class Stage3Tests(unittest.TestCase):
    def test_output_shape_and_shared_backbone(self):
        model=MultiViewConvNeXt(TinyClassifier(),7,fusion_hidden_dim=16,gradient_checkpointing=False); image=torch.randn(2,3,16,16)
        self.assertEqual(tuple(model((image,image,image,image)).shape),(2,7)); self.assertEqual(sum(isinstance(m,nn.Conv2d) for m in model.modules()),1)
    def test_wrong_view_count(self):
        model=MultiViewConvNeXt(TinyClassifier(),7,fusion_hidden_dim=16,gradient_checkpointing=False)
        with self.assertRaises(ValueError): model((torch.randn(1,3,16,16),))
    def test_test_split_is_sealed(self):
        with self.assertRaises(ValueError): V10NullControlDataset("unused.csv","unused","test",None)
if __name__=="__main__": unittest.main()
