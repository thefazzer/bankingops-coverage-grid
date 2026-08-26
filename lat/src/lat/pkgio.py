"""Read model for a §9 package directory (and the seller work dir, which shares the layout)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .canary import Canary
from .crypto import VerifyKey
from .lineage import load_atoms, load_episodes
from .manifest import load_anchor, load_manifest
from .models import Atom, Episode
from .redact import WorkDir


class Package(WorkDir):
    def __init__(self, path: str | Path):
        super().__init__(path)

    # --- files ------------------------------------------------------------------------------
    def exists(self, rel: str) -> bool:
        return (self.path / rel).exists()

    def read_json(self, rel: str) -> Optional[dict]:
        p = self.path / rel
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    @property
    def meta(self) -> dict:
        return self.read_json("package.json") or {}

    def manifest(self) -> tuple[Optional[dict], Optional[str]]:
        if not self.exists("manifest.json"):
            return None, None
        return load_manifest(self.path)

    def anchor(self) -> Optional[dict]:
        return load_anchor(self.path)

    def seller_pub(self) -> Optional[VerifyKey]:
        p = self.path / "pubkeys" / "seller.pub"
        return VerifyKey.load(p) if p.exists() else None

    def atoms(self) -> list[Atom]:
        return load_atoms(self.path / "lineage.jsonl")

    def episodes(self) -> list[Episode]:
        return load_episodes(self.path / "episodes.jsonl")

    def ratios(self) -> Optional[bytes]:
        p = self.path / "ratios.json"
        return p.read_bytes() if p.exists() else None

    def registry_entry(self) -> Optional[dict]:
        return self.read_json("canary/registry_entry.json")

    def canary(self) -> Optional[Canary]:
        e = self.registry_entry()
        return Canary.from_dict(e["entry"]) if e else None

    def holdout_commit(self) -> Optional[dict]:
        return self.read_json("holdout/commit.json")

    def all_files(self) -> list[Path]:
        return sorted(p for p in self.path.rglob("*") if p.is_file())
