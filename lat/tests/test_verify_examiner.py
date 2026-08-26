"""§6 examiner mode E1–E7: honest PASS; T3 CLASS_VIOLATION; pseudonym collision/inconsistency; E5 doc_id; sampling."""
import json
import os
from pathlib import Path

import pytest

from conftest import build_workspace
from lat.classes import Gazetteer
from lat.crypto import VerifyKey
from lat.models import Segmentation, VaultEntry
from lat.ner import Detection, RuleDetector
from lat.pkgio import Package
from lat.redact import make_token
from lat.verify import check_pseudonyms, examine


def _status(r, cid):
    return next(c["status"] for c in r["checks"] if c["id"] == cid)


def _ev(r, cid):
    return next(c["evidence"] for c in r["checks"] if c["id"] == cid)


def test_honest_examiner_full_and_sampled(honest, examiner_key, tmp_path):
    gaz = honest["ws"].gazetteer()
    r = examine(honest["pkg"], honest["vault"], sample=None, seed=1, gazetteer=gaz, examiner_key=examiner_key,
                out_dir=tmp_path, examiner_id="counsel-examiner")
    assert r["overall"] == "PASS", r["checks"]
    assert [c["id"] for c in r["checks"]] == ["E1", "E2", "E3", "E4", "E5", "E6", "E7"]
    e2 = _ev(r, "E2")
    assert e2["OPEN_OK"] == e2["population"] == e2["sample"] > 50 and e2["OPEN_FAIL"] == 0
    assert _ev(r, "E3")["CLASS_VIOLATION"] == 0 and _ev(r, "E5")["DOC_OK"] == honest["ws"].work.load_roots()["docs"].__len__()
    assert _ev(r, "E6")["counts"]["CRITICAL"] == 0
    # signed report + md with scoped wording, no general blessing
    rp = tmp_path / "report.json"
    assert VerifyKey.load(tmp_path / "examiner.pub").verify_file(rp)
    md = (tmp_path / "report.md").read_text()
    assert "OPEN_OK" in md and "residual scan:" in md and "origin: all sampled docs within" in md
    assert "Limits" in md and "not an opinion" in md
    for blessing in ("fully compliant", "safe to use", "guarantee", "certif"):
        assert blessing not in md.lower()
    assert r["statement"].startswith("On ") and f"seed 1" in r["statement"] and "package PKG1" in r["statement"]
    # seeded sample is deterministic
    r1 = examine(honest["pkg"], honest["vault"], sample=20, seed=42, gazetteer=gaz, examiner_key=examiner_key, out_dir=tmp_path / "a")
    r2 = examine(honest["pkg"], honest["vault"], sample=20, seed=42, gazetteer=gaz, examiner_key=examiner_key, out_dir=tmp_path / "b")
    assert _ev(r1, "E2")["sample"] == 20 and json.loads((tmp_path / "a" / "report.json").read_text())["sample"] == 20
    assert r1["statement"].split(":", 2)[2] == r2["statement"].split(":", 2)[2]


class MislabellingDetector:
    """T3: a seller detector that hides a substantive sentence under class DATE."""

    def __init__(self, inner):
        self.inner = inner

    def detect(self, text):
        dets = list(self.inner.detect(text))
        i = text.find("will settle")
        if i >= 0 and not any(d.start <= i < d.end for d in dets):
            dets.append(Detection(i, i + len("will settle"), "DATE", text[i:i + 11]))
        from lat.ner import resolve_overlaps
        return resolve_overlaps(dets)


def test_t3_class_mislabel_detected_by_examiner(tmp_path, examiner_key):
    from lat.fixtures import build_gazetteer
    det = MislabellingDetector(RuleDetector(build_gazetteer()))
    ws, vault, pkg = build_workspace(tmp_path / "t3", package_id="T3", detector=det)
    r = examine(pkg, vault, gazetteer=ws.gazetteer(), examiner_key=examiner_key, out_dir=tmp_path / "out")
    assert _status(r, "E2") == "PASS"                      # commitments open fine — the seller committed honestly
    assert _status(r, "E3") == "FAIL" and r["overall"] == "FAIL"
    v = _ev(r, "E3")["violations"]
    assert v and all(x["class"] == "DATE" for x in v)
    assert "CLASS_VIOLATION" in r["statement"] and f"{len(v)} CLASS_VIOLATION" in r["statement"]


def test_e2_open_fail_when_package_commit_tampered(honest, examiner_key, tmp_path, pkg_copy):
    seg_path = sorted((pkg_copy / "segmentation").glob("*.json"))[0]
    d = json.loads(seg_path.read_text())
    red = next(s for s in d["segments"] if s["kind"] == "REDACT")
    red["commit"] = os.urandom(32).hex()
    seg_path.write_text(json.dumps(d))
    r = examine(pkg_copy, honest["vault"], gazetteer=honest["ws"].gazetteer(), examiner_key=examiner_key, out_dir=tmp_path)
    assert _status(r, "E2") == "FAIL" and _ev(r, "E2")["OPEN_FAIL"] == 1
    assert _status(r, "E1") == "FAIL"   # V2 root mismatch too


def test_e5_doc_id_binding_when_original_swapped(honest, examiner_key, tmp_path, pkg_copy):
    """T2 examiner side: a doc whose reconstructed bytes do not hash to a manifest doc_id -> DOC_FAIL."""
    m = json.loads((pkg_copy / "manifest.json").read_text())
    roots = json.loads((pkg_copy / "roots.json").read_text())
    victim = next(iter(roots["docs"]))
    m["docs"] = [d for d in m["docs"] if d != victim]
    (pkg_copy / "manifest.json").write_text(json.dumps(m))
    r = examine(pkg_copy, honest["vault"], gazetteer=honest["ws"].gazetteer(), examiner_key=examiner_key, out_dir=tmp_path)
    e5 = _ev(r, "E5")
    assert _status(r, "E5") == "FAIL" and e5["failures"][0]["doc_id"] == victim and not e5["failures"][0]["in_manifest"]


def _seg(doc_id, entries, policy="shift_per_doc_v1"):
    from lat.models import Segment
    segs = [Segment(e.idx, e.start, e.end, "REDACT", e.cls, e.token, "00" * 32) for e in entries]
    return Segmentation(doc_id, segs, policy)


def test_e4_pseudonym_consistency_collision_and_inconsistency():
    k = os.urandom(32)
    from lat.classes import date_shift_days
    d1, d2 = "a1" * 32, "b2" * 32
    tok = lambda cls, s, d: make_token(cls, s, k, "shift_per_doc_v1", date_shift_days(k, d))

    def entry(idx, cls, s, d, token=None):
        return VaultEntry(idx, 0, 1, cls, s.encode(), os.urandom(32), token or tok(cls, s, d))

    # honest: same person in two docs -> same token; DATE per-doc shift differs and is fine
    e1 = [entry(0, "PERSON", "Marta Kowalczyk", d1), entry(1, "DATE", "2024-03-14", d1)]
    e2 = [entry(0, "PERSON", "marta kowalczyk", d2), entry(1, "DATE", "2024-03-14", d2)]
    assert e1[0].token == e2[0].token and e1[1].token != e2[1].token
    r = check_pseudonyms({d1: (_seg(d1, e1), e1), d2: (_seg(d2, e2), e2)}, k)
    assert r["ok"] and r["PSEUD_OK"] == 4
    # inconsistency: shipped token is not the HMAC-derived one
    bad = [entry(0, "PERSON", "Marta Kowalczyk", d1, token="⟦PERSON:AAAAAAAAAA⟧")]
    r = check_pseudonyms({d1: (_seg(d1, bad), bad)}, k)
    assert not r["ok"] and r["PSEUD_INCONSISTENT"] >= 1 and r["inconsistent"][0]["expected"] != "⟦PERSON:AAAAAAAAAA⟧"
    # collision: two originals -> one token (seller re-used a token)
    t = tok("PERSON", "Marta Kowalczyk", d1)
    col = [entry(0, "PERSON", "Marta Kowalczyk", d1, t), entry(1, "PERSON", "Tobias Brenner", d1, t)]
    r = check_pseudonyms({d1: (_seg(d1, col), col)}, k)
    assert not r["ok"] and r["PSEUD_COLLISION"] == 1
    # split: one original -> two tokens across docs
    sp1 = [entry(0, "PERSON", "Marta Kowalczyk", d1)]
    sp2 = [entry(0, "PERSON", "Marta Kowalczyk", d2, token="⟦PERSON:BBBBBBBBBB⟧")]
    r = check_pseudonyms({d1: (_seg(d1, sp1), sp1), d2: (_seg(d2, sp2), sp2)}, k)
    assert not r["ok"] and r["split"]


def test_e7_origin_out_of_scope(honest, examiner_key, tmp_path, pkg_copy):
    meta = json.loads((pkg_copy / "package.json").read_text())
    meta["declared_scope"] = {"institutions": ["INST-A"], "period_start": "2024-01-01", "period_end": "2024-06-30"}
    (pkg_copy / "package.json").write_text(json.dumps(meta))
    r = examine(pkg_copy, honest["vault"], gazetteer=honest["ws"].gazetteer(), examiner_key=examiner_key, out_dir=tmp_path)
    assert _status(r, "E7") == "FAIL" and all(x["institution_code"] == "INST-B" for x in _ev(r, "E7")["out_of_scope"])
    assert "sampled docs within ['INST-A']" in r["statement"] and not r["statement"].endswith("origin: all")
