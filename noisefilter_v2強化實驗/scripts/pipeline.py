"""NoiseFilter v2 sequential pipeline; formal training starts only with --stage all."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import statistics
import subprocess
import sys
from collections import Counter
from pathlib import Path

from runtime_bootstrap import ensure_runtime

ensure_runtime()

from _common import EXP_ROOT, PROJECT, GOV_ROOT, load_config, read_manifest, sha256_file, write_json

OUT = EXP_ROOT / 'results'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def preflight(cfg):
    import torch
    import torchvision
    import sklearn
    import matplotlib
    manifest = PROJECT / cfg['manifest']
    rows = read_manifest(manifest)
    assert rows and {r['schema_version'] for r in rows} == {'skindetect-data-contract-v1.0'}
    assert {r['source'] for r in rows} == set(cfg['sources'])
    assert all(0 <= int(r['label']) < 7 for r in rows)
    missing = [r['image_path'] for r in rows if not (PROJECT / r['image_path']).is_file()]
    if missing:
        raise RuntimeError(f'{len(missing)} missing images; first: {missing[:3]}')
    assert read(GOV_ROOT / 'reports/pipeline_gate.json')['passed'], 'Data gate failed'
    counts = Counter((r['split'], r['source']) for r in rows)
    groups = {}
    for r in rows:
        group = (r['source'], r.get('split_group_id') or r['group_id'])
        if group in groups and groups[group] != r['split']:
            raise RuntimeError(f'Group split leakage: {group}')
        groups[group] = r['split']
    training = read(GOV_ROOT / 'config.json')['training']
    baselines = []
    for seed in cfg['seeds']:
        folder = PROJECT / cfg['baseline']['result_root'] / f'regularized_seed{seed}'
        assert (folder / 'best.pt').is_file(), f'Missing baseline seed {seed}'
        result = read(folder / 'result.json')
        assert result['regularization'] == training, 'Baseline training configuration has changed'
        assert result['train_samples'] == sum(n for (split, _), n in counts.items() if split == 'train')
        assert result['validation_samples'] == {s: counts['validation', s] for s in cfg['sources']}
        baselines.append(str(folder / 'result.json'))
    payload = {'passed': True, 'python': sys.executable, 'torch': torch.__version__,
               'cuda': torch.cuda.is_available(), 'manifest_sha256': sha256_file(manifest),
               'counts': {f'{split}/{source}': n for (split, source), n in counts.items()},
               'training': training, 'baseline_results': baselines,
               'scope': 'governance-v1, 7 classes; validation only; sealed test untouched',
               'limitation': 'Historical baseline has no immutable image-content snapshot; counts/config checked.'}
    write_json(OUT / 'preflight.json', payload, 'pipeline.py')
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)


def fingerprint(cfg):
    paths = [PROJECT / cfg['manifest'], EXP_ROOT / 'config.json', GOV_ROOT / 'config.json',
             GOV_ROOT / 'scripts/train_regularized.py']
    paths += sorted((EXP_ROOT / 'scripts').glob('*.py'))
    paths += sorted((EXP_ROOT / 'vendor/noisefilter_v2').glob('*.py'))
    paths += [PROJECT / cfg['baseline']['result_root'] / f'regularized_seed{s}/result.json' for s in cfg['seeds']]
    return hashlib.sha256(''.join(sha256_file(p) for p in paths).encode()).hexdigest()


def g1(cfg):
    result = read(OUT / 'N0/seed17/result.json')
    assert not result['smoke_test']
    baseline = read(PROJECT / cfg['baseline']['seed_variance'])['candidates']['governance_v1']['summary']['HAM10000_balanced_accuracy']
    threshold = baseline['values_by_seed']['17'] - baseline['sample_standard_deviation']
    actual = result['summary']['HAM10000_balanced_accuracy']
    passed = actual >= threshold
    write_json(OUT / 'G1_pilot.json', {'passed': passed, 'threshold': threshold, 'actual': actual}, 'pipeline.py')
    if not passed:
        raise RuntimeError(f'G1 failed: HAM BA {actual:.4f} < {threshold:.4f}; remaining training stopped')


def summarize(cfg):
    records, histories = [], []
    for seed in cfg['seeds']:
        for kind, path in [('baseline', PROJECT / cfg['baseline']['result_root'] / f'regularized_seed{seed}/result.json'),
                           ('N0', OUT / f'N0/seed{seed}/result.json')]:
            if not path.exists():
                continue
            result = read(path)
            if result.get('smoke_test'):
                continue
            best = result['best']
            for source, metrics in best['validation_by_source'].items():
                records.append({'model': kind, 'seed': seed, 'source': source, 'epoch': best['epoch'],
                                **{k: metrics[k] for k in ['balanced_accuracy', 'macro_f1', 'accuracy', 'ece']}})
            histories.append((kind, seed, result['history']))
    report_dir = OUT / 'comparison'
    report_dir.mkdir(parents=True, exist_ok=True)
    with (report_dir / 'validation_comparison.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0]))
        writer.writeheader(); writer.writerows(records)
    baseline_summary = read(PROJECT / cfg['baseline']['seed_variance'])['candidates']['governance_v1']['summary']
    nf = [read(OUT / f'N0/seed{s}/result.json') for s in cfg['seeds'] if (OUT / f'N0/seed{s}/result.json').exists()]
    comparisons = {}
    if len(nf) == len(cfg['seeds']):
        for metric in cfg['gates']['G2_formal']['metrics']:
            values = [r['summary'][metric] for r in nf]
            avg, std = statistics.mean(values), statistics.stdev(values)
            b = baseline_summary[metric]
            delta = avg - b['mean']
            threshold = 2 * max(std, b['sample_standard_deviation'])
            comparisons[metric] = {'nf2_mean': avg, 'nf2_sample_std': std, 'baseline_mean': b['mean'],
                                   'delta': delta, 'two_s_threshold': threshold,
                                   'improvement_exceeds_two_s': delta > threshold}
    write_json(report_dir / 'summary.json', {'completed_N0_seeds': [r['seed'] for r in nf],
               'G2': comparisons, 'note': '2s is a project heuristic, not a significance test.'}, 'pipeline.py')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.5))
    for ax, source in zip(axes, cfg['sources']):
        for kind, seed, hist in histories:
            ax.plot([h['epoch'] for h in hist],
                    [100*h['validation_by_source'][source]['balanced_accuracy'] for h in hist],
                    color='tab:blue' if kind == 'baseline' else 'tab:orange',
                    linestyle={17:'-',42:'--',2026:':'}[seed],
                    label=f'{"原始基線" if kind == "baseline" else "濾鏡第二版"} 種子{seed}')
        ax.set(title=source, xlabel='訓練輪次', ylabel='平衡準確率（%）')
        ax.grid(alpha=.2); ax.legend(fontsize=7)
    fig.tight_layout(); fig.savefig(report_dir / '三來源驗證曲線.png', dpi=160); plt.close(fig)
    corruption_rows = []
    for path in sorted((OUT / 'corruption_eval').glob('*.json')):
        data = read(path)
        if data.get('smoke_test'):
            continue
        for source, items in data['results'].items():
            for condition, metrics in items.items():
                if isinstance(metrics, dict):
                    corruption_rows.append({'file': path.name, 'model': data['kind'], 'source': source,
                                            'condition': condition, **metrics})
    if corruption_rows:
        with (report_dir / 'corruption_comparison.csv').open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(corruption_rows[0]))
            writer.writeheader(); writer.writerows(corruption_rows)
    print(f'Reports: {report_dir}', flush=True)


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', choices=['check', 'prepare', 'all', 'evaluate', 'report'], default='check')
    ap.add_argument('--num-workers', type=int, default=0)
    args = ap.parse_args()
    cfg = load_config()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.stage == 'report':
        summarize(cfg); return
    preflight(cfg)
    if args.stage == 'check':
        subprocess.run([sys.executable, '-m', 'pytest', str(EXP_ROOT / 'tests'), '-q'], cwd=PROJECT, check=True)
        return
    identity = fingerprint(cfg)
    journal = OUT / 'pipeline_state.json'
    state = read(journal) if journal.exists() else {'fingerprint': identity, 'completed': []}
    if state['fingerprint'] != identity:
        raise RuntimeError('Pipeline input/code changed; review previous results before starting a new experiment.')
    lock = OUT / 'pipeline.lock'
    try:
        lock_fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise RuntimeError('Pipeline already running or interrupted. Check PID in results/pipeline.lock before removing it.')
    os.write(lock_fd, str(os.getpid()).encode()); os.close(lock_fd)
    logdir = OUT / 'logs'; logdir.mkdir(exist_ok=True)

    def step(name, script, *argv):
        if name in state['completed']:
            print(f'SKIP completed: {name}', flush=True); return
        state['current'] = name
        write_json(journal, state, 'pipeline.py')
        command = [sys.executable, '-u', str(EXP_ROOT / 'scripts' / script), *map(str, argv)]
        print(f'\nSTART {name}: {subprocess.list2cmdline(command)}', flush=True)
        with (logdir / f'{name}.log').open('a', encoding='utf-8') as log:
            proc = subprocess.Popen(command, cwd=PROJECT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, encoding='utf-8', errors='replace',
                                    env={**os.environ, 'PYTHONIOENCODING':'utf-8'})
            try:
                for line in proc.stdout:
                    print(line, end='', flush=True); log.write(line); log.flush()
                code = proc.wait()
            except BaseException:
                proc.terminate(); proc.wait(); raise
        if code:
            raise RuntimeError(f'{name} stopped (exit {code}); see {logdir / (name + ".log")}')
        state['completed'].append(name)
        write_json(journal, state, 'pipeline.py')

    try:
        if args.stage in ['prepare', 'all']:
            step('calibration', 'calibrate.py', '--num-workers', args.num_workers)
            step('G0', 'source_probe_input.py', '--feature', 'convnext', '--per-source', 600,
                 '--num-workers', args.num_workers)
            assert read(OUT / 'G0_input_probe_convnext.json')['passed'], 'G0 failed'
        if args.stage == 'all':
            for seed in cfg['seeds']:
                step(f'N0_seed{seed}', 'train_nf2.py', '--run', 'N0', '--seed', seed,
                     '--num-workers', args.num_workers, '--resume')
                if seed == 17:
                    g1(cfg)
            summarize(cfg)
        if args.stage in ['all', 'evaluate']:
            for seed in cfg['seeds']:
                for kind in ['baseline', 'nf2']:
                    ckpt = (PROJECT / cfg['baseline']['result_root'] / f'regularized_seed{seed}/best.pt'
                            if kind == 'baseline' else OUT / f'N0/seed{seed}/best.pt')
                    assert ckpt.exists(), f'Missing {ckpt}'
                    step(f'eval_{kind}_{seed}', 'eval_corruptions.py', '--kind', kind, '--run', 'N0',
                         '--checkpoint', ckpt, '--num-workers', args.num_workers)
            summarize(cfg)
        state['current'] = None
        state.pop('error', None)
    except BaseException as exc:
        state['error'] = str(exc)
        raise
    finally:
        write_json(journal, state, 'pipeline.py')
        lock.unlink()


if __name__ == '__main__':
    main()
