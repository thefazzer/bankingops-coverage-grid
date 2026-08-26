"""SPEC-02 §8 — runnable gates G1..G9 (`lat gate all`; exit non-zero on FAIL)."""
from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .canary import Registry
from .classes import Gazetteer, TOKEN_RE
from .holdout import near_dups_against_items
from .lineage import check_lineage, check_modes
from .manifest import utc_now
from .models import MODE_SYNTHESISE, SourceDoc
from .ner import Detector, RuleDetector
from .pkgio import Package
from .encoding import pretty_json
from .redact import RebuildError, redact_doc, rebuild_root
from .residual import scan as residual_scan
from .vault import NonceVault
from .verify import FAIL, PASS, WARN, Check, v7_vault_absent

GATE_NAMES = {"G1": "LEAKAGE_GATE", "G2": "CANARY_GATE", "G3": "MANIFEST_GATE", "G4": "CLASS_FLOOR_GATE",
              "G5": "RESIDUAL_GATE", "G6": "VAULT_GATE", "G7": "MODE_GATE", "G8": "DETERMINISM_GATE",
              "G9": "HOLDOUT_GATE"}


@dataclass
class GateContext:
    vault: Optional[NonceVault] = None
    source_docs: Optional[list[SourceDoc]] = None
    registry: Optional[Registry] = None
    audit_log: Optional[list[dict]] = None
    gazetteer: Optional[Gazetteer] = None
    detector: Optional[Detector] = None
    holdout_items: Optional[list[dict]] = None   # resolved from vault if None and vault given


def _holdout_items(pkg: Package, ctx: GateContext) -> Optional[list[dict]]:
    if ctx.holdout_items is not None:
        return ctx.holdout_items
    c = pkg.holdout_commit()
    if c and ctx.vault is not None:
        sec = ctx.vault.load_holdout(c["holdout_id"])
        if sec:
            return sec["items"]
    return None


def g1_leakage(pkg: Package, ctx: GateContext) -> Check:
    items = _holdout_items(pkg, ctx)
    if items is None:
        return Check("G1", FAIL, {"error": "holdout items unavailable (need vault with holdout secret or --holdout-items)"})
    pkg_docs = set(pkg.load_roots()["docs"]) if pkg.exists("roots.json") else set()
    shared_docs = sorted({d for i in items for d in i.get("source_doc_ids", [])} & pkg_docs)
    pkg_tokens = set()
    for p in pkg.all_files():
        try:
            pkg_tokens.update(TOKEN_RE.findall(p.read_text(encoding="utf-8")))
        except UnicodeDecodeError:
            pass
    hold_tokens = {t for i in items for t in TOKEN_RE.findall(i.get("task_text", "") + " " + str(i.get("answer", "")))}
    shared_tokens = sorted(set(pkg_tokens) & hold_tokens)
    episodes = pkg.episodes() if pkg.exists("episodes.jsonl") else []
    dups = near_dups_against_items([(e.episode_id, e.task_text) for e in episodes], items)
    ids_leaked = []
    for p in pkg.all_files():
        if p.name == "commit.json":
            continue
        try:
            t = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        ids_leaked += [i["item_id"] for i in items if i["item_id"] and i["item_id"] in t]
    ok = not shared_docs and not shared_tokens and not dups and not ids_leaked
    return Check("G1", PASS if ok else FAIL, {"shared_doc_ids": shared_docs[:10], "shared_entity_tokens": shared_tokens[:10],
                                             "near_dups": dups[:10], "item_ids_in_package": sorted(set(ids_leaked))[:10]})


def g2_canary(pkg: Package, ctx: GateContext) -> Check:
    meta = pkg.meta
    entry = pkg.registry_entry()
    pub = pkg.seller_pub()
    problems = []
    if entry is None:
        problems.append("package has no canary/registry_entry.json (unsalted package)")
    if ctx.registry is None:
        problems.append("registry unavailable")
    elif pub is None:
        problems.append("seller.pub missing")
    else:
        ok, chain_problems = ctx.registry.verify_chain(pub)
        problems += chain_problems
        line = ctx.registry.find(meta.get("package_id", ""), meta.get("recipient_id", ""))
        if line is None:
            problems.append(f"no registered salt for package {meta.get('package_id')} / recipient {meta.get('recipient_id')}")
        elif entry and line["entry"]["tag"] != entry["entry"].get("tag"):
            problems.append("registry entry in package differs from registry")
    return Check("G2", PASS if not problems else FAIL, {"problems": problems, "recipient_id": meta.get("recipient_id")})


def g3_manifest(pkg: Package, ctx: GateContext) -> Check:
    from .verify import v1_manifest, v2_roots
    v1, v2 = v1_manifest(pkg), v2_roots(pkg)
    pub = pkg.seller_pub()
    sigs = {f: (pub.verify_file(pkg.path / f) if pub and pkg.exists(f) else False)
            for f in ("roots.json", "lineage.jsonl", "ratios.json")}
    ok = v1.status == PASS and v2.status == PASS and all(sigs.values())
    return Check("G3", PASS if ok else FAIL, {"V1": v1.status, "V2": v2.status, "sigs": sigs,
                                             "problems": v1.evidence.get("problems", []) + v2.evidence.get("errors", [])})


def g4_class_floor(pkg: Package, ctx: GateContext) -> Check:
    r = pkg.read_json("ratios.json") or {}
    meta = pkg.meta
    tier = r.get("tier")
    marketed = meta.get("marketed_tier", "VERIFIED")
    label = meta.get("tier_label")
    if marketed == "VERIFIED":
        ok = tier == "VERIFIED" and label == "VERIFIED"
    else:
        ok = label == "MIXED"
    return Check("G4", PASS if ok else FAIL, {"ratios_tier": tier, "marketed_tier": marketed, "tier_label": label})


def g5_residual(pkg: Package, ctx: GateContext) -> Check:
    gaz = ctx.gazetteer or Gazetteer()
    items = _holdout_items(pkg, ctx)
    rs = residual_scan(pkg, gaz, ctx.detector, pkg.episodes() if pkg.exists("episodes.jsonl") else None,
                       holdout_commit=pkg.holdout_commit(), holdout_items=items)
    ok, reasons = rs.gate()
    return Check("G5", PASS if ok else FAIL, {"counts": rs.counts, "n_kept_segments": rs.n_kept_segments,
                                             "reasons": reasons, "findings": [f.to_dict() for f in rs.findings[:25]]})


def g6_vault(pkg: Package, ctx: GateContext) -> Check:
    c = v7_vault_absent(pkg)
    return Check("G6", c.status, c.evidence)


def g7_mode(pkg: Package, ctx: GateContext) -> Check:
    roots = pkg.load_roots() if pkg.exists("roots.json") else {"docs": {}}
    probs = check_modes(pkg.atoms(), roots) if pkg.exists("lineage.jsonl") else ["lineage.jsonl missing"]
    return Check("G7", PASS if not probs else FAIL, {"problems": probs[:10]})


def g8_determinism(pkg: Package, ctx: GateContext) -> Check:
    if ctx.vault is None or ctx.source_docs is None:
        return Check("G8", FAIL, {"error": "need vault + source docs to re-run redaction"})
    detector = ctx.detector or RuleDetector(ctx.gazetteer or Gazetteer())
    roots = pkg.load_roots()
    by_id = {d.doc_id: d for d in ctx.source_docs}
    mismatches, checked, missing = [], 0, []
    for doc_id, info in roots["docs"].items():
        if info.get("mode") == MODE_SYNTHESISE:
            continue
        doc = by_id.get(doc_id)
        if doc is None:
            missing.append(doc_id)
            continue
        r = redact_doc(doc, detector, ctx.vault, info["mode"], roots.get("date_policy", "shift_per_doc_v1"), persist=False)
        checked += 1
        if r.redacted != pkg.load_redacted(doc_id) or r.root.hex() != info["root"]:
            mismatches.append(doc_id)
    ok = not mismatches and not missing
    return Check("G8", PASS if ok else FAIL, {"docs_rerun": checked, "mismatches": mismatches[:10], "missing_source": missing[:10]})


def _parse_ts(s: str) -> Optional[_dt.datetime]:
    try:
        d = _dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=_dt.timezone.utc)
    except (ValueError, AttributeError):
        return None


def g9_holdout(pkg: Package, ctx: GateContext) -> Check:
    c = pkg.holdout_commit()
    if c is None:
        return Check("G9", FAIL, {"error": "holdout/commit.json missing"})
    if ctx.audit_log is None:
        return Check("G9", FAIL, {"error": "audit log unavailable"})
    created = _parse_ts(c.get("created_utc", ""))
    reviews = [_parse_ts(e.get("ts") or e.get("external_review_ts", "")) for e in ctx.audit_log
               if e.get("event") == "external_review" or "external_review_ts" in e]
    reviews = [r for r in reviews if r]
    earliest = min(reviews) if reviews else None
    ok = created is not None and (earliest is None or created < earliest)
    return Check("G9", PASS if ok else FAIL, {"holdout_created_utc": c.get("created_utc"),
                                             "earliest_external_review_ts": earliest.isoformat() if earliest else None,
                                             "n_external_reviews": len(reviews)})


GATES = [g1_leakage, g2_canary, g3_manifest, g4_class_floor, g5_residual, g6_vault, g7_mode, g8_determinism, g9_holdout]


def run_gates(pkg_path: str | Path, ctx: GateContext, write: bool = True, only: Optional[list[str]] = None) -> dict:
    pkg = Package(pkg_path)
    results = []
    for g in GATES:
        gid = g.__name__[:2].upper()
        if only and gid not in only:
            continue
        try:
            c = g(pkg, ctx)
        except Exception as e:  # a crashing gate is a failing gate
            c = Check(gid, FAIL, {"error": f"{type(e).__name__}: {e}"})
        results.append({"id": c.id, "name": GATE_NAMES[c.id], "status": c.status, "evidence": c.evidence})
    overall = FAIL if any(r["status"] == FAIL for r in results) else PASS
    report = {"package": pkg.meta.get("package_id"), "run_utc": utc_now(), "gates": results, "overall": overall}
    if write:
        (pkg.path / "gates_report.json").write_text(pretty_json(report), encoding="utf-8")
    return report
