"""Read committed training results; never load a model, images, or Test data."""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import statistics
from pathlib import Path

from training_state import atomic_json, atomic_write, file_sha256


def summarize(suite_path, runs, destination):
    spec = json.loads(Path(suite_path).read_text(encoding='utf-8-sig'))
    profiles = {p['id']: json.loads((Path(suite_path).parent / p['config']).read_text(encoding='utf-8-sig'))
                for p in spec['profiles']}
    records, missing = [], []
    classes = next(iter(profiles.values()))['class_names']
    for identifier, config in profiles.items():
        for seed in spec['seeds']:
            directory = Path(runs) / identifier / f'regularized_seed{seed}'
            path = directory / 'result.json'
            if not path.is_file():
                missing.append(f'{identifier}/seed{seed}')
                continue
            result = json.loads(path.read_text(encoding='utf-8'))
            inputs = json.loads((directory / 'run_inputs.json').read_text(encoding='utf-8'))
            if (result['seed'] != seed or result['test_used'] or inputs['test_used']
                    or result['experiment_id'] != identifier
                    or result['regularization'] != config['training']):
                raise RuntimeError(f'Result identity or formal settings differ: {path}')
            best = result['best']
            history_best = max(result['history'], key=lambda row: row['robust_selection_score'])
            if best['epoch'] != history_best['epoch']:
                raise RuntimeError('Best epoch is not the first maximum Validation Robust Score')
            row = dict(experiment=identifier, model=config['training']['model'],
                       initialization=config['training']['initialization'], seed=seed,
                       run_id=result['run_id'], status=result['status'], best_epoch=best['epoch'],
                       epochs_completed=result['epochs_completed'],
                       robust_score=best['robust_selection_score'], train_loss=best['train_loss'],
                       train_monitor_loss=best['train_monitor']['loss'],
                       elapsed_seconds=result['elapsed_seconds'], stop_reason=result['stop_reason'],
                       best_bad_epochs=best['bad_epochs'],
                       final_bad_epochs=result['history'][-1]['bad_epochs'],
                       config_sha256=file_sha256(Path(suite_path).parent / f'{identifier}.json'),
                       best_model=str(directory / 'best.pt'),
                       best_model_sha256=file_sha256(directory / 'best.pt'),
                       checkpoint_index=str(directory / 'checkpoints/index.json'),
                       result_file=str(path), run_inputs=str(directory / 'run_inputs.json'),
                       test_used=False)
            index = json.loads((directory / 'checkpoints/index.json').read_text(encoding='utf-8'))
            for i, descriptor in enumerate(index['generations']):
                label = 'latest' if i == 0 else 'previous'
                row[f'{label}_checkpoint'] = str(directory / 'checkpoints' / descriptor['file'])
                row[f'{label}_checkpoint_sha256'] = descriptor['sha256']
                row[f'{label}_checkpoint_epoch'] = descriptor['epoch']
            total_n, total_loss = 0, 0.0
            pooled = [[0] * len(classes) for _ in classes]
            for source, values in best['validation_by_source'].items():
                row[f'{source}.BA'] = values['balanced_accuracy']
                row[f'{source}.Macro_F1'] = values['macro_f1']
                row[f'{source}.Accuracy'] = values['accuracy']
                row[f'{source}.Loss'] = values['loss']
                cm = values['confusion_matrix']
                supported = values['metric_labels']
                for k, name in enumerate(classes):
                    denominator = sum(cm[k])
                    row[f'{source}.Recall.{name}'] = cm[k][k] / denominator if k in supported and denominator else None
                total_n += values['samples']
                total_loss += values['loss'] * values['samples']
                for i in range(len(classes)):
                    for j in range(len(classes)):
                        pooled[i][j] += cm[i][j]
            row['Validation.Loss'] = total_loss / total_n
            row['Validation.Accuracy'] = sum(pooled[i][i] for i in range(len(classes))) / total_n
            f1s = []
            for i, name in enumerate(classes):
                tp = pooled[i][i]
                support, predicted = sum(pooled[i]), sum(r[i] for r in pooled)
                row[f'Validation.Recall.{name}'] = tp / support if support else None
                if support:
                    f1s.append(2 * tp / (support + predicted))
            row['Validation.Macro_F1'] = statistics.mean(f1s)
            records.append(row)
            if result['status'] != 'completed':
                missing.append(f'{identifier}/seed{seed}: {result["status"]}')
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    metric_keys = ['robust_score', 'best_epoch', 'train_loss', 'train_monitor_loss', 'elapsed_seconds']
    metric_keys += sorted({k for row in records for k in row if k.startswith('Validation.') or any(k.startswith(s + '.') for s in next(iter(profiles.values()))['sources'])})
    groups = []
    for identifier in profiles:
        group = [r for r in records if r['experiment'] == identifier and r['status'] == 'completed']
        summary = {'experiment': identifier, 'n_completed': len(group), 'metrics': {}}
        for key in metric_keys:
            values = [r[key] for r in group if isinstance(r.get(key), (int, float))]
            if values:
                summary['metrics'][key] = dict(n=len(values), mean=statistics.mean(values),
                                               sample_std=statistics.stdev(values) if len(values) >= 2 else None)
        groups.append(summary)
    differences = []
    for architecture in ['resnet18', 'convnextv2_tiny']:
        pairs = []
        for seed in spec['seeds']:
            arms = {r['initialization']: r for r in records if r['model'] == architecture and r['seed'] == seed and r['status'] == 'completed'}
            if set(arms) == {'random', 'imagenet'}:
                pairs.append({'seed': seed, 'differences': {key: arms['imagenet'][key] - arms['random'][key]
                              for key in metric_keys if all(isinstance(arms[a].get(key), (int, float)) for a in arms)}})
        aggregate = {}
        for key in metric_keys:
            values = [p['differences'][key] for p in pairs if key in p['differences']]
            if values:
                aggregate[key] = dict(n=len(values), mean=statistics.mean(values),
                                     sample_std=statistics.stdev(values) if len(values) >= 2 else None)
        differences.append(dict(model=architecture, direction='ImageNet minus Random', paired_seeds=pairs, metrics=aggregate))
    report = dict(complete=not missing and len(records) == 15, expected_runs=15,
                  completed_runs=sum(r['status'] == 'completed' for r in records), missing_or_paused=missing,
                  selection='0.5 * mean(HAM BA, BCN BA, PAD BA) + 0.5 * min(HAM BA, BCN BA, PAD BA)',
                  definitions={'BA': 'Mean recall over source-supported labels; PAD excludes DF and VASC',
                               'Validation': 'Pooled confusion matrices of the three Validation sources; sample-weighted loss',
                               'std': 'Sample standard deviation, ddof=1; three independent seeds',
                               'loss': 'At the selected best epoch; V2 training loss uses MixUp and label smoothing',
                               'elapsed_seconds': 'Cumulative training loop including Validation/checkpoint time; excludes model setup and downtime between attempts',
                               'comparison': 'Descriptive paired seed differences; scores in [0,1], multiply differences by 100 for percentage points'},
                  runs=records, groups=groups, initialization_differences=differences, test_used=False)
    atomic_json(destination / 'baseline_results.json', report)
    columns = list(dict.fromkeys(key for row in records for key in row))
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    writer.writerows(records)
    atomic_write(destination / 'baseline_runs.csv', lambda f: f.write(buffer.getvalue().encode('utf-8-sig')))
    lines = [f'# SkinDetect 第一輪基線：{report["completed_runs"]}/15 完成', '',
             'Validation Robust Score 選模；Test 封存。標準差為樣本標準差（ddof=1）。', '',
             '| 實驗 | 完成 Seeds | Robust Score 平均 ± SD |', '|---|---:|---:|']
    for group in groups:
        value = group['metrics'].get('robust_score')
        formatted = '尚無完成結果' if not value else f'{value["mean"]:.6f} ± {value["sample_std"]:.6f}' if value['sample_std'] is not None else f'{value["mean"]:.6f}（僅一個 Seed）'
        lines.append(f'| {group["experiment"]} | {group["n_completed"]} | {formatted} |')
    lines += ['', '初始化差異（ImageNet − Random，同 Seed 配對）：']
    for difference in differences:
        value = difference['metrics'].get('robust_score')
        if value:
            lines.append(f'- {difference["model"]}：Robust Score 平均差 {100 * value["mean"]:+.3f} 個百分點，n={value["n"]}。')
    lines += ['', '完整各類 Recall、來源 BA／Macro-F1／Accuracy／Loss、時間、停止原因與權重路徑見同目錄 CSV／JSON。',
              '跨架構沿用各自基線前處理與優化設定；初始化比較僅在同架構內進行。',
              '限制：Epoch 級 Resume 保存主要 RNG／抽樣狀態；persistent workers 的增強 RNG 不保證逐位元重播。']
    atomic_write(destination / 'baseline_summary.md', lambda f: f.write(('\n'.join(lines) + '\n').encode('utf-8')))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--suite', type=Path, required=True)
    parser.add_argument('--runs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.suite, args.runs, args.output)
    print(json.dumps({k: result[k] for k in ['complete', 'completed_runs', 'missing_or_paused']}, ensure_ascii=False))
