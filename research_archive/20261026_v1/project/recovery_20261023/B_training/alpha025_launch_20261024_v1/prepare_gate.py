"""Bind C's unchanged delivery, new B authorization, actual CPU checks and sources."""
import ast
import importlib.metadata
import json
from pathlib import Path
import sys
from datetime import datetime

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'資料治理與泛化修復/scripts'))
import v2_alpha025_contract as c
from training_state import file_sha256, atomic_json

def main():
    if (c.RESULTS/'EXECUTION_GATE.json').exists():raise RuntimeError('Existing gate; preserve, do not regenerate')
    qa=c.read(c.CONFIG/'STATIC_QA.json')
    if not all(x['passed'] for x in qa['checks']):raise RuntimeError('C static checks not all passed')
    for name,sha in qa['output_sha256'].items():
        if file_sha256(c.CONFIG/name)!=sha:raise RuntimeError('C delivery changed: '+name)
    inputs={}
    # Read all delivered text/JSON; never C's generator or datasets/images/Test.
    for p in c.CONFIG.iterdir():
        if p.is_file():
            inputs[p.name]=c.read(p) if p.suffix=='.json' else p.read_text(encoding='utf-8-sig')
    c.validate_candidate(inputs[c.CANDIDATE+'.json'])
    difference=inputs['DIFF_AND_SOURCES.json']
    d=inputs['EVALUATION_CONTRACT.json']['rule_source']
    if file_sha256(d['path'])!=d['sha256']:raise RuntimeError('D governing source changed; stop')
    if difference['scientific_diff']!=[{'path':'/training/class_balance_alpha','before':.5,'after':.25}]:
        raise RuntimeError('C unique difference conflict')
    limits=inputs['suite.json']['limits']
    if (limits['runs'],limits['max_complete_epoch_segments'],limits['wall_clock_cap_seconds'])!=(3,90,None):
        raise RuntimeError('C limit conflict')
    if inputs['suite.json']['formal_training_authorized'] is not False:
        raise RuntimeError('C configuration delivery unexpected; use separate B authorization')
    versions={p:importlib.metadata.version(p) for p in ('torch','torchvision','timm','numpy','Pillow')}
    if versions!={'torch':'2.11.0+cu128','torchvision':'0.26.0+cu128','timm':'1.0.30','numpy':'1.26.4','Pillow':'10.4.0'}:
        raise RuntimeError('Required runtime package metadata differs')
    b=Path(__file__).parent
    log=(b/'CPU_TESTS.log').read_text(encoding='utf-8-sig')
    if 'Ran 12 tests' not in log or 'OK' not in log:raise RuntimeError('Related CPU checks not completed')
    launcher=c.AREA/'scripts/Start-V2Alpha025.ps1'
    source=[c.AREA/'scripts'/n for n in ('train_regularized.py','model_profiles.py','v2_alpha025_contract.py','run_v2_alpha025.py',
             'training_state.py','coverage_sampler.py','v2_opt_contract.py')]
    source += [ROOT/'第二階段/src/stage2'/n for n in ('models.py','engine.py','metrics.py')]
    for p in source:ast.parse(p.read_text(encoding='utf-8-sig'))
    cpu=c.read(ROOT/'recovery_20261023/A_data_environment/quick_model_check_20261024_v1/cpu_result.json')
    gpu=c.read(ROOT/'recovery_20261023/B_training/minimal_realdata_gpu_20261024_v1/gpu_result.json')
    if cpu['status']!='passed' or gpu['status']!='passed':raise RuntimeError('Prior compatibility not passed')
    # Freeze actual source bytes; never replace original historical evidence hashes.
    frozen=source+[launcher,*[p for p in c.CONFIG.iterdir() if p.is_file()],Path(d['path']),c.BASE_CONFIG,
                   b/'B_EXECUTION_AUTHORIZATION.md',b/'CPU_TESTS.log',Path(__file__)]
    for seed in (1,2,3):frozen.append(c.BASE_RESULTS/f'regularized_seed{seed}'/'run_inputs.json')
    gate=dict(version=c.VERSION,at=datetime.now().astimezone().isoformat(),execution_authorized=True,
              B_authorization_source=str(b/'B_EXECUTION_AUTHORIZATION.md'),C_configuration_delivery_unchanged=True,
              limits=c.LIMITS,cpu_compatibility_passed=True,cpu_checks=12,model_or_cuda_tests_repeated=False,
              reused_gpu_receipt=str(ROOT/'recovery_20261023/B_training/minimal_realdata_gpu_20261024_v1/gpu_result.json'),
              versions=versions,python_version='3.12.10',python=str(c.PYTHON),
              frozen_files={str(p):file_sha256(p) for p in frozen})
    c.RESULTS.mkdir(parents=True,exist_ok=True)
    for name in ('attempts','budget','logs','sources_runtime'):(c.RESULTS/name).mkdir(exist_ok=True)
    import shutil
    for p in source+[launcher]:
        dest=c.RESULTS/'sources_runtime'/p.relative_to(ROOT)
        dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():raise RuntimeError('Source snapshot exists; preserve')
        shutil.copy2(p,dest)
    atomic_json(c.RESULTS/'EXECUTION_GATE.json',gate)
    c.gate()
    atomic_json(b/'PREPARATION.json',dict(status='new_gate_ready',configuration_approved=True,
                execution_authorized=True,training_started=False,CUDA_test_repeated=False,
                gate_sha256=file_sha256(c.RESULTS/'EXECUTION_GATE.json'),C_files_verified=len(qa['output_sha256']),
                candidate=c.CANDIDATE,limits=c.LIMITS))
    print(json.dumps(dict(status='new_gate_ready',limits=c.LIMITS,versions=versions),ensure_ascii=False))

if __name__=='__main__':main()
