"""End-to-end through the `bocg` CLI on fixtures: run -> normalise -> matrix -> corroborate -> grid -> coverage
-> gate all -> bundle. No network."""
import json
import subprocess
import sys
from pathlib import Path

from click.testing import CliRunner

from bocg.bundle import verify_manifest
from bocg.cli import main
from conftest import FIXTURES


def _cli(args, cwd):
    r = CliRunner().invoke(main, args + ["-w", str(cwd)])
    return r


def test_bocg_console_script_exists():
    out = subprocess.run(["bocg", "--help"], capture_output=True, text=True, check=True)
    assert "BankingOps Coverage Grid" in out.stdout


def test_end_to_end_fixture_pipeline(tmp_path):
    w = tmp_path / "work"
    steps = [
        ["run", "--fixtures", str(FIXTURES), "--panel", str(FIXTURES / "panel-fixtures.yaml")],
        ["normalise", "--aliases", str(FIXTURES / "aliases.yaml")],
        ["matrix"],
        ["corroborate", "--ledger", str(FIXTURES / "corroboration_all_verified.csv")],
        ["grid"],
        ["coverage", "--own-cell", str(FIXTURES / "own_cell.json")],
        ["gate", "all"],
        ["bundle", "--date", "20250101"],
    ]
    for s in steps:
        r = _cli(s, w)
        assert r.exit_code == 0, f"{s}: {r.output}\n{r.exception}"
    rep = json.loads((w / "gates_report.json").read_text())
    assert rep["all_pass"] and len(rep["gates"]) == 10
    sha8 = json.loads((w / "run_meta.json").read_text())["prompt_sha8"]
    b = w / "bundle" / f"bocg-bundle-{sha8}-20250101"
    for f in ["prompt.txt", "system.txt", "prompt.sha256", "schema.json", "aliases.yaml", "aliases.sha256",
              "matrix.csv", "matrix.json", "corroboration.csv", "grid.json", "own_cell.json",
              "coverage_statement.md", "divergence_report.md", "methodology.md", "limits.md", "gates_report.json",
              "MANIFEST.sha256"]:
        assert (b / f).exists(), f
    assert len(list((b / "runs" / sha8).glob("*/*.json"))) == 14
    assert verify_manifest(b) == []
    assert (b / "prompt.sha256").read_text().split()[0] == sha8 + (b / "prompt.sha256").read_text().split()[0][8:]
    assert "consensus = textual convergence" in (b / "limits.md").read_text().lower().replace("**", "") or \
        "textual convergence, not economic importance" in (b / "limits.md").read_text()
    cov = (b / "coverage_statement.md").read_text()
    assert "`settlements`" in cov and "No claim is made about them" in cov
    assert "settlements" in (b / "divergence_report.md").read_text()


def test_gate_all_exits_nonzero_on_failure(tmp_path):
    w = tmp_path / "work"
    for s in [["run", "--fixtures", str(FIXTURES)], ["normalise", "--aliases", str(FIXTURES / "aliases.yaml")],
              ["matrix"], ["corroborate", "--ledger", str(FIXTURES / "corroboration_one_unverified.csv")], ["grid"],
              ["coverage", "--own-cell", str(FIXTURES / "own_cell.json")]]:
        assert _cli(s, w).exit_code == 0
    r = _cli(["gate", "all"], w)
    assert r.exit_code == 1 and "G6   CORROBORATION_GATE   FAIL" in r.output
    rb = _cli(["bundle"], w)
    assert rb.exit_code == 2 and "gates failing" in rb.output
    assert _cli(["bundle", "--no-require-gates", "--date", "20250101"], w).exit_code == 0


def test_run_without_panel_discovers_fixture_models_and_auto_drafts_aliases(tmp_path):
    w = tmp_path / "work"
    assert _cli(["run", "--fixtures", str(FIXTURES)], w).exit_code == 0
    r = _cli(["normalise"], w)
    assert r.exit_code == 0 and "AUTO-DRAFT" in r.output
    assert (w / "aliases.yaml").exists() and (w / "aliases.sha256").exists()
    assert _cli(["matrix"], w).exit_code == 0
    # identity draft: every canon becomes its own key, so more rows than the curated table
    assert len((w / "matrix.csv").read_text().splitlines()) - 1 > 11


def test_coverage_rejects_claims_beyond_filled_cells(tmp_path, ws_full):
    oc = json.loads((FIXTURES / "own_cell.json").read_text())
    oc["division_keys"].append("division_x")
    p = tmp_path / "oc.json"
    p.write_text(json.dumps(oc))
    r = _cli(["coverage", "--own-cell", str(p)], ws_full.root)
    assert r.exit_code == 2 and "division_x" in r.output


def test_run_requires_panel_or_fixtures(tmp_path):
    r = _cli(["run"], tmp_path / "w")
    assert r.exit_code == 2 and "--panel is required" in r.output


def test_python_module_entrypoint():
    out = subprocess.run([sys.executable, "-m", "bocg.cli", "--help"], capture_output=True, text=True)
    assert out.returncode == 0
