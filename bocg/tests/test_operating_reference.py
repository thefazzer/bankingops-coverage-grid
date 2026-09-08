import copy
import hashlib
import json
from pathlib import Path
import pytest
from jsonschema import Draft202012Validator
from build_operating_catalogue import build_catalogue, reference_id
from build_release_manifest import build_manifest, STATIC_ARTIFACTS

ROOT = Path(__file__).parents[2]

def test_catalogue_reproduces_public_sources_without_instances():
    value = json.loads((ROOT / 'reference/operating-catalogue.v1.json').read_text())
    assert build_catalogue(ROOT) == value
    assert value['institution_instances'] is False
    assert len({d['reference_id'] for d in value['definitions']}) == len(value['definitions'])
    assert sum(d['kind'] == 'division' for d in value['definitions']) == 42
    for source in value['sources']:
        assert hashlib.sha256((ROOT / source['path']).read_bytes()).hexdigest() == source['sha256']

def test_reference_identity_keeps_divisions_and_kinds_separate():
    assert reference_id('task', 'rates', 'price') != reference_id('function', 'rates', 'price')
    assert reference_id('task', 'rates', 'price') != reference_id('task', 'credit', 'price')
    assert reference_id('task', 'rates', 'price') != reference_id('task', 'rates', 'Price')
    assert reference_id('division', 'rates') == 'division:rates'

def test_register_schema_is_valid_and_review_is_explicit():
    schema = json.loads((ROOT / 'specs/operating-unit-register.schema.json').read_text())
    Draft202012Validator.check_schema(schema)
    review_schema = schema['$defs']['review']
    validator = Draft202012Validator(review_schema)
    assert list(validator.iter_errors({'status':'REVIEWED','reviewer_ref':None,'reviewed_at':None,'reason':'Source review'}))
    assert not list(validator.iter_errors({'status':'PROPOSED','reviewer_ref':None,'reviewed_at':None,'reason':'Source candidate'}))

def test_release_binds_contract_schema_and_reproducible_catalogue():
    manifest = build_manifest(tag='v0.4.0', commit_sha='a'*40, generated_at='2026-09-08T00:00:00Z', root=ROOT)
    rows = {row['path']:row for row in manifest['artifacts']}
    for path in ('specs/operating-reference-contract.json','specs/operating-unit-register.schema.json','reference/operating-catalogue.v1.json'):
        assert path in STATIC_ARTIFACTS
        assert rows[path]['sha256'] == hashlib.sha256((ROOT / path).read_bytes()).hexdigest()

def test_stale_catalogue_blocks_release(tmp_path):
    import shutil
    for path in STATIC_ARTIFACTS:
        dest=tmp_path/path;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/path,dest)
    shutil.copytree(ROOT/'live-run-20260826',tmp_path/'live-run-20260826')
    shutil.copytree(ROOT/'cells',tmp_path/'cells')
    catalogue=tmp_path/'reference/operating-catalogue.v1.json'
    value=json.loads(catalogue.read_text());value['definitions'][0]['label']='Unreviewed change';catalogue.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='catalogue'):
        build_manifest(tag='v0.4.0',commit_sha='a'*40,generated_at='2026-09-08T00:00:00Z',root=tmp_path)
