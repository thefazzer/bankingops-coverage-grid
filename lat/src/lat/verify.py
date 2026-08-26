"""SPEC-02 §6 — verifier, two modes, one CLI.

buyer   : V1..V7 with no vault              -> verify_buyer.json
examiner: E1 (=V1..V7) + E2..E7 with vault  -> report.json (signed by examiner) + report.md
"""
from __future__ import annotations

import datetime as _dt
import json
import math
import random
import re as _re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .canary import MIN_CARRIERS, detect_path, verify_registry_line
from .classes import CLASS_SET, Gazetteer, class_predicate, date_shift_days, canonical_original
from .crypto import commitment
from .encoding import canonical_json, pretty_json, sha256_hex
from .holdout import near_dups_against_sketches
from .lineage import check_lineage
from .manifest import utc_now, verify_manifest
from .models import KEEP, MODE_SYNTHESISE, REDACT
from .pkgio import Package
from .ratios import compute_ratios
from .redact import RebuildError, make_token, rebuild_leaves, rebuild_root, reconstruct_original
from .residual import scan as residual_scan
from .vault import NonceVault
from . import crypto

PASS, FAIL, WARN = "PASS", "FAIL", "WARN"


@dataclass
class Check:
    id: str
    status: str
    evidence: dict = field(default_factory=dict)

    def to_dict(self):
        return {"id": self.id, "status": self.status, "evidence": self.evidence}


def _overall(checks: list[Check]) -> str:
    return FAIL if any(c.status == FAIL for c in checks) else PASS


# =============================================================================== buyer V1..V7

def v1_manifest(pkg: Package) -> Check:
    m, sha = pkg.manifest()
    if m is None:
        return Check("V1", FAIL, {"error": "manifest.json missing"})
    r = verify_manifest(m, sha, pkg.anchor())
    roots = pkg.load_roots() if pkg.exists("roots.json") else {"docs": {}}
    missing = sorted(d for d in roots["docs"] if d not in set(m["docs"]))
    ev = {"n_docs_manifest": r["n_docs"], "sha": r["sha"], "anchor": r["anchor"], "problems": r["problems"],
          "package_docs_not_in_manifest": missing[:10]}
    return Check("V1", PASS if r["ok"] and not missing else FAIL, ev)


def v2_roots(pkg: Package) -> Check:
    pub = pkg.seller_pub()
    if pub is None or not pkg.exists("roots.json"):
        return Check("V2", FAIL, {"error": "roots.json or pubkeys/seller.pub missing"})
    sig_ok = pub.verify_file(pkg.path / "roots.json")
    roots = pkg.load_roots()
    mismatches, errors, checked = [], [], 0
    for doc_id, info in roots["docs"].items():
        if info.get("mode") == MODE_SYNTHESISE:
            continue
        try:
            seg = pkg.load_segmentation(doc_id)
            red = pkg.load_redacted(doc_id)
            if seg.doc_id != doc_id:
                errors.append(f"{doc_id[:12]}: segmentation doc_id mismatch")
                continue
            for s in seg.segments:
                if s.kind == REDACT and s.cls not in CLASS_SET:
                    errors.append(f"{doc_id[:12]}#{s.idx}: unknown class {s.cls}")
            root = rebuild_root(doc_id, seg, red).hex()
            checked += 1
            if root != info.get("root"):
                mismatches.append(doc_id)
        except (FileNotFoundError, RebuildError, ValueError) as e:
            errors.append(f"{doc_id[:12]}: {e}")
    for doc_id in pkg.doc_ids():
        if doc_id not in roots["docs"]:
            errors.append(f"{doc_id[:12]}: redacted doc not in roots.json")
    ok = sig_ok and not mismatches and not errors
    return Check("V2", PASS if ok else FAIL, {"sig_ok": sig_ok, "docs_checked": checked, "root_mismatches": mismatches[:10],
                                             "errors": errors[:10]})


def v3_lineage(pkg: Package) -> Check:
    pub = pkg.seller_pub()
    if pub is None or not pkg.exists("lineage.jsonl"):
        return Check("V3", FAIL, {"error": "lineage.jsonl or seller.pub missing"})
    sig_ok = pub.verify_file(pkg.path / "lineage.jsonl")
    try:
        atoms, episodes = pkg.atoms(), pkg.episodes()
    except (KeyError, ValueError) as e:
        return Check("V3", FAIL, {"error": f"malformed lineage: {e}"})
    r = check_lineage(atoms, episodes, pkg)
    ev = {"sig_ok": sig_ok, "n_atoms": r["n_atoms"], "n_failed": r["n_failed"],
          "atom_failures": dict(list(r["atom_failures"].items())[:10]), "episode_problems": r["episode_problems"][:10]}
    return Check("V3", PASS if sig_ok and r["ok"] else FAIL, ev)


def v4_ratios(pkg: Package) -> Check:
    pub = pkg.seller_pub()
    shipped = pkg.ratios()
    if pub is None or shipped is None:
        return Check("V4", FAIL, {"error": "ratios.json or seller.pub missing"})
    sig_ok = pub.verify_file(pkg.path / "ratios.json")
    try:
        shipped_obj = json.loads(shipped)
        recomputed = compute_ratios(pkg.atoms(), float(shipped_obj.get("tier_floor", 0.8)))
    except Exception as e:
        return Check("V4", FAIL, {"error": str(e)})
    identical = canonical_json(recomputed) == shipped.strip()
    return Check("V4", PASS if sig_ok and identical else FAIL,
                 {"sig_ok": sig_ok, "byte_identical": identical, "recomputed_tier": recomputed["tier"],
                  "recomputed_by_bytes_pct": recomputed["by_bytes"]["pct"]})


def v5_canary(pkg: Package) -> Check:
    pub = pkg.seller_pub()
    line = pkg.registry_entry()
    if pub is None or line is None:
        return Check("V5", FAIL, {"error": "canary/registry_entry.json or seller.pub missing"})
    sig_file_ok = pub.verify_file(pkg.path / "canary" / "registry_entry.json", pkg.path / "canary" / "registry_entry.sig")
    line_ok = verify_registry_line(line, pub)
    entry = line["entry"]
    meta = pkg.meta
    ident_ok = entry.get("package_id") == meta.get("package_id") and entry.get("recipient_id") == meta.get("recipient_id")
    det = detect_path(pkg.path / "lineage.jsonl") if pkg.exists("lineage.jsonl") else None
    recovered = det is not None and det.detected and det.tag == entry.get("tag")
    ok = sig_file_ok and line_ok and ident_ok and recovered
    return Check("V5", PASS if ok else FAIL,
                 {"registry_sig_ok": line_ok, "entry_file_sig_ok": sig_file_ok, "identity_matches_package": ident_ok,
                  "recipient_id": entry.get("recipient_id"), "carriers_found": det.carriers_found if det else 0,
                  "min_carriers": MIN_CARRIERS, "recovered_tag_matches": recovered})


def _package_text_files(pkg: Package, exclude: tuple[str, ...] = ()) -> list[tuple[Path, str]]:
    out = []
    for p in pkg.all_files():
        rel = p.relative_to(pkg.path).as_posix()
        if rel in exclude:
            continue
        try:
            out.append((p, p.read_text(encoding="utf-8")))
        except UnicodeDecodeError:
            out.append((p, ""))
    return out


def v6_holdout(pkg: Package) -> Check:
    c = pkg.holdout_commit()
    if c is None:
        return Check("V6", FAIL, {"error": "holdout/commit.json missing"})
    problems = []
    if not c.get("items_commit") or len(c["items_commit"]) != 64:
        problems.append("items_commit missing/malformed")
    try:
        _dt.datetime.fromisoformat(c.get("created_utc", "").replace("Z", "+00:00"))
    except ValueError:
        problems.append("created_utc not a valid timestamp")
    ids = [i for i in c.get("item_ids", []) if i]
    leaked = []
    for p, text in _package_text_files(pkg, exclude=("holdout/commit.json",)):
        for iid in ids:
            if iid in text:
                leaked.append(f"{iid} in {p.relative_to(pkg.path).as_posix()}")
    texts = [(e.episode_id, e.task_text) for e in pkg.episodes()] if pkg.exists("episodes.jsonl") else []
    dups = near_dups_against_sketches(texts, c)
    if leaked:
        problems.append(f"holdout item ids appear in package: {leaked[:5]}")
    if dups:
        problems.append(f"episodes near-duplicate of holdout items: {dups[:5]}")
    return Check("V6", PASS if not problems else FAIL,
                 {"holdout_id": c.get("holdout_id"), "created_utc": c.get("created_utc"), "anchored": bool(c.get("anchor")),
                  "n_items": c.get("n_items"), "problems": problems})


_SUSPECT_NAME = _re.compile(r"(vault|k_pseud|nonce|secret|seller\.key|signing[_-]?key|\.enc$|\.key$)", _re.I)
_SUSPECT_KEYS = {"nonce", "nonce_h", "original", "original_bytes", "originals", "k_pseud", "seller_seed", "private_key"}
_HEX64 = _re.compile(r"\b[0-9a-f]{64}\b")
_MAGIC = (crypto.VAULT_MAGIC, b"-----BEGIN", b"\x89PNG", b"PK\x03\x04")


def _entropy(data: bytes) -> float:
    if not data:
        return 0.0
    c = Counter(data)
    n = len(data)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def _json_keys(obj, acc: set):
    if isinstance(obj, dict):
        for k, v in obj.items():
            acc.add(k)
            _json_keys(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _json_keys(v, acc)


def v7_vault_absent(pkg: Package) -> Check:
    """No nonces / K_pseud / originals: filename, magic, JSON-key, unknown-64-hex and entropy scans."""
    findings = []
    known: set[str] = set()
    m, sha = pkg.manifest()
    if m:
        known.update(m.get("docs", []))
        known.add(m.get("merkle_root", ""))
        known.add(m.get("prev_sha", "") or "")
        known.add(sha or "")
    known.add("0" * 64)
    if pkg.exists("roots.json"):
        for doc_id, info in pkg.load_roots()["docs"].items():
            known.add(doc_id)
            known.add(info.get("root") or "")
            try:
                seg = pkg.load_segmentation(doc_id)
                leaves, _ = rebuild_leaves(doc_id, seg, pkg.load_redacted(doc_id))
                known.update(l.hex() for l in leaves)
            except Exception:
                pass
    if pkg.exists("lineage.jsonl"):
        for a in pkg.atoms():
            known.add(a.content_sha256)
            known.update(r.leaf_or_commit for r in a.span_refs)
            known.update(r.doc_id for r in a.span_refs)
    if pkg.exists("canary/registry_entry.json"):
        known.add(pkg.registry_entry().get("prev_hash", ""))
    hc = pkg.holdout_commit()
    if hc:
        known.add(hc.get("items_commit", ""))
    for p in pkg.all_files():
        rel = p.relative_to(pkg.path).as_posix()
        data = p.read_bytes()
        if _SUSPECT_NAME.search(rel):
            findings.append(f"suspect filename: {rel}")
        if any(data.startswith(mg) for mg in _MAGIC):
            findings.append(f"suspect magic bytes: {rel}")
        if len(data) > 256 and _entropy(data) > 7.2:
            findings.append(f"high entropy ({_entropy(data):.2f} bits/byte): {rel}")
        if rel.endswith((".json", ".jsonl")):
            try:
                text = data.decode("utf-8")
                objs = [json.loads(l) for l in text.splitlines() if l.strip()] if rel.endswith(".jsonl") else [json.loads(text)]
                keys: set = set()
                for o in objs:
                    _json_keys(o, keys)
                bad = sorted(keys & _SUSPECT_KEYS)
                if bad:
                    findings.append(f"suspect JSON keys {bad} in {rel}")
            except (UnicodeDecodeError, json.JSONDecodeError):
                findings.append(f"unparseable JSON: {rel}")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            findings.append(f"non-UTF-8 file: {rel}")
            continue
        unknown = sorted({h for h in _HEX64.findall(text) if h not in known})
        if unknown:
            findings.append(f"{len(unknown)} unknown 64-hex string(s) (possible nonce/key) in {rel}: {unknown[0][:16]}…")
    return Check("V7", PASS if not findings else FAIL, {"findings": findings[:20], "n_files": len(pkg.all_files())})


def verify_buyer(pkg_path: str | Path, out_path: Optional[str | Path] = None) -> dict:
    pkg = Package(pkg_path)
    checks = [v1_manifest(pkg), v2_roots(pkg), v3_lineage(pkg), v4_ratios(pkg), v5_canary(pkg), v6_holdout(pkg),
              v7_vault_absent(pkg)]
    result = {"mode": "buyer", "package": pkg.meta.get("package_id"), "verified_utc": utc_now(),
              "checks": [c.to_dict() for c in checks], "overall": _overall(checks)}
    out = Path(out_path) if out_path else pkg.path / "verify_buyer.json"
    out.write_text(pretty_json(result), encoding="utf-8")
    return result


# =============================================================================== examiner E1..E7

def _sample(items: list, n: Optional[int], seed: int) -> list:
    if not n or n >= len(items):
        return list(items)
    return random.Random(seed).sample(items, n)


def check_pseudonyms(docs: dict, k_pseud: bytes) -> dict:
    """E4: docs = {doc_id: (Segmentation, [VaultEntry])}. Every shipped token must equal the HMAC/policy-derived
    token for the vault original; same (class, canonical original) never maps to two tokens (PSEUD_INCONSISTENT);
    two originals never share one token (PSEUD_COLLISION). DATE/AMOUNT tokens are policy-derived per doc, so their
    consistency is checked per doc; all other classes corpus-wide."""
    key_to_tokens: dict[tuple, set] = defaultdict(set)
    token_to_keys: dict[tuple, set] = defaultdict(set)
    inconsistent, n_entries = [], 0
    for doc_id, (seg, entries) in docs.items():
        shift = date_shift_days(k_pseud, doc_id)
        by_idx = {s.idx: s for s in seg.segments}
        for e in entries:
            n_entries += 1
            original = e.original.decode("utf-8", errors="replace")
            expected = make_token(e.cls, original, k_pseud, seg.date_policy, shift)
            shipped = by_idx[e.idx].token if e.idx in by_idx else None
            if shipped != expected or e.token != expected:
                inconsistent.append({"doc_id": doc_id, "idx": e.idx, "class": e.cls, "expected": expected, "shipped": shipped})
            scope = doc_id if e.cls in ("DATE", "AMOUNT_EXACT") else "*"
            key = (scope, e.cls, canonical_original(original))
            key_to_tokens[key].add(shipped)
            token_to_keys[(scope, shipped)].add(key)
    collisions = [{"token": t[1], "originals": len(ks)} for t, ks in token_to_keys.items() if len(ks) > 1]
    split = [{"class": k_[1], "tokens": sorted(x for x in ts if x)} for k_, ts in key_to_tokens.items() if len(ts) > 1]
    return {"ok": not inconsistent and not collisions and not split, "PSEUD_OK": n_entries - len(inconsistent),
            "entries_checked": n_entries, "PSEUD_INCONSISTENT": len(inconsistent) + len(split),
            "PSEUD_COLLISION": len(collisions), "inconsistent": inconsistent[:10], "split": split[:10],
            "collisions": collisions[:10]}


def examine(pkg_path: str | Path, vault: NonceVault, sample: Optional[int] = None, seed: int = 0,
            gazetteer: Optional[Gazetteer] = None, examiner_key: Optional[crypto.SigningKey] = None,
            out_dir: Optional[str | Path] = None, examiner_id: str = "examiner") -> dict:
    pkg = Package(pkg_path)
    gaz = gazetteer or Gazetteer()
    checks: list[Check] = []

    # E1 = V1..V7
    buyer_checks = [v1_manifest(pkg), v2_roots(pkg), v3_lineage(pkg), v4_ratios(pkg), v5_canary(pkg), v6_holdout(pkg),
                    v7_vault_absent(pkg)]
    checks.append(Check("E1", _overall(buyer_checks), {"checks": [c.to_dict() for c in buyer_checks]}))

    roots = pkg.load_roots() if pkg.exists("roots.json") else {"docs": {}}
    m, _ = pkg.manifest()
    manifest_docs = set(m["docs"]) if m else set()
    k = vault.k_pseud

    # gather all commitments (doc_id, segment, vault entry)
    universe = []           # (doc_id, Segment)
    docs_data = {}          # doc_id -> (seg, red, vault doc)
    vault_missing = []
    for doc_id, info in roots["docs"].items():
        if info.get("mode") == MODE_SYNTHESISE:
            continue
        vd = vault.load_doc(doc_id)
        if vd is None:
            vault_missing.append(doc_id)
            continue
        seg = pkg.load_segmentation(doc_id)
        red = pkg.load_redacted(doc_id)
        docs_data[doc_id] = (seg, red, vd)
        for s in seg.segments:
            if s.kind == REDACT:
                universe.append((doc_id, s))
    sampled = _sample(universe, sample, seed)

    # E2 open
    open_ok, open_fail = 0, []
    e3_ok, e3_viol = 0, []
    for doc_id, s in sampled:
        seg, red, vd = docs_data[doc_id]
        entry = next((e for e in vd["entries"] if e.idx == s.idx), None)
        if entry is None:
            open_fail.append({"doc_id": doc_id, "idx": s.idx, "reason": "no vault entry"})
            continue
        c = commitment(doc_id, s.idx, s.start, s.end, s.cls, entry.original, entry.nonce).hex()
        if c == s.commit and (entry.start, entry.end, entry.cls) == (s.start, s.end, s.cls):
            open_ok += 1
        else:
            open_fail.append({"doc_id": doc_id, "idx": s.idx, "reason": "H(...original||nonce) != commit"})
            continue
        # E3 class
        original = entry.original.decode("utf-8", errors="replace")
        if class_predicate(s.cls, original, gaz):
            e3_ok += 1
        else:
            e3_viol.append({"doc_id": doc_id, "idx": s.idx, "class": s.cls, "original_len": len(original)})
    checks.append(Check("E2", PASS if not open_fail and not vault_missing else FAIL,
                        {"sample": len(sampled), "population": len(universe), "seed": seed, "OPEN_OK": open_ok,
                         "OPEN_FAIL": len(open_fail), "failures": open_fail[:10], "vault_missing_docs": vault_missing[:10]}))
    checks.append(Check("E3", PASS if not e3_viol else FAIL,
                        {"CLASS_OK": e3_ok, "CLASS_VIOLATION": len(e3_viol), "violations": e3_viol[:10]}))

    # E4 pseud: whole vault (cheap), against package tokens
    e4 = check_pseudonyms({d: (seg, vd["entries"]) for d, (seg, red, vd) in docs_data.items()}, k)
    checks.append(Check("E4", PASS if e4["ok"] else FAIL, {k_: v for k_, v in e4.items() if k_ != "ok"}))

    # E5 doc_id
    doc_ok, doc_fail = 0, []
    for doc_id, (seg, red, vd) in docs_data.items():
        try:
            rec = reconstruct_original(seg, red, vd["entries"])
            h = sha256_hex(rec)
            if h == doc_id and doc_id in manifest_docs:
                doc_ok += 1
            else:
                doc_fail.append({"doc_id": doc_id, "reconstructed": h, "in_manifest": doc_id in manifest_docs})
        except RebuildError as e:
            doc_fail.append({"doc_id": doc_id, "error": str(e)})
    checks.append(Check("E5", PASS if not doc_fail and not vault_missing else FAIL,
                        {"DOC_OK": doc_ok, "DOC_FAIL": len(doc_fail), "failures": doc_fail[:10]}))

    # E6 residual
    rs = residual_scan(pkg, gaz, episodes=pkg.episodes() if pkg.exists("episodes.jsonl") else None,
                       holdout_commit=pkg.holdout_commit())
    gate_ok, reasons = rs.gate()
    checks.append(Check("E6", PASS if rs.counts["CRITICAL"] == 0 else FAIL,
                        {"counts": rs.counts, "n_kept_segments": rs.n_kept_segments, "gate": {"pass": gate_ok, "reasons": reasons},
                         "findings": [f.to_dict() for f in rs.findings[:25]]}))

    # E7 origin
    scope = pkg.meta.get("declared_scope") or {}
    insts = set(scope.get("institutions", []))
    ps, pe = scope.get("period_start", ""), scope.get("period_end", "")
    out_of_scope = []
    sampled_docs = sorted({d for d, _ in sampled}) or sorted(docs_data)
    for doc_id in sampled_docs:
        o = docs_data[doc_id][2]["origin"]
        if insts and o.institution_code not in insts:
            out_of_scope.append({"doc_id": doc_id, "institution_code": o.institution_code})
        elif ps and pe and not (ps <= o.period_start and o.period_end <= pe):
            out_of_scope.append({"doc_id": doc_id, "period": [o.period_start, o.period_end]})
    checks.append(Check("E7", PASS if not out_of_scope and scope else (WARN if not scope else FAIL),
                        {"declared_scope": scope, "docs_checked": len(sampled_docs), "out_of_scope": out_of_scope[:10]}))

    # ratios recomputed
    ratios = compute_ratios(pkg.atoms()) if pkg.exists("lineage.jsonl") else None
    overall = _overall(checks)
    date = utc_now()
    pid = pkg.meta.get("package_id")
    e2, e3, e4, e5, e6, e7 = (checks[i].evidence for i in range(1, 7))
    pct = ratios["by_bytes"]["pct"] if ratios else {}
    statement = (
        f"On {date}, over sample {len(sampled)} of {len(universe)} commitments (seed {seed}) in package {pid}: "
        f"E2 {e2['OPEN_OK']}/{len(sampled)} OPEN_OK; E3 {e3['CLASS_OK']}/{len(sampled)} CLASS_OK, "
        f"{e3['CLASS_VIOLATION']} CLASS_VIOLATION; E4 {e4['PSEUD_INCONSISTENT']} PSEUD_INCONSISTENT, "
        f"{e4['PSEUD_COLLISION']} PSEUD_COLLISION; E5 {e5['DOC_OK']}/{e5['DOC_OK'] + e5['DOC_FAIL']} DOC_OK; "
        f"ratios (recomputed, by bytes): SPAN_VERIFIED {pct.get('SPAN_VERIFIED', 0):.1%}, "
        f"PSEUDONYMISED_TRACEABLE {pct.get('PSEUDONYMISED_TRACEABLE', 0):.1%}, "
        f"SYNTHETIC_UNPROVABLE {pct.get('SYNTHETIC_UNPROVABLE', 0):.1%}, tier {ratios['tier'] if ratios else 'n/a'}; "
        f"residual scan: CRITICAL {e6['counts']['CRITICAL']}, HIGH {e6['counts']['HIGH']}, MEDIUM {e6['counts']['MEDIUM']}; "
        f"origin: {'all' if not e7['out_of_scope'] else str(len(sampled_docs) - len(e7['out_of_scope'])) + ' of ' + str(len(sampled_docs))} "
        f"sampled docs within {sorted(insts) if insts else 'undeclared institutions'}/"
        f"{(ps + '..' + pe) if ps and pe else 'undeclared period'}."
    )
    report = {"mode": "examiner", "examiner_id": examiner_id, "package": pid, "recipient_id": pkg.meta.get("recipient_id"),
              "verified_utc": date, "sample": len(sampled), "population": len(universe), "seed": seed,
              "checks": [c.to_dict() for c in checks], "ratios_recomputed": ratios, "overall": overall,
              "statement": statement,
              "scope_limits": ("This finding is limited to the enumerated checks over the stated sample. It is not an opinion "
                               "on semantic safety of kept text, correctness of doctrine, or absence of re-identification "
                               "via operational detail (SPEC-02 §0 non-claims; T7).")}
    out = Path(out_dir) if out_dir else pkg.path
    out.mkdir(parents=True, exist_ok=True)
    rp = out / "report.json"
    rp.write_text(pretty_json(report), encoding="utf-8")
    key = examiner_key or crypto.SigningKey.generate()
    key.sign_file(rp)
    key.public().save(out / "examiner.pub")
    (out / "report.md").write_text(render_report_md(report), encoding="utf-8")
    return report


def render_report_md(report: dict) -> str:
    lines = [f"# LAT examiner report — package {report.get('package')}", "",
             f"Examiner: `{report.get('examiner_id')}`  ·  Date: {report.get('verified_utc')}  ·  "
             f"Overall: **{report.get('overall')}**", "", "## Finding (scoped statement)", "", report["statement"], "",
             "## Checks", "", "| id | status | evidence (abridged) |", "|---|---|---|"]
    for c in report["checks"]:
        ev = {k: v for k, v in c["evidence"].items() if k not in ("checks", "findings", "declared_scope")}
        s = json.dumps(ev, ensure_ascii=False)
        if len(s) > 160:
            s = s[:157] + "..."
        lines.append(f"| {c['id']} | {c['status']} | `{s.replace('|', '/')}` |")
    e1 = next((c for c in report["checks"] if c["id"] == "E1"), None)
    if e1:
        lines += ["", "### E1 = buyer checks V1–V7", "", "| id | status |", "|---|---|"]
        lines += [f"| {c['id']} | {c['status']} |" for c in e1["evidence"]["checks"]]
    lines += ["", "## Limits", "", report["scope_limits"], ""]
    return "\n".join(lines)
