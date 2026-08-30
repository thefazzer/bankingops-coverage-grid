#!/usr/bin/env python3
"""SPEC-03 runnable gates: S3-G1..G4. Exit non-zero on any failure."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILURES: list[str] = []


def fail(msg: str) -> None:
    FAILURES.append(msg)


def gate_cells() -> None:
    """S3-G1 citations, S3-G2 consequence anchors, schema validity."""
    schema = json.loads((ROOT / "specs/control-point-cell.schema.json").read_text())
    try:
        import jsonschema
        validator = jsonschema.Draft202012Validator(schema)
    except ImportError:
        validator = None
    for path in sorted((ROOT / "cells").glob("*.json")):
        try:
            cell = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            fail(f"S3-G1 {path.name}: invalid JSON ({exc})")
            continue
        if validator:
            for err in validator.iter_errors(cell):
                fail(f"S3-G1 {path.name}: schema: {err.message[:120]}")
        for i, cit in enumerate(cell.get("citations") or []):
            if not str(cit.get("url", "")).startswith("http"):
                fail(f"S3-G1 {path.name}: citation {i} has no URL")
        anchor = cell.get("consequence_anchor") or {}
        if not anchor.get("public_source"):
            fail(f"S3-G2 {path.name}: consequence anchor lacks public_source")
        if re.search(r"\d+\.\d{3,}", str(anchor.get("magnitude_band", ""))):
            fail(f"S3-G2 {path.name}: magnitude_band has invented precision")


def gate_deny() -> None:
    """S3-G3: forbidden tokens in cells and SPEC-03."""
    literals, patterns = [], []
    sources = [ROOT / "tools/forbidden_cells.txt"]
    local = ROOT / "tools/forbidden_cells.local.txt"   # untracked seller list
    if local.is_file():
        sources.append(local)
    for source in sources:
        for line in source.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("regex:"):
                patterns.append(re.compile(line[6:], re.I))
            else:
                literals.append(line.lower())
    targets = list((ROOT / "cells").glob("*.json")) + [ROOT / "specs/SPEC-03-control-point-cells.md"]
    for path in targets:
        text = path.read_text(encoding="utf-8", errors="replace")
        lowered = text.lower()
        for token in literals:
            if token in lowered:
                fail(f"S3-G3 {path.name}: forbidden token (from deny list)")
        for pattern in patterns:
            if pattern.search(text):
                fail(f"S3-G3 {path.name}: forbidden pattern {pattern.pattern!r}")


def gate_conformance_doc() -> None:
    """S3-G4: CONFORMANCE.md rows intact and statused."""
    doc = (ROOT / "CONFORMANCE.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| (\d+) \| .+ \| (EVIDENCED|PARTIAL|NOT MET) \|", doc, re.M)
    if len(rows) < 15:
        fail(f"S3-G4 CONFORMANCE.md: {len(rows)} statused rows found, baseline is 15")
    numbers = [int(r[0]) for r in rows]
    if numbers != list(range(1, len(numbers) + 1)):
        fail("S3-G4 CONFORMANCE.md: row numbering broken (row removed or reordered)")


def main() -> int:
    gate_cells()
    gate_deny()
    gate_conformance_doc()
    if FAILURES:
        print("GATE FAILURES:")
        for f in FAILURES:
            print("  ", f)
        return 1
    cells = len(list((ROOT / "cells").glob("*.json")))
    print(f"all SPEC-03 gates pass ({cells} cells, CONFORMANCE.md intact)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
