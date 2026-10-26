from pathlib import Path
import json,csv,hashlib,statistics,math

ROOT=Path('D:/SkinDetect_base')
OUT=Path(__file__).resolve().parent
SRCS=['HAM10000','BCN20000','PAD-UFES-20']
newbase=ROOT/'資料治理與泛化修復/results/v2_512_alpha025_20261024_v1/executions/retry1_20261024_v1/runs/v2in_res512_alpha025'
oldbase=ROOT/'資料治理與泛化修復/results/v2_resolution_20261021_v1/runs/v2in_res512'
allrows=[];runs=[];sources=[]
def small(r):
    return {'epoch':r['epoch'],'robust':r['robust_selection_score'],'train_augmented_mixup_loss':r['train_loss'],
            'monitor_loss':r['train_monitor']['loss'],'monitor_ba':r['train_monitor']['balanced_accuracy'],
            'source_ba':{s:r['validation_by_source'][s]['balanced_accuracy'] for s in SRCS},
            'source_loss':{s:r['validation_by_source'][s]['loss'] for s in SRCS},'lr':r['learning_rate']}
for name,base in [('alpha050',oldbase),('alpha025',newbase)]:
    for seed in [1,2,3]:
        p=base/f'regularized_seed{seed}'/'result.json'
        b=p.read_bytes();j=json.loads(b);h=j['history'];best=j['best'];be=best['epoch']
        # No stopping-rule replay: cite saved best epoch and look up its record.
        br=next(x for x in h if x['epoch']==be);last=h[-1]
        source={'path':str(p),'sha256':hashlib.sha256(b).hexdigest(),'run_id':j['run_id'],'status':j['status'],'epochs':len(h)}
        sources.append(source)
        d={'group':name,'seed':seed,'run_id':j['run_id'],'best_epoch':be,'stop_epoch':last['epoch'],
            'first':small(h[0]),'best':small(br),'last':small(last),'best_to_stop':{},'within_observed_history':{}}
        d['best_to_stop']={'robust_delta_pp':100*(last['robust_selection_score']-br['robust_selection_score']),
            'monitor_ba_delta_pp':100*(last['train_monitor']['balanced_accuracy']-br['train_monitor']['balanced_accuracy']),
            'monitor_loss_delta':last['train_monitor']['loss']-br['train_monitor']['loss'],
            'augmented_mixup_loss_delta':last['train_loss']-br['train_loss'],
            'sources':{s:{'ba_delta_pp':100*(last['validation_by_source'][s]['balanced_accuracy']-br['validation_by_source'][s]['balanced_accuracy']),
                          'loss_delta':last['validation_by_source'][s]['loss']-br['validation_by_source'][s]['loss']} for s in SRCS}}
        d['within_observed_history']={'worst_source_counts':{s:sum(min(SRCS,key=lambda z:r['validation_by_source'][z]['balanced_accuracy'])==s for r in h) for s in SRCS},
            'monitor_at_best_minus_source_pp':{s:100*(br['train_monitor']['balanced_accuracy']-br['validation_by_source'][s]['balanced_accuracy']) for s in SRCS},
            'loss_min_epoch':{s:min(h,key=lambda r:r['validation_by_source'][s]['loss'])['epoch'] for s in SRCS},
            'source_max_ba_epoch':{s:max(h,key=lambda r:r['validation_by_source'][s]['balanced_accuracy'])['epoch'] for s in SRCS},
            'source_max_ba_value':{s:max(r['validation_by_source'][s]['balanced_accuracy'] for r in h) for s in SRCS}}
        runs.append(d)
        for r in h:
            row={'group':name,'seed':seed,'run_id':j['run_id'],'epoch':r['epoch'],'selected_best':r['epoch']==be,
                 'train_augmented_mixup_loss':r['train_loss'],'monitor_ba':r['train_monitor']['balanced_accuracy'],
                 'monitor_loss':r['train_monitor']['loss'],'robust':r['robust_selection_score'],'lr':r['learning_rate'],
                 'bad_epochs_saved':r.get('bad_epochs')}
            for s in SRCS:
                row[s+'_ba']=r['validation_by_source'][s]['balanced_accuracy'];row[s+'_loss']=r['validation_by_source'][s]['loss']
            allrows.append(row)
with (OUT/'curves_84_epochs.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=allrows[0].keys());w.writeheader();w.writerows(allrows)
payload={'date':'2026-10-25','scope':'Saved-history-only CPU derivation, no predictions/metrics/stopping replay','sources':sources,'runs':runs,
         'n_saved_epochs':len(allrows),'limits':['Train monitor is mixed source-class-stratified subset of 1500, not per-source training evaluation.',
         'Augmented MixUp+LS training loss is not commensurate with eval monitor/Validation LS loss.',
         'Monitor and source Validation use same deterministic eval transforms but different membership/composition.',
         'Observed source maximum epochs are diagnostic only; never reselect deployed/best checkpoint by source.',
         'Cannot infer an unobserved future peak or prove domain shift from a mixed monitor gap.']}
(OUT/'CURVE_DIAGNOSIS.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
for r in runs:
    print(r['group'],r['seed'],'best/last',r['best_epoch'],r['stop_epoch'],
          'monitorBA',round(r['best']['monitor_ba']*100,3),'->',round(r['last']['monitor_ba']*100,3),
          'robust',round(r['best']['robust']*100,3),'->',round(r['last']['robust']*100,3),
          'monitor loss',round(r['best']['monitor_loss'],4),'->',round(r['last']['monitor_loss'],4),
          'source deltas',r['best_to_stop']['sources'])

# Standard scientific plot from saved numbers only. No model frameworks imported.
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axs=plt.subplots(3,3,figsize=(13.5,10),sharex='col')
    colors={'alpha050':'#226699','alpha025':'#d1781b'}
    for seed in [1,2,3]:
        for group in ['alpha050','alpha025']:
            rows=[r for r in allrows if r['group']==group and r['seed']==seed]
            x=[r['epoch'] for r in rows];c=colors[group]
            axs[0,seed-1].plot(x,[100*r['robust'] for r in rows],label=group,color=c)
            axs[1,seed-1].plot(x,[100*r['monitor_ba'] for r in rows],color=c,ls='-',label=group+' monitor')
            axs[1,seed-1].plot(x,[100*r['BCN20000_ba'] for r in rows],color=c,ls='--',label=group+' BCN Val')
            axs[2,seed-1].plot(x,[r['monitor_loss'] for r in rows],color=c,label=group+' monitor')
            axs[2,seed-1].plot(x,[r['BCN20000_loss'] for r in rows],color=c,ls='--',label=group+' BCN Val')
            br=next(r for r in rows if r['selected_best'])
            axs[0,seed-1].scatter([br['epoch']],[100*br['robust']],color=c,s=40)
        axs[0,seed-1].set_title('Seed '+str(seed));axs[2,seed-1].set_xlabel('Epoch')
    axs[0,0].set_ylabel('Validation Robust (%)');axs[1,0].set_ylabel('BA (%)');axs[2,0].set_ylabel('Eval LS loss')
    for ax in axs.flat:ax.grid(alpha=.25)
    axs[0,0].legend();axs[1,0].legend(fontsize=7);axs[2,0].legend(fontsize=7)
    fig.suptitle('Existing 512 alpha=.50 vs new alpha=.25 | saved histories only\nMixed Train monitor and BCN Validation have different membership/composition; no Test',fontsize=12)
    fig.tight_layout(rect=[0,0,1,.95]);fig.savefig(OUT/'curves_512_alpha025.png',dpi=160);fig.savefig(OUT/'curves_512_alpha025.svg');plt.close(fig)
except ImportError as e:
    (OUT/'plot_unavailable.txt').write_text(str(e),encoding='utf-8')
