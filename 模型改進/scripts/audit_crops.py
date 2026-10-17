"""G-R0: estimate all non-test rows, report fallback per source, create review overlays."""
from pathlib import Path
import sys
import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from common import ROOT, EXP, read_rows, write, sha
from geometry import estimate
import numpy as np
import torch
from PIL import Image, ImageOps, ImageDraw
from tqdm import tqdm


def worker_init():
    torch.set_num_threads(1)


def estimate_row(r):
    with Image.open(ROOT/r['image_path']) as im:
        result=estimate(ImageOps.exif_transpose(im).convert('RGB'))
    return r['record_id'],r['source'],result


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--review-list', required=True,
        help='CSV containing image_path for the original fixed 10-image screening set')
    ap.add_argument('--workers',type=int,default=4)
    args=ap.parse_args()
    review=read_rows(args.review_list)
    if len(review)!=10: raise SystemExit('Exactly the original 10 review images are required')
    manifest=EXP/'data/cp005_manifest.csv'; rows=read_rows(manifest)
    out=EXP/'reports/R0_bbox_overlay'; out.mkdir(parents=True,exist_ok=True)
    cache_path=EXP/'data/bbox_D2.json'
    if cache_path.exists(): raise SystemExit('Existing bbox audit; refusing overwrite')
    torch.set_num_threads(2)
    records={}; summary=defaultdict(list)
    with ProcessPoolExecutor(max_workers=args.workers,initializer=worker_init) as pool:
        for record_id,source,result in tqdm(pool.map(estimate_row,rows,chunksize=32),total=len(rows),desc='病灶框估計',unit='張'):
            records[record_id]=result; summary[source].append(result)
    for i,r in enumerate(review):
        with Image.open(ROOT/r['image_path']) as im:
            im=ImageOps.exif_transpose(im).convert('RGB'); result=estimate(im)
            if result['bbox']:
                x,y,w,h=result['bbox']; ImageDraw.Draw(im).rectangle((x,y,x+w,y+h),outline='red',width=max(2,im.width//200))
            im.thumbnail((1000,1000)); im.save(out/f'{i+1:02d}.png')
    stats={s:{'count':len(v),'fallback_rate':float(np.mean([r['fallback'] for r in v])),
        'area_quartiles':np.quantile([r['area_fraction'] for r in v if r['area_fraction'] is not None],[.25,.5,.75]).tolist()}
        for s,v in summary.items()}
    write(cache_path,{'manifest_sha256':sha(manifest),'records':records})
    write(EXP/'reports/R0_bbox_stats.json',{'manifest_sha256':sha(manifest),'by_source':stats,
        'quantitative_passed':all(v['fallback_rate']<=.2 for v in stats.values()),
        'visual_review_approved':False,'passed':False,'review_list':str(args.review_list),
        'note':'Requires human review of the original ten images; not localization accuracy.'})
    print('Quantitative audit complete; visual review is required before R2.')


if __name__=='__main__': main()
