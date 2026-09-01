#!/usr/bin/env python3
"""Build the content-addressed manifest published with each BOCG release."""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "thefazzer/bankingops-coverage-grid"
SCHEMA_ID = "bankingops-coverage-grid.release-manifest.v1"
SEMANTIC_PROFILE = Path("specs/common-semantic-profile.yaml")
STATIC_ARTIFACTS = {
    "CONFORMANCE.md": "conformance-record",
    "specs/SPEC-01-coverage-grid-elicitation.md": "normative-specification",
    "specs/SPEC-03-control-point-cells.md": "normative-specification",
    "specs/SPEC-04-common-semantic-profile.md": "normative-specification",
    "specs/SPEC-05-insight-construction.md": "normative-specification",
    "specs/control-point-cell.schema.json": "json-schema",
    "specs/common-semantic-profile.yaml": "semantic-profile",
    "specs/insight-construction-profile.yaml": "semantic-profile",
    "specs/insight-construction.schema.json": "json-schema",
    "specs/institutional-speech-act.schema.json": "json-schema",
    "specs/rubrics/episode-feasibility.yaml": "adjudication-rubric",
    "specs/rubrics/five-families.yaml": "adjudication-rubric",
    "specs/bocg-release-manifest.schema.json": "release-manifest-schema",
}
RUN_ARTIFACTS = {
    "RUN_SUMMARY.json": "run-summary",
    "aliases.yaml": "normalisation-aliases",
    "exclusions.json": "exclusion-ledger",
    "gates_report.json": "gate-report",
    "matrix.json": "coverage-matrix",
    "normalised.json": "normalised-grid",
}


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _profile_identity(profile_path: Path) -> tuple[str, str]:
    # Keep the release builder dependency-free. These two scalar keys are
    # deliberately required near the top of the canonical YAML profile.
    profile_id = version = None
    in_profile = False
    for raw_line in profile_path.read_text(encoding="utf-8").splitlines():
        if raw_line == "profile:":
            in_profile = True
            continue
        if in_profile and raw_line and not raw_line.startswith(" "):
            break
        if in_profile and raw_line.startswith("  id:"):
            profile_id = raw_line.split(":", 1)[1].strip()
        elif in_profile and raw_line.startswith("  version:"):
            version = raw_line.split(":", 1)[1].strip()
    if not profile_id or not version:
        raise ValueError("semantic profile id/version are not readable")
    return profile_id, version


def _artifact(root: Path, relative: str, role: str) -> dict:
    path = root / relative
    body = path.read_bytes()
    media_type = mimetypes.guess_type(relative)[0] or "application/octet-stream"
    if relative.endswith((".yaml", ".yml")):
        media_type = "application/yaml"
    elif relative.endswith(".md"):
        media_type = "text/markdown"
    return {
        "path": relative,
        "role": role,
        "media_type": media_type,
        "size_bytes": len(body),
        "sha256": sha256_bytes(body),
    }


def build_manifest(
    *,
    tag: str,
    commit_sha: str,
    generated_at: str,
    root: Path = ROOT,
    run_dir: str = "live-run-20260826",
) -> dict:
    if not tag:
        raise ValueError("release tag is required")
    if len(commit_sha) != 40 or any(c not in "0123456789abcdef" for c in commit_sha):
        raise ValueError("commit SHA must be 40 lowercase hexadecimal characters")
    try:
        parsed_time = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("generated-at must be an ISO 8601 timestamp") from exc
    if parsed_time.tzinfo is None:
        raise ValueError("generated-at must include a timezone")

    artifact_roles = dict(STATIC_ARTIFACTS)
    artifact_roles.update(
        {f"{run_dir}/{name}": role for name, role in RUN_ARTIFACTS.items()}
    )
    artifact_roles.update(
        {
            path.relative_to(root).as_posix(): "control-point-cell"
            for path in sorted((root / "cells").glob("*.json"))
        }
    )
    artifacts = [
        _artifact(root, relative, artifact_roles[relative])
        for relative in sorted(artifact_roles)
    ]
    profile_path = root / SEMANTIC_PROFILE
    profile_id, profile_version = _profile_identity(profile_path)
    manifest = {
        "schema": SCHEMA_ID,
        "release": {
            "repository": REPOSITORY,
            "tag": tag,
            "commit_sha": commit_sha,
            "generated_at": parsed_time.astimezone(timezone.utc).isoformat().replace(
                "+00:00", "Z"
            ),
        },
        "semantic_profile": {
            "id": profile_id,
            "version": profile_version,
            "path": SEMANTIC_PROFILE.as_posix(),
            "sha256": sha256_bytes(profile_path.read_bytes()),
        },
        "artifacts": artifacts,
        "aggregate_sha256": sha256_bytes(canonical_json(artifacts)),
        "invariants": {
            "semantic_ceiling": "control_point",
            "occurrence_claims_permitted": False,
            "institution_specific_workflow_permitted": False,
            "mappings_are_identity": False,
        },
    }
    manifest["manifest_sha256"] = sha256_bytes(canonical_json(manifest))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--commit", required=True, dest="commit_sha")
    parser.add_argument(
        "--generated-at",
        default=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )
    parser.add_argument("--run-dir", default="live-run-20260826")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    manifest = build_manifest(
        tag=args.tag,
        commit_sha=args.commit_sha,
        generated_at=args.generated_at,
        run_dir=args.run_dir,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {args.output} ({len(manifest['artifacts'])} artifacts, "
        f"sha256 {manifest['manifest_sha256']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
