# bankingops — BankingOps Coverage Grid + Lineage Attestation Toolkit

Two artifacts: a reproducible way to derive a taxonomy of banking operational divisions from base-model
consensus (rather than from one person's assertion), and a toolkit that makes provenance claims about a
derived corpus machine-verifiable by a party who never sees the source material.

`live-run-20260826/` holds a real run of the first: five vendor families, cold, with every raw response published.
It is **provisional** — the anchor-corroboration gate has not been satisfied. See that folder's README.

The grid is a model-consensus prior, not a validated map. `docs/downstream-evidence.md` records how its division keys
have been exercised by a preregistered downstream evaluation lane; those results are calibration evidence from a private
corpus (one institution, not released) and are not validation of the grid.
`docs/isda-overlap.md` records the ISDA regulatory overlap work and where the
provisional live run touches ISDA standards and governance processes. The note
does not claim validated consensus.

| Artifact | Spec | Package | CLI | Tests |
|---|---|---|---|---|
| **BankingOps Coverage Grid (BOCG)** — model-consensus taxonomy of capital-markets operational divisions, anchored + corroborated, with runnable gates | `specs/SPEC-01-coverage-grid-elicitation.md` | `bocg/` | `bocg` | 93 passing |
| **Lineage Attestation Toolkit (LAT)** — span commitments, per-atom lineage classes, salted canaries, sealed holdout, buyer/examiner verification, runnable gates | `specs/SPEC-02-lineage-attestation.md` | `lat/` | `lat` | 70 passing |
| **Common semantic profile** — standards-backed meanings for existing division, function, control-point, evidence and coverage fields; explicitly stops above institution workflow | `specs/SPEC-04-common-semantic-profile.md` | `specs/common-semantic-profile.yaml` | `python3 tools/gate_conformance.py` | conformance gate |
| **Insight-construction profile** — portable Atom, Trace, Episode, institutional speech-act and adjudication definitions; definitions only, never institution instances | `specs/SPEC-05-insight-construction.md` | `specs/insight-construction-profile.yaml` | `python3 tools/gate_conformance.py` | lifecycle + rubric gates |
| **Release manifest** — content-addressed assertion of the exact public specs, semantic profile, cells and release-run artifacts consumed at runtime | `specs/bocg-release-manifest.schema.json` | release asset `bocg-release-manifest.json` | `python3 tools/build_release_manifest.py --tag <tag> --commit <sha> --output bocg-release-manifest.json` | self-hash + per-artifact hashes |
| **Task concepts + episode surface** — grouped function/task definitions with per-division provenance (machine-clustered AUTO or argued REVIEWED) and the instance-free shape that records how deep an Episode's ratified evidence binds to the grid | `specs/SPEC-08-task-concepts-and-episode-surface.md` | `reference/task-concepts.v1.json` + `reference/task-concept-rulings.yaml` + `specs/task-concepts.schema.json` + `specs/episode-surface.schema.json` | `python3 tools/build_task_concepts.py --check`; `python3 tools/episode_surface.py <surface.json>` | S8 gates |
| **Public-eval surface overlay** — likelihood-matched projection of public rubrics/benchmarks/evals onto the SPEC-08 depth ladder; division roll-up of saturation vs admitted voids | `specs/SPEC-09-public-eval-surface-overlay.md` | `reference/public-eval-inventory.v1.yaml` + `reference/public-eval-surface-map.v1.json` + `specs/public-eval-surface-overlay.schema.json` | `python3 tools/public_eval_overlay.py check` | S9 gates |
| **Compliance scenario** — replayable, manifest-pinned contract that composes a control-point cell, terminality task, input state, oracle and expected verdict | `specs/SPEC-07-replayable-compliance-scenario.md` + `specs/SPEC-07-compliance-scenario.md` | `specs/replayable-compliance-scenario.schema.json` + `specs/compliance-scenario.schema.json` + `specs/fixtures/compliance-scenario-synthetic.json` | `python3 tools/gate_conformance.py` | S7 gate |

The benchmark that sits in the seller's own cell is the **PB-Ops Eval**; it is deliberately *not* referenced anywhere in the BOCG elicitation assets (invariant I2, gate G1).

## Operating reference contract — v0.4.0

[ SPEC-06 ](specs/SPEC-06-operating-reference.md) adds a stable reference catalogue
and a schema for consumer-owned desk/business-unit registers. Public definitions
are derived from the existing grid; named units, configurations and evidence stay
with the consuming institution. The release manifest pins the contract, schema
and catalogue so downstream products can verify dependency upgrades.

## Task concepts and episode surface — v0.6.0

[ SPEC-08 ](specs/SPEC-08-task-concepts-and-episode-surface.md) groups the released
function and task labels into concepts one division at a time and states, per
division, whether the grouping was machine-clustered (`AUTO`, unread) or argued
under a named ruling (`REVIEWED`). In v0.6.0 one division is reviewed
(prime brokerage and client financing: two argued task merges and one argued
function merge, 23 aliases) and 41 are machine-clustered. The catalogue, matrix
and cells are unchanged. The episode surface is the consumer-owned shape for
recording which concepts, released tasks and control points one Episode touches
and how deep its ratified evidence goes; candidates never raise that depth.

## Public-eval surface overlay — SPEC-09

[ SPEC-09 ](specs/SPEC-09-public-eval-surface-overlay.md) supplements the grid with
a public rubric/benchmark/eval overlay likelihood-matched to the SPEC-08 depth
ladder. Only third-party public eval inventory classes paint; BOCG cell citations
and own rubrics do not. Capital-markets / IB public benches (Mercor APEX,
Rogo Big Finance Bench, Handshake BankerToolBench) hydrate the inventory and
paint advisory / research / capital-markets divisions alongside the Harvey LAB
seed. A derived division roll-up in the map reports saturation vs voids. Voids
are admitted BOCG surface without painted public-eval touch — not elicited
competency gaps (I7). Presentation style is left to consumers.

## Tags (for search)
BankingOps Coverage Grid, PB-Ops Eval, FinExhaust, BankingEnv, model consensus taxonomy, benchmark ceiling, frontier saturation, sealed holdout, rubric design, capital markets eval gap, seat-cost filter, terminality test, corroboration ledger, lineage attestation, span commitment, salted canary, pseudonymisation, clean room, buyer-counsel attestation, runnable gates, provenance manifest.

## Quickstart (Python ≥ 3.11)

```bash
pip install -e bocg -e lat pytest
(cd bocg && pytest -q) && (cd lat && pytest -q)
```

BOCG fixture-mode end-to-end (no API keys, no network):
```bash
cd bocg && F=tests/fixtures
bocg run --fixtures $F --panel $F/panel-fixtures.yaml -w work
bocg normalise --aliases $F/aliases.yaml -w work && bocg matrix -w work
bocg corroborate --ledger $F/corroboration_all_verified.csv -w work
bocg grid -w work && bocg coverage --own-cell $F/own_cell.json -w work
bocg gate all -w work && bocg bundle -w work
```
Live mode: copy `bocg/examples/panel.yaml`, set provider API keys in env, drop `--fixtures`. Run ALL models before any human reads any response (§4 ORDER); author `aliases.yaml` only after runs complete (§5.2).

LAT end-to-end on synthetic fixtures:
```bash
mkdir demo && cd demo && export LAT_VAULT_KEY_FILE=$PWD/vault.key
lat fixtures generate -w . --n-docs 12 --seed 1
lat vault init -w . && lat manifest build -w . && lat redact -w . --mode pseudonymise
lat lineage build -w . && lat ratios -w .
lat canary register -w . --package-id P001 --recipient buyer-acme && lat holdout commit -w .
lat package build -w . --package-id P001 --recipient buyer-acme     # runs gates G1–G9
lat verify --mode buyer --package pkg-P001                           # V1–V7, no vault needed
lat keygen --out examiner.key
lat verify --mode examiner --package pkg-P001 --vault vault --sample 50 --seed 7 --examiner-key examiner.key --gazetteers gazetteers
```
Point LAT at the real corpus by replacing `lat fixtures generate` with your own `docs/` + `gazetteers/`; import the existing BTC-anchored hash set with `lat manifest build --import-v0 <hashes.txt>`.

## Known deviations from spec (documented in each package README)
- BOCG: the frozen prompt's own negative instructions contain "under-served"; an explicit allowlist of those sentences is stripped before G1/G8 scanning (otherwise the spec's own prompt could never pass its own gate).
- LAT: OpenTimestamps anchoring is a stub (interface only, no network); canary "field-ordering" carrier not implemented (canonical JSON would erase it); NER is a rule/gazetteer baseline behind a pluggable `Detector` protocol.

## What LAT proves / does not prove
Proves: integrity vs anchored manifest, delta-only-at-committed-positions, per-atom lineage class + ratios, canary recipient recovery, holdout commitment. Does **not** prove: semantic safety of kept text, correctness of doctrine, or absence of re-identification via operational detail (flagged heuristically by the residual scan, never claimed).
