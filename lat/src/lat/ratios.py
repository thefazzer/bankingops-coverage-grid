"""SPEC-02 §5 — lineage ratios, recomputable from lineage.jsonl alone; canonical JSON bytes."""
from __future__ import annotations

from collections import Counter, defaultdict

from .classes import LINEAGE_CLASSES
from .encoding import canonical_json, utf8
from .lineage import canonical_content
from .models import Atom

TIER_FLOOR = 0.80


def _pct(counts: dict, total: int) -> dict:
    return {c: (round(counts.get(c, 0) / total, 6) if total else 0.0) for c in LINEAGE_CLASSES}


def compute_ratios(atoms: list[Atom], tier_floor: float = TIER_FLOOR) -> dict:
    by_atoms = Counter()
    by_bytes = Counter()
    per_ep_atoms: dict[str, Counter] = defaultdict(Counter)
    per_ep_n: Counter = Counter()
    for a in atoms:
        n = len(utf8(canonical_content(a.content)))
        by_atoms[a.lineage_class] += 1
        by_bytes[a.lineage_class] += n
        per_ep_atoms[a.episode_id][a.lineage_class] += 1
        per_ep_n[a.episode_id] += 1
    ta, tb = sum(by_atoms.values()), sum(by_bytes.values())
    per_episode = []
    for eid in sorted(per_ep_atoms):
        c, n = per_ep_atoms[eid], per_ep_n[eid]
        per_episode.append({"episode_id": eid, "n_atoms": n,
                            "pct_span_verified": round(c["SPAN_VERIFIED"] / n, 6),
                            "pct_pseud": round(c["PSEUDONYMISED_TRACEABLE"] / n, 6),
                            "pct_synth": round(c["SYNTHETIC_UNPROVABLE"] / n, 6)})
    verified_bytes = (by_bytes["SPAN_VERIFIED"] + by_bytes["PSEUDONYMISED_TRACEABLE"]) / tb if tb else 0.0
    return {
        "by_atoms": {**{c: by_atoms.get(c, 0) for c in LINEAGE_CLASSES}, "total": ta, "pct": _pct(by_atoms, ta)},
        "by_bytes": {**{c: by_bytes.get(c, 0) for c in LINEAGE_CLASSES}, "total": tb, "pct": _pct(by_bytes, tb)},
        "per_episode": per_episode,
        "tier_floor": tier_floor,
        "tier": "VERIFIED" if verified_bytes >= tier_floor else "MIXED",
    }


def ratios_bytes(atoms: list[Atom], tier_floor: float = TIER_FLOOR) -> bytes:
    return canonical_json(compute_ratios(atoms, tier_floor))
