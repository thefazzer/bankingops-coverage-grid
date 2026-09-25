#!/usr/bin/env python3
"""Public-eval LLMAJ adjudication: primary + sensitivity, intersection-union.

Qualitative mapping of public_benchmark inventory onto the BOCG surface is not a
one-pass owner ruling. Same discipline as five-families / downstream-evidence
model judges:

  - judge-primary and judge-sensitivity sheets are both required
  - disagreement is preserved (never averaged silently)
  - paint eligibility requires pass_rule public-eval-mapping/intersection-union/v1

Commands:
    python3 tools/public_eval_llmaj.py check [--ledger PATH] [--fixture PATH]
    python3 tools/public_eval_llmaj.py candidates
    python3 tools/public_eval_llmaj.py promote-gate
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RUBRIC_PATH = ROOT / "specs/rubrics/public-eval-mapping.yaml"
SCHEMA_PATH = ROOT / "specs/public-eval-llmaj.schema.json"
LEDGER_PATH = ROOT / "reference/public-eval-llmaj-ledger.v1.json"
FIXTURE_PATH = ROOT / "specs/fixtures/public-eval-llmaj-synthetic.json"
INVENTORY_PATH = ROOT / "reference/public-eval-inventory.v1.yaml"
OVERLAY_PATH = ROOT / "reference/public-eval-surface-map.v1.json"
PASS_RULE = "public-eval-mapping/intersection-union/v1"
REQUIRED_ASSESSORS = ("judge-primary", "judge-sensitivity")
FAMILIES = (
    "SURFACE_BINDING",
    "LIMITS_NAMED",
    "NEGATIVE_CONTROL",
    "EVIDENCE_ABLATION",
    "LATERAL_HIRE",
)
HARD_FAIL_FAMILIES = frozenset({"SURFACE_BINDING", "NEGATIVE_CONTROL"})
PAINT = frozenset({"QUALIFIED_MAPPING", "RATIFIED_MAPPING"})


def load_rubric() -> dict:
    return yaml.safe_load(RUBRIC_PATH.read_text(encoding="utf-8"))["rubric"]


def inventory_by_id() -> dict[str, dict]:
    inv = yaml.safe_load(INVENTORY_PATH.read_text(encoding="utf-8"))
    return {item["id"]: item for item in inv.get("artifacts") or []}


def sheet_by_assessor(case: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for sheet in case.get("sheets") or []:
        aid = sheet.get("assessor_id")
        if aid in out:
            raise ValueError(f"{case.get('case_id')}: duplicate assessor {aid}")
        out[aid] = sheet
    return out


def family_map(sheet: dict) -> dict[str, dict]:
    return {row["family_id"]: row for row in sheet.get("families") or []}


def recompute_case(case: dict) -> tuple[str, bool, str | None]:
    """Return (case_verdict, paint_eligible, disagreement_note)."""
    sheets = sheet_by_assessor(case)
    missing = [a for a in REQUIRED_ASSESSORS if a not in sheets]
    if missing:
        return "FAIL", False, f"missing required assessors: {missing}"

    primary = sheets["judge-primary"]
    sensitivity = sheets["judge-sensitivity"]
    p_map = family_map(primary)
    s_map = family_map(sensitivity)
    if set(p_map) != set(FAMILIES) or set(s_map) != set(FAMILIES):
        return "FAIL", False, "each sheet must judge all five families exactly once"

    notes: list[str] = []
    primary_pass = True
    sensitivity_pass = True

    for family in FAMILIES:
        pv = p_map[family]["verdict"]
        sv = s_map[family]["verdict"]
        if pv == "FAIL" and family in HARD_FAIL_FAMILIES:
            primary_pass = False
        if sv == "FAIL" and family in HARD_FAIL_FAMILIES:
            sensitivity_pass = False
        if pv not in {"PASS", "NOT_APPLICABLE"}:
            primary_pass = False
        if sv not in {"PASS", "NOT_APPLICABLE"}:
            sensitivity_pass = False
        if pv != sv:
            notes.append(f"{family}: primary={pv} sensitivity={sv}")

    p_promo = primary.get("promotion_verdict")
    s_promo = sensitivity.get("promotion_verdict")
    if p_promo != s_promo:
        notes.append(f"promotion_verdict: primary={p_promo} sensitivity={s_promo}")

    if p_promo == "PASS" and s_promo == "PASS" and primary_pass and sensitivity_pass:
        return "PASS", True, None if not notes else "; ".join(notes)

    if p_promo == "FAIL" and s_promo == "FAIL":
        return "FAIL", False, None if not notes else "; ".join(notes)

    # Disagreement or partial → UNCERTAIN, never paint.
    note = "; ".join(notes) if notes else "assessors did not jointly PASS under intersection-union"
    return "UNCERTAIN", False, note


def case_problems(case: dict, *, inventory: dict[str, dict], concepts_sha: str, tag: str) -> list[str]:
    problems: list[str] = []
    where = case.get("case_id") or "<case>"
    if case.get("pass_rule_ref") != PASS_RULE:
        problems.append(f"{where}: pass_rule_ref must be {PASS_RULE}")
    inv = inventory.get(case.get("inventory_id") or "")
    if inv is None:
        problems.append(f"{where}: unknown inventory_id")
    expected_verdict, expected_paint, expected_note = recompute_case(case)
    if case.get("case_verdict") != expected_verdict:
        problems.append(
            f"{where}: case_verdict {case.get('case_verdict')!r} != recomputed {expected_verdict!r}"
        )
    if bool(case.get("paint_eligible")) != expected_paint:
        problems.append(
            f"{where}: paint_eligible {case.get('paint_eligible')!r} != recomputed {expected_paint!r}"
        )
    if expected_note and not (case.get("disagreement_note") or "").strip():
        problems.append(f"{where}: disagreement/limits note required when judges do not jointly PASS")
    if case.get("paint_eligible") and inv and inv.get("class") != "public_benchmark":
        # LLMAJ paint path is defined for public_benchmark; method peers use other rules.
        problems.append(f"{where}: paint_eligible LLMAJ cases must target public_benchmark inventory")
    return problems


def ledger_problems(ledger: dict, *, allow_fixture_models: bool = False) -> list[str]:
    problems: list[str] = []
    rubric = load_rubric()
    if ledger.get("schema") != "bocg.public-eval-llmaj/v1":
        problems.append("ledger schema must be bocg.public-eval-llmaj/v1")
    if ledger.get("rubric_id") != rubric["id"]:
        problems.append("ledger rubric_id drift")
    if ledger.get("rubric_version") != rubric["version"]:
        problems.append("ledger rubric_version drift")
    concepts = json.loads((ROOT / "reference/task-concepts.v1.json").read_text(encoding="utf-8"))
    if ledger.get("bocg_release", {}).get("task_concepts_sha256") != concepts["task_concepts_sha256"]:
        problems.append("ledger is bound to a different task-concepts digest")
    inventory = inventory_by_id()
    seen: set[str] = set()
    for case in ledger.get("cases") or []:
        cid = case.get("case_id")
        if cid in seen:
            problems.append(f"duplicate case_id {cid}")
        seen.add(cid)
        problems.extend(
            case_problems(
                case,
                inventory=inventory,
                concepts_sha=concepts["task_concepts_sha256"],
                tag=str(ledger.get("bocg_release", {}).get("tag")),
            )
        )
        if not allow_fixture_models:
            for sheet in case.get("sheets") or []:
                mid = str(sheet.get("model_id") or "")
                if mid.startswith("fixture-"):
                    problems.append(
                        f"{cid}: live ledger cannot use fixture-* model_id ({mid}); "
                        "synthetic agreement does not paint production rows"
                    )
    return problems


def schema_validate(document: dict) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return []
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    return [
        err.message
        for err in sorted(
            jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).iter_errors(document),
            key=lambda e: list(e.path),
        )
    ]


def cmd_check(ledger_path: Path, fixture_path: Path | None) -> int:
    failed = False
    if fixture_path and fixture_path.is_file():
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        for msg in schema_validate(fixture):
            print("FAIL fixture schema:", msg)
            failed = True
        # Fixture may use fixture-* models; still must recompute intersection-union.
        for problem in ledger_problems(fixture, allow_fixture_models=True):
            # Reuse case recompute; skip live-model prohibition by flag.
            if "fixture-*" in problem or "live ledger cannot use fixture" in problem:
                continue
            print("FAIL fixture:", problem)
            failed = True
        # Explicit recompute-only pass for fixture cases:
        inventory = inventory_by_id()
        concepts = json.loads((ROOT / "reference/task-concepts.v1.json").read_text(encoding="utf-8"))
        for case in fixture.get("cases") or []:
            for problem in case_problems(
                case,
                inventory=inventory,
                concepts_sha=concepts["task_concepts_sha256"],
                tag=str(fixture.get("bocg_release", {}).get("tag")),
            ):
                print("FAIL fixture:", problem)
                failed = True
        if not failed:
            print(f"ok fixture cases={len(fixture.get('cases') or [])}")

    if ledger_path.is_file():
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        for msg in schema_validate(ledger):
            print("FAIL ledger schema:", msg)
            failed = True
        for problem in ledger_problems(ledger, allow_fixture_models=False):
            print("FAIL ledger:", problem)
            failed = True
        if not failed:
            print(f"ok ledger cases={len(ledger.get('cases') or [])}")
    else:
        print(f"ok ledger absent ({ledger_path.relative_to(ROOT)}); PENDING candidates wait for live LLMAJ")

    return 1 if failed else 0


def cmd_candidates() -> int:
    overlay = json.loads(OVERLAY_PATH.read_text(encoding="utf-8"))
    inventory = inventory_by_id()
    rows = []
    for row in overlay.get("rows") or []:
        if row.get("mapping_status") not in {"PROPOSED", "PENDING"}:
            continue
        inv = inventory.get(row.get("inventory_id") or "")
        if not inv or inv.get("class") != "public_benchmark":
            continue
        rows.append(
            {
                "row_id": row["row_id"],
                "inventory_id": row["inventory_id"],
                "division_key": row.get("division_key"),
                "depth": row.get("depth"),
                "band": row.get("band"),
                "rule_id": row.get("rule_id"),
                "status": row.get("mapping_status"),
            }
        )
    print(json.dumps({"pending_public_benchmark_candidates": rows}, indent=2))
    return 0


def cmd_promote_gate() -> int:
    """S9-G5: public_benchmark paint requires a live LLMAJ PASS case."""
    overlay = json.loads(OVERLAY_PATH.read_text(encoding="utf-8"))
    inventory = inventory_by_id()
    ledger_cases: dict[str, dict] = {}
    if LEDGER_PATH.is_file():
        ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
        problems = ledger_problems(ledger, allow_fixture_models=False)
        if problems:
            for problem in problems:
                print("FAIL", problem)
            return 1
        ledger_cases = {c["case_id"]: c for c in ledger.get("cases") or []}

    failed = False
    for row in overlay.get("rows") or []:
        if row.get("mapping_status") not in PAINT:
            continue
        inv = inventory.get(row.get("inventory_id") or "")
        if not inv:
            print(f"FAIL {row.get('row_id')}: unknown inventory")
            failed = True
            continue
        if inv.get("class") != "public_benchmark":
            # Method peers / rubrics may paint without LLMAJ (existing R-PEER-SHAPE seed).
            if row.get("llmaj_pass_ref"):
                print(f"FAIL {row.get('row_id')}: llmaj_pass_ref only valid for public_benchmark paint")
                failed = True
            continue
        ref = row.get("llmaj_pass_ref")
        if not ref:
            print(
                f"FAIL {row.get('row_id')}: public_benchmark QUALIFIED/RATIFIED requires "
                "llmaj_pass_ref from a live primary+sensitivity PASS case"
            )
            failed = True
            continue
        case = ledger_cases.get(ref)
        if case is None:
            print(f"FAIL {row.get('row_id')}: llmaj_pass_ref {ref!r} not in live ledger")
            failed = True
            continue
        if not case.get("paint_eligible") or case.get("case_verdict") != "PASS":
            print(f"FAIL {row.get('row_id')}: llmaj case {ref} is not paint-eligible PASS")
            failed = True
            continue
        if case.get("candidate_row_id") != row.get("row_id"):
            print(f"FAIL {row.get('row_id')}: llmaj case bound to a different candidate_row_id")
            failed = True
            continue
        if case.get("inventory_id") != row.get("inventory_id"):
            print(f"FAIL {row.get('row_id')}: llmaj case inventory mismatch")
            failed = True
    if failed:
        return 1
    print("ok promote-gate: no one-pass public_benchmark paint")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--ledger", type=Path, default=LEDGER_PATH)
    check.add_argument("--fixture", type=Path, default=FIXTURE_PATH)
    sub.add_parser("candidates")
    sub.add_parser("promote-gate")
    args = parser.parse_args(argv)
    if args.command == "check":
        return cmd_check(args.ledger, args.fixture)
    if args.command == "candidates":
        return cmd_candidates()
    return cmd_promote_gate()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
