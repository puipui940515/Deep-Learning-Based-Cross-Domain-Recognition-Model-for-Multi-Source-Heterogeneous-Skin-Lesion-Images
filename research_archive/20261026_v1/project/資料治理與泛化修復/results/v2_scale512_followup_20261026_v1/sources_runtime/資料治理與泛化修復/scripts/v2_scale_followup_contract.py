"""Only the approved Base S2 -> Base S3 -> Large micro2 S1 fresh batch."""
from __future__ import annotations
import copy
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import time
import uuid
from training_state import atomic_json,file_sha256
from v2_opt_contract import describe_groups,best_metrics,now
from v2_opt_contract import close_failed_segment as original_close

PROJECT=Path(__file__).resolve().parents[2]
AREA=PROJECT/'資料治理與泛化修復'
VERSION='v2_scale512_followup_20261026_v1'
CONFIG=AREA/'configs'/VERSION
RESULTS=AREA/'results'/VERSION
B_ROOT=PROJECT/'recovery_20261023/B_training/scale512_followup_20261026_v1'
OLD_CONFIG=AREA/'configs/v2_scale512_seed1_20261025_v1'
OLD_RESULTS=AREA/'results/v2_scale512_seed1_20261025_v1'
TINY=AREA/'results/v2_resolution_20261021_v1/runs/v2in_res512'
PYTHON=PROJECT/'.venv-skindetect-recovery-20261023/Scripts/python.exe'
JOBS=(('base_seed2','v2in_scale512_base_confirm',2,'base'),
      ('base_seed3','v2in_scale512_base_confirm',3,'base'),
      ('large_micro2_seed1','v2in_scale512_large_micro2',1,'large'))
CANDIDATES={'v2in_scale512_base_confirm':('base',[2,3]),'v2in_scale512_large_micro2':('large',[1])}
LIMITS=dict(runs=3,epochs=90,max_epochs_per_run=30,wall_clock_cap_seconds=None,
            time_limit_mode='explicit_unbounded_elapsed_time_finite_workload')
TRACK_GPU_MEMORY=TRACK_DATA_WAIT=TRACK_PHASE_TIMING=True
NOTE='User approved complete D scale512 followup draft 2026-10-26; three fresh runs only'

def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def folder(candidate,seed):return RESULTS/'runs'/candidate/f'regularized_seed{seed}'

def expected_config(candidate):
    size,seeds=CANDIDATES[candidate]
    expected=copy.deepcopy(read(OLD_CONFIG/f'v2in_scale512_{size}.json'))
    expected['pipeline_id']=VERSION
    expected['formal_suite']['seeds']=seeds
    expected['experiment'].update(id=candidate,confirmation_note=NOTE)
    expected['training'].update(batch_size=2,gradient_accumulation=32)
    expected['optimization']=dict(version=VERSION,authorization_sha256=file_sha256(CONFIG/'AUTHORIZATION.md'))
    return expected

def validate_candidate(config):
    candidate=config['experiment']['id']
    if candidate not in CANDIDATES or config!=expected_config(candidate):
        raise RuntimeError('Followup differs beyond approved candidate/seed metadata and Large 2x32')

def gate():
    proof=read(RESULTS/'EXECUTION_GATE.json')
    if (proof['version']!=VERSION or not proof['execution_authorized'] or not proof['cpu_passed']
            or proof['limits']!=LIMITS or proof['jobs']!=[list(j) for j in JOBS]):
        raise RuntimeError('Followup gate/authorization/workload mismatch')
    for path,sha in proof['frozen_files'].items():
        if file_sha256(path)!=sha:raise RuntimeError('Frozen source/config/evidence changed: '+path)
    for package,version in proof['versions'].items():
        if importlib.metadata.version(package)!=version:raise RuntimeError('Environment changed: '+package)
    if platform.python_version()!=proof['python']:raise RuntimeError('Python changed')
    return proof

def runtime_contract(config):
    return dict(config['optimization'],execution_gate_sha256=file_sha256(RESULTS/'EXECUTION_GATE.json'),
        evaluation_contract_sha256=file_sha256(CONFIG/'EVALUATION_CONTRACT.json'),limits=LIMITS,
        allowed_seeds=CANDIDATES[config['experiment']['id']][1],fresh_only=True,wall_clock_cap_seconds=None)

def validate_execution(config,args):
    gate();validate_candidate(config)
    candidate=config['experiment']['id']
    active=read(RESULTS/'state.json').get('active') or {}
    matching=[j for j in JOBS if j[1:3]==(candidate,args.seed)]
    if (len(matching)!=1 or not args.formal or not args.require_cuda or args.resume
            or active.get('job')!=matching[0][0] or active.get('candidate')!=candidate
            or active.get('seed')!=args.seed or not active.get('token')
            or active['token']!=os.environ.get('SKINDETECT_OPT_TOKEN')
            or os.environ.get('SKINDETECT_OPT_VERSION')!=VERSION
            or args.config.resolve()!=CONFIG/(candidate+'.json')
            or args.output_root.resolve()!=RESULTS/'runs'/candidate):
        raise RuntimeError('Explicit fresh followup job/seed/token/config/output required; Resume forbidden')

def verify_initialization(inputs):
    contract=inputs['contract'];candidate=contract['experiment_id'];seed=inputs['seed']
    if candidate not in CANDIDATES or seed not in CANDIDATES[candidate][1] or contract['seed']!=seed:
        raise RuntimeError('Unapproved candidate/seed initialization')
    old=read(TINY/f'regularized_seed{seed}/run_inputs.json')
    for key in ('selected_train_record_ids','selected_validation_record_ids'):
        if inputs[key]!=old[key]:raise RuntimeError('Governed Train/Validation identity mismatch')
    if len(inputs['selected_train_record_ids'])!=18919 or sum(map(len,inputs['selected_validation_record_ids'].values()))!=3611:
        raise RuntimeError('Incomplete Train/Validation')
    if inputs['initial_optimizer_state_entries']!=0:raise RuntimeError('Fresh empty optimizer required')
    cfg=read(CONFIG/(candidate+'.json'))
    if inputs['effective_training_config']!=cfg['training'] or contract['pretrained_sha256']!=cfg['experiment']['weights']['sha256']:
        raise RuntimeError('Initialization/configuration identity mismatch')
    reference=read(OLD_RESULTS/'runs/v2in_scale512_base/regularized_seed1/run_inputs.json')
    if contract['effective_transforms']!=reference['contract']['effective_transforms']:
        raise RuntimeError('Original complete transforms differ')
    head=inputs['initial_classifier_sha256']
    if len(head)!=64 or any(ch not in '0123456789abcdef' for ch in head):raise RuntimeError('Invalid initial head fingerprint')
    # Seed2/3 deliberately have no Seed1 head-SHA equality requirement.
    if candidate=='v2in_scale512_large_micro2':
        expected=read(OLD_RESULTS/'preflight/large_micro2.json')['initial_classifier_sha256']
        if head!=expected:raise RuntimeError('Large fresh Seed1 head differs from saved initialization evidence')
    sampling=inputs['data']
    if inputs.get('test_used') is not False or contract['data']!=old['contract']['data']:
        raise RuntimeError('Data provenance/Test boundary mismatch')

def budget_summary():
    events=[read(p) for p in (RESULTS/'budget').glob('epoch_*.json')]
    return dict(completed_epoch_segments=sum(bool(e.get('committed')) for e in events),
        used_epoch_seconds=sum(e.get('seconds',max(0,time.time()-e['started_unix'])) for e in events),
        active=[e for e in events if e['status']=='active'],events=events,wall_clock_cap_seconds=None)

class EpochBudget:
    def __init__(self,config,seed,run_id):
        self.candidate,self.seed,self.run_id=config['experiment']['id'],seed,run_id
    def begin(self,epoch):
        matches=[j for j in JOBS if j[1:3]==(self.candidate,self.seed)]
        if len(matches)!=1 or not 1<=epoch<=30:raise RuntimeError('Unapproved followup epoch/job')
        summary=budget_summary();events=summary['events']
        if summary['active']:raise RuntimeError('Unclosed epoch lease; no automatic retry')
        if summary['completed_epoch_segments']>=90:raise RuntimeError('90 complete epoch cap')
        own=[e for e in events if (e['candidate'],e['seed'])==(self.candidate,self.seed)]
        if any(e['run_id']!=self.run_id or not e.get('committed') or e['epoch']>=epoch for e in own):
            raise RuntimeError('Existing run/failed or repeated epoch; no automatic retry/Resume')
        if epoch!=len(own)+1:raise RuntimeError('Epoch sequence gap')
        if (RESULTS/'STOP').exists():return False
        self.start=time.perf_counter()
        self.event=dict(id=uuid.uuid4().hex,candidate=self.candidate,seed=self.seed,run_id=self.run_id,epoch=epoch,
            token=os.environ['SKINDETECT_OPT_TOKEN'],pid=os.getpid(),started_utc=now(),started_unix=time.time(),status='active',committed=False)
        self.path=RESULTS/'budget'/('epoch_'+self.event['id']+'.json');atomic_json(self.path,self.event);return True
    def finish(self,descriptor):
        if descriptor['epoch']!=self.event['epoch']:raise RuntimeError('Checkpoint/epoch mismatch')
        self.event.update(status='completed',committed=True,seconds=time.perf_counter()-self.start,ended_utc=now(),checkpoint=descriptor)
        atomic_json(self.path,self.event)

def close_failed_segment(token,reason):original_close(token,reason,root=RESULTS)
