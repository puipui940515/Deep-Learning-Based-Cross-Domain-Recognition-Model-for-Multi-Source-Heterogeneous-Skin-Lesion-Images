"""One approved alpha025 study. Explicitly unbounded time, finite workload."""
from __future__ import annotations
import copy
import importlib.metadata
import json
import os
import platform
import time
import uuid
from pathlib import Path
from training_state import atomic_json, file_sha256
from v2_opt_contract import describe_groups, best_metrics, now

PROJECT=Path(__file__).resolve().parents[2]
AREA=PROJECT/'資料治理與泛化修復'
VERSION='v2_512_alpha025_20261024_v1'
CANDIDATE='v2in_res512_alpha025'
CONFIG=AREA/'configs'/VERSION
RESULTS=AREA/'results'/VERSION
PYTHON=PROJECT/'.venv-skindetect-recovery-20261023/Scripts/python.exe'
BASE_CONFIG=AREA/'configs/v2_resolution_20261021_v1/v2in_res512.json'
BASE_RESULTS=AREA/'results/v2_resolution_20261021_v1/runs/v2in_res512'
TRACK_GPU_MEMORY=True
TRACK_DATA_WAIT=True
LIMITS={'runs':3,'epochs':90,'max_epochs_per_run':30,'wall_clock_cap_seconds':None,
        'time_limit_mode':'explicit_unbounded_elapsed_time_finite_workload'}

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def validate_candidate(config):
    base=read(BASE_CONFIG)
    expected=copy.deepcopy(base)
    expected['training']['class_balance_alpha']=.25
    expected['experiment']['id']=CANDIDATE
    expected['experiment']['confirmation_note']=read(CONFIG/(CANDIDATE+'.json'))['experiment']['confirmation_note']
    expected['pipeline_id']=VERSION
    expected['optimization']={'version':VERSION,'authorization_sha256':file_sha256(CONFIG/'AUTHORIZATION.md')}
    if config != expected:
        raise RuntimeError('Candidate differs beyond alpha .5 -> .25 and approved metadata')
    if config['training'] != read(CONFIG/'PLANNED_EFFECTIVE_CONTRACT.json')['training']:
        raise RuntimeError('C planned effective training contract differs')

def gate():
    delivery=read(CONFIG/'suite.json')
    if (delivery['configuration_approved'] is not True or delivery['seeds'] != [1,2,3]
            or delivery['candidates'] != [CANDIDATE]
            or delivery['limits']['wall_clock_cap_seconds'] is not None
            or delivery['limits']['max_complete_epoch_segments'] != 90):
        raise RuntimeError('C approved finite-workload policy differs')
    proof=read(RESULTS/'EXECUTION_GATE.json')
    if (proof.get('execution_authorized') is not True or proof['version'] != VERSION
            or proof['limits'] != LIMITS or proof.get('cpu_compatibility_passed') is not True):
        raise RuntimeError('New B execution authorization/CPU gate missing')
    for p,h in proof['frozen_files'].items():
        if Path(p).name.lower()=='test.csv':raise RuntimeError('Test sealed')
        if file_sha256(p) != h:raise RuntimeError('New frozen source/config changed: '+p)
    for name,version in proof['versions'].items():
        if importlib.metadata.version(name) != version:raise RuntimeError('Environment version differs: '+name)
    if platform.python_version() != proof['python_version']:raise RuntimeError('Python differs')
    validate_candidate(read(CONFIG/(CANDIDATE+'.json')))
    return proof

def runtime_contract(config):
    return dict(config['optimization'],execution_gate_sha256=file_sha256(RESULTS/'EXECUTION_GATE.json'),
                suite_sha256=file_sha256(CONFIG/'suite.json'),limits=LIMITS,all_three_seeds_required=True)

def validate_execution(config,args):
    gate()
    active=read(RESULTS/'state.json').get('active') or {}
    if (not args.formal or not args.require_cuda or args.seed not in (1,2,3)
            or active.get('candidate') != CANDIDATE or active.get('seed') != args.seed
            or not active.get('token') or active['token'] != os.environ.get('SKINDETECT_OPT_TOKEN')
            or os.environ.get('SKINDETECT_OPT_VERSION') != VERSION
            or args.config.resolve() != CONFIG/(CANDIDATE+'.json')
            or args.output_root.resolve() != RESULTS/'runs'/CANDIDATE):
        raise RuntimeError('Matching new controller/token/seed/output required')

def verify_initialization(inputs):
    old=read(BASE_RESULTS/f"regularized_seed{inputs['seed']}"/'run_inputs.json')
    for key in ('initial_classifier_sha256','selected_train_record_ids','selected_validation_record_ids'):
        if inputs[key] != old[key]:raise RuntimeError('New independent initialization/data identity differs: '+key)
    if inputs['initial_optimizer_state_entries'] != 0:raise RuntimeError('Optimizer inherited state')
    if inputs['contract']['pretrained_sha256'] != old['contract']['pretrained_sha256']:
        raise RuntimeError('Pinned ImageNet identity differs')

def workload_guard(events,seed,run_id,epoch):
    if seed not in (1,2,3) or not 1<=epoch<=30:raise RuntimeError('Unapproved seed/epoch')
    if any(e['status']=='active' for e in events):raise RuntimeError('Unclosed epoch ledger; reconcile stopped child first')
    identities={(e['seed'],e['run_id']) for e in events}
    if any(s==seed and rid!=run_id for s,rid in identities):raise RuntimeError('Seed already owns another run; no fresh retry')
    if (seed,run_id) not in identities and len(identities)>=3:raise RuntimeError('Three-run limit')
    if any(e.get('committed') and e['seed']==seed and e['epoch']>=epoch for e in events):
        raise RuntimeError('Committed epoch cannot be repeated')
    if sum(bool(e.get('committed')) for e in events)>=90:raise RuntimeError('90 complete epoch limit')

def budget_summary(root=RESULTS):
    events=[read(p) for p in (root/'budget').glob('epoch_*.json')]
    return dict(wall_clock_cap_seconds=None,remaining_seconds=None,time_limit_mode=LIMITS['time_limit_mode'],
                used_epoch_seconds=sum(e.get('seconds',max(0,time.time()-e['started_unix'])) for e in events),
                completed_epoch_segments=sum(bool(e.get('committed')) for e in events),
                active=[e for e in events if e['status']=='active'],events=events)

class EpochBudget:
    def __init__(self,config,seed,run_id):
        self.seed,self.run_id=seed,run_id
    def begin(self,epoch):
        workload_guard(budget_summary()['events'],self.seed,self.run_id,epoch)
        if (RESULTS/'STOP').exists():return False
        self.started=time.perf_counter()
        self.event=dict(id=uuid.uuid4().hex,candidate=CANDIDATE,seed=self.seed,run_id=self.run_id,epoch=epoch,
                        token=os.environ['SKINDETECT_OPT_TOKEN'],pid=os.getpid(),started_utc=now(),
                        started_unix=time.time(),status='active',committed=False)
        self.path=RESULTS/'budget'/('epoch_'+self.event['id']+'.json')
        atomic_json(self.path,self.event)
        return True
    def finish(self,checkpoint):
        self.event.update(status='completed',committed=True,ended_utc=now(),seconds=time.perf_counter()-self.started,
                          checkpoint=checkpoint,measurement='epoch_including_validation_checkpoint_metric_fsync')
        atomic_json(self.path,self.event)

def close_failed_segment(token,reason):
    for path in (RESULTS/'budget').glob('epoch_*.json'):
        e=read(path)
        if e['status']=='active' and e['token']==token:
            index=RESULTS/'runs'/CANDIDATE/f"regularized_seed{e['seed']}"/'checkpoints/index.json'
            committed=index.is_file() and any(g['epoch']==e['epoch'] for g in read(index)['generations'])
            e.update(status='interrupted',committed=bool(committed),ended_utc=now(),
                     seconds=max(0,time.time()-e['started_unix']),reason=reason)
            atomic_json(path,e)
