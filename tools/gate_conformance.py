#!/usr/bin/env python3
"""SPEC-03 runnable gates: S3-G1..G4. Exit non-zero on any failure."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

from build_release_manifest import build_manifest, canonical_json, sha256_bytes

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
    targets = list((ROOT / "cells").glob("*.json")) + [
        ROOT / "specs/SPEC-03-control-point-cells.md",
        ROOT / "specs/SPEC-04-common-semantic-profile.md",
        ROOT / "specs/common-semantic-profile.yaml",
    ]
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
    if len(rows) < 16:
        fail(f"S3-G4 CONFORMANCE.md: {len(rows)} statused rows found, baseline is 16")
    numbers = [int(r[0]) for r in rows]
    if numbers != list(range(1, len(numbers) + 1)):
        fail("S3-G4 CONFORMANCE.md: row numbering broken (row removed or reordered)")


def _schema_pointer_exists(schema: dict, pointer: str) -> bool:
    prefix = "control-point-cell.schema.json#"
    if not pointer.startswith(prefix):
        return False
    value: object = schema
    for part in pointer[len(prefix):].strip("/").split("/"):
        if not part:
            continue
        if not isinstance(value, dict) or part not in value:
            return False
        value = value[part]
    return True


def gate_common_semantics() -> None:
    """S4: portable mappings reuse existing schemas and stop above workflow."""
    profile_path = ROOT / "specs/common-semantic-profile.yaml"
    schema = json.loads((ROOT / "specs/control-point-cell.schema.json").read_text())
    try:
        profile = yaml.safe_load(profile_path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        fail(f"S4-G1 common semantic profile is unreadable: {exc}")
        return
    meta = profile.get("profile") or {}
    if meta.get("id") != "bocg-common-semantics" or meta.get("scope", {}).get("ceiling") != "control_point":
        fail("S4-G1 profile identity or control-point ceiling drifted")
    if meta.get("scope", {}).get("occurrence_claims_permitted") is not False:
        fail("S4-G1 occurrence claims must remain prohibited")
    prohibited = set(meta.get("prohibited_object_types") or [])
    required_prohibited = {"ObservationAtom", "Trace", "Episode", "EmailDiscourseBlock", "FiveFamilyAssessment"}
    if not required_prohibited.issubset(prohibited):
        fail("S4-G1 below-floor object deny list is incomplete")

    standards = profile.get("standards") or {}
    for authority, row in standards.items():
        if not isinstance(row, dict) or not str(row.get("uri") or "").startswith("https://"):
            fail(f"S4-G2 standard {authority}: HTTPS URI required")
        if not row.get("label") or not row.get("authority") or not row.get("use"):
            fail(f"S4-G2 standard {authority}: label, authority and use required")
    allowed = set((profile.get("mapping_policy") or {}).get("allowed_relations") or [])
    if not allowed or (profile.get("mapping_policy") or {}).get("mapping_is_not_identity") is not True:
        fail("S4-G2 mapping strengths or non-identity policy missing")

    def check_mappings(location: str, mappings: object) -> None:
        if not isinstance(mappings, list) or not mappings:
            fail(f"S4-G2 {location}: at least one mapping required")
            return
        for index, row in enumerate(mappings):
            if not isinstance(row, dict):
                fail(f"S4-G2 {location}[{index}]: mapping must be an object")
                continue
            if row.get("authority") not in standards:
                fail(f"S4-G2 {location}[{index}]: undeclared authority")
            if row.get("relation") not in allowed:
                fail(f"S4-G2 {location}[{index}]: prohibited mapping relation")
            if not row.get("term"):
                fail(f"S4-G2 {location}[{index}]: mapped term required")

    for object_id, row in (profile.get("semantic_objects") or {}).items():
        check_mappings(f"semantic_objects.{object_id}", (row or {}).get("mappings"))
    field_mappings = profile.get("field_mappings") or {}
    for pointer, mappings in field_mappings.items():
        if not _schema_pointer_exists(schema, pointer):
            fail(f"S4-G3 field mapping does not resolve existing schema path: {pointer}")
        check_mappings(f"field_mappings.{pointer}", mappings)
    required_fields = set(schema.get("required") or [])
    mapped_fields = {
        pointer.split("/properties/", 1)[1].split("/", 1)[0]
        for pointer in field_mappings
        if "/properties/" in pointer
    }
    if required_fields - mapped_fields:
        fail(f"S4-G3 required SPEC-03 fields lack mappings: {sorted(required_fields - mapped_fields)}")
    for relation_id, row in (profile.get("relation_vocabulary") or {}).items():
        if (row or {}).get("domain") not in (profile.get("semantic_objects") or {}):
            fail(f"S4-G4 relation {relation_id}: unknown domain")
        if (row or {}).get("range") not in (profile.get("semantic_objects") or {}):
            fail(f"S4-G4 relation {relation_id}: unknown range")
        check_mappings(f"relation_vocabulary.{relation_id}", (row or {}).get("mappings"))


def gate_release_manifest() -> None:
    """S4-G5: a release can publish one self-consistent hash manifest."""
    try:
        manifest = build_manifest(
            tag="v0.0.0-gate",
            commit_sha="0" * 40,
            generated_at="2000-01-01T00:00:00Z",
        )
        schema = json.loads(
            (ROOT / "specs/bocg-release-manifest.schema.json").read_text()
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        fail(f"S4-G5 release manifest cannot be built: {exc}")
        return
    try:
        import jsonschema

        for error in jsonschema.Draft202012Validator(
            schema, format_checker=jsonschema.FormatChecker()
        ).iter_errors(manifest):
            fail(f"S4-G5 release manifest schema: {error.message[:120]}")
    except ImportError:
        pass
    artifacts = manifest.get("artifacts") or []
    if [row.get("path") for row in artifacts] != sorted(
        row.get("path") for row in artifacts
    ):
        fail("S4-G5 release artifacts are not deterministically ordered")
    if manifest.get("aggregate_sha256") != sha256_bytes(canonical_json(artifacts)):
        fail("S4-G5 aggregate artifact digest is invalid")
    claimed = manifest.pop("manifest_sha256", None)
    if claimed != sha256_bytes(canonical_json(manifest)):
        fail("S4-G5 manifest self-digest is invalid")


def gate_insight_construction() -> None:
    """S5: portable occurrence shapes remain static and lifecycle-safe."""
    profile_path = ROOT / "specs/insight-construction-profile.yaml"
    try:
        profile = yaml.safe_load(profile_path.read_text())
        insight_schema = json.loads((ROOT / "specs/insight-construction.schema.json").read_text())
        speech_schema = json.loads((ROOT / "specs/institutional-speech-act.schema.json").read_text())
        episode = yaml.safe_load((ROOT / "specs/rubrics/episode-feasibility.yaml").read_text())
        families = yaml.safe_load((ROOT / "specs/rubrics/five-families.yaml").read_text())
    except (OSError, ValueError, yaml.YAMLError) as exc:
        fail(f"S5-G1 insight-construction artifacts unreadable: {exc}")
        return
    meta = profile.get("profile") or {}
    scope = meta.get("scope") or {}
    if meta.get("id") != "bocg-insight-construction" or meta.get("layered_on") != "bocg-common-semantics":
        fail("S5-G1 layered profile identity drifted")
    if scope.get("definitions_only") is not True or scope.get("occurrence_instances_permitted") is not False:
        fail("S5-G1 profile must publish definitions but no occurrence instances")
    lifecycle = profile.get("lifecycle_vocabulary") or {}
    required = {"directed", "scheduled", "executed", "completed", "verified"}
    if not required.issubset(set(lifecycle.get("ordered_states") or [])):
        fail("S5-G2 lifecycle state separation is incomplete")
    rules = lifecycle.get("inference_rules") or {}
    if any(rules.get(key) is not False for key in (
        "directive_implies_execution", "scheduled_implies_execution",
        "executed_implies_completion", "completed_implies_verification",
    )):
        fail("S5-G2 lifecycle inference must fail closed")
    if not {"ObservationAtom", "Trace", "Episode"}.issubset((insight_schema.get("$defs") or {}).keys()):
        fail("S5-G3 insight schema lacks Atom/Trace/Episode definitions")
    obligation = ((speech_schema.get("properties") or {}).get("obligation_frame") or {}).get("properties") or {}
    if "executed" in ((obligation.get("execution_status") or {}).get("enum") or []):
        fail("S5-G3 directive expansion must not assert execution")
    if (episode.get("rubric") or {}).get("safeguards", {}).get("atom_truth_does_not_imply_episode_truth") is not True:
        fail("S5-G4 Episode rubric lacks composition safeguard")
    family_ids = set(((families.get("rubric") or {}).get("families") or {}).keys())
    if family_ids != {"DEEP_DOMAIN_TRANSFER", "EVIDENCE_ABLATION", "NEGATIVE_CONTROL", "LATERAL_HIRE", "COMMERCIAL_INSIGHT"}:
        fail("S5-G5 Five Families vocabulary drifted")


def main() -> int:
    gate_cells()
    gate_deny()
    gate_conformance_doc()
    gate_common_semantics()
    gate_release_manifest()
    gate_insight_construction()
    if FAILURES:
        print("GATE FAILURES:")
        for f in FAILURES:
            print("  ", f)
        return 1
    cells = len(list((ROOT / "cells").glob("*.json")))
    print(f"all SPEC-03/SPEC-04/SPEC-05 gates pass ({cells} cells, CONFORMANCE.md intact)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
