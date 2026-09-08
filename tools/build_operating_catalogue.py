#!/usr/bin/env python3
"""Derive stable reference identifiers from existing public BOCG artifacts."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE_PATH = 'reference/operating-catalogue.v1.json'
CONTRACT_VERSION = '1.0.0'

def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()

def reference_id(kind, division, label=''):
    if kind == 'division':
        return 'division:' + division
    digest = hashlib.sha256(canonical_bytes([kind, division, label])).hexdigest()[:24]
    return kind + ':' + division + ':' + digest

def build_catalogue(root=ROOT, matrix_path='live-run-20260826/matrix.json'):
    raw = (root / matrix_path).read_bytes()
    matrix = json.loads(raw)
    definitions = []
    keys = matrix['division_keys']
    if len(set(keys)) != len(keys) or set(keys) != {r['division_key'] for r in matrix['rows']}:
        raise ValueError('matrix division keys are inconsistent')
    for row in sorted(matrix['rows'], key=lambda r: r['division_key']):
        division = row['division_key']
        definitions.append({'reference_id': reference_id('division', division), 'kind': 'division', 'division_key': division, 'label': division, 'aliases': sorted(set(row['names'])), 'basis': 'model_consensus_prior'})
        for label in sorted(set(row['seat_pool']['functions'])):
            definitions.append({'reference_id': reference_id('function', division, label), 'kind': 'function', 'division_key': division, 'label': label, 'basis': 'model_consensus_prior'})
        tasks = {}
        for task in row['seat_pool']['terminality_tasks']:
            label = task['canon']
            if label in tasks:
                raise ValueError('duplicate canonical task in a division')
            tasks[label] = task
        for label, task in sorted(tasks.items()):
            definitions.append({'reference_id': reference_id('task', division, label), 'kind': 'task', 'division_key': division, 'label': label, 'basis': 'model_consensus_prior', 'task': task})
    sources = [{'path': matrix_path, 'sha256': hashlib.sha256(raw).hexdigest()}]
    for path in sorted((root / 'cells').glob('*.json')):
        raw = path.read_bytes(); cell = json.loads(raw)
        if cell['status'] != 'CURATED':
            continue
        if cell['division_key'] not in keys:
            raise ValueError('control point names an unknown division')
        definitions.append({'reference_id': 'control_point:' + cell['cell_id'], 'kind': 'control_point', 'division_key': cell['division_key'], 'label': cell['control_point'], 'basis': 'curated_public_control', 'cell': cell})
        sources.append({'path': path.relative_to(root).as_posix(), 'sha256': hashlib.sha256(raw).hexdigest()})
    definitions.sort(key=lambda r: r['reference_id'])
    if len({r['reference_id'] for r in definitions}) != len(definitions):
        raise ValueError('reference identifier collision')
    result = {'schema': 'bocg.operating-catalogue/v1', 'contract_version': CONTRACT_VERSION, 'identity_rule': 'division key; otherwise SHA-256 of exact kind, division key and source canonical label, first 24 hex characters; control points retain cell_id', 'institution_instances': False, 'sources': sources, 'definitions': definitions}
    result['catalogue_sha256'] = hashlib.sha256(canonical_bytes(result)).hexdigest()
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    destination = ROOT / CATALOGUE_PATH
    expected = json.dumps(build_catalogue(), indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if not destination.exists() or destination.read_text() != expected:
            raise SystemExit('operating catalogue is stale; regenerate before release')
        print('Operating catalogue reproduces exactly.')
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(expected)
        print('Wrote', CATALOGUE_PATH)

if __name__ == '__main__':
    main()
