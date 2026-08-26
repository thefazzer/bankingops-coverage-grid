"""Seller-side workspace layout used by the CLI.

<ws>/
  source/docs/*.txt  source/origins.json  source/episodes_spec.json  source/holdout_items.json  source/audit_log.json
  gazetteers/*.txt
  manifest.json  manifest.sha  anchor_proof.ots
  vault/                       (encrypted; never shipped)   vault.key (default key file; never shipped)
  work/                        (roots.json, segmentation/, redacted/, lineage.jsonl, episodes.jsonl, ratios.json, pubkeys/)
  canary/registry.jsonl
  holdout/commit.json
  pkg-<package_id>/            (§9 package)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .canary import Registry
from .classes import Gazetteer
from .models import SourceDoc
from .ner import RuleDetector
from .redact import WorkDir, load_source_docs
from .vault import NonceVault, resolve_vault_key


class Workspace:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    @property
    def source(self) -> Path:
        return self.root / "source"

    @property
    def gazetteers(self) -> Path:
        return self.root / "gazetteers"

    @property
    def vault_dir(self) -> Path:
        return self.root / "vault"

    @property
    def work(self) -> WorkDir:
        return WorkDir(self.root / "work")

    @property
    def registry(self) -> Registry:
        return Registry(self.root / "canary" / "registry.jsonl")

    @property
    def holdout_dir(self) -> Path:
        return self.root / "holdout"

    def package_dir(self, package_id: str) -> Path:
        return self.root / f"pkg-{package_id}"

    def vault(self, key_file: Optional[str] = None, create: bool = False) -> NonceVault:
        key = resolve_vault_key(key_file, self.root, create=create)
        v = NonceVault(self.vault_dir, key)
        if create:
            v.init()
        return v

    def docs(self) -> list[SourceDoc]:
        return load_source_docs(self.source)

    def gazetteer(self) -> Gazetteer:
        return Gazetteer.load(self.gazetteers) if self.gazetteers.exists() else Gazetteer()

    def detector(self, redact_amounts: bool = False) -> RuleDetector:
        return RuleDetector(self.gazetteer(), redact_amounts=redact_amounts)

    def audit_log(self) -> Optional[list[dict]]:
        p = self.source / "audit_log.json"
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def episodes_spec(self) -> dict:
        return json.loads((self.source / "episodes_spec.json").read_text(encoding="utf-8"))
