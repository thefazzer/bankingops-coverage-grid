"""§5.1 CANON_NAME: lowercase, strip punctuation, collapse whitespace, singularise, drop stopwords."""
from __future__ import annotations

import re
import unicodedata

STOPWORDS = {"the", "of", "and", "&", "desk", "business", "group"}

# Words whose surface form ends in 's' but is not a plural (kept as-is).
_SINGULAR_EXCEPTIONS = {
    "analysis", "basis", "crisis", "chassis", "thesis", "synthesis", "hypothesis", "diagnosis", "prognosis",
    "axis", "series", "species", "news", "status", "apparatus", "consensus", "prospectus", "surplus", "bonus",
    "focus", "nexus", "census", "fx", "ops", "gas", "plus", "minus", "bus", "class", "process", "access",
    "loss", "mass", "cross", "gross", "less", "bis", "ois", "cds", "irs", "abs", "mbs", "clo", "cdo", "etf",
    "iss", "sfs", "ucits", "mifid", "emir", "dfa", "ccass", "less", "excess", "us",
}

_STRIP_PUNCT = re.compile(r"[^0-9a-z\s]+")
_WS = re.compile(r"\s+")


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def singularise(word: str) -> str:
    """Deterministic, rule-based English singularisation (good enough for division names)."""
    w = word
    if len(w) <= 3 or w in _SINGULAR_EXCEPTIONS or w.endswith("ss") or w.endswith("us") or w.endswith("is"):
        return w
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("ves") and len(w) > 4:
        return w[:-3] + "f"
    if w.endswith(("ches", "shes", "sses", "xes", "zes")):
        return w[:-2]
    if w.endswith("oes") and len(w) > 4:
        return w[:-2]
    if w.endswith("s"):
        return w[:-1]
    return w


def canon_name(name: str) -> str:
    s = _strip_accents(str(name)).lower()
    s = s.replace("&", " ")
    s = _STRIP_PUNCT.sub(" ", s)
    words = [w for w in _WS.split(s.strip()) if w]
    words = [singularise(w) for w in words]
    words = [w for w in words if w not in STOPWORDS]
    return " ".join(words)


def slug_key(canon: str) -> str:
    """Default division_key derived from a canon name (used for auto-drafted alias tables)."""
    return re.sub(r"[^a-z0-9]+", "_", canon.strip().lower()).strip("_") or "unnamed"
