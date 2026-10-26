"""Approved two-candidate contract, paired gates, and durable epoch budget.

No alternative trainer, model builder, transform, or checkpoint implementation.
"""
from __future__ import annotations
import copy
import hashlib
import json
import math
import os
import statistics
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from training_state import atomic_json, file_sha256

PROJECT = Path(r'D:\SkinDetect_base')
AREA = PROJECT / '資料治理與泛化修復'
VERSION = 'v2_optimization_20261020_v1'
CONFIG = AREA / 'configs' / VERSION
RESULTS = AREA / 'results' / VERSION
BASE_CONFIG = AREA / 'configs/five_model_baseline_20261019_v1/convnextv2_tiny_imagenet.json'
BASE_RESULTS = AREA / 'results/baseline_20261019_v1/runs/convnextv2_tiny_imagenet'
BASE_SHA = '4982675565cbd7641846b5865e4c30cea2a9efdfa20265505f8c05ee69c99940'
CANDIDATES = {'v2in_lr5e5': ('learning_rate', 0.00005), 'v2in_ld09': ('layer_decay', 0.9)}
LIMITS = {'runs': 6, 'epochs': 180, 'loop_seconds': 25920}
LABELS = ['AKIEC', 'BCC', 'BKL', 'DF', 'NV', 'VASC', 'MEL']


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def suite():
    value = read(CONFIG / 'suite.json')
    if (value['version'] != VERSION or value['candidates'] != list(CANDIDATES)
            or value['seeds'] != [1, 2, 3] or value['limits'] != LIMITS
            or value['formal_training_authorized'] is not True):
        raise RuntimeError('Optimization authorization/order/budget differs')
    if file_sha256(CONFIG / 'AUTHORIZATION.md') != value['authorization_sha256']:
        raise RuntimeError('Authorization fingerprint differs')
    return value


def validate_candidate(config):
    identifier = config['experiment']['id']
    if identifier not in CANDIDATES or file_sha256(BASE_CONFIG) != BASE_SHA:
        raise RuntimeError('Unapproved candidate or changed baseline')
    spec = suite()
    expected = copy.deepcopy(read(BASE_CONFIG))
    key, value = CANDIDATES[identifier]
    expected['training'][key] = value
    expected['experiment']['id'] = identifier
    expected['optimization'] = {'version': VERSION, 'authorization_sha256': spec['authorization_sha256']}
    if config != expected:
        raise RuntimeError('Candidate differs beyond its single approved variable')


def gate(require_acceptance=True):
    spec = suite()
    for path, sha in spec['immutable_inputs'].items():
        # Test content is deliberately not present in this allowlist.
        if Path(path).name.lower() == 'test.csv':
            raise RuntimeError('Test must remain sealed')
        if file_sha256(path) != sha:
            raise RuntimeError('Frozen input/source differs: ' + path)
    for identifier in CANDIDATES:
        validate_candidate(read(CONFIG / (identifier + '.json')))
    if require_acceptance:
        acceptance = read(CONFIG / 'ACCEPTANCE.json')
        if acceptance.get('passed') is not True or acceptance.get('kind') != 'non_training_cpu':
            raise RuntimeError('Non-training acceptance has not passed')
        for path, sha in acceptance['runtime_hashes'].items():
            if file_sha256(path) != sha:
                raise RuntimeError('Accepted runtime fingerprint differs: ' + path)
    return spec


def runtime_contract(config):
    return dict(config['optimization'], suite_sha256=file_sha256(CONFIG / 'suite.json'),
                acceptance_sha256=file_sha256(CONFIG / 'ACCEPTANCE.json'), limits=LIMITS)


def validate_execution(config, args):
    validate_candidate(config)
    gate()
    active = read(RESULTS / 'state.json').get('active', {})
    if (not args.formal or not args.require_cuda or args.seed not in [1, 2, 3]
            or active.get('candidate') != config['experiment']['id'] or active.get('seed') != args.seed
            or active.get('token') != os.environ.get('SKINDETECT_OPT_TOKEN')
            or not active.get('token')
            or args.config.resolve() != CONFIG / (config['experiment']['id'] + '.json')
            or args.output_root.resolve() != RESULTS / 'runs' / config['experiment']['id']):
        raise RuntimeError('Candidate must run through its authorized sequential controller')


def describe_groups(model, optimizer):
    names = {id(p): n for n, p in model.named_parameters()}
    return [dict(group=i, parameter_names=[names[id(p)] for p in g['params']],
                 initial_lr=g['lr'], weight_decay=g['weight_decay'])
            for i, g in enumerate(optimizer.param_groups)]


def budget_summary(root=RESULTS):
    events = [read(p) for p in (root / 'budget').glob('epoch_*.json')]
    active = [e for e in events if e['status'] == 'active']
    spent = sum(e['seconds'] for e in events if e['status'] != 'active')
    live = sum(max(0, time.time() - e['started_unix']) for e in active)
    return dict(charged_seconds=spent, active_seconds=live, used_seconds=spent + live,
                remaining_seconds=max(0, LIMITS['loop_seconds'] - spent - live),
                completed_epoch_segments=sum(bool(e.get('committed')) for e in events),
                run_count=len({(e['candidate'], e['seed']) for e in events}),
                active=active, events=events)


def reserve_seconds(summary):
    observed = [e['seconds'] for e in summary['events'] if e.get('committed')]
    return max(600.0, 2.0 * max(observed, default=120.0))


class EpochBudget:
    def __init__(self, config, seed, run_id, root=RESULTS):
        self.candidate, self.seed, self.run_id = config['experiment']['id'], seed, run_id
        self.root, self.event = root, None

    def begin(self, epoch):
        summary = budget_summary(self.root)
        if summary['active']:
            raise RuntimeError('Unclosed epoch timing lease; manual reconciliation required')
        identity = (self.candidate, self.seed)
        identities = {(e['candidate'], e['seed']) for e in summary['events']}
        if identity not in identities and len(identities) >= LIMITS['runs']:
            raise RuntimeError('Run budget exhausted')
        if (summary['remaining_seconds'] < reserve_seconds(summary)
                or summary['completed_epoch_segments'] >= LIMITS['epochs']):
            atomic_json(self.root / 'BUDGET_PAUSE.json', dict(at=now(), reason='insufficient_safe_epoch_reserve',
                        candidate=self.candidate, seed=self.seed, next_epoch=epoch,
                        remaining_seconds=summary['remaining_seconds'], reserve_seconds=reserve_seconds(summary)))
            return False
        self.started = time.perf_counter()
        self.event = dict(id=uuid.uuid4().hex, candidate=self.candidate, seed=self.seed, run_id=self.run_id,
                          epoch=epoch, token=os.environ.get('SKINDETECT_OPT_TOKEN'), pid=os.getpid(),
                          started_utc=now(), started_unix=time.time(), status='active', committed=False)
        self.path = self.root / 'budget' / ('epoch_' + self.event['id'] + '.json')
        atomic_json(self.path, self.event)
        return True

    def finish(self, checkpoint):
        self.event.update(status='completed', committed=True, ended_utc=now(),
                          seconds=time.perf_counter() - self.started, checkpoint=checkpoint,
                          measurement='trainer_epoch_perf_counter_including_validation_checkpoint_and_metric_fsync')
        atomic_json(self.path, self.event)
        self.event = None


def close_failed_segment(token, reason, root=RESULTS):
    # Only while the child has failed/exited; never run on a live restored epoch.
    for path in (root / 'budget').glob('epoch_*.json'):
        event = read(path)
        if event['status'] == 'active' and event['token'] == token:
            seconds = time.time() - event['started_unix']
            if seconds < 0:
                raise RuntimeError('Clock moved backwards; budget cannot be reconciled')
            index_path = root / 'runs' / event['candidate'] / f"regularized_seed{event['seed']}" / 'checkpoints/index.json'
            index = read(index_path) if index_path.exists() else {}
            committed = any(g['epoch'] == event['epoch'] for g in index.get('generations', []))
            event.update(status='interrupted', seconds=seconds, ended_utc=now(), committed=committed,
                         reason=reason, measurement='wall_time_to_observed_failure_conservative_upper_bound')
            atomic_json(path, event)


def best_metrics(result):
    best = result['best']
    sources = best['validation_by_source']
    merged = [[sum(s['confusion_matrix'][i][j] for s in sources.values()) for j in range(7)] for i in range(7)]
    total = sum(map(sum, merged))
    recall, f1 = [], []
    for i in range(7):
        tp, support = merged[i][i], sum(merged[i])
        precision_denom = sum(row[i] for row in merged)
        recall.append(tp / support if support else 0.0)
        f1.append(2 * tp / (support + precision_denom) if support + precision_denom else 0.0)
    values = dict(robust=best['robust_selection_score'], accuracy=sum(merged[i][i] for i in range(7))/total,
                  macro_f1=statistics.mean(f1), combined_mel=recall[6])
    diseases = {}
    for source, item in sources.items():
        values[source + ':ba'] = item['balanced_accuracy']
        matrix = item['confusion_matrix']
        diseases[source] = {}
        for i in item['metric_labels']:
            tp, support = matrix[i][i], sum(matrix[i])
            if support <= 0:
                raise RuntimeError('Supported disease has no validation support')
            values[source + ':' + LABELS[i]] = tp / support
            diseases[source][LABELS[i]] = dict(tp=tp, support=support, recall=tp/support)
    if not all(math.isfinite(v) for v in values.values()):
        raise RuntimeError('Non-finite paired metric')
    return dict(values=values, diseases=diseases, merged_confusion_matrix=merged,
                best_epoch=best['epoch'], validation_by_source=sources)


def decide(candidate, results, baselines):
    seeds = sorted(results)
    if seeds not in ([1, 2], [1, 2, 3]) or sorted(baselines) != seeds:
        raise RuntimeError('Gate requires the exact paired seeds')
    values, deltas = {}, {}
    for seed in seeds:
        values[seed] = best_metrics(results[seed])
        baseline = best_metrics(baselines[seed])
        deltas[seed] = {k: v - baseline['values'][k] for k, v in values[seed]['values'].items()}
    means = {k: statistics.mean(d[k] for d in deltas.values()) for k in deltas[seeds[0]]}
    checks = {}
    if len(seeds) == 2:
        checks.update(robust=means['robust'] > 0, bcn=means['BCN20000:ba'] > 0,
                      macro_f1=means['macro_f1'] >= 0, accuracy=means['accuracy'] >= -.005)
    else:
        checks.update(robust=means['robust'] >= .0100, bcn=means['BCN20000:ba'] > 0,
                      macro_f1=means['macro_f1'] > 0, accuracy=means['accuracy'] > 0,
                      at_least_two_improved=sum(d['robust'] > 0 for d in deltas.values()) >= 2)
    checks['per_seed_robust'] = all(d['robust'] >= -.01 for d in deltas.values())
    for source in ('HAM10000', 'PAD-UFES-20'):
        checks[source + ':ba'] = means[source + ':ba'] >= -.01
    for disease in ('DF', 'BKL', 'MEL'):
        checks['BCN20000:' + disease] = means['BCN20000:' + disease] >= -.03
    checks['combined_mel'] = means['combined_mel'] >= -.01
    if len(seeds) == 3:
        for key in means:
            if ':' in key and not key.endswith(':ba'):
                checks['disease_guard:' + key] = means[key] >= -.05
    return dict(candidate=candidate, stage='screen' if len(seeds)==2 else 'adoption', seeds=seeds,
                passed=all(checks.values()), checks=checks, mean_paired_deltas=means, paired_deltas=deltas,
                metrics=values, candidate_means={k: statistics.mean(v['values'][k] for v in values.values()) for k in means},
                candidate_sample_std={k: statistics.stdev(v['values'][k] for v in values.values()) for k in means},
                ddof=1, clinical_or_significance_claim=False)
