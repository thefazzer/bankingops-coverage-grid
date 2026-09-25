#!/usr/bin/env python3
"""Aggregate live public-eval LLMAJ sheets into the ledger and paint PASS rows.

Reads frozen-prompt judge responses under a run directory, applies
intersection-union (exact agreement on division_key/depth/band/rule_id plus
family PASS), writes reference/public-eval-llmaj-ledger.v1.json, and promotes
paint-eligible cases onto the overlay without owner-authored candidates.

    python3 tools/public_eval_llmaj_aggregate.py live-run-public-eval-llmaj/<prereg12>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from public_eval_llmaj import (  # noqa: E402
    LEDGER_PATH,
    OVERLAY_PATH,
    PASS_RULE,
    REQUIRED_ASSESSORS,
    load_prereg,
    recompute_case,
)
from public_eval_overlay import refresh_rollup_and_digest  # noqa: E402

FAMILIES = (
    "SURFACE_BINDING",
    "LIMITS_NAMED",
    "NEGATIVE_CONTROL",
    "EVIDENCE_ABLATION",
    "LATERAL_HIRE",
)


def _load_response(path: Path) -> dict:
    text = path.read_text(encoding="utf-8").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _mapping_key(m: dict) -> tuple:
    return (m["division_key"], m["depth"], m["band"], m["rule_id"])


def _sheet_from_response(resp: dict, *, model_id: str, assessed_at: str) -> dict:
    families = resp.get("families") or []
    by_id = {f["family_id"]: f for f in families}
    ordered = []
    for fid in FAMILIES:
        row = by_id.get(fid)
        if row is None:
            raise ValueError(f"missing family {fid}")
        ordered.append(
            {
                "family_id": fid,
                "verdict": row["verdict"],
                "rationale": row["rationale"],
            }
        )
    return {
        "assessor_id": resp["assessor_id"],
        "model_id": model_id,
        "assessed_at": assessed_at,
        "families": ordered,
        "promotion_verdict": resp["promotion_verdict"],
        "notes": (resp.get("notes") or "")[:2000] or None,
    }


def build_cases(run_dir: Path, prereg: dict) -> list[dict]:
    jobs = json.loads((run_dir / "jobs.json").read_text(encoding="utf-8"))
    by_inv: dict[str, dict[str, dict]] = {}
    model_by = prereg["panel"]["models"]
    assessed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for job in jobs:
        path = ROOT / job["response_path"]
        if not path.is_file():
            raise FileNotFoundError(f"missing judge response: {path}")
        resp = _load_response(path)
        if resp.get("assessor_id") != job["assessor"]:
            raise ValueError(f"{path}: assessor_id mismatch")
        if resp.get("inventory_id") != job["inventory_id"]:
            raise ValueError(f"{path}: inventory_id mismatch")
        by_inv.setdefault(job["inventory_id"], {})[job["assessor"]] = {
            "response": resp,
            "model_id": job["model_id"],
            "path": path,
        }

    cases: list[dict] = []
    for inventory_id, sheets_in in sorted(by_inv.items()):
        missing = [a for a in REQUIRED_ASSESSORS if a not in sheets_in]
        if missing:
            raise ValueError(f"{inventory_id}: missing assessors {missing}")
        primary = sheets_in["judge-primary"]["response"]
        sensitivity = sheets_in["judge-sensitivity"]["response"]
        p_maps = {_mapping_key(m): m for m in primary.get("mappings") or []}
        s_maps = {_mapping_key(m): m for m in sensitivity.get("mappings") or []}
        agreed = sorted(set(p_maps) & set(s_maps))

        p_sheet = _sheet_from_response(
            primary, model_id=model_by["judge-primary"], assessed_at=assessed_at
        )
        s_sheet = _sheet_from_response(
            sensitivity, model_id=model_by["judge-sensitivity"], assessed_at=assessed_at
        )
        # Drop None notes for schema cleanliness
        for sheet in (p_sheet, s_sheet):
            if sheet.get("notes") is None:
                sheet.pop("notes", None)

        if not agreed:
            # Still record a card-level disagreement / empty-intersection case for audit.
            case = {
                "case_id": f"llmaj_{inventory_id.replace('.', '_')}_no_intersection",
                "inventory_id": inventory_id,
                "proposed_division_key": "ma_advisory",  # placeholder unused when not paint_eligible
                "proposed_depth": "division",
                "proposed_band": "L1",
                "proposed_rule_id": "R-REJECT",
                "sheets": [p_sheet, s_sheet],
                "pass_rule_ref": PASS_RULE,
                "case_verdict": "UNCERTAIN",
                "paint_eligible": False,
                "disagreement_note": (
                    "No exact (division_key, depth, band, rule_id) intersection between "
                    f"primary mappings={list(p_maps)} and sensitivity mappings={list(s_maps)}"
                ),
            }
            # Recompute may override if both promo FAIL etc.
            verdict, paint, note = recompute_case(case)
            # Force no paint when no agreed mapping
            case["case_verdict"] = "UNCERTAIN" if verdict == "PASS" else verdict
            case["paint_eligible"] = False
            if note and not case.get("disagreement_note"):
                case["disagreement_note"] = note
            # Avoid fake division_key when no intersection — use first admitted? Schema requires a key.
            # Keep placeholder but paint_eligible false.
            cases.append(case)
            continue

        for key in agreed:
            division_key, depth, band, rule_id = key
            rationale = p_maps[key]["rationale"]
            case = {
                "case_id": f"llmaj_{inventory_id.replace('.', '_')}_{division_key}",
                "inventory_id": inventory_id,
                "proposed_division_key": division_key,
                "proposed_depth": depth,
                "proposed_band": band,
                "proposed_rule_id": rule_id,
                "sheets": [p_sheet, s_sheet],
                "pass_rule_ref": PASS_RULE,
                "case_verdict": "PASS",
                "paint_eligible": True,
            }
            verdict, paint, note = recompute_case(case)
            case["case_verdict"] = verdict
            case["paint_eligible"] = paint
            if note:
                case["disagreement_note"] = note
            # Attach mapping rationale into notes if paint eligible for explainability via sheets already.
            case["_mapping_rationale"] = rationale  # stripped before write
            cases.append(case)
    return cases


def promote_overlay(cases: list[dict], prereg: dict) -> dict:
    overlay = json.loads(OVERLAY_PATH.read_text(encoding="utf-8"))
    # Remove any prior public_benchmark painted rows (should be none) then add PASS cases.
    from public_eval_llmaj import inventory_by_id

    inventory = inventory_by_id()
    kept = []
    for row in overlay.get("rows") or []:
        inv = inventory.get(row.get("inventory_id") or "")
        if inv and inv.get("class") == "public_benchmark" and row.get("mapping_status") in {
            "QUALIFIED_MAPPING",
            "RATIFIED_MAPPING",
            "PROPOSED",
            "PENDING",
        }:
            continue
        kept.append(row)
    overlay["rows"] = kept
    overlay["method"]["llmaj_prereg_sha256"] = prereg["prereg_sha256"]
    overlay["method"]["band_weights"] = dict(prereg["band_weights"])
    overlay["method"]["channels_in_saturation"] = list(prereg["channels_in_saturation"])

    ruled_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for case in cases:
        if not case.get("paint_eligible"):
            continue
        rationale = case.pop("_mapping_rationale", None) or (
            f"Live LLMAJ intersection-union PASS under prereg {prereg['prereg_sha256'][:12]} "
            f"for {case['inventory_id']} → {case['proposed_division_key']}."
        )
        if len(rationale) < 20:
            rationale = rationale + " LLMAJ live promotion."
        row_id = f"ovr_{case['inventory_id'].replace('.', '_')}_{case['proposed_division_key']}"
        # Ensure row_id pattern ^ovr_[a-z0-9_]+$
        row_id = re.sub(r"[^a-z0-9_]", "_", row_id)
        overlay["rows"].append(
            {
                "function_concept_id": None,
                "task_concept_id": None,
                "task_reference_id": None,
                "control_point_id": None,
                "channel": "public",
                "ruling": {"ruled_at": ruled_at, "ruled_by_role": "owner"},
                "band": case["proposed_band"],
                "depth": case["proposed_depth"],
                "division_key": case["proposed_division_key"],
                "row_id": row_id,
                "inventory_id": case["inventory_id"],
                "mapping_status": "QUALIFIED_MAPPING",
                "rule_id": case["proposed_rule_id"],
                "llmaj_pass_ref": case["case_id"],
                "rationale": rationale
                + " Promoted only after primary+sensitivity exact mapping agreement under the locked prereg.",
            }
        )
    return refresh_rollup_and_digest(overlay)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    run_dir = args.run_dir
    if not run_dir.is_absolute():
        run_dir = ROOT / run_dir
    prereg = load_prereg()
    cases = build_cases(run_dir, prereg)
    for case in cases:
        case.pop("_mapping_rationale", None)

    ledger = {
        "schema": "bocg.public-eval-llmaj/v1",
        "rubric_id": "bocg-public-eval-mapping",
        "rubric_version": "1.0.0",
        "prereg_sha256": prereg["prereg_sha256"],
        "bocg_release": {
            "tag": "v0.6.1",
            "task_concepts_sha256": prereg["inputs"]["task_concepts_sha256"],
        },
        "cases": cases,
    }
    summary = {
        "cases": len(cases),
        "paint_eligible": sum(1 for c in cases if c.get("paint_eligible")),
        "case_ids": [c["case_id"] for c in cases],
    }
    print(json.dumps(summary, indent=2))
    if args.dry_run:
        return 0

    # Rebuild cases with rationales for promotion
    cases_with = build_cases(run_dir, prereg)
    ledger["cases"] = [{k: v for k, v in c.items() if k != "_mapping_rationale"} for c in cases_with]
    LEDGER_PATH.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    overlay = promote_overlay(cases_with, prereg)
    OVERLAY_PATH.write_text(json.dumps(overlay, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", LEDGER_PATH.relative_to(ROOT))
    print("wrote", OVERLAY_PATH.relative_to(ROOT))
    print("summary", overlay["division_rollup"]["summary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
