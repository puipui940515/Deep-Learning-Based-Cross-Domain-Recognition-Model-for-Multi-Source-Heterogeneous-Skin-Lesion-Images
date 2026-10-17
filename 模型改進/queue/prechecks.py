"""Scheduled data integrity/near-duplicate review and actual model shortcut diagnostics."""
from pathlib import Path
import sys
import json
import argparse
import hashlib
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from common import ROOT,EXP,read_rows,load,write,sha
from safety import check_finite


def near_pairs(rows,fps,tree_type):
    tree=tree_type(); pairs=[]
    for i,r in enumerate(rows):
        item=fps[r['image_path']]; ph=int(item['phash'],16)
        for j in tree.query(ph,4):
            other=rows[j]
            if r['split']==other['split']: continue
            dh=(int(item['dhash'],16)^int(fps[other['image_path']]['dhash'],16)).bit_count()
            if dh<=4:
                pairs.append({'a':other['record_id'],'b':r['record_id'],
                              'splits':[other['split'],r['split']],'dhash_distance':dh,
                              'phash_distance':(ph^int(fps[other['image_path']]['phash'],16)).bit_count()})
        tree.add(ph,i)
    return pairs


def data_audit(folder):
    sys.path.insert(0,str(ROOT/'資料治理與泛化修復/scripts'))
    from pipeline_lib import BKTree,fingerprint_image
    cfg=load(EXP/'config.json'); manifest=ROOT/cfg['manifest']
    rows=read_rows(manifest)
    old={r['image_path']:r for r in read_rows(ROOT/'資料治理與泛化修復/data/image_fingerprints_v2.csv')}
    fps={}; errors=[]; groups={}; duplicates=[]; seen={}
    def check(r):
        p=ROOT/r['image_path']; h=hashlib.sha256()
        try:
            with p.open('rb') as f:
                for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
            previous=old.get(r['image_path'])
            item=previous if previous and previous['sha256'].lower()==h.hexdigest() else fingerprint_image(p)
            return r,item,None
        except Exception as e: return r,None,str(e)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i,(r,item,error) in enumerate(pool.map(check,rows),1):
            if error: errors.append({'record_id':r['record_id'],'error':error}); continue
            fps[r['image_path']]=item
            key=item['sha256'].lower()
            if key in seen: duplicates.append([seen[key],r['record_id']])
            seen[key]=r['record_id']
            previous=groups.setdefault(r['cp005_group'],r['split'])
            if previous!=r['split']: errors.append({'group':r['cp005_group'],'error':'cross-split group'})
            if i%2000==0: print('Data hashes checked',i,'/',len(rows),flush=True)
    pairs=near_pairs(rows,fps,BKTree) if not errors else []
    # Explicit user-reviewed nonduplicates can be accepted; no automatic deletion or silent approval.
    review_path=folder/'near_duplicate_review.json'
    reviewed=set()
    manifest_hash=sha(manifest)
    if review_path.exists():
        review=load(review_path)
        if review['manifest_sha256']!=manifest_hash: raise RuntimeError('Stale duplicate review')
        reviewed={tuple(sorted(pair)) for pair in review.get('confirmed_nonduplicate_pairs',[])}
    pending=[p for p in pairs if tuple(sorted([p['a'],p['b']])) not in reviewed]
    result={'passed':not(errors or duplicates or pending),'manifest_sha256':manifest_hash,
            'fresh_sha256_checked':len(fps),'errors':errors,'exact_duplicates':duplicates,
            'near_duplicate_candidates':pairs,'pending_review':pending,
            'note':'Near hashes are candidates, not confirmed duplicate diagnoses. No files removed.'}
    write(folder/'data_audit.json',result)
    if not result['passed']:
        raise RuntimeError(f'Data safety review required: errors={len(errors)}, exact={len(duplicates)}, near candidates={len(pending)}; see data_audit.json')


def shortcut_test(folder,paths):
    import numpy as np
    import torch
    from PIL import Image,ImageOps
    sys.path.insert(0,str(EXP/'scripts'))
    from train import Images,build_model,report
    from preprocessing import Letterbox
    from _common import balanced_sample
    active_cfg=load(EXP/'config.json')
    rows=balanced_sample([r for r in read_rows(ROOT/active_cfg['manifest']) if r['split']=='val_select'],40,20261009)
    device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    result={}
    for path in paths:
        r=load(path/'result.json'); cfg=r['config']; model=build_model('convnext_tiny',False,8).to(device)
        state=torch.load(path/'best.pt',map_location=device,weights_only=False); check_finite(state)
        model.load_state_dict(state['model']); model.eval(); dataset=Images(rows,cfg)
        logits={k:[] for k in ['original','dark_border','corner_position','content_removed','center_occluded']}
        for i,row in enumerate(rows):
            x,_,_=dataset[i]; x=x.to(device); size=x.shape[-1]
            mean=torch.tensor(cfg['normalization']['mean'],device=device)[:,None,None]
            std=torch.tensor(cfg['normalization']['std'],device=device)[:,None,None]
            with Image.open(ROOT/row['image_path']) as im: wh=ImageOps.exif_transpose(im).size
            if cfg['preprocessing']['mode']=='letterbox': box=Letterbox(size).geometry(*wh)['content_box']
            else: box=(0,0,size,size)
            left,top,right,bottom=box
            dark=(-mean/std).expand_as(x).clone(); dark[:,top:bottom,left:right]=x[:,top:bottom,left:right]
            shifted=torch.zeros_like(x); shifted[:,:bottom-top,:right-left]=x[:,top:bottom,left:right]
            removed=x.clone(); removed[:,top:bottom,left:right]=0
            occluded=x.clone(); occluded[:,size//4:3*size//4,size//4:3*size//4]=0
            with torch.inference_mode():
                z=model(torch.stack([x,dark,shifted,removed,occluded])).float(); check_finite(z)
            for key,value in zip(logits,z.cpu().numpy()): logits[key].append(value)
        y=np.array([int(r['label']) for r in rows]); sources=[r['source'] for r in rows]
        raw=np.array(logits['original']); baseline=torch.tensor(raw).softmax(1).numpy()
        values={}
        for key,items in logits.items():
            z=np.array(items); p=torch.tensor(z).softmax(1).numpy()
            values[key]={'metrics':report(z,y,sources),'top1_change_fraction':float((z.argmax(1)!=raw.argmax(1)).mean()),
                         'mean_probability_l1_change':float(abs(p-baseline).sum(1).mean())}
        result[path.name]={'preprocessing':cfg['preprocessing'],'conditions':values}
    write(folder/'shortcut_tests.json',{'split':'val_select','pilot':True,'models':result,
        'record_ids':[r['record_id'] for r in rows],
        'caveat':'Center occlusion is NOT a ground-truth lesion mask. Content removal tests padding only, not anatomical background. Diagnostic scores never skip NF2.'})


if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--stage',choices=['data','shortcut'],required=True)
    ap.add_argument('--folder',type=Path,required=True); ap.add_argument('--run-dirs',type=Path,nargs='*',default=[])
    a=ap.parse_args(); a.folder.mkdir(parents=True,exist_ok=True)
    if a.stage=='data': data_audit(a.folder)
    else: shortcut_test(a.folder,a.run_dirs)
