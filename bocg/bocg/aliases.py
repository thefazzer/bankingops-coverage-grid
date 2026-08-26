"""§5.2 ALIAS_TABLE: aliases.yaml (canon_name -> division_key), versioned, with rationale per decision."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .canon import canon_name, slug_key
from .util import BocgError, sha256_file


@dataclass
class AliasTable:
    version: int
    authored_after_runs: str | None
    entries: list[dict]                   # [{canon, key, rationale}]
    auto_generated: bool = False
    mapping: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "AliasTable":
        if not isinstance(d, dict) or "aliases" not in d:
            raise BocgError("aliases.yaml must be a mapping with an `aliases` list")
        t = cls(version=int(d.get("version", 1)), authored_after_runs=d.get("authored_after_runs"),
                entries=list(d["aliases"] or []), auto_generated=bool(d.get("auto_generated", False)))
        t.validate()
        return t

    def validate(self) -> list[str]:
        problems = []
        seen: dict[str, str] = {}
        for i, e in enumerate(self.entries):
            if not isinstance(e, dict) or not e.get("canon") or not e.get("key"):
                problems.append(f"entry {i}: needs `canon` and `key`")
                continue
            c = canon_name(str(e["canon"]))
            if c != str(e["canon"]).strip():
                # tolerate non-canonical spelling but always match on the canonical form
                pass
            k = str(e["key"])
            if not str(e.get("rationale", "")).strip():
                problems.append(f"entry {i} ({c!r}): missing rationale")
            if c in seen and seen[c] != k:
                problems.append(f"alias {c!r} maps to two keys: {seen[c]!r} and {k!r}")
            seen[c] = k
        if problems:
            raise BocgError("invalid aliases.yaml: " + "; ".join(problems))
        self.mapping = seen
        return problems

    def key_for(self, name: str) -> str | None:
        return self.mapping.get(canon_name(name))

    def keys(self) -> set[str]:
        return set(self.mapping.values())

    def to_dict(self) -> dict:
        d = {"version": self.version, "authored_after_runs": self.authored_after_runs, "aliases": self.entries}
        if self.auto_generated:
            d["auto_generated"] = True
        return d


def load_aliases(path: Path) -> AliasTable:
    path = Path(path)
    if not path.exists():
        raise BocgError(f"alias table not found: {path}")
    return AliasTable.from_dict(yaml.safe_load(path.read_text(encoding="utf-8")) or {})


def write_aliases(path: Path, table: AliasTable) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    header = ("# BOCG alias table (SPEC-01 §5.2). Maps canon_name -> division_key. Authored AFTER all runs complete.\n"
              "# Every entry must carry a rationale. The sha256 of this file is published in aliases.sha256.\n")
    path.write_text(header + yaml.safe_dump(table.to_dict(), sort_keys=False, allow_unicode=True), encoding="utf-8")
    return sha256_file(path)


def draft_identity_table(canon_names: list[str], prompt_sha8: str) -> AliasTable:
    """Auto-draft: identity mapping canon -> slug key. Marked auto_generated; a human must review before publication."""
    entries = [{"canon": c, "key": slug_key(c), "rationale": "AUTO-DRAFT identity mapping (unreviewed)"}
               for c in sorted(set(canon_names))]
    t = AliasTable(version=1, authored_after_runs=prompt_sha8, entries=entries, auto_generated=True)
    t.validate()
    return t
