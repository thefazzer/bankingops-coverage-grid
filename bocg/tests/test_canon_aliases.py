"""§5.1 canonicalisation + §5.2 alias table."""
import pytest
import yaml

from bocg.aliases import AliasTable, draft_identity_table, load_aliases, write_aliases
from bocg.canon import canon_name, singularise, slug_key
from bocg.util import BocgError


@pytest.mark.parametrize("raw,expected", [
    ("Rates Trading", "rate trading"),
    ("Interest Rates Trading Desk", "interest rate trading"),
    ("Securities Services (Custody & Fund Services)", "security service custody fund service"),
    ("The Settlements Group", "settlement"),
    ("FX  Trading\tdesk", "fx trading"),
    ("Collateral Management & Margining", "collateral management margining"),
    ("Equities   Trading", "equity trading"),
    ("Crédit Trading business", "credit trading"),
    ("Regulatory Reporting & Analysis", "regulatory reporting analysis"),
])
def test_canon_name(raw, expected):
    assert canon_name(raw) == expected


def test_singularise_rules():
    assert singularise("equities") == "equity"
    assert singularise("services") == "service"
    assert singularise("settlements") == "settlement"
    assert singularise("analysis") == "analysis"
    assert singularise("class") == "class"
    assert singularise("fx") == "fx"
    assert singularise("matches") == "match"


def test_canon_is_idempotent_and_deterministic():
    for n in ["Rates Trading", "Securities Services", "Trade Support Middle Office"]:
        c = canon_name(n)
        assert canon_name(c) == c
        assert canon_name(n) == c


def test_alias_table_maps_variants_to_one_key(fixtures_dir):
    t = load_aliases(fixtures_dir / "aliases.yaml")
    assert t.key_for("Rates Trading") == "rates_trading"
    assert t.key_for("Interest Rates Trading Desk") == "rates_trading"
    assert t.key_for("Global Rates Trading") == "rates_trading"
    assert t.key_for("Cash Equities Trading") == "equities_trading"
    assert t.key_for("Something Unknown") is None
    assert "settlements" in t.keys()
    assert all(e.get("rationale") for e in t.entries)


def test_alias_table_rejects_alias_mapped_to_two_keys():
    with pytest.raises(BocgError, match="maps to two keys"):
        AliasTable.from_dict({"version": 1, "aliases": [
            {"canon": "rate trading", "key": "rates_trading", "rationale": "a"},
            {"canon": "Rates Trading", "key": "rates", "rationale": "b"}]})


def test_alias_table_requires_rationale():
    with pytest.raises(BocgError, match="rationale"):
        AliasTable.from_dict({"version": 1, "aliases": [{"canon": "rate trading", "key": "rates_trading"}]})


def test_identity_draft_and_roundtrip(tmp_path):
    t = draft_identity_table(["rate trading", "fx trading"], "deadbeef")
    assert t.auto_generated and t.key_for("Rates Trading") == "rate_trading"
    assert t.key_for("FX trading") == slug_key("fx trading") == "fx_trading"
    sha = write_aliases(tmp_path / "a.yaml", t)
    loaded = load_aliases(tmp_path / "a.yaml")
    assert loaded.mapping == t.mapping and len(sha) == 64
    assert yaml.safe_load((tmp_path / "a.yaml").read_text())["auto_generated"] is True
