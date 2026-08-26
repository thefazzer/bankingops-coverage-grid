"""`bocg normalise`: validate every run, recompute admission (I9), canonicalise names (§5.1), apply aliases (§5.2)."""
from __future__ import annotations

import shutil
from pathlib import Path

from .aliases import AliasTable, draft_identity_table, load_aliases, write_aliases
from .canon import canon_name
from .run import load_runs
from .util import BocgError, Workspace, read_json, sha256_file, sha256_text, write_json
from .validate import admission, assess

NORMALISED_VERSION = "bocg.normalised.v1"


def _threshold(ws: Workspace) -> float:
    meta = read_json(ws.run_meta)
    return float(meta["panel"]["params"]["threshold_usd"])


def normalise_runs(ws: Workspace, aliases_path: Path | None = None, echo=print) -> dict:
    meta = read_json(ws.run_meta)
    threshold = _threshold(ws)
    runs = load_runs(ws, meta["prompt_sha8"])

    samples = []
    canon_set: dict[str, list[str]] = {}
    for rec in runs:
        s = {"model_id": rec["model_id"], "model_dir": rec["_model_dir"], "vendor": rec.get("vendor"),
             "provider": rec.get("provider"), "sample_idx": rec["sample_idx"], "path": rec["_path"],
             "response_sha256": rec["response_sha256"], "run_status": rec["status"],
             "status": "INVALID", "invalid_reasons": [], "order_check": None, "self_assess": [],
             "divisions": [], "rejected": [], "admission_diffs": []}
        if rec["status"] == "ERROR":
            s["invalid_reasons"] = ["RUN_ERROR"]
            samples.append(s)
            continue
        raw = rec["response_raw"]
        if sha256_text(raw) != rec["response_sha256"]:
            s["invalid_reasons"] = ["SHA_MISMATCH"]
            samples.append(s)
            continue
        a = assess(raw)
        s["order_check"] = a.order
        s["self_assess"] = a.self_assess
        if not a.valid:
            s["invalid_reasons"] = a.invalid_reasons()
            samples.append(s)
            continue
        s["status"] = "VALID"
        obj = a.obj
        for i, div in enumerate(obj["divisions"]):
            adm = admission(div, threshold)
            c = canon_name(div["name"])
            canon_set.setdefault(c, [])
            if div["name"] not in canon_set[c]:
                canon_set[c].append(div["name"])
            d = {"index": i, "name": div["name"], "canon": c, "division_key": None,
                 "model_placement": "divisions", "server_admitted": adm.admitted, "admission": adm.to_dict(),
                 "axis": div["axis"], "confidence": div.get("confidence"),
                 "a1_regulatory": div.get("a1_regulatory"), "a2_segment": div.get("a2_segment"),
                 "a3_market_size": div.get("a3_market_size"), "a4_seat": div["a4_seat"]}
            if not adm.admitted:
                s["admission_diffs"].append({"name": div["name"], "model_placement": "divisions",
                                             "server_placement": "rejected", "reasons": adm.reasons,
                                             "arith_mismatch": adm.arith_mismatch})
            elif adm.arith_mismatch:
                s["admission_diffs"].append({"name": div["name"], "model_placement": "divisions",
                                             "server_placement": "divisions", "reasons": ["ARITH_MISMATCH"],
                                             "arith_mismatch": True})
            s["divisions"].append(d)
        for r in obj["rejected"]:
            s["rejected"].append({"name": r["name"], "canon": canon_name(r["name"]),
                                  "reason_codes": r["reason_codes"], "note": r.get("note", "")})
        samples.append(s)

    # alias table: provided -> copy into workspace; else existing workspace table; else auto-draft identity
    admitted_canons = sorted({d["canon"] for s in samples for d in s["divisions"] if d["server_admitted"]})
    if aliases_path is not None:
        table = load_aliases(Path(aliases_path))
        if Path(aliases_path).resolve() != ws.aliases_yaml.resolve():
            shutil.copyfile(aliases_path, ws.aliases_yaml)
    elif ws.aliases_yaml.exists():
        table = load_aliases(ws.aliases_yaml)
    else:
        echo("[normalise] no aliases.yaml given: writing AUTO-DRAFT identity table (review before publication)")
        table = draft_identity_table(admitted_canons, meta["prompt_sha8"])
        write_aliases(ws.aliases_yaml, table)
    aliases_sha = sha256_file(ws.aliases_yaml)
    ws.aliases_sha256.write_text(aliases_sha + "  aliases.yaml\n", encoding="utf-8")

    unaliased = []
    for s in samples:
        for d in s["divisions"]:
            k = table.key_for(d["name"])
            d["division_key"] = k
            if d["server_admitted"] and k is None and d["canon"] not in unaliased:
                unaliased.append(d["canon"])
    if unaliased:
        echo(f"[normalise] WARNING {len(unaliased)} admitted canon name(s) have no alias and will be excluded "
             f"from the matrix: {unaliased}")

    out = {"schema_version": NORMALISED_VERSION, "prompt_sha8": meta["prompt_sha8"],
           "prompt_sha256": meta["prompt_sha256"], "threshold_usd": threshold,
           "aliases_sha256": aliases_sha, "unaliased_canons": unaliased,
           "samples": samples}
    write_json(ws.normalised_json, out)
    write_json(ws.canon_names_json, {"prompt_sha8": meta["prompt_sha8"],
                                     "canon_names": {c: sorted(v) for c, v in sorted(canon_set.items())},
                                     "admitted_canons": admitted_canons})
    n_valid = sum(s["status"] == "VALID" for s in samples)
    echo(f"[normalise] {len(samples)} samples, {n_valid} VALID, {len(canon_set)} distinct canon names, "
         f"aliases sha={aliases_sha[:8]}")
    return out
