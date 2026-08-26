"""§8 RUNNABLE GATES G1–G10. Each gate is a function(ws) -> {id, name, status, evidence}.

Gates recompute from the stored artifacts (raw runs, ledger CSV, alias table, ...) rather than trusting
derived files, so a silently edited artifact is caught.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Callable

from .aliases import load_aliases
from .corroborate import _check_columns, validate_ledger
from .matrix import build_matrix
from .prompt import find_forbidden, find_self_assessment, load_frozen
from .run import Panel, load_runs, run_panel
from .util import BocgError, Workspace, read_csv, read_json, sha256_file, sha256_text, utc_now_iso, write_json
from .validate import admission, assess, order_check, parse_json

GateResult = dict


def _res(gid: str, name: str, ok: bool, evidence: dict) -> GateResult:
    return {"id": gid, "name": name, "status": "PASS" if ok else "FAIL", "evidence": evidence}


def _norm_index(ws: Workspace) -> dict[tuple[str, int], dict] | None:
    if not ws.normalised_json.exists():
        return None
    n = read_json(ws.normalised_json)
    return {(s["model_dir"], int(s["sample_idx"])): s for s in n["samples"]}


def _marked_invalid(norm_idx, rec: dict, reason: str | None = None) -> bool:
    if rec.get("status") in ("INVALID", "ERROR") and reason in (None, "SCHEMA_INVALID", "PARSE_ERROR"):
        return True
    if norm_idx is None:
        return False
    s = norm_idx.get((rec["_model_dir"], int(rec["sample_idx"])))
    if s is None or s["status"] != "INVALID":
        return False
    return reason is None or reason in s["invalid_reasons"]


def _published_sha(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").split()[0].strip()


# ---------------------------------------------------------------------------------------------------------
def g1_contamination(ws: Workspace) -> GateResult:
    ev: dict = {}
    ok = True
    if not ws.prompt_txt.exists() or not ws.system_txt.exists():
        return _res("G1", "CONTAMINATION_GATE", False, {"error": "prompt.txt/system.txt missing in workspace"})
    prompt = ws.prompt_txt.read_text(encoding="utf-8")
    system = ws.system_txt.read_text(encoding="utf-8")
    hits_p = find_forbidden(prompt)
    hits_s = find_forbidden(system)
    ev["forbidden_hits_prompt"] = hits_p
    ev["forbidden_hits_system"] = hits_s
    ok &= not hits_p and not hits_s
    actual = sha256_file(ws.prompt_txt)
    published = _published_sha(ws.prompt_sha256)
    ev["prompt_sha256_actual"] = actual
    ev["prompt_sha256_published"] = published
    ok &= published == actual
    # every run record must have been produced with the published prompt hash
    try:
        runs = load_runs(ws)
        bad = [r["_path"] for r in runs if r.get("prompt_sha256") != published]
        ev["runs_checked"] = len(runs)
        ev["runs_with_other_prompt_sha"] = bad
        ok &= not bad
    except BocgError as e:
        ev["runs_checked"] = 0
        ev["note"] = str(e)
    return _res("G1", "CONTAMINATION_GATE", bool(ok), ev)


def g2_schema(ws: Workspace) -> GateResult:
    try:
        runs = load_runs(ws)
    except BocgError as e:
        return _res("G2", "SCHEMA_GATE", False, {"error": str(e)})
    norm_idx = _norm_index(ws)
    sha_mismatch, unmarked_invalid = [], []
    n_valid = n_invalid_marked = 0
    for r in runs:
        if r.get("status") == "ERROR":
            n_invalid_marked += 1
            continue
        if sha256_text(r["response_raw"]) != r["response_sha256"]:
            sha_mismatch.append(r["_path"])
            continue
        a = assess(r["response_raw"])
        if a.schema_valid:
            n_valid += 1
        elif _marked_invalid(norm_idx, r):
            n_invalid_marked += 1
        else:
            unmarked_invalid.append({"path": r["_path"], "reasons": a.invalid_reasons()})
    ok = not sha_mismatch and not unmarked_invalid
    return _res("G2", "SCHEMA_GATE", ok, {"responses": len(runs), "schema_valid": n_valid,
                                          "invalid_marked": n_invalid_marked, "sha256_mismatch": sha_mismatch,
                                          "invalid_unmarked": unmarked_invalid})


def g3_order(ws: Workspace) -> GateResult:
    try:
        runs = load_runs(ws)
    except BocgError as e:
        return _res("G3", "ORDER_GATE", False, {"error": str(e)})
    norm_idx = _norm_index(ws)
    checked, violations = 0, []
    for r in runs:
        if r.get("status") == "ERROR":
            continue
        a = assess(r["response_raw"])
        if not a.schema_valid:
            continue
        checked += 1
        oc = order_check(r["response_raw"])
        if not oc["ok"] and not _marked_invalid(norm_idx, r, "ORDER_VIOLATION"):
            violations.append({"path": r["_path"], "order_check": oc})
    return _res("G3", "ORDER_GATE", not violations, {"responses_checked": checked, "violations": violations,
                                                     "normalised_present": norm_idx is not None})


def g4_rejection(ws: Workspace) -> GateResult:
    try:
        runs = load_runs(ws)
    except BocgError as e:
        return _res("G4", "REJECTION_GATE", False, {"error": str(e)})
    norm_idx = _norm_index(ws)
    checked, violations = 0, []
    for r in runs:
        if r.get("status") == "ERROR":
            continue
        obj, err = parse_json(r["response_raw"])
        if err or not isinstance(obj, dict):
            continue
        checked += 1
        n = len(obj.get("rejected") or [])
        if n < 1 and not _marked_invalid(norm_idx, r, "REJECTED_EMPTY") and not _marked_invalid(norm_idx, r, "SCHEMA_INVALID"):
            violations.append({"path": r["_path"], "rejected_len": n})
    return _res("G4", "REJECTION_GATE", not violations, {"responses_checked": checked, "violations": violations})


def g5_admission(ws: Workspace) -> GateResult:
    if not ws.normalised_json.exists():
        return _res("G5", "ADMISSION_GATE", False, {"error": "normalised.json missing; run `bocg normalise`"})
    norm = read_json(ws.normalised_json)
    threshold = float(norm["threshold_usd"])
    try:
        runs = {(r["_model_dir"], int(r["sample_idx"])): r for r in load_runs(ws)}
    except BocgError as e:
        return _res("G5", "ADMISSION_GATE", False, {"error": str(e)})
    stale, overrides, arith = [], [], []
    n_div = 0
    for s in norm["samples"]:
        if s["status"] != "VALID":
            continue
        r = runs.get((s["model_dir"], int(s["sample_idx"])))
        if r is None:
            stale.append({"sample": [s["model_dir"], s["sample_idx"]], "reason": "run record missing"})
            continue
        obj, _ = parse_json(r["response_raw"])
        raw_divs = obj["divisions"]
        if len(raw_divs) != len(s["divisions"]):
            stale.append({"sample": [s["model_dir"], s["sample_idx"]], "reason": "division count differs"})
            continue
        for d, raw in zip(s["divisions"], raw_divs):
            n_div += 1
            adm = admission(raw, threshold)
            if adm.admitted != d["server_admitted"] or \
               abs(adm.addressable_seat_cost_recomputed - d["admission"]["addressable_seat_cost_recomputed"]) > 1e-6:
                stale.append({"sample": [s["model_dir"], s["sample_idx"]], "division": raw["name"],
                              "reason": "normalised admission differs from recompute"})
            if not adm.admitted:
                overrides.append({"model_id": s["model_id"], "sample_idx": s["sample_idx"], "name": raw["name"],
                                  "model_placement": "divisions", "server_placement": "rejected",
                                  "reasons": adm.reasons})
            if adm.arith_mismatch:
                arith.append({"model_id": s["model_id"], "sample_idx": s["sample_idx"], "name": raw["name"],
                              "model_value": adm.addressable_seat_cost_model,
                              "recomputed": adm.addressable_seat_cost_recomputed})
    return _res("G5", "ADMISSION_GATE", not stale, {"divisions_recomputed": n_div, "threshold_usd": threshold,
                                                    "self_placement_overridden": overrides,
                                                    "arith_mismatch": arith, "stale": stale})


def g6_corroboration(ws: Workspace) -> GateResult:
    if not ws.matrix_json.exists() or not ws.corroboration_csv.exists():
        return _res("G6", "CORROBORATION_GATE", False,
                    {"error": "matrix.json or corroboration.csv missing; run `bocg matrix` + `bocg corroborate`"})
    mx = read_json(ws.matrix_json)
    try:
        cols, rows = read_csv(ws.corroboration_csv)
        _check_columns(cols)
    except Exception as e:  # noqa: BLE001
        return _res("G6", "CORROBORATION_GATE", False, {"error": f"ledger unreadable: {e}"})
    summ = validate_ledger(mx, rows)
    failing = {}
    admitted = 0
    for key, d in summ["divisions"].items():
        if d["rejected_post_corroboration"]:
            continue     # not admitted -> no anchors counted
        admitted += 1
        if not d["publishable"]:
            failing[key] = {"verified_types": d["verified_types"], "a4_status": d["a4_status"],
                            "unverified_count": d["unverified_count"], "missing_rows": d["missing_rows"]}
    ok = not summ["problems"] and not failing
    return _res("G6", "CORROBORATION_GATE", ok, {"ledger_rows": len(rows), "admitted_divisions": admitted,
                                                 "rejected_post_corroboration": sorted(
                                                     k for k, d in summ["divisions"].items()
                                                     if d["rejected_post_corroboration"]),
                                                 "ledger_problems": summ["problems"], "failing": failing})


def g7_alias(ws: Workspace) -> GateResult:
    ev: dict = {}
    if not ws.aliases_yaml.exists() or not ws.aliases_sha256.exists():
        return _res("G7", "ALIAS_GATE", False, {"error": "aliases.yaml / aliases.sha256 missing"})
    actual = sha256_file(ws.aliases_yaml)
    published = _published_sha(ws.aliases_sha256)
    ev["aliases_sha256_actual"] = actual
    ev["aliases_sha256_published"] = published
    ok = actual == published
    try:
        table = load_aliases(ws.aliases_yaml)
    except BocgError as e:
        return _res("G7", "ALIAS_GATE", False, {**ev, "error": str(e)})
    ev["alias_entries"] = len(table.entries)
    ev["auto_generated"] = table.auto_generated
    if ws.matrix_json.exists():
        mx = read_json(ws.matrix_json)
        ev["matrix_aliases_sha256"] = mx["aliases_sha256"]
        ok &= mx["aliases_sha256"] == actual
        missing = sorted(k for k in mx["division_keys"] if k not in table.keys())
        ev["keys_without_alias"] = missing
        ok &= not missing
    else:
        ev["note"] = "matrix.json missing; key coverage not checked"
        ok = False
    return _res("G7", "ALIAS_GATE", bool(ok), ev)


def g8_self_assess(ws: Workspace) -> GateResult:
    ev: dict = {}
    if not ws.prompt_txt.exists():
        return _res("G8", "SELF_ASSESS_GATE", False, {"error": "prompt.txt missing"})
    text = ws.prompt_txt.read_text(encoding="utf-8") + "\n" + ws.system_txt.read_text(encoding="utf-8")
    ph = find_self_assessment(text, apply_allowlist=True)
    ev["prompt_hits"] = ph
    ok = not ph
    try:
        runs = load_runs(ws)
    except BocgError as e:
        return _res("G8", "SELF_ASSESS_GATE", False, {**ev, "error": str(e)})
    norm_idx = _norm_index(ws)
    invalidated, unmarked = [], []
    for r in runs:
        if r.get("status") == "ERROR":
            continue
        hits = find_self_assessment(r["response_raw"])
        if not hits:
            continue
        if _marked_invalid(norm_idx, r, "SELF_ASSESSMENT_LANGUAGE"):
            invalidated.append({"path": r["_path"], "hits": hits})
        else:
            unmarked.append({"path": r["_path"], "hits": hits})
    ev["responses_checked"] = len(runs)
    ev["responses_invalidated"] = invalidated
    ev["violations_not_marked_invalid"] = unmarked
    return _res("G8", "SELF_ASSESS_GATE", ok and not unmarked, ev)


def g9_repro(ws: Workspace) -> GateResult:
    if not ws.matrix_csv.exists() or not ws.run_meta.exists():
        return _res("G9", "REPRO_GATE", False, {"error": "matrix.csv or run_meta.json missing"})
    meta = read_json(ws.run_meta)
    fixtures = Path(meta["fixtures_dir"]) if meta.get("fixtures_dir") else ws.runs_dir(meta["prompt_sha8"])
    if not fixtures.is_dir():
        return _res("G9", "REPRO_GATE", False, {"error": f"replay source missing: {fixtures}"})
    from .matrix import write_matrix
    from .normalise import normalise_runs
    panel_d = meta["panel"]
    panel = Panel(models=[], samples=panel_d["samples"], threshold_usd=panel_d["params"]["threshold_usd"],
                  currency=panel_d["params"]["currency"], as_of_year=panel_d["params"]["as_of_year"],
                  temperature=panel_d["call"]["temperature"], top_p=panel_d["call"]["top_p"],
                  max_tokens=panel_d["call"]["max_tokens"], seed_base=panel_d["call"]["seed_base"])
    with tempfile.TemporaryDirectory(prefix="bocg-g9-") as td:
        tws = Workspace(td)
        quiet = lambda *a, **k: None  # noqa: E731
        run_panel(tws, panel, fixtures_dir=fixtures, echo=quiet)
        normalise_runs(tws, aliases_path=ws.aliases_yaml, echo=quiet)
        write_matrix(tws, echo=quiet)
        replay = tws.matrix_csv.read_bytes()
    original = ws.matrix_csv.read_bytes()
    ok = replay == original
    return _res("G9", "REPRO_GATE", ok, {"replay_source": str(fixtures), "matrix_sha256_original": sha256_text(original.decode()),
                                         "matrix_sha256_replay": sha256_text(replay.decode()), "byte_identical": ok})


def g10_panel(ws: Workspace) -> GateResult:
    try:
        runs = load_runs(ws)
    except BocgError as e:
        return _res("G10", "PANEL_GATE", False, {"error": str(e)})
    by_model: dict[str, dict] = {}
    not_cold, missing_params = [], []
    for r in runs:
        m = by_model.setdefault(r["model_id"], {"vendor": r.get("vendor"), "k": 0})
        m["k"] += 1
        req = r.get("request") or {}
        p = req.get("params") or {}
        for f in ("temperature", "top_p", "max_tokens", "seed"):
            if f not in p:
                missing_params.append({"path": r["_path"], "missing": f})
        cold = req.get("cold") or {}
        if cold.get("tools") is not False or cold.get("browsing") is not False or cold.get("retrieval") is not False \
                or cold.get("prior_turns") != 0 or not cold.get("provider_cold_guarantee", False):
            not_cold.append(r["_path"])
    vendors = sorted({m["vendor"] for m in by_model.values() if m["vendor"]})
    under = {mid: m["k"] for mid, m in by_model.items() if m["k"] < 3}
    # A panel is only as wide as the data it actually produced: a vendor whose calls errored or whose responses
    # were all rejected contributes nothing, and counting it would let a 2-vendor result be published as a
    # 4-vendor consensus. Vendor diversity is therefore measured on VALID samples, not on panel composition.
    valid_by_model: dict[str, int] = {}
    try:
        norm = read_json(ws.normalised_json)
        for s in norm.get("samples", []):
            if s.get("status") == "VALID":
                valid_by_model[s.get("model_id", "?")] = valid_by_model.get(s.get("model_id", "?"), 0) + 1
    except Exception as e:                                              # normalised.json absent => cannot assess
        return _res("G10", "PANEL_GATE", False, {"error": f"normalised.json required for validity-weighted panel check: {e}",
                                                 "vendors_declared": vendors})
    for mid, m in by_model.items():
        m["valid"] = valid_by_model.get(mid, 0)
    # A model that produced too little valid data may be dropped from the board ONLY by an explicit,
    # reasoned entry in exclusions.json. Silent tolerance would let a weak model be quietly ignored;
    # requiring the declaration keeps the exclusion auditable and publishable alongside the matrix.
    exclusions = {}
    if ws.root.joinpath("exclusions.json").exists():
        exclusions = {e["model_id"]: e for e in read_json(ws.root / "exclusions.json").get("excluded", [])}
    bad_exclusions = [mid for mid, e in exclusions.items()
                      if not str(e.get("reason", "")).strip() or mid not in by_model]
    vendors_with_data = sorted({m["vendor"] for mid, m in by_model.items()
                                if m["vendor"] and m["valid"] >= 3 and mid not in exclusions})
    short = {mid: m["valid"] for mid, m in by_model.items()
             if m["valid"] < 3 and mid not in exclusions}
    under = {mid: k for mid, k in under.items() if mid not in exclusions}
    ok = (len(vendors_with_data) >= 4 and not under and not short and not not_cold
          and not missing_params and not bad_exclusions)
    return _res("G10", "PANEL_GATE", ok, {"vendors_declared": vendors, "vendors_with_3plus_valid": vendors_with_data,
                                          "models": by_model, "models_under_3_samples": under,
                                          "models_under_3_valid": short, "excluded": exclusions,
                                          "invalid_exclusions": bad_exclusions,
                                          "not_cold": not_cold, "missing_params": missing_params})


GATES: dict[str, Callable[[Workspace], GateResult]] = {
    "G1": g1_contamination, "G2": g2_schema, "G3": g3_order, "G4": g4_rejection, "G5": g5_admission,
    "G6": g6_corroboration, "G7": g7_alias, "G8": g8_self_assess, "G9": g9_repro, "G10": g10_panel,
}


def run_gates(ws: Workspace, which: list[str] | None = None, write_report: bool = True) -> dict:
    ids = which or list(GATES)
    results = []
    for gid in ids:
        if gid not in GATES:
            raise BocgError(f"unknown gate {gid}; known: {list(GATES)}")
        try:
            results.append(GATES[gid](ws))
        except Exception as e:  # noqa: BLE001 - a crashing gate is a FAIL, never a silent pass
            results.append(_res(gid, GATES[gid].__name__, False, {"error": f"{type(e).__name__}: {e}"}))
    report = {"ts_utc": utc_now_iso(), "prompt_sha8": (read_json(ws.run_meta)["prompt_sha8"] if ws.run_meta.exists() else None),
              "all_pass": all(r["status"] == "PASS" for r in results), "gates": results}
    if write_report and not which:
        write_json(ws.gates_report, report)
    return report
