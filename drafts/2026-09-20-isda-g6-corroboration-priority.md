# ISDA-adjacent G6 corroboration priority

Status: PROVISIONAL. This draft records the priority order for hand-corroborating
anchors of the ISDA-adjacent division keys. It does not claim any anchor has been
verified.

## Priority rationale

G6 of SPEC-01 requires every anchor to be verified by a human or agent against
the actual cited source before a division is treated as corroborated. The live
run (2026-08-26) is PROVISIONAL because G6 is not satisfied for any division.

ISDA's regulatory footprint directly touches roughly ten division keys in the
BOCG grid. To close the overlap gap in the taxonomy itself, corroboration should
start with the divisions that are (a) most strongly named by the model panel,
(b) already linked to ISDA-native regulation in their A1 anchors, and (c) most
relevant to the new control-point cells added in this epic.

## Priority order

| Rank | Division key | Tier | Model support | Rationale |
|---|---|---|---|---|
| 1 | `prime_brokerage_financing` | MODERATE | 5 | Highest panel support; SA-CCR / SFT margin anchors are public BIS/SEC/CFTC material and directly relevant to ISDA GMRA / SIMM collateral workflows. |
| 2 | `credit_trading` | MODERATE | 4 | Strong support; ISDA Credit Derivatives Determinations Committee and 2014 Definitions are the canonical public source for the credit-event lifecycle cell. |
| 3 | `rates_trading` | MODERATE | 4 | Strong support; CFTC swap-data-reporting and FRTB anchors are public and map to SIMM / clearing documentation. |
| 4 | `collateral_margin_management` | WEAK | 1 | Low model support but the only division that directly hosts SIMM initial-margin and margin-dispute controls; corroboration here validates the new margin cell. |
| 5 | `trade_lifecycle_operations` | WEAK | 3 | Hosts the OTC confirmation / portfolio-reconciliation cell; CFTC Part 23 and ISDA documentation are public. |
| 6 | `regulatory_transaction_reporting` | WEAK | 1 | Hosts the UTI/UPI reporting cell; EMIR Refit and CFTC Part 45 are public, but model support is thin. |
| 7 | `xva_counterparty_risk` | WEAK | 2 | SA-CCR / CVA risk capital anchors are public, but relevance to the new cells is indirect. |

## Suggested verification sources

- `prime_brokerage_financing`: BIS SA-CCR standard text; SEC Net Capital Rule 15c3-1; large-bank 10-K FICC / prime services segment disclosures.
- `credit_trading`: ISDA DC Rules and public DC question/result archive; ISDA 2014 Credit Derivatives Definitions; FINRA TRACE rule 6730.
- `rates_trading`: CFTC 17 CFR Part 43 / 45; BCBS FRTB standard; bank 10-K rates/FICC disclosures.
- `collateral_margin_management`: BCBS-IOSCO margin framework; ISDA SIMM specification; CFTC/ESMA margin rules.
- `trade_lifecycle_operations`: CFTC 17 CFR 23.501; ISDA confirmation and reconciliation guidance.
- `regulatory_transaction_reporting`: ESMA RTS 22; CFTC Part 45; ISO 4914 UPI standard.
- `xva_counterparty_risk`: Basel CVA risk capital framework; BCBS-IOSCO margin framework.

## Definition of done for G6 on these keys

For each key, at least one A1 regulatory anchor and one A2 segment anchor are
verified against the original public source, and the verification is recorded in
the corroboration ledger with reviewer reference, source URL and checked date.
