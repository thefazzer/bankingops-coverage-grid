"""§3 post-validation: field order (I5), admission recompute + ARITH_MISMATCH (I9), self-assessment (I7)."""
import copy
import json

from bocg.validate import admission, assess, order_check, parse_json, schema_errors
from conftest import load_fixture_response


def test_fixture_responses_are_schema_valid():
    obj = load_fixture_response("alpha-lm-1.0", 0)
    assert schema_errors(obj) == []


def test_order_check_passes_on_fixture_raw_text(fixtures_dir):
    raw = json.loads((fixtures_dir / "alpha-lm-1.0" / "0.json").read_text())["response_raw"]
    oc = order_check(raw)
    assert oc["ok"] and oc["violations"] == [] and oc["divisions_checked"] == 9


def test_order_check_fails_when_name_precedes_anchors():
    obj = load_fixture_response("alpha-lm-1.0", 0)
    div = obj["divisions"][0]
    reordered = {"name": div["name"], "axis": div["axis"], "confidence": div["confidence"],
                 "a1_regulatory": div["a1_regulatory"], "a2_segment": div["a2_segment"],
                 "a3_market_size": div["a3_market_size"], "a4_seat": div["a4_seat"]}
    obj["divisions"][0] = reordered
    raw = json.dumps(obj, indent=2)
    assert schema_errors(obj) == []            # JSON Schema cannot see order ...
    oc = order_check(raw)                      # ... the raw-text offset check can
    assert not oc["ok"] and oc["violations"] == [0]
    a = assess(raw)
    assert not a.valid and "ORDER_VIOLATION" in a.invalid_reasons()


def test_order_check_ignores_nested_name_keys():
    # a nested object containing a "name" key before a1_regulatory must not trip the top-level check
    obj = load_fixture_response("alpha-lm-1.0", 0)
    div = obj["divisions"][0]
    div2 = {"a1_regulatory": [{"regime": "x", "jurisdiction": "y", "citation": "z", "name": "nested"}],
            **{k: v for k, v in div.items() if k != "a1_regulatory"}}
    obj["divisions"][0] = div2
    raw = json.dumps(obj)
    assert order_check(raw)["ok"]


def test_admission_recompute_uses_midpoint_times_determinable_fraction():
    div = load_fixture_response("alpha-lm-1.0", 0)["divisions"][0]     # rates trading
    a = admission(div, 200000)
    lo, hi = div["a4_seat"]["cost_per_seat"]
    assert a.addressable_seat_cost_recomputed == ((lo + hi) / 2) * div["a4_seat"]["determinable_fraction"]
    assert a.admitted and a.reasons == [] and not a.arith_mismatch and a.anchors_nonnull == 3


def test_admission_flags_arith_mismatch_but_uses_recomputed_value():
    div = load_fixture_response("alpha-lm-1.0", 0)["divisions"][-1]    # market risk control (alpha)
    assert div["a4_seat"]["addressable_seat_cost"] == 260000.0
    a = admission(div, 200000)
    assert a.arith_mismatch and a.addressable_seat_cost_recomputed == 229500.0 and a.admitted


def test_admission_overrides_model_placement_when_seat_below_threshold():
    div = load_fixture_response("gamma-analyst-3", 0)["divisions"][-1]  # market risk control (gamma)
    a = admission(div, 200000)
    assert not a.admitted and a.reasons == ["R_SEAT_BELOW_THRESHOLD"] and a.arith_mismatch


def test_admission_requires_two_anchors_and_three_tasks():
    div = copy.deepcopy(load_fixture_response("alpha-lm-1.0", 0)["divisions"][0])
    div["a1_regulatory"] = None
    div["a2_segment"] = []
    div["a4_seat"]["terminality"] = div["a4_seat"]["terminality"][:2]
    a = admission(div, 200000)
    assert set(a.reasons) == {"R_ANCHORS_LT2", "R_TERMINALITY_LT3"} and a.anchors_nonnull == 1


def test_arith_tolerance_boundary():
    div = copy.deepcopy(load_fixture_response("alpha-lm-1.0", 0)["divisions"][0])
    true = admission(div, 200000).addressable_seat_cost_recomputed
    div["a4_seat"]["addressable_seat_cost"] = true * 1.04
    assert not admission(div, 200000).arith_mismatch
    div["a4_seat"]["addressable_seat_cost"] = true * 1.06
    assert admission(div, 200000).arith_mismatch


def test_assess_marks_invalid_json_and_self_assessment(fixtures_dir):
    raw = json.loads((fixtures_dir / "alpha-lm-1.0" / "3.json").read_text())["response_raw"]
    a = assess(raw)
    assert a.parse_error and not a.valid and a.invalid_reasons() == ["PARSE_ERROR"]
    raw = json.loads((fixtures_dir / "beta-reasoner-2" / "3.json").read_text())["response_raw"]
    a = assess(raw)
    assert a.schema_valid and not a.valid and a.invalid_reasons() == ["SELF_ASSESSMENT_LANGUAGE"]
    assert any("under-served" in h["match"] for h in a.self_assess)


def test_parse_json_strips_code_fence_only():
    obj, err = parse_json('```json\n{"a": 1}\n```')
    assert obj == {"a": 1} and err is None
    obj, err = parse_json('{"a": 1,}')
    assert obj is None and err


def test_empty_rejected_is_schema_invalid():
    obj = load_fixture_response("alpha-lm-1.0", 0)
    obj["rejected"] = []
    assert any("rejected" in e for e in schema_errors(obj))
