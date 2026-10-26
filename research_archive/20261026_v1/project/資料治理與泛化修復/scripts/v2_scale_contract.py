"""Approved Base/Large/Huge Seed1 scale screen, finite workload without time cap."""
from __future__ import annotations
import copy
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import time
import uuid
from training_state import atomic_json, file_sha256
from v2_opt_contract import describe_groups, best_metrics, now
from v2_opt_contract import close_failed_segment as original_close

PROJECT=Path(__file__).resolve().parents[2]
AREA=PROJECT/'資料治理與泛化修復'
VERSION='v2_scale512_seed1_20261025_v1'
CONFIG=AREA/'configs'/VERSION
RESULTS=AREA/'results'/VERSION
PYTHON=PROJECT/'.venv-skindetect-recovery-20261023/Scripts/python.exe'
BASE_CONFIG=AREA/'configs/v2_resolution_20261021_v1/v2in_res512.json'
TINY_RESULTS=AREA/'results/v2_resolution_20261021_v1/runs/v2in_res512/regularized_seed1'
SIZES=('base','large','huge')
CANDIDATES={f'v2in_scale512_{s}':s for s in SIZES}
LIMITS=dict(runs=3,epochs=90,max_epochs_per_run=30,wall_clock_cap_seconds=None,
            time_limit_mode='explicit_unbounded_elapsed_time_finite_workload')
TRACK_GPU_MEMORY=True
TRACK_DATA_WAIT=True
TRACK_PHASE_TIMING=True

def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def validate_candidate(config):
    candidate=config['experiment']['id']
    if candidate not in CANDIDATES:raise RuntimeError('Unapproved scale candidate')
    size=CANDIDATES[candidate]
    training=config['training']
    if training['batch_size'] not in (8,4,2,1) or training['batch_size']*training['gradient_accumulation']!=64:
        raise RuntimeError('Only approved 8x8/4x16/2x32/1x64')
    expected=copy.deepcopy(read(BASE_CONFIG))
    expected['training'].update(model=f'convnextv2_{size}',batch_size=training['batch_size'],gradient_accumulation=64//training['batch_size'])
    expected['pipeline_id']=VERSION
    expected['formal_suite']['seeds']=[1]
    expected['experiment'].update(id=candidate,confirmation_note='Direct user approved scale512 Seed1 screen 2026-10-25; Tiny reference only',
                                  weights=read(CONFIG/'WEIGHT_SPECS.json')[size])
    expected['optimization']=dict(version=VERSION,authorization_sha256=file_sha256(CONFIG/'AUTHORIZATION.md'))
    if config!=expected:raise RuntimeError('Scale recipe differs beyond authorized model/microbatch and metadata')

def gate():
    proof=read(RESULTS/'EXECUTION_GATE.json')
    if not proof['execution_authorized'] or proof['version']!=VERSION or proof['limits']!=LIMITS or not proof['cpu_passed']:
        raise RuntimeError('Scale execution gate missing/mismatched')
    for p,sha in proof['frozen_files'].items():
        if file_sha256(p)!=sha:raise RuntimeError('Frozen source/config changed: '+p)
    for package,version in proof['versions'].items():
        if importlib.metadata.version(package)!=version:raise RuntimeError('Environment changed: '+package)
    if platform.python_version()!=proof['python']:raise RuntimeError('Python changed')
    return proof

def runtime_contract(config):
    return dict(config['optimization'],execution_gate_sha256=file_sha256(RESULTS/'EXECUTION_GATE.json'),
                limits=LIMITS,seed=1,screen_only=True,wall_clock_cap_seconds=None)

def validate_execution(config,args):
    gate();validate_candidate(config)
    candidate=config['experiment']['id']
    active=read(RESULTS/'state.json').get('active') or {}
    if (not args.formal or not args.require_cuda or args.seed!=1 or args.resume
            or active.get('candidate')!=candidate or active.get('seed')!=1
            or active.get('token')!=os.environ.get('SKINDETECT_OPT_TOKEN')
            or os.environ.get('SKINDETECT_OPT_VERSION')!=VERSION
            or args.config.resolve()!=CONFIG/(candidate+'.json')
            or args.output_root.resolve()!=RESULTS/'runs'/candidate):
        raise RuntimeError('Matching fresh Seed1 controller/config/output required; no automatic Resume/retry')

def verify_initialization(inputs):
    old=read(TINY_RESULTS/'run_inputs.json')
    for key in ('selected_train_record_ids','selected_validation_record_ids'):
        if inputs[key]!=old[key]:raise RuntimeError('Original governed Train/Validation IDs differ')
    if inputs['initial_optimizer_state_entries']!=0:raise RuntimeError('Not fresh optimizer')
    candidate=inputs['contract']['experiment_id']
    cfg=read(CONFIG/(candidate+'.json'))
    size=CANDIDATES[candidate]
    accepted=read(RESULTS/'preflight'/'SELECTION.json')[size]
    if accepted['status']!='passed' or inputs['initial_classifier_sha256']!=accepted['initial_classifier_sha256']:
        raise RuntimeError('Fresh independent Seed1 head differs from preflight construction')
    if inputs['contract']['pretrained_sha256']!=cfg['experiment']['weights']['sha256']:
        raise RuntimeError('Pinned FCMAE ImageNet1K differs')

def budget_summary():
    events=[read(p) for p in (RESULTS/'budget').glob('epoch_*.json')]
    return dict(completed_epoch_segments=sum(bool(e.get('committed')) for e in events),
        used_epoch_seconds=sum(e.get('seconds',max(0,time.time()-e['started_unix'])) for e in events),
        active=[e for e in events if e['status']=='active'],events=events,wall_clock_cap_seconds=None)

class EpochBudget:
    def __init__(self,config,seed,run_id):
        self.candidate,self.seed,self.run_id=config['experiment']['id'],seed,run_id
    def begin(self,epoch):
        events=budget_summary()['events']
        if self.seed!=1 or self.candidate not in CANDIDATES or not 1<=epoch<=30:raise RuntimeError('Unapproved scale workload')
        if any(e['status']=='active' for e in events):raise RuntimeError('Unclosed epoch lease; no retry')
        if sum(bool(e.get('committed')) for e in events)>=90:raise RuntimeError('90 complete epoch cap')
        if any(e['candidate']==self.candidate and (e['run_id']!=self.run_id or (e.get('committed') and e['epoch']>=epoch)) for e in events):
            raise RuntimeError('Candidate already owns run/epoch; no repeat')
        if (RESULTS/'STOP').exists():return False
        self.start=time.perf_counter()
        self.event=dict(id=uuid.uuid4().hex,candidate=self.candidate,seed=1,run_id=self.run_id,epoch=epoch,
            token=os.environ['SKINDETECT_OPT_TOKEN'],pid=os.getpid(),started_utc=now(),started_unix=time.time(),status='active',committed=False)
        self.path=RESULTS/'budget'/('epoch_'+self.event['id']+'.json')
        atomic_json(self.path,self.event);return True
    def finish(self,descriptor):
        self.event.update(status='completed',committed=True,seconds=time.perf_counter()-self.start,ended_utc=now(),checkpoint=descriptor)
        atomic_json(self.path,self.event)

def close_failed_segment(token,reason):original_close(token,reason,root=RESULTS)
