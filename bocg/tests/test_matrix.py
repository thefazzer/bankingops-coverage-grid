"""§5.3–5.7 matrix, tiers, axis vote, anchor/seat pools; determinism; run logging (§4)."""
import json
from pathlib import Path

from bocg.matrix import axis_vote, build_matrix, tiers
from bocg.util import read_json, sha256_text
from conftest import run_to_matrix


def test_matrix_is_byte_identical_across_replays(tmp_path):
    a = run_to_matrix(tmp_path / "a")
    b = run_to_matrix(tmp_path / "b")
    assert a.matrix_csv.read_bytes() == b.matrix_csv.read_bytes()
    assert a.matrix_json.read_bytes() == b.matrix_json.read_bytes()


def test_matrix_cells_and_tiers(ws_matrix):
    mx = read_json(ws_matrix.matrix_json)
    assert [m["model_id"] for m in mx["models"]] == sorted(m["model_id"] for m in mx["models"])
    assert mx["division_keys"] == sorted(mx["division_keys"])
    rows = {r["division_key"]: r for r in mx["rows"]}
    # alpha has k=4 (3 valid + 1 INVALID) so a division named in all valid samples scores 0.75
    assert rows["rates_trading"]["cells"]["alpha-lm-1.0"] == 0.75
    assert rows["rates_trading"]["model_support"] == 4 and rows["rates_trading"]["tier"] == "STRONG"
    assert rows["commodities_trading"]["tier"] == "WEAK" and rows["commodities_trading"]["model_support"] == 1
    assert rows["equities_trading"]["tier"] == "MODERATE"
    # gamma's "Market Risk Control" was demoted server-side -> only alpha's (arith-mismatched but admitted) counts
    assert rows["market_risk_control"]["cells"]["gamma-analyst-3"] == 0.0
    assert rows["market_risk_control"]["cells"]["alpha-lm-1.0"] == 0.25
    csv_lines = ws_matrix.matrix_csv.read_text().splitlines()
    assert csv_lines[0] == "division_key,alpha-lm-1.0,beta-reasoner-2,delta-decomposer-4,gamma-analyst-3,model_support,tier"
    assert len(csv_lines) == 1 + len(mx["rows"])


def test_tier_thresholds():
    assert tiers(4, 4) == "STRONG" and tiers(3, 4) == "MODERATE" and tiers(2, 4) == "MODERATE" and tiers(1, 4) == "WEAK"
    assert tiers(5, 6) == "STRONG" and tiers(4, 6) == "MODERATE" and tiers(3, 6) == "MODERATE" and tiers(2, 6) == "WEAK"


def test_axis_vote_majority_and_ties():
    axes = [{"business_line": "gm", "side": "sell", "region": ["EMEA"], "product": ["rates"], "office": "front"},
            {"business_line": "gm", "side": "buy", "region": ["EMEA", "AMER"], "product": ["credit"], "office": "front"},
            {"business_line": "ops", "side": "sell", "region": ["EMEA"], "product": ["rates"], "office": "back"}]
    v = axis_vote(axes)
    assert v == {"business_line": "gm", "side": "sell", "region": ["EMEA"], "product": ["rates"], "office": "front"}
    tie = axis_vote(axes[:2])
    # side 1-1 -> both; product 1-1 -> multi; EMEA is in 2/2 (majority), AMER in 1/2 (tie -> dropped)
    assert tie == {"business_line": "gm", "side": "both", "region": ["EMEA"], "product": ["multi"], "office": "front"}
    tie2 = axis_vote([{"region": ["EMEA"], "product": []}, {"region": ["APAC"], "product": []}])
    assert tie2["region"] == ["GLOBAL"] and tie2["product"] == ["multi"] and tie2["business_line"] == "multi"


def test_anchor_pool_dedupes_and_seat_pool_medians(ws_matrix):
    mx = read_json(ws_matrix.matrix_json)
    rows = {r["division_key"]: r for r in mx["rows"]}
    rt = rows["rates_trading"]
    # 4 vendors x up to 3 samples each emit the same two A1 citations -> pool has exactly 2
    assert len(rt["anchor_pool"]["A1"]) == 2 and len(rt["anchor_pool"]["A2"]) == 1
    assert rt["seat_pool"]["terminality_count"] == 3
    assert rt["seat_pool"]["addressable_seat_cost_median"] >= 200000
    assert rows["commodities_trading"]["anchor_pool"]["A3"] == []


def test_run_logging_layout_and_verbatim_bytes(ws_matrix, fixtures_dir):
    meta = read_json(ws_matrix.run_meta)
    d = ws_matrix.runs_dir(meta["prompt_sha8"])
    assert sorted(p.name for p in d.iterdir()) == ["alpha-lm-1.0", "beta-reasoner-2", "delta-decomposer-4",
                                                    "gamma-analyst-3"]
    rec = read_json(d / "alpha-lm-1.0" / "0.json")
    fx = json.loads((fixtures_dir / "alpha-lm-1.0" / "0.json").read_text())
    assert rec["response_raw"] == fx["response_raw"]                  # verbatim
    assert rec["response_sha256"] == sha256_text(fx["response_raw"])
    for k in ("request", "response_raw", "response_sha256", "ts_utc", "usage"):
        assert k in rec
    assert rec["request"]["params"] == {"temperature": 0.2, "top_p": 1.0, "max_tokens": 16000, "seed": 1000,
                                        "stream": False}
    assert rec["request"]["cold"]["tools"] is False and rec["vendor"] == "alphalabs"
    inv = read_json(d / "alpha-lm-1.0" / "3.json")
    assert inv["status"] == "INVALID" and inv["repair_pass"]["attempted"] and "PARSE_ERROR" in inv["invalid_reasons"]
    assert ws_matrix.prompt_sha256.read_text().split()[0] == meta["prompt_sha256"]
    assert Path(ws_matrix.prompt_txt).read_bytes() == (Path(__file__).parents[1] / "bocg" / "assets" / "prompt.txt").read_bytes()


def test_normalised_records_admission_diffs(ws_matrix):
    n = read_json(ws_matrix.normalised_json)
    by = {(s["model_id"], s["sample_idx"]): s for s in n["samples"]}
    assert by[("alpha-lm-1.0", 3)]["status"] == "INVALID"
    assert by[("beta-reasoner-2", 3)]["invalid_reasons"] == ["SELF_ASSESSMENT_LANGUAGE"]
    g0 = by[("gamma-analyst-3", 0)]
    assert any(d["server_placement"] == "rejected" and d["reasons"] == ["R_SEAT_BELOW_THRESHOLD"]
               for d in g0["admission_diffs"])
    a0 = by[("alpha-lm-1.0", 0)]
    assert any(d["reasons"] == ["ARITH_MISMATCH"] for d in a0["admission_diffs"])
    assert n["unaliased_canons"] == []


def test_build_matrix_ignores_invalid_and_unaliased(ws_matrix):
    n = read_json(ws_matrix.normalised_json)
    for s in n["samples"]:
        for d in s["divisions"]:
            if d["division_key"] == "settlements":
                d["division_key"] = None
    mx = build_matrix(n)
    assert "settlements" not in mx["division_keys"]
