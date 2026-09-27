#!/usr/bin/env python3
"""Generate the public, non-occurrence release projection used by the Lab.

APPLY into Finexhaust as ficta-meridian-site/scripts/gen-release-observatory.py

Extensions vs prior Finexhaust build:
  - Emit cleanroom_eval companion pin (version 1.2.0) into latest.json
  - Emit public_eval block from BOCG public-eval-observatory (or rebuild from
    ledger + companion pin when observatory artifact is absent on older tags)
  - Include SPEC-08/09 + public-eval + task-concept contracts in the public set
  - Hash public-eval-overlay.ts when present among sealed inputs
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PUBLIC_PREFIXES = (
    "specs/SPEC-05-",
    "specs/SPEC-06-",
    "specs/SPEC-08-",
    "specs/SPEC-09-",
    "specs/operating-",
    "specs/insight-construction",
    "specs/institutional-speech-act",
    "specs/episode-surface",
    "specs/task-concepts",
    "specs/public-eval-",
    "specs/rubrics/",
    "reference/operating-",
    "reference/task-concept",
    "reference/public-eval-",
    "reference/cleanroom-eval-companion",
)

INPUT_PATHS = (
    "sku/episode-bocg-linkage.json",
    "sku/registry.json",
    "ficta-meridian-site/app/data/episode-chain.ts",
    "ficta-meridian-site/app/data/capability-map.ts",
    "ficta-meridian-site/app/data/coverage-grid.ts",
    "ficta-meridian-site/app/data/evidence-depth.ts",
    "ficta-meridian-site/app/data/public-eval-overlay.ts",
    "ficta-meridian-site/app/data/public-eval-observatory.ts",
)


def sha256_bytes(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _observatory_from_bocg(artifact_root: Path) -> dict | None:
    path = artifact_root / "reference/public-eval-observatory.v1.json"
    if path.is_file():
        return _load_json(path)
    return None


def _rebuild_public_eval(artifact_root: Path) -> dict:
    """Fallback when BOCG tag predates the observatory artifact."""
    ledger_path = artifact_root / "reference/public-eval-llmaj-ledger.v1.json"
    inv_path = artifact_root / "reference/public-eval-inventory.v1.yaml"
    pin_path = artifact_root / "reference/cleanroom-eval-companion.v1.json"
    overlay_path = artifact_root / "reference/public-eval-surface-map.v1.json"
    if not ledger_path.is_file():
        raise SystemExit("public-eval LLMAJ ledger missing from BOCG artifact root")
    ledger = _load_json(ledger_path)
    inventory: dict[str, dict] = {}
    if inv_path.is_file():
        current = None
        for raw in inv_path.read_text(encoding="utf-8").splitlines():
            if raw.startswith("  - id:"):
                if current and current.get("id"):
                    inventory[current["id"]] = current
                current = {"id": raw.split(":", 1)[1].strip()}
            elif current is not None:
                for key in ("title", "url", "class"):
                    prefix = f"    {key}:"
                    if raw.startswith(prefix):
                        current[key] = raw.split(":", 1)[1].strip()
        if current and current.get("id"):
            inventory[current["id"]] = current
    cleanroom = (
        _load_json(pin_path)
        if pin_path.is_file()
        else {
            "repository": "thefazzer/cleanroom-eval",
            "version": "1.2.0",
            "commit_sha": "d01e56e35dd13143a7d3af364b43d59f286a3c50",
            "release_tag": "v1.2.0",
            "release_status": "github_release_published",
            "bocg_companion_tag": "v0.6.2",
            "url": "https://github.com/thefazzer/cleanroom-eval",
            "notes": "fallback pin embedded in Meridian generator",
        }
    )
    cases = []
    for case in ledger.get("cases") or []:
        inv = inventory.get(case["inventory_id"]) or {}
        title = (inv.get("title") or case["inventory_id"]).split(" (", 1)[0]
        cases.append(
            {
                "case_id": case["case_id"],
                "inventory_id": case["inventory_id"],
                "title": title,
                "url": inv.get("url"),
                "case_verdict": case.get("case_verdict"),
                "paint_eligible": bool(case.get("paint_eligible")),
                "disagreement_note": case.get("disagreement_note"),
            }
        )
    painted = []
    if overlay_path.is_file():
        overlay = _load_json(overlay_path)
        for row in overlay.get("rows") or []:
            if row.get("mapping_status") not in {"QUALIFIED_MAPPING", "RATIFIED_MAPPING"}:
                continue
            inv = inventory.get(row["inventory_id"]) or {}
            painted.append(
                {
                    "row_id": row["row_id"],
                    "inventory_id": row["inventory_id"],
                    "title": (inv.get("title") or row["inventory_id"]).split(" (", 1)[0],
                    "mapping_status": row["mapping_status"],
                    "division_key": row.get("division_key"),
                    "band": row.get("band"),
                    "llmaj_pass_ref": row.get("llmaj_pass_ref"),
                }
            )
    return {
        "schema": "bocg.public-eval-observatory/v1",
        "prereg_sha256": ledger.get("prereg_sha256"),
        "cleanroom_eval": {
            "repository": cleanroom.get("repository"),
            "version": cleanroom.get("version"),
            "commit_sha": cleanroom.get("commit_sha"),
            "release_tag": cleanroom.get("release_tag"),
            "release_status": cleanroom.get("release_status"),
            "bocg_companion_tag": cleanroom.get("bocg_companion_tag"),
            "url": cleanroom.get("url"),
            "notes": cleanroom.get("notes"),
        },
        "llmaj": {
            "case_count": len(cases),
            "paint_eligible_count": sum(1 for c in cases if c["paint_eligible"]),
            "headline": (
                "Live LLMAJ: empty mapping-key intersection on Mercor / Rogo / "
                "BankerToolBench — no public_benchmark QUALIFIED paint."
                if not any(c["paint_eligible"] for c in cases)
                else "Live LLMAJ paint-eligible cases present."
            ),
            "cases": cases,
        },
        "overlay_paint": {
            "painted_row_count": len(painted),
            "rows": painted,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", required=True, type=Path)
    parser.add_argument("--typescript", required=True, type=Path)
    parser.add_argument("--public-json", required=True, type=Path)
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--source-commit", default=os.environ.get("GITHUB_SHA", "local"))
    parser.add_argument("--built-at", default=None)
    args = parser.parse_args()

    lock = _load_json(args.lock)
    repo_root = args.lock.resolve().parents[2]
    sys.path.insert(0, str(repo_root))
    sys.path.insert(0, str(repo_root / "knowledge-graph"))
    from canonical.operating_reference import ReferenceBundle
    from canonical.operating_reference_public import public_reference_projection
    from canonical.bocg_release import validate_manifest, sha256_bytes as bocg_sha

    manifest = lock["manifest"]
    validated = validate_manifest(
        manifest, tag=manifest["release"]["tag"], commit_sha=manifest["release"]["commit_sha"]
    )
    for artifact in validated:
        body = (args.artifact_root / artifact["path"]).read_bytes()
        if len(body) != artifact["size_bytes"] or bocg_sha(body) != artifact["sha256"]:
            raise SystemExit("public projection artifact verification failed")

    bundle = ReferenceBundle.from_checkout(args.lock, args.artifact_root)
    references = public_reference_projection(
        bundle, repo_root / "sku/regulatory-evidence/valuation-risk-v0.1"
    )
    release = manifest["release"]
    built_at = args.built_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    artifacts = [
        {
            "path": row["path"],
            "role": row["role"],
            "sha256": row["sha256"],
            "size_bytes": row["size_bytes"],
            "url": f"https://github.com/{release['repository']}/blob/{release['tag']}/{row['path']}",
        }
        for row in manifest["artifacts"]
        if row["path"].startswith(PUBLIC_PREFIXES)
    ]
    if not any(row["role"] == "operating-reference-catalogue" for row in artifacts):
        raise SystemExit("operating reference catalogue missing from release projection")

    inputs = []
    for relative in INPUT_PATHS:
        path = repo_root / relative
        if not path.is_file():
            continue
        body = path.read_bytes()
        inputs.append(
            {"path": relative, "sha256": sha256_bytes(body), "size_bytes": len(body)}
        )

    observatory = _observatory_from_bocg(args.artifact_root) or _rebuild_public_eval(
        args.artifact_root
    )
    cleanroom = observatory.get("cleanroom_eval") or {}
    public_eval = {
        "prereg_sha256": observatory.get("prereg_sha256"),
        "headline": (observatory.get("llmaj") or {}).get("headline"),
        "llmaj": observatory.get("llmaj"),
        "overlay_paint": observatory.get("overlay_paint"),
        "observatory_sha256": observatory.get("observatory_sha256"),
        "source": (
            "bocg.public-eval-observatory/v1"
            if observatory.get("schema") == "bocg.public-eval-observatory/v1"
            and observatory.get("observatory_sha256")
            else "rebuilt_from_bocg_ledger"
        ),
    }

    projection = {
        "schema": "ficta-meridian.public-release-observatory/v2",
        "built_at": built_at,
        "source": {"repository": "thefazzer/finexhaust", "commit": args.source_commit},
        "bocg": {
            "repository": release["repository"],
            "tag": release["tag"],
            "commit_sha": release["commit_sha"],
            "manifest_sha256": manifest["manifest_sha256"],
            "aggregate_sha256": manifest["aggregate_sha256"],
            "artifact_count": len(manifest["artifacts"]),
            "profile": manifest["semantic_profile"]["id"]
            + " "
            + manifest["semantic_profile"]["version"],
            "operating_reference_version": bundle.contract["version"],
            "verification": "all_manifest_artifact_bytes_verified_at_build",
        },
        "cleanroom_eval": {
            "repository": cleanroom.get("repository", "thefazzer/cleanroom-eval"),
            "version": cleanroom.get("version", "1.2.0"),
            "commit_sha": cleanroom.get("commit_sha"),
            "release_tag": cleanroom.get("release_tag"),
            "release_status": cleanroom.get("release_status"),
            "bocg_companion_tag": cleanroom.get("bocg_companion_tag"),
            "url": cleanroom.get("url", "https://github.com/thefazzer/cleanroom-eval"),
            "notes": cleanroom.get("notes"),
        },
        "public_eval": public_eval,
        "contracts": artifacts,
        "inputs": inputs,
        "boundary": {
            "definitions_public": True,
            "occurrence_instances_public": False,
            "record_plane_public": False,
            "cast_only_examples": True,
        },
    }
    projection["reference_summary"] = {
        "catalogue_counts": references["catalogue_counts"],
        "regulatory_sources": len(references["regulatory_sources"]),
        "regulatory_mappings": len(references["regulatory_mappings"]),
        "evidence_bocg_releases": references["evidence"]["original_bocg_releases"],
    }

    references_json = args.public_json.parent / "operating-reference.json"
    references_ts = args.typescript.parent / "operating-reference.ts"
    encoded = json.dumps(references, ensure_ascii=False)
    import re

    if re.search(
        r"\bubs\b|corpus-1|/home/|source_profile_id|source_path|solver-|UBS-CUR",
        encoded,
        re.I,
    ):
        raise SystemExit("private reference identifier in public projection")
    from tacit_boundary.release_guard import scan_bytes

    if scan_bytes("public/operating-reference.json", encoded.encode()):
        raise SystemExit("public reference release guard failed")

    references_json.parent.mkdir(parents=True, exist_ok=True)
    references_json.write_text(
        json.dumps(references, indent=2, ensure_ascii=False) + "\n"
    )
    references_ts.parent.mkdir(parents=True, exist_ok=True)
    references_ts.write_text(
        "// GENERATED by scripts/gen-release-observatory.py.\n"
        "export const OPERATING_REFERENCE = "
        + json.dumps(references, indent=2, ensure_ascii=False)
        + " as const;\n"
    )

    # Also emit a typed public-eval observatory module for the Lab UI.
    pe_ts = args.typescript.parent / "public-eval-observatory.ts"
    pe_ts.write_text(
        "// GENERATED by scripts/gen-release-observatory.py — do not hand-edit.\n"
        f"export const PUBLIC_EVAL_OBSERVATORY = {json.dumps(public_eval, indent=2, ensure_ascii=False)} as const;\n"
        f"export const CLEANROOM_EVAL_PIN = {json.dumps(projection['cleanroom_eval'], indent=2, ensure_ascii=False)} as const;\n",
        encoding="utf-8",
    )

    args.public_json.parent.mkdir(parents=True, exist_ok=True)
    args.public_json.write_text(
        json.dumps(projection, indent=2) + "\n", encoding="utf-8"
    )
    args.typescript.parent.mkdir(parents=True, exist_ok=True)
    args.typescript.write_text(
        "// GENERATED by scripts/gen-release-observatory.py — do not hand-edit.\n"
        f"export const RELEASE_OBSERVATORY = {json.dumps(projection, indent=2, ensure_ascii=False)} as const;\n",
        encoding="utf-8",
    )
    print(
        f"{release['tag']} · {len(artifacts)} public contracts · "
        f"cleanroom {projection['cleanroom_eval']['version']} · "
        f"llmaj cases {(public_eval.get('llmaj') or {}).get('case_count')} · "
        f"{args.public_json}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
