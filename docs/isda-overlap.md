# ISDA overlap note: where the grid's divisions touch ISDA-native concepts

```
ARTIFACT : overlap note (non-normative; not a manifest artifact; not a coverage claim)
AS OF    : 2026-09-20
SOURCE   : lexical inspection of the provisional live run in live-run-20260826/
RULE     : the grid is a model-consensus prior; this note is structural and lexical,
           not validated consensus; ISDA-relevant keys are WEAK
```

## 0. Why this note exists

Several divisions named by the provisional live run contain tasks, input records or
regime anchors that refer to ISDA standards, documentation families or governance
processes. This note records where that overlap is visible in the public artifact so
that consumers do not read it as an endorsement, a coverage claim or a statement that
the grid has validated ISDA's taxonomy against bank operations. It is a vocabulary
observation, not a manifest item.

Everything below is scoped to the model-consensus prior in `live-run-20260826/`, which
remains **PROVISIONAL** (G6 corroboration outstanding). The ISDA-relevant keys are
predominantly in the **WEAK** tier of the live run. The overlap is structural and
lexical, not validated consensus.

## 1. Division keys with ISDA-adjacent material

The table lists admitted division keys whose terminality tasks or market-size anchors
mention ISDA standards, ISDA documentation families (ISDA Master, ISDA confirmation,
ISDA definitions), CSA/GMRA/GMSLA margin or collateral agreements, the ISDA Standard
Initial Margin Model (SIMM), or ISDA Determinations Committee processes. Counts are
raw mentions across the model-sampled terminality tasks in `normalised.json`; anchor
counts are `a3_market_size` entries whose `publisher` is "ISDA".

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

Reading notes:

- The counts are not weighted by importance. A mention of "ISDA SIMM" in a margin
calculation task is one mention; so is a generic "ISDA/CSA" in a counterparty-eligibility
check. Counts should not be compared across keys as scores.
- `client_lifecycle_kyc` and `model_risk_management` have live-run support of zero,
so their single ISDA-adjacent mention is a lexical residue, not a confirmed division.
- `credit_trading` is the only MODERATE-tier key in this list whose overlap is driven
by ISDA-native failure processes (credit events, Determinations Committee decisions,
CDS auction settlement). `rates_trading`'s overlap is instead documentation-level
(swap confirmation, ISDA Master matching).

## 2. ISDA-relevant regimes per key

The regulatory anchors (`a1_regulatory`) that touch ISDA's domain are not ISDA regimes
as such; they are public rules that reference the same instruments ISDA standardises.
The most relevant are:

| Division key | Selected ISDA-relevant public regimes |
|---|---|
| `credit_trading` | Real-time public reporting of swap transaction data (credit default swaps); MiFIR post-trade transparency for bonds and credit derivatives; Short Selling Regulation — sovereign and CDS restrictions |
| `collateral_margin_management` | BCBS-IOSCO margin requirements for non-centrally cleared derivatives; EMIR risk-mitigation margin RTS; CFTC/SEC uncleared swap margin rules; UMR |
| `xva_counterparty_risk` | Uncleared margin rules (initial and variation margin); BCBS-IOSCO non-cleared margin requirements |
| `repo_secfin_collateral` | SFTR securities financing transaction reporting; US Treasury clearing mandate for eligible repo transactions |
| `trade_lifecycle_operations` | EMIR timely confirmation and portfolio reconciliation for uncleared OTC derivatives; CFTC swap confirmation requirements for swap dealers; CSDR settlement discipline |
| `rates_trading` | CFTC swap data reporting and swap-dealer business conduct; MiFIR derivatives trading obligation and transaction reporting |
| `client_lifecycle_kyc` | Swap dealer documentation and relationship documentation requirements |

These regimes are cited by the models as public anchors; they do not establish that
the division key is correctly bounded or that ISDA's taxonomy maps cleanly onto it.

## 3. The two ISDA-native failure classes visible in the grid

ISDA itself publishes standard documentation and governs determinations processes;
the grid's model-generated terminality tasks touch two ISDA-native priced-failure
classes most directly:

1. **Documentation / confirmation mismatch.** Tasks mention confirming ISDA swap terms,
matching ISDA confirmations to term sheets, validating CSA terms in collateral systems,
and reconciling GMRA/GMSLA documentation for repo and securities financing. The priced
failure is operational: an unmatched or mis-captured term produces a trade dispute,
failed settlement or wrong margin call.

2. **Credit event determination and auction settlement.** Tasks in `credit_trading`
mention applying ISDA Determinations Committee decisions, handling CDS credit events
and auction settlements, and validating reference entities and restructuring clauses
against ISDA credit derivatives definitions. The priced failure is contractual: a wrong
application of a determination or auction result produces a settlement mismatch or
PvL hit.

A third cluster — SIMM / initial-margin calculation and dispute resolution — appears in
`collateral_margin_management`, `xva_counterparty_risk` and `model_risk_management`, but
that cluster is anchored in public margin rules rather than in an ISDA pricing failure
as such; ISDA SIMM is the methodology, while the priced failure sits in the regulatory
margin regime.

## 4. What ISDA's stack models versus what the grid models

ISDA's public taxonomy is built around the lifecycle of a derivatives contract and its
supporting infrastructure:

| ISDA layer | Typical ISDA concern |
|---|---|
| Trade | Execution, confirmation, affirmation, allocation |
| Event | Credit events, lifecycle events, determinations, auctions, settlements |
| Legal agreement | ISDA Master, CSA, Schedule, Protocol adherence |
| Report | Regulatory reporting, taxonomy, market-size surveys |

The grid instead models banking operations from the outside in:

| Grid layer | Grid concern |
|---|---|
| Division | Operational division of a global bank (sell-side or buy-side counterpart) |
| Function | Principal human seat inside the division |
| Control point | Publicly citable checkpoint where a failure has a priced consequence |
| Priced failure | Failure class with a public cost anchor (SPEC-03 I2) |

The overlap is therefore diagonal, not one-to-one:

- ISDA's "trade" layer crosses `trade_lifecycle_operations`, `rates_trading`,
`credit_trading`, `cross_asset_structuring` and parts of `client_lifecycle_kyc`.
- ISDA's "event" layer concentrates in `credit_trading` (Determinations Committee,
CDS auction) and touches `equity_derivatives_structured` and `trade_lifecycle_operations`
(corporate action adjustments, fixings).
- ISDA's "legal agreement" layer is most visible in `collateral_margin_management`
(CSA), `repo_secfin_collateral` (GMRA/GMSLA), `xva_counterparty_risk` (netting
opinions, CSA ingestion) and `rates_trading` / `credit_trading` (confirmation matching).
- ISDA's "report" layer overlaps only as market-size anchors (`ISDA Margin Survey`)
under `collateral_margin_management` and `xva_counterparty_risk`; the grid does not
treat reporting as a division in itself.

## 5. Explicit caveat

- The live run is **PROVISIONAL**; no anchor has been hand-corroborated (G6 still FAILS
in `live-run-20260826/RUN_SUMMARY.json`).
- The ISDA-relevant keys are **WEAK** in the live run, except `credit_trading` and
`rates_trading` (MODERATE). WEAK means the model-consensus prior is thin; a lexical
overlap is not a validation.
- This note is **non-normative** and is **not a manifest artifact**. It is not listed in
`bocg-release-manifest.json` and does not create or fill any `corpus_coverage` field in
the cells.
- The overlap is **structural and lexical**, not validated consensus. A division key
mentioning "ISDA" in a task string is not evidence that the bank division exists, that
ISDA would recognise the key, or that any specific control point is covered.
- Consumers looking for authoritative ISDA definitions should consult ISDA's own
documentation, not this grid.

## 6. Links

- Provisional live run: `live-run-20260826/`
- Division aliases and merge rationale: `live-run-20260826/aliases.yaml`
- Coverage matrix: `live-run-20260826/matrix.csv`
- Control-point cells (when they land): `cells/`
- SPEC-07 — division/function/control-point catalogue (when it lands): `specs/SPEC-07-divisions-cells-and-regimes.md`

This note may be revised without a release.
