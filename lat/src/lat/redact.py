"""SPEC-02 §2/§4 — segmentation, commitments, keep leaves, doc roots, redacted docs, vault entries.

Byte offsets throughout: a SourceDoc is NFC-normalised UTF-8 bytes; segments partition [0,len(bytes)).
Detectors work on str/char offsets; `char_to_byte_offsets` converts.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .classes import (CLASS_SET, TOKEN_CLOSE, TOKEN_OPEN, amount_band, canonical_original, date_shift_days,
                      date_token_value)
from .crypto import commitment, keep_leaf, merkle_root, new_nonce, pseudonym_id
from .encoding import nfc, pretty_json, sha256_hex
from .models import (KEEP, MODE_PSEUDONYMISE, MODE_SYNTHESISE, REDACT, Origin, Segment, Segmentation, SourceDoc,
                     VaultEntry)
from .ner import Detector
from .vault import NonceVault

LAT_VERSION = "0.1.0"


# --------------------------------------------------------------------------- source loading

def load_source_docs(source_dir: str | Path) -> list[SourceDoc]:
    """Load *.txt docs (NFC-normalised) + optional origins.json {filename: origin}."""
    d = Path(source_dir)
    docs_dir = d / "docs" if (d / "docs").is_dir() else d
    origins = {}
    op = d / "origins.json"
    if op.exists():
        origins = json.loads(op.read_text(encoding="utf-8"))
    docs = []
    for p in sorted(docs_dir.glob("*.txt")):
        text = p.read_text(encoding="utf-8")
        docs.append(SourceDoc.from_text(text, Origin.from_dict(origins.get(p.name)), p.name))
    return docs


def char_to_byte_offsets(text: str) -> list[int]:
    offs = [0]
    for ch in text:
        offs.append(offs[-1] + len(ch.encode("utf-8")))
    return offs


# --------------------------------------------------------------------------- tokens

def make_token(cls: str, original: str, k_pseud: bytes, date_policy: str, shift_days: int) -> str:
    if cls == "DATE":
        v = date_token_value(original, date_policy, shift_days)
        if v is None:  # unparsable date-like string: fall back to HMAC pseudonym
            v = pseudonym_id(k_pseud, cls, canonical_original(original))
        return f"{TOKEN_OPEN}DATE:{v}{TOKEN_CLOSE}"
    if cls == "AMOUNT_EXACT":
        return f"{TOKEN_OPEN}AMOUNT:{amount_band(original)}{TOKEN_CLOSE}"
    return f"{TOKEN_OPEN}{cls}:{pseudonym_id(k_pseud, cls, canonical_original(original))}{TOKEN_CLOSE}"


# --------------------------------------------------------------------------- segmentation

def segment_doc(doc: SourceDoc, detector: Detector) -> list[tuple[int, int, str]]:
    """Run detector, return sorted non-overlapping REDACT byte spans [(start,end,class)]."""
    text = doc.text
    offs = char_to_byte_offsets(text)
    spans = []
    for det in detector.detect(text):
        if det.cls not in CLASS_SET:
            raise ValueError(f"detector returned unknown class {det.cls}")
        if det.end <= det.start:
            continue
        spans.append((offs[det.start], offs[det.end], det.cls))
    spans.sort()
    last = 0
    for s, e, _ in spans:
        if s < last:
            raise ValueError("overlapping detections")
        last = e
    return spans


@dataclass
class RedactResult:
    doc_id: str
    segmentation: Segmentation
    redacted: bytes
    root: bytes
    entries: list[VaultEntry]
    mode: str


def redact_doc(doc: SourceDoc, detector: Detector, vault: NonceVault, mode: str = MODE_PSEUDONYMISE,
               date_policy: str = "shift_per_doc_v1", persist: bool = True) -> RedactResult:
    """Pseudonymise one doc: segments, commitments (nonce reused from vault if present → G8 determinism),
    keep leaves, root. SYNTHESISE mode records the doc as unprovable: no redacted output, root=None."""
    if mode == MODE_SYNTHESISE:
        if persist:
            vault.save_doc(doc.doc_id, [], doc.origin, mode, date_policy, 0, doc.name)
        seg = Segmentation(doc.doc_id, [], date_policy, mode)
        return RedactResult(doc.doc_id, seg, b"", b"", [], mode)

    k = vault.k_pseud
    shift = date_shift_days(k, doc.doc_id)
    known = vault.existing_nonces(doc.doc_id)
    spans = segment_doc(doc, detector)
    data = doc.data
    segments: list[Segment] = []
    entries: list[VaultEntry] = []
    leaves: list[bytes] = []
    out = bytearray()
    pos = 0
    idx = 0

    def add_keep(s, e):
        nonlocal idx
        chunk = data[s:e]
        segments.append(Segment(idx, s, e, KEEP))
        leaves.append(keep_leaf(doc.doc_id, idx, s, e, chunk))
        out.extend(chunk)
        idx += 1

    for s, e, cls in spans:
        if s > pos:
            add_keep(pos, s)
        original = data[s:e]
        token = make_token(cls, original.decode("utf-8"), k, date_policy, shift)
        nonce = known.get((idx, s, e, cls, original)) or new_nonce()
        c = commitment(doc.doc_id, idx, s, e, cls, original, nonce)
        segments.append(Segment(idx, s, e, REDACT, cls, token, c.hex()))
        entries.append(VaultEntry(idx, s, e, cls, original, nonce, token))
        leaves.append(c)
        out.extend(token.encode("utf-8"))
        idx += 1
        pos = e
    if pos < len(data):
        add_keep(pos, len(data))
    seg = Segmentation(doc.doc_id, segments, date_policy, mode)
    if persist:
        vault.save_doc(doc.doc_id, entries, doc.origin, mode, date_policy, shift, doc.name)
    return RedactResult(doc.doc_id, seg, bytes(out), merkle_root(leaves), entries, mode)


# --------------------------------------------------------------------------- verifier-side rebuild (V2)

class RebuildError(Exception):
    pass


def rebuild_leaves(doc_id: str, seg: Segmentation, redacted: bytes) -> tuple[list[bytes], list[bytes]]:
    """From redacted bytes + segmentation (commitments taken as given) rebuild the ordered leaf list
    and the per-segment redacted byte chunks. Raises RebuildError on any inconsistency."""
    errs = seg.check_partition()
    if errs:
        raise RebuildError("; ".join(errs))
    leaves, chunks = [], []
    pos = 0
    for s in seg.segments:
        if s.kind == KEEP:
            n = s.end - s.start
            chunk = redacted[pos:pos + n]
            if len(chunk) != n:
                raise RebuildError(f"segment {s.idx}: redacted text too short")
            leaves.append(keep_leaf(doc_id, s.idx, s.start, s.end, chunk))
        else:
            tok = s.token.encode("utf-8")
            chunk = redacted[pos:pos + len(tok)]
            if chunk != tok:
                raise RebuildError(f"segment {s.idx}: token mismatch in redacted text")
            try:
                leaves.append(bytes.fromhex(s.commit))
            except ValueError:
                raise RebuildError(f"segment {s.idx}: bad commit hex")
        chunks.append(chunk)
        pos += len(chunk)
    if pos != len(redacted):
        raise RebuildError(f"redacted text has {len(redacted) - pos} trailing bytes not covered by segmentation")
    return leaves, chunks


def rebuild_root(doc_id: str, seg: Segmentation, redacted: bytes) -> bytes:
    leaves, _ = rebuild_leaves(doc_id, seg, redacted)
    return merkle_root(leaves)


def reconstruct_original(seg: Segmentation, redacted: bytes, entries: list[VaultEntry]) -> bytes:
    """Examiner E5: kept chunks from redacted text + originals from vault → source bytes."""
    _, chunks = rebuild_leaves(seg.doc_id, seg, redacted)
    by_idx = {e.idx: e for e in entries}
    out = bytearray()
    for s, chunk in zip(seg.segments, chunks):
        if s.kind == KEEP:
            out.extend(chunk)
        else:
            if s.idx not in by_idx:
                raise RebuildError(f"vault has no entry for segment {s.idx}")
            out.extend(by_idx[s.idx].original)
    return bytes(out)


# --------------------------------------------------------------------------- work dir IO

class WorkDir:
    """Seller-side build directory (also the read model for a package: same relative layout)."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    @property
    def seg_dir(self) -> Path:
        return self.path / "segmentation"

    @property
    def red_dir(self) -> Path:
        return self.path / "redacted"

    def write_result(self, r: RedactResult) -> None:
        if r.mode == MODE_SYNTHESISE:  # unprovable doc: nothing verifiable is shipped; drop stale outputs
            for p in (self.seg_dir / f"{r.doc_id}.json", self.red_dir / f"{r.doc_id}.txt"):
                if p.exists():
                    p.unlink()
            return
        self.seg_dir.mkdir(parents=True, exist_ok=True)
        self.red_dir.mkdir(parents=True, exist_ok=True)
        (self.seg_dir / f"{r.doc_id}.json").write_text(pretty_json(r.segmentation.to_dict()), encoding="utf-8")
        (self.red_dir / f"{r.doc_id}.txt").write_bytes(r.redacted)

    def write_roots(self, results: list[RedactResult], date_policy: str, existing: Optional[dict] = None) -> dict:
        roots = existing or {"version": 1, "lat_version": LAT_VERSION, "date_policy": date_policy, "docs": {}}
        for r in results:
            roots["docs"][r.doc_id] = {"mode": r.mode, "root": r.root.hex() if r.mode != MODE_SYNTHESISE else None,
                                       "n_segments": len(r.segmentation.segments)}
        roots["docs"] = dict(sorted(roots["docs"].items()))
        self.path.mkdir(parents=True, exist_ok=True)
        (self.path / "roots.json").write_text(pretty_json(roots), encoding="utf-8")
        return roots

    def load_roots(self) -> dict:
        return json.loads((self.path / "roots.json").read_text(encoding="utf-8"))

    def doc_ids(self) -> list[str]:
        return sorted(p.stem for p in self.seg_dir.glob("*.json")) if self.seg_dir.exists() else []

    def load_segmentation(self, doc_id: str) -> Segmentation:
        return Segmentation.from_dict(json.loads((self.seg_dir / f"{doc_id}.json").read_text(encoding="utf-8")))

    def load_redacted(self, doc_id: str) -> bytes:
        return (self.red_dir / f"{doc_id}.txt").read_bytes()


def redact_corpus(docs: list[SourceDoc], detector: Detector, vault: NonceVault, work: WorkDir,
                  mode: str = MODE_PSEUDONYMISE, date_policy: str = "shift_per_doc_v1",
                  sign: bool = True) -> list[RedactResult]:
    results = []
    for doc in docs:
        r = redact_doc(doc, detector, vault, mode, date_policy)
        work.write_result(r)
        results.append(r)
    existing = work.load_roots() if (work.path / "roots.json").exists() else None
    if existing and existing.get("date_policy") != date_policy:
        existing = None
    work.write_roots(results, date_policy, existing)
    if sign:
        vault.signing_key.sign_file(work.path / "roots.json")
        (work.path / "pubkeys").mkdir(exist_ok=True)
        vault.signing_key.public().save(work.path / "pubkeys" / "seller.pub")
    return results
