# Live run — 2026-08-26

Elicitation of a model-consensus taxonomy of a G-SIB's capital-markets operational divisions, under the
frozen prompt `efd90b74`. Every response in `runs/` is the raw bytes returned by the provider, logged
verbatim with its sha256, model id and call parameters.

## Panel

| model | vendor | valid / samples | on the board |
|---|---|---|---|
| gpt-5.6-sol | openai | 3/3 | yes |
| claude-opus-5 | anthropic | 3/3 | yes |
| deepseek-v4-pro | deepseek | 3/3 | yes |
| kimi-k3 | moonshot | 3/3 | yes |
| qwen3.6-35b | qwen | 3/3 | yes |
| x-preview-f-free | opencode-zen | 1/3 | excluded (declared) |
| gemma-4-31b | google | 0/3 | excluded (declared) |
| glm-5.2 | zhipu | 0/3 | excluded (declared) |

Exclusions are declared with reasons in `exclusions.json`; the gate refuses to ignore a model that is not
declared there, so no model can be dropped silently. Excluded models' raw responses are still published.

## Result

Divisions named by four or more vendors: `prime_brokerage_financing`, `equities_trading`, `credit_trading`,
`rates_trading`, `commodities_trading`, `securitised_products`. Full board in `matrix.csv`.

## Status — PROVISIONAL, do not cite

G10 (panel width) passes. **G6 (corroboration) does not**: no anchor in this run has been verified by hand
against an actual filing, rulebook or published series. Every citation below the matrix is a model's
assertion and nothing more. The gate report in `gates_report.json` records this.

## Reading the numbers

A cell is the fraction of that model's valid samples that named the division. `model_support` counts models
with a cell >= 0.5. `aliases.yaml` maps the 188 surface names the panel produced onto 42 division keys and
carries a written rationale for every merge — that table is the main judgement call in this artifact and the
right place to start if you want to argue with the result.
