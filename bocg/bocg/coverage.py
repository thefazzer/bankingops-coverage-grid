"""§7 / I10: own_cell.json (post hoc, separate) -> coverage_statement.md + divergence_report.md."""
from __future__ import annotations

import shutil
from pathlib import Path

from .util import BocgError, Workspace, read_json

REQUIRED_OWN_CELL_KEYS = ("division_keys", "corpus_coverage", "practitioner_divergences")
CLUSTER_BUCKETS = ("supports_well", "thin", "cannot_speak")


def validate_own_cell(oc: dict, grid: dict) -> list[str]:
    problems = []
    for k in REQUIRED_OWN_CELL_KEYS:
        if k not in oc:
            problems.append(f"own_cell.json missing `{k}`")
    if problems:
        return problems
    cell_keys = {c["division_key"] for c in grid["cells"]}
    for k in oc["division_keys"]:
        if k not in cell_keys:
            problems.append(f"division_key {k!r} is not a filled cell in grid.json (no claims beyond filled cells)")
    if not isinstance(oc["corpus_coverage"], dict):
        problems.append("`corpus_coverage` must map task_cluster -> {supports_well[], thin[], cannot_speak[]}")
    else:
        for cluster, buckets in oc["corpus_coverage"].items():
            for b in CLUSTER_BUCKETS:
                if b not in buckets or not isinstance(buckets[b], list):
                    problems.append(f"corpus_coverage[{cluster!r}] needs list `{b}`")
    for i, d in enumerate(oc["practitioner_divergences"]):
        for f in ("division_key", "consensus_view", "practitioner_view", "evidence"):
            if f not in d:
                problems.append(f"practitioner_divergences[{i}] missing `{f}`")
        if d.get("division_key") not in cell_keys:
            problems.append(f"practitioner_divergences[{i}] refers to unknown division_key {d.get('division_key')!r}")
    return problems


def _fmt_money(v) -> str:
    return "n/a" if v is None else f"{v:,.0f}"


def render_coverage_statement(oc: dict, grid: dict) -> str:
    cells = {c["division_key"]: c for c in grid["cells"]}
    out = ["# Coverage statement", "",
           f"Generated post hoc from `own_cell.json` and `grid.json` (prompt `{grid['prompt_sha8']}`, "
           f"alias table `{grid['aliases_sha256'][:8]}`). This statement makes claims **only** about the filled "
           "grid cells listed below. It does not rank divisions, does not assert economic importance, and does "
           "not describe any model's capability (gaps are not elicited; they can only come from measured task "
           "scores in a later phase).", "",
           "## Cells addressed", "",
           "| division_key | tier | side | office | region | product | verified anchors (A1/A2/A3/A4) | "
           "addressable seat cost (median) | terminality tasks |",
           "|---|---|---|---|---|---|---|---|---|"]
    for k in oc["division_keys"]:
        c = cells[k]
        av = c["anchors_verified"]
        ax = c["axis"]
        out.append(f"| `{k}` | {c['tier']} | {ax['side']} | {ax['office']} | {', '.join(ax['region'])} | "
                   f"{', '.join(ax['product'])} | {av['A1']}/{av['A2']}/{av['A3']}/{'yes' if av['A4'] else 'no'} | "
                   f"{_fmt_money(c['addressable_seat_cost_median'])} | {c['terminality_count']} |")
    out += ["", "## Corpus coverage per task cluster", "",
            "Buckets are the seller's own declaration of what its corpus can and cannot speak to. They are not "
            "model outputs and were not elicited from any model.", ""]
    for cluster in sorted(oc["corpus_coverage"]):
        b = oc["corpus_coverage"][cluster]
        out.append(f"### {cluster}")
        out.append("")
        for bucket in CLUSTER_BUCKETS:
            items = b.get(bucket) or []
            out.append(f"- **{bucket}**: " + (", ".join(f"`{i}`" for i in items) if items else "_none declared_"))
        out.append("")
    not_addressed = sorted(set(cells) - set(oc["division_keys"]))
    out += ["## Limits", "",
            "- Consensus tier = textual convergence of frozen models under a cold prompt, not economic importance.",
            "- Competency gaps were not elicited from models and are not claimed here.",
            "- Anchor counts are corroboration statistics (ledger status VERIFIED), not market statistics.",
            f"- Grid cells not addressed by this statement ({len(not_addressed)}): "
            + (", ".join(f"`{k}`" for k in not_addressed) if not_addressed else "none")
            + ". No claim is made about them.",
            f"- Practitioner divergences from consensus: {len(oc['practitioner_divergences'])} "
            "(see `divergence_report.md`; published as findings, not smoothed).", ""]
    return "\n".join(out)


def render_divergence_report(oc: dict, grid: dict) -> str:
    cells = {c["division_key"]: c for c in grid["cells"]}
    out = ["# Divergence report", "",
           "Where the practitioner view differs from the model consensus. Each divergence is published as a "
           "finding; the consensus value in `grid.json` is **not** altered to match the practitioner.", ""]
    divs = oc["practitioner_divergences"]
    if not divs:
        out.append("_No divergences declared._")
        return "\n".join(out) + "\n"
    for i, d in enumerate(sorted(divs, key=lambda x: x["division_key"]), 1):
        c = cells.get(d["division_key"], {})
        out += [f"## {i}. `{d['division_key']}` (tier {c.get('tier', '?')}, model_support {c.get('model_support', '?')})",
                "", f"- **Consensus view:** {d['consensus_view']}", f"- **Practitioner view:** {d['practitioner_view']}",
                f"- **Evidence:** {d['evidence']}", ""]
    return "\n".join(out)


def write_coverage(ws: Workspace, own_cell_path: Path, echo=print) -> None:
    if not ws.grid_json.exists():
        raise BocgError("grid.json missing; run `bocg grid` first")
    grid = read_json(ws.grid_json)
    oc = read_json(own_cell_path)
    problems = validate_own_cell(oc, grid)
    if problems:
        raise BocgError("invalid own_cell.json: " + "; ".join(problems))
    if Path(own_cell_path).resolve() != ws.own_cell_json.resolve():
        shutil.copyfile(own_cell_path, ws.own_cell_json)
    ws.coverage_md.write_text(render_coverage_statement(oc, grid), encoding="utf-8")
    ws.divergence_md.write_text(render_divergence_report(oc, grid), encoding="utf-8")
    echo(f"[coverage] wrote {ws.coverage_md} and {ws.divergence_md}")
