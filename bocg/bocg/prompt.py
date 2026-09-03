"""Frozen prompt assets (SPEC-01 §2, §3): loading, rendering, hashing, token lists."""
from __future__ import annotations

import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from .util import sha256_bytes, sha256_text

DEFAULT_PARAMS = {"THRESHOLD_USD": 200000, "CURRENCY": "USD", "AS_OF_YEAR": 2025}
PLACEHOLDERS = ("{THRESHOLD_USD}", "{CURRENCY}", "{AS_OF_YEAR}")


def asset_path(name: str) -> Path:
    return Path(str(resources.files("bocg").joinpath("assets", name)))


def asset_bytes(name: str) -> bytes:
    return asset_path(name).read_bytes()


def asset_text(name: str) -> str:
    return asset_bytes(name).decode("utf-8")


@dataclass(frozen=True)
class FrozenPrompt:
    prompt_text: str        # frozen prompt.txt (placeholders intact)
    system_text: str        # frozen system.txt
    schema_text: str        # schema.json text
    prompt_sha256: str      # sha256 of frozen prompt.txt bytes

    @property
    def prompt_sha8(self) -> str:
        return self.prompt_sha256[:8]

    def render(self, threshold_usd: int | float = 200000, currency: str = "USD", as_of_year: int = 2025) -> str:
        """Substitute the three permitted placeholders (only these; nothing else is touched)."""
        out = self.prompt_text
        out = out.replace("{THRESHOLD_USD}", _fmt_num(threshold_usd))
        out = out.replace("{CURRENCY}", str(currency))
        out = out.replace("{AS_OF_YEAR}", str(as_of_year))
        return out


def _fmt_num(v: int | float) -> str:
    return str(int(v)) if float(v).is_integer() else str(v)


def load_frozen(prompt_path: Path | None = None, system_path: Path | None = None,
                schema_path: Path | None = None) -> FrozenPrompt:
    p = Path(prompt_path).read_bytes() if prompt_path else asset_bytes("prompt.txt")
    s = Path(system_path).read_text(encoding="utf-8") if system_path else asset_text("system.txt")
    sc = Path(schema_path).read_text(encoding="utf-8") if schema_path else asset_text("schema.json")
    return FrozenPrompt(prompt_text=p.decode("utf-8"), system_text=s, schema_text=sc, prompt_sha256=sha256_bytes(p))


def _read_list(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out


def forbidden_tokens(path: Path | None = None) -> list[str]:
    text = Path(path).read_text(encoding="utf-8") if path else asset_text("forbidden_tokens.txt")
    return _read_list(text)


def negative_instruction_allowlist(path: Path | None = None) -> list[str]:
    text = Path(path).read_text(encoding="utf-8") if path else asset_text("negative_instruction_allowlist.txt")
    return _read_list(text)


def self_assess_patterns(path: Path | None = None) -> list[re.Pattern]:
    text = Path(path).read_text(encoding="utf-8") if path else asset_text("self_assess_patterns.txt")
    return [re.compile(p, re.IGNORECASE) for p in _read_list(text)]


def strip_allowlisted(text: str, allowlist: list[str] | None = None) -> str:
    """Remove the exact negative-instruction phrases (see assets/negative_instruction_allowlist.txt)."""
    for phrase in (allowlist if allowlist is not None else negative_instruction_allowlist()):
        text = text.replace(phrase, " ")
    return text


def token_regex(token: str) -> re.Pattern:
    """Whole-word, case-insensitive match; internal whitespace/hyphens match any run of space/hyphen."""
    parts = [re.escape(p) for p in re.split(r"[\s\-]+", token.strip()) if p]
    body = r"[\s\-]+".join(parts)
    lead = r"(?<![A-Za-z0-9])" if re.match(r"[A-Za-z0-9]", token.strip()) else ""
    trail = r"(?![A-Za-z0-9])" if re.search(r"[A-Za-z0-9]$", token.strip()) else ""
    return re.compile(lead + body + trail, re.IGNORECASE)


HASHED_PREFIX = "sha256:"


def is_hashed_entry(token: str) -> bool:
    """A denylist line of the form sha256:<hex> denies a token without printing it (SPEC-01 §2.3)."""
    return token.strip().lower().startswith(HASHED_PREFIX)


def canonical_token(token: str) -> str:
    """The form a hashed entry commits to: lowercase; runs of whitespace/hyphen collapse to one space."""
    return " ".join(p for p in re.split(r"[\s\-]+", token.strip().lower()) if p)


def _phrase_candidates(text: str, max_words: int = 6):
    """Yield (canonical phrase, start, end) for every run of 1..max_words whole words joined only by
    whitespace/hyphen. Mirrors token_regex(): word boundaries are non-alphanumerics."""
    words = [(m.group(0).lower(), m.start(), m.end()) for m in re.finditer(r"[A-Za-z0-9]+", text)]
    for i, (word, start, end) in enumerate(words):
        yield word, start, end
        parts, last = [word], end
        for nxt, s2, e2 in words[i + 1: i + max_words]:
            if not re.fullmatch(r"[\s\-]+", text[last:s2]):
                break
            parts.append(nxt)
            last = e2
            yield " ".join(parts), start, last


def find_hashed(text: str, entries: list[str]) -> list[dict]:
    """Return [{token, count, sample, span}] for every sha256: entry whose token occurs whole-word in text.
    The matched text is never echoed (that would print the denied token); the first span is reported instead."""
    wanted = {e.strip()[len(HASHED_PREFIX):].lower(): e.strip() for e in entries}
    hits: dict[str, dict] = {}
    for phrase, start, end in _phrase_candidates(text):
        entry = wanted.get(sha256_text(phrase))
        if entry is None:
            continue
        if entry in hits:
            hits[entry]["count"] += 1
        else:
            hits[entry] = {"token": entry, "count": 1, "sample": "<redacted: hashed entry>", "span": [start, end]}
    return list(hits.values())


def find_forbidden(text: str, tokens: list[str] | None = None, apply_allowlist: bool = True) -> list[dict]:
    """Return [{token, count, sample}] for every forbidden token present in text (after allowlist stripping)."""
    scan = strip_allowlisted(text) if apply_allowlist else text
    entries = tokens if tokens is not None else forbidden_tokens()
    hits = []
    for tok in entries:
        if is_hashed_entry(tok):
            continue
        rx = token_regex(tok)
        ms = list(rx.finditer(scan))
        if ms:
            m = ms[0]
            hits.append({"token": tok, "count": len(ms),
                         "sample": scan[max(0, m.start() - 30): m.end() + 30].replace("\n", " ")})
    hits.extend(find_hashed(scan, [t for t in entries if is_hashed_entry(t)]))
    return hits


def find_self_assessment(text: str, patterns: list[re.Pattern] | None = None, apply_allowlist: bool = False) -> list[dict]:
    scan = strip_allowlisted(text) if apply_allowlist else text
    hits = []
    for rx in (patterns if patterns is not None else self_assess_patterns()):
        m = rx.search(scan)
        if m:
            hits.append({"pattern": rx.pattern, "match": m.group(0),
                         "sample": scan[max(0, m.start() - 30): m.end() + 30].replace("\n", " ")})
    return hits


def prompt_sha256_of(text: str) -> str:
    return sha256_text(text)
