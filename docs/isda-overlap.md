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
| `cp_aana_umr_scope` | `collateral_margin_management` | AANA computation and documentation for UMR in-scope status. |
| `cp_csa_vm_call_timeline` | `collateral_margin_management` | Daily CSA variation-margin call within the regulatory timeline. |
| `cp_simm_im_dispute` | `collateral_margin_management` | Investigation and resolution of SIMM IM differences above the dispute threshold. |
| `cp_umr_im_segregation` | `collateral_margin_management` | Regulatory IM calculation, segregated posting and segregation evidence. |
| `cp_otc_derivatives_confirmation_reconciliation` | `trade_lifecycle_operations` | OTC derivative confirmation and portfolio reconciliation against counterparty data. |
| `cp_derivatives_transaction_reporting_uti_upi` | `regulatory_transaction_reporting` | UTI/UPI generation, validation and pair-matching for OTC derivative transaction reports. |
| `cp_credit_event_determination_committee_application` | `credit_trading` | Application of ISDA Determinations Committee outcomes to credit derivatives positions. |
| `cp_dc_outcome_application` | `credit_trading` | Re-papering, cash settlement or position adjustment after a DC resolution, with product-control confirmation. |
| `cp_derivatives_documentation_execution` | `client_lifecycle_kyc` | Execution and capture of ISDA Master, CSA, GMRA, GMSLA and protocol adherence. |
| `cp_cftc_part43_realtime` | `regulatory_transaction_reporting` | Real-time public swap reports under CFTC Part 43. |
| `cp_emir_refit_uti_pairing` | `regulatory_transaction_reporting` | UTI generation, pairing and TR reconciliation under EMIR REFIT. |
| `cp_mifir_art26_t1_submission` | `regulatory_transaction_reporting` | Complete MiFIR Article 26 report by T+1. |
| `cp_otc_confirmation_timeliness` | `trade_lifecycle_operations` | Uncleared OTC confirmations issued and matched within the regulatory deadline. |
| `cp_portfolio_reconciliation` | `trade_lifecycle_operations` | Periodic portfolio reconciliation and valuation/term-break resolution. |
| `cp_reporting_error_remediation` | `regulatory_transaction_reporting` | Remediation and notification of identified reporting errors. |

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

## Lexical overlap in the provisional live run

The following tables are structural and lexical, not validated consensus. Counts
are raw mentions across model-sampled terminality tasks in
`live-run-20260826/normalised.json`; ISDA publisher anchors are `a3_market_size`
entries whose publisher is "ISDA". The live run remains PROVISIONAL.

| Division key | Live-run support | Tier | ISDA-adjacent terminality mentions | ISDA publisher anchors |
|---|---:|---|---:|---:|
| `collateral_margin_management` | 1 | WEAK | 11 | 4 |
| `xva_counterparty_risk` | 2 | WEAK | 8 | 1 |
| `credit_trading` | 4 | MODERATE | 6 | 0 |
| `repo_secfin_collateral` | 2 | WEAK | 4 | 0 |
| `buyside_trading_execution` | 3 | WEAK | 3 | 0 |
| `cross_asset_structuring` | 1 | WEAK | 2 | 0 |
| `equity_derivatives_structured` | 2 | WEAK | 2 | 0 |
| `rates_trading` | 4 | MODERATE | 2 | 0 |
| `trade_lifecycle_operations` | 3 | WEAK | 2 | 0 |
| `client_lifecycle_kyc` | 0 | WEAK | 1 | 0 |
| `fx_trading` | 3 | WEAK | 1 | 0 |
| `model_risk_management` | 0 | WEAK | 1 | 0 |

Counts are not importance scores. `client_lifecycle_kyc` and
`model_risk_management` have live-run support of zero, so their single
ISDA-adjacent mention is lexical residue, not a confirmed division.

### ISDA-relevant public regimes per key

| Division key | Selected ISDA-relevant public regimes |
|---|---|
| `credit_trading` | Real-time public reporting of swap transaction data; MiFIR post-trade transparency for bonds and credit derivatives; Short Selling Regulation sovereign and CDS restrictions |
| `collateral_margin_management` | BCBS-IOSCO non-cleared margin; EMIR risk-mitigation margin RTS; CFTC/SEC uncleared swap margin; UMR |
| `xva_counterparty_risk` | Uncleared margin rules; BCBS-IOSCO non-cleared margin requirements |
| `repo_secfin_collateral` | SFTR securities financing transaction reporting; US Treasury clearing mandate for eligible repo |
| `trade_lifecycle_operations` | EMIR timely confirmation and portfolio reconciliation; CFTC swap confirmation; CSDR settlement discipline |
| `rates_trading` | CFTC swap-data reporting and swap-dealer business conduct; MiFIR derivatives trading obligation |
| `client_lifecycle_kyc` | Swap dealer documentation and relationship-documentation requirements |

### What ISDA's stack models versus what the grid models

| ISDA layer | Typical ISDA concern |
|---|---|
| Trade | Execution, confirmation, affirmation, allocation |
| Event | Credit events, lifecycle events, determinations, auctions, settlements |
| Legal agreement | ISDA Master, CSA, Schedule, protocol adherence |
| Report | Regulatory reporting, taxonomy, market-size surveys |

| Grid layer | Grid concern |
|---|---|
| Division | Operational division of a global bank |
| Function | Principal human seat inside the division |
| Control point | Publicly citable checkpoint where a failure has a priced consequence |
| Priced failure | Failure class with a public cost anchor (SPEC-03 I2) |

The overlap is diagonal, not one-to-one. ISDA's trade layer crosses
`trade_lifecycle_operations`, `rates_trading`, `credit_trading` and
`client_lifecycle_kyc`. The event layer concentrates in `credit_trading`. The
legal-agreement layer is most visible in `collateral_margin_management`,
`repo_secfin_collateral` and `xva_counterparty_risk`. The report layer appears
mainly as market-size anchors, not as a division.
