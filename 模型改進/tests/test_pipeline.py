from pathlib import Path
import sys
import numpy as np
import pytest
from PIL import Image

EXP=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(EXP/'src')); sys.path.insert(0,str(EXP/'scripts'))
from common import load,read_rows,sha
from geometry import estimate,crop
from train import allocate,Images


def test_real_manifest_group_roles_and_support():
    rows=read_rows(EXP/'data/cp005_manifest.csv'); groups={}
    for r in rows:
        assert groups.setdefault(r['cp005_group'],r['split'])==r['split']
    for source in {r['source'] for r in rows}:
        expected={r['label'] for r in rows if r['source']==source}
        for split in ['train','val_select','val_assess']:
            assert {r['label'] for r in rows if r['source']==source and r['split']==split}==expected
    assert len(rows)==86534
    assert sha(EXP/'data/cp005_manifest.csv')==load(EXP/'reports/cp005_split.json')['manifest_sha256']


def test_output_rerun_preserves_previous(tmp_path):
    a=allocate(tmp_path,'R0_hash_seed17'); (a/'result.json').write_text('original')
    b=allocate(tmp_path,'R0_hash_seed17')
    assert a!=b and b.name.endswith('_rerun1')
    assert (a/'result.json').read_text()=='original'


def test_dark_lesion_estimate_and_fallback():
    a=np.full((200,300,3),180,dtype=np.uint8); a[60:140,100:200]=70
    im=Image.fromarray(a); result=estimate(im,'D2')
    assert not result['fallback']
    assert .1<result['area_fraction']<.2
    cut=crop(im,'D2',1.5,result); assert cut.width==cut.height
    flat=Image.new('RGB',(300,200),(180,180,180))
    assert estimate(flat)['fallback']
    assert crop(flat,'D0').size==(140,140)


def test_real_input_and_eight_class_forward_backward():
    import torch
    from train import build_model
    cfg=load(EXP/'config.json'); cfg['run']=cfg['runs']['R0']
    rows=read_rows(EXP/'data/cp005_manifest.csv')
    image,label,source=Images(rows[:1],cfg)[0]
    assert image.shape==(3,224,224) and torch.isfinite(image).all()
    device='cuda' if torch.cuda.is_available() else 'cpu'
    model=build_model('convnext_tiny',False,8).to(device)
    # Synthetic optimization signal only; no experiment checkpoint or real-data training.
    x=torch.randn(1,3,224,224,device=device)
    out=model(x); assert out.shape==(1,8)
    torch.nn.functional.cross_entropy(out,torch.tensor([7],device=device)).backward()
    assert model.classifier[2].weight.grad is not None


def test_registered_effective_batch():
    cfg=load(EXP/'config.json')
    for run in cfg['runs'].values():
        assert cfg['training']['effective_batch']==32
        assert 32%run['batch_size']==0 and run['size']<=384
