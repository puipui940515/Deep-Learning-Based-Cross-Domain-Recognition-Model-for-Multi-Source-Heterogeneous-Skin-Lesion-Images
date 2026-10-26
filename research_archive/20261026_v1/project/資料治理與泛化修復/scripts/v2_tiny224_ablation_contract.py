"""Fresh-only, finite six-run Tiny224 single-variable ablation contract."""
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
from v2_tiny224_ablation import VARIANTS, audit

PROJECT = Path(__file__).resolve().parents[2]
AREA = PROJECT / '資料治理與泛化修復'
VERSION = 'v2_tiny224_activation_dropout_ablation_20261026_v1'
CONFIG = AREA / 'configs' / VERSION
STUDY_RESULTS = AREA / 'results' / VERSION
RESULTS = STUDY_RESULTS / 'executions/ampwin1_20261026_v1'
CPU_ROOT = PROJECT / 'recovery_20261023/B_training/tiny224_activation_dropout_ablation_20261026_v1'
B_ROOT = CPU_ROOT / 'ampwin1_20261026_v1'
BASE_CONFIG = AREA / 'configs/five_model_baseline_20261019_v1/convnextv2_tiny_imagenet.json'
BASE_RESULTS = AREA / 'results/baseline_20261019_v1/runs/convnextv2_tiny_imagenet'
BASE_SHA = '4982675565cbd7641846b5865e4c30cea2a9efdfa20265505f8c05ee69c99940'
PYTHON = PROJECT / '.venv-skindetect-recovery-20261023/Scripts/python.exe'
EXECUTION_REV = 'ampwin1_20261026_v1'
DISPATCH_TOKEN = '[DISPATCH_TOKEN_REDACTED]'
CANDIDATES = {'v2in_tiny224_relu_only': ('relu', [1, 2, 3]),
              'v2in_tiny224_stage_dropout01_only': ('dropout', [1, 2, 3])}
JOBS = tuple((f'{group}_seed{seed}', candidate, seed, group)
             for candidate, (group, seeds) in CANDIDATES.items() for seed in seeds)
MICRO = {'relu': 32, 'dropout': 32}
LIMITS = dict(runs=6, epochs=180, max_epochs_per_run=30, wall_clock_cap_seconds=None,
              time_limit_mode='explicit_unbounded_elapsed_time_finite_workload')
TRACK_GPU_MEMORY = TRACK_DATA_WAIT = TRACK_PHASE_TIMING = True


def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def folder(candidate, seed): return RESULTS / 'runs' / candidate / f'regularized_seed{seed}'
def reference_folder(group, seed): return BASE_RESULTS / f'regularized_seed{seed}'


def expected_config(candidate):
    if candidate not in CANDIDATES or file_sha256(BASE_CONFIG) != BASE_SHA:
        raise RuntimeError('Unknown candidate or changed original224 configuration')
    expected = copy.deepcopy(read(BASE_CONFIG))
    expected['pipeline_id'] = VERSION
    expected['experiment'].update(id=candidate,
        confirmation_note='User authorized one Tiny224 scientific variable only, 2026-10-26; '+DISPATCH_TOKEN)
    expected['architecture_modification'] = copy.deepcopy(VARIANTS[candidate])
    expected['optimization'] = dict(version=VERSION, authorization_sha256=file_sha256(CONFIG / 'AUTHORIZATION.md'))
    return expected


def validate_candidate(config):
    candidate = config['experiment']['id']
    if candidate not in CANDIDATES or config != expected_config(candidate):
        raise RuntimeError('Candidate changed beyond its single approved architecture variable and identity metadata')


def gate():
    proof = read(RESULTS / 'EXECUTION_GATE.json')
    if (proof['version'] != VERSION or not proof['execution_authorized'] or not proof['cpu_passed']
            or not proof['gpu_passed'] or not proof['io_passed'] or proof['dispatch_token'] != DISPATCH_TOKEN
            or proof['execution_revision'] != EXECUTION_REV or proof['limits'] != LIMITS
            or proof['jobs'] != [list(job) for job in JOBS]):
        raise RuntimeError('New batch authorization/validation/budget mismatch')
    for path, sha in proof['frozen_files'].items():
        if file_sha256(path) != sha: raise RuntimeError('Frozen source/config/evidence changed: '+path)
    for package, version in proof['versions'].items():
        if importlib.metadata.version(package) != version: raise RuntimeError('Environment changed: '+package)
    if platform.python_version() != proof['python']: raise RuntimeError('Python changed')
    return proof


def runtime_contract(config):
    return dict(config['optimization'], execution_gate_sha256=file_sha256(RESULTS/'EXECUTION_GATE.json'),
        evaluation_contract_sha256=file_sha256(CONFIG/'COMPARISON_CONTRACT.json'), limits=LIMITS,
        repair_authorization_sha256=file_sha256(B_ROOT/'REPAIR_AUTHORIZATION.md'),
        execution_revision=EXECUTION_REV, authorization_id=DISPATCH_TOKEN,
        architecture_modification=config['architecture_modification'], allowed_seeds=[1, 2, 3],
        fresh_only=True, wall_clock_cap_seconds=None)


def validate_execution(config, args):
    gate(); validate_candidate(config)
    candidate = config['experiment']['id']; active = read(RESULTS/'state.json').get('active') or {}
    matching = [job for job in JOBS if job[1:3] == (candidate, args.seed)]
    if (len(matching) != 1 or not args.formal or not args.require_cuda or args.resume
            or active.get('job') != matching[0][0] or active.get('execution_revision') != EXECUTION_REV
            or active.get('candidate') != candidate or active.get('seed') != args.seed
            or not active.get('token') or active['token'] != os.environ.get('SKINDETECT_OPT_TOKEN')
            or os.environ.get('SKINDETECT_OPT_VERSION') != VERSION
            or args.config.resolve() != CONFIG/(candidate+'.json')
            or args.output_root.resolve() != RESULTS/'runs'/candidate):
        raise RuntimeError('Explicit new fresh job/seed/token/config/output required; Resume forbidden')


def model_audit(model, config): return audit(model, config)
def architecture_name(config): return config['experiment']['id']+'_7_class'
def gpu_evidence(group): return read(B_ROOT/f'GPU_{group}.json')


def verify_initialization(inputs):
    contract = inputs['contract']; candidate = contract['experiment_id']; seed = inputs['seed']
    if candidate not in CANDIDATES or seed not in (1, 2, 3) or contract['seed'] != seed:
        raise RuntimeError('Unapproved architecture/Seed')
    group = CANDIDATES[candidate][0]; old = read(reference_folder(group, seed)/'run_inputs.json')
    for key in ('selected_train_record_ids', 'selected_validation_record_ids'):
        if inputs[key] != old[key]: raise RuntimeError('Original224 same-Seed data IDs differ')
    if len(inputs['selected_train_record_ids']) != 18919 or sum(map(len, inputs['selected_validation_record_ids'].values())) != 3611:
        raise RuntimeError('Incomplete governed Train/Validation')
    cfg = read(CONFIG/(candidate+'.json'))
    if (inputs['initial_optimizer_state_entries'] != 0 or inputs['effective_training_config'] != cfg['training']
            or cfg['training'] != old['effective_training_config'] or inputs['test_used'] is not False):
        raise RuntimeError('Fresh initialization/original recipe/Test boundary differs')
    if (contract['pretrained_sha256'] != cfg['experiment']['weights']['sha256']
            or contract['data'] != old['contract']['data'] or contract['class_names'] != old['contract']['class_names']):
        raise RuntimeError('Pinned weights/data/classes differ')
    cpu = read(CPU_ROOT/f'CPU_{group}.json')
    if contract['effective_transforms'] != cpu['effective_transforms']:
        raise RuntimeError('Original224 full preprocessing differs')
    if inputs['architecture_audit'] != cpu['architecture_audit']:
        raise RuntimeError('Actual single-variable architecture differs')
    if inputs['initial_classifier_sha256'] != old['initial_classifier_sha256']:
        raise RuntimeError('Newly constructed head differs from original same-Seed initialization')
    if seed == 1 and inputs['initial_classifier_sha256'] != gpu_evidence(group)['initial_classifier_sha256']:
        raise RuntimeError('Seed1 initialization differs from compatibility evidence')


def budget_summary():
    events = [read(path) for path in (RESULTS/'budget').glob('epoch_*.json')]
    return dict(completed_epoch_segments=sum(bool(e.get('committed')) for e in events),
        used_epoch_seconds=sum(e.get('seconds', max(0, time.time()-e['started_unix'])) for e in events),
        active=[e for e in events if e['status'] == 'active'], events=events, wall_clock_cap_seconds=None)


class EpochBudget:
    def __init__(self, config, seed, run_id):
        self.candidate, self.seed, self.run_id = config['experiment']['id'], seed, run_id

    def begin(self, epoch):
        if len([job for job in JOBS if job[1:3] == (self.candidate, self.seed)]) != 1 or not 1 <= epoch <= 30:
            raise RuntimeError('Unapproved epoch/job')
        summary = budget_summary(); events = summary['events']
        if summary['active']: raise RuntimeError('Unclosed epoch lease; no automatic retry')
        if summary['completed_epoch_segments'] >= 180: raise RuntimeError('180 complete epoch cap')
        own = [e for e in events if (e['candidate'], e['seed']) == (self.candidate, self.seed)]
        if any(e['run_id'] != self.run_id or not e.get('committed') or e['epoch'] >= epoch for e in own):
            raise RuntimeError('Existing/failed/repeated epoch; no automatic retry or Resume')
        if epoch != len(own)+1: raise RuntimeError('Epoch sequence gap')
        if (RESULTS/'STOP').exists(): return False
        self.start = time.perf_counter()
        self.event = dict(id=uuid.uuid4().hex, candidate=self.candidate, seed=self.seed, run_id=self.run_id,
            epoch=epoch, token=os.environ['SKINDETECT_OPT_TOKEN'], pid=os.getpid(), started_utc=now(),
            started_unix=time.time(), status='active', committed=False)
        self.path = RESULTS/'budget'/('epoch_'+self.event['id']+'.json'); atomic_json(self.path, self.event)
        return True

    def finish(self, descriptor):
        if descriptor['epoch'] != self.event['epoch']: raise RuntimeError('Checkpoint/epoch mismatch')
        self.event.update(status='completed', committed=True, seconds=time.perf_counter()-self.start,
                          ended_utc=now(), checkpoint=descriptor)
        atomic_json(self.path, self.event)


def close_failed_segment(token, reason): original_close(token, reason, root=RESULTS)
