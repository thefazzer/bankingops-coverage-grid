# SPEC-05 — Portable insight-construction and adjudication contracts

```
ARTIFACT : static definitions and rubrics for evidence-grounded insights
STATUS   : v0.2 normative profile
SOURCE   : specs/insight-construction-profile.yaml
BOUNDARY : definitions and conformance only; no institutional instances
```

## Purpose

This profile is a second, layered BOCG contract. SPEC-04 remains the public
division/function/control-point profile and continues to prohibit occurrence
instances. SPEC-05 defines portable shapes that an implementation may use for
Observation Atoms, Traces, Episodes, institutional speech-act expansion and
adjudication. It does not publish any firm's emails, workflow, people, systems,
graph, extraction logic or adjudication ledger.

## Normative separation

```text
BOCG:       schemas + vocabulary + rubrics + conformance fixtures
consumer:   extraction + instance data + inference + persistence + UI
```

An Observation Atom is an independently addressable, evidence-bound
proposition. A Trace orders or relates Atom identifiers without asserting
causality merely from order. An Episode is defeasible connective tissue among
Atoms; its existence does not make every inferred actor, cause or outcome true.

## Institutional speech acts

Implementations MUST preserve the literal speech act separately from a
defeasible institutional reading. One source span MAY support multiple Atoms.
The lifecycle states `directed`, `scheduled`, `executed`, `completed` and
`verified` are non-interchangeable. A directive MUST NOT establish execution,
completion or verification.

## Temporal anchors and deadlines

Episode and obligation-frame records may carry typed temporal anchors
(`observed_at`, `valid_from`, `valid_to`, `deadline`, `scheduled_at`,
`executed_at`, `completed_at`, `verified_at`). An observation timestamp never
supplies a validity bound, and a scheduled time never proves execution. Deadline
constraints name a deadline type (`regulatory`, `contractual`, `internal_sla`,
`market_cutoff`) and a reference time; they express when a state is due, not that
it occurred. Unknown timestamps remain unknown.

## Adjudication

Machine constructions are immutable. SME decisions are append-only overlays,
bound to exact evidence and the prior machine construction. Split decisions
retain the original Atom and produce content-addressed component Atoms sharing
the same evidence selector. Dependent Traces and Episodes require explicit
recomposition.

## Portability boundary

Normative artifacts contain no institution names, employee identities, corpus
paths, source text, workflow instances, customer data or implementation code.
Consumers pin a BOCG release manifest and fail closed on hash mismatch.
