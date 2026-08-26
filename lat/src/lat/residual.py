"""SPEC-02 §7 RESIDUAL_SCAN — heuristic scan of kept text. Never claimed as proof (§0 non-claims, T7).

R1 NER re-run over kept text: PERSON/ORG not in allowlist                      -> HIGH
R2 ids/emails/phones/IBAN (always) and LEI/ISIN with name context              -> CRITICAL
R3 quasi-identifier tuples (product, size_band, date_bucket, venue) with k<K_MIN -> MEDIUM
R4 ⟦COUNTERPARTY:x⟧ within 40 chars of a surviving proper noun                 -> MEDIUM
R5 near-dup of episode task text vs holdout (MinHash Jaccard >= 0.8)            -> CRITICAL
Gates: CRITICAL == 0; HIGH <= 0.1% of kept segments; MEDIUM reported only.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

import regex as re

from .classes import (ACCOUNT_RE, AMOUNT_RE, EMAIL_RE, Gazetteer, IBAN_RE, ISIN_RE, LEI_RE, PHONE_RE, TOKEN_RE,
                      TRADE_RE, amount_band, canonical_original)
from .holdout import near_dups_against_items, near_dups_against_sketches
from .models import KEEP, Episode
from .ner import Detector, RuleDetector
from .redact import WorkDir, rebuild_leaves

K_MIN = 5
HIGH_MAX_FRACTION = 0.001
PROPER_NOUN_RE = re.compile(r"\b[A-Z][a-z]{2,}\b")
_STOP = {"the", "please", "this", "that", "these", "those", "our", "your", "their", "from", "subject", "author", "kind",
         "best", "regards", "thanks", "hello", "dear", "note", "operations", "client", "settlement", "margin", "trade"}
_MONTHS_DAYS = {"january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
                "november", "december", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}


@dataclass
class Finding:
    rule: str
    severity: str
    doc_id: str
    detail: str
    offset: int = -1

    def to_dict(self):
        return {"rule": self.rule, "severity": self.severity, "doc_id": self.doc_id, "detail": self.detail,
                "offset": self.offset}


@dataclass
class ScanResult:
    findings: list[Finding] = field(default_factory=list)
    n_kept_segments: int = 0
    n_docs: int = 0

    @property
    def counts(self) -> dict:
        c = Counter(f.severity for f in self.findings)
        return {"CRITICAL": c["CRITICAL"], "HIGH": c["HIGH"], "MEDIUM": c["MEDIUM"]}

    def gate(self) -> tuple[bool, list[str]]:
        c = self.counts
        reasons = []
        if c["CRITICAL"] > 0:
            reasons.append(f"CRITICAL findings: {c['CRITICAL']} (required 0)")
        allowed = HIGH_MAX_FRACTION * max(self.n_kept_segments, 1)
        if c["HIGH"] > allowed:
            reasons.append(f"HIGH findings: {c['HIGH']} > {HIGH_MAX_FRACTION:.1%} of {self.n_kept_segments} kept segments")
        return not reasons, reasons

    def to_dict(self):
        ok, reasons = self.gate()
        return {"counts": self.counts, "n_kept_segments": self.n_kept_segments, "n_docs": self.n_docs,
                "gate": {"pass": ok, "reasons": reasons}, "findings": [f.to_dict() for f in self.findings],
                "disclaimer": "Heuristic scan; absence of findings is not proof of non-re-identifiability (SPEC-02 §0, T7)."}


def _token_spans(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in TOKEN_RE.finditer(text)]


def _in_token(spans, s, e) -> bool:
    return any(s < te and e > ts for ts, te in spans)


def _sentence_start(text: str, pos: int) -> bool:
    prefix = text[:pos].rstrip()
    return not prefix or prefix[-1] in ".!?:;\n-—]*" or prefix.endswith(("\n", "- "))


def _proper_nouns(text: str, lo: int, hi: int, gaz: Gazetteer):
    """Surviving proper nouns in text[lo:hi]: capitalised words not at sentence start, not stopwords/months/allowlist."""
    for m in PROPER_NOUN_RE.finditer(text, lo, hi):
        w = m.group(0)
        if w.casefold() in _MONTHS_DAYS or w.casefold() in _STOP or gaz.allowed(w) or _sentence_start(text, m.start()):
            continue
        yield m.start(), w


def _has_name_context(text: str, pos: int, gaz: Gazetteer, window: int = 60) -> bool:
    lo, hi = max(0, pos - window), min(len(text), pos + window)
    return any(True for _ in _proper_nouns(text, lo, hi, gaz))


def scan_doc_text(doc_id: str, text: str, gaz: Gazetteer, detector: Detector) -> list[Finding]:
    """R1, R2, R4 over the redacted text of one doc (tokens are skipped; only kept text is inspected)."""
    out: list[Finding] = []
    tspans = _token_spans(text)
    # R1
    for d in detector.detect(text):
        if _in_token(tspans, d.start, d.end):
            continue
        if d.cls in ("PERSON", "LEGAL_ENTITY", "COUNTERPARTY", "CLIENT") and not gaz.allowed(d.text):
            out.append(Finding("R1", "HIGH", doc_id, f"{d.cls} surviving in kept text: {d.text!r}", d.start))
    # R2
    for rx, label, always in ((EMAIL_RE, "EMAIL", True), (PHONE_RE, "PHONE", True), (IBAN_RE, "IBAN", True),
                              (ACCOUNT_RE, "ACCOUNT_ID", True), (TRADE_RE, "TRADE_ID", True),
                              (LEI_RE, "LEI", False), (ISIN_RE, "ISIN", False)):
        for m in rx.finditer(text):
            if _in_token(tspans, m.start(), m.end()):
                continue
            if always or _has_name_context(text, m.start(), gaz):
                out.append(Finding("R2", "CRITICAL", doc_id, f"{label} in kept text: {m.group(0)!r}", m.start()))
            else:
                out.append(Finding("R2", "MEDIUM", doc_id, f"{label} without name context: {m.group(0)!r}", m.start()))
    # R4
    for m in TOKEN_RE.finditer(text):
        if m.group(1) != "COUNTERPARTY":
            continue
        lo, hi = max(0, m.start() - 40), min(len(text), m.end() + 40)
        for s, w in _proper_nouns(text, lo, hi, gaz):
            if _in_token(tspans, s, s + len(w)):
                continue
            out.append(Finding("R4", "MEDIUM", doc_id, f"{m.group(0)} within 40 chars of proper noun {w!r}", s))
            break
    return out


def quasi_tuple(text: str, gaz: Gazetteer) -> tuple:
    low = text.casefold()
    product = next((p for p in sorted(gaz.products, key=len, reverse=True) if p.casefold() in low), None)
    venue = next((v for v in sorted(gaz.venues, key=len, reverse=True) if v.casefold() in low), None)
    band = None
    m = re.search(r"⟦AMOUNT:([^⟧]+)⟧", text)
    if m:
        band = m.group(1)
    else:
        m = AMOUNT_RE.search(text)
        if m:
            band = amount_band(m.group(0))
    bucket = None
    m = re.search(r"⟦DATE:(\d{4}-\d{2})", text)
    if m:
        bucket = m.group(1)
    return (product, band, bucket, venue)


def scan(work: WorkDir, gaz: Optional[Gazetteer] = None, detector: Optional[Detector] = None,
         episodes: Optional[list[Episode]] = None, holdout_commit: Optional[dict] = None,
         holdout_items: Optional[list[dict]] = None, k_min: int = K_MIN) -> ScanResult:
    gaz = gaz or Gazetteer()
    detector = detector or RuleDetector(gaz)
    res = ScanResult()
    tuples: dict[str, tuple] = {}
    for doc_id in work.doc_ids():
        seg = work.load_segmentation(doc_id)
        red = work.load_redacted(doc_id)
        res.n_docs += 1
        res.n_kept_segments += sum(1 for s in seg.segments if s.kind == KEEP)
        text = red.decode("utf-8")
        res.findings.extend(scan_doc_text(doc_id, text, gaz, detector))
        tuples[doc_id] = quasi_tuple(text, gaz)
    # R3
    freq = Counter(t for t in tuples.values())
    for doc_id, t in tuples.items():
        if sum(1 for x in t if x is not None) < 2:
            continue
        if freq[t] < k_min:
            res.findings.append(Finding("R3", "MEDIUM", doc_id, f"quasi-identifier tuple {t} has k={freq[t]} < {k_min}"))
    # R5
    if episodes:
        texts = [(e.episode_id, e.task_text) for e in episodes if e.task_text]
        hits = []
        if holdout_items is not None:
            hits = near_dups_against_items(texts, holdout_items)
        elif holdout_commit is not None:
            hits = near_dups_against_sketches(texts, holdout_commit)
        for h in hits:
            res.findings.append(Finding("R5", "CRITICAL", "", f"episode {h['label']} near-dup of holdout item "
                                                             f"{h['item_id']} (jaccard {h['jaccard']})"))
    return res
