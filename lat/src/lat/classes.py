"""SPEC-02 §4 — redaction classes, class predicates (examiner E3), DATE and AMOUNT policies,
canonicalisation of originals for pseudonym derivation."""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Callable, Optional

import regex as re

from .crypto import hmac_sha256
from .encoding import nfc, concat

CLASSES = (
    "PERSON", "COUNTERPARTY", "CLIENT", "LEGAL_ENTITY", "INTERNAL_SYSTEM", "ACCOUNT_ID", "TRADE_ID",
    "EMAIL", "PHONE", "DATE", "AMOUNT_EXACT", "LOCATION", "FREE_TEXT_QUOTE",
)
CLASS_SET = frozenset(CLASSES)

LINEAGE_CLASSES = ("SPAN_VERIFIED", "PSEUDONYMISED_TRACEABLE", "SYNTHETIC_UNPROVABLE")
DERIVATION_OPS = ("QUOTE", "PSEUDONYMISE", "PARAPHRASE", "SYNTHESISE")
OP_TO_LINEAGE = {
    "QUOTE": "SPAN_VERIFIED",
    "PSEUDONYMISE": "PSEUDONYMISED_TRACEABLE",
    "PARAPHRASE": "SYNTHETIC_UNPROVABLE",
    "SYNTHESISE": "SYNTHETIC_UNPROVABLE",
}

TOKEN_OPEN = "⟦"   # ⟦
TOKEN_CLOSE = "⟧"  # ⟧
TOKEN_RE = re.compile(r"⟦([A-Z_]+):([^⟦⟧]*)⟧")

# --------------------------------------------------------------------------- regexes shared by
# detector (§4), predicates (E3) and residual scan (§7 R2)
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"(?<![\w/])(?:\+\d{1,3}[ -]?)?(?:\(?\d{2,4}\)?[ -]?)\d{3,4}[ -]?\d{3,4}(?![\w/])")
IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}(?: ?[A-Z0-9]{1,4})?\b")
LEI_RE = re.compile(r"\b(?:LEI[ :#-]*)?([A-Z0-9]{18}\d{2})\b")
ISIN_RE = re.compile(r"\b[A-Z]{2}[A-Z0-9]{9}\d\b")
ACCOUNT_RE = re.compile(r"\b(?:ACC|ACCT|CUST|LOAN|SSI)-\d{4,12}\b|\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}(?: ?[A-Z0-9]{1,4})?\b")
TRADE_RE = re.compile(r"\b(?:TRD|TKT|CONF|SET|ORD|MSG)-\d{4}-\d{4,8}\b")
MONTHS = "Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
DATE_RE = re.compile(
    r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|\d{1,2}\.\d{1,2}\.\d{4}"
    r"|\d{1,2}(?:st|nd|rd|th)? (?:" + MONTHS + r")\.? \d{4}|(?:" + MONTHS + r")\.? \d{1,2}(?:st|nd|rd|th)?,? \d{4})\b"
)
AMOUNT_RE = re.compile(
    r"(?:(?:USD|EUR|GBP|CHF|JPY|SEK|NOK|DKK|PLN|[$€£])\s?\d{1,3}(?:[,\d]{0,15})(?:\.\d{1,2})?(?:\s?(?:mm|m|bn|k|MM|M|BN|K))?)"
    r"|(?:\d{1,3}(?:[,\d]{0,15})(?:\.\d{1,2})?\s?(?:mm|m|bn|k|MM|M|BN|K)?\s?(?:USD|EUR|GBP|CHF|JPY|SEK|NOK|DKK|PLN))"
)
LEGAL_SUFFIX_RE = re.compile(
    r"\b(?:[A-Z][\w&'.-]*\s){0,3}[A-Z][\w&'.-]*\s(?:Ltd\.?|Limited|GmbH|AG|S\.A\.|SA|SpA|LLC|LLP|Inc\.?|plc|PLC|B\.V\.|BV|NV|N\.V\.|SE|Holdings|Partners|Bancorp|Trust)\b"
)
CAP_MULTIWORD_RE = re.compile(r"\b[A-Z][a-z]+(?:[-'][A-Z][a-z]+)?(?:\s[A-Z][a-z]+(?:[-'][A-Z][a-z]+)?){1,2}\b")

_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d.%m.%Y", "%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y",
                 "%B %d, %Y", "%b %d, %Y", "%d %b. %Y")


def parse_date(s: str) -> Optional[_dt.date]:
    t = re.sub(r"(\d)(?:st|nd|rd|th)\b", r"\1", s.strip())
    t = t.replace("Sept ", "Sep ")
    for fmt in _DATE_FORMATS:
        try:
            return _dt.datetime.strptime(t, fmt).date()
        except ValueError:
            continue
    return None


def canonical_original(s: str) -> str:
    """canonical(original): NFC, casefold, whitespace collapsed, edge punctuation stripped."""
    t = nfc(s).casefold()
    t = re.sub(r"\s+", " ", t).strip()
    t = t.strip(" .,;:'\"()[]{}<>")
    return t


# --------------------------------------------------------------------------- DATE policy

DATE_POLICIES = ("shift_per_doc_v1", "bucket_month_v1")


def date_shift_days(k_pseud: bytes, doc_id: str) -> int:
    """Deterministic per-doc shift in [-182, +182] \\ {0}, derived from K_pseud (never shipped)."""
    mac = hmac_sha256(k_pseud, concat("date-shift", doc_id))
    n = int.from_bytes(mac[:4], "big") % 364  # 0..363
    shift = n - 182
    return shift if shift < 0 else shift + 1


def date_token_value(original: str, policy: str, shift_days: int) -> Optional[str]:
    d = parse_date(original)
    if d is None:
        return None
    if policy == "shift_per_doc_v1":
        return (d + _dt.timedelta(days=shift_days)).isoformat()
    if policy == "bucket_month_v1":
        return d.strftime("%Y-%m")
    raise ValueError(f"unknown date policy {policy}")


# --------------------------------------------------------------------------- AMOUNT policy

AMOUNT_BANDS = [(1_000, "<1k"), (10_000, "1k-10k"), (100_000, "10k-100k"), (1_000_000, "100k-1m"),
                (10_000_000, "1m-10m"), (100_000_000, "10m-100m"), (float("inf"), ">100m")]


def parse_amount(s: str) -> Optional[float]:
    m = re.search(r"\d[\d,]*(?:\.\d+)?", s)
    if not m:
        return None
    v = float(m.group(0).replace(",", ""))
    tail = s[m.end():].strip().lower()
    if tail.startswith("bn"):
        v *= 1e9
    elif tail.startswith("mm") or tail.startswith("m"):
        v *= 1e6
    elif tail.startswith("k"):
        v *= 1e3
    return v


def amount_band(original: str) -> str:
    v = parse_amount(original)
    if v is None:
        return "unparsed"
    for limit, label in AMOUNT_BANDS:
        if v < limit:
            return label
    return ">100m"


# --------------------------------------------------------------------------- Gazetteer

@dataclass
class Gazetteer:
    counterparties: set[str] = field(default_factory=set)
    clients: set[str] = field(default_factory=set)
    internal_systems: set[str] = field(default_factory=set)
    locations: set[str] = field(default_factory=set)
    persons: set[str] = field(default_factory=set)
    allowlist: set[str] = field(default_factory=set)   # generic terms allowed in kept text (R1)
    products: set[str] = field(default_factory=set)    # for R3 quasi-identifier tuples
    venues: set[str] = field(default_factory=set)      # for R3

    FILES = {
        "counterparties": "counterparties.txt", "clients": "clients.txt", "internal_systems": "internal_systems.txt",
        "locations": "locations.txt", "persons": "persons.txt", "allowlist": "allowlist.txt",
        "products": "products.txt", "venues": "venues.txt",
    }

    @classmethod
    def load(cls, directory) -> "Gazetteer":
        from pathlib import Path
        g = cls()
        d = Path(directory)
        for attr, fname in cls.FILES.items():
            p = d / fname
            if p.exists():
                vals = {ln.strip() for ln in p.read_text(encoding="utf-8").splitlines()
                        if ln.strip() and not ln.startswith("#")}
                setattr(g, attr, vals)
        return g

    def save(self, directory) -> None:
        from pathlib import Path
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        for attr, fname in self.FILES.items():
            (d / fname).write_text("\n".join(sorted(getattr(self, attr))) + "\n", encoding="utf-8")

    def _has(self, coll: set[str], s: str) -> bool:
        c = canonical_original(s)
        return any(canonical_original(x) == c for x in coll)

    def class_of(self, s: str) -> Optional[str]:
        if self._has(self.counterparties, s):
            return "COUNTERPARTY"
        if self._has(self.clients, s):
            return "CLIENT"
        if self._has(self.internal_systems, s):
            return "INTERNAL_SYSTEM"
        if self._has(self.persons, s):
            return "PERSON"
        if self._has(self.locations, s):
            return "LOCATION"
        return None

    def allowed(self, s: str) -> bool:
        return self._has(self.allowlist, s)


# --------------------------------------------------------------------------- Class predicates (E3)

def _full(rx, s: str) -> bool:
    return rx.fullmatch(s.strip()) is not None


def class_predicate(cls: str, original: str, gaz: Optional[Gazetteer] = None) -> bool:
    """Does `original` satisfy the class predicate? Used by examiner E3 (CLASS_OK / CLASS_VIOLATION)."""
    s = original.strip()
    if not s:
        return False
    gaz = gaz or Gazetteer()
    if cls == "EMAIL":
        return _full(EMAIL_RE, s)
    if cls == "PHONE":
        return _full(PHONE_RE, s)
    if cls == "DATE":
        return _full(DATE_RE, s) and parse_date(s) is not None
    if cls == "ACCOUNT_ID":
        return _full(ACCOUNT_RE, s) or _full(IBAN_RE, s)
    if cls == "TRADE_ID":
        return _full(TRADE_RE, s)
    if cls == "AMOUNT_EXACT":
        return _full(AMOUNT_RE, s) and parse_amount(s) is not None
    if cls == "LEGAL_ENTITY":
        return _full(LEGAL_SUFFIX_RE, s) or _full(LEI_RE, s)
    if cls == "PERSON":
        return gaz._has(gaz.persons, s) or (_full(CAP_MULTIWORD_RE, s) and len(s.split()) <= 3)
    if cls == "COUNTERPARTY":
        return gaz._has(gaz.counterparties, s) if gaz.counterparties else _full(LEGAL_SUFFIX_RE, s) or _full(CAP_MULTIWORD_RE, s)
    if cls == "CLIENT":
        return gaz._has(gaz.clients, s) if gaz.clients else _full(LEGAL_SUFFIX_RE, s) or _full(CAP_MULTIWORD_RE, s)
    if cls == "INTERNAL_SYSTEM":
        return gaz._has(gaz.internal_systems, s) if gaz.internal_systems else bool(re.fullmatch(r"[A-Z][A-Z0-9-]{2,}", s))
    if cls == "LOCATION":
        return gaz._has(gaz.locations, s) or _full(CAP_MULTIWORD_RE, s) or bool(re.fullmatch(r"[A-Z][a-z]+", s))
    if cls == "FREE_TEXT_QUOTE":
        # only class allowed to hold substantive text; must be an explicit quotation
        return len(s) >= 2 and s[0] in "\"'“‘«" and s[-1] in "\"'”’»"
    return False


ClassPredicate = Callable[[str, str, Optional[Gazetteer]], bool]
