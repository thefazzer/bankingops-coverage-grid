# ISDA regulatory overlap in the BankingOps Coverage Grid

This document records the ISDA regulatory overlap work completed under
[`thefazzer/bankingops-coverage-grid#6`](https://github.com/thefazzer/bankingops-coverage-grid/issues/6).
It stays above the SPEC-03 floor: definitions, schemas, rubrics, public citations
and conformance gates. It does not contain institution instances, corpus material
or workflow claims.

## Why the overlap matters

ISDA's regulatory footprint (UMR/SIMM margin, OTC confirmation and portfolio
reconciliation, EMIR/CFTC/MiFIR transaction reporting, netting enforceability,
Determinations Committee outcomes) touches roughly ten of the 42 admitted BOCG
division keys and about 77 of the 1,025 catalogue definitions in
`reference/operating-catalogue.v1.json`. Before this epic the public layer had no
ISDA-native control-point cells and no standards-backed way to cite ISDA public
artefacts.

## What changed

### SPEC-04 — Common semantic profile

- Added ISDA public standards to the standards layer:
  - **Common Domain Model (CDM)** — `https://cdm.finos.org/`
  - **FpML** — `https://www.fpml.org/`
  - **ISO 4914 UPI** — `https://www.anna-dsb.com/upi/`
  - **ISO 20022** — `https://www.iso20022.org/`
- Promoted `derivatives_documentation_control` to the
  `candidate_vocabulary_gaps` list because the current division key
  `client_lifecycle_kyc` had zero model support in the live run and does not
  adequately represent ISDA Master / CSA / GMRA / GMSLA execution and protocol
  adherence.

### Control-point cells

Five new `status: PROPOSED` cells were authored. They are intentionally
solution-neutral and cite only public sources.

| Cell | Division | Control point |
|---|---|---|
| `cp_simm_initial_margin_reconciliation` | `collateral_margin_management` | Bilateral agreement of SIMM initial margin before the regulatory settlement deadline. |
| `cp_otc_derivatives_confirmation_reconciliation` | `trade_lifecycle_operations` | OTC derivative confirmation and portfolio reconciliation against counterparty data. |
| `cp_derivatives_transaction_reporting_uti_upi` | `regulatory_transaction_reporting` | UTI/UPI generation, validation and pair-matching for OTC derivative transaction reports. |
| `cp_credit_event_determination_committee_application` | `credit_trading` | Application of ISDA Determinations Committee outcomes to credit derivatives positions. |
| `cp_derivatives_documentation_execution` | `client_lifecycle_kyc` | Execution and capture of ISDA Master, CSA, GMRA, GMSLA and protocol adherence. |

Two existing `failure_class` values — `margin_dispute` and `reporting_rejection` —
are now exercised by the new cells.

### SPEC-07 — Replayable compliance scenario contract

- Added `specs/SPEC-07-replayable-compliance-scenario.md`.
- Added `specs/replayable-compliance-scenario.schema.json`, which composes:
  - a BOCG release pinned by manifest hash;
  - one control-point cell pinned by `cell_id` and SHA-256;
  - one operating-catalogue task pinned by `division_key` and `reference_id`;
  - a bounded synthetic input state;
  - a public oracle (regulatory clause, standard rule set, reference table or
deterministic function);
  - a closed-set expected verdict (`compliant`, `non_compliant`, `indeterminate`,
`out_of_scope`);
  - a deterministic scenario hash.
- Added `specs/scenario-run-ledger.schema.json` to record model release,
manifest hash, scenario hash and actual verdict.

### SPEC-05 — Time and deadline semantics

- Extended `specs/insight-construction.schema.json` with `TemporalAnchor` and
  `DeadlineConstraint` definitions.
- Extended `specs/institutional-speech-act.schema.json` with optional deadline
  constraints on the obligation frame.
- Added temporal semantics to `specs/insight-construction-profile.yaml`:
  observation time is not validity time; scheduled time does not prove execution;
  unknown bounds remain unknown.
- Documented the semantics in `specs/SPEC-05-insight-construction.md`.

### G6 corroboration priority

- Drafted `drafts/2026-09-20-isda-g6-corroboration-priority.md` with a ranked
  list of ISDA-adjacent division keys for hand-corroboration.
- Initialised `live-run-20260826/corroboration.csv` (1015 rows) and
  `corroboration_summary.json` from the published anchor pool. Every row is
  `UNVERIFIED`; G6 still fails for the honest reason (unverified anchors) rather
  than a missing ledger.
- Kept the `glm-5.2` exclusion: retry did not yield three valid samples.
- The live run remains PROVISIONAL; this epic records the priority order and
  the ledger skeleton but does not claim any anchor has been verified.

## Conformance

All changes are gated by the existing conformance tooling:

```bash
python3 tools/gate_conformance.py
python3 tools/build_operating_catalogue.py --check
(cd bocg && pytest -q)
(cd lat && pytest -q)
```

## What is deliberately not in scope

- Institution instances, desk configurations, or private evidence.
- Claims that any model, benchmark or environment satisfies a cell.
- Live Determinations Committee outcomes, trade data or UPI values.
- Corpus-side oracle adapters or regression runs (those live in the private
  FinExhaust repo and flow back as counts and hashes only).

## References

- `specs/common-semantic-profile.yaml`
- `specs/SPEC-04-common-semantic-profile.md`
- `specs/SPEC-05-insight-construction.md`
- `specs/SPEC-07-replayable-compliance-scenario.md`
- `specs/replayable-compliance-scenario.schema.json`
- `specs/scenario-run-ledger.schema.json`
- `specs/insight-construction.schema.json`
- `specs/institutional-speech-act.schema.json`
- `drafts/2026-09-20-isda-g6-corroboration-priority.md`
