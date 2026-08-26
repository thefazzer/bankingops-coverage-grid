"""§9 PUBLICATION BUNDLE: bocg-bundle-<prompt_sha8>-<date>/ with MANIFEST.sha256."""
from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from .prompt import asset_path
from .util import BocgError, Workspace, read_json, sha256_file

REQUIRED = ["prompt.txt", "system.txt", "prompt.sha256", "schema.json", "aliases.yaml", "aliases.sha256",
            "matrix.csv", "matrix.json", "corroboration.csv", "grid.json", "own_cell.json",
            "coverage_statement.md", "divergence_report.md", "gates_report.json"]
OPTIONAL = ["normalised.json", "canon_names.json", "corroboration_summary.json", "run_meta.json"]


def make_bundle(ws: Workspace, out_dir: Path | None = None, date: str | None = None, require_gates: bool = True,
                echo=print) -> Path:
    missing = [f for f in REQUIRED if not (ws.root / f).exists()]
    if missing:
        raise BocgError(f"cannot bundle; missing workspace files: {missing}")
    if require_gates:
        rep = read_json(ws.gates_report)
        if not rep.get("all_pass"):
            failed = [g["id"] for g in rep["gates"] if g["status"] != "PASS"]
            raise BocgError(f"cannot bundle; gates failing: {failed} (use --no-require-gates to force a draft bundle)")
    sha8 = ws.prompt_sha8_from_meta()
    date = date or datetime.now(timezone.utc).strftime("%Y%m%d")
    root = Path(out_dir) if out_dir else ws.bundle_root
    bdir = root / f"bocg-bundle-{sha8}-{date}"
    if bdir.exists():
        shutil.rmtree(bdir)
    bdir.mkdir(parents=True)
    for f in REQUIRED + OPTIONAL:
        src = ws.root / f
        if src.exists():
            shutil.copyfile(src, bdir / f)
    shutil.copytree(ws.runs_dir(sha8), bdir / "runs" / sha8)
    shutil.copyfile(asset_path("methodology.md"), bdir / "methodology.md")
    shutil.copyfile(asset_path("limits.md"), bdir / "limits.md")
    # MANIFEST: sha256 of every file, sorted by relative path, LF line endings
    lines = []
    for p in sorted(x for x in bdir.rglob("*") if x.is_file()):
        rel = p.relative_to(bdir).as_posix()
        lines.append(f"{sha256_file(p)}  {rel}")
    (bdir / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
    echo(f"[bundle] {bdir} ({len(lines)} files, MANIFEST.sha256 written)")
    return bdir


def verify_manifest(bdir: Path) -> list[str]:
    """Return mismatches between MANIFEST.sha256 and on-disk files (empty list == OK)."""
    bad = []
    for line in (Path(bdir) / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines():
        h, rel = line.split("  ", 1)
        p = Path(bdir) / rel
        if not p.exists() or sha256_file(p) != h:
            bad.append(rel)
    return bad
