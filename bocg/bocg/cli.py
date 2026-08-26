"""`bocg` command-line interface (SPEC-01 §10)."""
from __future__ import annotations

import sys
from pathlib import Path

import click

from .util import BocgError, Workspace

WORKDIR_OPT = click.option("--workdir", "-w", default="bocg_work", show_default=True, type=click.Path(),
                           help="bocg working directory")


def _ws(workdir: str) -> Workspace:
    return Workspace(Path(workdir))


def _fail(e: Exception) -> None:
    click.echo(f"error: {e}", err=True)
    sys.exit(2)


@click.group()
@click.version_option(package_name="bocg")
def main() -> None:
    """BankingOps Coverage Grid — model-consensus taxonomy elicitation (SPEC-01)."""


@main.command()
@click.option("--panel", "panel_path", type=click.Path(exists=True, dir_okay=False), default=None,
              help="panel.yaml (models, samples, params, call settings). Optional in --fixtures mode.")
@click.option("--fixtures", "fixtures", type=click.Path(exists=True, file_okay=False), default=None,
              help="DRY_RUN: replay stored responses from DIR/<model_id>/<i>.json (no network)")
@click.option("--concurrency", type=int, default=1, show_default=True,
              help="parallel in-flight calls (live mode only; each call is independent/cold so this cannot "
                   "affect response content). Fixture replay always runs sequentially.")
@WORKDIR_OPT
def run(panel_path: str | None, fixtures: str | None, concurrency: int, workdir: str) -> None:
    """Run the frozen prompt against the panel (cold, logged verbatim) or replay fixtures."""
    from .run import Panel, run_panel
    try:
        panel = Panel.load(Path(panel_path)) if panel_path else Panel.default_fixture_panel()
        if not panel_path and not fixtures:
            raise BocgError("--panel is required unless --fixtures is given")
        meta = run_panel(_ws(workdir), panel, fixtures_dir=Path(fixtures) if fixtures else None,
                         echo=click.echo, concurrency=max(1, concurrency))
        click.echo(f"[run] prompt_sha8={meta['prompt_sha8']} models={len(meta['models'])} -> {workdir}/runs/")
    except BocgError as e:
        _fail(e)


@main.command()
@click.option("--aliases", "aliases", type=click.Path(exists=True, dir_okay=False), default=None,
              help="aliases.yaml (canon_name -> division_key). If omitted, an identity AUTO-DRAFT is generated.")
@WORKDIR_OPT
def normalise(aliases: str | None, workdir: str) -> None:
    """Validate runs, recompute admission server-side, canonicalise names, apply the alias table."""
    from .normalise import normalise_runs
    try:
        normalise_runs(_ws(workdir), aliases_path=Path(aliases) if aliases else None, echo=click.echo)
    except BocgError as e:
        _fail(e)


@main.command()
@WORKDIR_OPT
def matrix(workdir: str) -> None:
    """Build the agreement matrix (matrix.csv + matrix.json) with tiers, axis votes, anchor/seat pools."""
    from .matrix import write_matrix
    try:
        write_matrix(_ws(workdir), echo=click.echo)
    except BocgError as e:
        _fail(e)


@main.command()
@click.option("--ledger", "ledger", type=click.Path(dir_okay=False), required=True,
              help="corroboration.csv; created from the anchor pool if it does not exist")
@click.option("--init", "init", is_flag=True, help="(re)initialise: add UNVERIFIED rows for any pooled anchor missing")
@WORKDIR_OPT
def corroborate(ledger: str, init: bool, workdir: str) -> None:
    """Initialise / validate the corroboration ledger and write corroboration_summary.json."""
    from .corroborate import corroborate as _corr
    try:
        _corr(_ws(workdir), Path(ledger), init=init, echo=click.echo)
    except BocgError as e:
        _fail(e)


@main.command()
@WORKDIR_OPT
def grid(workdir: str) -> None:
    """Write grid.json from matrix.json + corroboration summary."""
    from .grid import write_grid
    try:
        write_grid(_ws(workdir), echo=click.echo)
    except BocgError as e:
        _fail(e)


@main.command()
@click.option("--own-cell", "own_cell", type=click.Path(exists=True, dir_okay=False), required=True)
@WORKDIR_OPT
def coverage(own_cell: str, workdir: str) -> None:
    """Render coverage_statement.md + divergence_report.md from own_cell.json (post hoc, I10)."""
    from .coverage import write_coverage
    try:
        write_coverage(_ws(workdir), Path(own_cell), echo=click.echo)
    except BocgError as e:
        _fail(e)


@main.command()
@click.argument("which", nargs=-1)
@WORKDIR_OPT
def gate(which: tuple[str, ...], workdir: str) -> None:
    """Run gates: `bocg gate all` (writes gates_report.json) or `bocg gate G1 G6`. Exit 1 on any FAIL."""
    from .gates import run_gates
    ids = None if (not which or "all" in which) else [w.upper() for w in which]
    try:
        report = run_gates(_ws(workdir), ids)
    except BocgError as e:
        _fail(e)
        return
    for g in report["gates"]:
        click.echo(f"{g['id']:<4} {g['name']:<20} {g['status']}")
        if g["status"] != "PASS":
            ev = g["evidence"]
            keys = [k for k in ev if ev[k] not in (None, [], {}, 0, False, "")]
            for k in keys[:8]:
                click.echo(f"      {k}: {str(ev[k])[:300]}")
    if ids is None:
        click.echo(f"gates_report.json written: all_pass={report['all_pass']}")
    if not report["all_pass"]:
        sys.exit(1)


@main.command()
@click.option("--out", "out", type=click.Path(file_okay=False), default=None, help="bundle parent dir")
@click.option("--date", "date", default=None, help="YYYYMMDD (default: today UTC)")
@click.option("--no-require-gates", "no_gates", is_flag=True, help="build a draft bundle even if gates fail")
@WORKDIR_OPT
def bundle(out: str | None, date: str | None, no_gates: bool, workdir: str) -> None:
    """Assemble bocg-bundle-<prompt_sha8>-<date>/ with MANIFEST.sha256."""
    from .bundle import make_bundle
    try:
        make_bundle(_ws(workdir), Path(out) if out else None, date=date, require_gates=not no_gates, echo=click.echo)
    except BocgError as e:
        _fail(e)


if __name__ == "__main__":
    main()
