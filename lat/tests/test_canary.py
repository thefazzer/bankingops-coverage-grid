"""C6 / T5: canary encode/apply/detect, >=3 carrier threshold, survives paraphrase-lite edits, registry."""
import json
import os
import random

import pytest

from lat import canary as C
from lat.crypto import SigningKey
from lat.lineage import content_hash


def _atoms(n=12):
    out = []
    for i in range(n):
        content = f"atom {i} says the break is a timing difference and will roll off ⟦COUNTERPARTY:ABCDEF{i:04d}⟧ soon"
        if i % 3 == 0:
            content = f"plain atom {i} with several words and no pseudonym token inside at all"
        out.append({"atom_id": f"ep/a{i:03d}", "content": content, "content_sha256": content_hash(content)})
    return out


def test_tag_encoding_roundtrip():
    for _ in range(50):
        t = os.urandom(4)
        assert C.decode_tag(C.encode_tag(t)) == t
    assert all(ch in C.INVISIBLE for ch in C.encode_tag(b"\xff\x00\xaa\x55"))


def test_apply_and_detect_both_methods():
    atoms = _atoms()
    c = C.new_canary("P", "recipient-x", atoms, "2024-01-01T00:00:00Z")
    assert {m for _, m in c.positions} == {"ZW_SEQ", "PSEUD_SUFFIX"}
    out = C.apply_canary(atoms, c)
    for a, b in zip(atoms, out):
        assert C.strip_carriers(b["content"]) == a["content"]        # invisible to verifiers
        assert content_hash(b["content"]) == a["content_sha256"]
        assert b["content"] != a["content"]
    text = "\n".join(json.dumps(b, ensure_ascii=False) for b in out)
    r = C.detect(text)
    assert r.detected and r.tag == c.tag.hex() and r.carriers_found == len(c.positions)
    assert r.methods["PSEUD_SUFFIX"] > 0 and r.methods["ZW_SEQ"] > 0
    # suffix carrier sits inside the token, before ⟧
    tok = next(b["content"] for b in out if "⟦" in b["content"])
    assert C.PSEUD_START in tok and tok.index(C.PSEUD_START) < tok.index("⟧")


def test_threshold_requires_three_carriers():
    atoms = _atoms(2)
    c = C.Canary("P", "r", os.urandom(16), [(atoms[0]["atom_id"], "ZW_SEQ"), (atoms[1]["atom_id"], "ZW_SEQ")])
    out = C.apply_canary(atoms, c)
    r = C.detect(" ".join(a["content"] for a in out))
    assert r.carriers_found == 2 and not r.detected
    c.positions.append((atoms[1]["atom_id"], "ZW_SEQ"))
    out = C.apply_canary(atoms, c)
    assert C.detect(" ".join(a["content"] for a in out)).detected


def test_survives_paraphrase_lite_edits_and_strip_defeats():
    atoms = _atoms(20)
    c = C.new_canary("P", "leaker", atoms, "")
    out = C.apply_canary(atoms, c)
    rng = random.Random(3)
    lines = [a["content"] for a in out]
    kept = [l for l in lines if rng.random() > 0.4]              # drop ~40 % of atoms
    edited = []
    for l in kept:
        words = l.split(" ")
        for _ in range(3):                                          # substitute / delete words
            i = rng.randrange(len(words))
            words[i] = rng.choice(["", "the", "soon", "later", words[i][::-1]])
        edited.append(" ".join(w for w in words if w))
    r = C.detect("\n".join(edited))
    assert r.detected and r.tag == c.tag.hex()
    # T5 counter-case: stripping every invisible code point removes the canary (detected by V5 on the package)
    assert not C.detect(C.strip_carriers("\n".join(edited))).detected


def test_registry_append_only_signed(tmp_path):
    reg = C.Registry(tmp_path / "registry.jsonl")
    key = SigningKey.generate()
    atoms = _atoms(4)
    l1 = reg.append(C.new_canary("P1", "a", atoms, ""), key)
    l2 = reg.append(C.new_canary("P1", "b", atoms, ""), key)
    assert l1["prev_hash"] == "0" * 64 and l2["prev_hash"] == C.Registry.line_hash(l1)
    assert reg.verify_chain(key.public()) == (True, [])
    assert reg.find("P1", "b")["entry"]["recipient_id"] == "b"
    assert reg.find_by_tag(l2["entry"]["tag"]).recipient_id == "b"
    with pytest.raises(ValueError):
        reg.append(C.new_canary("P1", "a", atoms, ""), key)          # duplicate
    # tampering with an earlier line breaks the chain and the signature
    lines = reg.path.read_text().splitlines()
    t = json.loads(lines[0])
    t["entry"]["recipient_id"] = "mallory"
    lines[0] = json.dumps(t, sort_keys=True)
    reg.path.write_text("\n".join(lines) + "\n")
    ok, problems = reg.verify_chain(key.public())
    assert not ok and any("signature" in p for p in problems) and any("chain" in p for p in problems)
    assert not C.verify_registry_line(t, key.public())


def test_detect_path_handles_json_escaped_carriers(tmp_path):
    atoms = _atoms(6)
    c = C.new_canary("P", "r", atoms, "")
    out = C.apply_canary(atoms, c)
    p = tmp_path / "escaped.jsonl"
    p.write_text("\n".join(json.dumps(a) for a in out))            # ensure_ascii=True -> ​ escapes
    r = C.detect_path(p)
    assert r.detected and r.tag == c.tag.hex()
