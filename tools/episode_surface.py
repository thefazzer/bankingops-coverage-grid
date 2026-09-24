#!/usr/bin/env python3
"""SPEC-08 §3 episode-surface depth rule and release-bound reference checks.

A consumer computes an Episode's evidence depth from its touchpoints. The rule
is small enough to restate: the deepest touchpoint whose mapping status is
ratified (RATIFIED_MAPPING or QUALIFIED_MAPPING) sets `evidence_depth`; the
deepest PROPOSED or PENDING touchpoint sets `candidate_depth`. Rejected and
deferred touchpoints stay on the record and set neither. Candidates never raise
evidence depth. No touchpoints, or no ratified touchpoint, is depth `none`.

    python3 tools/episode_surface.py specs/fixtures/episode-surface-synthetic.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPTH_ORDER = ('none', 'division', 'function_concept', 'task_concept', 'terminal_task', 'control_point')
RATIFIED = frozenset({'RATIFIED_MAPPING', 'QUALIFIED_MAPPING'})
CANDIDATE = frozenset({'PROPOSED', 'PENDING'})
ID_FIELD_FOR_DEPTH = {
    'function_concept': 'function_concept_id',
    'task_concept': 'task_concept_id',
    'terminal_task': 'task_reference_id',
    'control_point': 'control_point_id',
}


def depth_rank(depth: str) -> int:
    return DEPTH_ORDER.index(depth)


def deepest(touchpoints: list[dict], statuses: frozenset[str]) -> str:
    best = 'none'
    for point in touchpoints:
        if point.get('mapping_status') in statuses and depth_rank(point['depth']) > depth_rank(best):
            best = point['depth']
    return best


def evidence_depth(surface: dict) -> str:
    return deepest(surface.get('touchpoints') or [], RATIFIED)


def candidate_depth(surface: dict) -> str:
    return deepest(surface.get('touchpoints') or [], CANDIDATE)


def surface_problems(surface: dict, *, root: Path = ROOT) -> list[str]:
    """Structural problems beyond JSON Schema: depth rule and release-bound identifiers."""
    problems: list[str] = []
    concepts = json.loads((root / 'reference/task-concepts.v1.json').read_text(encoding='utf-8'))
    catalogue = json.loads((root / 'reference/operating-catalogue.v1.json').read_text(encoding='utf-8'))
    concept_ids = {c['concept_id']: c for c in concepts['concepts']}
    definitions = {d['reference_id']: d for d in catalogue['definitions']}
    divisions = {d['division_key'] for d in catalogue['definitions'] if d['kind'] == 'division'}
    cells = {p.stem for p in (root / 'cells').glob('*.json')}
    release = surface.get('bocg_release') or {}
    if release.get('task_concepts_sha256') != concepts['task_concepts_sha256']:
        problems.append('surface is bound to a different task-concepts digest')
    for index, point in enumerate(surface.get('touchpoints') or []):
        where = f'touchpoint {index}'
        division = point.get('division_key')
        if division not in divisions:
            problems.append(f'{where}: unknown division {division!r}')
        depth = point.get('depth')
        field = ID_FIELD_FOR_DEPTH.get(depth)
        if field and not point.get(field):
            problems.append(f'{where}: depth {depth} needs {field}')
        for key, kind in (('function_concept_id', 'function_concept'), ('task_concept_id', 'task_concept')):
            value = point.get(key)
            if value is None:
                continue
            concept = concept_ids.get(value)
            if concept is None:
                problems.append(f'{where}: {key} is not a released concept')
            elif concept['kind'] != kind or concept['division_key'] != division:
                problems.append(f'{where}: {key} belongs to another kind or division')
        task_ref = point.get('task_reference_id')
        if task_ref is not None:
            definition = definitions.get(task_ref)
            if definition is None or definition['kind'] != 'task' or definition['division_key'] != division:
                problems.append(f'{where}: task_reference_id is not a released task of the division')
            elif point.get('task_concept_id') in concept_ids:
                if task_ref not in concept_ids[point['task_concept_id']]['members']:
                    problems.append(f'{where}: task_reference_id is not a member of task_concept_id')
        cell = point.get('control_point_id')
        if cell is not None:
            if cell not in cells:
                problems.append(f'{where}: control_point_id is not a released cell')
            else:
                cell_division = json.loads((root / 'cells' / f'{cell}.json').read_text(encoding='utf-8')).get('division_key')
                if cell_division in divisions and cell_division != division:
                    problems.append(f'{where}: control_point_id belongs to another division')
    if surface.get('evidence_depth') != evidence_depth(surface):
        problems.append('evidence_depth does not follow the depth rule')
    if surface.get('candidate_depth') != candidate_depth(surface):
        problems.append('candidate_depth does not follow the depth rule')
    return problems


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    surface = json.loads(Path(argv[1]).read_text(encoding='utf-8'))
    problems = surface_problems(surface)
    for problem in problems:
        print('FAIL', problem)
    if not problems:
        print(f"evidence_depth={evidence_depth(surface)} candidate_depth={candidate_depth(surface)}")
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
