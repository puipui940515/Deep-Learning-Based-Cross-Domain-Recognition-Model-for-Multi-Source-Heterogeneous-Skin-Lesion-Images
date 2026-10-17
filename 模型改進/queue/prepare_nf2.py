"""Train-only, group-separated calibration/probe. Never changes historical G0."""
from pathlib import Path
import sys
import hashlib
import json
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from common import ROOT, EXP, read_rows
from safety import check_finite
from nf_adapter import NF, PROFILES, identity, artifact_dir, chain
sys.path.insert(0, str(NF/'scripts'))
from _common import PixelDataset, balanced_sample
from source_probe_input import ConvNeXtFeatures, logistic_cv_ba
import numpy as np
import torch
from torch.utils.data import DataLoader
from preprocessing import RealPixelInput
from PIL import Image,ImageOps


class UnpaddedDataset(PixelDataset):
    def __init__(self,rows,cfg):
        self.rows=rows
        self.transform=RealPixelInput(cfg)
    def __getitem__(self,i):
        r=self.rows[i]
        with Image.open(ROOT/r['image_path']) as im:
            x=self.transform.pixels(ImageOps.exif_transpose(im).convert('RGB'))
        return x,int(r['label']),r['source']


def save(path, obj):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    temp.replace(path)


def main():
    torch.set_num_threads(4)
    folder = artifact_dir(); folder.mkdir(parents=True, exist_ok=True)
    cfg=json.loads((EXP/'config.json').read_text(encoding='utf-8-sig'))
    manifest=ROOT/cfg['manifest']
    split_gate=json.loads((ROOT/cfg.get('split_report','模型改進/reports/cp005_split.json')).read_text(encoding='utf-8-sig'))
    manifest_hash=hashlib.sha256(manifest.read_bytes()).hexdigest()
    if not split_gate['passed'] or split_gate['manifest_sha256']!=manifest_hash:
        raise RuntimeError('CP005 split gate mismatch')
    cfg['run']=cfg['runs']['R0']
    if (folder/'gate.json').exists():
        print('Existing preparation:', folder, flush=True); return
    rows = [r for r in read_rows(manifest) if r['split']=='train']
    # Group assignment happens before sampling: no patient/lesion overlap between calibration and probe.
    def calibration_group(r): return int(hashlib.sha256(r['cp005_group'].encode()).hexdigest()[:8], 16)%10 < 3
    calibration_rows = balanced_sample([r for r in rows if calibration_group(r)], 200, 20261008)
    probe_rows = balanced_sample([r for r in rows if not calibration_group(r)], 600, 20261008)
    if {r['cp005_group'] for r in calibration_rows} & {r['cp005_group'] for r in probe_rows}:
        raise RuntimeError('Calibration/probe groups overlap')
    sources_expected = {r['source'] for r in rows}
    for sample in [calibration_rows, probe_rows]:
        if {r['source'] for r in sample} != sources_expected: raise RuntimeError('Missing source')
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    def loader(sample): return DataLoader(UnpaddedDataset(sample,cfg),batch_size=16,num_workers=0,collate_fn=lambda items:items)
    transform=RealPixelInput(cfg)
    calibration = chain('full').to(device).eval()
    with torch.no_grad():
        stats = calibration.calibrate(x.unsqueeze(0).to(device) for batch in loader(calibration_rows) for x,_,_ in batch)
    payload = {'split_used': 'train', 'calibration': {k:v for k,v in stats.items() if k!='images'},
               'record_ids': [r['record_id'] for r in calibration_rows], 'identity': identity()}
    check_finite(payload)
    save(folder/'calibration.json', payload)
    filters = {p:chain(p, payload).to(device).eval() for p in PROFILES}
    extractor = ConvNeXtFeatures().to(device).eval()
    features = {p:[] for p in ['off', *PROFILES]}
    with torch.no_grad():
        for batch, items in enumerate(loader(probe_rows)):
            for profile in features:
                output=[]
                for x,_,_ in items:
                    x=x.unsqueeze(0).to(device)
                    real=x if profile=='off' else filters[profile](x)
                    output.append(transform.finish_pixels(real.squeeze(0)))
                pixels=torch.stack(output)
                check_finite(pixels, profile)
                z = extractor(pixels).float().cpu(); check_finite(z)
                features[profile].append(z)
            if batch%20==0: print('NF2 probe batch', batch, flush=True)
    labels = np.array([int(r['label']) for r in probe_rows])
    sources = np.array([r['source'] for r in probe_rows])
    groups = np.array([r['cp005_group'] for r in probe_rows])
    scores = {}
    for profile, parts in features.items():
        x = torch.cat(parts).numpy()
        print('Grouped probe:', profile, flush=True)
        source = logistic_cv_ba(x, sources, 5, 17, groups)['balanced_accuracy']
        disease = {}
        for s in sorted(sources_expected):
            mask = sources==s
            disease[s] = logistic_cv_ba(x[mask], labels[mask], 5, 17, groups[mask])['balanced_accuracy']
        scores[profile] = {'source_ba': source, 'disease_ba_by_source': disease}
    decisions = {}
    for profile in PROFILES:
        drop = scores['off']['source_ba']-scores[profile]['source_ba']
        harm = max(scores['off']['disease_ba_by_source'][s]-scores[profile]['disease_ba_by_source'][s]
                   for s in sources_expected)
        decisions[profile] = {'passed': drop>=0.03 and harm<=0.02,
                              'source_ba_drop': drop, 'worst_disease_ba_drop': harm}
    gate = {'identity': identity(), 'status':'prepared','effect_threshold_is_diagnostic_only':True,
            'version':'2.0.0','placement':'real_pixels_before_padding',
            'split_used':'train', 'profiles':decisions, 'scores':scores,
            'calibration_sha256': hashlib.sha256((folder/'calibration.json').read_bytes()).hexdigest(),
            'probe_record_ids':[r['record_id'] for r in probe_rows],
            'thresholds':{'source_drop_min':0.03, 'max_per_source_disease_drop':0.02},
            'note':'Diagnostic gate, not clinical evidence; no val_select or val_assess used.'}
    save(folder/'gate.json', gate)
    print(json.dumps(decisions, indent=2), flush=True)


if __name__=='__main__': main()
