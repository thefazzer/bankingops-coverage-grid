"""SPEC-02 §2 NonceVault — { doc_id -> [{idx, nonce, original_bytes, class}], K_pseud, seller signing key }.
Encrypted at rest with AES-GCM (one blob per file, AAD = file name). Examiner-only; never shipped.

Key resolution (`resolve_vault_key`): explicit key file > env LAT_VAULT_KEY (hex/base64) >
env LAT_VAULT_KEY_FILE > <workspace>/vault.key.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Optional

from .crypto import SigningKey, aead_decrypt, aead_encrypt
from .models import Origin, VaultEntry

KEYS_FILE = "keys.json.enc"
DOC_SUFFIX = ".json.enc"


def parse_key_material(s: str | bytes) -> bytes:
    if isinstance(s, bytes):
        s = s.decode("ascii")
    s = s.strip()
    try:
        b = bytes.fromhex(s)
        if len(b) == 32:
            return b
    except ValueError:
        pass
    b = base64.b64decode(s)
    if len(b) != 32:
        raise ValueError("vault key must decode to 32 bytes")
    return b


def resolve_vault_key(key_file: Optional[str | Path] = None, workspace: Optional[str | Path] = None,
                      create: bool = False) -> bytes:
    if key_file:
        p = Path(key_file)
        if p.exists():
            return parse_key_material(p.read_text())
        if create:
            k = os.urandom(32)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(k.hex() + "\n")
            os.chmod(p, 0o600)
            return k
        raise FileNotFoundError(f"vault key file {p} not found")
    if os.environ.get("LAT_VAULT_KEY"):
        return parse_key_material(os.environ["LAT_VAULT_KEY"])
    if os.environ.get("LAT_VAULT_KEY_FILE"):
        return resolve_vault_key(os.environ["LAT_VAULT_KEY_FILE"], create=create)
    if workspace:
        return resolve_vault_key(Path(workspace) / "vault.key", create=create)
    raise RuntimeError("no vault key: set LAT_VAULT_KEY, LAT_VAULT_KEY_FILE or pass --vault-key-file")


class NonceVault:
    def __init__(self, path: str | Path, key: bytes):
        self.path = Path(path)
        self.key = key
        self._keys: Optional[dict] = None

    # ---- raw encrypted file IO -------------------------------------------------------------
    def _write(self, name: str, obj) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        blob = aead_encrypt(self.key, json.dumps(obj, sort_keys=True).encode("utf-8"), aad=name.encode())
        (self.path / name).write_bytes(blob)

    def _read(self, name: str):
        p = self.path / name
        if not p.exists():
            return None
        return json.loads(aead_decrypt(self.key, p.read_bytes(), aad=name.encode()).decode("utf-8"))

    # ---- init / keys ------------------------------------------------------------------------
    @property
    def exists(self) -> bool:
        return (self.path / KEYS_FILE).exists()

    def init(self, force: bool = False) -> None:
        if self.exists and not force:
            return
        sk = SigningKey.generate()
        self._keys = {"k_pseud": os.urandom(32).hex(), "seller_seed": base64.b64encode(sk.seed()).decode()}
        self._write(KEYS_FILE, self._keys)
        (self.path / "seller.pub").write_text(sk.public().b64() + "\n")

    def _load_keys(self) -> dict:
        if self._keys is None:
            self._keys = self._read(KEYS_FILE)
            if self._keys is None:
                raise RuntimeError(f"vault at {self.path} not initialised (run `lat vault init`)")
        return self._keys

    @property
    def k_pseud(self) -> bytes:
        return bytes.fromhex(self._load_keys()["k_pseud"])

    @property
    def signing_key(self) -> SigningKey:
        return SigningKey.from_seed(base64.b64decode(self._load_keys()["seller_seed"]))

    # ---- per-doc entries --------------------------------------------------------------------
    def doc_ids(self) -> list[str]:
        return sorted(p.name[:-len(DOC_SUFFIX)] for p in self.path.glob("*" + DOC_SUFFIX)
                      if p.name != KEYS_FILE and not p.name.startswith("holdout_"))

    def load_doc(self, doc_id: str) -> Optional[dict]:
        """Returns {doc_id, origin, mode, date_policy, date_shift_days, entries:[VaultEntry]} or None."""
        raw = self._read(doc_id + DOC_SUFFIX)
        if raw is None:
            return None
        raw["entries"] = [VaultEntry(e["idx"], e["start"], e["end"], e["class"], base64.b64decode(e["original"]),
                                     bytes.fromhex(e["nonce"]), e["token"]) for e in raw["entries"]]
        raw["origin"] = Origin.from_dict(raw.get("origin"))
        return raw

    def save_doc(self, doc_id: str, entries: list[VaultEntry], origin: Origin, mode: str, date_policy: str,
                 date_shift_days: int, source_name: str = "") -> None:
        self._write(doc_id + DOC_SUFFIX, {
            "doc_id": doc_id, "origin": origin.to_dict(), "mode": mode, "date_policy": date_policy,
            "date_shift_days": date_shift_days, "source_name": source_name,
            "entries": [{"idx": e.idx, "start": e.start, "end": e.end, "class": e.cls,
                         "original": base64.b64encode(e.original).decode(), "nonce": e.nonce.hex(), "token": e.token}
                        for e in entries],
        })

    def existing_nonces(self, doc_id: str) -> dict[tuple, bytes]:
        """(idx,start,end,class,original) -> nonce, for deterministic re-runs (G8)."""
        d = self.load_doc(doc_id)
        if not d:
            return {}
        return {(e.idx, e.start, e.end, e.cls, e.original): e.nonce for e in d["entries"]}

    # ---- holdout secrets ---------------------------------------------------------------------
    def save_holdout(self, holdout_id: str, obj: dict) -> None:
        self._write(f"holdout_{holdout_id}.json.enc", obj)

    def load_holdout(self, holdout_id: str) -> Optional[dict]:
        return self._read(f"holdout_{holdout_id}.json.enc")
