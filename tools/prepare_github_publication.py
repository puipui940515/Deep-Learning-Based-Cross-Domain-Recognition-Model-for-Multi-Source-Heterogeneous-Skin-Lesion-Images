"""Build a separate, auditable source publication without touching research history."""
from __future__ import annotations

import collections
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / '發佈包' / 'GitHub_2026-10-17'
TEXT_EXTENSIONS = {'.py', '.ps1', '.json', '.toml', '.yaml', '.yml', '.ini', '.cfg',
                   '.md', '.txt', '.html', '.css', '.js', '.mjs', '.cjs', '.ipynb',
                   '.csv', '.tsv', '.sh', '.bat', '.cmd'}
EXCLUDED_PARTS = {'Dataset', 'datasets', 'node_modules', '.git', '__pycache__', '.pytest_cache',
                  'checkpoints', 'results', 'smoke_results', 'logs', '_素材', 'models',
                  'UI訓練任務', '發佈包', '_備份', 'files_test', 'Claude outputs'}
SENSITIVE_JSON_KEYS = {'patient_id', 'lesion_id', 'image_path', 'record_id'}
SECRET_PATTERNS = [re.compile(r'gh[pousr]_[A-Za-z0-9]{30,}'),
                   re.compile(r'github_pat_[A-Za-z0-9_]{40,}'),
                   re.compile(r'sk-(?:proj-)?[A-Za-z0-9_-]{40,}'),
                   re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')]


def sensitive_json(value):
    if isinstance(value, dict):
        return any(k in SENSITIVE_JSON_KEYS and v not in (None, '', [], {}) or sensitive_json(v)
                   for k, v in value.items())
    if isinstance(value, list):
        return any(sensitive_json(item) for item in value)
    return False


def finalize_publication(export: Path):
    """Keep public indexes truthful when private assets were omitted."""
    registry_path = export/'實驗紀錄庫'/'registry.json'
    if registry_path.is_file():
        registry = json.loads(registry_path.read_text(encoding='utf-8-sig'))
        experiments = []
        for experiment in registry.get('experiments', []):
            kept = []
            for artifact in experiment.get('files', []):
                target = (registry_path.parent/artifact['library_path']).resolve()
                if target.is_relative_to(registry_path.parent.resolve()) and target.is_file():
                    artifact['size_bytes'] = target.stat().st_size
                    kept.append(artifact)
            if kept:
                experiment['files'] = kept
                experiment['file_count'] = len(kept)
                experiments.append(experiment)
        registry['experiments'] = experiments
        registry['experiment_count'] = len(experiments)
        registry['file_count'] = sum(len(item['files']) for item in experiments)
        registry['total_bytes'] = sum(item['size_bytes'] for exp in experiments for item in exp['files'])
        registry['notice'] = 'GitHub 程式發布版：僅列入已附上的彙總紀錄；資料、權重與未附檔案不列入連結。'
        registry['publication_filter'] = 'tools/prepare_github_publication.py'
        registry_path.write_text(json.dumps(registry,ensure_ascii=False,indent=2),encoding='utf-8')
    for path in export.rglob('*.ipynb'):
        notebook = json.loads(path.read_text(encoding='utf-8-sig'))
        for cell in notebook.get('cells', []):
            if cell.get('cell_type') == 'code':
                cell['outputs'] = []
                cell['execution_count'] = None
        path.write_text(json.dumps(notebook,ensure_ascii=False,indent=1),encoding='utf-8')
    downloads = export/'docs'/'資料集下載說明.md'
    if downloads.is_file():
        text = downloads.read_text(encoding='utf-8-sig')
        downloads.write_text(text.replace('](開發歷程/', '](../開發歷程/'),encoding='utf-8')


def exclusion(path: Path) -> str | None:
    parts = path.parts
    if any(p in EXCLUDED_PARTS or p.startswith(('.venv', '.ppt_', 'ppt_', '.chart-data')) for p in parts):
        return 'local data, dependency, checkpoint or build output'
    if parts[0] in {'重要資產', '環境檢查'}:
        return 'local model or machine assets'
    if path.name.startswith('.env') and path.name != '.env.example':
        return 'environment credentials'
    if path.name == 'probe_images.txt':
        return 'individual-image probe input list'
    if 'data' in parts and 'mapping' not in path.stem.lower():
        return 'per-image training data or manifest'
    if path.name in {'server_stdout.log', 'server_stderr.log'} or path.suffix in {'.log', '.lock', '.npz', '.npy'}:
        return 'runtime state or raw outputs'
    if path.suffix.lower() in {'.png', '.svg'}:
        if parts[0] == 'UI使用手冊_圖片版' and len(parts) == 2 and re.match(r'^\d\d_', path.name):
            return None
        if parts[0] in {'plots_export', 'experiment_plots_zh'}:
            return None
        return 'clinical screenshots, crops or generated preview assets'
    if path.suffix.lower() not in TEXT_EXTENSIONS and path.name not in {'.gitignore', '.gitattributes', 'LICENSE', 'NOTICE', 'COPYING'}:
        return 'binary, dataset image, archive or presentation'
    if path.suffix.lower() in {'.csv', '.tsv'} and not any(word in path.stem.lower() for word in
            ['mapping', 'summary', 'metrics', 'class_matrix', 'source_class', 'aggregate']):
        return 'individual-record table'
    if (ROOT/path).stat().st_size > 10 * 1024**2:
        return 'large generated artifact'
    if path.suffix.lower() == '.json' and 'reports' in parts:
        try:
            if sensitive_json(json.loads((ROOT/path).read_text(encoding='utf-8-sig'))):
                return 'report contains individual image or patient identifiers'
        except (ValueError, UnicodeError):
            return 'unreadable generated report'
    return None


def main():
    raw = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT)
    paths = sorted({Path(p.decode('utf-8')) for p in raw.split(b'\0') if p})
    included, excluded = [], []
    for path in paths:
        if not (ROOT/path).is_file():
            continue
        reason = exclusion(path)
        if reason:
            excluded.append({'path': path.as_posix(), 'reason': reason})
        else:
            if path.suffix.lower() not in {'.png', '.svg'}:
                text = (ROOT/path).read_text(encoding='utf-8-sig', errors='replace')
                if any(pattern.search(text) for pattern in SECRET_PATTERNS):
                    raise RuntimeError(f'Credential-like content detected; not exported: {path}')
            included.append(path)
    if EXPORT.exists():
        raise RuntimeError(f'Refusing to overwrite an existing export: {EXPORT}')
    EXPORT.mkdir(parents=True)
    for path in included:
        target = EXPORT/path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT/path, target)
    # Keep the project's existing dataset README intact, under an explicit name.
    downloads = EXPORT/'docs'/'資料集下載說明.md'
    downloads.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT/'README.md', downloads)
    # Generated publication README is supplied as a dedicated source document.
    shutil.copy2(ROOT/'tools'/'github_publication_README.md', EXPORT/'README.md')
    finalize_publication(EXPORT)
    manifest = [{'path': p.relative_to(EXPORT).as_posix(), 'bytes': p.stat().st_size,
                 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                for p in sorted(EXPORT.rglob('*')) if p.is_file()]
    report = {'source_commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'export_directory': str(EXPORT), 'file_count': len(manifest),
              'total_bytes': sum(item['bytes'] for item in manifest),
              'files': manifest, 'excluded': excluded}
    report_path = EXPORT.parent/'GitHub_2026-10-17_發布清單.json'
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'export':str(EXPORT),'files':len(manifest),'MiB':round(report['total_bytes']/1024**2,2),
                      'excluded_reasons':dict(collections.Counter(item['reason'] for item in excluded)),
                      'report':str(report_path)},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
