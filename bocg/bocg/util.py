"""Shared helpers: hashing, deterministic JSON, timestamps, workspace paths."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


class BocgError(Exception):
    """Raised for user-facing pipeline errors (missing inputs, invalid ledgers, ...)."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def canonical_json(obj: Any) -> str:
    """Deterministic JSON: sorted keys, fixed separators, trailing newline, ASCII-safe off."""
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def write_json(path: Path, obj: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(obj), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_csv(path: Path, header: list[str], rows: Iterable[list[Any]]) -> None:
    """Deterministic CSV: LF line endings, minimal quoting, UTF-8."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    for r in rows:
        w.writerow(r)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(buf.getvalue(), encoding="utf-8")


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        rows = list(r)
        return list(r.fieldnames or []), rows


def safe_dirname(model_id: str) -> str:
    """Model ids are used as directory names; keep them filesystem-safe (colons/slashes replaced)."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", model_id)


def median(values: list[float]) -> float | None:
    vals = sorted(float(v) for v in values)
    if not vals:
        return None
    n = len(vals)
    mid = n // 2
    if n % 2 == 1:
        return vals[mid]
    return (vals[mid - 1] + vals[mid]) / 2.0


def env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


class Workspace:
    """Layout of a bocg working directory."""

    def __init__(self, root: Path | str):
        self.root = Path(root)

    # frozen inputs (copied at run time)
    @property
    def prompt_txt(self) -> Path: return self.root / "prompt.txt"
    @property
    def system_txt(self) -> Path: return self.root / "system.txt"
    @property
    def prompt_sha256(self) -> Path: return self.root / "prompt.sha256"
    @property
    def schema_json(self) -> Path: return self.root / "schema.json"
    @property
    def run_meta(self) -> Path: return self.root / "run_meta.json"
    @property
    def runs_root(self) -> Path: return self.root / "runs"
    # normalisation
    @property
    def normalised_json(self) -> Path: return self.root / "normalised.json"
    @property
    def canon_names_json(self) -> Path: return self.root / "canon_names.json"
    @property
    def aliases_yaml(self) -> Path: return self.root / "aliases.yaml"
    @property
    def aliases_sha256(self) -> Path: return self.root / "aliases.sha256"
    # matrix
    @property
    def matrix_csv(self) -> Path: return self.root / "matrix.csv"
    @property
    def matrix_json(self) -> Path: return self.root / "matrix.json"
    # corroboration
    @property
    def corroboration_csv(self) -> Path: return self.root / "corroboration.csv"
    @property
    def corroboration_summary(self) -> Path: return self.root / "corroboration_summary.json"
    # grid / coverage
    @property
    def grid_json(self) -> Path: return self.root / "grid.json"
    @property
    def own_cell_json(self) -> Path: return self.root / "own_cell.json"
    @property
    def coverage_md(self) -> Path: return self.root / "coverage_statement.md"
    @property
    def divergence_md(self) -> Path: return self.root / "divergence_report.md"
    # gates / bundle
    @property
    def gates_report(self) -> Path: return self.root / "gates_report.json"
    @property
    def bundle_root(self) -> Path: return self.root / "bundle"

    def runs_dir(self, prompt_sha8: str) -> Path:
        return self.runs_root / prompt_sha8

    def prompt_sha8_from_meta(self) -> str:
        if not self.run_meta.exists():
            raise BocgError(f"missing {self.run_meta}; run `bocg run` first")
        return read_json(self.run_meta)["prompt_sha8"]
