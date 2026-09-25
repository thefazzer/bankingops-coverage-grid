#!/usr/bin/env python3
"""Public-eval surface overlay: validate and roll up division saturation/voids.

Likelihood-matched projection of *public* rubrics/benchmarks/evals onto the
SPEC-08 episode-surface depth ladder. Painted rows
(QUALIFIED_MAPPING / RATIFIED_MAPPING on channel=public, paint-eligible inventory
class) drive saturation; admitted divisions with zero painted rows are voids.

BOCG control-point cells and their citations are not public evals and must not
paint. Own rubrics/evals use channel=own_artifact or own_cell and never paint.

    python3 tools/public_eval_overlay.py check
    python3 tools/public_eval_overlay.py build
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = ROOT / "reference/public-eval-inventory.v1.yaml"
OVERLAY_PATH = ROOT / "reference/public-eval-surface-map.v1.json"
SCHEMA_PATH = ROOT / "specs/public-eval-surface-overlay.schema.json"
PAINT = frozenset({"QUALIFIED_MAPPING", "RATIFIED_MAPPING"})
PAINT_CLASSES = frozenset(
    {"peer_framework", "peer_task_shape", "public_benchmark", "public_rubric"}
)
ID_FIELD_FOR_DEPTH = {
    "function_concept": "function_concept_id",
    "task_concept": "task_concept_id",
    "terminal_task": "task_reference_id",
    "control_point": "control_point_id",
}
BAND_WEIGHTS = {"L1": 1, "L2": 2, "L3": 3}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_inventory() -> dict:
    return yaml.safe_load(INVENTORY_PATH.read_text(encoding="utf-8"))


def inventory_digest() -> str:
    return sha256_file(INVENTORY_PATH)


def inventory_by_id(inventory: dict) -> dict[str, dict]:
    return {item["id"]: item for item in inventory.get("artifacts") or []}


def matrix_tiers() -> dict[str, str]:
    path = ROOT / "live-run-20260826/matrix.csv"
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as handle:
        return {row["division_key"]: row["tier"] for row in csv.DictReader(handle)}


def review_status_by_division(concepts: dict) -> dict[str, str]:
    return {d["division_key"]: d["review_status"] for d in concepts["divisions"]}


def admitted_divisions(catalogue: dict) -> list[str]:
    return sorted(
        d["division_key"]
        for d in catalogue["definitions"]
        if d["kind"] == "division"
    )


def paint_weight(row: dict, weights: dict[str, int], inv_item: dict | None) -> int:
    if row.get("mapping_status") not in PAINT:
        return 0
    if row.get("channel") != "public":
        return 0
    if not inv_item or inv_item.get("class") not in PAINT_CLASSES:
        return 0
    band = row.get("band")
    if band not in weights:
        return 0
    return int(weights[band])


def compute_division_rollup(overlay: dict, *, root: Path = ROOT) -> dict:
    concepts = json.loads((root / "reference/task-concepts.v1.json").read_text(encoding="utf-8"))
    catalogue = json.loads((root / "reference/operating-catalogue.v1.json").read_text(encoding="utf-8"))
    inventory = load_inventory()
    by_inv = inventory_by_id(inventory)
    tiers = matrix_tiers()
    reviews = review_status_by_division(concepts)
    weights = dict(overlay["method"]["band_weights"])
    by_div: dict[str, list[dict]] = {key: [] for key in admitted_divisions(catalogue)}
    for row in overlay.get("rows") or []:
        inv_item = by_inv.get(row.get("inventory_id") or "")
        if paint_weight(row, weights, inv_item) <= 0:
            continue
        key = row.get("division_key")
        if key in by_div:
            by_div[key].append(row)
    divisions = []
    max_sat = 0
    painted_divs = 0
    painted_rows = 0
    for key in sorted(by_div):
        rows = by_div[key]
        sat = sum(paint_weight(r, weights, by_inv.get(r["inventory_id"])) for r in rows)
        max_sat = max(max_sat, sat)
        if rows:
            painted_divs += 1
            painted_rows += len(rows)
        divisions.append(
            {
                "division_key": key,
                "review_status": reviews.get(key, "AUTO"),
                "matrix_tier": tiers.get(key, "UNKNOWN"),
                "painted_rows": len(rows),
                "saturation": sat,
                "void": len(rows) == 0,
                "row_ids": [r["row_id"] for r in rows],
            }
        )
    return {
        "grain": "division",
        "band_weights": weights,
        "divisions": divisions,
        "summary": {
            "admitted_divisions": len(divisions),
            "painted_divisions": painted_divs,
            "void_divisions": len(divisions) - painted_divs,
            "painted_rows": painted_rows,
            "max_saturation": max_sat,
        },
    }


def overlay_problems(overlay: dict, *, root: Path = ROOT) -> list[str]:
    problems: list[str] = []
    concepts = json.loads((root / "reference/task-concepts.v1.json").read_text(encoding="utf-8"))
    catalogue = json.loads((root / "reference/operating-catalogue.v1.json").read_text(encoding="utf-8"))
    inventory = load_inventory()
    by_inv = inventory_by_id(inventory)
    concept_ids = {c["concept_id"]: c for c in concepts["concepts"]}
    definitions = {d["reference_id"]: d for d in catalogue["definitions"]}
    divisions = {d["division_key"] for d in catalogue["definitions"] if d["kind"] == "division"}
    cells = {p.stem for p in (root / "cells").glob("*.json")}

    if overlay.get("bocg_release", {}).get("task_concepts_sha256") != concepts["task_concepts_sha256"]:
        problems.append("overlay is bound to a different task-concepts digest")
    if overlay.get("inventory_sha256") != inventory_digest():
        problems.append("overlay inventory_sha256 does not match reference/public-eval-inventory.v1.yaml")

    method = overlay.get("method") or {}
    if set(method.get("paint_statuses") or []) != PAINT:
        problems.append("method.paint_statuses must be exactly QUALIFIED_MAPPING and RATIFIED_MAPPING")
    if method.get("band_weights") != BAND_WEIGHTS:
        problems.append("method.band_weights must be L1=1, L2=2, L3=3 for this release")
    if set(method.get("channels_in_saturation") or []) != {"public"}:
        problems.append("method.channels_in_saturation must be exactly ['public']")
    if set(method.get("paint_inventory_classes") or []) != PAINT_CLASSES:
        problems.append("method.paint_inventory_classes must be the public-eval class set only")
    if not method.get("llmaj_prereg_sha256"):
        problems.append("method.llmaj_prereg_sha256 is required (front-loaded LLMAJ prereg)")
    else:
        from public_eval_llmaj import overlay_non_influence_problems

        problems.extend(overlay_non_influence_problems(overlay))

    seen_rows: set[str] = set()
    for index, row in enumerate(overlay.get("rows") or []):
        where = f"row {index} ({row.get('row_id')})"
        rid = row.get("row_id")
        if rid in seen_rows:
            problems.append(f"{where}: duplicate row_id")
        seen_rows.add(rid)
        inv_id = row.get("inventory_id")
        inv_item = by_inv.get(inv_id or "")
        if inv_item is None:
            problems.append(f"{where}: unknown inventory_id")
        status = row.get("mapping_status")
        division = row.get("division_key")
        depth = row.get("depth")
        channel = row.get("channel")
        if status in PAINT:
            if channel != "public":
                problems.append(f"{where}: painted row must use channel=public")
            if inv_item and inv_item.get("class") not in PAINT_CLASSES:
                problems.append(
                    f"{where}: inventory class {inv_item.get('class')!r} cannot paint "
                    "(not a public rubric/benchmark/eval)"
                )
            if inv_item and inv_item.get("class") in {"own_rubric", "own_eval", "control_point_citation"}:
                problems.append(f"{where}: BOCG-own or citation inventory cannot paint public-eval saturation")
            if division not in divisions:
                problems.append(f"{where}: painted row needs an admitted division_key")
            if depth not in ID_FIELD_FOR_DEPTH and depth != "division":
                problems.append(f"{where}: painted row needs a SPEC-08 depth")
            if row.get("band") not in BAND_WEIGHTS:
                problems.append(f"{where}: painted row needs band L1|L2|L3")
            if not row.get("ruling"):
                problems.append(f"{where}: painted row needs a ruling")
            if not (row.get("rationale") or "").strip():
                problems.append(f"{where}: painted row needs a rationale")
        elif division is not None and division not in divisions:
            if status not in {"DEFERRED_MAPPING", "REJECTED_MAPPING"}:
                problems.append(f"{where}: unknown division {division!r}")
        field = ID_FIELD_FOR_DEPTH.get(depth) if depth else None
        if field and not row.get(field):
            problems.append(f"{where}: depth {depth} needs {field}")
        for key, kind in (("function_concept_id", "function_concept"), ("task_concept_id", "task_concept")):
            value = row.get(key)
            if value is None:
                continue
            concept = concept_ids.get(value)
            if concept is None:
                problems.append(f"{where}: {key} is not a released concept")
            elif concept["kind"] != kind or (division and concept["division_key"] != division):
                problems.append(f"{where}: {key} belongs to another kind or division")
        task_ref = row.get("task_reference_id")
        if task_ref is not None:
            definition = definitions.get(task_ref)
            if definition is None or definition["kind"] != "task" or (
                division and definition["division_key"] != division
            ):
                problems.append(f"{where}: task_reference_id is not a released task of the division")
            elif row.get("task_concept_id") in concept_ids:
                if task_ref not in concept_ids[row["task_concept_id"]]["members"]:
                    problems.append(f"{where}: task_reference_id is not a member of task_concept_id")
        cell = row.get("control_point_id")
        if cell is not None:
            if cell not in cells:
                problems.append(f"{where}: control_point_id is not a released cell")
            else:
                cell_division = json.loads(
                    (root / "cells" / f"{cell}.json").read_text(encoding="utf-8")
                ).get("division_key")
                if cell_division in divisions and division and cell_division != division:
                    problems.append(f"{where}: control_point_id belongs to another division")
                if status in PAINT:
                    problems.append(
                        f"{where}: control_point depth must not paint public-eval saturation "
                        "(BOCG cell coverage is not a public eval)"
                    )

    expected = compute_division_rollup(overlay, root=root)
    if overlay.get("division_rollup") != expected:
        problems.append("division_rollup does not match painted public-eval rows / band weights")
    return problems


def refresh_rollup_and_digest(overlay: dict) -> dict:
    overlay = dict(overlay)
    overlay["inventory_sha256"] = inventory_digest()
    overlay["division_rollup"] = compute_division_rollup(overlay)
    return overlay


def cmd_build() -> int:
    overlay = json.loads(OVERLAY_PATH.read_text(encoding="utf-8"))
    method = dict(overlay.get("method") or {})
    method.setdefault(
        "paint_inventory_classes",
        sorted(PAINT_CLASSES),
    )
    overlay["method"] = method
    overlay = refresh_rollup_and_digest(overlay)
    OVERLAY_PATH.write_text(json.dumps(overlay, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OVERLAY_PATH.relative_to(ROOT)}")
    print("summary:", overlay["division_rollup"]["summary"])
    return 0


def cmd_check() -> int:
    overlay = json.loads(OVERLAY_PATH.read_text(encoding="utf-8"))
    try:
        import jsonschema

        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        errors = sorted(
            jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).iter_errors(overlay),
            key=lambda e: list(e.path),
        )
        for err in errors:
            print("FAIL schema:", err.message)
        schema_failed = bool(errors)
    except ImportError:
        schema_failed = False
        print("WARN jsonschema not installed; schema check skipped")
    problems = overlay_problems(overlay)
    for problem in problems:
        print("FAIL", problem)
    # S9-G5: public_benchmark paint is LLMAJ multi-pass only (never one-pass owner).
    from public_eval_llmaj import cmd_promote_gate

    promote_rc = cmd_promote_gate()
    if schema_failed or problems or promote_rc != 0:
        return 1
    summary = overlay["division_rollup"]["summary"]
    print(
        f"ok painted={summary['painted_divisions']} voids={summary['void_divisions']} "
        f"rows={summary['painted_rows']} max_sat={summary['max_saturation']}"
    )
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "build"))
    args = parser.parse_args(argv)
    if args.command == "check":
        return cmd_check()
    return cmd_build()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
