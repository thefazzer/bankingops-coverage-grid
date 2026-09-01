# DRAFT — role/facing semantics for division keys

> **INTEGRATED**: folded into specs/common-semantic-profile.yaml 0.3.0 (role_semantics section). This file is retained as the staging-history record only.

Staged from a FinExhaust owner ruling (2026-08-31). Local draft only:
committing, pushing, and the Release that re-mints the manifest are separate
owner actions. Contains no corpus text, no client identities, no personal
names.

## Proposed semantic-profile addition

Buy-side and sell-side are **roles in the capital-markets ecosystem**, joined
by a directional, perspective-dependent predicate **FACES** (a sell-side
institution faces buy-side clients). Consequently:

- `buyside_*` division keys denote functions of the buy-side ROLE
  (allocation, investment, risk). For a consumer modelling a sell-side
  institution, these keys describe the FACED CLIENT's functions and MUST NOT
  be applied as the institution's own operational divisions.
- Sell-side role functions: intermediation, liquidity, capital.
- The profile currently leaves this relational reading implicit; making it
  explicit prevents consumers mis-assigning `buyside_*` keys to sell-side
  institutions (observed failure mode in a live consumer).

## Vocabulary gaps observed by the same ruling (candidates, not decisions)

1. Margin/financing **terms governance** (calculation-basis and terms
   changes) — recurring episodes fit no current key; nearest is
   `collateral_margin_management`.
2. Equity-financing hierarchy: equity trading → equity financing → prime
   brokerage → equity swaps / securities financing — consumers collapse
   "swaps" into `fx_trading`/`rates_trading`; a hierarchy note would prevent
   the token-level collapse ("has a rates feature" ≠ "is rates").
3. Basket structures of single-stock swaps (aggregation concept; owner
   suggested a name tentatively — left open).
4. Cross-currency funding basis (funding index = benchmark/reference rate).

