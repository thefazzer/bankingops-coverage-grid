"""§7 grid.json: axes + cells (division_key, tier, axis, anchors_verified, seat cost median, terminality count)."""
from __future__ import annotations

from .util import BocgError, Workspace, read_json, write_json

GRID_VERSION = "bocg.grid.v1"


def build_grid(mx: dict, corroboration_summary: dict | None) -> dict:
    cells = []
    axes = {"business_line": set(), "side": set(), "region": set(), "product": set(), "office": set()}
    divs = (corroboration_summary or {}).get("divisions", {})
    for r in mx["rows"]:
        key = r["division_key"]
        c = divs.get(key)
        if c is None:
            anchors_verified = {"A1": 0, "A2": 0, "A3": 0, "A4": False}
            tier = r["tier"]
            corroborated = False
        else:
            anchors_verified = c["anchors_verified"]
            tier = "REJECTED_POST_CORROBORATION" if c["rejected_post_corroboration"] else r["tier"]
            corroborated = bool(c["publishable"])
        ax = r["axis"]
        axes["business_line"].add(ax["business_line"])
        axes["side"].add(ax["side"])
        axes["region"].update(ax["region"])
        axes["product"].update(ax["product"])
        axes["office"].add(ax["office"])
        cells.append({
            "division_key": key,
            "tier": tier,
            "consensus_tier": r["tier"],
            "model_support": r["model_support"],
            "axis": ax,
            "anchors_verified": anchors_verified,
            "corroborated": corroborated,
            "addressable_seat_cost_median": r["seat_pool"]["addressable_seat_cost_median"],
            "terminality_count": r["seat_pool"]["terminality_count"],
            "corpus_coverage": None,
        })
    cells.sort(key=lambda c: c["division_key"])
    return {"schema_version": GRID_VERSION, "prompt_sha8": mx["prompt_sha8"], "aliases_sha256": mx["aliases_sha256"],
            "n_models": mx["n_models"],
            "axes": {k: sorted(v) for k, v in axes.items()},
            "cells": cells}


def write_grid(ws: Workspace, echo=print) -> dict:
    if not ws.matrix_json.exists():
        raise BocgError("matrix.json missing; run `bocg matrix` first")
    mx = read_json(ws.matrix_json)
    summ = read_json(ws.corroboration_summary) if ws.corroboration_summary.exists() else None
    if summ is None:
        echo("[grid] WARNING no corroboration summary; anchors_verified will be all zero")
    g = build_grid(mx, summ)
    write_json(ws.grid_json, g)
    echo(f"[grid] {len(g['cells'])} cells -> {ws.grid_json}")
    return g
