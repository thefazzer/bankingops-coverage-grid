"""§3 encoding + commitment/keep-leaf/Merkle known-answer vectors; T1 hiding; signing; vault AEAD."""
import hashlib
import os
import struct

import pytest

from lat import crypto
from lat.encoding import DS_COMMIT, DS_KEEP, DS_NODE, canonical_json, concat, lp, u64


def H(b):
    return hashlib.sha256(b).digest()


def LP(b):
    return struct.pack(">I", len(b)) + b


def test_length_prefix_and_ints():
    assert lp(b"ab") == b"\x00\x00\x00\x02ab"
    assert lp(7) == b"\x00\x00\x00\x08" + b"\x00" * 7 + b"\x07"
    assert u64(1 << 40) == (1 << 40).to_bytes(8, "big")
    assert lp("é") == LP("é".encode("utf-8"))
    # NFC: decomposed e + combining acute normalises to precomposed
    assert lp("é") == lp("é")
    with pytest.raises(ValueError):
        u64(-1)


def test_commitment_vector_independent_implementation():
    doc_id = "ab" * 32
    nonce = bytes(range(32))
    expect = H(LP(b"LAT/commit/v1") + LP(doc_id.encode()) + LP((3).to_bytes(8, "big")) + LP((10).to_bytes(8, "big"))
               + LP((25).to_bytes(8, "big")) + LP(b"PERSON") + LP(b"Marta Kowalczyk") + LP(nonce))
    assert crypto.commitment(doc_id, 3, 10, 25, "PERSON", b"Marta Kowalczyk", nonce) == expect
    with pytest.raises(ValueError):
        crypto.commitment(doc_id, 3, 10, 25, "PERSON", b"x", b"short")


def test_keep_leaf_vector():
    doc_id = "cd" * 32
    expect = H(LP(b"LAT/keep/v1") + LP(doc_id.encode()) + LP((0).to_bytes(8, "big")) + LP((0).to_bytes(8, "big"))
               + LP((5).to_bytes(8, "big")) + LP(b"hello"))
    assert crypto.keep_leaf(doc_id, 0, 0, 5, b"hello") == expect


def test_merkle_vectors():
    a, b, c = H(b"a"), H(b"b"), H(b"c")
    node = lambda l, r: H(LP(b"LAT/node/v1") + LP(l) + LP(r))
    assert crypto.merkle_root([a]) == a
    assert crypto.merkle_root([a, b]) == node(a, b)
    # odd: duplicate last
    assert crypto.merkle_root([a, b, c]) == node(node(a, b), node(c, c))
    assert crypto.merkle_root([a, b, c, a]) == node(node(a, b), node(c, a))
    assert crypto.merkle_root([]) == node(b"", b"")
    # order matters
    assert crypto.merkle_root([a, b]) != crypto.merkle_root([b, a])


def test_domain_separation_distinguishes_keep_from_commit():
    # Same inputs but different DS tags never collide
    doc_id = "ef" * 32
    k = crypto.keep_leaf(doc_id, 0, 0, 3, b"abc")
    assert DS_COMMIT != DS_KEEP != DS_NODE
    assert k != H(concat(DS_COMMIT, doc_id, 0, 0, 3, b"abc"))


# ------------------------------------------------------------------------------- T1 hiding

def test_t1_commitments_share_no_structure():
    doc_id = "01" * 32
    c1 = crypto.commitment(doc_id, 0, 0, 5, "PERSON", b"Alice", os.urandom(32))
    c2 = crypto.commitment(doc_id, 0, 0, 5, "PERSON", b"Alicf", os.urandom(32))
    assert c1 != c2 and c1[:4] != c2[:4]
    hamming = sum(bin(x ^ y).count("1") for x, y in zip(c1, c2))
    assert 80 <= hamming <= 176  # ~128 expected of 256 bits


def test_t1_dictionary_attack_fails_without_nonce():
    doc_id = "02" * 32
    secret_nonce = os.urandom(32)
    target = crypto.commitment(doc_id, 4, 100, 115, "PERSON", b"Marta Kowalczyk", secret_nonce)
    candidates = [b"Marta Kowalczyk", b"Tobias Brenner", b"Ingrid Solheim", b"Ravi Natarajan"]
    # attacker knows all public fields and the true original is in the candidate list, but not the nonce
    for guess_nonce in (bytes(32), b"\xff" * 32, os.urandom(32)):
        assert all(crypto.commitment(doc_id, 4, 100, 115, "PERSON", c, guess_nonce) != target for c in candidates)
    # with the nonce the commitment opens to exactly one candidate
    opens = [c for c in candidates if crypto.commitment(doc_id, 4, 100, 115, "PERSON", c, secret_nonce) == target]
    assert opens == [b"Marta Kowalczyk"]


def test_t1_pseudonym_requires_key():
    k1, k2 = os.urandom(32), os.urandom(32)
    p1 = crypto.pseudonym_id(k1, "PERSON", "marta kowalczyk")
    assert p1 == crypto.pseudonym_id(k1, "PERSON", "marta kowalczyk")
    assert p1 != crypto.pseudonym_id(k2, "PERSON", "marta kowalczyk")
    assert p1 != crypto.pseudonym_id(k1, "CLIENT", "marta kowalczyk")
    assert len(p1) == 10 and p1.isalnum()


# ------------------------------------------------------------------------------- signing / AEAD

def test_ed25519_roundtrip(tmp_path):
    k = crypto.SigningKey.generate()
    f = tmp_path / "x.json"
    f.write_bytes(canonical_json({"a": 1}))
    sig = k.sign_file(f)
    assert sig.name == "x.json.sig"
    assert k.public().verify_file(f)
    f.write_bytes(canonical_json({"a": 2}))
    assert not k.public().verify_file(f)
    k.save(tmp_path / "k")
    assert crypto.SigningKey.load(tmp_path / "k").public().b64() == k.public().b64()
    assert not crypto.SigningKey.generate().public().verify_b64(b"x", k.sign_b64(b"x"))


def test_aead_vault_blob():
    key = os.urandom(32)
    blob = crypto.aead_encrypt(key, b"secret", aad=b"name")
    assert blob.startswith(crypto.VAULT_MAGIC)
    assert crypto.aead_decrypt(key, blob, aad=b"name") == b"secret"
    with pytest.raises(ValueError):
        crypto.aead_decrypt(os.urandom(32), blob, aad=b"name")
    with pytest.raises(ValueError):
        crypto.aead_decrypt(key, blob, aad=b"other")
    with pytest.raises(ValueError):
        crypto.aead_decrypt(key, blob[:-1] + bytes([blob[-1] ^ 1]), aad=b"name")


def test_holdout_commit_binds_items_and_nonce():
    items = [{"item_id": "H1", "task_text": "t", "answer": "a"}]
    n = os.urandom(32)
    c = crypto.holdout_commit(items, n)
    assert c == crypto.holdout_commit(items, n)
    assert c != crypto.holdout_commit([{"item_id": "H1", "task_text": "t", "answer": "b"}], n)
    assert c != crypto.holdout_commit(items, os.urandom(32))
