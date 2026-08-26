"""§3 response validation + post-validation (I5 order check, I9 admission recompute), I7 self-assessment scan."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

import jsonschema

from .prompt import asset_text, find_self_assessment

ARITH_TOLERANCE = 0.05  # >5% deviation => ARITH_MISMATCH

_schema_cache: dict[str, Any] = {}


def load_schema(schema_text: str | None = None) -> dict:
    text = schema_text if schema_text is not None else asset_text("schema.json")
    if text not in _schema_cache:
        _schema_cache[text] = json.loads(text)
    return _schema_cache[text]


def parse_json(raw: str) -> tuple[Any | None, str | None]:
    """Parse the raw response as JSON. No fix-ups (I4/RETRY): the only leniency is stripping a ```json fence."""
    text = raw.strip()
    m = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    try:
        return json.loads(text), None
    except json.JSONDecodeError as e:
        return None, f"JSON parse error: {e}"


def schema_errors(obj: Any, schema: dict | None = None) -> list[str]:
    v = jsonschema.Draft202012Validator(schema or load_schema())
    errs = sorted(v.iter_errors(obj), key=lambda e: list(e.absolute_path))
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}" for e in errs]


# --------------------------------------------------------------------------------------------------------------
# I5 ORDER CHECK on raw text
# --------------------------------------------------------------------------------------------------------------
_DIV_ARRAY = re.compile(r'"divisions"\s*:\s*\[')


def _iter_top_objects(text: str, start: int) -> list[tuple[int, int]]:
    """Yield (start,end) byte offsets of the top-level objects inside the array starting at `start` ('[')."""
    spans = []
    depth = 0
    in_str = False
    esc = False
    obj_start = -1
    i = start
    n = len(text)
    arr_depth = 0
    while i < n:
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "[":
                arr_depth += 1
            elif c == "]":
                arr_depth -= 1
                if arr_depth == 0:
                    break
            elif c == "{":
                if depth == 0:
                    obj_start = i
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0 and obj_start >= 0:
                    spans.append((obj_start, i + 1))
                    obj_start = -1
        i += 1
    return spans


def order_check(raw: str) -> dict:
    """I5: within each division object, byte offset of '"a1_regulatory"' < offset of '"name"'.

    Operates on the raw text (not the parsed object). Returns {ok, divisions_checked, violations:[idx...]}.
    """
    text = raw
    m = _DIV_ARRAY.search(text)
    if not m:
        return {"ok": False, "divisions_checked": 0, "violations": [], "error": "no divisions array found"}
    spans = _iter_top_objects(text, m.end() - 1)
    violations = []
    for idx, (s, e) in enumerate(spans):
        chunk = text[s:e]
        a1 = _top_level_key_offset(chunk, "a1_regulatory")
        nm = _top_level_key_offset(chunk, "name")
        if a1 is None or nm is None or not (a1 < nm):
            violations.append(idx)
    return {"ok": not violations and bool(spans), "divisions_checked": len(spans), "violations": violations}


def _top_level_key_offset(chunk: str, key: str) -> int | None:
    """Offset of the first occurrence of "key" at nesting depth 1 inside `chunk` (which starts with '{')."""
    depth = 0
    in_str = False
    esc = False
    i = 0
    n = len(chunk)
    target = f'"{key}"'
    while i < n:
        c = chunk[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            if depth == 1 and chunk.startswith(target, i):
                # must be a key: next non-space char after the closing quote is ':'
                j = i + len(target)
                while j < n and chunk[j] in " \t\r\n":
                    j += 1
                if j < n and chunk[j] == ":":
                    return i
            in_str = True
        elif c in "{[":
            depth += 1
        elif c in "}]":
            depth -= 1
        i += 1
    return None


# --------------------------------------------------------------------------------------------------------------
# I9 ADMISSION RECOMPUTE (server-side)
# --------------------------------------------------------------------------------------------------------------
@dataclass
class Admission:
    anchors_nonnull: int
    addressable_seat_cost_model: float
    addressable_seat_cost_recomputed: float
    arith_mismatch: bool
    terminality_count: int
    admitted: bool
    reasons: list[str] = field(default_factory=list)   # reason codes from the schema enum

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def _nonnull_anchor(a: Any) -> bool:
    return isinstance(a, list) and len(a) > 0


def recompute_seat_cost(a4: dict) -> float:
    lo, hi = a4["cost_per_seat"]
    return ((float(lo) + float(hi)) / 2.0) * float(a4["determinable_fraction"])


def admission(div: dict, threshold: float) -> Admission:
    a4 = div["a4_seat"]
    nonnull = sum(_nonnull_anchor(div.get(k)) for k in ("a1_regulatory", "a2_segment", "a3_market_size"))
    recomputed = recompute_seat_cost(a4)
    model_val = float(a4.get("addressable_seat_cost", 0.0))
    if recomputed == 0:
        mismatch = model_val != 0
    else:
        mismatch = abs(model_val - recomputed) / abs(recomputed) > ARITH_TOLERANCE
    tcount = len(a4.get("terminality") or [])
    reasons = []
    if nonnull < 2:
        reasons.append("R_ANCHORS_LT2")
    if recomputed < float(threshold):
        reasons.append("R_SEAT_BELOW_THRESHOLD")
    if tcount < 3:
        reasons.append("R_TERMINALITY_LT3")
    return Admission(anchors_nonnull=nonnull, addressable_seat_cost_model=model_val,
                     addressable_seat_cost_recomputed=recomputed, arith_mismatch=mismatch,
                     terminality_count=tcount, admitted=not reasons, reasons=reasons)


# --------------------------------------------------------------------------------------------------------------
# Full response assessment (used by normalise and by gates)
# --------------------------------------------------------------------------------------------------------------
@dataclass
class Assessment:
    parse_error: str | None
    schema_errors: list[str]
    order: dict | None
    rejected_count: int | None
    self_assess: list[dict]
    obj: Any | None

    @property
    def schema_valid(self) -> bool:
        return self.parse_error is None and not self.schema_errors

    @property
    def valid(self) -> bool:
        """VALID = parses + schema-valid + order ok + rejected>=1 + no self-assessment language."""
        return (self.schema_valid and bool(self.order and self.order["ok"])
                and (self.rejected_count or 0) >= 1 and not self.self_assess)

    def invalid_reasons(self) -> list[str]:
        r = []
        if self.parse_error:
            r.append("PARSE_ERROR")
        if self.schema_errors:
            r.append("SCHEMA_INVALID")
        if self.order is not None and not self.order["ok"]:
            r.append("ORDER_VIOLATION")
        if self.rejected_count is not None and self.rejected_count < 1:
            r.append("REJECTED_EMPTY")
        if self.self_assess:
            r.append("SELF_ASSESSMENT_LANGUAGE")
        return r


def assess(raw: str, schema: dict | None = None) -> Assessment:
    obj, perr = parse_json(raw)
    if perr:
        return Assessment(perr, [], None, None, find_self_assessment(raw), None)
    errs = schema_errors(obj, schema)
    rej = len(obj.get("rejected") or []) if isinstance(obj, dict) else None
    order = order_check(raw) if not errs else None
    return Assessment(None, errs, order, rej, find_self_assessment(raw), obj)
