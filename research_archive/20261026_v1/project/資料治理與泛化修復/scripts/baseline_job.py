"""Standalone local job and progress/report wrapper around the accepted runner."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

from training_state import atomic_json, atomic_write, file_sha256, run_directory


def now():
    return datetime.now(timezone.utc).isoformat()


def read_gpu():
    try:
        result = subprocess.run(['nvidia-smi', '--query-gpu=timestamp,utilization.gpu,memory.used,memory.total,power.draw',
                                 '--format=csv,noheader'], capture_output=True, text=True, timeout=3)
        return result.stdout.strip() if result.returncode == 0 else 'unavailable'
    except (OSError, subprocess.TimeoutExpired):
        return 'unavailable'


def progress(root, spec, state, gpu_snapshot='not sampled'):
    lines = [f'SkinDetect 15-run baseline | {now()} | job={state["status"]}', '']
    table = [f'# SkinDetect 15 次訓練監控表', '', f'更新時間（UTC）：{now()}',
             f'工作狀態：{state["status"]}；Wrapper PID：{state.get("wrapper_pid", "N/A")}', '',
             f'GPU 即時取樣（時間、Util %、已用 MiB、總 MiB、功耗 W）：{gpu_snapshot}', '',
             'GPU 取樣是目前整張卡的瞬間狀態，不能當成整輪 GPU 運算耗時。',
             '訓練／驗證區段均含資料等待；純 GPU 運算與純資料載入尚未分開量測，明確標為 N/A。', '',
             '| 實驗 | Seed | 狀態 | Epoch | Train Loss | Robust | 本輪秒數 |',
             '|---|---:|---|---:|---:|---:|---:|']
    completed = 0
    for item in spec['profiles']:
        for seed in spec['seeds']:
            directory = root / 'runs' / item['id'] / f'regularized_seed{seed}'
            result_path = directory / 'result.json'
            row = None
            epoch_rows = {}
            latest = None
            index_path = directory / 'checkpoints/index.json'
            if index_path.is_file():
                index = json.loads(index_path.read_text(encoding='utf-8'))
                latest = index['generations'][0]
                for path in sorted(directory.glob('metrics_*.jsonl'), key=lambda p: p.stat().st_mtime_ns):
                    for line in path.read_text(encoding='utf-8').splitlines():
                        try:
                            candidate = json.loads(line)
                        except ValueError:  # A live writer may have an incomplete tail.
                            continue
                        if candidate['epoch'] < latest['epoch'] or candidate['checkpoint_sha256'] == latest['sha256']:
                            epoch_rows[candidate['epoch']] = candidate
                        if candidate['checkpoint_sha256'] == latest['sha256']:
                            row = candidate
            status = 'pending'
            if result_path.is_file():
                result = json.loads(result_path.read_text(encoding='utf-8'))
                status = result['status']
                completed += status == 'completed'
            elif directory.exists():
                status = 'running / no committed epoch yet' if latest is None else 'running'
            seed_status_path = directory.parent / 'suite.json'
            if seed_status_path.is_file():
                seed_state = json.loads(seed_status_path.read_text(encoding='utf-8'))['seeds'].get(str(seed), {})
                if seed_state.get('status') in ['running', 'failed']:
                    status = seed_state['status']
            text = f'{item["id"]} seed={seed}: {status}'
            if row:
                text += (f' epoch={row["epoch"]}/30 loss={row["train_loss"]:.6f}'
                         f' robust={row["robust_selection_score"]:.6f}'
                         f' best={row["best_score"]:.6f}@{row["best_epoch"]}'
                         f' epoch_seconds={row["epoch_seconds"]:.2f}')
            lines.append(text)
            table.append(f'| {item["id"]} | {seed} | {status} | '
                         + (f'{row["epoch"]}/30 | {row["train_loss"]:.6f} | {row["robust_selection_score"]:.6f} | {row["epoch_seconds"]:.2f} |'
                            if row else '— | — | — | — |'))
            if (directory / 'run_inputs.json').is_file():
                detail = [f'# {item["id"]} / Seed {seed} 監控表', '', f'更新時間（UTC）：{now()}',
                          f'狀態：{status}；正式資料 Train=18,919／Validation=3,611；Test 封存。',
                          f'本次 GPU 即時取樣：{gpu_snapshot}' if status == 'running' else 'GPU 即時值請見主工作 MONITORING.md。', '',
                          '各區段為牆鐘耗時。Train 含取資料、傳輸、前反向及更新；Evaluation 含訓練監測與三來源驗證。',
                          '純 GPU 運算／純資料載入未獨立量測，以下 N/A 不是 0 秒。正式選模以 result.json／完整 Checkpoint 為準。', '',
                          '| Epoch | Train Loss | Val Loss | Robust | HAM BA | BCN BA | PAD BA | Train 秒 | Eval 秒 | Checkpoint 秒 | 全輪秒 | GPU 運算秒 | 資料載入秒 |',
                          '|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|']
                for epoch, metrics in sorted(epoch_rows.items()):
                    validation = metrics['validation_by_source']
                    val_loss = sum(v['loss'] * v['samples'] for v in validation.values()) / sum(v['samples'] for v in validation.values())
                    detail.append(f'| {epoch} | {metrics["train_loss"]:.6f} | {val_loss:.6f} | {metrics["robust_selection_score"]:.6f} | '
                                  + ' | '.join(f'{validation[s]["balanced_accuracy"]:.6f}' for s in ['HAM10000', 'BCN20000', 'PAD-UFES-20'])
                                  + f' | {metrics["train_seconds"]:.2f} | {metrics["evaluation_seconds"]:.2f} | {metrics["checkpoint_seconds"]:.2f} | {metrics["epoch_seconds"]:.2f} | N/A | N/A |')
                atomic_write(directory / 'MONITORING.md', lambda f: f.write(('\n'.join(detail) + '\n').encode('utf-8')))
    lines += ['', f'Completed: {completed}/15', f'Logs/checkpoints: {root / "runs"}',
              f'After completion: {root / "reports"}',
              f'Safe epoch-boundary pause: create empty file {root / "STOP"}',
              'Resume the SAME job with --resume after removing STOP; no fresh restart on missing checkpoint.']
    atomic_write(root / 'PROGRESS.txt', lambda f: f.write(('\n'.join(lines) + '\n').encode('utf-8')))
    table += ['', f'完成：{completed}/15。各 Seed 目錄內 MONITORING.md 保存逐輪區段耗時與來源指標。']
    atomic_write(root / 'MONITORING.md', lambda f: f.write(('\n'.join(table) + '\n').encode('utf-8')))
    return completed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--suite', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    root = args.output_root.resolve()
    suite = args.suite.resolve()
    spec = json.loads(suite.read_text(encoding='utf-8-sig'))
    scripts = Path(__file__).parent
    contract = {'suite': str(suite), 'suite_sha256': file_sha256(suite),
                'sources': {p.name: file_sha256(p) for p in [Path(__file__), scripts / 'summarize_baseline.py',
                            scripts / 'suite_runner.py', scripts / 'run_formal_seeds.py',
                            scripts / 'train_regularized.py', scripts / 'training_state.py', scripts / 'model_profiles.py']}}
    with run_directory(root, args.resume):
        status_path = root / 'job.json'
        if args.resume:
            state = json.loads(status_path.read_text(encoding='utf-8'))
            if state['contract'] != contract or not (root / 'runs/models.json').is_file():
                raise RuntimeError('Job Resume contract/state mismatch; refusing fresh restart')
        else:
            state = {'job_id': uuid.uuid4().hex, 'created_utc': now(), 'contract': contract, 'attempts': []}
        attempt = {'id': uuid.uuid4().hex, 'started_utc': now(), 'resume': args.resume}
        state['attempts'].append(attempt)
        state.update(status='starting', wrapper_pid=os.getpid(), updated_utc=now())
        atomic_json(status_path, state)
        command = [sys.executable, '-u', str(scripts / 'run_formal_seeds.py'),
                   '--suite', str(suite), '--output-root', str(root / 'runs')]
        if args.resume:
            command.append('--resume')
        env = os.environ.copy()
        env.update(PYTHONUTF8='1', PYTHONUNBUFFERED='1', PYTHONDONTWRITEBYTECODE='1',
                   SKINDETECT_SUITE_STOP_FILE=str(root / 'STOP'))
        log_path = root / f'runner_{attempt["id"]}.log'
        try:
            with log_path.open('xb') as handle:
                child = subprocess.Popen(command, cwd=scripts.parents[1], env=env,
                                         stdout=handle, stderr=subprocess.STDOUT)
                state.update(status='running', child_pid=child.pid, runner_log=str(log_path))
                atomic_json(status_path, state)
                while True:
                    gpu = read_gpu()
                    state.update(completed_runs=progress(root, spec, state, gpu), gpu_snapshot=gpu, updated_utc=now())
                    atomic_json(status_path, state)
                    try:
                        code = child.wait(timeout=15)
                        break
                    except subprocess.TimeoutExpired:
                        pass
            state.update(status='summarizing' if code == 0 else 'failed', child_exit_code=code)
            atomic_json(status_path, state)
            from summarize_baseline import summarize
            report = summarize(suite, root / 'runs', root / 'reports')
            state.update(status='completed' if code == 0 and report['complete'] else 'paused' if code == 0 else 'failed',
                         completed_runs=report['completed_runs'])
        except BaseException:
            state.update(status='failed', error=traceback.format_exc())
            atomic_write(root / f'error_{attempt["id"]}.log', lambda f: f.write(state['error'].encode('utf-8')))
            raise
        finally:
            attempt['ended_utc'] = now()
            state['updated_utc'] = now()
            atomic_json(status_path, state)
            progress(root, spec, state, read_gpu())
        if state['status'] == 'failed':
            raise SystemExit(1)


if __name__ == '__main__':
    main()
