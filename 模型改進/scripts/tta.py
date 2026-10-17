"""Eight-view inference using exactly the checkpoint's input preprocessing."""
from pathlib import Path
import sys
import argparse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from common import ROOT,EXP,load,read_rows,write,sha
from train import Images,infer,report,build_model
import torch
import numpy as np
from torch.utils.data import DataLoader


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--run-dir',type=Path,required=True); a=ap.parse_args()
    result=load(a.run_dir/'result.json'); cfg=result['config']
    assert not result['smoke_test']
    manifest=ROOT/cfg['manifest']; assert sha(manifest)==cfg['manifest_sha256']
    out=a.run_dir/'tta'
    out.mkdir(exist_ok=False)
    cache=load(EXP/'data/bbox_D2.json')['records'] if cfg['run']['crop']=='D2' else None
    device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model=build_model('convnext_tiny',False,8).to(device)
    state=torch.load(a.run_dir/'best.pt',map_location=device,weights_only=False); model.load_state_dict(state['model'])
    metrics={}
    for split in ['val_select','val_assess']:
        rows=[r for r in read_rows(manifest) if r['split']==split and
              (split!='val_select' or r['source']!=cfg['run']['held_out'])]
        dl=DataLoader(Images(rows,cfg,cache=cache),batch_size=cfg['run']['batch_size'])
        z,y,s=infer(model,dl,device,tta=True); metrics[split]=report(z,y,s)
        np.savez_compressed(out/f'{split}_logits.npz',logits=z,targets=y,sources=np.array(s),record_ids=np.array([r['record_id'] for r in rows]))
    write(out/'result.json',{'metrics':metrics,'views':8,'crop':cfg['run']['crop'],
          'seed':result['seed'],'pilot':True,'sealed_test_used':False})


if __name__=='__main__': main()
