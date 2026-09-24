"""SPEC-08: task concepts, rulings and the episode surface."""
import copy
import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker

from build_task_concepts import build_task_concepts, concept_id, machine_clusters, render, KINDS
from build_release_manifest import build_manifest, STATIC_ARTIFACTS
from episode_surface import candidate_depth, evidence_depth, surface_problems

ROOT = Path(__file__).parents[2]


def _concepts():
    return json.loads((ROOT / 'reference/task-concepts.v1.json').read_text())


def test_task_concepts_reproduce_and_validate():
    value = _concepts()
    assert render(build_task_concepts(ROOT)) == (ROOT / 'reference/task-concepts.v1.json').read_text()
    schema = json.loads((ROOT / 'specs/task-concepts.schema.json').read_text())
    Draft202012Validator.check_schema(schema)
    assert not list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value))
    assert value['institution_instances'] is False
    assert value['method']['machine']['read_by_a_human'] is False


def test_every_released_definition_belongs_to_exactly_one_concept_of_its_division():
    value = _concepts()
    catalogue = json.loads((ROOT / 'reference/operating-catalogue.v1.json').read_text())
    released = {d['reference_id']: d for d in catalogue['definitions'] if d['kind'] in KINDS}
    seen = []
    for concept in value['concepts']:
        for member in concept['members']:
            assert released[member]['division_key'] == concept['division_key']
            assert KINDS[released[member]['kind']] == concept['kind']
            seen.append(member)
    assert sorted(seen) == sorted(released)
    assert len({c['concept_id'] for c in value['concepts']}) == len(value['concepts'])


def test_prime_brokerage_is_the_only_reviewed_division_with_twenty_three_aliases():
    value = _concepts()
    reviewed = [d for d in value['divisions'] if d['review_status'] == 'REVIEWED']
    assert [d['division_key'] for d in reviewed] == ['prime_brokerage_financing']
    assert value['counts'] == {**value['counts'], 'reviewed_divisions': 1, 'auto_divisions': 41, 'reviewed_aliases': 23}
    pb = reviewed[0]
    assert pb['ruling']['aliases'] == 23 and pb['ruling']['argued_merges'] == 3
    merges = [c for c in value['concepts'] if c['division_key'] == 'prime_brokerage_financing' and c['basis'] == 'argued_merge']
    by_label = {c['label']: c for c in merges}
    assert len(by_label['calculate a client margin requirement']['aliases']) == 4
    assert len(by_label['issue collect a house reg margin call under client s margin agreement']['aliases']) == 10
    composite = [c for c in merges if c['kind'] == 'function_concept']
    assert len(composite) == 1 and len(composite[0]['members']) == 9 and composite[0]['label_source'] == 'ruled'
    for concept in merges:
        assert concept['rationale'] and all(a['rationale'] for a in concept['aliases'])
    standalone = [c for c in value['concepts'] if c['division_key'] == 'prime_brokerage_financing' and c['basis'] == 'standalone_under_review']
    assert all(len(c['members']) == 1 and not c['aliases'] for c in standalone)


def test_auto_divisions_are_machine_clustered_and_never_claim_review():
    value = _concepts()
    for division in value['divisions']:
        if division['review_status'] == 'AUTO':
            assert division['ruling'] is None and division['basis'] == 'machine_clustered'
    for concept in value['concepts']:
        if concept['review_status'] == 'AUTO':
            assert concept['basis'] == 'machine_clustered' and concept['label_source'] == 'member'
            assert concept['label'] in concept['member_labels']
            assert all('unread by any human' in a['rationale'] for a in concept['aliases'])


def test_machine_clustering_is_deterministic_and_never_invents_a_label():
    labels = ['report corporate bond trade to trace within 15 minute', 'report us corporate bond trade to trace within required window', 'price a cash bond or credit derivative']
    first = machine_clusters(labels)
    assert first == machine_clusters(list(reversed(labels)))
    assert any(len(group) == 2 for group in first)
    assert {label for group in first for label in group} == set(labels)


def test_concept_identity_separates_kind_division_and_label():
    assert concept_id('task_concept', 'a', 'x') != concept_id('function_concept', 'a', 'x')
    assert concept_id('task_concept', 'a', 'x') != concept_id('task_concept', 'b', 'x')
    assert concept_id('task_concept', 'a', 'x') != concept_id('task_concept', 'a', 'X')


def test_ruling_rejects_unknown_members_and_missing_rationales(tmp_path):
    import shutil
    for relative in ('reference/operating-catalogue.v1.json', 'reference/task-concept-rulings.yaml'):
        dest = tmp_path / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, dest)
    rulings_path = tmp_path / 'reference/task-concept-rulings.yaml'
    original = yaml.safe_load(rulings_path.read_text())
    broken = copy.deepcopy(original)
    broken['rulings'][0]['concepts'][0]['members'].append('not a released task')
    rulings_path.write_text(yaml.safe_dump(broken, sort_keys=False))
    with pytest.raises(ValueError, match='not a released'):
        build_task_concepts(tmp_path)
    broken = copy.deepcopy(original)
    broken['rulings'][0]['concepts'][0]['alias_rationales'].pop('calculate client portfolio margin')
    rulings_path.write_text(yaml.safe_dump(broken, sort_keys=False))
    with pytest.raises(ValueError, match='rationale'):
        build_task_concepts(tmp_path)
    broken = copy.deepcopy(original)
    broken['rulings'][0]['review_status'] = 'AUTO'
    rulings_path.write_text(yaml.safe_dump(broken, sort_keys=False))
    with pytest.raises(ValueError, match='REVIEWED'):
        build_task_concepts(tmp_path)


def test_episode_surface_fixture_follows_depth_rule_and_release_binding():
    schema = json.loads((ROOT / 'specs/episode-surface.schema.json').read_text())
    Draft202012Validator.check_schema(schema)
    fixture = json.loads((ROOT / 'specs/fixtures/episode-surface-synthetic.json').read_text())
    assert not list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(fixture))
    assert surface_problems(fixture, root=ROOT) == []
    assert evidence_depth(fixture) == fixture['evidence_depth']
    assert candidate_depth(fixture) == fixture['candidate_depth']


def test_candidates_never_raise_evidence_depth():
    fixture = json.loads((ROOT / 'specs/fixtures/episode-surface-synthetic.json').read_text())
    for point in fixture['touchpoints']:
        if point['mapping_status'] in {'RATIFIED_MAPPING', 'QUALIFIED_MAPPING'}:
            point['mapping_status'] = 'PROPOSED'
            point['ruling'] = None
    assert evidence_depth(fixture) == 'none'
    assert candidate_depth(fixture) != 'none'
    assert 'evidence_depth does not follow the depth rule' in surface_problems(fixture, root=ROOT)


def test_surface_rejects_identifiers_outside_the_release():
    fixture = json.loads((ROOT / 'specs/fixtures/episode-surface-synthetic.json').read_text())
    point = next(p for p in fixture['touchpoints'] if p['task_concept_id'])
    point['task_concept_id'] = 'task_concept:' + point['division_key'] + ':' + '0' * 24
    assert any('not a released concept' in p for p in surface_problems(fixture, root=ROOT))


def test_release_binds_concepts_and_refuses_stale_concepts(tmp_path):
    import hashlib
    import shutil
    manifest = build_manifest(tag='v0.6.0', commit_sha='a' * 40, generated_at='2026-09-24T00:00:00Z', root=ROOT)
    rows = {row['path']: row for row in manifest['artifacts']}
    for path in ('specs/SPEC-08-task-concepts-and-episode-surface.md', 'specs/task-concepts.schema.json', 'specs/episode-surface.schema.json', 'reference/task-concepts.v1.json', 'reference/task-concept-rulings.yaml', 'specs/fixtures/episode-surface-synthetic.json'):
        assert path in STATIC_ARTIFACTS
        assert rows[path]['sha256'] == hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
    for path in STATIC_ARTIFACTS:
        dest = tmp_path / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / path, dest)
    shutil.copytree(ROOT / 'live-run-20260826', tmp_path / 'live-run-20260826')
    shutil.copytree(ROOT / 'cells', tmp_path / 'cells')
    concepts = tmp_path / 'reference/task-concepts.v1.json'
    value = json.loads(concepts.read_text())
    value['concepts'][0]['label'] = 'Unreviewed change'
    concepts.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='task concepts'):
        build_manifest(tag='v0.6.0', commit_sha='a' * 40, generated_at='2026-09-24T00:00:00Z', root=tmp_path)
