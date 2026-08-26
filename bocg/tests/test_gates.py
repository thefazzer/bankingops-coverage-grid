"""§8 gates G1–G10: a passing and a failing case for each."""
import json
import shutil

import pytest

from bocg.corroborate import corroborate
from bocg.gates import GATES, run_gates
from bocg.grid import write_grid
from bocg.util import BocgError, read_json, sha256_file, sha256_text, write_json
from conftest import FIXTURES, QUIET


def gate(ws, gid):
    return GATES[gid](ws)


def _runs(ws):
    return ws.runs_dir(read_json(ws.run_meta)["prompt_sha8"])


def _rewrite_run(ws, model, idx, mutate):
    p = _runs(ws) / model / f"{idx}.json"
    rec = read_json(p)
    mutate(rec)
    write_json(p, rec)
    return p


# ---------------------------------------------------------------- happy path
def test_all_gates_pass_on_fixture_pipeline(ws_full):
    run_gates(ws_full)
    rep = read_json(ws_full.gates_report)
    assert rep["all_pass"], [g for g in rep["gates"] if g["status"] != "PASS"]
    assert [g["id"] for g in rep["gates"]] == [f"G{i}" for i in range(1, 11)]
    for g in rep["gates"]:
        assert set(g) >= {"id", "status", "evidence"} and g["evidence"]


# ---------------------------------------------------------------- G1
def test_g1_pass(ws_matrix):
    r = gate(ws_matrix, "G1")
    assert r["status"] == "PASS" and r["evidence"]["forbidden_hits_prompt"] == []
    assert r["evidence"]["prompt_sha256_actual"] == r["evidence"]["prompt_sha256_published"]


def test_g1_fails_on_forbidden_token(ws_matrix):
    ws_matrix.prompt_txt.write_text(ws_matrix.prompt_txt.read_text() + "\nConsider the prime brokerage desk.\n")
    ws_matrix.prompt_sha256.write_text(sha256_file(ws_matrix.prompt_txt) + "  prompt.txt\n")
    r = gate(ws_matrix, "G1")
    assert r["status"] == "FAIL"
    assert [h["token"] for h in r["evidence"]["forbidden_hits_prompt"]] == ["prime brokerage"]


def test_g1_fails_on_sha_mismatch(ws_matrix):
    ws_matrix.prompt_sha256.write_text("0" * 64 + "  prompt.txt\n")
    r = gate(ws_matrix, "G1")
    assert r["status"] == "FAIL" and r["evidence"]["runs_with_other_prompt_sha"]


# ---------------------------------------------------------------- G2
def test_g2_pass(ws_matrix):
    r = gate(ws_matrix, "G2")
    assert r["status"] == "PASS" and r["evidence"]["schema_valid"] == 13 and r["evidence"]["invalid_marked"] == 1


def test_g2_fails_on_silently_edited_response(ws_matrix):
    _rewrite_run(ws_matrix, "alpha-lm-1.0", 0, lambda rec: rec.update(response_raw=rec["response_raw"] + " "))
    r = gate(ws_matrix, "G2")
    assert r["status"] == "FAIL" and len(r["evidence"]["sha256_mismatch"]) == 1


def test_g2_fails_on_unmarked_invalid_response(ws_matrix):
    def mutate(rec):
        rec["response_raw"] = "not json at all"
        rec["response_sha256"] = sha256_text(rec["response_raw"])
        rec["status"] = "OK"
    _rewrite_run(ws_matrix, "alpha-lm-1.0", 1, mutate)
    r = gate(ws_matrix, "G2")
    assert r["status"] == "FAIL" and r["evidence"]["invalid_unmarked"][0]["reasons"] == ["PARSE_ERROR"]


# ---------------------------------------------------------------- G3
def _order_violating_raw():
    obj = json.loads(json.loads((FIXTURES / "alpha-lm-1.0" / "0.json").read_text())["response_raw"])
    d = obj["divisions"][0]
    obj["divisions"][0] = {"name": d["name"], **{k: v for k, v in d.items() if k != "name"}}
    return json.dumps(obj, indent=2)


def test_g3_pass(ws_matrix):
    r = gate(ws_matrix, "G3")
    assert r["status"] == "PASS" and r["evidence"]["responses_checked"] == 13


def test_g3_fails_on_name_before_anchors(ws_matrix):
    raw = _order_violating_raw()
    _rewrite_run(ws_matrix, "alpha-lm-1.0", 0, lambda rec: rec.update(response_raw=raw, response_sha256=sha256_text(raw)))
    r = gate(ws_matrix, "G3")            # normalised.json is now stale: violation not marked INVALID
    assert r["status"] == "FAIL" and r["evidence"]["violations"][0]["order_check"]["violations"] == [0]


def test_g3_passes_once_normalise_marks_violation_invalid(ws_matrix):
    from bocg.normalise import normalise_runs
    raw = _order_violating_raw()
    _rewrite_run(ws_matrix, "alpha-lm-1.0", 0, lambda rec: rec.update(response_raw=raw, response_sha256=sha256_text(raw)))
    normalise_runs(ws_matrix, echo=QUIET)
    n = read_json(ws_matrix.normalised_json)
    s = [s for s in n["samples"] if s["model_id"] == "alpha-lm-1.0" and s["sample_idx"] == 0][0]
    assert s["status"] == "INVALID" and "ORDER_VIOLATION" in s["invalid_reasons"]
    assert gate(ws_matrix, "G3")["status"] == "PASS"


# ---------------------------------------------------------------- G4
def test_g4_pass(ws_matrix):
    assert gate(ws_matrix, "G4")["status"] == "PASS"


def test_g4_fails_on_empty_rejected_marked_ok(ws_matrix):
    def mutate(rec):
        obj = json.loads(rec["response_raw"])
        obj["rejected"] = []
        rec["response_raw"] = json.dumps(obj)
        rec["response_sha256"] = sha256_text(rec["response_raw"])
        rec["status"] = "OK"
    _rewrite_run(ws_matrix, "delta-decomposer-4", 0, mutate)
    ws_matrix.normalised_json.unlink()
    r = gate(ws_matrix, "G4")
    assert r["status"] == "FAIL" and r["evidence"]["violations"][0]["rejected_len"] == 0


# ---------------------------------------------------------------- G5
def test_g5_pass_logs_overrides_and_arith(ws_matrix):
    r = gate(ws_matrix, "G5")
    assert r["status"] == "PASS"
    ov = r["evidence"]["self_placement_overridden"]
    assert {o["model_id"] for o in ov} == {"gamma-analyst-3"} and all(o["reasons"] == ["R_SEAT_BELOW_THRESHOLD"] for o in ov)
    assert any(a["model_id"] == "alpha-lm-1.0" for a in r["evidence"]["arith_mismatch"])


def test_g5_fails_when_normalised_admission_is_tampered(ws_matrix):
    n = read_json(ws_matrix.normalised_json)
    for s in n["samples"]:
        for d in s["divisions"]:
            if d["division_key"] == "market_risk_control" and not d["server_admitted"]:
                d["server_admitted"] = True          # someone "admitted" a demoted division by hand
    write_json(ws_matrix.normalised_json, n)
    r = gate(ws_matrix, "G5")
    assert r["status"] == "FAIL" and r["evidence"]["stale"]


def test_g5_fails_without_normalised(ws_matrix):
    ws_matrix.normalised_json.unlink()
    assert gate(ws_matrix, "G5")["status"] == "FAIL"


# ---------------------------------------------------------------- G6
def test_g6_pass(ws_full):
    r = gate(ws_full, "G6")
    assert r["status"] == "PASS" and r["evidence"]["admitted_divisions"] == 11 and r["evidence"]["failing"] == {}


def test_g6_fails_on_unverified_anchor(ws_matrix):
    corroborate(ws_matrix, FIXTURES / "corroboration_one_unverified.csv", echo=QUIET)
    r = gate(ws_matrix, "G6")
    assert r["status"] == "FAIL" and list(r["evidence"]["failing"]) == ["settlements"]
    assert r["evidence"]["failing"]["settlements"]["unverified_count"] == 1


def test_g6_refuted_anchor_moves_division_to_rejected_post_corroboration(ws_matrix):
    corroborate(ws_matrix, FIXTURES / "corroboration_refuted.csv", echo=QUIET)
    r = gate(ws_matrix, "G6")
    assert r["status"] == "PASS" and r["evidence"]["rejected_post_corroboration"] == ["commodities_trading"]
    g = write_grid(ws_matrix, echo=QUIET)
    cell = [c for c in g["cells"] if c["division_key"] == "commodities_trading"][0]
    assert cell["tier"] == "REJECTED_POST_CORROBORATION" and cell["consensus_tier"] == "WEAK"


def test_g6_fails_when_ledger_missing_a_pooled_anchor(ws_full):
    lines = ws_full.corroboration_csv.read_text().splitlines()
    kept = [lines[0]] + [ln for ln in lines[1:] if not ln.startswith("fx_trading,A2,")]
    ws_full.corroboration_csv.write_text("\n".join(kept) + "\n")
    r = gate(ws_full, "G6")
    assert r["status"] == "FAIL" and r["evidence"]["failing"]["fx_trading"]["missing_rows"]


def test_ledger_validation_rejects_bad_status(ws_matrix, tmp_path):
    src = (FIXTURES / "corroboration_all_verified.csv").read_text().replace("VERIFIED", "MAYBE", 1)
    p = tmp_path / "bad.csv"
    p.write_text(src)
    with pytest.raises(BocgError, match="invalid status"):
        corroborate(ws_matrix, p, echo=QUIET)


# ---------------------------------------------------------------- G7
def test_g7_pass(ws_matrix):
    r = gate(ws_matrix, "G7")
    assert r["status"] == "PASS" and r["evidence"]["keys_without_alias"] == []


def test_g7_fails_on_alias_sha_drift(ws_matrix):
    ws_matrix.aliases_yaml.write_text(ws_matrix.aliases_yaml.read_text() + "# edited after publication\n")
    r = gate(ws_matrix, "G7")
    assert r["status"] == "FAIL" and r["evidence"]["aliases_sha256_actual"] != r["evidence"]["aliases_sha256_published"]


def test_g7_fails_on_key_without_alias_or_duplicate_alias(ws_matrix):
    import yaml
    d = yaml.safe_load(ws_matrix.aliases_yaml.read_text())
    d["aliases"] = [e for e in d["aliases"] if e["key"] != "settlements"]
    ws_matrix.aliases_yaml.write_text(yaml.safe_dump(d))
    ws_matrix.aliases_sha256.write_text(sha256_file(ws_matrix.aliases_yaml) + "  aliases.yaml\n")
    mx = read_json(ws_matrix.matrix_json)
    mx["aliases_sha256"] = sha256_file(ws_matrix.aliases_yaml)
    write_json(ws_matrix.matrix_json, mx)
    r = gate(ws_matrix, "G7")
    assert r["status"] == "FAIL" and r["evidence"]["keys_without_alias"] == ["settlements"]
    d["aliases"].append({"canon": "rate trading", "key": "other_key", "rationale": "dup"})
    ws_matrix.aliases_yaml.write_text(yaml.safe_dump(d))
    ws_matrix.aliases_sha256.write_text(sha256_file(ws_matrix.aliases_yaml) + "  aliases.yaml\n")
    r = gate(ws_matrix, "G7")
    assert r["status"] == "FAIL" and "two keys" in r["evidence"]["error"]


# ---------------------------------------------------------------- G8
def test_g8_pass_with_seeded_response_invalidated(ws_matrix):
    r = gate(ws_matrix, "G8")
    assert r["status"] == "PASS" and r["evidence"]["prompt_hits"] == []
    assert len(r["evidence"]["responses_invalidated"]) == 1
    assert r["evidence"]["responses_invalidated"][0]["path"].endswith("beta-reasoner-2/3.json")


def test_g8_fails_when_prompt_has_gap_language(ws_matrix):
    ws_matrix.prompt_txt.write_text(ws_matrix.prompt_txt.read_text() + "\nList divisions that are under-served.\n")
    r = gate(ws_matrix, "G8")
    assert r["status"] == "FAIL" and r["evidence"]["prompt_hits"]


def test_g8_fails_when_violating_response_not_marked_invalid(ws_matrix):
    ws_matrix.normalised_json.unlink()
    r = gate(ws_matrix, "G8")
    assert r["status"] == "FAIL" and len(r["evidence"]["violations_not_marked_invalid"]) == 1


# ---------------------------------------------------------------- G9
def test_g9_pass(ws_matrix):
    r = gate(ws_matrix, "G9")
    assert r["status"] == "PASS" and r["evidence"]["byte_identical"]


def test_g9_fails_when_matrix_edited(ws_matrix):
    ws_matrix.matrix_csv.write_text(ws_matrix.matrix_csv.read_text().replace("0.7500", "0.7501", 1))
    assert gate(ws_matrix, "G9")["status"] == "FAIL"


def test_g9_replays_from_runs_dir_when_no_fixtures(ws_matrix):
    meta = read_json(ws_matrix.run_meta)
    meta["fixtures_dir"] = None            # live-mode workspace: replay source is runs/<sha8>/
    write_json(ws_matrix.run_meta, meta)
    r = gate(ws_matrix, "G9")
    assert r["status"] == "PASS" and r["evidence"]["replay_source"].endswith(meta["prompt_sha8"])


# ---------------------------------------------------------------- G10
def test_g10_pass(ws_matrix):
    r = gate(ws_matrix, "G10")
    assert r["status"] == "PASS" and len(r["evidence"]["vendors_with_3plus_valid"]) == 4


def test_g10_fails_with_three_vendors(ws_matrix):
    shutil.rmtree(_runs(ws_matrix) / "delta-decomposer-4")
    r = gate(ws_matrix, "G10")
    assert r["status"] == "FAIL" and len(r["evidence"]["vendors_declared"]) == 3


def test_g10_fails_with_under_three_samples_or_non_cold(ws_matrix):
    (_runs(ws_matrix) / "gamma-analyst-3" / "2.json").unlink()
    r = gate(ws_matrix, "G10")
    assert r["status"] == "FAIL" and r["evidence"]["models_under_3_samples"] == {"gamma-analyst-3": 2}
    ws2 = ws_matrix
    _rewrite_run(ws2, "alpha-lm-1.0", 0, lambda rec: rec["request"]["cold"].update(tools=True))
    assert gate(ws2, "G10")["evidence"]["not_cold"]


def test_run_gates_reports_crash_as_fail(ws_matrix, monkeypatch):
    import bocg.gates as g
    monkeypatch.setitem(g.GATES, "G1", lambda ws: 1 / 0)
    rep = run_gates(ws_matrix, ["G1"], write_report=False)
    assert rep["gates"][0]["status"] == "FAIL" and "ZeroDivisionError" in rep["gates"][0]["evidence"]["error"]
