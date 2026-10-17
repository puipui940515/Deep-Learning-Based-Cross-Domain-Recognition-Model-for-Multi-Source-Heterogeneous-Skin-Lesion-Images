"""Read-only data audit and train-only grouped metadata probes. No CNN training."""
from pathlib import Path
import sys
import json
from collections import defaultdict,Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from common import ROOT,EXP,read_rows,sha,write
from preprocessing import Letterbox
import numpy as np
from PIL import Image
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import balanced_accuracy_score,accuracy_score,confusion_matrix


def probe(x,y,groups):
    pred=np.empty_like(y)
    fold_scores=[]
    for tr,te in StratifiedGroupKFold(5,shuffle=True,random_state=17).split(x,y,groups):
        assert not set(groups[tr]) & set(groups[te])
        model=DecisionTreeClassifier(max_depth=5,min_samples_leaf=20,class_weight='balanced',random_state=17)
        model.fit(x[tr],y[tr]); pred[te]=model.predict(x[te])
        fold_scores.append(float(balanced_accuracy_score(y[te],pred[te])))
    classes=np.unique(y)
    return {'ba':float(balanced_accuracy_score(y,pred)), 'accuracy':float(accuracy_score(y,pred)),
            'fold_ba':fold_scores,'classes':classes.tolist(),'confusion_matrix':confusion_matrix(y,pred,labels=classes).tolist()}


def main():
    rows=read_rows(EXP/'data/cp005_manifest.csv')
    fp={r['image_path']:r for r in read_rows(ROOT/'資料治理與泛化修復/data/image_fingerprints_v2.csv')}
    def crossings(key):
        items=defaultdict(list)
        for r in rows:
            value=key(r)
            if value: items[value].append(r)
        return [{'key':str(k),'n':len(v),'splits':sorted({r['split'] for r in v}),
                 'examples':[r['record_id'] for r in v[:5]]} for k,v in items.items() if len({r['split'] for r in v})>1]
    checks={
        'cp005_group':crossings(lambda r:r['cp005_group']),
        'same_image_path':crossings(lambda r:r['image_path']),
        'same_cached_sha256':crossings(lambda r:fp.get(r['image_path'],{}).get('sha256','').lower()),
        'same_image_id_across_sources':crossings(lambda r:r['image_id']),
    }
    for field in ['patient_id','lesion_id']:
        checks[field]=crossings(lambda r:(r['source'],r[field]) if r[field].strip().lower() not in ['', 'none','unknown','nan'] else None)
    counts={}; missing={}
    for s in sorted({r['source'] for r in rows}):
        train=[r for r in rows if r['split']=='train' and r['source']==s]
        counts[s]=dict(Counter(r['diagnosis_canonical_code'] for r in train))
        missing[s]={field:sum(r[field].strip().lower() in ['', 'none','unknown','nan'] for r in train) for field in ['patient_id','lesion_id']}
    rng=np.random.default_rng(20261008); sample=[]
    for s in sorted(counts):
        pool=[r for r in rows if r['source']==s and r['split']=='train']
        sample.extend(pool[int(i)] for i in rng.permutation(len(pool))[:1200])
    geometry=[]; current_dims=[]; changes=[]; transform=Letterbox(224)
    for r in sample:
        path=ROOT/r['image_path']
        with Image.open(path) as im:
            w,h=im.size
            if im.getexif().get(274,1) in [5,6,7,8]: w,h=h,w
        current_dims.append((w,h))
        info=transform.geometry(w,h); geometry.append(info['resized_size'])
        cached=fp.get(r['image_path'],{})
        if not cached or int(cached['file_size'])!=path.stat().st_size:
            changes.append(r['record_id'])
    x=np.array(geometry); src=np.array([r['source'] for r in sample]); y=np.array([int(r['label']) for r in sample])
    groups=np.array([r['cp005_group'] for r in sample]); sources=sorted(counts)
    source_feature=np.array([[sources.index(r['source'])] for r in sample])
    profiles={}
    for s in sources:
        arr=x[src==s]
        profiles[s]={'n':len(arr),'padding_fraction_mean':float(np.mean(1-arr[:,0]*arr[:,1]/224**2)),
                     'square_fraction':float(np.mean(arr[:,0]==arr[:,1])),
                     'top_resized_sizes':Counter(f'{w}x{h}' for w,h in arr).most_common(5)}
    payload={'manifest_sha256':sha(EXP/'data/cp005_manifest.csv'),
        'scope':'Train-only diagnostic probes. No CNN optimization, no val_select/val_assess inference.',
        'cross_split_counts':{k:len(v) for k,v in checks.items()},'cross_split_examples':{k:v[:20] for k,v in checks.items()},
        'train_class_counts_by_source':counts,'missing_patient_lesion_ids_train':missing,
        'sample_count':len(sample),'sample_record_ids':[r['record_id'] for r in sample],
        'sample_current_size_vs_cached_file_size_mismatch':changes,
        'padding_profiles':profiles,'geometry_to_source':probe(x,src,groups),
        'geometry_to_disease':probe(x,y,groups),'source_identity_to_disease':probe(source_feature,y,groups),
        'limitations':['Cached SHA256 was not recomputed; same-size edits not excluded.',
                      'No new perceptual duplicate search or manual lesion/background review.',
                      'Metadata decision tree proves available shortcut signal, not that CNN uses it.',
                      'Patient identifiers are source-scoped; unknown cross-source identities remain unresolved.']}
    write(EXP/'reports/shortcut_audit_2026-10-08.json',payload)
    print(json.dumps({k:v for k,v in payload.items() if k in ['cross_split_counts','padding_profiles','geometry_to_source','geometry_to_disease','source_identity_to_disease','missing_patient_lesion_ids_train']},ensure_ascii=False,indent=2))


if __name__=='__main__': main()
