from __future__ import annotations

import json
from pathlib import Path

import pytest

from bocg.corroborate import corroborate
from bocg.coverage import write_coverage
from bocg.grid import write_grid
from bocg.matrix import write_matrix
from bocg.normalise import normalise_runs
from bocg.run import Panel, run_panel
from bocg.util import Workspace

FIXTURES = Path(__file__).parent / "fixtures"
QUIET = lambda *a, **k: None  # noqa: E731


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


def run_to_matrix(root: Path) -> Workspace:
    ws = Workspace(root)
    run_panel(ws, Panel.load(FIXTURES / "panel-fixtures.yaml"), fixtures_dir=FIXTURES, echo=QUIET)
    normalise_runs(ws, aliases_path=FIXTURES / "aliases.yaml", echo=QUIET)
    write_matrix(ws, echo=QUIET)
    return ws


def run_full(root: Path, ledger: str = "corroboration_all_verified.csv") -> Workspace:
    ws = run_to_matrix(root)
    corroborate(ws, FIXTURES / ledger, echo=QUIET)
    write_grid(ws, echo=QUIET)
    write_coverage(ws, FIXTURES / "own_cell.json", echo=QUIET)
    return ws


@pytest.fixture
def ws_matrix(tmp_path: Path) -> Workspace:
    return run_to_matrix(tmp_path / "w")


@pytest.fixture
def ws_full(tmp_path: Path) -> Workspace:
    return run_full(tmp_path / "w")


def load_fixture_response(model: str, idx: int) -> dict:
    return json.loads(json.loads((FIXTURES / model / f"{idx}.json").read_text())["response_raw"])
