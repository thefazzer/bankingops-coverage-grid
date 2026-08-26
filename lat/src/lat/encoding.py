"""SPEC-02 §3 — domain separation tags, length-prefix encoding, canonical JSON, hashing.

Every `||` in the spec is encoded as `u32 BE len || bytes` (§3.2). Integers are u64 BE
(8 bytes) *and then* length-prefixed like every other field. Strings are UTF-8 after NFC
normalisation. doc_ids and other hashes are encoded as their lowercase hex string (UTF-8).
"""
from __future__ import annotations

import hashlib
import json
import struct
import unicodedata
from typing import Any

DS_COMMIT = b"LAT/commit/v1"
DS_KEEP = b"LAT/keep/v1"
DS_NODE = b"LAT/node/v1"
DS_HOLD = b"LAT/holdout/v1"
DS_MAN = b"LAT/manifest/v1"


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def utf8(s: str) -> bytes:
    return nfc(s).encode("utf-8")


def u64(n: int) -> bytes:
    if n < 0 or n >= 1 << 64:
        raise ValueError("u64 out of range")
    return struct.pack(">Q", n)


def lp(field: bytes | str | int) -> bytes:
    """Length-prefix a field: u32 BE length || bytes. ints -> u64 BE first, strings -> NFC UTF-8."""
    if isinstance(field, int) and not isinstance(field, bool):
        field = u64(field)
    elif isinstance(field, str):
        field = utf8(field)
    elif not isinstance(field, (bytes, bytearray)):
        raise TypeError(f"cannot length-prefix {type(field)}")
    if len(field) >= 1 << 32:
        raise ValueError("field too long for u32 length prefix")
    return struct.pack(">I", len(field)) + bytes(field)


def concat(*fields: bytes | str | int) -> bytes:
    return b"".join(lp(f) for f in fields)


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(obj: Any) -> bytes:
    """Deterministic JSON: sorted keys, no whitespace, non-ASCII preserved, NFC strings."""
    return json.dumps(_nfc_obj(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def _nfc_obj(o: Any) -> Any:
    if isinstance(o, str):
        return nfc(o)
    if isinstance(o, dict):
        return {nfc(str(k)): _nfc_obj(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_nfc_obj(v) for v in o]
    return o


def pretty_json(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
