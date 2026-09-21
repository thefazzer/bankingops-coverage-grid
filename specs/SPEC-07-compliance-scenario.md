# SPEC-07 — Replayable compliance scenario contract

```
ARTIFACT : static contract and schema for replayable compliance scenarios
STATUS   : v0.1 normative spec + schema
SOURCE   : specs/compliance-scenario.schema.json
BOUNDARY : definitions, schema and one synthetic fixture only; no institution scenarios or private data
```

## Purpose

A compliance scenario composes a control-point cell, a terminality task, an
input state, an oracle and an expected verdict into one content-addressed,
replayable object. It is pinned to a BOCG release manifest and, optionally, to
a released model checkpoint. Consumers fail closed when the pinned manifest
hash does not match the manifest they are consuming.

## Contract

A scenario MUST be valid JSON and conform to `specs/compliance-scenario.schema.json`.
It MUST contain:

| Field | Semantics |
|---|---|
| `manifest_sha256` | SHA-256 of the BOCG release manifest the scenario is pinned to. |
| `cell_id` | Identifier of the control-point cell under test. |
| `task_ref` | Reference to a released terminality task from `reference/operating-catalogue.v1.json`. |
| `input_state` | Reference to a CDM event, FpML document or synthetic fixture, addressed by hash. |
| `oracle` | Deterministic validator reference (CDM/DRR validation, SIMM, ISDA CDS Standard Model, or a rule predicate) with version. |
| `expected_verdict` | Predicate over lifecycle states `directed`, `scheduled`, `executed`, `completed`, `verified`. A directive never satisfies execution. |
| `deadline` | Regime clock reference for the scenario's time semantics. |
| `pass_rule` | Statistical assertion rule: `replicates`, `judges`, or `alpha`. The assertion is statistical, never boolean. |
| `leakage_attestation` | LAT holdout commitment reference. |
| `controls` | Five-families checks that apply; `NEGATIVE_CONTROL` and `EVIDENCE_ABLATION` are required at minimum. |

## Boundary

The repository contains only the contract, schema and a synthetic fixture.
Scenarios that carry institution data, real transactions, internal models or
proprietary oracles are consumer-owned and MUST NOT be published here.

## Conformance

Run `python3 tools/gate_conformance.py`; the S7 gate validates that the
synthetic fixture parses, matches the schema, pins a known manifest hash, and
honours the lifecycle non-interference rules from SPEC-05.
