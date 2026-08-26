"""§2/§4 redaction: segmentation partition, tokens, DATE/AMOUNT policies, vault, determinism (G8), rebuild."""
import os

import pytest

from lat.classes import Gazetteer, amount_band, class_predicate, date_shift_days, parse_date
from lat.crypto import commitment
from lat.encoding import sha256_hex
from lat.models import KEEP, MODE_SYNTHESISE, REDACT, SourceDoc
from lat.ner import Detection, RuleDetector, StaticDetector
from lat.redact import (RebuildError, WorkDir, rebuild_root, reconstruct_original, redact_corpus, redact_doc,
                        rebuild_leaves)
from lat.vault import NonceVault

TEXT = ("Marta Kowalczyk confirmed that Norvale Capital will settle TRD-2024-11223 on 2024-03-14.\n"
        "Please reach marta.k@examplebank.test or +000 123 4567 890 before 2024-03-21.\n"
        "Norvale Capital sent USD 1,250,000.00 to account ACC-123456. Marta Kowalczyk agreed.\n")


@pytest.fixture
def gaz():
    return Gazetteer(counterparties={"Norvale Capital"}, persons={"Marta Kowalczyk"})


@pytest.fixture
def vault(tmp_path):
    v = NonceVault(tmp_path / "vault", os.urandom(32))
    v.init()
    return v


def test_segments_partition_and_tokens(gaz, vault):
    doc = SourceDoc.from_text(TEXT, name="t.txt")
    r = redact_doc(doc, RuleDetector(gaz), vault)
    seg = r.segmentation
    assert seg.check_partition(len(doc.data)) == []
    assert seg.segments[0].start == 0 and seg.segments[-1].end == len(doc.data)
    classes = {s.cls for s in seg.segments if s.kind == REDACT}
    assert {"PERSON", "COUNTERPARTY", "TRADE_ID", "DATE", "EMAIL", "PHONE", "ACCOUNT_ID"} <= classes
    # consistency: same entity -> same token, corpus-wide
    person_tokens = {s.token for s in seg.segments if s.cls == "PERSON"}
    cp_tokens = {s.token for s in seg.segments if s.cls == "COUNTERPARTY"}
    assert len(person_tokens) == 1 and len(cp_tokens) == 1
    assert next(iter(person_tokens)).startswith("⟦PERSON:") and next(iter(person_tokens)).endswith("⟧")
    # amounts kept by default (§4 policy)
    assert b"USD 1,250,000.00" in r.redacted
    assert b"Marta" not in r.redacted and b"Norvale" not in r.redacted
    # commitments recompute from vault entries
    for e in r.entries:
        s = seg.segments[e.idx]
        assert commitment(doc.doc_id, e.idx, e.start, e.end, e.cls, e.original, e.nonce).hex() == s.commit
    assert rebuild_root(doc.doc_id, seg, r.redacted) == r.root
    assert reconstruct_original(seg, r.redacted, r.entries) == doc.data
    assert sha256_hex(reconstruct_original(seg, r.redacted, r.entries)) == doc.doc_id


def test_date_shift_preserves_intervals_and_amount_banding(gaz, vault):
    doc = SourceDoc.from_text(TEXT, name="t.txt")
    r = redact_doc(doc, RuleDetector(gaz, redact_amounts=True), vault)
    dates = [s.token for s in r.segmentation.segments if s.cls == "DATE"]
    d1, d2 = (parse_date(t[len("⟦DATE:"):-1]) for t in dates)
    assert (d2 - d1).days == 7  # 2024-03-14 -> 2024-03-21 interval preserved
    shift = date_shift_days(vault.k_pseud, doc.doc_id)
    assert shift != 0 and -182 <= shift <= 182
    assert (d1 - parse_date("2024-03-14")).days == shift
    amt = [s.token for s in r.segmentation.segments if s.cls == "AMOUNT_EXACT"]
    assert amt == ["⟦AMOUNT:1m-10m⟧"]
    assert amount_band("USD 12,500.00") == "10k-100k" and amount_band("8.0m EUR") == "1m-10m"


def test_determinism_same_vault_same_output(gaz, tmp_path):
    """G8: re-running redaction with the same vault reproduces identical RedactedDoc + roots."""
    key = os.urandom(32)
    v = NonceVault(tmp_path / "v", key)
    v.init()
    doc = SourceDoc.from_text(TEXT, name="t.txt")
    r1 = redact_doc(doc, RuleDetector(gaz), v)
    v2 = NonceVault(tmp_path / "v", key)  # reopen from disk
    r2 = redact_doc(doc, RuleDetector(gaz), v2)
    assert r1.redacted == r2.redacted and r1.root == r2.root
    assert [s.commit for s in r1.segmentation.segments] == [s.commit for s in r2.segmentation.segments]
    # a different vault (different K_pseud + nonces) yields different tokens and roots
    v3 = NonceVault(tmp_path / "other", os.urandom(32))
    v3.init()
    r3 = redact_doc(doc, RuleDetector(gaz), v3)
    assert r3.redacted != r1.redacted and r3.root != r1.root


def test_vault_encrypted_at_rest_and_wrong_key(gaz, tmp_path):
    key = os.urandom(32)
    v = NonceVault(tmp_path / "v", key)
    v.init()
    doc = SourceDoc.from_text(TEXT, name="t.txt")
    redact_doc(doc, RuleDetector(gaz), v)
    for p in (tmp_path / "v").glob("*.enc"):
        raw = p.read_bytes()
        assert raw.startswith(b"LATV1") and b"Marta" not in raw and b"Norvale" not in raw
    assert NonceVault(tmp_path / "v", key).load_doc(doc.doc_id)["entries"]
    with pytest.raises(ValueError):
        NonceVault(tmp_path / "v", os.urandom(32)).load_doc(doc.doc_id)


def test_synthesise_mode_records_unprovable_doc(gaz, vault, tmp_path):
    doc = SourceDoc.from_text(TEXT, name="t.txt")
    work = WorkDir(tmp_path / "work")
    res = redact_corpus([doc], RuleDetector(gaz), vault, work, mode=MODE_SYNTHESISE)
    assert res[0].mode == MODE_SYNTHESISE and res[0].redacted == b""
    roots = work.load_roots()
    assert roots["docs"][doc.doc_id] == {"mode": "SYNTHESISE", "root": None, "n_segments": 0}
    assert not (work.red_dir / f"{doc.doc_id}.txt").exists()


def test_rebuild_detects_tampering(gaz, vault):
    doc = SourceDoc.from_text(TEXT, name="t.txt")
    r = redact_doc(doc, RuleDetector(gaz), vault)
    # one byte in kept text -> different root (T2)
    red = bytearray(r.redacted)
    i = red.index(b"Please")
    red[i] = ord("p")
    assert rebuild_root(doc.doc_id, r.segmentation, bytes(red)) != r.root
    # token changed in redacted text but not in segmentation -> rebuild error
    red2 = r.redacted.replace(b"\xe2\x9f\xa6PERSON:", b"\xe2\x9f\xa6PERSOM:", 1)
    with pytest.raises(RebuildError):
        rebuild_leaves(doc.doc_id, r.segmentation, red2)
    # truncated
    with pytest.raises(RebuildError):
        rebuild_leaves(doc.doc_id, r.segmentation, r.redacted[:-3])


def test_pluggable_detector_and_class_predicates(vault):
    text = "The quick brown fox jumped over the lazy dog on 2024-01-01."
    i, j = text.index("quick brown fox"), text.index("2024-01-01")
    det = StaticDetector([Detection(i, i + 15, "DATE", "quick brown fox"), Detection(j, j + 10, "DATE", "2024-01-01")])
    doc = SourceDoc.from_text(text, name="x.txt")
    r = redact_doc(doc, det, vault)
    originals = {e.original.decode(): e.cls for e in r.entries}
    assert originals == {"quick brown fox": "DATE", "2024-01-01": "DATE"}
    assert class_predicate("DATE", "2024-01-01") and class_predicate("DATE", "14 March 2024")
    assert not class_predicate("DATE", "quick brown fox")
    assert class_predicate("EMAIL", "a.b@example.test") and not class_predicate("EMAIL", "hello")
    assert class_predicate("TRADE_ID", "TRD-2024-00001") and not class_predicate("TRADE_ID", "hello world")
    assert class_predicate("PERSON", "Marta Kowalczyk") and not class_predicate("PERSON", "please confirm the booking")
    assert class_predicate("FREE_TEXT_QUOTE", '"quoted words"') and not class_predicate("FREE_TEXT_QUOTE", "plain words")
    g = Gazetteer(counterparties={"Norvale Capital"})
    assert class_predicate("COUNTERPARTY", "norvale capital", g) and not class_predicate("COUNTERPARTY", "Acme", g)


def test_unicode_offsets_are_bytes(vault):
    text = "Café — Émile Zola met Norvale Capital on 2024-02-02."
    g = Gazetteer(counterparties={"Norvale Capital"})
    doc = SourceDoc.from_text(text, name="u.txt")
    r = redact_doc(doc, RuleDetector(g), vault)
    assert r.segmentation.check_partition(len(doc.data)) == []
    assert reconstruct_original(r.segmentation, r.redacted, r.entries) == doc.data
    assert r.redacted.decode("utf-8")  # valid UTF-8 boundaries
