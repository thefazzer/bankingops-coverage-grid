# Public-eval surface overlay — division choropleth

```
ARTIFACT : derived choropleth render (reproducible from public-eval-surface-map.v1.json)
RELEASE  : v0.6.0 / task_concepts_sha256=92f823baf46a…
GRAIN    : division (42 admitted keys)
PAINT    : QUALIFIED_MAPPING + RATIFIED_MAPPING on channel=public only
BANDS    : L1=1, L2=2, L3=3 (explainable likelihood weights)
VOID     : admitted division with zero painted public-eval rows
NOT      : a competency score, an under-served claim (I7), or institution coverage
```

## Legend

| Symbol | Meaning |
|---|---|
| saturation N | weighted sum of painted rows (L1=1, L2=2, L3=3) |
| VOID | admitted BOCG surface with no painted public-eval touch |
| matrix_tier | live-run consensus tier (panel density), not eval density |
| review_status | SPEC-08 AUTO (machine prior) or REVIEWED (argued merges) |

## Summary

- Admitted divisions: **42**
- Painted divisions: **6**
- Void divisions: **36**
- Painted rows: **19**
- Max saturation: **14**

## Choropleth (division grain)

| Division | Tier | Review | Painted | Saturation | Void |
|---|---|---|---:|---:|---|
| `collateral_margin_management` | WEAK | AUTO | 5 | 14 ██████████ |  |
| `regulatory_transaction_reporting` | WEAK | AUTO | 5 | 13 █████████░ |  |
| `trade_lifecycle_operations` | WEAK | AUTO | 4 | 9 ██████░░░░ |  |
| `credit_trading` | MODERATE | AUTO | 2 | 6 ████░░░░░░ |  |
| `prime_brokerage_financing` | MODERATE | REVIEWED | 2 | 4 ███░░░░░░░ |  |
| `client_lifecycle_kyc` | WEAK | AUTO | 1 | 2 █░░░░░░░░░ |  |
| `buyside_investment_compliance` | WEAK | AUTO | 0 | 0 VOID | yes |
| `buyside_investment_operations` | WEAK | AUTO | 0 | 0 VOID | yes |
| `buyside_ldi_overlay` | WEAK | AUTO | 0 | 0 VOID | yes |
| `buyside_performance_risk_reporting` | WEAK | AUTO | 0 | 0 VOID | yes |
| `buyside_portfolio_management` | WEAK | AUTO | 0 | 0 VOID | yes |
| `buyside_trading_execution` | WEAK | AUTO | 0 | 0 VOID | yes |
| `capital_markets_origination_combined` | WEAK | AUTO | 0 | 0 VOID | yes |
| `commodities_physical_operations` | WEAK | AUTO | 0 | 0 VOID | yes |
| `commodities_trading` | MODERATE | AUTO | 0 | 0 VOID | yes |
| `cross_asset_structuring` | WEAK | AUTO | 0 | 0 VOID | yes |
| `custody_asset_servicing` | WEAK | AUTO | 0 | 0 VOID | yes |
| `dcm_origination` | WEAK | AUTO | 0 | 0 VOID | yes |
| `ecm_origination` | WEAK | AUTO | 0 | 0 VOID | yes |
| `electronic_execution` | WEAK | AUTO | 0 | 0 VOID | yes |
| `em_trading` | WEAK | AUTO | 0 | 0 VOID | yes |
| `equities_trading` | MODERATE | AUTO | 0 | 0 VOID | yes |
| `equity_derivatives_structured` | WEAK | AUTO | 0 | 0 VOID | yes |
| `ficc_combined` | WEAK | AUTO | 0 | 0 VOID | yes |
| `fx_trading` | WEAK | AUTO | 0 | 0 VOID | yes |
| `institutional_sales_coverage` | WEAK | AUTO | 0 | 0 VOID | yes |
| `leveraged_finance_loan_capital_markets` | WEAK | AUTO | 0 | 0 VOID | yes |
| `listed_derivatives_client_clearing` | WEAK | AUTO | 0 | 0 VOID | yes |
| `ma_advisory` | WEAK | AUTO | 0 | 0 VOID | yes |
| `macro_combined_rates_fx_em` | WEAK | AUTO | 0 | 0 VOID | yes |
| `market_risk_management` | WEAK | AUTO | 0 | 0 VOID | yes |
| `market_risk_valuation_control` | WEAK | AUTO | 0 | 0 VOID | yes |
| `model_risk_management` | WEAK | AUTO | 0 | 0 VOID | yes |
| `municipal_public_finance` | WEAK | AUTO | 0 | 0 VOID | yes |
| `product_control_ipv` | WEAK | AUTO | 0 | 0 VOID | yes |
| `rates_trading` | MODERATE | AUTO | 0 | 0 VOID | yes |
| `repo_secfin_collateral` | WEAK | AUTO | 0 | 0 VOID | yes |
| `securitised_products` | MODERATE | AUTO | 0 | 0 VOID | yes |
| `sellside_research` | WEAK | AUTO | 0 | 0 VOID | yes |
| `trade_surveillance` | WEAK | AUTO | 0 | 0 VOID | yes |
| `treasury_balance_sheet_funding` | WEAK | AUTO | 0 | 0 VOID | yes |
| `xva_counterparty_risk` | WEAK | AUTO | 0 | 0 VOID | yes |

## How to read voids vs saturation

Saturation concentrates where published control-point cells and argued public-eval
mappings already bind to the grid (often collateral, reporting, trade lifecycle,
credit). Voids are admitted divisions the overlay has not yet painted — they are
valid BOCG surface under seat/terminality/anchor rules, not elicited competency gaps.

Rebuild: `python3 tools/public_eval_overlay.py build && python3 tools/public_eval_overlay.py check`.
