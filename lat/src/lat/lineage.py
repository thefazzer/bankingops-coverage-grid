"""SPEC-02 §2 Atom/Episode, C3 — lineage build (seller) and per-atom lineage checks (buyer V3).

Atom content is checked after `strip_carriers` (canary code points removed) and NFC.
content_sha256 = sha256(NFC(strip_carriers(content)))."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Optional

from .canary import strip_carriers
from .classes import DERIVATION_OPS, LINEAGE_CLASSES, OP_TO_LINEAGE
from .crypto import keep_leaf
from .encoding import nfc, sha256_hex, utf8
from .models import KEEP, MODE_SYNTHESISE, REDACT, Atom, Episode, Segmentation, SourceDoc, SpanRef
from .redact import RebuildError, WorkDir, char_to_byte_offsets, rebuild_leaves

GENERATOR_VERSION = "lat-lineage/0.1.0"


def canonical_content(content: str) -> str:
    return nfc(strip_carriers(content))


def content_hash(content: str) -> str:
    return sha256_hex(utf8(canonical_content(content)))


# --------------------------------------------------------------------------- build

class LineageBuildError(Exception):
    pass


class DocView:
    """Cached per-doc view: segmentation, redacted bytes, rebuilt leaves and chunks."""

    def __init__(self, work: WorkDir, doc_id: str):
        self.doc_id = doc_id
        self.seg: Segmentation = work.load_segmentation(doc_id)
        self.redacted: bytes = work.load_redacted(doc_id)
        self.leaves, self.chunks = rebuild_leaves(doc_id, self.seg, self.redacted)

    def overlapping(self, bs: int, be: int):
        return [s for s in self.seg.segments if s.start < be and s.end > bs]


def build_atom_from_span(episode_id: str, seq: int, op: str, doc: SourceDoc, view: DocView, cstart: int, cend: int,
                         generator_version: str = GENERATOR_VERSION) -> Atom:
    """QUOTE / PSEUDONYMISE atom from a char span of the *source* text."""
    offs = char_to_byte_offsets(doc.text)
    bs, be = offs[cstart], offs[cend]
    if be <= bs:
        raise LineageBuildError("empty span")
    segs = view.overlapping(bs, be)
    parts, refs = [], []
    for s in segs:
        if s.kind == KEEP:
            parts.append(doc.data[max(bs, s.start):min(be, s.end)])
        else:
            if op == "QUOTE":
                raise LineageBuildError(f"QUOTE span [{cstart},{cend}) overlaps REDACT segment {s.idx} "
                                        f"({s.cls}); use PSEUDONYMISE")
            parts.append(s.token.encode("utf-8"))
        refs.append(SpanRef(doc.doc_id, s.idx, view.leaves[s.idx].hex()))
    content = b"".join(parts).decode("utf-8")
    atom_id = f"{episode_id}/a{seq:03d}"
    return Atom(atom_id, episode_id, content, op, OP_TO_LINEAGE[op], refs, generator_version, content_hash(content))


def build_synthetic_atom(episode_id: str, seq: int, op: str, content: str, refs: Optional[list[SpanRef]] = None,
                         generator_version: str = GENERATOR_VERSION) -> Atom:
    if op not in ("PARAPHRASE", "SYNTHESISE"):
        raise LineageBuildError(op)
    atom_id = f"{episode_id}/a{seq:03d}"
    return Atom(atom_id, episode_id, content, op, OP_TO_LINEAGE[op], refs or [], generator_version,
                content_hash(content))


def episode_summary(atoms: list[Atom]) -> dict:
    by_atoms = Counter(a.lineage_class for a in atoms)
    by_bytes = Counter()
    for a in atoms:
        by_bytes[a.lineage_class] += len(utf8(canonical_content(a.content)))
    return {"by_atoms": {c: by_atoms.get(c, 0) for c in LINEAGE_CLASSES},
            "by_bytes": {c: by_bytes.get(c, 0) for c in LINEAGE_CLASSES}, "n_atoms": len(atoms)}


def build_lineage(spec: dict, docs: list[SourceDoc], work: WorkDir, roots: dict) -> tuple[list[Atom], list[Episode]]:
    """spec = {"episodes":[{episode_id, task_id, task_text, trace_ref, verifier_ref,
                             atoms:[{op, doc, start, end} | {op, content}]}]}
    `doc` may be a source filename or a doc_id. Docs in SYNTHESISE mode only accept SYNTHESISE atoms."""
    by_name = {d.name: d for d in docs}
    by_id = {d.doc_id: d for d in docs}
    views: dict[str, DocView] = {}
    atoms: list[Atom] = []
    episodes: list[Episode] = []
    for ep in spec["episodes"]:
        eid = ep["episode_id"]
        ep_atoms: list[Atom] = []
        for seq, a in enumerate(ep["atoms"]):
            op = a["op"]
            if op not in DERIVATION_OPS:
                raise LineageBuildError(f"{eid}: unknown op {op}")
            doc = by_name.get(a.get("doc")) or by_id.get(a.get("doc"))
            if op in ("QUOTE", "PSEUDONYMISE"):
                if doc is None:
                    raise LineageBuildError(f"{eid}: atom {seq} references unknown doc {a.get('doc')}")
                mode = roots["docs"].get(doc.doc_id, {}).get("mode")
                if mode == MODE_SYNTHESISE:
                    raise LineageBuildError(f"{eid}: {op} atom on SYNTHESISE-mode doc {doc.doc_id[:12]} (§1 hard boundary)")
                if doc.doc_id not in views:
                    views[doc.doc_id] = DocView(work, doc.doc_id)
                ep_atoms.append(build_atom_from_span(eid, seq, op, doc, views[doc.doc_id], int(a["start"]), int(a["end"])))
            else:
                # synthetic atoms carry no verified refs (§1: SYNTHESISE output is unprovable, always)
                ep_atoms.append(build_synthetic_atom(eid, seq, op, a["content"], []))
        atoms.extend(ep_atoms)
        episodes.append(Episode(eid, ep.get("task_id", eid), [x.atom_id for x in ep_atoms], ep.get("trace_ref", ""),
                                ep.get("verifier_ref", ""), ep.get("task_text", ""), episode_summary(ep_atoms)))
    return atoms, episodes


# --------------------------------------------------------------------------- IO

def write_jsonl(path: str | Path, rows: list[dict]) -> None:
    with Path(path).open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n")


def read_jsonl(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def load_atoms(path: str | Path) -> list[Atom]:
    return [Atom.from_dict(r) for r in read_jsonl(path)]


def load_episodes(path: str | Path) -> list[Episode]:
    return [Episode.from_dict(r) for r in read_jsonl(path)]


# --------------------------------------------------------------------------- checks (V3 / G7)

class ViewCache:
    def __init__(self, work: WorkDir):
        self.work = work
        self.views: dict[str, DocView] = {}
        self.errors: dict[str, str] = {}

    def get(self, doc_id: str) -> Optional[DocView]:
        if doc_id in self.errors:
            return None
        if doc_id not in self.views:
            try:
                self.views[doc_id] = DocView(self.work, doc_id)
            except (FileNotFoundError, RebuildError, ValueError) as e:
                self.errors[doc_id] = str(e)
                return None
        return self.views[doc_id]


def check_atom(atom: Atom, cache: ViewCache) -> list[str]:
    """Return list of problems (empty == atom passes V3 checks)."""
    p: list[str] = []
    if atom.derivation_op not in DERIVATION_OPS:
        p.append(f"unknown derivation_op {atom.derivation_op}")
        return p
    if atom.lineage_class != OP_TO_LINEAGE[atom.derivation_op]:
        p.append(f"lineage_class {atom.lineage_class} inconsistent with derivation_op {atom.derivation_op}")
    if atom.content_sha256 != content_hash(atom.content):
        p.append("content_sha256 mismatch")
    content = utf8(canonical_content(atom.content))
    resolved = []
    for r in atom.span_refs:
        v = cache.get(r.doc_id)
        if v is None:
            p.append(f"span_ref doc {r.doc_id[:12]} not resolvable: {cache.errors.get(r.doc_id, 'missing')}")
            continue
        if r.idx < 0 or r.idx >= len(v.leaves):
            p.append(f"span_ref idx {r.idx} out of range for {r.doc_id[:12]}")
            continue
        if v.leaves[r.idx].hex() != r.leaf_or_commit:
            p.append(f"span_ref {r.doc_id[:12]}#{r.idx}: leaf_or_commit does not match rebuilt leaves")
            continue
        resolved.append((v, r.idx))
    if atom.lineage_class == "SPAN_VERIFIED":
        if not atom.span_refs:
            p.append("SPAN_VERIFIED atom without span_refs")
        for v, i in resolved:
            if v.seg.segments[i].kind != KEEP:
                p.append(f"SPAN_VERIFIED atom references REDACT segment {v.doc_id[:12]}#{i}")
        if resolved and len(resolved) == len(atom.span_refs):
            kept = b"".join(v.chunks[i] for v, i in resolved if v.seg.segments[i].kind == KEEP)
            if content not in kept:
                p.append("content is not a substring of the referenced KEEP segments")
    elif atom.lineage_class == "PSEUDONYMISED_TRACEABLE":
        if not atom.span_refs:
            p.append("PSEUDONYMISED_TRACEABLE atom without span_refs")
        if resolved and len(resolved) == len(atom.span_refs):
            red = b"".join(v.chunks[i] for v, i in resolved)
            if content not in red:
                p.append("content is not a substring of the RedactedDoc over referenced segments")
    elif atom.lineage_class != "SYNTHETIC_UNPROVABLE":
        p.append(f"unknown lineage_class {atom.lineage_class}")
    return p


def check_lineage(atoms: list[Atom], episodes: list[Episode], work: WorkDir) -> dict:
    cache = ViewCache(work)
    failures = {}
    for a in atoms:
        probs = check_atom(a, cache)
        if probs:
            failures[a.atom_id] = probs
    atom_ids = {a.atom_id for a in atoms}
    ep_probs = []
    seen = set()
    for e in episodes:
        for aid in e.atoms:
            if aid not in atom_ids:
                ep_probs.append(f"episode {e.episode_id} references missing atom {aid}")
            seen.add(aid)
        ep_atoms = [a for a in atoms if a.episode_id == e.episode_id]
        if e.lineage_summary and e.lineage_summary != episode_summary(ep_atoms):
            ep_probs.append(f"episode {e.episode_id}: lineage_summary does not recompute")
    for a in atoms:
        if a.atom_id not in seen:
            ep_probs.append(f"atom {a.atom_id} not listed in any episode")
    dup = [k for k, v in Counter(a.atom_id for a in atoms).items() if v > 1]
    if dup:
        ep_probs.append(f"duplicate atom ids: {dup[:5]}")
    return {"ok": not failures and not ep_probs, "n_atoms": len(atoms), "n_failed": len(failures),
            "atom_failures": failures, "episode_problems": ep_probs}


def check_modes(atoms: list[Atom], roots: dict) -> list[str]:
    """G7 MODE_GATE: PARAPHRASE/SYNTHESISE atoms must be SYNTHETIC_UNPROVABLE; no mixed-mode docs."""
    probs = []
    doc_ops: dict[str, set] = {}
    for a in atoms:
        if a.derivation_op in ("PARAPHRASE", "SYNTHESISE") and a.lineage_class != "SYNTHETIC_UNPROVABLE":
            probs.append(f"{a.atom_id}: {a.derivation_op} atom carries {a.lineage_class}")
        for r in a.span_refs:
            doc_ops.setdefault(r.doc_id, set()).add(a.derivation_op)
    for doc_id, ops in doc_ops.items():
        mode = roots.get("docs", {}).get(doc_id, {}).get("mode")
        if mode == MODE_SYNTHESISE and ops & {"QUOTE", "PSEUDONYMISE"}:
            probs.append(f"doc {doc_id[:12]}: SYNTHESISE-mode doc referenced by verifiable atoms")
        if ops & {"QUOTE", "PSEUDONYMISE"} and ops & {"SYNTHESISE"}:
            probs.append(f"doc {doc_id[:12]}: mixed-mode atoms {sorted(ops)}")
    return probs
