"""§8 gates G1–G9 and §7 residual scan."""
import json
import os
import shutil

import pytest

from conftest import build_workspace
from lat.classes import Gazetteer
from lat.gates import GateContext, run_gates
from lat.models import SourceDoc
from lat.ner import RuleDetector, StaticDetector
from lat.package import PackageBuildError, build_package
from lat.pkgio import Package
from lat.redact import WorkDir, redact_corpus
from lat.residual import scan
from lat.vault import NonceVault


def _ctx(h):
    ws = h["ws"]
    return GateContext(vault=h["vault"], source_docs=ws.docs(), registry=ws.registry, audit_log=ws.audit_log(),
                       gazetteer=ws.gazetteer(), detector=ws.detector())


def _g(report, gid):
    return next(g for g in report["gates"] if g["id"] == gid)


def test_gates_pass_on_honest_package(honest, pkg_copy):
    r = run_gates(pkg_copy, _ctx(honest), write=True)
    assert r["overall"] == "PASS", [(g["id"], g["evidence"]) for g in r["gates"] if g["status"] != "PASS"]
    assert [g["id"] for g in r["gates"]] == [f"G{i}" for i in range(1, 10)]
    rep = json.loads((pkg_copy / "gates_report.json").read_text())
    assert rep["overall"] == "PASS" and _g(rep, "G8")["evidence"]["docs_rerun"] > 0


def test_g2_refuses_unsalted_package(tmp_path):
    ws, vault, _ = build_workspace(tmp_path / "w", n_docs=4, register_canary=False, build_pkg=False)
    with pytest.raises(PackageBuildError, match="G2"):
        build_package(ws, "X", "nobody", vault, run_gate_checks=False)
    # registered for one recipient does not license another
    from lat import canary as C
    from lat.lineage import read_jsonl
    from lat.manifest import utc_now
    ws.registry.append(C.new_canary("X", "alice", read_jsonl(ws.work.path / "lineage.jsonl"), utc_now()), vault.signing_key)
    with pytest.raises(PackageBuildError):
        build_package(ws, "X", "bob", vault, run_gate_checks=False)
    pkg, rep = build_package(ws, "X", "alice", vault, run_gate_checks=True)
    assert rep["overall"] == "PASS" and _g(rep, "G2")["status"] == "PASS"
    assert json.loads((pkg / "package.json").read_text())["gates_overall"] == "PASS"


def test_g2_unregistered_recipient_in_package(honest, pkg_copy):
    meta = json.loads((pkg_copy / "package.json").read_text())
    meta["recipient_id"] = "mallory"
    (pkg_copy / "package.json").write_text(json.dumps(meta))
    r = run_gates(pkg_copy, _ctx(honest), write=False, only=["G2"])
    assert _g(r, "G2")["status"] == "FAIL"


def test_g4_class_floor(honest, pkg_copy):
    meta = json.loads((pkg_copy / "package.json").read_text())
    meta["marketed_tier"], meta["tier_label"] = "VERIFIED", "MIXED"
    (pkg_copy / "package.json").write_text(json.dumps(meta))
    r = run_gates(pkg_copy, _ctx(honest), write=False, only=["G4"])
    assert _g(r, "G4")["status"] == "FAIL"
    meta["marketed_tier"] = "MIXED"
    (pkg_copy / "package.json").write_text(json.dumps(meta))
    assert _g(run_gates(pkg_copy, _ctx(honest), write=False, only=["G4"]), "G4")["status"] == "PASS"


def test_g7_mode_gate(honest, pkg_copy):
    from lat.lineage import read_jsonl, write_jsonl
    atoms = read_jsonl(pkg_copy / "lineage.jsonl")
    a = next(x for x in atoms if x["derivation_op"] == "PARAPHRASE")
    a["lineage_class"] = "SPAN_VERIFIED"
    write_jsonl(pkg_copy / "lineage.jsonl", atoms)
    r = run_gates(pkg_copy, _ctx(honest), write=False, only=["G7"])
    assert _g(r, "G7")["status"] == "FAIL"


def test_g8_determinism_gate_detects_drift(honest, pkg_copy):
    ctx = _ctx(honest)
    assert _g(run_gates(pkg_copy, ctx, write=False, only=["G8"]), "G8")["status"] == "PASS"
    # a different detector configuration (amounts redacted) would not reproduce the package
    ctx.detector = RuleDetector(honest["ws"].gazetteer(), redact_amounts=True)
    assert _g(run_gates(pkg_copy, ctx, write=False, only=["G8"]), "G8")["status"] == "FAIL"
    # and so would a different vault
    ctx.detector = honest["ws"].detector()
    other = NonceVault(pkg_copy.parent / "othervault", os.urandom(32))
    other.init()
    ctx.vault = other
    assert _g(run_gates(pkg_copy, ctx, write=False, only=["G8"]), "G8")["status"] == "FAIL"


def test_g9_holdout_before_external_review(honest, pkg_copy):
    ctx = _ctx(honest)
    assert _g(run_gates(pkg_copy, ctx, write=False, only=["G9"]), "G9")["status"] == "PASS"
    ctx.audit_log = [{"event": "external_review", "ts": "2020-01-01T00:00:00Z"}]
    assert _g(run_gates(pkg_copy, ctx, write=False, only=["G9"]), "G9")["status"] == "FAIL"
    ctx.audit_log = None
    assert _g(run_gates(pkg_copy, ctx, write=False, only=["G9"]), "G9")["status"] == "FAIL"


def test_g1_leakage_gate(honest, pkg_copy):
    ctx = _ctx(honest)
    eps = (pkg_copy / "episodes.jsonl").read_text().splitlines()
    e = json.loads(eps[0])
    items = ctx.vault.load_holdout(Package(pkg_copy).holdout_commit()["holdout_id"])["items"]
    e["task_text"] = items[0]["task_text"]
    eps[0] = json.dumps(e)
    (pkg_copy / "episodes.jsonl").write_text("\n".join(eps) + "\n")
    r = run_gates(pkg_copy, ctx, write=False, only=["G1", "G5"])
    assert _g(r, "G1")["status"] == "FAIL" and _g(r, "G1")["evidence"]["near_dups"]
    assert _g(r, "G5")["status"] == "FAIL"  # R5 CRITICAL
    # shared source doc id
    ctx.holdout_items = [dict(items[0], source_doc_ids=[next(iter(Package(pkg_copy).load_roots()["docs"]))])]
    assert _g(run_gates(pkg_copy, ctx, write=False, only=["G1"]), "G1")["evidence"]["shared_doc_ids"]


def test_residual_scan_flags_leaks(tmp_path):
    """A weak seller detector leaves an e-mail (R2 CRITICAL) and a person name (R1 HIGH) in kept text."""
    text = ("Please reach Marta Kowalczyk at marta.k@examplebank.test about ⟦COUNTERPARTY:X⟧.\n"
            "The break is a timing difference and will roll off at the next batch.\n")
    gaz = Gazetteer(counterparties={"Norvale Capital"}, persons={"Marta Kowalczyk"})
    v = NonceVault(tmp_path / "v", os.urandom(32))
    v.init()
    work = WorkDir(tmp_path / "work")
    redact_corpus([SourceDoc.from_text(text, name="d.txt")], StaticDetector([]), v, work)   # nothing redacted
    rs = scan(work, gaz, RuleDetector(gaz))
    rules = {(f.rule, f.severity) for f in rs.findings}
    assert ("R2", "CRITICAL") in rules and ("R1", "HIGH") in rules
    ok, reasons = rs.gate()
    assert not ok and any("CRITICAL" in r for r in reasons)
    d = rs.to_dict()
    assert d["gate"]["pass"] is False and "not proof" in d["disclaimer"]
    # after proper redaction the same text is clean
    work2 = WorkDir(tmp_path / "work2")
    redact_corpus([SourceDoc.from_text(text, name="d.txt")], RuleDetector(gaz), v, work2)
    rs2 = scan(work2, gaz, RuleDetector(gaz))
    assert rs2.counts["CRITICAL"] == 0 and rs2.counts["HIGH"] == 0 and rs2.gate()[0]


def test_residual_r4_and_r3(tmp_path):
    gaz = Gazetteer(products={"FX forward"}, venues={"Ceres OTC"}, allowlist={"Trade Support"})
    v = NonceVault(tmp_path / "v", os.urandom(32))
    v.init()
    work = WorkDir(tmp_path / "work")
    docs = [SourceDoc.from_text("the FX forward with ⟦COUNTERPARTY:ABC⟧ was executed on Ceres OTC with Falconer desk on "
                                "⟦DATE:2024-03-01⟧ for USD 12,500.00.\n", name="a.txt")]
    redact_corpus(docs, StaticDetector([]), v, work)
    rs = scan(work, gaz, StaticDetector([]))
    rules = {f.rule for f in rs.findings}
    assert "R4" in rules and "R3" in rules
    r4 = next(f for f in rs.findings if f.rule == "R4")
    assert "Falconer" in r4.detail or "Ceres" in r4.detail


@pytest.mark.parametrize("seed", [2, 3, 4])
def test_fixture_corpora_redact_clean_across_seeds(tmp_path, seed):
    """Property: the default detector + fixture gazetteer leaves no CRITICAL/HIGH residuals on synthetic corpora."""
    from lat.fixtures import generate
    from lat.workspace import Workspace
    generate(tmp_path, n_docs=9, seed=seed)
    ws = Workspace(tmp_path)
    v = NonceVault(tmp_path / "v", os.urandom(32))
    v.init()
    redact_corpus(ws.docs(), ws.detector(), v, ws.work)
    rs = scan(ws.work, ws.gazetteer(), ws.detector())
    assert rs.counts["CRITICAL"] == 0 and rs.counts["HIGH"] == 0, [f.detail for f in rs.findings if f.severity != "MEDIUM"]
    for doc in ws.docs():   # no raw identifiers survive
        red = ws.work.load_redacted(doc.doc_id).decode()
        assert "@" not in red and "TRD-" not in red and "ACC-" not in red
