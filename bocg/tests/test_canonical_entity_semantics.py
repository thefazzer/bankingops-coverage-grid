import sys
from pathlib import Path
import yaml

sys.path.insert(0, str(Path(__file__).parents[2] / "tools"))
import gate_conformance as gate  # noqa: E402


ROOT = Path(__file__).parents[2]


def test_standards_bearing_entity_contract_and_existing_facing_rules_conform():
    gate.FAILURES.clear()
    gate.gate_common_semantics()
    assert gate.FAILURES == []
    profile = yaml.safe_load((ROOT / "specs/common-semantic-profile.yaml").read_text())
    assert profile["role_semantics"]["faces"]["properties"]["directional"] is True
    assert profile["profile"]["scope"]["occurrence_claims_permitted"] is False
    gaps = profile.get("candidate_vocabulary_gaps") or {}
    assert gaps.get("non_normative") is True
    assert any(
        "derivatives trading documentation control" in str(candidate)
        for candidate in gaps.get("candidates") or []
    )


def test_gate_rejects_corpus_identity_and_unversioned_product_classes(tmp_path, monkeypatch):
    specs = tmp_path / "specs"
    specs.mkdir()
    schema = ROOT / "specs/control-point-cell.schema.json"
    (specs / schema.name).write_bytes(schema.read_bytes())
    profile = yaml.safe_load((ROOT / "specs/common-semantic-profile.yaml").read_text())
    profile["entity_semantics"]["corpus_membership_is_identity"] = True
    profile["entity_semantics"]["product_classification"]["reference_key"].remove("regime")
    (specs / "common-semantic-profile.yaml").write_text(yaml.safe_dump(profile))
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    gate.FAILURES.clear()
    gate.gate_common_semantics()
    assert any("corpus_membership_is_identity" in error for error in gate.FAILURES)
    assert any("product reference" in error for error in gate.FAILURES)
    gate.FAILURES.clear()
