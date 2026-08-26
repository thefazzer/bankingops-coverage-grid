"""§6 buyer mode V1–V7 on an honest package, and FAIL on each tamper case (§10 T2, T4, T5, T6, vault leak)."""
import json
import os
import shutil
from pathlib import Path

from lat.canary import strip_carriers
from lat.lineage import read_jsonl, write_jsonl
from lat.ratios import compute_ratios
from lat.verify import verify_buyer


def _status(result, cid):
    return next(c["status"] for c in result["checks"] if c["id"] == cid)


def _run(pkg, out=None):
    return verify_buyer(pkg, out)


def test_honest_package_passes_all(honest, tmp_path):
    r = _run(honest["pkg"], tmp_path / "vb.json")
    assert r["overall"] == "PASS", r
    assert [c["id"] for c in r["checks"]] == ["V1", "V2", "V3", "V4", "V5", "V6", "V7"]
    assert all(c["status"] == "PASS" for c in r["checks"])
    assert (tmp_path / "vb.json").exists()
    # §9 layout present
    for rel in ("manifest.json", "manifest.sha", "anchor_proof.ots", "roots.json", "roots.json.sig", "lineage.jsonl",
                "lineage.jsonl.sig", "episodes.jsonl", "ratios.json", "ratios.json.sig", "canary/registry_entry.json",
                "canary/registry_entry.sig", "holdout/commit.json", "pubkeys/seller.pub", "README-VERIFY.md",
                "package.json"):
        assert (honest["pkg"] / rel).exists(), rel
    assert (honest["pkg"] / "segmentation").is_dir() and (honest["pkg"] / "redacted").is_dir()


def test_t2_modify_kept_text_one_byte(pkg_copy):
    doc = sorted((pkg_copy / "redacted").glob("*.txt"))[0]
    data = bytearray(doc.read_bytes())
    i = data.index(b"the")
    data[i] = ord("T")
    doc.write_bytes(bytes(data))
    r = _run(pkg_copy)
    assert _status(r, "V2") == "FAIL" and r["overall"] == "FAIL"
    assert doc.stem in next(c for c in r["checks"] if c["id"] == "V2")["evidence"]["root_mismatches"]


def test_t2_swap_doc_not_in_manifest(pkg_copy):
    m = json.loads((pkg_copy / "manifest.json").read_text())
    m["docs"] = m["docs"][1:]
    (pkg_copy / "manifest.json").write_text(json.dumps(m))
    r = _run(pkg_copy)
    assert _status(r, "V1") == "FAIL"   # sha mismatch, merkle mismatch, and package doc not in manifest


def test_t4_inflate_span_verified_by_mislabelling(pkg_copy):
    """Relabel a synthetic atom as SPAN_VERIFIED/QUOTE with a bogus ref -> V3 substring/ref failure; V4 ratio mismatch."""
    atoms = read_jsonl(pkg_copy / "lineage.jsonl")
    synth = next(a for a in atoms if a["lineage_class"] == "SYNTHETIC_UNPROVABLE")
    ref_atom = next(a for a in atoms if a["lineage_class"] == "SPAN_VERIFIED")
    synth["lineage_class"], synth["derivation_op"] = "SPAN_VERIFIED", "QUOTE"
    synth["span_refs"] = ref_atom["span_refs"]
    write_jsonl(pkg_copy / "lineage.jsonl", atoms)
    r = _run(pkg_copy)
    v3 = next(c for c in r["checks"] if c["id"] == "V3")
    assert v3["status"] == "FAIL" and not v3["evidence"]["sig_ok"]
    assert any("substring" in p for probs in v3["evidence"]["atom_failures"].values() for p in probs)
    v4 = next(c for c in r["checks"] if c["id"] == "V4")
    assert v4["status"] == "FAIL" and not v4["evidence"]["byte_identical"]


def test_t4_ratios_file_edited(pkg_copy):
    r0 = json.loads((pkg_copy / "ratios.json").read_text())
    r0["by_bytes"]["pct"]["SPAN_VERIFIED"] = 0.99
    (pkg_copy / "ratios.json").write_text(json.dumps(r0, sort_keys=True, separators=(",", ":")))
    r = _run(pkg_copy)
    assert _status(r, "V4") == "FAIL"


def test_t5_strip_canary(pkg_copy):
    p = pkg_copy / "lineage.jsonl"
    p.write_text(strip_carriers(p.read_text(encoding="utf-8")), encoding="utf-8")
    r = _run(pkg_copy)
    v5 = next(c for c in r["checks"] if c["id"] == "V5")
    assert v5["status"] == "FAIL" and v5["evidence"]["carriers_found"] == 0
    assert _status(r, "V3") == "FAIL"  # signature no longer matches the stripped file


def test_t5_canary_for_wrong_recipient(pkg_copy):
    meta = json.loads((pkg_copy / "package.json").read_text())
    meta["recipient_id"] = "someone-else"
    (pkg_copy / "package.json").write_text(json.dumps(meta))
    r = _run(pkg_copy)
    v5 = next(c for c in r["checks"] if c["id"] == "V5")
    assert v5["status"] == "FAIL" and not v5["evidence"]["identity_matches_package"]


def test_t6_holdout_missing_or_leaked(pkg_copy):
    c = json.loads((pkg_copy / "holdout" / "commit.json").read_text())
    (pkg_copy / "episodes.jsonl").write_text(
        (pkg_copy / "episodes.jsonl").read_text() + json.dumps({"episode_id": "leak", "task_id": c["item_ids"][0],
                                                                "atoms": [], "task_text": "x"}) + "\n")
    r = _run(pkg_copy)
    assert _status(r, "V6") == "FAIL"
    shutil.rmtree(pkg_copy / "holdout")
    r = _run(pkg_copy)
    assert _status(r, "V6") == "FAIL"


def test_v7_vault_material_in_package(pkg_copy, honest):
    # 1. an encrypted vault blob copied in
    src = next((honest["root"] / "vault").glob("*.json.enc"))
    shutil.copy(src, pkg_copy / "segmentation" / "extra.json.enc")
    r = _run(pkg_copy)
    v7 = next(c for c in r["checks"] if c["id"] == "V7")
    assert v7["status"] == "FAIL" and any("magic" in f or "filename" in f for f in v7["evidence"]["findings"])
    (pkg_copy / "segmentation" / "extra.json.enc").unlink()
    assert _status(_run(pkg_copy), "V7") == "PASS"
    # 2. a nonce smuggled into a JSON file as an unknown 64-hex string
    seg = sorted((pkg_copy / "segmentation").glob("*.json"))[0]
    d = json.loads(seg.read_text())
    d["note"] = os.urandom(32).hex()
    seg.write_text(json.dumps(d))
    r = _run(pkg_copy)
    v7 = next(c for c in r["checks"] if c["id"] == "V7")
    assert v7["status"] == "FAIL" and any("64-hex" in f for f in v7["evidence"]["findings"])
    # 3. suspicious JSON key
    seg.write_text(json.dumps(dict(d, note=None, nonce="x")))
    v7 = next(c for c in _run(pkg_copy)["checks"] if c["id"] == "V7")
    assert v7["status"] == "FAIL" and any("JSON keys" in f for f in v7["evidence"]["findings"])


def test_v2_signature_forgery(pkg_copy):
    from lat.crypto import SigningKey
    k = SigningKey.generate()
    roots = json.loads((pkg_copy / "roots.json").read_text())
    (pkg_copy / "roots.json").write_text(json.dumps(roots, indent=1))
    k.sign_file(pkg_copy / "roots.json")   # signed by the wrong key
    r = _run(pkg_copy)
    v2 = next(c for c in r["checks"] if c["id"] == "V2")
    assert v2["status"] == "FAIL" and not v2["evidence"]["sig_ok"]
