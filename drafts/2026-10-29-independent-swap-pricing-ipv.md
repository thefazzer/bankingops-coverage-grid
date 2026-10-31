# DRAFT — independent swap-pricing / IPV coverage proposal

> **PROPOSAL ONLY**: this review does not accept a vocabulary gap, add a
> canonical term, or bind the source trace to BOCG.

Review basis: BOCG v0.7.0 (`06284f09f6367ca15df51d6463164a2120baa4ae`),
including all 315 operating definitions, 228 function/task concepts, and 17
control cells. This note is a non-normative review record; it changes no
catalogue, release artifact, trace outcome, or consumer pin.

## Synthetic evidence and limits

The source-equivalent excerpts, with source spelling retained:

> For Posrt Swap we also we need to support IPV to independently price a swap
>
> (Colleague 02 is creating the API/library but *putting in placeholders* for Portfolio Swap)

This supports an independent-pricing requirement and reported API/library work
with placeholders. It does not establish operational IPV execution, usable
pricing output, control ownership, or completion. The API/library work may
enable IPV rather than constitute IPV itself. Synthetic participant identity
and product label are not resolved to real identities or product scope;
authorship and event date remain unresolved.

Independent pricing could expose valuation discrepancies, but these excerpts
do not establish a discrepancy or quantify financial benefit or exposure. No
regulatory obligation, individual designation, or control owner is inferred.

## Coverage assessment

No reviewed v0.7.0 function/task concept explicitly represents independent
swap pricing or price verification. The nearest released references are related
but do not establish this purpose:

| Released reference | Catalogue purpose | Limit for this evidence |
|---|---|---|
| `task:equity_derivatives_structured:70260143deeff4fa00dc3c71` — **daily mark risk calculation** | Official marks and Greeks, with valuation-control sign-off. | Independent pricing might support marking, but official daily marking is not identified as the purpose. |
| `task:equity_derivatives_structured:024963f5f3b250a0e0b4c75e` — **price structured equity derivative or note** | Pricing and approval for a client quote. | Client-quote production and this product scope are not established. |
| `task:market_risk_management:ea3978263f9fe3f9907cf00c` — **validate risk model output** | Assessment against validation criteria and backtest data. | A pricing-library requirement does not establish model validation or its inputs. |
| `function:market_risk_management:0ec57c48f3f8573c02025f6c` — **Market risk management and control** | Broad market-risk function. | The source does not identify a controlling function or this specific context. |
| `cp_portfolio_reconciliation` | Periodic counterparty portfolio reconciliation, including valuation or term differences. | No counterparty comparison or reconciliation workflow is established. Independent pricing alone is not reconciliation. |

These are adjacent concepts, not a defensible existing mapping for the stated
independent-pricing purpose. Valuation is present in BOCG; the candidate gap is
specific to independent price verification, not valuation generally.

## Proposed disposition

Keep the trace unbound and its outcome open. Record a candidate for future
review: if operational evidence confirms a stable task within BOCG's remit,
consider a reference that distinguishes independent verification from quote
production, official marking, model validation, and counterparty
reconciliation. Do not add a catalogue entry or release mapping on the
requirement-and-placeholder evidence alone. A later documented match or
out-of-scope ruling may instead resolve the proposal.
