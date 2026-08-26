"""§5.3–5.7: agreement matrix, consensus tiers, axis vote, anchor pool, seat pool. Deterministic ordering."""
from __future__ import annotations

import math
from collections import Counter
from typing import Any

from .canon import canon_name
from .util import Workspace, median, read_json, write_csv, write_json

MATRIX_VERSION = "bocg.matrix.v1"
SUPPORT_CELL = 0.5


def anchor_citation_text(atype: str, a: dict) -> str:
    """The text that identifies an anchor for dedupe (§5.6) and for the corroboration ledger (§6)."""
    if atype == "A1":
        return f"{a.get('regime','')} | {a.get('jurisdiction','')} | {a.get('citation','')}"
    if atype == "A2":
        return f"{a.get('bank','')} | {a.get('filing','')} | FY{a.get('fiscal_year','')} | {a.get('line_item','')}"
    if atype == "A3":
        return (f"{a.get('publisher','')} | {a.get('series','')} | {a.get('value','')} {a.get('unit','')} | "
                f"as_of {a.get('as_of','')}")
    raise ValueError(atype)


def anchor_dedupe_key(atype: str, a: dict) -> tuple[str, str]:
    if atype == "A1":
        cit = a.get("citation", "")
    elif atype == "A2":
        cit = f"{a.get('bank','')} {a.get('filing','')} {a.get('fiscal_year','')} {a.get('line_item','')}"
    else:
        cit = f"{a.get('publisher','')} {a.get('series','')} {a.get('as_of','')}"
    return (atype, canon_name(cit))


def tiers(model_support: int, n_models: int) -> str:
    if n_models > 0 and model_support >= math.ceil(0.8 * n_models):
        return "STRONG"
    if n_models > 0 and model_support >= math.ceil(0.5 * n_models):
        return "MODERATE"
    return "WEAK"


def _vote_scalar(values: list[Any], tie_value: Any) -> Any:
    c = Counter(v for v in values if v is not None)
    if not c:
        return tie_value
    top = c.most_common()
    if len(top) > 1 and top[0][1] == top[1][1]:
        return tie_value
    return top[0][0]


def _vote_list(lists: list[list[Any]], fallback: Any) -> list[Any]:
    n = len(lists)
    c: Counter = Counter()
    for lst in lists:
        for v in set(lst or []):
            c[v] += 1
    chosen = sorted(v for v, k in c.items() if k * 2 > n)   # strict majority; ties => fallback
    return chosen or [fallback]


def axis_vote(axes: list[dict]) -> dict:
    return {
        "business_line": _vote_scalar([a.get("business_line") for a in axes], "multi"),
        "side": _vote_scalar([a.get("side") for a in axes], "both"),
        "region": _vote_list([a.get("region") or [] for a in axes], "GLOBAL"),
        "product": _vote_list([a.get("product") or [] for a in axes], "multi"),
        "office": _vote_scalar([a.get("office") for a in axes], "multi"),
    }


def build_matrix(norm: dict) -> dict:
    samples = norm["samples"]
    # columns: model ids in deterministic (sorted) order; k = samples run per model (all statuses)
    k_by_model: Counter = Counter(s["model_id"] for s in samples)
    vendor_by_model = {s["model_id"]: s.get("vendor") for s in samples}
    models = sorted(k_by_model)
    n_models = len(models)

    naming: dict[str, dict[str, set]] = {}          # key -> model -> {sample_idx}
    per_key: dict[str, dict[str, list]] = {}        # key -> {axes, anchors, seat...}
    for s in samples:
        if s["status"] != "VALID":
            continue
        seen_in_sample: set[str] = set()
        for d in s["divisions"]:
            key = d.get("division_key")
            if not d["server_admitted"] or key is None:
                continue
            naming.setdefault(key, {}).setdefault(s["model_id"], set()).add(s["sample_idx"])
            pk = per_key.setdefault(key, {"axes": [], "a1": [], "a2": [], "a3": [], "seat_mid": [],
                                          "det_frac": [], "addr": [], "terminality": [], "names": [],
                                          "functions": []})
            pk["axes"].append(d["axis"])
            for atype, fld in (("A1", "a1_regulatory"), ("A2", "a2_segment"), ("A3", "a3_market_size")):
                for a in (d.get(fld) or []):
                    pk[atype.lower()].append(a)
            seat = d["a4_seat"]
            lo, hi = seat["cost_per_seat"]
            pk["seat_mid"].append((float(lo) + float(hi)) / 2.0)
            pk["det_frac"].append(float(seat["determinable_fraction"]))
            pk["addr"].append(float(d["admission"]["addressable_seat_cost_recomputed"]))
            pk["terminality"].extend(seat.get("terminality") or [])
            pk["functions"].append(seat.get("function"))
            if d["name"] not in pk["names"]:
                pk["names"].append(d["name"])
            seen_in_sample.add(key)

    keys = sorted(naming)
    cells: dict[str, dict[str, float]] = {}
    rows = []
    for key in keys:
        cells[key] = {}
        for m in models:
            n = len(naming[key].get(m, ()))
            cells[key][m] = round(n / k_by_model[m], 6) if k_by_model[m] else 0.0
        support = sum(1 for m in models if cells[key][m] >= SUPPORT_CELL)
        pk = per_key[key]
        # §5.6 anchor pool: union deduped by (type, canon(citation))
        pool: dict[str, list[dict]] = {"A1": [], "A2": [], "A3": []}
        seen_anchor: set[tuple[str, str]] = set()
        for atype in ("A1", "A2", "A3"):
            for a in pk[atype.lower()]:
                dk = anchor_dedupe_key(atype, a)
                if dk in seen_anchor:
                    continue
                seen_anchor.add(dk)
                pool[atype].append({"anchor": a, "anchor_text": anchor_citation_text(atype, a), "dedupe": dk[1]})
            pool[atype].sort(key=lambda x: x["anchor_text"])
        # §5.7 seat pool
        tasks: dict[str, dict] = {}
        for t in pk["terminality"]:
            c = canon_name(t.get("task", ""))
            if c and c not in tasks:
                tasks[c] = {"canon": c, **t}
        seat_pool = {
            "cost_per_seat_midpoint_median": median(pk["seat_mid"]),
            "determinable_fraction_median": median(pk["det_frac"]),
            "addressable_seat_cost_median": median(pk["addr"]),
            "functions": sorted({f for f in pk["functions"] if f}),
            "terminality_tasks": [tasks[c] for c in sorted(tasks)],
            "terminality_count": len(tasks),
        }
        rows.append({
            "division_key": key,
            "names": sorted(pk["names"]),
            "cells": cells[key],
            "model_support": support,
            "tier": tiers(support, n_models),
            "axis": axis_vote(pk["axes"]),
            "anchor_pool": pool,
            "seat_pool": seat_pool,
            "n_samples": sum(len(v) for v in naming[key].values()),
        })

    return {"schema_version": MATRIX_VERSION, "prompt_sha8": norm["prompt_sha8"],
            "aliases_sha256": norm["aliases_sha256"], "threshold_usd": norm["threshold_usd"],
            "models": [{"model_id": m, "vendor": vendor_by_model.get(m), "k": k_by_model[m]} for m in models],
            "n_models": n_models,
            "tier_thresholds": {"STRONG": math.ceil(0.8 * n_models) if n_models else None,
                                "MODERATE": math.ceil(0.5 * n_models) if n_models else None},
            "division_keys": keys, "rows": rows}


def matrix_csv_rows(mx: dict) -> tuple[list[str], list[list]]:
    models = [m["model_id"] for m in mx["models"]]
    header = ["division_key"] + models + ["model_support", "tier"]
    rows = []
    for r in mx["rows"]:
        rows.append([r["division_key"]] + [f"{r['cells'][m]:.4f}" for m in models] + [r["model_support"], r["tier"]])
    return header, rows


def write_matrix(ws: Workspace, echo=print) -> dict:
    norm = read_json(ws.normalised_json)
    mx = build_matrix(norm)
    header, rows = matrix_csv_rows(mx)
    write_csv(ws.matrix_csv, header, rows)
    write_json(ws.matrix_json, mx)
    echo(f"[matrix] {len(mx['rows'])} division keys x {mx['n_models']} models -> {ws.matrix_csv}")
    return mx
