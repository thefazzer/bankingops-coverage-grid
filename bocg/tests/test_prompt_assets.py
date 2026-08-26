"""Frozen prompt assets: §2.1/2.2 text, schema embedding, placeholders, forbidden tokens (I1, I2, I7)."""
import json
import re

from bocg.prompt import (PLACEHOLDERS, asset_text, find_forbidden, find_self_assessment, forbidden_tokens,
                         load_frozen, token_regex)


def test_prompt_has_placeholders_and_embedded_schema():
    fp = load_frozen()
    for ph in PLACEHOLDERS:
        assert ph in fp.prompt_text
    assert "<SCHEMA>" not in fp.prompt_text
    schema = json.loads(asset_text("schema.json"))
    assert schema["$id"] == "bocg.response.v1"
    assert asset_text("schema.json").rstrip("\n") in fp.prompt_text  # embedded verbatim
    assert fp.prompt_text.startswith("Decompose the capital-markets and global-markets business")
    assert fp.system_text.startswith("You are an analyst producing a structured decomposition.")


def test_render_substitutes_only_placeholders():
    fp = load_frozen()
    r = fp.render(200000, "USD", 2025)
    assert "{THRESHOLD_USD}" not in r and ">= 200000 USD" in r and "as of 2025" in r
    # rendering does not change the frozen hash
    assert fp.prompt_sha256 == load_frozen().prompt_sha256 and len(fp.prompt_sha8) == 8


def test_prompt_and_system_are_free_of_forbidden_tokens():
    fp = load_frozen()
    assert find_forbidden(fp.prompt_text) == []
    assert find_forbidden(fp.system_text) == []
    assert find_self_assessment(fp.prompt_text + fp.system_text, apply_allowlist=True) == []


def test_forbidden_token_list_covers_spec_and_names():
    toks = {t.lower() for t in forbidden_tokens()}
    for t in ["prime brokerage", "prime broker", "pb", "equity finance", "securities lending", "stock loan",
              "single stock swap", "single-stock swap", "synthetic", "trs", "total return swap", "delta one",
              "delta-one", "hedge fund", "finexhaust", "bankingenv", "pb-ops", "jefferies", "gap", "under-served",
              "underserved", "model capability", "benchmark", "eval"]:
        assert t in toks
    banks = [t for t in toks if t in {"goldman sachs", "morgan stanley", "barclays", "hsbc", "ubs", "nomura"}]
    assert len(banks) == 6
    assert len(toks) >= 24 + 30 + 20


def test_token_regex_is_whole_word():
    rx = token_regex("PB")
    assert rx.search("the PB desk") and not rx.search("PBX phone") and not rx.search("apb")
    assert token_regex("gap").search("a Gap here") and not token_regex("gap").search("gaps")  # exact token only
    assert token_regex("delta-one").search("delta one") and token_regex("delta one").search("Delta-One")
    assert find_forbidden("we cover hedge funds", apply_allowlist=False) == []  # plural is a different token
    hits = find_forbidden("prime brokerage ops", apply_allowlist=False)
    assert hits and hits[0]["token"] == "prime brokerage"


def test_prompt_assets_do_not_mention_seller_segment():
    text = (asset_text("prompt.txt") + asset_text("system.txt")).lower()
    for bad in ["prime brokerage", "equity finance", "swap", "hedge fund"]:
        assert not re.search(r"\b" + re.escape(bad) + r"s?\b", text)
