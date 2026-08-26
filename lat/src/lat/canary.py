"""SPEC-02 §2 Canary / C6 / T5 — per-recipient salted canaries.

Carrier methods:
  ZW_SEQ        : invisible zero-width sequence inserted at a word boundary of an atom's content.
  PSEUD_SUFFIX  : invisible sequence appended inside a pseudonym token, right before ⟧
                  (the "invisible pseudonym-suffix variant"; uses a distinct start marker).
Each carrier encodes the full 32-bit canary tag = HMAC(salt, package_id || recipient_id)[:4]
as 16 base-4 symbols over four zero-width code points. Detection needs >= 3 agreeing carriers
(MIN_CARRIERS) and maps tag -> registry entry -> recipient_id.

All carriers live in the invisible code-point set `INVISIBLE`; `strip_carriers()` removes them
and is applied by every verifier before substring/sha checks, so canaries never break lineage.

Registry: append-only JSONL hash chain (each line {entry, prev_hash, sig}), Ed25519-signed.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

import regex as re

from .crypto import SigningKey, VerifyKey, hmac_sha256
from .encoding import canonical_json, concat, sha256_hex
from .classes import TOKEN_RE

ALPHABET = "\u200b\u200c\u200d\u2060"        # ZWSP, ZWNJ, ZWJ, WJ: 2 bits per symbol
ZW_START, PSEUD_START, END = "\u2062", "\u2064", "\u2063"  # invisible times / plus / separator
INVISIBLE = frozenset(ALPHABET + ZW_START + PSEUD_START + END + "\ufeff\u2061")
_STRIP_RE = re.compile("[" + "".join(sorted(INVISIBLE)) + "]")
_CARRIER_RE = re.compile(f"([{ZW_START}{PSEUD_START}])([{ALPHABET}]{{16}}){END}")
MIN_CARRIERS = 3
METHODS = ("ZW_SEQ", "PSEUD_SUFFIX")


def strip_carriers(s: str) -> str:
    return _STRIP_RE.sub("", s)


def has_carriers(s: str) -> bool:
    return _STRIP_RE.search(s) is not None


def canary_tag(salt: bytes, package_id: str, recipient_id: str) -> bytes:
    return hmac_sha256(salt, concat(package_id, recipient_id))[:4]


def encode_tag(tag: bytes) -> str:
    n = int.from_bytes(tag, "big")
    return "".join(ALPHABET[(n >> (2 * (15 - i))) & 3] for i in range(16))


def decode_tag(sym: str) -> bytes:
    n = 0
    for ch in sym:
        n = (n << 2) | ALPHABET.index(ch)
    return n.to_bytes(4, "big")


@dataclass
class Canary:
    package_id: str
    recipient_id: str
    salt: bytes
    positions: list[tuple[str, str]] = field(default_factory=list)   # (atom_id, method)
    created_utc: str = ""

    @property
    def tag(self) -> bytes:
        return canary_tag(self.salt, self.package_id, self.recipient_id)

    def to_dict(self) -> dict:
        return {"package_id": self.package_id, "recipient_id": self.recipient_id, "salt": self.salt.hex(),
                "tag": self.tag.hex(), "positions": [list(p) for p in self.positions], "created_utc": self.created_utc,
                "methods": list(METHODS), "min_carriers": MIN_CARRIERS}

    @classmethod
    def from_dict(cls, d: dict) -> "Canary":
        return cls(d["package_id"], d["recipient_id"], bytes.fromhex(d["salt"]),
                   [tuple(p) for p in d.get("positions", [])], d.get("created_utc", ""))


# --------------------------------------------------------------------------- apply

def plan_positions(canary: Canary, atoms: list[dict]) -> list[tuple[str, str]]:
    """Every atom carries a canary: PSEUD_SUFFIX where the atom contains a token, ZW_SEQ otherwise
    (atoms with tokens also get ZW_SEQ so that stripping tokens alone does not defeat detection)."""
    pos = []
    for a in atoms:
        if TOKEN_RE.search(a["content"]):
            pos.append((a["atom_id"], "PSEUD_SUFFIX"))
        pos.append((a["atom_id"], "ZW_SEQ"))
    return pos


def _insert_zw(content: str, carrier: str, salt: bytes, atom_id: str) -> str:
    # deterministic word-boundary position derived from salt+atom_id
    spaces = [m.start() for m in re.finditer(r" ", content)]
    if not spaces:
        return content + carrier
    h = int.from_bytes(hmac_sha256(salt, atom_id.encode())[:4], "big")
    p = spaces[h % len(spaces)]
    return content[:p] + carrier + content[p:]


def apply_canary_to_content(content: str, method: str, canary: Canary, atom_id: str) -> str:
    sym = encode_tag(canary.tag)
    if method == "ZW_SEQ":
        return _insert_zw(content, ZW_START + sym + END, canary.salt, atom_id)
    if method == "PSEUD_SUFFIX":
        m = TOKEN_RE.search(content)
        if not m:
            return content
        i = m.end() - 1  # position of ⟧
        return content[:i] + PSEUD_START + sym + END + content[i:]
    raise ValueError(method)


def apply_canary(atoms: list[dict], canary: Canary) -> list[dict]:
    """Return new atom dicts with carriers inserted per canary.positions."""
    by_id = {a["atom_id"]: dict(a) for a in atoms}
    for atom_id, method in canary.positions:
        if atom_id in by_id:
            by_id[atom_id]["content"] = apply_canary_to_content(by_id[atom_id]["content"], method, canary, atom_id)
    return [by_id[a["atom_id"]] for a in atoms]


# --------------------------------------------------------------------------- detect

@dataclass
class DetectResult:
    carriers_found: int
    tags: dict            # tag_hex -> count
    tag: Optional[str]    # winning tag (>= MIN_CARRIERS) or None
    recipient_id: Optional[str] = None
    package_id: Optional[str] = None
    methods: dict = field(default_factory=dict)

    @property
    def detected(self) -> bool:
        return self.tag is not None

    def to_dict(self):
        return {"carriers_found": self.carriers_found, "tags": self.tags, "tag": self.tag, "detected": self.detected,
                "recipient_id": self.recipient_id, "package_id": self.package_id, "methods": self.methods}


def extract_carriers(text: str) -> list[tuple[str, str]]:
    out = []
    for m in _CARRIER_RE.finditer(text):
        method = "ZW_SEQ" if m.group(1) == ZW_START else "PSEUD_SUFFIX"
        out.append((decode_tag(m.group(2)).hex(), method))
    return out


def detect(text: str, registry: Optional["Registry"] = None, min_carriers: int = MIN_CARRIERS) -> DetectResult:
    carriers = extract_carriers(text)
    counts = Counter(t for t, _ in carriers)
    methods = Counter(m for _, m in carriers)
    tag = None
    if counts:
        best, n = counts.most_common(1)[0]
        if n >= min_carriers:
            tag = best
    res = DetectResult(len(carriers), dict(counts), tag, methods=dict(methods))
    if tag and registry is not None:
        e = registry.find_by_tag(tag)
        if e:
            res.recipient_id = e.recipient_id
            res.package_id = e.package_id
    return res


def detect_path(path: str | Path, registry: Optional["Registry"] = None) -> DetectResult:
    p = Path(path)
    files = sorted(x for x in p.rglob("*") if x.is_file()) if p.is_dir() else [p]
    text = "".join(f.read_text(encoding="utf-8", errors="ignore") for f in files)
    # also recover carriers that were JSON-escaped (​ ...) by a re-serialising tool
    if "\\u2" in text or "\\ufeff" in text:
        text = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), text)
    return detect(text, registry)


# --------------------------------------------------------------------------- registry

class Registry:
    """Append-only, hash-chained, Ed25519-signed canary registry (JSONL)."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def lines(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()]

    @staticmethod
    def line_hash(line: dict) -> str:
        return sha256_hex(canonical_json(line))

    @staticmethod
    def signed_bytes(entry: dict, prev_hash: str) -> bytes:
        return canonical_json({"entry": entry, "prev_hash": prev_hash})

    def append(self, canary: Canary, key: SigningKey) -> dict:
        lines = self.lines()
        for l in lines:
            if l["entry"]["package_id"] == canary.package_id and l["entry"]["recipient_id"] == canary.recipient_id:
                raise ValueError("canary already registered for this package/recipient")
            if l["entry"]["tag"] == canary.tag.hex():
                raise ValueError("tag collision; re-salt")
        prev_hash = self.line_hash(lines[-1]) if lines else "0" * 64
        entry = canary.to_dict()
        line = {"entry": entry, "prev_hash": prev_hash, "sig": key.sign_b64(self.signed_bytes(entry, prev_hash))}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, sort_keys=True, ensure_ascii=False) + "\n")
        return line

    def verify_chain(self, pub: VerifyKey) -> tuple[bool, list[str]]:
        problems = []
        prev = "0" * 64
        for i, l in enumerate(self.lines()):
            if l.get("prev_hash") != prev:
                problems.append(f"line {i}: broken hash chain")
            if not pub.verify_b64(self.signed_bytes(l["entry"], l["prev_hash"]), l.get("sig", "")):
                problems.append(f"line {i}: bad signature")
            prev = self.line_hash(l)
        return not problems, problems

    def find(self, package_id: str, recipient_id: str) -> Optional[dict]:
        for l in self.lines():
            if l["entry"]["package_id"] == package_id and l["entry"]["recipient_id"] == recipient_id:
                return l
        return None

    def find_by_tag(self, tag_hex: str) -> Optional[Canary]:
        for l in self.lines():
            if l["entry"]["tag"] == tag_hex:
                return Canary.from_dict(l["entry"])
        return None


def verify_registry_line(line: dict, pub: VerifyKey) -> bool:
    try:
        return pub.verify_b64(Registry.signed_bytes(line["entry"], line["prev_hash"]), line["sig"])
    except Exception:
        return False


def new_canary(package_id: str, recipient_id: str, atoms: list[dict], created_utc: str) -> Canary:
    c = Canary(package_id, recipient_id, os.urandom(16), [], created_utc)
    c.positions = plan_positions(c, atoms)
    return c
