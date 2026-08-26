"""SPEC-02 §2 Manifest / §3.6 anchoring — build, verify, supersets/subsets with diff log,
OpenTimestamps STUB anchor (interface only; no network)."""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Optional, Protocol

from .crypto import manifest_merkle_root
from .encoding import canonical_json, pretty_json, sha256_hex
from .models import SourceDoc

ANCHOR_FILE = "anchor_proof.ots"


def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def manifest_sha(manifest: dict) -> str:
    return sha256_hex(canonical_json(manifest))


def build_manifest(doc_ids: list[str], prev: Optional[dict] = None, allow_subset: bool = False,
                   created_utc: Optional[str] = None) -> dict:
    """New manifest; if `prev` given it must be a superset, or an explicit subset (allow_subset) with diff log."""
    docs = sorted(set(doc_ids))
    m = {"version": 1, "created_utc": created_utc or utc_now(), "docs": docs,
         "merkle_root": manifest_merkle_root(docs).hex(), "anchor": None}
    if prev is not None:
        prev_docs = set(prev.get("docs", []))
        added = sorted(set(docs) - prev_docs)
        removed = sorted(prev_docs - set(docs))
        if removed and not allow_subset:
            raise ValueError(f"new manifest drops {len(removed)} doc(s) from v{prev.get('version')}; "
                             "pass allow_subset to record an explicit subset with diff log")
        m["version"] = int(prev.get("version", 0)) + 1
        m["prev_sha"] = manifest_sha(prev)
        m["diff_log"] = {"prev_version": prev.get("version"), "added": added, "removed": removed,
                         "kind": "subset" if removed else "superset"}
    return m


def import_v0(hashes: list[str], created_utc: Optional[str] = None, anchor: Optional[dict] = None) -> dict:
    """Import an existing (e.g. BTC-anchored) hash set as manifest v0."""
    docs = sorted(set(h.lower() for h in hashes))
    return {"version": 0, "created_utc": created_utc or utc_now(), "docs": docs,
            "merkle_root": manifest_merkle_root(docs).hex(), "anchor": anchor}


def write_manifest(m: dict, directory: str | Path) -> tuple[Path, Path]:
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    mp = d / "manifest.json"
    sp = d / "manifest.sha"
    mp.write_text(pretty_json(m), encoding="utf-8")
    sp.write_text(manifest_sha(m) + "\n", encoding="utf-8")
    return mp, sp


def load_manifest(directory: str | Path) -> tuple[dict, Optional[str]]:
    d = Path(directory)
    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    sp = d / "manifest.sha"
    return m, (sp.read_text().strip() if sp.exists() else None)


def verify_manifest(m: dict, sha: Optional[str], anchor_proof: Optional[dict] = None) -> dict:
    """V1: sha recompute, merkle root recompute, docs sorted+unique, anchor proof (stub) if present."""
    problems = []
    if sha is None:
        problems.append("manifest.sha missing")
    elif manifest_sha(m) != sha:
        problems.append("manifest.sha mismatch")
    docs = m.get("docs", [])
    if docs != sorted(set(docs)):
        problems.append("docs not sorted/unique")
    if manifest_merkle_root(docs).hex() != m.get("merkle_root"):
        problems.append("merkle_root mismatch")
    anchor_status = "none"
    if anchor_proof is not None:
        ok, info = get_anchor_provider(anchor_proof.get("provider", "")).verify(bytes.fromhex(m["merkle_root"]),
                                                                                anchor_proof)
        anchor_status = info
        if not ok:
            problems.append(f"anchor proof invalid: {info}")
    return {"ok": not problems, "problems": problems, "n_docs": len(docs), "anchor": anchor_status,
            "sha": manifest_sha(m)}


# --------------------------------------------------------------------------- anchoring (stub)

class AnchorProvider(Protocol):
    name: str

    def stamp(self, digest: bytes) -> dict: ...

    def verify(self, digest: bytes, proof: dict) -> tuple[bool, str]: ...


class OpenTimestampsStub:
    """Interface-only OpenTimestamps provider. Produces a proof *record* that binds the digest and a
    local timestamp, but performs NO calendar submission and NO Bitcoin verification. Verification
    reports STUB status explicitly so no verifier can mistake it for a real anchor."""
    name = "opentimestamps-stub"

    def stamp(self, digest: bytes) -> dict:
        return {"provider": self.name, "digest": digest.hex(), "stamped_utc": utc_now(),
                "status": "PENDING_STUB", "calendar": None, "bitcoin": None,
                "note": "stub: not submitted to any calendar server; no network access in LAT v0.1"}

    def verify(self, digest: bytes, proof: dict) -> tuple[bool, str]:
        if proof.get("provider") != self.name:
            return False, f"unexpected provider {proof.get('provider')}"
        if proof.get("digest") != digest.hex():
            return False, "proof digest does not match manifest merkle_root"
        return True, "STUB: digest bound in local proof record; NOT network/blockchain verified"


_PROVIDERS = {OpenTimestampsStub.name: OpenTimestampsStub()}


def get_anchor_provider(name: str) -> AnchorProvider:
    if name not in _PROVIDERS:
        raise ValueError(f"unknown anchor provider {name!r}; available: {sorted(_PROVIDERS)}")
    return _PROVIDERS[name]


def write_anchor(m: dict, directory: str | Path, provider: str = OpenTimestampsStub.name) -> Path:
    proof = get_anchor_provider(provider).stamp(bytes.fromhex(m["merkle_root"]))
    p = Path(directory) / ANCHOR_FILE
    p.write_text(pretty_json(proof), encoding="utf-8")
    return p


def load_anchor(directory: str | Path) -> Optional[dict]:
    p = Path(directory) / ANCHOR_FILE
    if not p.exists():
        return None
    txt = p.read_text(encoding="utf-8").strip()
    if txt in ("", "null"):
        return None
    return json.loads(txt)
