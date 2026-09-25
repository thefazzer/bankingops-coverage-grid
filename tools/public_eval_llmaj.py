#!/usr/bin/env python3
"""Public-eval LLMAJ: front-loaded prereg + frozen observable prompt.

Qualitative mapping of public_benchmark inventory onto the BOCG surface is not a
one-pass owner ruling and not an owner-steered candidate list. Same purity bar
as SPEC-01 frozen prompt / FinExhaust prereg:

  - All parameters front-loaded in reference/public-eval-llmaj-prereg.v1.json
  - Single observable judge prompt for every inventory card (no per-artifact variants)
  - Primary + sensitivity sheets; disagreement preserved; intersection-union
  - No way to steer relative public-eval saturation or seller own coverage

Commands:
    python3 tools/public_eval_llmaj.py check
    python3 tools/public_eval_llmaj.py prereg-check
    python3 tools/public_eval_llmaj.py render-prompt --inventory-id ID --assessor judge-primary
    python3 tools/public_eval_llmaj.py inventory-cards
    python3 tools/public_eval_llmaj.py promote-gate
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RUBRIC_PATH = ROOT / "specs/rubrics/public-eval-mapping.yaml"
PROMPT_PATH = ROOT / "specs/prompts/public-eval-llmaj-judge.v1.txt"
PREREG_PATH = ROOT / "reference/public-eval-llmaj-prereg.v1.json"
PREREG_SCHEMA_PATH = ROOT / "specs/public-eval-llmaj-prereg.schema.json"
SCHEMA_PATH = ROOT / "specs/public-eval-llmaj.schema.json"
LEDGER_PATH = ROOT / "reference/public-eval-llmaj-ledger.v1.json"
FIXTURE_PATH = ROOT / "specs/fixtures/public-eval-llmaj-synthetic.json"
INVENTORY_PATH = ROOT / "reference/public-eval-inventory.v1.yaml"
OVERLAY_PATH = ROOT / "reference/public-eval-surface-map.v1.json"
CATALOGUE_PATH = ROOT / "reference/operating-catalogue.v1.json"
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
CANDIDATE = frozenset({"PROPOSED", "PENDING"})


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_sha(value: object) -> str:
    return sha256_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


def load_rubric() -> dict:
    return yaml.safe_load(RUBRIC_PATH.read_text(encoding="utf-8"))["rubric"]


def load_prereg() -> dict:
    return json.loads(PREREG_PATH.read_text(encoding="utf-8"))


def inventory_by_id() -> dict[str, dict]:
    inv = yaml.safe_load(INVENTORY_PATH.read_text(encoding="utf-8"))
    return {item["id"]: item for item in inv.get("artifacts") or []}


def inventory_card(item: dict) -> str:
    """Byte-stable card shape for every artifact — no owner commentary."""
    checked = item.get("checked_at")
    if hasattr(checked, "isoformat"):
        checked = checked.isoformat()
    return json.dumps(
        {
            "id": item["id"],
            "title": item["title"],
            "url": item["url"],
            "class": item["class"],
            "access": item.get("access"),
            "checked_at": checked,
        },
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )


def division_catalogue_text() -> str:
    catalogue = json.loads(CATALOGUE_PATH.read_text(encoding="utf-8"))
    rows = []
    for definition in catalogue["definitions"]:
        if definition.get("kind") != "division":
            continue
        rows.append(
            {
                "division_key": definition["division_key"],
                "label": definition.get("label"),
                "aliases": definition.get("aliases") or [],
            }
        )
    rows.sort(key=lambda r: r["division_key"])
    return json.dumps(rows, ensure_ascii=False, indent=2)


def render_judge_prompt(*, inventory_id: str, assessor_id: str) -> str:
    if assessor_id not in REQUIRED_ASSESSORS:
        raise ValueError(f"assessor_id must be one of {REQUIRED_ASSESSORS}")
    item = inventory_by_id().get(inventory_id)
    if item is None:
        raise ValueError(f"unknown inventory_id {inventory_id}")
    if item.get("class") != "public_benchmark":
        raise ValueError("frozen prompt is only for public_benchmark inventory cards")
    rubric = load_rubric()
    text = PROMPT_PATH.read_text(encoding="utf-8")
    replacements = {
        "{ASSESSOR_ID}": assessor_id,
        "{INVENTORY_CARD}": inventory_card(item),
        "{DIVISION_CATALOGUE}": division_catalogue_text(),
        "{RUBRIC_ID}": rubric["id"],
        "{RUBRIC_VERSION}": rubric["version"],
        "{RUBRIC_TEXT}": RUBRIC_PATH.read_text(encoding="utf-8"),
    }
    for key, value in replacements.items():
        text = text.replace(key, value)
    return text


def prereg_problems(prereg: dict | None = None) -> list[str]:
    problems: list[str] = []
    prereg = prereg or load_prereg()
    claimed = prereg.get("prereg_sha256")
    core = {k: v for k, v in prereg.items() if k != "prereg_sha256"}
    if claimed != canonical_sha(core):
        problems.append("prereg_sha256 does not match canonical prereg body")
    prompt_meta = prereg.get("observable_prompt") or {}
    if sha256_file(ROOT / prompt_meta.get("path", "")) != prompt_meta.get("sha256"):
        problems.append("observable prompt bytes drifted from prereg sha256")
    rubric_meta = prereg.get("rubric") or {}
    if sha256_file(ROOT / rubric_meta.get("path", "")) != rubric_meta.get("sha256"):
        problems.append("rubric bytes drifted from prereg sha256")
    inputs = prereg.get("inputs") or {}
    if sha256_file(ROOT / inputs.get("inventory_path", "")) != inputs.get("inventory_sha256"):
        problems.append("inventory bytes drifted from prereg sha256 (re-lock prereg after inventory edits)")
    if sha256_file(ROOT / inputs.get("catalogue_path", "")) != inputs.get("catalogue_sha256"):
        problems.append("catalogue bytes drifted from prereg sha256")
    concepts = json.loads((ROOT / "reference/task-concepts.v1.json").read_text(encoding="utf-8"))
    if inputs.get("task_concepts_sha256") != concepts["task_concepts_sha256"]:
        problems.append("prereg task_concepts_sha256 drift")
    if list(prereg.get("channels_in_saturation") or []) != ["public"]:
        problems.append("prereg channels_in_saturation must be exactly [public]")
    ni = prereg.get("non_influence") or {}
    if ni.get("relative_public_eval_saturation") != "forbidden_to_steer":
        problems.append("prereg must forbid steering relative public-eval saturation")
    if ni.get("seller_own_coverage") != "forbidden_to_steer":
        problems.append("prereg must forbid steering seller own coverage")
    if ni.get("owner_authored_candidate_rows") != "forbidden":
        problems.append("prereg must forbid owner-authored candidate rows")
    if ni.get("per_artifact_prompt_variants") != "forbidden":
        problems.append("prereg must forbid per-artifact prompt variants")
    if (prereg.get("candidate_policy") or {}).get("mode") != "llmaj_output_only":
        problems.append("candidate_policy.mode must be llmaj_output_only")
    for path in ni.get("forbidden_context_paths") or []:
        # Paths are denylist names; existence is allowed in-repo but must not enter judge context.
        if not str(path).strip():
            problems.append("empty forbidden_context_path")
    try:
        import jsonschema

        schema = json.loads(PREREG_SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        for err in jsonschema.Draft202012Validator(
            schema, format_checker=jsonschema.FormatChecker()
        ).iter_errors(prereg):
            problems.append(f"prereg schema: {err.message}")
    except ImportError:
        pass
    return problems


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
    note = "; ".join(notes) if notes else "assessors did not jointly PASS under intersection-union"
    return "UNCERTAIN", False, note


def case_problems(case: dict, *, inventory: dict[str, dict]) -> list[str]:
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
        problems.append(f"{where}: paint_eligible LLMAJ cases must target public_benchmark inventory")
    # Owner-staged candidate rows are forbidden under llmaj_output_only.
    if case.get("candidate_row_id"):
        problems.append(
            f"{where}: candidate_row_id is forbidden under llmaj_output_only "
            "(overlay rows are created from PASS cases, not owner staging)"
        )
    return problems


def ledger_problems(ledger: dict, *, allow_fixture_models: bool = False) -> list[str]:
    problems: list[str] = []
    rubric = load_rubric()
    prereg = load_prereg()
    if ledger.get("schema") != "bocg.public-eval-llmaj/v1":
        problems.append("ledger schema must be bocg.public-eval-llmaj/v1")
    if ledger.get("rubric_id") != rubric["id"]:
        problems.append("ledger rubric_id drift")
    if ledger.get("rubric_version") != rubric["version"]:
        problems.append("ledger rubric_version drift")
    if ledger.get("prereg_sha256") != prereg.get("prereg_sha256"):
        problems.append("ledger prereg_sha256 does not match locked prereg pack")
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
        problems.extend(case_problems(case, inventory=inventory))
        if not allow_fixture_models:
            for sheet in case.get("sheets") or []:
                mid = str(sheet.get("model_id") or "")
                if mid.startswith("fixture-"):
                    problems.append(
                        f"{cid}: live ledger cannot use fixture-* model_id ({mid}); "
                        "synthetic agreement does not paint production rows"
                    )
    return problems


def schema_validate(document: dict, schema_path: Path = SCHEMA_PATH) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return []
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    return [
        err.message
        for err in sorted(
            jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).iter_errors(document),
            key=lambda e: list(e.path),
        )
    ]


def overlay_non_influence_problems(overlay: dict) -> list[str]:
    """Owner cannot stage public_benchmark candidates or diverge from prereg weights."""
    problems: list[str] = []
    prereg = load_prereg()
    method = overlay.get("method") or {}
    if method.get("llmaj_prereg_sha256") != prereg.get("prereg_sha256"):
        problems.append("overlay method.llmaj_prereg_sha256 must equal locked prereg_sha256")
    if method.get("band_weights") != prereg.get("band_weights"):
        problems.append("overlay band_weights drifted from front-loaded prereg (steers relative saturation)")
    if list(method.get("channels_in_saturation") or []) != list(prereg.get("channels_in_saturation") or []):
        problems.append("overlay channels_in_saturation drifted from prereg")
    inventory = inventory_by_id()
    for row in overlay.get("rows") or []:
        inv = inventory.get(row.get("inventory_id") or "")
        if not inv:
            continue
        if inv.get("class") == "public_benchmark" and row.get("mapping_status") in CANDIDATE:
            problems.append(
                f"{row.get('row_id')}: owner-authored PROPOSED/PENDING public_benchmark row forbidden "
                "(llmaj_output_only; would steer relative saturation)"
            )
        if row.get("channel") in {"own_cell", "own_artifact"} and row.get("mapping_status") in PAINT:
            problems.append(f"{row.get('row_id')}: own channel cannot paint public-eval saturation")
    return problems


def cmd_prereg_check() -> int:
    problems = prereg_problems()
    for problem in problems:
        print("FAIL", problem)
    if problems:
        return 1
    prereg = load_prereg()
    print(f"ok prereg_sha256={prereg['prereg_sha256']} prompt_sha256={prereg['observable_prompt']['sha256']}")
    return 0


def cmd_check(ledger_path: Path, fixture_path: Path | None) -> int:
    failed = cmd_prereg_check() != 0
    overlay = json.loads(OVERLAY_PATH.read_text(encoding="utf-8"))
    for problem in overlay_non_influence_problems(overlay):
        print("FAIL", problem)
        failed = True

    if fixture_path and fixture_path.is_file():
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        for msg in schema_validate(fixture):
            print("FAIL fixture schema:", msg)
            failed = True
        for problem in ledger_problems(fixture, allow_fixture_models=True):
            if "live ledger cannot use fixture" in problem:
                continue
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
        print(f"ok ledger absent ({ledger_path.relative_to(ROOT)})")
    return 1 if failed else 0


def cmd_inventory_cards() -> int:
    """List public_benchmark cards that the frozen prompt can be rendered for."""
    cards = []
    for item in sorted(inventory_by_id().values(), key=lambda x: x["id"]):
        if item.get("class") != "public_benchmark":
            continue
        cards.append({"id": item["id"], "title": item["title"], "url": item["url"]})
    print(json.dumps({"public_benchmark_cards": cards, "prompt_path": PROMPT_PATH.relative_to(ROOT).as_posix()}, indent=2))
    return 0


def cmd_render_prompt(inventory_id: str, assessor_id: str) -> int:
    if prereg_problems():
        for problem in prereg_problems():
            print("FAIL", problem)
        return 1
    print(render_judge_prompt(inventory_id=inventory_id, assessor_id=assessor_id))
    return 0


def cmd_promote_gate() -> int:
    """S9-G5: public_benchmark paint requires live LLMAJ PASS under locked prereg."""
    if prereg_problems():
        for problem in prereg_problems():
            print("FAIL", problem)
        return 1
    overlay = json.loads(OVERLAY_PATH.read_text(encoding="utf-8"))
    for problem in overlay_non_influence_problems(overlay):
        print("FAIL", problem)
        return 1
    inventory = inventory_by_id()
    prereg = load_prereg()
    ledger_cases: dict[str, dict] = {}
    ledger_prereg = None
    if LEDGER_PATH.is_file():
        ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
        problems = ledger_problems(ledger, allow_fixture_models=False)
        if problems:
            for problem in problems:
                print("FAIL", problem)
            return 1
        ledger_prereg = ledger.get("prereg_sha256")
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
            if row.get("llmaj_pass_ref"):
                print(f"FAIL {row.get('row_id')}: llmaj_pass_ref only valid for public_benchmark paint")
                failed = True
            continue
        ref = row.get("llmaj_pass_ref")
        if not ref:
            print(
                f"FAIL {row.get('row_id')}: public_benchmark QUALIFIED/RATIFIED requires "
                "llmaj_pass_ref from a live primary+sensitivity PASS case under the locked prereg"
            )
            failed = True
            continue
        if ledger_prereg != prereg.get("prereg_sha256"):
            print(f"FAIL {row.get('row_id')}: live ledger is not bound to the locked prereg")
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
        if case.get("inventory_id") != row.get("inventory_id"):
            print(f"FAIL {row.get('row_id')}: llmaj case inventory mismatch")
            failed = True
            continue
        if case.get("proposed_division_key") != row.get("division_key"):
            print(f"FAIL {row.get('row_id')}: llmaj case division mismatch")
            failed = True
            continue
    if failed:
        return 1
    print("ok promote-gate: front-loaded prereg; no owner-steered public_benchmark paint")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--ledger", type=Path, default=LEDGER_PATH)
    check.add_argument("--fixture", type=Path, default=FIXTURE_PATH)
    sub.add_parser("prereg-check")
    sub.add_parser("inventory-cards")
    render = sub.add_parser("render-prompt")
    render.add_argument("--inventory-id", required=True)
    render.add_argument("--assessor", default="judge-primary", choices=list(REQUIRED_ASSESSORS))
    sub.add_parser("promote-gate")
    args = parser.parse_args(argv)
    if args.command == "check":
        return cmd_check(args.ledger, args.fixture)
    if args.command == "prereg-check":
        return cmd_prereg_check()
    if args.command == "inventory-cards":
        return cmd_inventory_cards()
    if args.command == "render-prompt":
        return cmd_render_prompt(args.inventory_id, args.assessor)
    return cmd_promote_gate()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
