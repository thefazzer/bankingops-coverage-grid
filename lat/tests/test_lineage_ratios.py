"""C3/C4: lineage classes, substring checks, ratios recompute (§5), mode boundary (§1, G7)."""
import json
import os

import pytest

from lat.classes import Gazetteer, OP_TO_LINEAGE
from lat.encoding import canonical_json
from lat.lineage import (LineageBuildError, ViewCache, build_lineage, check_atom, check_lineage, check_modes,
                         content_hash, load_atoms)
from lat.models import Atom, SourceDoc, SpanRef
from lat.ner import RuleDetector
from lat.ratios import compute_ratios, ratios_bytes
from lat.redact import WorkDir, redact_corpus
from lat.vault import NonceVault

TEXT = ("Marta Kowalczyk confirmed that Norvale Capital will settle the trade on 2024-03-14.\n"
        "Please confirm the booking once the reconciliation break has been cleared.\n"
        "The break is a timing difference and will roll off at the next batch.\n")


@pytest.fixture
def built(tmp_path):
    gaz = Gazetteer(counterparties={"Norvale Capital"}, persons={"Marta Kowalczyk"})
    v = NonceVault(tmp_path / "v", os.urandom(32))
    v.init()
    doc = SourceDoc.from_text(TEXT, name="d.txt")
    work = WorkDir(tmp_path / "work")
    redact_corpus([doc], RuleDetector(gaz), v, work)
    return doc, work, v


def test_op_to_class_mapping():
    assert OP_TO_LINEAGE == {"QUOTE": "SPAN_VERIFIED", "PSEUDONYMISE": "PSEUDONYMISED_TRACEABLE",
                             "PARAPHRASE": "SYNTHETIC_UNPROVABLE", "SYNTHESISE": "SYNTHETIC_UNPROVABLE"}


def test_build_lineage_and_checks(built):
    doc, work, v = built
    l1 = TEXT.index("Please")
    l1e = TEXT.index("\n", l1)
    spec = {"episodes": [{"episode_id": "ep-1", "task_id": "t", "task_text": "task", "atoms": [
        {"op": "QUOTE", "doc": "d.txt", "start": l1, "end": l1e},
        {"op": "PSEUDONYMISE", "doc": "d.txt", "start": 0, "end": TEXT.index("\n")},
        {"op": "PARAPHRASE", "content": "Someone confirmed settlement."},
        {"op": "SYNTHESISE", "content": "Synthetic advice."},
    ]}]}
    atoms, episodes = build_lineage(spec, [doc], work, work.load_roots())
    assert [a.lineage_class for a in atoms] == ["SPAN_VERIFIED", "PSEUDONYMISED_TRACEABLE", "SYNTHETIC_UNPROVABLE",
                                                "SYNTHETIC_UNPROVABLE"]
    assert atoms[0].content == TEXT[l1:l1e]
    assert "⟦PERSON:" in atoms[1].content and "⟦COUNTERPARTY:" in atoms[1].content and "Marta" not in atoms[1].content
    assert all(r.doc_id == doc.doc_id for r in atoms[1].span_refs) and len(atoms[1].span_refs) >= 4
    assert atoms[2].span_refs == []
    assert episodes[0].atoms == [a.atom_id for a in atoms]
    assert episodes[0].lineage_summary["by_atoms"]["SPAN_VERIFIED"] == 1
    r = check_lineage(atoms, episodes, work)
    assert r["ok"], r
    # QUOTE over a REDACT segment is refused (would leak the original)
    bad = {"episodes": [{"episode_id": "e", "atoms": [{"op": "QUOTE", "doc": "d.txt", "start": 0, "end": 20}]}]}
    with pytest.raises(LineageBuildError):
        build_lineage(bad, [doc], work, work.load_roots())


def test_check_atom_detects_inflation(built):
    """T4: a synthetic atom relabelled SPAN_VERIFIED / QUOTE fails the substring + class checks."""
    doc, work, v = built
    cache = ViewCache(work)
    view = cache.get(doc.doc_id)
    keep_idx = next(i for i, s in enumerate(view.seg.segments) if s.kind == "KEEP")
    ref = SpanRef(doc.doc_id, keep_idx, view.leaves[keep_idx].hex())
    good = Atom("a", "e", view.chunks[keep_idx].decode()[:10], "QUOTE", "SPAN_VERIFIED", [ref], "g",
                content_hash(view.chunks[keep_idx].decode()[:10]))
    assert check_atom(good, cache) == []
    # class inconsistent with op
    a = Atom("a", "e", "x", "PARAPHRASE", "SPAN_VERIFIED", [ref], "g", content_hash("x"))
    assert any("inconsistent" in p for p in check_atom(a, cache))
    # content not substring of referenced KEEP
    a = Atom("a", "e", "not in the document at all", "QUOTE", "SPAN_VERIFIED", [ref], "g",
             content_hash("not in the document at all"))
    assert any("substring" in p for p in check_atom(a, cache))
    # bad leaf reference
    a = Atom("a", "e", "x", "QUOTE", "SPAN_VERIFIED", [SpanRef(doc.doc_id, keep_idx, "00" * 32)], "g", content_hash("x"))
    assert any("leaf_or_commit" in p for p in check_atom(a, cache))
    # SPAN_VERIFIED referencing a REDACT segment
    red_idx = next(i for i, s in enumerate(view.seg.segments) if s.kind == "REDACT")
    a = Atom("a", "e", "x", "QUOTE", "SPAN_VERIFIED", [SpanRef(doc.doc_id, red_idx, view.leaves[red_idx].hex())], "g",
             content_hash("x"))
    assert any("REDACT" in p for p in check_atom(a, cache))
    # content hash mismatch
    a = Atom("a", "e", "x", "PARAPHRASE", "SYNTHETIC_UNPROVABLE", [], "g", "00" * 32)
    assert check_atom(a, cache) == ["content_sha256 mismatch"]


def test_ratios_recompute_canonical_and_tier():
    def atom(i, op, content):
        return Atom(f"a{i}", "ep-a" if i % 2 else "ep-b", content, op, OP_TO_LINEAGE[op], [], "g", content_hash(content))
    atoms = [atom(0, "QUOTE", "x" * 50), atom(1, "PSEUDONYMISE", "y" * 40), atom(2, "PARAPHRASE", "z" * 10),
             atom(3, "SYNTHESISE", "w" * 5)]
    r = compute_ratios(atoms)
    assert r["by_atoms"]["total"] == 4 and r["by_bytes"]["total"] == 105
    assert r["by_bytes"]["pct"]["SPAN_VERIFIED"] == round(50 / 105, 6)
    assert r["tier"] == "VERIFIED"
    assert compute_ratios(atoms, tier_floor=0.9)["tier"] == "MIXED"
    assert [e["episode_id"] for e in r["per_episode"]] == ["ep-a", "ep-b"]
    b = ratios_bytes(atoms)
    assert b == canonical_json(json.loads(b)) and b"\n" not in b and b" " not in b
    # carriers do not affect byte counts
    atoms2 = [Atom(a.atom_id, a.episode_id, a.content[:2] + "​⁢" + a.content[2:], a.derivation_op,
                   a.lineage_class, [], "g", a.content_sha256) for a in atoms]
    assert ratios_bytes(atoms2) == b


def test_mode_gate():
    roots = {"docs": {"d1": {"mode": "PSEUDONYMISE"}, "d2": {"mode": "SYNTHESISE"}}}
    ok = [Atom("a", "e", "x", "SYNTHESISE", "SYNTHETIC_UNPROVABLE", [], "g", content_hash("x"))]
    assert check_modes(ok, roots) == []
    bad = [Atom("a", "e", "x", "PARAPHRASE", "SPAN_VERIFIED", [], "g", content_hash("x"))]
    assert check_modes(bad, roots)
    mixed = [Atom("a", "e", "x", "QUOTE", "SPAN_VERIFIED", [SpanRef("d2", 0, "00")], "g", content_hash("x"))]
    assert any("SYNTHESISE-mode" in p for p in check_modes(mixed, roots))
