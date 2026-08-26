"""SPEC-02 §2 Holdout / C7 / T6 — sealed holdout commit / reveal / verify, plus MinHash sketches
used for near-duplicate checks (R5, V6, G1) without shipping the items."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable, Optional

import regex as re
from datasketch import MinHash

from .crypto import holdout_commit
from .encoding import pretty_json
from .manifest import utc_now

NUM_PERM = 64
NEAR_DUP_THRESHOLD = 0.8


def shingles(text: str, k: int = 3) -> set[str]:
    words = re.findall(r"\w+", text.casefold())
    if len(words) < k:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i:i + k]) for i in range(len(words) - k + 1)}


def minhash(text: str, num_perm: int = NUM_PERM) -> MinHash:
    m = MinHash(num_perm=num_perm, seed=1)
    for s in shingles(text):
        m.update(s.encode("utf-8"))
    return m


def sketch_values(text: str, num_perm: int = NUM_PERM) -> list[int]:
    return [int(x) for x in minhash(text, num_perm).hashvalues]


def minhash_from_values(vals: list[int]) -> MinHash:
    import numpy as np
    m = MinHash(num_perm=len(vals), seed=1)
    m.hashvalues = np.array(vals, dtype=np.uint64)
    return m


def jaccard_est(a: MinHash, b: MinHash) -> float:
    return float(a.jaccard(b))


def committed_payload(items: list[dict]) -> list[dict]:
    """items+answers, canonical ordering by item_id."""
    return sorted(({"item_id": i["item_id"], "task_text": i.get("task_text", ""), "answer": i.get("answer", ""),
                    "source_doc_ids": sorted(i.get("source_doc_ids", []))} for i in items), key=lambda x: x["item_id"])


def make_commit(holdout_id: str, items: list[dict], nonce_h: Optional[bytes] = None,
                created_utc: Optional[str] = None) -> tuple[dict, dict]:
    """Returns (public commit.json object, secret reveal object)."""
    nonce_h = nonce_h or os.urandom(32)
    payload = committed_payload(items)
    c = holdout_commit(payload, nonce_h).hex()
    public = {"holdout_id": holdout_id, "items_commit": c, "created_utc": created_utc or utc_now(), "anchor": None,
              "n_items": len(payload), "item_ids": [i["item_id"] for i in payload],
              "task_minhash": {"num_perm": NUM_PERM, "sketches": [sketch_values(i["task_text"]) for i in payload]}}
    secret = {"holdout_id": holdout_id, "nonce_h": nonce_h.hex(), "items": payload, "items_commit": c}
    return public, secret


def verify_reveal(commit: dict, reveal: dict) -> tuple[bool, str]:
    try:
        payload = committed_payload(reveal["items"])
        c = holdout_commit(payload, bytes.fromhex(reveal["nonce_h"])).hex()
    except Exception as e:
        return False, f"malformed reveal: {e}"
    if c != commit.get("items_commit"):
        return False, "items_commit mismatch: revealed items+answers+nonce do not open the commitment"
    if commit.get("holdout_id") != reveal.get("holdout_id"):
        return False, "holdout_id mismatch"
    return True, "commitment opens to revealed items"


def write_commit(public: dict, directory: str | Path) -> Path:
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    p = d / "commit.json"
    p.write_text(pretty_json(public), encoding="utf-8")
    return p


def load_commit(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def near_dups_against_sketches(texts: Iterable[tuple[str, str]], commit: dict,
                               threshold: float = NEAR_DUP_THRESHOLD) -> list[dict]:
    """texts = [(label, text)]; compare against holdout sketches in commit.json."""
    sk = commit.get("task_minhash") or {}
    sketches = [minhash_from_values(v) for v in sk.get("sketches", [])]
    ids = commit.get("item_ids", [])
    hits = []
    for label, text in texts:
        if not text.strip():
            continue
        m = minhash(text, sk.get("num_perm", NUM_PERM))
        for i, s in enumerate(sketches):
            j = jaccard_est(m, s)
            if j >= threshold:
                hits.append({"label": label, "item_id": ids[i] if i < len(ids) else i, "jaccard": round(j, 3)})
    return hits


def near_dups_against_items(texts: Iterable[tuple[str, str]], items: list[dict],
                            threshold: float = NEAR_DUP_THRESHOLD) -> list[dict]:
    sk = [(i["item_id"], minhash(i.get("task_text", ""))) for i in items]
    hits = []
    for label, text in texts:
        if not text.strip():
            continue
        m = minhash(text)
        for iid, s in sk:
            j = jaccard_est(m, s)
            if j >= threshold:
                hits.append({"label": label, "item_id": iid, "jaccard": round(j, 3)})
    return hits
