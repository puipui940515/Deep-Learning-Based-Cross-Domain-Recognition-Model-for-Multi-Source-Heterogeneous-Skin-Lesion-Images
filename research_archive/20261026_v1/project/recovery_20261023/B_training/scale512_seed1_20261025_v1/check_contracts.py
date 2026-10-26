"""Direct CPU checks for scale integration, without training or old test-suite replay."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import sys
OUT=Path(__file__).resolve().parent;PROJECT=OUT.parents[2];AREA=PROJECT/'資料治理與泛化修復'
sys.path.insert(0,str(AREA/'scripts'))
import v2_scale_contract as c
import model_profiles as profile
checks=[]
def check(name,condition):
    assert condition,name
    checks.append(name)
def node(source,name):
    tree=ast.parse(source)
    return ast.dump(next(n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name),include_attributes=False)
trainer=AREA/'scripts/train_regularized.py';before=(OUT/'before/train_regularized.py').read_text(encoding='utf-8')
current=trainer.read_text(encoding='utf-8')
for name in ('train_epoch','evaluate','supported_source_metrics','build_transform','load_governed_release'):
    check('original_unchanged_'+name,node(before,name)==node(current,name))
for path in [trainer,AREA/'scripts/model_profiles.py',AREA/'scripts/v2_scale_contract.py',PROJECT/'第二階段/src/stage2/models.py',OUT/'gpu_preflight.py',OUT/'run_preflights.py']:
    ast.parse(path.read_text(encoding='utf-8'));checks.append('syntax_'+path.name)
for size in c.SIZES:
    cfg=c.read(c.CONFIG/f'v2in_scale512_{size}.json')
    for micro in (8,4,2,1):
        option=copy.deepcopy(cfg);option['training'].update(batch_size=micro,gradient_accumulation=64//micro)
        profile.validate_profile(option,formal=True);checks.append(f'{size}_{micro}x{64//micro}_accepted')
    for field,value in [('class_balance_alpha',.25),('learning_rate',.001),('num_workers',0),('image_size',224)]:
        wrong=copy.deepcopy(cfg);wrong['training'][field]=value
        try:profile.validate_profile(wrong,formal=True)
        except RuntimeError:checks.append(size+'_reject_'+field)
        else:raise AssertionError('Unapproved mutation accepted')
old=c.read(c.BASE_CONFIG);profile.validate_profile(old,formal=True);checks.append('original_tiny_profile_retained')
protected=c.read(OUT/'PROTECTED_INPUTS.json')
check('unrelated_original_files_unchanged',all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in protected.items()))
check('finite_workload_no_time_cap',c.LIMITS['runs']==3 and c.LIMITS['epochs']==90 and c.LIMITS['wall_clock_cap_seconds'] is None)
check('no_model_import_in_cpu_check',all(x not in sys.modules for x in ('torch','timm','torchvision')))
(OUT/'CPU_CHECKS.json').write_text(json.dumps(dict(status='passed',checks=checks,torch_imported=False),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(status='passed',count=len(checks),torch_imported=False)))
