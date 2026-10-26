"""Fail closed if the accepted baseline configuration/code/data has changed."""
import argparse
import json
from pathlib import Path

from training_state import file_sha256

parser = argparse.ArgumentParser()
parser.add_argument('--record', type=Path, required=True)
args = parser.parse_args()
record = json.loads(args.record.read_text(encoding='utf-8'))
if record.get('passed') is not True or len(record['gpu_acceptance']['cases']) != 5:
    raise RuntimeError('All five GPU/Resume acceptance cases must pass before launch')
for case in record['gpu_acceptance']['cases']:
    if case['passed'] is not True:
        raise RuntimeError('Failed GPU acceptance case')
for path, expected in record['frozen_hashes'].items():
    if file_sha256(path) != expected:
        raise RuntimeError(f'Frozen baseline input changed: {path}')
print('PASS: accepted baseline code, five configs, weights, and immutable manifest fingerprints unchanged')
