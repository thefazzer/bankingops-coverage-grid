#!/usr/bin/env python3
"""Build the Meridian-facing public-eval observatory projection.

Surfaces:
  - cleanroom-eval companion pin (version + commit; release may still be pending)
  - live LLMAJ case outcomes for public_benchmark cards (including empty
    intersection / paint_eligible=false), without promoting QUALIFIED paint
  - overlay paint summary (peer QUALIFIED vs public_benchmark voids)

    python3 tools/public_eval_observatory.py build
    python3 tools/public_eval_observatory.py check
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = ROOT / "reference/public-eval-llmaj-ledger.v1.json"
PREREG_PATH = ROOT / "reference/public-eval-llmaj-prereg.v1.json"
OVERLAY_PATH = ROOT / "reference/public-eval-surface-map.v1.json"
INVENTORY_PATH = ROOT / "reference/public-eval-inventory.v1.yaml"
OUT_PATH = ROOT / "reference/public-eval-observatory.v1.json"
SCHEMA_PATH = ROOT / "specs/public-eval-observatory.schema.json"
CLEANROOM_PIN_PATH = ROOT / "reference/cleanroom-eval-companion.v1.json"

SCHEMA = "bocg.public-eval-observatory/v1"
PAINT = {"QUALIFIED_MAPPING", "RATIFIED_MAPPING"}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_inventory() -> dict[str, dict]:
    """Minimal YAML inventory loader (id/title/url/class)."""
    text = INVENTORY_PATH.read_text(encoding="utf-8")
    items: dict[str, dict] = {}
    current: dict | None = None
    for raw in text.splitlines():
        if raw.startswith("  - id:"):
            if current and current.get("id"):
                items[current["id"]] = current
            current = {"id": raw.split(":", 1)[1].strip()}
            continue
        if current is None:
            continue
        m = re.match(r"    (title|url|class|access|checked_at):\s*(.*)$", raw)
        if m:
            current[m.group(1)] = m.group(2).strip()
    if current and current.get("id"):
        items[current["id"]] = current
    return items


def load_cleanroom_pin() -> dict:
    pin = json.loads(CLEANROOM_PIN_PATH.read_text(encoding="utf-8"))
    if pin.get("schema") != "bocg.cleanroom-eval-companion/v1":
        raise ValueError("cleanroom companion pin schema drift")
    if pin.get("version") != "1.2.0":
        raise ValueError("cleanroom companion pin must be 1.2.0 for this observatory")
    return pin


def short_title(inventory_id: str, inv: dict[str, dict]) -> str:
    title = (inv.get(inventory_id) or {}).get("title") or inventory_id
    # Prefer a shop-floor label over the full parenthetical title.
    return title.split(" (", 1)[0].strip()


def build_observatory() -> dict:
    ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    overlay = json.loads(OVERLAY_PATH.read_text(encoding="utf-8"))
    prereg = json.loads(PREREG_PATH.read_text(encoding="utf-8"))
    inventory = load_inventory()
    cleanroom = load_cleanroom_pin()

    cases = []
    paint_eligible = 0
    for case in ledger.get("cases") or []:
        inv_id = case["inventory_id"]
        inv = inventory.get(inv_id) or {}
        eligible = bool(case.get("paint_eligible"))
        if eligible:
            paint_eligible += 1
        primary = next(
            (s for s in case.get("sheets") or [] if s.get("assessor_id") == "judge-primary"),
            {},
        )
        sensitivity = next(
            (s for s in case.get("sheets") or [] if s.get("assessor_id") == "judge-sensitivity"),
            {},
        )
        cases.append(
            {
                "case_id": case["case_id"],
                "inventory_id": inv_id,
                "title": short_title(inv_id, inventory),
                "url": inv.get("url"),
                "inventory_class": inv.get("class"),
                "case_verdict": case.get("case_verdict"),
                "paint_eligible": eligible,
                "disagreement_note": case.get("disagreement_note"),
                "pass_rule_ref": case.get("pass_rule_ref"),
                "primary_promotion": primary.get("promotion_verdict"),
                "sensitivity_promotion": sensitivity.get("promotion_verdict"),
                "assessors": [
                    {
                        "assessor_id": s.get("assessor_id"),
                        "model_id": s.get("model_id"),
                        "promotion_verdict": s.get("promotion_verdict"),
                    }
                    for s in case.get("sheets") or []
                ],
            }
        )

    painted = []
    for row in overlay.get("rows") or []:
        if row.get("mapping_status") not in PAINT:
            continue
        inv = inventory.get(row.get("inventory_id") or "") or {}
        painted.append(
            {
                "row_id": row["row_id"],
                "inventory_id": row["inventory_id"],
                "title": short_title(row["inventory_id"], inventory),
                "url": inv.get("url"),
                "inventory_class": inv.get("class"),
                "mapping_status": row["mapping_status"],
                "division_key": row.get("division_key"),
                "depth": row.get("depth"),
                "band": row.get("band"),
                "rule_id": row.get("rule_id"),
                "llmaj_pass_ref": row.get("llmaj_pass_ref"),
                "rationale": row.get("rationale"),
            }
        )

    public_benchmark_ids = sorted(
        iid for iid, item in inventory.items() if item.get("class") == "public_benchmark"
    )
    covered = {c["inventory_id"] for c in cases}
    missing_llmaj = [iid for iid in public_benchmark_ids if iid not in covered]

    body = {
        "schema": SCHEMA,
        "bocg_release": dict(ledger.get("bocg_release") or {}),
        "prereg_sha256": ledger.get("prereg_sha256") or prereg.get("prereg_sha256"),
        "cleanroom_eval": {
            "repository": cleanroom["repository"],
            "version": cleanroom["version"],
            "commit_sha": cleanroom["commit_sha"],
            "release_tag": cleanroom.get("release_tag"),
            "release_status": cleanroom.get("release_status"),
            "bocg_companion_tag": cleanroom.get("bocg_companion_tag"),
            "url": cleanroom.get("url"),
            "notes": cleanroom.get("notes"),
        },
        "llmaj": {
            "rubric_id": ledger.get("rubric_id"),
            "rubric_version": ledger.get("rubric_version"),
            "pass_rule_ref": "public-eval-mapping/intersection-union/v1",
            "candidate_policy": "llmaj_output_only",
            "case_count": len(cases),
            "paint_eligible_count": paint_eligible,
            "public_benchmark_inventory_count": len(public_benchmark_ids),
            "missing_llmaj_inventory_ids": missing_llmaj,
            "headline": (
                "Live primary+sensitivity LLMAJ under the locked prereg produced "
                f"{paint_eligible} paint-eligible PASS case(s) across "
                f"{len(cases)} public_benchmark card(s). Empty mapping-key "
                "intersection on Mercor / Rogo / BankerToolBench → no "
                "public_benchmark QUALIFIED paint."
                if paint_eligible == 0
                else f"{paint_eligible} public_benchmark card(s) paint-eligible under locked prereg."
            ),
            "cases": cases,
        },
        "overlay_paint": {
            "painted_row_count": len(painted),
            "public_benchmark_painted_count": sum(
                1 for r in painted if r.get("inventory_class") == "public_benchmark"
            ),
            "rows": painted,
            "division_rollup_summary": (overlay.get("division_rollup") or {}).get("summary"),
        },
        "meridian": {
            "footer_harness": f"thefazzer/cleanroom-eval · {cleanroom['version']}",
            "latest_json_fields": ["cleanroom_eval", "public_eval"],
            "ui_ obligatory_cases": [
                "public.mercor_apex1_ib",
                "public.mercor_apex_agents",
                "public.rogo_big_finance_bench",
                "public.handshake_bankertoolbench",
            ],
        },
    }
    body["observatory_sha256"] = sha256_bytes(
        json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    return body


def observatory_problems(doc: dict) -> list[str]:
    problems: list[str] = []
    if doc.get("schema") != SCHEMA:
        problems.append(f"schema must be {SCHEMA}")
    pin = load_cleanroom_pin()
    cr = doc.get("cleanroom_eval") or {}
    if cr.get("version") != pin["version"]:
        problems.append("cleanroom_eval.version drifted from companion pin")
    if cr.get("commit_sha") != pin["commit_sha"]:
        problems.append("cleanroom_eval.commit_sha drifted from companion pin")
    llmaj = doc.get("llmaj") or {}
    cases = llmaj.get("cases") or []
    if llmaj.get("case_count") != len(cases):
        problems.append("llmaj.case_count does not match cases[]")
    if llmaj.get("paint_eligible_count") != sum(1 for c in cases if c.get("paint_eligible")):
        problems.append("llmaj.paint_eligible_count drift")
    required = set((doc.get("meridian") or {}).get("ui_obligatory_cases") or [])
    present = {c.get("inventory_id") for c in cases}
    missing = sorted(required - present)
    if missing:
        problems.append(f"missing obligatory LLMAJ cases for Meridian UI: {missing}")
    empty = [c["inventory_id"] for c in cases if not c.get("paint_eligible")]
    if required - set(empty) and llmaj.get("paint_eligible_count") == 0:
        # When nothing paints, every obligatory card must appear as non-eligible.
        still = sorted(required - set(empty))
        if still:
            problems.append(f"obligatory cards missing from non-eligible set: {still}")
    rebuilt = build_observatory()
    # Compare without sha (recomputed)
    left = {k: v for k, v in doc.items() if k != "observatory_sha256"}
    right = {k: v for k, v in rebuilt.items() if k != "observatory_sha256"}
    if left != right:
        problems.append("observatory body is stale; re-run build")
    return problems


def cmd_build() -> int:
    doc = build_observatory()
    OUT_PATH.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"wrote {OUT_PATH.relative_to(ROOT)} "
        f"cases={doc['llmaj']['case_count']} paint_eligible={doc['llmaj']['paint_eligible_count']} "
        f"cleanroom={doc['cleanroom_eval']['version']} sha={doc['observatory_sha256'][:12]}"
    )
    return 0


def cmd_check() -> int:
    if not OUT_PATH.is_file():
        print(f"FAIL missing {OUT_PATH.relative_to(ROOT)}")
        return 1
    doc = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    try:
        import jsonschema

        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        for err in sorted(
            jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).iter_errors(doc),
            key=lambda e: list(e.path),
        ):
            print("FAIL schema:", err.message)
            return 1
    except ImportError:
        pass
    problems = observatory_problems(doc)
    for problem in problems:
        print("FAIL", problem)
    if problems:
        return 1
    print(
        f"ok observatory cleanroom={doc['cleanroom_eval']['version']} "
        f"cases={doc['llmaj']['case_count']} paint_eligible={doc['llmaj']['paint_eligible_count']}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build")
    sub.add_parser("check")
    args = parser.parse_args(argv)
    if args.command == "build":
        return cmd_build()
    return cmd_check()


if __name__ == "__main__":
    raise SystemExit(main())
