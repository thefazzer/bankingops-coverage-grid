"""SPEC-02 §9 — package build: §9 layout, canary applied, signatures, package.json, README-VERIFY.md,
gates run (gates_report.json). Refuses to build an unsalted package (G2)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional

from .canary import Canary, apply_canary
from .gates import GateContext, run_gates
from .lineage import read_jsonl, write_jsonl
from .manifest import ANCHOR_FILE, utc_now
from .models import MODE_SYNTHESISE
from .redact import LAT_VERSION
from .encoding import pretty_json
from .workspace import Workspace


class PackageBuildError(Exception):
    pass


def _copy(src: Path, dst: Path, required: bool = True) -> None:
    if not src.exists():
        if required:
            raise PackageBuildError(f"missing build input: {src}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dst)


def declared_scope_from_vault(vault, doc_ids: list[str]) -> dict:
    insts, starts, ends = set(), [], []
    for d in doc_ids:
        vd = vault.load_doc(d)
        if vd:
            o = vd["origin"]
            insts.add(o.institution_code)
            if o.period_start:
                starts.append(o.period_start)
            if o.period_end:
                ends.append(o.period_end)
    return {"institutions": sorted(insts), "period_start": min(starts) if starts else "",
            "period_end": max(ends) if ends else ""}


def build_package(ws: Workspace, package_id: str, recipient_id: str, vault, marketed_tier: str = "VERIFIED",
                  scope: Optional[dict] = None, out_dir: Optional[Path] = None, run_gate_checks: bool = True,
                  redact_amounts: bool = False) -> tuple[Path, Optional[dict]]:
    work = ws.work.path
    out = Path(out_dir) if out_dir else ws.package_dir(package_id)
    # G2: refuse to build without a registered per-recipient salt
    line = ws.registry.find(package_id, recipient_id)
    if line is None:
        raise PackageBuildError(f"no registered canary for package {package_id!r} / recipient {recipient_id!r}; "
                                "run `lat canary register` first (G2 CANARY_GATE)")
    canary = Canary.from_dict(line["entry"])
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    key = vault.signing_key

    # manifest + anchor
    _copy(ws.root / "manifest.json", out / "manifest.json")
    _copy(ws.root / "manifest.sha", out / "manifest.sha")
    if (ws.root / ANCHOR_FILE).exists():
        _copy(ws.root / ANCHOR_FILE, out / ANCHOR_FILE)
    else:
        (out / ANCHOR_FILE).write_text("null\n")
    # roots, segmentation, redacted
    _copy(work / "roots.json", out / "roots.json")
    _copy(work / "roots.json.sig", out / "roots.json.sig")
    _copy(work / "segmentation", out / "segmentation")
    _copy(work / "redacted", out / "redacted")
    # lineage with canary applied, re-signed
    atoms = read_jsonl(work / "lineage.jsonl")
    if not atoms:
        raise PackageBuildError("work/lineage.jsonl missing or empty (run `lat lineage build`)")
    write_jsonl(out / "lineage.jsonl", apply_canary(atoms, canary))
    key.sign_file(out / "lineage.jsonl")
    _copy(work / "episodes.jsonl", out / "episodes.jsonl")
    # ratios (canonical bytes) + sig
    _copy(work / "ratios.json", out / "ratios.json")
    key.sign_file(out / "ratios.json")
    # canary registry entry
    (out / "canary").mkdir()
    (out / "canary" / "registry_entry.json").write_text(pretty_json(line), encoding="utf-8")
    sig = key.sign_b64((out / "canary" / "registry_entry.json").read_bytes())
    (out / "canary" / "registry_entry.sig").write_text(sig + "\n")
    # holdout commit (public only)
    _copy(ws.holdout_dir / "commit.json", out / "holdout" / "commit.json")
    holdout_id = json.loads((out / "holdout" / "commit.json").read_text())["holdout_id"]
    # pubkey
    (out / "pubkeys").mkdir()
    key.public().save(out / "pubkeys" / "seller.pub")
    # package.json
    roots = json.loads((out / "roots.json").read_text(encoding="utf-8"))
    doc_ids = [d for d, i in roots["docs"].items() if i.get("mode") != MODE_SYNTHESISE]
    ratios = json.loads((out / "ratios.json").read_text(encoding="utf-8"))
    tier_label = "VERIFIED" if (marketed_tier == "VERIFIED" and ratios.get("tier") == "VERIFIED") else "MIXED"
    meta = {"package_id": package_id, "recipient_id": recipient_id, "created_utc": utc_now(), "lat_version": LAT_VERSION,
            "marketed_tier": marketed_tier, "tier_label": tier_label, "ratios_tier": ratios.get("tier"),
            "declared_scope": scope or declared_scope_from_vault(vault, doc_ids), "holdout_id": holdout_id,
            "canary_tag": canary.tag.hex(), "n_docs": len(doc_ids), "n_atoms": len(atoms),
            "date_policy": roots.get("date_policy")}
    (out / "package.json").write_text(pretty_json(meta), encoding="utf-8")
    (out / "README-VERIFY.md").write_text(readme_verify(meta), encoding="utf-8")
    report = None
    if run_gate_checks:
        ctx = GateContext(vault=vault, source_docs=ws.docs(), registry=ws.registry, audit_log=ws.audit_log(),
                          gazetteer=ws.gazetteer(), detector=ws.detector(redact_amounts=redact_amounts))
        report = run_gates(out, ctx, write=True)
        meta["gates_overall"] = report["overall"]
        (out / "package.json").write_text(pretty_json(meta), encoding="utf-8")
    return out, report


def readme_verify(meta: dict) -> str:
    pid = meta["package_id"]
    return f"""# README-VERIFY — package `{pid}` (recipient `{meta['recipient_id']}`)

Built with LAT {meta['lat_version']} on {meta['created_utc']}. Tier label: **{meta['tier_label']}**
(ratios tier {meta['ratios_tier']}, marketed as {meta['marketed_tier']}). Date policy: `{meta['date_policy']}`.
Declared scope: institutions {meta['declared_scope'].get('institutions')}, period
{meta['declared_scope'].get('period_start')}..{meta['declared_scope'].get('period_end')}.

## Buyer (no vault) — V1..V7

```bash
pip install lat            # or: pip install -e <lat source dir>
lat verify --mode buyer --package pkg-{pid}
cat pkg-{pid}/verify_buyer.json      # {{"checks":[{{"id":"V1",...}}], "overall":"PASS|FAIL"}}
lat canary detect pkg-{pid}/lineage.jsonl --registry-entry pkg-{pid}/canary/registry_entry.json
lat manifest verify --dir pkg-{pid}
```

What buyer verification establishes (and only this): manifest hash/merkle root recompute (V1); every
redacted doc's root recomputes from kept bytes + segmentation + commitments and matches the seller-signed
roots.json (V2); every atom's lineage class is consistent with its derivation op and, for
SPAN_VERIFIED / PSEUDONYMISED_TRACEABLE atoms, the content is a substring of the referenced committed
segments (V3); ratios.json is byte-identical to a recomputation from lineage.jsonl (V4); the package
carries a registered, signed canary for the stated recipient that is recoverable from the package (V5);
a dated holdout commitment is present and no holdout ids / near-duplicates appear (V6); no vault material
(nonces, K_pseud, originals) is present (V7).

## Examiner (holds the nonce vault) — E1..E7

```bash
export LAT_VAULT_KEY_FILE=/secure/path/vault.key       # or LAT_VAULT_KEY=<hex>
lat verify --mode examiner --package pkg-{pid} --vault /secure/path/vault \\
    --sample 200 --seed 42 --examiner-key /secure/path/examiner.key --gazetteers <gazetteer dir>
cat pkg-{pid}/report.md                 # narrowly scoped, dated statement
lat report --package pkg-{pid}           # re-render report.md from report.json
```

The examiner's report.json is signed with the examiner's Ed25519 key (`report.json.sig`, `examiner.pub`).

## Holdout reveal (only after the evaluation is closed)

```bash
lat holdout verify --commit pkg-{pid}/holdout/commit.json --reveal reveal.json
```

## What this does NOT prove
LAT does not prove semantic safety of kept text, correctness of doctrine, or absence of re-identification
via operational detail. The residual scan (E6/G5) is heuristic. The anchor proof, if present, is an
OpenTimestamps *stub* record in this version (no network verification).
"""
