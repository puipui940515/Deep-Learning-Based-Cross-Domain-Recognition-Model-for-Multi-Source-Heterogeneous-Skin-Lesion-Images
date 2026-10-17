"""P0 four-source baseline: diagnostic only, no gate and no backbone updates."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from common import ROOT,EXP,read_rows,write,sha
sys.path.insert(0,str(ROOT/'noisefilter_v2強化實驗/scripts'))
from source_probe_input import ConvNeXtFeatures,logistic_cv_ba
from _common import PixelDataset,balanced_sample
import torch
import numpy as np
from torch.utils.data import DataLoader
from tqdm import tqdm


def main():
    dest=EXP/'reports/P0_source_probe.json'
    if dest.exists(): raise SystemExit('P0 exists; refusing overwrite')
    manifest=EXP/'data/cp005_manifest.csv'
    rows=balanced_sample([r for r in read_rows(manifest) if r['split']=='val_select'],600,17)
    device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model=ConvNeXtFeatures().to(device).eval(); chunks=[]
    torch.set_num_threads(4)
    with torch.inference_mode():
        for x,_,_ in tqdm(DataLoader(PixelDataset(rows,224,exif=True),batch_size=16),desc='P0 凍結特徵'):
            chunks.append(model(x.to(device)).cpu().numpy())
    result=logistic_cv_ba(np.concatenate(chunks),np.array([r['source'] for r in rows]),5,17,
                          np.array([r['cp005_group'] for r in rows]))
    write(dest,{'manifest_sha256':sha(manifest),'split':'val_select','feature':'ImageNet ConvNeXt-Tiny frozen',
                'probe':result,'pilot':True,'seeds':[17],'backbone_trained':False,'gate':None,
                'record_ids':[r['record_id'] for r in rows],
                'note':'New four-source split; not directly comparable with prior G0 train/three-source scores.'})
    print(result)


if __name__=='__main__': main()
