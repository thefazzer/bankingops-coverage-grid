# bankingops — BankingOps Coverage Grid + Lineage Attestation Toolkit

Two artifacts: a reproducible way to derive a taxonomy of banking operational divisions from base-model
consensus (rather than from one person's assertion), and a toolkit that makes provenance claims about a
derived corpus machine-verifiable by a party who never sees the source material.

`live-run-20260826/` holds a real run of the first: five vendor families, cold, with every raw response published.
It is **provisional** — the anchor-corroboration gate has not been satisfied. See that folder's README.

The grid is a model-consensus prior, not a validated map. `docs/downstream-evidence.md` records how its division keys
have been exercised by a preregistered downstream evaluation lane; those results are calibration evidence from a private
corpus (one institution, not released) and are not validation of the grid.

| Artifact | Spec | Package | CLI | Tests |
|---|---|---|---|---|
| **BankingOps Coverage Grid (BOCG)** — model-consensus taxonomy of capital-markets operational divisions, anchored + corroborated, with runnable gates | `specs/SPEC-01-coverage-grid-elicitation.md` | `bocg/` | `bocg` | 87 passing |
| **Lineage Attestation Toolkit (LAT)** — span commitments, per-atom lineage classes, salted canaries, sealed holdout, buyer/examiner verification, runnable gates | `specs/SPEC-02-lineage-attestation.md` | `lat/` | `lat` | 70 passing |
| **Common semantic profile** — standards-backed meanings for existing division, function, control-point, evidence and coverage fields; explicitly stops above institution workflow | `specs/SPEC-04-common-semantic-profile.md` | `specs/common-semantic-profile.yaml` | `python3 tools/gate_conformance.py` | conformance gate |
| **Insight-construction profile** — portable Atom, Trace, Episode, institutional speech-act and adjudication definitions; definitions only, never institution instances | `specs/SPEC-05-insight-construction.md` | `specs/insight-construction-profile.yaml` | `python3 tools/gate_conformance.py` | lifecycle + rubric gates |
| **Release manifest** — content-addressed assertion of the exact public specs, semantic profile, cells and release-run artifacts consumed at runtime | `specs/bocg-release-manifest.schema.json` | release asset `bocg-release-manifest.json` | `python3 tools/build_release_manifest.py --tag <tag> --commit <sha> --output bocg-release-manifest.json` | self-hash + per-artifact hashes |

The benchmark that sits in the seller's own cell is the **PB-Ops Eval**; it is deliberately *not* referenced anywhere in the BOCG elicitation assets (invariant I2, gate G1).

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
