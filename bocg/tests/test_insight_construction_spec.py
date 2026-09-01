import json
from pathlib import Path

import jsonschema
import yaml


ROOT = Path(__file__).parents[2]


def test_profile_is_layered_and_contains_no_instances():
    profile = yaml.safe_load((ROOT / "specs/insight-construction-profile.yaml").read_text())
    meta = profile["profile"]
    assert meta["layered_on"] == "bocg-common-semantics"
    assert meta["scope"]["definitions_only"] is True
    assert meta["scope"]["occurrence_instances_permitted"] is False


def test_institutional_directive_keeps_execution_unobserved():
    schema = json.loads((ROOT / "specs/institutional-speech-act.schema.json").read_text())
    value = {
        "schema": "kg-institutional-speech-act-expansion.v1",
        "literal_speech_act": {"type": "confirmation_request"},
        "institutional_speech_act": {"type": "directive"},
        "pragmatic_expansion": {"expanded_reading": "Confirm the earliest feasible execution time and then execute.", "basis": ["managerial_authority"], "adjudication_status": "sme_confirmed"},
        "obligation_frame": {"directive_status": "directed", "execution_status": "not_observed", "completion_status": "not_observed", "verification_status": "not_observed"},
        "state_separation_enforced": True,
    }
    jsonschema.Draft202012Validator(schema).validate(value)
    value["obligation_frame"]["execution_status"] = "executed"
    assert list(jsonschema.Draft202012Validator(schema).iter_errors(value))


def test_release_manifest_contains_every_spec_05_artifact():
    from build_release_manifest import STATIC_ARTIFACTS
    required = {
        "specs/SPEC-05-insight-construction.md",
        "specs/insight-construction-profile.yaml",
        "specs/insight-construction.schema.json",
        "specs/institutional-speech-act.schema.json",
        "specs/rubrics/episode-feasibility.yaml",
        "specs/rubrics/five-families.yaml",
    }
    assert required.issubset(STATIC_ARTIFACTS)
