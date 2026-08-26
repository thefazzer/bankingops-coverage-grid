"""§4 detection pipeline: pluggable Detector interface, rule detector classes, overlap resolution, gazetteer IO."""
from lat.classes import Gazetteer
from lat.ner import CompositeDetector, Detection, Detector, RuleDetector, StaticDetector, resolve_overlaps


def test_rule_detector_classes():
    gaz = Gazetteer(counterparties={"Norvale Capital"}, clients={"Pellucid Pension Fund"}, internal_systems={"TRADEHUB"},
                    locations={"Port Ellery"}, persons={"Marta Kowalczyk"}, allowlist={"Trade Support"})
    text = ("Marta Kowalczyk (Trade Support) booked TRD-2024-00042 for Pellucid Pension Fund with Norvale Capital in "
            "TRADEHUB on 14 March 2024; contact marta.k@examplebank.test / +000 123 4567 890, account ACC-123456, "
            "IBAN XX12 FAKE 1234 5678 9012 34, from the Port Ellery branch of Brightmoor Securities Ltd; Tobias Brenner agreed.")
    dets = RuleDetector(gaz).detect(text)
    by_cls = {}
    for d in dets:
        by_cls.setdefault(d.cls, []).append(d.text)
    assert by_cls["PERSON"] == ["Marta Kowalczyk", "Tobias Brenner"]      # gazetteer + capitalised heuristic
    assert by_cls["COUNTERPARTY"] == ["Norvale Capital"] and by_cls["CLIENT"] == ["Pellucid Pension Fund"]
    assert by_cls["INTERNAL_SYSTEM"] == ["TRADEHUB"] and by_cls["LOCATION"] == ["Port Ellery"]
    assert by_cls["TRADE_ID"] == ["TRD-2024-00042"] and by_cls["DATE"] == ["14 March 2024"]
    assert by_cls["EMAIL"] == ["marta.k@examplebank.test"] and by_cls["PHONE"] == ["+000 123 4567 890"]
    assert "ACC-123456" in by_cls["ACCOUNT_ID"] and any(x.startswith("XX12") for x in by_cls["ACCOUNT_ID"])
    assert by_cls["LEGAL_ENTITY"] == ["Brightmoor Securities Ltd"]
    assert "Trade Support" not in sum(by_cls.values(), [])                 # allowlisted
    # non-overlapping, sorted
    assert all(dets[i].end <= dets[i + 1].start for i in range(len(dets) - 1))
    # amounts only when policy says so
    assert not [d for d in RuleDetector(gaz).detect("paid USD 1,000.00") if d.cls == "AMOUNT_EXACT"]
    assert [d.text for d in RuleDetector(gaz, redact_amounts=True).detect("paid USD 1,000.00")] == ["USD 1,000.00"]
    assert [d.cls for d in RuleDetector(gaz, redact_amounts={"USD 1,000.00"}).detect("USD 1,000.00 and USD 5.00")] == ["AMOUNT_EXACT"]


def test_overlap_resolution_and_composite():
    cands = [Detection(0, 10, "PERSON", "x"), Detection(0, 15, "EMAIL", "y"), Detection(12, 20, "DATE", "z")]
    kept = resolve_overlaps(cands)
    assert [d.cls for d in kept] == ["EMAIL"]  # EMAIL outranks PERSON; DATE overlaps the winner
    comp = CompositeDetector(StaticDetector([Detection(0, 3, "CLIENT", "abc")]), StaticDetector([Detection(5, 8, "DATE", "d")]))
    assert [d.cls for d in comp.detect("abc  def")] == ["CLIENT", "DATE"]
    assert isinstance(comp, Detector) and isinstance(RuleDetector(), Detector)


def test_gazetteer_roundtrip(tmp_path):
    g = Gazetteer(counterparties={"A Corp"}, allowlist={"Kind Regards"}, products={"repo"})
    g.save(tmp_path)
    g2 = Gazetteer.load(tmp_path)
    assert g2.counterparties == {"A Corp"} and g2.allowed("kind regards") and g2.products == {"repo"}
    assert g2.class_of("a corp") == "COUNTERPARTY" and g2.class_of("nobody") is None


def test_gazetteer_name_inside_email_does_not_split_the_email():
    gaz = Gazetteer(persons={"Marta"})
    dets = RuleDetector(gaz).detect("write to marta.lindqvist@fakecorp.test today")
    assert [(d.cls, d.text) for d in dets] == [("EMAIL", "marta.lindqvist@fakecorp.test")]
