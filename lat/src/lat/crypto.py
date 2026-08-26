"""SPEC-02 §2/§3 — commitments, keep leaves, Merkle roots, holdout commits, pseudonym HMAC,
Ed25519 signing and AES-GCM at-rest encryption."""
from __future__ import annotations

import base64
import hmac
import os
import hashlib
from pathlib import Path
from typing import Iterable, Sequence

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidSignature, InvalidTag

from .encoding import DS_COMMIT, DS_HOLD, DS_KEEP, DS_MAN, DS_NODE, canonical_json, concat, sha256

NONCE_LEN = 32


# ---------------------------------------------------------------------------
# Commitments / leaves / Merkle (§2, §3.1, §3.2)
# ---------------------------------------------------------------------------

def new_nonce() -> bytes:
    return os.urandom(NONCE_LEN)


def commitment(doc_id: str, idx: int, start: int, end: int, cls: str, original: bytes, nonce: bytes) -> bytes:
    """commit = H(DS_COMMIT || doc_id || idx || start || end || class || original_bytes || nonce)."""
    if len(nonce) != NONCE_LEN:
        raise ValueError("nonce must be 32 bytes")
    return sha256(concat(DS_COMMIT, doc_id, idx, start, end, cls, original, nonce))


def keep_leaf(doc_id: str, idx: int, start: int, end: int, data: bytes) -> bytes:
    """leaf = H(DS_KEEP || doc_id || idx || start || end || bytes)."""
    return sha256(concat(DS_KEEP, doc_id, idx, start, end, data))


def merkle_node(left: bytes, right: bytes) -> bytes:
    return sha256(concat(DS_NODE, left, right))


def merkle_root(leaves: Sequence[bytes]) -> bytes:
    """Binary Merkle tree with DS_NODE; odd level -> duplicate last. Single leaf -> the leaf itself.
    Empty -> H(DS_NODE || "" || "")."""
    if not leaves:
        return merkle_node(b"", b"")
    level = list(leaves)
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        level = [merkle_node(level[i], level[i + 1]) for i in range(0, len(level), 2)]
    return level[0]


def manifest_leaf(doc_id: str) -> bytes:
    return sha256(concat(DS_MAN, doc_id))


def manifest_merkle_root(doc_ids: Iterable[str]) -> bytes:
    return merkle_root([manifest_leaf(d) for d in sorted(doc_ids)])


def holdout_commit(items_and_answers, nonce_h: bytes) -> bytes:
    """items_commit = H(DS_HOLD || canonical_json(items+answers) || nonce_h)."""
    return sha256(concat(DS_HOLD, canonical_json(items_and_answers), nonce_h))


# ---------------------------------------------------------------------------
# Pseudonyms (§2 Replacement)
# ---------------------------------------------------------------------------

def hmac_sha256(key: bytes, data: bytes) -> bytes:
    return hmac.new(key, data, hashlib.sha256).digest()


def pseudonym_id(k_pseud: bytes, cls: str, canonical_original: str) -> str:
    """pseudonym_id = base32(HMAC(K_pseud, class || canonical(original)))[:10]"""
    mac = hmac_sha256(k_pseud, concat(cls, canonical_original))
    return base64.b32encode(mac).decode("ascii")[:10]


# ---------------------------------------------------------------------------
# Ed25519 (§3.5)
# ---------------------------------------------------------------------------

class SigningKey:
    def __init__(self, private: Ed25519PrivateKey):
        self._priv = private

    @classmethod
    def generate(cls) -> "SigningKey":
        return cls(Ed25519PrivateKey.generate())

    @classmethod
    def from_seed(cls, seed: bytes) -> "SigningKey":
        return cls(Ed25519PrivateKey.from_private_bytes(seed))

    @classmethod
    def load(cls, path: str | Path) -> "SigningKey":
        raw = Path(path).read_bytes().strip()
        seed = base64.b64decode(raw) if len(raw) != 32 else raw
        return cls.from_seed(seed)

    def seed(self) -> bytes:
        return self._priv.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                        serialization.NoEncryption())

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(base64.b64encode(self.seed()) + b"\n")

    def public(self) -> "VerifyKey":
        return VerifyKey(self._priv.public_key())

    def sign(self, data: bytes) -> bytes:
        return self._priv.sign(data)

    def sign_b64(self, data: bytes) -> str:
        return base64.b64encode(self.sign(data)).decode("ascii")

    def sign_file(self, path: str | Path) -> Path:
        p = Path(path)
        sig_path = p.with_name(p.name + ".sig")
        sig_path.write_text(self.sign_b64(p.read_bytes()) + "\n")
        return sig_path


class VerifyKey:
    def __init__(self, public: Ed25519PublicKey):
        self._pub = public

    @classmethod
    def from_bytes(cls, raw: bytes) -> "VerifyKey":
        return cls(Ed25519PublicKey.from_public_bytes(raw))

    @classmethod
    def from_b64(cls, b64: str) -> "VerifyKey":
        return cls.from_bytes(base64.b64decode(b64.strip()))

    @classmethod
    def load(cls, path: str | Path) -> "VerifyKey":
        return cls.from_b64(Path(path).read_text())

    def raw(self) -> bytes:
        return self._pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)

    def b64(self) -> str:
        return base64.b64encode(self.raw()).decode("ascii")

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.b64() + "\n")

    def verify(self, data: bytes, sig: bytes) -> bool:
        try:
            self._pub.verify(sig, data)
            return True
        except InvalidSignature:
            return False

    def verify_b64(self, data: bytes, sig_b64: str) -> bool:
        try:
            return self.verify(data, base64.b64decode(sig_b64.strip()))
        except Exception:
            return False

    def verify_file(self, path: str | Path, sig_path: str | Path | None = None) -> bool:
        p = Path(path)
        sp = Path(sig_path) if sig_path else p.with_name(p.name + ".sig")
        if not p.exists() or not sp.exists():
            return False
        return self.verify_b64(p.read_bytes(), sp.read_text())


# ---------------------------------------------------------------------------
# AES-GCM at-rest encryption for the vault (§2 NonceVault)
# ---------------------------------------------------------------------------

VAULT_MAGIC = b"LATV1"


def aead_encrypt(key: bytes, plaintext: bytes, aad: bytes = b"") -> bytes:
    if len(key) != 32:
        raise ValueError("vault key must be 32 bytes")
    iv = os.urandom(12)
    return VAULT_MAGIC + iv + AESGCM(key).encrypt(iv, plaintext, aad)


def aead_decrypt(key: bytes, blob: bytes, aad: bytes = b"") -> bytes:
    if not blob.startswith(VAULT_MAGIC):
        raise ValueError("not a LAT vault blob")
    iv = blob[len(VAULT_MAGIC):len(VAULT_MAGIC) + 12]
    ct = blob[len(VAULT_MAGIC) + 12:]
    try:
        return AESGCM(key).decrypt(iv, ct, aad)
    except InvalidTag as e:
        raise ValueError("vault decryption failed (wrong key or tampered blob)") from e
