"""SPEC-02 §4 — pluggable detection pipeline. No ML dependency: the default `RuleDetector`
combines regexes (ids/emails/phones/dates/amounts), a seller-supplied gazetteer
(COUNTERPARTY/CLIENT/INTERNAL_SYSTEM/LOCATION/PERSON) and capitalised-multiword heuristics
(PERSON / LEGAL_ENTITY). Any object implementing `Detector.detect(text) -> list[Detection]`
can be plugged in (e.g. a spaCy-backed detector) — the rest of LAT is agnostic."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Protocol, runtime_checkable

import regex as re

from .classes import (ACCOUNT_RE, AMOUNT_RE, CAP_MULTIWORD_RE, DATE_RE, EMAIL_RE, Gazetteer, IBAN_RE,
                      LEGAL_SUFFIX_RE, PHONE_RE, TRADE_RE, canonical_original)


@dataclass(frozen=True)
class Detection:
    start: int      # char offset (inclusive)
    end: int        # char offset (exclusive)
    cls: str
    text: str
    source: str = "rule"


@runtime_checkable
class Detector(Protocol):
    def detect(self, text: str) -> list[Detection]: ...


# Priority when spans overlap: higher wins; ties -> longer span, then earlier.
PRIORITY = {
    "EMAIL": 100, "ACCOUNT_ID": 95, "TRADE_ID": 95, "PHONE": 90, "DATE": 85, "AMOUNT_EXACT": 80,
    "COUNTERPARTY": 75, "CLIENT": 75, "INTERNAL_SYSTEM": 75, "LEGAL_ENTITY": 60, "PERSON": 55, "LOCATION": 50,
    "FREE_TEXT_QUOTE": 10,
}

# Capitalised bigrams that are not names (very small built-in allowlist; seller extends via gazetteer allowlist.txt)
_BUILTIN_ALLOW = {
    "kind regards", "best regards", "many thanks", "thank you", "good morning", "good afternoon", "trade support",
    "middle office", "back office", "front office", "risk management", "please confirm", "please note",
    "please advise", "settlement date", "trade date", "value date", "net settlement", "gross settlement",
    "operations team", "reference data", "settlement instructions", "confirmation status",
}


class RuleDetector:
    """Default rule/gazetteer detector. `redact_amounts=False` implements the §4 AMOUNT_EXACT
    policy (keep unless flagged); pass True (or a set of flagged amounts) to redact them."""

    def __init__(self, gazetteer: Optional[Gazetteer] = None, redact_amounts: bool | Iterable[str] = False,
                 person_heuristic: bool = True, org_heuristic: bool = True):
        self.gaz = gazetteer or Gazetteer()
        self.redact_amounts = redact_amounts
        self.person_heuristic = person_heuristic
        self.org_heuristic = org_heuristic
        self._gaz_patterns = self._compile_gazetteer()

    def _compile_gazetteer(self):
        pats = []
        for cls, coll in (("COUNTERPARTY", self.gaz.counterparties), ("CLIENT", self.gaz.clients),
                          ("INTERNAL_SYSTEM", self.gaz.internal_systems), ("PERSON", self.gaz.persons),
                          ("LOCATION", self.gaz.locations)):
            for term in sorted(coll, key=len, reverse=True):
                if term:
                    pats.append((cls, re.compile(r"(?<![\w-])" + re.escape(term) + r"(?![\w-])", re.IGNORECASE)))
        return pats

    def _allowed(self, s: str) -> bool:
        c = canonical_original(s)
        return c in _BUILTIN_ALLOW or self.gaz.allowed(s)

    def detect(self, text: str) -> list[Detection]:
        cands: list[Detection] = []

        def add(rx, cls, source="rule"):
            for m in rx.finditer(text):
                s, e = m.span()
                if e > s:
                    cands.append(Detection(s, e, cls, text[s:e], source))

        add(EMAIL_RE, "EMAIL")
        add(TRADE_RE, "TRADE_ID")
        add(ACCOUNT_RE, "ACCOUNT_ID")
        add(IBAN_RE, "ACCOUNT_ID")
        add(DATE_RE, "DATE")
        add(PHONE_RE, "PHONE")
        if self.redact_amounts:
            flagged = None if self.redact_amounts is True else {canonical_original(x) for x in self.redact_amounts}
            for m in AMOUNT_RE.finditer(text):
                if flagged is None or canonical_original(m.group(0)) in flagged:
                    cands.append(Detection(m.start(), m.end(), "AMOUNT_EXACT", m.group(0)))
        for cls, rx in self._gaz_patterns:
            add(rx, cls, "gazetteer")
        if self.org_heuristic:
            for m in LEGAL_SUFFIX_RE.finditer(text):
                cands.append(Detection(m.start(), m.end(), "LEGAL_ENTITY", m.group(0), "heuristic"))
        if self.person_heuristic:
            for m in CAP_MULTIWORD_RE.finditer(text):
                if not self._allowed(m.group(0)):
                    cands.append(Detection(m.start(), m.end(), "PERSON", m.group(0), "heuristic"))
        return resolve_overlaps(cands)


def resolve_overlaps(cands: list[Detection]) -> list[Detection]:
    """Greedy: sort by (priority desc, length desc, start asc); keep non-overlapping.
    Structured rules and seller-supplied gazetteer matches (ranked by class PRIORITY) outrank heuristics."""
    boost = {"gazetteer": 100, "rule": 100, "heuristic": 0}
    order = sorted(cands, key=lambda d: (-(PRIORITY.get(d.cls, 0) + boost.get(d.source, 100)), -(d.end - d.start), d.start))
    taken: list[Detection] = []
    for d in order:
        if all(d.end <= t.start or d.start >= t.end for t in taken):
            taken.append(d)
    return sorted(taken, key=lambda d: d.start)


class CompositeDetector:
    """Combine several detectors (e.g. RuleDetector + an ML NER); overlaps resolved by priority."""

    def __init__(self, *detectors: Detector):
        self.detectors = detectors

    def detect(self, text: str) -> list[Detection]:
        out: list[Detection] = []
        for d in self.detectors:
            out.extend(d.detect(text))
        return resolve_overlaps(out)


class StaticDetector:
    """Detector returning fixed spans — used by tests (e.g. T3 mislabelling) and manual overrides."""

    def __init__(self, detections: list[Detection]):
        self._d = detections

    def detect(self, text: str) -> list[Detection]:
        return resolve_overlaps(list(self._d))
