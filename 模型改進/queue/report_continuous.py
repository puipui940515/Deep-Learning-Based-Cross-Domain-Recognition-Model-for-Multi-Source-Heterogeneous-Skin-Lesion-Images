"""Current-session descriptive plots; never selects a winning seed."""
from pathlib import Path
import json
import csv
import statistics
import sys
import argparse

EXP=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(EXP/'src'))
import common  # runtime bootstrap for plotting dependencies


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--folder',type=Path,default=EXP/'results/continuous/required_nf2_v2')
    folder=ap.parse_args().folder
    journal=folder/'completed.jsonl'
    if not journal.exists(): return
    paths=list(dict.fromkeys(json.loads(line)['folder'] for line in journal.read_text(encoding='utf-8').splitlines()))
    results=[json.loads((Path(p)/'result.json').read_text(encoding='utf-8')) for p in paths]
    rows=[]
    for r in results:
        for source,m in r['metrics']['val_select']['by_source'].items():
            rows.append({'run':r['run'],'profile':r['config'].get('noisefilter_v2',{}).get('profile','off'),
                         'seed':r['seed'],'source':source,'balanced_accuracy':m['balanced_accuracy'],
                         'macro_f1':m['macro_f1'],'ece':m['ece'],'best_epoch':r['best_epoch']})
    with (folder/'選模分割比較.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif']=['Microsoft JhengHei','SimHei','DejaVu Sans']
    labels={'off':'無濾波','full':'完整濾波','no-tone':'移除色調濾波'}
    fig,ax=plt.subplots(figsize=(10,5))
    for r in results:
        if r['run']!='R0': continue
        profile=r['config'].get('noisefilter_v2',{}).get('profile','off')
        ax.plot([h['epoch'] for h in r['history']],
                [100*h['val_select']['worst_source_balanced_accuracy'] for h in r['history']],
                label=f'{labels[profile]}／種子 {r["seed"]}')
    ax.set(title='濾波對照：選模分割（非獨立評估結果）',xlabel='訓練輪次',ylabel='最差來源平衡準確率（%）')
    ax.grid(alpha=.2); ax.legend(fontsize=8); fig.tight_layout()
    fig.savefig(folder/'濾波對照曲線.png',dpi=150); plt.close(fig)
    groups={}
    for row in rows:
        key=f'{row["run"]}/{row["profile"]}/{row["source"]}'
        groups.setdefault(key,[]).append(row)
    summary={k:{'seeds':[r['seed'] for r in items], 'n':len(items),
                'ba_mean':statistics.mean(r['balanced_accuracy'] for r in items),
                'ba_sample_std':statistics.stdev(r['balanced_accuracy'] for r in items) if len(items)>1 else None}
             for k,items in groups.items()}
    paired={}
    baseline={(r['source'],r['seed']):r for r in rows if r['run']=='R0' and r['profile']=='off'}
    for profile in ['full','no-tone']:
        for source in sorted({r['source'] for r in rows}):
            matches=[r for r in rows if r['run']=='R0' and r['profile']==profile and r['source']==source
                     and (source,r['seed']) in baseline]
            if not matches: continue
            delta=[r['balanced_accuracy']-baseline[source,r['seed']]['balanced_accuracy'] for r in matches]
            paired[f'{profile}/{source}']={'seeds':[r['seed'] for r in matches],
                'ba_delta_mean':statistics.mean(delta),
                'ba_delta_sample_std':statistics.stdev(delta) if len(delta)>1 else None}
    (folder/'選模分割統計.json').write_text(json.dumps({'split':'val_select','not_independent_assessment':True,
                 'summary':summary,'paired_filter_minus_baseline':paired},ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__': main()
