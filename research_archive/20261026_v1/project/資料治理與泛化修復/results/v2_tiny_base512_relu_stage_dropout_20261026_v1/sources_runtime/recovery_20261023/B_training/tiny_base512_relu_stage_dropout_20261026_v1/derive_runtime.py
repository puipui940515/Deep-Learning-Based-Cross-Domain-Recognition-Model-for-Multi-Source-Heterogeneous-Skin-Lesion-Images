"""Adapt only the existing serial batch contract/controller to six approved jobs."""
from pathlib import Path
import ast

OUT=Path(__file__).resolve().parent
PROJECT=OUT.parents[2]
SCRIPTS=PROJECT/'資料治理與泛化修復/scripts'

def replace(text,before,after):
    if text.count(before)!=1:raise RuntimeError('Unexpected source for exact adaptation: '+before[:80])
    return text.replace(before,after,1)

def main():
    text=(OUT/'before/v2_scale_followup_contract.py').read_text(encoding='utf-8')
    text=text.replace('v2_scale512_followup_20261026_v1','v2_tiny_base512_relu_stage_dropout_20261026_v1')
    text=text.replace('B_training/scale512_followup_20261026_v1','B_training/tiny_base512_relu_stage_dropout_20261026_v1')
    start=text.index('JOBS=');end=text.index('LIMITS=',start)
    text=text[:start]+'''DISPATCH_TOKEN='[DISPATCH_TOKEN_REDACTED]'
JOBS=tuple((f'{size}_seed{seed}',f'v2in_{size}512_relu_stage_dropout',seed,size) for size in ('tiny','base') for seed in (1,2,3))
CANDIDATES={f'v2in_{size}512_relu_stage_dropout':(size,[1,2,3]) for size in ('tiny','base')}
MICRO={'tiny':8,'base':2}
BASE_CONFIGS={'tiny':AREA/'configs/v2_resolution_20261021_v1/v2in_res512.json',
              'base':AREA/'configs/v2_scale512_followup_20261026_v1/v2in_scale512_base_confirm.json'}
from v2_relu_stage_dropout import VARIANT
'''+text[end:]
    text=text.replace('runs=3,epochs=90','runs=6,epochs=180')
    text=replace(text,"NOTE='User approved complete D scale512 followup draft 2026-10-26; three fresh runs only'","NOTE='Human authorized Tiny then Base three Seeds, ReLU plus stage Dropout .1; dispatch '+DISPATCH_TOKEN")
    start=text.index('def expected_config');end=text.index('def validate_candidate',start)
    text=text[:start]+'''def expected_config(candidate):
    size,seeds=CANDIDATES[candidate]
    expected=copy.deepcopy(read(BASE_CONFIGS[size]))
    expected['pipeline_id']=VERSION
    expected['formal_suite']['seeds']=seeds
    expected['experiment'].update(id=candidate,confirmation_note=NOTE)
    expected['architecture_modification']=copy.deepcopy(VARIANT)
    expected['optimization']=dict(version=VERSION,authorization_sha256=file_sha256(CONFIG/'AUTHORIZATION.md'))
    return expected

'''+text[end:]
    text=text.replace("or proof['limits']!=LIMITS", "or not proof['gpu_passed'] or proof['dispatch_token']!=DISPATCH_TOKEN\n            or proof['limits']!=LIMITS")
    text=text.replace('EVALUATION_CONTRACT.json','COMPARISON_CONTRACT.json')
    text=text.replace("allowed_seeds=CANDIDATES[config['experiment']['id']][1]", "architecture_modification=config['architecture_modification'],allowed_seeds=CANDIDATES[config['experiment']['id']][1]")
    start=text.index('def verify_initialization');end=text.index('def budget_summary',start)
    text=text[:start]+'''def reference_folder(size,seed):
    if size=='tiny':return TINY/f'regularized_seed{seed}'
    if seed==1:return OLD_RESULTS/'runs/v2in_scale512_base/regularized_seed1'
    return AREA/'results/v2_scale512_followup_20261026_v1/runs/v2in_scale512_base_confirm'/f'regularized_seed{seed}'

def model_audit(model,config):
    from v2_relu_stage_dropout import audit
    return audit(model,CANDIDATES[config['experiment']['id']][0])

def verify_initialization(inputs):
    contract=inputs['contract'];candidate=contract['experiment_id'];seed=inputs['seed']
    if candidate not in CANDIDATES or seed not in (1,2,3) or contract['seed']!=seed:raise RuntimeError('Unapproved model/seed')
    size=CANDIDATES[candidate][0];old=read(reference_folder(size,seed)/'run_inputs.json')
    for key in ('selected_train_record_ids','selected_validation_record_ids'):
        if inputs[key]!=old[key]:raise RuntimeError('Original same-Seed Train/Validation IDs differ')
    if len(inputs['selected_train_record_ids'])!=18919 or sum(map(len,inputs['selected_validation_record_ids'].values()))!=3611:raise RuntimeError('Incomplete data')
    cfg=read(CONFIG/(candidate+'.json'))
    if inputs['initial_optimizer_state_entries']!=0 or inputs['effective_training_config']!=cfg['training']:raise RuntimeError('Fresh optimizer/recipe mismatch')
    if contract['pretrained_sha256']!=cfg['experiment']['weights']['sha256'] or contract['data']!=old['contract']['data']:raise RuntimeError('Pinned initialization/data differs')
    if contract['effective_transforms']!=old['contract']['effective_transforms'] or inputs['test_used'] is not False:raise RuntimeError('Transform/Test boundary mismatch')
    observed=inputs['architecture_audit'];expected=read(RESULTS/'preflight'/f'{size}.json')['architecture_audit']
    if observed!=expected:raise RuntimeError('Actual architecture differs from validated candidate')
    head=inputs['initial_classifier_sha256']
    if len(head)!=64 or any(ch not in '0123456789abcdef' for ch in head):raise RuntimeError('Invalid head SHA')
    if seed==1 and head!=read(RESULTS/'preflight'/f'{size}.json')['initial_classifier_sha256']:raise RuntimeError('Fresh Seed1 head differs from temporary precheck')
    # Seeds2/3 save their own seeded heads; no Seed1 equality requirement.

'''+text[end:]
    text=text.replace(">=90",">=180").replace('90 complete epoch cap','180 complete epoch cap')
    text=text.replace('Followup differs beyond approved candidate/seed metadata and Large 2x32','Candidate differs beyond approved ReLU plus stage dropout and version metadata')
    target=SCRIPTS/'v2_relu_dropout_contract.py'
    if target.exists():raise RuntimeError('Existing derived contract retained')
    ast.parse(text);target.write_text(text,encoding='utf-8')
    text=(OUT/'before/run_v2_scale_followup.py').read_text(encoding='utf-8').replace('import v2_scale_followup_contract as c','import v2_relu_dropout_contract as c')
    text=text.replace('512後續研究：即時監控','Tiny／Base512 ReLU＋Stage Dropout：即時監控')
    text=text.replace('單GPU固定Base Seed2 → Base Seed3 → Large Seed1 micro2。','單GPU固定Tiny Seed1→2→3，再Base Seed1→2→3。')
    text=text.replace('全部micro2×累積32／effective64','Tiny8×8／Base2×32／effective64')
    text=text.replace('最多3新run／90完整Epoch','最多6新run／180完整Epoch；只改Block ReLU＋四Stage後元素Dropout=.1')
    text=text.replace("|{seed}|2×32|", "|{seed}|{row['micro_batch']}×{row['accumulation']}|")
    text=text.replace('Base三Seed前瞻ALL與Large單Seed診斷契約見configs/v2_scale512_followup_20261026_v1/EVALUATION_CONTRACT.json','各模型新三Seed對原架構同Seed；比較契約見configs/v2_tiny_base512_relu_stage_dropout_20261026_v1/COMPARISON_CONTRACT.json')
    start=text.index('def arithmetic_handoff');end=text.index('def finalize',start)
    text=text[:start]+'''def arithmetic_handoff(state):
    for size in ('tiny','base'):
        path=ROOT/(size.upper()+'_COMPARISON.json')
        if path.exists() or not all(state['runs'][f'{size}_seed{seed}']['status']=='completed' for seed in (1,2,3)):continue
        new=[state['runs'][f'{size}_seed{seed}']['metrics'] for seed in (1,2,3)]
        old=[state['references'][f'original_{size}_seed{seed}']['metrics'] for seed in (1,2,3)]
        values={}
        for key in new[0]['values']:
            a=[m['values'][key] for m in new];b=[m['values'][key] for m in old];delta=[x-y for x,y in zip(a,b)]
            values[key]=dict(new_mean=statistics.mean(a),new_sample_sd=statistics.stdev(a),original_mean=statistics.mean(b),
                original_sample_sd=statistics.stdev(b),paired_deltas=delta,mean_delta=statistics.mean(delta),sample_sd_delta=statistics.stdev(delta))
        atomic_json(path,dict(status='saved_result_arithmetic_pending_D',model=size,seeds=[1,2,3],ddof=1,metrics=values,new_per_seed=new,original_per_seed=old,
            PAD_DF_VASC='N/A; unsupported',combination_not_separate_causal_effects=True,automatic_adoption=False,test_used=False))

'''+text[end:]
    text=text.replace("evaluation_contract=str(c.CONFIG/'EVALUATION_CONTRACT.json'),base_summary_exists=(ROOT/'BASE_CONFIRMATION_SUMMARY.json').exists(),\n        large_diagnostic_exists=(ROOT/'LARGE_MICRO2_DIAGNOSTIC.json').exists()", "comparison_contract=str(c.CONFIG/'COMPARISON_CONTRACT.json'),tiny_summary_exists=(ROOT/'TINY_COMPARISON.json').exists(),\n        base_summary_exists=(ROOT/'BASE_COMPARISON.json').exists()")
    start=text.index("    (ROOT/'B_HANDOFF.md').write_text(");end=text.index('\n\ndef run_job',start)
    text=text[:start]+'''    (ROOT/'B_HANDOFF.md').write_text('本批狀態：'+state['status']+'。Tiny512三Seed後Base512三Seed，僅ReLU＋四Stage後Dropout=.1組合變更。RunID／完整與最佳輪／停止原因／指標見FINAL_RESULTS；各模型對原架構同Seed的mean/sampleSD與TP/N/Recall見TINY_COMPARISON及BASE_COMPARISON（若齊全）。完整命令／配置／架構audit／run_inputs／metrics／best／雙代Checkpoint／失敗與計帳均保留。交總控供D判讀，不自動採納或追加研究，不作獨立因果／Test宣稱。',encoding='utf-8')
'''+text[end:]
    text=text.replace(">=3:raise RuntimeError('Three fresh attempts exhausted')",">=6:raise RuntimeError('Six fresh attempts exhausted')")
    start=text.index('        references={');end=text.index('        state=dict(',start)
    text=text[:start]+'''        references={f'original_{size}_seed{seed}':reference(c.reference_folder(size,seed),c.MICRO[size],64//c.MICRO[size]) for size in ('tiny','base') for seed in (1,2,3)}
'''+text[end:]
    text=text.replace('size=size,micro_batch=2,accumulation=32','size=size,micro_batch=c.MICRO[size],accumulation=64//c.MICRO[size]')
    target=SCRIPTS/'run_v2_relu_dropout.py'
    if target.exists():raise RuntimeError('Existing derived controller retained')
    ast.parse(text);target.write_text(text,encoding='utf-8')

if __name__=='__main__':main()
