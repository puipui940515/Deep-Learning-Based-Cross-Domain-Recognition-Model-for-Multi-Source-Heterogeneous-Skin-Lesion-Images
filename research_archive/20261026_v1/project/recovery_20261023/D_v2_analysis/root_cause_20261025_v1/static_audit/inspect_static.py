"""Read saved contracts and source text only; no model imports/payload/manifest rows."""
from pathlib import Path
import json, hashlib, re

ROOT=Path('D:/SkinDetect_base')
OUT=Path(__file__).resolve().parent
NEW=ROOT/'資料治理與泛化修復/results/v2_512_alpha025_20261024_v1/executions/retry1_20261024_v1/runs/v2in_res512_alpha025'
OLD=ROOT/'資料治理與泛化修復/results/v2_resolution_20261021_v1/runs/v2in_res512'
AREA=ROOT/'資料治理與泛化修復'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
close=read(ROOT/'recovery_20261023/B_training/alpha025_retry1_20261024_v1/CLOSEOUT_CHECKS_20261025_v1.json')
exposure=read(AREA/'configs/v2_512_alpha025_20261024_v1/SAMPLING_EXPOSURE.json')
runs=[]
for seed in (1,2,3):
    new=read(NEW/f'regularized_seed{seed}/run_inputs.json')
    groups=new['optimizer_groups']
    names=[n for g in groups for n in g['parameter_names']]
    runs.append(dict(seed=seed,run_id=new['run_id'],
        identity_checks_reused=close['existing_record_identity_checks'][str(seed)],
        initial_classifier_sha256=new['initial_classifier_sha256'],
        initial_optimizer_state_entries=new['initial_optimizer_state_entries'],
        optimizer_group_count=len(groups),optimizer_named_tensor_count=len(names),
        duplicate_optimizer_names=sorted({n for n in names if names.count(n)>1}),
        optimizer_initial_lrs=sorted({g['initial_lr'] for g in groups}),
        optimizer_weight_decays=sorted({g['weight_decay'] for g in groups}),
        stages_present={p:any(n.startswith(p) for n in names) for p in ('stem.','stages.0.','stages.1.','stages.2.','stages.3.','head.')},
        classifier_group_entries=[g for g in groups if any(n.startswith('head.fc') for n in g['parameter_names'])],
        class_names=new['contract']['class_names'],
        pretrain_identity=new['contract']['weight_identity'],
        training=new['effective_training_config'],
        transforms=new['contract']['effective_transforms'],
        versions=new['contract']['versions'],
        recorded_source_hashes=new['contract']['source_hashes']))
source_checks=[]
for rel,expected in runs[0]['recorded_source_hashes'].items():
    p=ROOT/rel
    actual=hashlib.sha256(p.read_bytes()).hexdigest()
    source_checks.append(dict(path=str(p),expected_recorded_sha256=expected,current_sha256=actual,matches=actual==expected))
patterns={
 '資料治理與泛化修復/scripts/model_profiles.py': ['def construct_model','head_keys =','load_state_dict(backbone','def optimizer_and_scheduler','optimizer = torch.optim.AdamW','T_max=training'],
 '第二階段/src/stage2/models.py':['def build_model','timm.create_model','def parameter_groups_with_layer_decay','if not parameter.requires_grad','no_decay =','def count_parameters'],
 '資料治理與泛化修復/scripts/train_regularized.py':['def load_governed_release','row["label_name"]','def build_transform','RandomResizedCrop','RandomErasing','def sample_weights','def supported_source_metrics','def evaluate','model.eval()','def train_epoch','mixed =','loss = lam','scaler.step','monitor_rows =','model = profile.construct_model','criterion =','initial_classifier_sha256','monitor = evaluate','robust_score =','train_validation_gap'],
 '資料治理與泛化修復/scripts/v2_alpha025_contract.py':['def verify_initialization','initial_classifier_sha256','initial_optimizer_state_entries'],
 '資料治理與泛化修復/scripts/v2_opt_contract.py':['def best_metrics','merged =','macro_f1=statistics.mean'],
 '第二階段/src/stage2/metrics.py':['def metrics_from_logits','matrix[target, prediction]','balanced_accuracy'],
}
anchors=[]
for rel,terms in patterns.items():
    lines=(ROOT/rel).read_text(encoding='utf-8-sig').splitlines()
    for i,l in enumerate(lines,1):
        for term in terms:
            if term in l: anchors.append(dict(path=str(ROOT/rel),line=i,text=l.strip(),term=term))
sel={s:{c:v for c,v in d['classes'].items() if c in ('NV','DF','VASC','MEL','BKL','AKIEC')} for s,d in exposure['by_source'].items()}
evidence=dict(scope='saved contracts and static source; no PT payload, model import, GPU, inference or Test access',
    reused_B_receipt=str(ROOT/'recovery_20261023/B_training/alpha025_retry1_20261024_v1/CLOSEOUT_CHECKS_20261025_v1.json'),
    reused_C_audit=str(ROOT/'recovery_20261023/C_training_config/RECOVERY_REPORT.md'),
    runs=runs,small_source_identity_checks=source_checks,anchors=anchors,
    sampling_expectations_cited_not_recomputed=sel,
    sampling_expectations_source=str(AREA/'configs/v2_512_alpha025_20261024_v1/SAMPLING_EXPOSURE.json'),
    limitations=['Optimizer names are recorded trainable tensor names, not payload numel/gradient/update measurement.',
      'B initialization checks cite pinned identity/head/source execution contract, not fresh independent byte comparison of encoder payload.',
      'Expected sampling exposure is analytic expectation, not realized per-epoch class draws.',
      'Mixed-source train_monitor BA minus source Val BA is not a matched-source generalization gap.'])
(OUT/'EVIDENCE.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'runs':len(runs),'optimizer_named_tensors':[r['optimizer_named_tensor_count'] for r in runs],
 'groups':[r['optimizer_group_count'] for r in runs], 'small_sources_match':all(x['matches'] for x in source_checks)},ensure_ascii=False))
