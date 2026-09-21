import json
from pathlib import Path

import jsonschema
import pytest
import yaml


ROOT = Path(__file__).parents[2]


def test_profile_is_layered_and_contains_no_instances():
    profile = yaml.safe_load((ROOT / "specs/insight-construction-profile.yaml").read_text())
    meta = profile["profile"]
    assert meta["layered_on"] == "bocg-common-semantics"
    assert meta["scope"]["definitions_only"] is True
    assert meta["scope"]["occurrence_instances_permitted"] is False


def test_profile_contains_temporal_semantics_for_lifecycle_states():
    profile = yaml.safe_load((ROOT / "specs/insight-construction-profile.yaml").read_text())
    temporal = profile["lifecycle_vocabulary"]["temporal_semantics"]
    assert "occurred_at" in temporal
    assert temporal["occurred_at"]["source_anchor_required"] is True
    assert "deadline_ref" in temporal
    assert temporal["deadline_ref"]["citation_required"] is True
    assert "calendar_ref" in temporal


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


@pytest.fixture
def insight_validator():
    schema = json.loads((ROOT / "specs/insight-construction.schema.json").read_text())
    return jsonschema.Draft202012Validator(schema)


def _episode_fixture(**status_overrides):
    return {
        "kind": "Episode",
        "episode_id": "ep-test-temporal",
        "atom_ids": ["a1"],
        "composition_status": "candidate",
        **status_overrides,
    }


def test_episode_accepts_plain_lifecycle_state(insight_validator):
    episode = _episode_fixture(
        execution_status="scheduled",
        completion_status="not_observed",
        verification_status="not_observed",
    )
    insight_validator.validate(episode)


def test_episode_accepts_state_transition_with_occurred_at(insight_validator):
    episode = _episode_fixture(
        execution_status={"state": "executed", "occurred_at": "2026-09-20T14:30:00Z"},
        completion_status="not_observed",
        verification_status="not_observed",
    )
    insight_validator.validate(episode)


def test_episode_accepts_state_transition_with_deadline_and_calendar(insight_validator):
    episode = _episode_fixture(
        execution_status={
            "state": "scheduled",
            "deadline_ref": {"expression": "T+1 business day", "citation": "EMIR Art. 4 (Regulation (EU) 648/2012)"},
            "calendar_ref": "TARGET2",
        },
        completion_status="not_observed",
        verification_status="not_observed",
    )
    insight_validator.validate(episode)


def test_episode_rejects_state_transition_missing_required_deadline_fields(insight_validator):
    episode = _episode_fixture(
        execution_status={"state": "scheduled", "deadline_ref": {"expression": "T+1 business day"}},
        completion_status="not_observed",
        verification_status="not_observed",
    )
    assert list(insight_validator.iter_errors(episode))


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
