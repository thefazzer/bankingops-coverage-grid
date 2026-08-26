"""SPEC-02 §2 — object model (plain dataclasses; JSON (de)serialisation helpers)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

from .encoding import sha256_hex, utf8

KEEP = "KEEP"
REDACT = "REDACT"
MODE_PSEUDONYMISE = "PSEUDONYMISE"
MODE_SYNTHESISE = "SYNTHESISE"


@dataclass
class Origin:
    institution_code: str = "UNKNOWN"
    period_start: str = ""
    period_end: str = ""
    channel: str = "unknown"

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "Origin":
        d = d or {}
        return cls(d.get("institution_code", "UNKNOWN"), d.get("period_start", ""), d.get("period_end", ""),
                   d.get("channel", "unknown"))


@dataclass
class SourceDoc:
    doc_id: str
    data: bytes                      # NFC-normalised UTF-8 bytes; doc_id = sha256(data)
    origin: Origin = field(default_factory=Origin)
    name: str = ""                   # source filename (seller-side only)

    @classmethod
    def from_text(cls, text: str, origin: Optional[Origin] = None, name: str = "") -> "SourceDoc":
        data = utf8(text)
        return cls(sha256_hex(data), data, origin or Origin(), name)

    @property
    def text(self) -> str:
        return self.data.decode("utf-8")


@dataclass
class Segment:
    idx: int
    start: int                       # byte offset into source doc (inclusive)
    end: int                         # byte offset (exclusive)
    kind: str                        # KEEP | REDACT
    cls: Optional[str] = None        # REDACT only
    token: Optional[str] = None      # REDACT only: replacement token ⟦CLASS:pseudonym_id⟧
    commit: Optional[str] = None     # REDACT only: hex commitment

    def to_dict(self) -> dict:
        d = {"idx": self.idx, "start": self.start, "end": self.end, "kind": self.kind}
        if self.kind == REDACT:
            d.update({"class": self.cls, "token": self.token, "commit": self.commit})
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Segment":
        return cls(int(d["idx"]), int(d["start"]), int(d["end"]), d["kind"], d.get("class"), d.get("token"),
                   d.get("commit"))


@dataclass
class Segmentation:
    doc_id: str
    segments: list[Segment]
    date_policy: str = "shift_per_doc_v1"
    mode: str = MODE_PSEUDONYMISE
    version: int = 1

    def to_dict(self) -> dict:
        return {"version": self.version, "doc_id": self.doc_id, "mode": self.mode, "date_policy": self.date_policy,
                "segments": [s.to_dict() for s in self.segments]}

    @classmethod
    def from_dict(cls, d: dict) -> "Segmentation":
        return cls(d["doc_id"], [Segment.from_dict(s) for s in d["segments"]], d.get("date_policy", "shift_per_doc_v1"),
                   d.get("mode", MODE_PSEUDONYMISE), int(d.get("version", 1)))

    def check_partition(self, total_len: Optional[int] = None) -> list[str]:
        """Segments must partition [0,len) in order with no gaps/overlaps; REDACT needs exactly one class."""
        errs = []
        pos = 0
        for i, s in enumerate(self.segments):
            if s.idx != i:
                errs.append(f"idx {s.idx} != position {i}")
            if s.start != pos:
                errs.append(f"segment {i}: start {s.start} != expected {pos}")
            if s.end <= s.start:
                errs.append(f"segment {i}: empty or negative span")
            if s.kind not in (KEEP, REDACT):
                errs.append(f"segment {i}: bad kind {s.kind}")
            if s.kind == REDACT and (not s.cls or not s.token or not s.commit):
                errs.append(f"segment {i}: REDACT without class/token/commit")
            pos = s.end
        if total_len is not None and pos != total_len:
            errs.append(f"segments end at {pos}, doc length {total_len}")
        return errs


@dataclass
class VaultEntry:
    idx: int
    start: int
    end: int
    cls: str
    original: bytes
    nonce: bytes
    token: str


@dataclass
class SpanRef:
    doc_id: str
    idx: int
    leaf_or_commit: str

    def to_dict(self):
        return {"doc_id": self.doc_id, "idx": self.idx, "leaf_or_commit": self.leaf_or_commit}

    @classmethod
    def from_dict(cls, d):
        return cls(d["doc_id"], int(d["idx"]), d["leaf_or_commit"])


@dataclass
class Atom:
    atom_id: str
    episode_id: str
    content: str
    derivation_op: str
    lineage_class: str
    span_refs: list[SpanRef]
    generator_version: str
    content_sha256: str

    def to_dict(self):
        return {"atom_id": self.atom_id, "episode_id": self.episode_id, "content": self.content,
                "derivation_op": self.derivation_op, "lineage_class": self.lineage_class,
                "span_refs": [r.to_dict() for r in self.span_refs], "generator_version": self.generator_version,
                "content_sha256": self.content_sha256}

    @classmethod
    def from_dict(cls, d):
        return cls(d["atom_id"], d["episode_id"], d["content"], d["derivation_op"], d["lineage_class"],
                   [SpanRef.from_dict(r) for r in d.get("span_refs", [])], d.get("generator_version", ""),
                   d["content_sha256"])


@dataclass
class Episode:
    episode_id: str
    task_id: str
    atoms: list[str]
    trace_ref: str = ""
    verifier_ref: str = ""
    task_text: str = ""
    lineage_summary: dict = field(default_factory=dict)

    def to_dict(self):
        return {"episode_id": self.episode_id, "task_id": self.task_id, "atoms": list(self.atoms),
                "trace_ref": self.trace_ref, "verifier_ref": self.verifier_ref, "task_text": self.task_text,
                "lineage_summary": self.lineage_summary}

    @classmethod
    def from_dict(cls, d):
        return cls(d["episode_id"], d["task_id"], list(d["atoms"]), d.get("trace_ref", ""), d.get("verifier_ref", ""),
                   d.get("task_text", ""), d.get("lineage_summary", {}))
