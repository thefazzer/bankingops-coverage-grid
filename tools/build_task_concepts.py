#!/usr/bin/env python3
"""Derive task concepts and function concepts from the released operating catalogue.

A concept groups released function or task definitions of ONE division that
denote the same operational work. Two provenance classes exist and are never
mixed inside a division:

  AUTO      machine_clustered: deterministic average-linkage clustering over
            Jaccard similarity of canonical label tokens. Nobody has read these
            groups. They are a machine prior, not a curation.
  REVIEWED  argued_merge / standalone_under_review: every merge in the division
            is argued in reference/task-concept-rulings.yaml with a named
            reviewer, a date and a rationale per alias. Definitions the ruling
            does not merge stand alone.

Concepts never cross a division. Concept identity follows SPEC-06: SHA-256 of
the exact kind, division key and concept label, first 24 hex characters. A
stable identifier does not prove unchanged membership: consumers compare the
per-concept definition digest.

    python3 tools/build_task_concepts.py            # write reference/task-concepts.v1.json
    python3 tools/build_task_concepts.py --check    # fail if the file is stale
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from itertools import combinations
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'bocg'))
from bocg.canon import canon_name  # noqa: E402

CATALOGUE_PATH = 'reference/operating-catalogue.v1.json'
RULINGS_PATH = 'reference/task-concept-rulings.yaml'
OUTPUT_PATH = 'reference/task-concepts.v1.json'
CONTRACT_VERSION = '1.0.0'
SCHEMA_ID = 'bocg.task-concepts/v1'
RULINGS_SCHEMA_ID = 'bocg.task-concept-rulings/v1'

# Machine clustering parameters. Changing any of them changes every AUTO
# concept; the method block in the output records them so a consumer can tell.
SIMILARITY_THRESHOLD = 0.4
KINDS = {'function': 'function_concept', 'task': 'task_concept'}
STOPLIST = frozenset({
    'a', 'an', 'the', 'to', 'for', 'of', 'and', 'or', 'per', 'with', 'under', 'against',
    'within', 'before', 'after', 'at', 'on', 'in', 'by', 'from', 'into', 'as', 's', 'its',
    'it', 'each', 'all', 'any', 'correct', 'required', 'prescribed', 'applicable',
    'appropriate', 'daily', 'weekly', 'monthly', 'day', 'end', 'new', 'existing', 'that',
    'is', 'are', 'be', 'via', 'versus', 'vs', 'using', 'use', 'their', 'client', 'house',
    'regulatory',
})
VARIANTS = {
    'calculate': 'compute', 'calculation': 'compute', 'computation': 'compute',
    'recompute': 'compute', 'computing': 'compute', 'reconciliation': 'reconcile',
    'settlement': 'settle', 'confirmation': 'confirm', 'reporting': 'report',
    'processing': 'process', 'allocation': 'allocate', 'matching': 'match',
    'issuance': 'issue', 'margining': 'margin', 'valuation': 'value',
    'determination': 'determine', 'submission': 'submit', 'execution': 'execute',
    'generation': 'generate', 'validation': 'validate', 'verification': 'verify',
    'investigation': 'investigate', 'resolution': 'resolve', 'pricing': 'price',
    'hedging': 'hedge', 'marking': 'mark', 'booking': 'book', 'clearing': 'clear',
    'funding': 'fund', 'lending': 'lend', 'borrowing': 'borrow', 'trading': 'trade',
    'monitoring': 'monitor', 'derivatif': 'derivative', 'derivatives': 'derivative',
    'securities': 'security',
}
BASIS_AUTO = 'machine_clustered'
BASIS_MERGE = 'argued_merge'
BASIS_STANDALONE = 'standalone_under_review'


def canonical_bytes(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def concept_id(kind: str, division: str, label: str) -> str:
    digest = sha256_bytes(canonical_bytes([kind, division, label]))[:24]
    return kind + ':' + division + ':' + digest


def tokens(label: str) -> frozenset[str]:
    out = set()
    for word in canon_name(label).split():
        if word.isdigit():
            continue
        word = VARIANTS.get(word, word)
        if word in STOPLIST:
            continue
        out.add(word)
    return frozenset(out)


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def machine_clusters(labels: list[str]) -> list[list[str]]:
    """Average-linkage agglomerative clustering; deterministic for a given label set."""
    labels = sorted(set(labels))
    toks = {label: tokens(label) for label in labels}
    clusters = [[label] for label in labels]
    while True:
        best = None
        for i, j in combinations(range(len(clusters)), 2):
            sims = [jaccard(toks[a], toks[b]) for a in clusters[i] for b in clusters[j]]
            score = sum(sims) / len(sims)
            if score >= SIMILARITY_THRESHOLD and (best is None or score > best[0]):
                best = (score, i, j)
        if best is None:
            break
        _, i, j = best
        clusters[i] = sorted(clusters[i] + clusters[j])
        del clusters[j]
    return sorted(clusters)


def representative(labels: list[str]) -> str:
    """Shortest member label, ties broken alphabetically; never an invented label."""
    return sorted(labels, key=lambda s: (len(s), s))[0]


def mean_similarity(label: str, others: list[str]) -> float:
    if not others:
        return 1.0
    t = tokens(label)
    return sum(jaccard(t, tokens(o)) for o in others) / len(others)


def _definition(entry: dict, members: list[dict], aliases: list[dict]) -> dict:
    value = dict(entry)
    value['members'] = [m['reference_id'] for m in members]
    value['member_labels'] = [m['label'] for m in members]
    value['aliases'] = aliases
    value['definition_sha256'] = sha256_bytes(canonical_bytes({k: v for k, v in value.items() if k != 'definition_sha256'}))
    return value


def load_rulings(root: Path) -> dict:
    raw = yaml.safe_load((root / RULINGS_PATH).read_text(encoding='utf-8'))
    if not isinstance(raw, dict) or raw.get('schema') != RULINGS_SCHEMA_ID:
        raise ValueError('task-concept rulings file has the wrong schema')
    seen = set()
    for ruling in raw.get('rulings') or []:
        for field in ('division_key', 'review_status', 'ruled_by', 'ruled_at', 'basis', 'concepts'):
            if not ruling.get(field):
                raise ValueError(f'ruling lacks {field}')
        if ruling['review_status'] != 'REVIEWED':
            raise ValueError('a ruling can only assign REVIEWED status')
        if ruling['division_key'] in seen:
            raise ValueError('two rulings name the same division')
        seen.add(ruling['division_key'])
    return raw


def build_task_concepts(root: Path = ROOT) -> dict:
    catalogue_raw = (root / CATALOGUE_PATH).read_bytes()
    catalogue = json.loads(catalogue_raw)
    rulings_raw = (root / RULINGS_PATH).read_bytes()
    rulings = load_rulings(root)
    ruling_by_division = {r['division_key']: r for r in rulings.get('rulings') or []}

    definitions = catalogue['definitions']
    division_keys = sorted(d['division_key'] for d in definitions if d['kind'] == 'division')
    for key in ruling_by_division:
        if key not in division_keys:
            raise ValueError(f'ruling names an unknown division: {key}')
    by_division: dict[str, dict[str, dict[str, dict]]] = {k: {'function': {}, 'task': {}} for k in division_keys}
    for d in definitions:
        if d['kind'] in KINDS:
            if d['label'] in by_division[d['division_key']][d['kind']]:
                raise ValueError('duplicate label inside a division')
            by_division[d['division_key']][d['kind']][d['label']] = d

    concepts: list[dict] = []
    division_rows: list[dict] = []
    for division in division_keys:
        ruling = ruling_by_division.get(division)
        counts = {'functions': len(by_division[division]['function']), 'tasks': len(by_division[division]['task']),
                  'function_concepts': 0, 'task_concepts': 0, 'aliases': 0, 'argued_merges': 0}
        if ruling is None:
            review_status, basis = 'AUTO', BASIS_AUTO
            for kind, concept_kind in KINDS.items():
                pool = by_division[division][kind]
                for group in machine_clusters(list(pool)):
                    label = representative(group)
                    members = [pool[m] for m in group]
                    aliases = [{
                        'reference_id': pool[m]['reference_id'], 'label': m,
                        'rationale': f'machine-clustered: mean Jaccard {mean_similarity(m, [o for o in group if o != m]):.2f} to the other members; unread by any human',
                    } for m in group if m != label]
                    concepts.append(_definition({
                        'concept_id': concept_id(concept_kind, division, label), 'kind': concept_kind,
                        'division_key': division, 'label': label, 'label_source': 'member',
                        'review_status': review_status, 'basis': BASIS_AUTO, 'rationale': None,
                    }, members, aliases))
                    counts[concept_kind + 's'] += 1
                    counts['aliases'] += len(aliases)
        else:
            review_status, basis = 'REVIEWED', BASIS_MERGE
            consumed: dict[str, set[str]] = {'function': set(), 'task': set()}
            for ruled in ruling['concepts']:
                kind = {'function_concept': 'function', 'task_concept': 'task'}[ruled['kind']]
                pool = by_division[division][kind]
                member_labels = list(ruled['members'])
                if len(member_labels) < 2:
                    raise ValueError('an argued merge needs at least two members')
                for m in member_labels:
                    if m not in pool:
                        raise ValueError(f'ruled member is not a released {kind} of {division}: {m!r}')
                    if m in consumed[kind]:
                        raise ValueError(f'ruled member appears in two concepts: {m!r}')
                    consumed[kind].add(m)
                label = ruled['label']
                label_source = ruled.get('label_source') or ('member' if label in member_labels else 'ruled')
                if (label_source == 'member') != (label in member_labels):
                    raise ValueError(f'label_source disagrees with membership for {label!r}')
                alias_rationales = ruled.get('alias_rationales') or {}
                aliases = []
                for m in sorted(member_labels):
                    if m == label:
                        continue
                    if not str(alias_rationales.get(m, '')).strip():
                        raise ValueError(f'argued merge lacks a rationale for alias {m!r}')
                    aliases.append({'reference_id': pool[m]['reference_id'], 'label': m, 'rationale': str(alias_rationales[m]).strip()})
                members = [pool[m] for m in sorted(member_labels)]
                concepts.append(_definition({
                    'concept_id': concept_id(ruled['kind'], division, label), 'kind': ruled['kind'],
                    'division_key': division, 'label': label, 'label_source': label_source,
                    'review_status': review_status, 'basis': BASIS_MERGE, 'rationale': str(ruled['rationale']).strip(),
                }, members, aliases))
                counts[ruled['kind'] + 's'] += 1
                counts['aliases'] += len(aliases)
                counts['argued_merges'] += 1
            for kind, concept_kind in KINDS.items():
                for label, entry in sorted(by_division[division][kind].items()):
                    if label in consumed[kind]:
                        continue
                    concepts.append(_definition({
                        'concept_id': concept_id(concept_kind, division, label), 'kind': concept_kind,
                        'division_key': division, 'label': label, 'label_source': 'member',
                        'review_status': review_status, 'basis': BASIS_STANDALONE, 'rationale': None,
                    }, [entry], []))
                    counts[concept_kind + 's'] += 1
        division_rows.append({
            'division_key': division, 'review_status': review_status, 'basis': basis,
            'ruling': None if ruling is None else {
                'ruled_by': ruling['ruled_by'], 'ruled_at': str(ruling['ruled_at']), 'basis': ruling['basis'],
                'argued_merges': counts['argued_merges'], 'aliases': counts['aliases'],
            },
            'counts': {k: counts[k] for k in ('functions', 'function_concepts', 'tasks', 'task_concepts', 'aliases')},
        })

    concepts.sort(key=lambda c: c['concept_id'])
    if len({c['concept_id'] for c in concepts}) != len(concepts):
        raise ValueError('concept identifier collision')
    membership = [m for c in concepts for m in c['members']]
    if len(membership) != len(set(membership)):
        raise ValueError('a released definition belongs to two concepts')
    expected = {d['reference_id'] for d in definitions if d['kind'] in KINDS}
    if set(membership) != expected:
        raise ValueError('every released function and task must belong to exactly one concept')

    result = {
        'schema': SCHEMA_ID,
        'contract_version': CONTRACT_VERSION,
        'identity_rule': 'SHA-256 of exact kind, division key and concept label, first 24 hex characters; concepts never cross a division',
        'institution_instances': False,
        'sources': [
            {'path': CATALOGUE_PATH, 'sha256': sha256_bytes(catalogue_raw)},
            {'path': RULINGS_PATH, 'sha256': sha256_bytes(rulings_raw)},
        ],
        'method': {
            'machine': {
                'algorithm': 'average-linkage agglomerative clustering over Jaccard similarity of canonical label tokens',
                'similarity_threshold': SIMILARITY_THRESHOLD,
                'token_rule': 'bocg.canon.canon_name, digits dropped, verb/noun variants folded, stoplist removed',
                'stoplist_sha256': sha256_bytes(canonical_bytes(sorted(STOPLIST))),
                'variants_sha256': sha256_bytes(canonical_bytes(VARIANTS)),
                'representative_rule': 'shortest member label, ties alphabetical; never an invented label',
                'read_by_a_human': False,
            },
            'reviewed': {
                'rulings_path': RULINGS_PATH,
                'rule': 'only argued merges group definitions; everything the ruling does not merge stands alone',
            },
        },
        'divisions': division_rows,
        'concepts': concepts,
        'counts': {
            'divisions': len(division_rows),
            'reviewed_divisions': sum(r['review_status'] == 'REVIEWED' for r in division_rows),
            'auto_divisions': sum(r['review_status'] == 'AUTO' for r in division_rows),
            'function_concepts': sum(c['kind'] == 'function_concept' for c in concepts),
            'task_concepts': sum(c['kind'] == 'task_concept' for c in concepts),
            'aliases': sum(len(c['aliases']) for c in concepts),
            'reviewed_aliases': sum(len(c['aliases']) for c in concepts if c['review_status'] == 'REVIEWED'),
        },
    }
    result['task_concepts_sha256'] = sha256_bytes(canonical_bytes(result))
    return result


def render(value: dict) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + '\n'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    destination = ROOT / OUTPUT_PATH
    expected = render(build_task_concepts())
    if args.check:
        if not destination.exists() or destination.read_text(encoding='utf-8') != expected:
            raise SystemExit('task concepts are stale; regenerate before release')
        print('Task concepts reproduce exactly.')
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(expected, encoding='utf-8')
        print('Wrote', OUTPUT_PATH)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
