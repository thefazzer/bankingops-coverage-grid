# SPEC-07 — Scenario-run ledger

```
ARTIFACT : append-only, content-addressed ledger that records a model identity against a scenario outcome
STATUS   : v0.1 normative schema
SOURCE   : specs/scenario-run-ledger-rows.schema.json
BOUNDARY : ledger structure only; no institution-specific corpus, task text or occurrence claims
```

## Purpose

A regression harness that runs scenarios "after model release" needs an immutable
row that binds:

- the model that was evaluated,
- the release manifest that pinned the reference artefacts,
- the scenario/task contract that was executed,
- the evaluation lane (replicates, judges, pass rule),
- the runner harness and tree cleanliness,
- the verdict, and
- the sealed evidence bundle.

`specs/scenario-run-ledger-rows.schema.json` defines that row. The run-level
ledger in `specs/scenario-run-ledger.schema.json` remains the simpler per-run
record. Nothing in this ledger is
a claim about the grid itself; it is a portable record of a model-scenario outcome
that consumers can replay or audit against the named manifest and evidence bundle.

## Row semantics

A ledger is a JSON object with `schema`, `version` and `rows`. Rows are ordered and
append-only. A row is never mutated or deleted; a correction is a new row whose
`replaces_row_sha256` names the prior row it supersedes.

Each row carries:

| Field | Meaning |
|---|---|
| `row_sha256` | Content-addressed digest of the row, computed over the canonical JSON of the row excluding `row_sha256`. |
| `recorded_at` | ISO 8601 timestamp when the row was recorded. |
| `replaces_row_sha256` | Hash of the row this row corrects, or `null` for an original row. |
| `model.model_id` | Exact model identifier returned by the provider. |
| `model.provider_release` | Provider release identifier that scopes `model_id`, e.g. `openai/2026-08`. |
| `manifest_sha256` | SHA-256 of the pinned BOCG release manifest (`bocg-release-manifest.json`). |
| `scenario_sha256` | SHA-256 of the scenario/task contract executed. |
| `replicates` | Number of independent replicates executed for this model/scenario pair (>= 1). |
| `judge_ids` | Non-empty list of distinct judge identifiers that rendered the verdict. |
| `pass_rule_ref` | Reference to the pass rule applied (e.g. `five-families/intersection-union/v1`). |
| `verdict` | One of `PASS`, `FAIL`, `UNCERTAIN`, `NOT_APPLICABLE`, reusing the five-families vocabulary (`specs/rubrics/five-families.yaml`). |
| `freeze.runner_sha256` | SHA-256 of the runner/evaluation harness code artifact. |
| `freeze.clean_tree` | `true` iff the runner executed against a clean source tree. |
| `evidence_ref` | SHA-256 of the sealed run bundle that supports the verdict. |

## Verdict vocabulary

The four verdicts are taken directly from the five-families rubric
(`specs/rubrics/five-families.yaml`):

- `PASS` — the scenario's canonical claim is satisfied under the pass rule.
- `FAIL` — the claim is not satisfied.
- `UNCERTAIN` — the evidence does not establish a definitive pass or fail.
- `NOT_APPLICABLE` — the scenario or rule does not apply to this model/scenario pair.

## Immutability and corrections

Rows are immutable. A correction appends a new row that references the old row by
`replaces_row_sha256`. Consumers that replay history must process rows in order and
apply corrections so that the latest row for a given logical evaluation supersedes
earlier rows. Deleting a row is prohibited.

## Conformance

`tools/gate_conformance.py` validates that:

- the schema is a valid JSON Schema,
- the example fixture is valid against the schema,
- every row's `row_sha256` matches the canonical JSON digest of the row excluding `row_sha256`,
- every `replaces_row_sha256` (if non-null) resolves to an earlier row in the ledger,
- verdict values belong to the five-families vocabulary.
