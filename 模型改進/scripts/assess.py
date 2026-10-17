"""P1: fit temperature on val_select once, report on val_assess; no threshold recommendation."""
from pathlib import Path
import sys
import argparse
import json
import numpy as np
from scipy.optimize import minimize_scalar

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from common import EXP,write,load
from metrics import evaluate
from train import probabilities,report


def fit_temperature(z,y):
    def nll(log_t):
        p=probabilities(z/np.exp(log_t))
        return float(-np.log(p[np.arange(len(y)),y].clip(1e-12)).mean())
    return float(np.exp(minimize_scalar(nll,bounds=(-4,4),method='bounded').x))


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--run-dirs',type=Path,nargs='+',required=True); args=ap.parse_args()
    records=[]; all_probs=[]; reference=None; seeds=[]; configs=[]
    out=EXP/'reports/P1'; out.mkdir(parents=True,exist_ok=True)
    for folder in args.run_dirs:
        result=load(folder/'result.json')
        if result['smoke_test']: raise SystemExit('Smoke output cannot be used for P1')
        selection=np.load(folder/'val_select_logits.npz'); assessment=np.load(folder/'val_assess_logits.npz')
        if reference is not None and not np.array_equal(reference['record_ids'],assessment['record_ids']):
            raise SystemExit('Assessment identities/order mismatch')
        reference=assessment
        t=fit_temperature(selection['logits'],selection['targets'])
        p=probabilities(assessment['logits']/t)
        assert np.array_equal(p.argmax(1),assessment['logits'].argmax(1)), 'G-P1 argmax changed'
        by_source={}
        for source in sorted(set(selection['sources'])):
            fitmask=selection['sources']==source; mask=assessment['sources']==source
            if not mask.any(): continue
            ts=fit_temperature(selection['logits'][fitmask],selection['targets'][fitmask])
            by_source[str(source)]={'temperature':ts,'metrics':evaluate(probabilities(assessment['logits'][mask]/ts),
                 assessment['targets'][mask],np.unique(assessment['targets'][mask]).tolist())}
        targets=assessment['targets']; truth=np.isin(targets,[1,6,7]); malignant=p[:,[1,6,7]].sum(1)
        curve=[]
        for threshold in np.linspace(0,1,101):
            pred=malignant>=threshold
            curve.append({'threshold':float(threshold),'sensitivity':float(pred[truth].mean()),
                          'specificity':float((~pred[~truth]).mean())})
        records.append({'run_directory':folder.name,'temperature':t,'val_assess':report(np.log(p.clip(1e-12)),targets,assessment['sources']),
                        'by_source_temperature':by_source,'sensitivity_specificity_curve':curve,'G_P1_passed':True})
        all_probs.append(p); seeds.append(result['seed']); configs.append(result['config'])
    if len(all_probs)>1:
        assert sorted(seeds)==[17,42,2026], 'Ensemble requires three distinct registered seeds'
        normalized=[{k:v for k,v in c.items() if k!='seed'} for c in configs]
        assert all(c==normalized[0] for c in normalized), 'Ensemble configs must match'
    payload={'seeds':seeds,'pilot':len(seeds)!=3,'records':records,
             'temperature_fit_split':'val_select','report_split':'val_assess',
             'recommended_threshold':None,'note':'Threshold curve is descriptive; no clinically validated cost matrix.'}
    if len(all_probs)==3:
        p=np.mean(all_probs,axis=0)
        payload['ensemble']=report(np.log(p.clip(1e-12)),reference['targets'],reference['sources'])
    destination=out/('__'.join(p.name for p in args.run_dirs)+'.json')
    if destination.exists(): raise SystemExit('P1 result already exists; refusing overwrite')
    write(destination,payload); print(destination)


if __name__=='__main__': main()
