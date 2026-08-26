# Methodology — BankingOps Coverage Grid (BOCG)

This bundle was produced by the `bocg` pipeline implementing SPEC-01 (model-consensus taxonomy elicitation).

1. **Frozen prompt.** `prompt.txt` and `system.txt` are byte-fixed; `prompt.sha256` is the published hash of
   `prompt.txt`. The prompt is parameterised only by `{THRESHOLD_USD}`, `{CURRENCY}`, `{AS_OF_YEAR}`; the rendered
   values are logged in every run record. Any edit to the prompt yields a new `prompt_sha8` and a full re-run (I1).
2. **Cold runs.** Every call used a fresh context, the fixed system prompt, no tools, no browsing, no retrieval and
   no prior turns. Temperature, top_p, seed and max_tokens are logged per sample (I3). Responses are stored as raw
   bytes with sha256 (I4) under `runs/<prompt_sha8>/<model_id>/<i>.json`.
3. **Validation.** Each response is validated against `schema.json`; the anchor-before-name field order is checked
   on the raw text (I5); `rejected[]` must be non-empty (I6); `addressable_seat_cost` is recomputed server-side and
   the admission rule is re-applied — the model's own placement is advisory only (I9).
4. **Normalisation.** Division names are canonicalised (§5.1) and mapped to `division_key` via `aliases.yaml`
   (§5.2), which was authored after all runs completed; every alias carries a rationale and the table's sha256 is
   published.
5. **Agreement matrix.** `matrix.csv` rows are `division_key`, columns are `model_id`; a cell is the fraction of
   that model's samples naming the key. Consensus tiers follow §5.4. Axis values are majority votes (§5.5);
   anchors and seat statistics are pooled across samples (§5.6–5.7).
6. **Corroboration.** Every pooled anchor was checked against its source and recorded in `corroboration.csv` (§6).
   UNVERIFIED anchors never count toward admission; REFUTED anchors are removed from the pool.
7. **Grid and coverage.** `grid.json` is the map. `own_cell.json`, `coverage_statement.md` and
   `divergence_report.md` were generated post hoc and separately (I10).
8. **Gates.** `gates_report.json` records G1–G10 with evidence; the bundle is only published when all gates PASS.
