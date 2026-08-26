"""§6 CORROBORATION LEDGER: corroboration.csv init (from the anchor pool) + validation + summary."""
from __future__ import annotations

from pathlib import Path

from .util import BocgError, Workspace, read_csv, read_json, utc_now_iso, write_csv, write_json

LEDGER_COLUMNS = ["division_key", "anchor_type", "anchor_text", "source_url_or_doc", "checked_by", "checked_ts",
                  "status", "verified_value", "note"]
STATUSES = {"VERIFIED", "UNVERIFIED", "REFUTED", "PARTIAL"}
ANCHOR_TYPES = {"A1", "A2", "A3", "A4"}


def a4_anchor_text(row: dict) -> str:
    sp = row["seat_pool"]
    fn = "; ".join(sp.get("functions") or [])
    mid = sp.get("cost_per_seat_midpoint_median")
    return (f"SEAT: {fn} | cost_per_seat midpoint median {mid} | determinable_fraction median "
            f"{sp.get('determinable_fraction_median')} | {sp.get('terminality_count')} terminality tasks")


def expected_rows(mx: dict) -> list[dict]:
    """One ledger row per pooled anchor (A1–A3) plus one A4 row per division key. Deterministic order."""
    out = []
    for r in mx["rows"]:
        key = r["division_key"]
        for atype in ("A1", "A2", "A3"):
            for a in r["anchor_pool"][atype]:
                out.append({"division_key": key, "anchor_type": atype, "anchor_text": a["anchor_text"]})
        out.append({"division_key": key, "anchor_type": "A4", "anchor_text": a4_anchor_text(r)})
    return out


def init_ledger(ws: Workspace, ledger_path: Path, echo=print) -> int:
    """Create (or extend, idempotently) the ledger with UNVERIFIED rows for every pooled anchor."""
    mx = read_json(ws.matrix_json)
    existing: list[dict] = []
    if ledger_path.exists():
        cols, existing = read_csv(ledger_path)
        _check_columns(cols)
    have = {(e["division_key"], e["anchor_type"], e["anchor_text"]) for e in existing}
    added = 0
    rows = [dict(e) for e in existing]
    for exp in expected_rows(mx):
        k = (exp["division_key"], exp["anchor_type"], exp["anchor_text"])
        if k in have:
            continue
        rows.append({**exp, "source_url_or_doc": "", "checked_by": "", "checked_ts": "", "status": "UNVERIFIED",
                     "verified_value": "", "note": ""})
        added += 1
    rows.sort(key=lambda e: (e["division_key"], e["anchor_type"], e["anchor_text"]))
    write_csv(ledger_path, LEDGER_COLUMNS, [[e.get(c, "") for c in LEDGER_COLUMNS] for e in rows])
    echo(f"[corroborate] ledger {ledger_path}: {len(rows)} rows ({added} added, UNVERIFIED)")
    return added


def _check_columns(cols: list[str]) -> None:
    if [c.strip() for c in cols] != LEDGER_COLUMNS:
        raise BocgError(f"ledger columns must be exactly {LEDGER_COLUMNS}; got {cols}")


def validate_ledger(mx: dict, ledger_rows: list[dict]) -> dict:
    """Return the corroboration summary (per division) and structural problems."""
    problems = []
    index: dict[tuple[str, str, str], list[dict]] = {}
    for i, e in enumerate(ledger_rows):
        if e.get("status") not in STATUSES:
            problems.append(f"row {i + 2}: invalid status {e.get('status')!r}")
        if e.get("anchor_type") not in ANCHOR_TYPES:
            problems.append(f"row {i + 2}: invalid anchor_type {e.get('anchor_type')!r}")
        if e.get("status") == "VERIFIED" and not (e.get("checked_by") or "").strip():
            problems.append(f"row {i + 2}: VERIFIED without checked_by")
        index.setdefault((e["division_key"], e["anchor_type"], e["anchor_text"]), []).append(e)

    divisions = {}
    for r in mx["rows"]:
        key = r["division_key"]
        counts = {t: {s: 0 for s in sorted(STATUSES)} | {"MISSING": 0} for t in ("A1", "A2", "A3")}
        missing = []
        refuted_texts = []
        for atype in ("A1", "A2", "A3"):
            for a in r["anchor_pool"][atype]:
                rows = index.get((key, atype, a["anchor_text"]))
                if not rows:
                    counts[atype]["MISSING"] += 1
                    missing.append({"anchor_type": atype, "anchor_text": a["anchor_text"]})
                    continue
                st = _worst(rows)
                counts[atype][st] += 1
                if st == "REFUTED":
                    refuted_texts.append(a["anchor_text"])
        a4rows = index.get((key, "A4", a4_anchor_text(r)))
        a4_status = _worst(a4rows) if a4rows else "MISSING"
        if not a4rows:
            missing.append({"anchor_type": "A4", "anchor_text": a4_anchor_text(r)})
        verified_types = sum(1 for t in ("A1", "A2", "A3") if counts[t]["VERIFIED"] > 0)
        non_refuted_types = sum(1 for t in ("A1", "A2", "A3")
                                if (counts[t]["VERIFIED"] + counts[t]["UNVERIFIED"] + counts[t]["PARTIAL"]
                                    + counts[t]["MISSING"]) > 0)
        unverified = sum(counts[t]["UNVERIFIED"] + counts[t]["MISSING"] for t in counts) \
            + (1 if a4_status in ("UNVERIFIED", "MISSING") else 0)
        divisions[key] = {
            "counts": counts, "a4_status": a4_status,
            "anchors_verified": {"A1": counts["A1"]["VERIFIED"], "A2": counts["A2"]["VERIFIED"],
                                 "A3": counts["A3"]["VERIFIED"], "A4": a4_status == "VERIFIED"},
            "verified_types": verified_types,
            "non_refuted_types": non_refuted_types,
            # §6: REFUTED anchors removed; division drops below admission => REJECTED_POST_CORROBORATION
            "rejected_post_corroboration": non_refuted_types < 2 or a4_status == "REFUTED",
            # G6 publication condition
            "publishable": verified_types >= 2 and a4_status == "VERIFIED" and unverified == 0,
            "unverified_count": unverified,
            "refuted": refuted_texts,
            "missing_rows": missing,
        }
    return {"problems": problems, "divisions": divisions, "ledger_rows": len(ledger_rows)}


_ORDER = ["REFUTED", "UNVERIFIED", "PARTIAL", "VERIFIED"]


def _worst(rows: list[dict]) -> str:
    sts = [e.get("status", "UNVERIFIED") for e in rows]
    for s in _ORDER:
        if s in sts:
            return s
    return "UNVERIFIED"


def corroborate(ws: Workspace, ledger_path: Path, init: bool = False, echo=print) -> dict:
    ledger_path = Path(ledger_path)
    if init or not ledger_path.exists():
        init_ledger(ws, ledger_path, echo=echo)
    mx = read_json(ws.matrix_json)
    cols, rows = read_csv(ledger_path)
    _check_columns(cols)
    summary = validate_ledger(mx, rows)
    if ledger_path.resolve() != ws.corroboration_csv.resolve():
        ws.corroboration_csv.write_bytes(ledger_path.read_bytes())
    summary["ledger_source"] = str(ledger_path)
    summary["ts_utc"] = utc_now_iso()
    write_json(ws.corroboration_summary, summary)
    n_pub = sum(1 for d in summary["divisions"].values() if d["publishable"])
    echo(f"[corroborate] {len(rows)} rows; {n_pub}/{len(summary['divisions'])} divisions fully corroborated; "
         f"{len(summary['problems'])} structural problems")
    if summary["problems"]:
        raise BocgError("ledger problems: " + "; ".join(summary["problems"][:10]))
    return summary
