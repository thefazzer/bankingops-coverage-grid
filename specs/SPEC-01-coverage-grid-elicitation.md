# SPEC-01 — BankingOps Coverage Grid: model-consensus taxonomy elicitation

```
ARTIFACT      : BankingOps Coverage Grid (BOCG)
CELL_BENCHMARK: PB-Ops Eval (declared post-hoc; NEVER referenced in elicitation)
PROJECT       : FinExhaust / BankingEnv
STATUS        : v0.1 goal spec for implementing agent
TAGS          : BankingOps Coverage Grid, PB-Ops Eval, FinExhaust, BankingEnv, model consensus taxonomy,
                benchmark ceiling, frontier saturation, sealed holdout, rubric design, capital markets eval gap,
                seat-cost filter, terminality test, corroboration ledger
```

## 0. GOAL

Produce a reproducible, model-derived taxonomy of the operational divisions of a global bank's capital-markets /
global-markets business, where every admitted division is (a) named independently by multiple frozen base models
under a fixed cold prompt, (b) anchored to externally verifiable quantities, and (c) staffed by expensive
judgement-bearing human seats with terminal, record-checkable tasks. Output = an agreement matrix + corroboration
ledger + grid + coverage statement, publishable as a bundle whose every input is hash-fixed.

The grid is the MAP. Competency GAPS are NOT elicited from models (models cannot introspect capability);
gaps come only from measured task scores in a later phase (out of scope here).

## 1. NON-NEGOTIABLE INVARIANTS

```
I1  PROMPT_FROZEN        prompt.txt is byte-fixed before run 1; sha256 published; any edit => new prompt_version, full re-run.
I2  ZERO_SEEDING         prompt contains no candidate division names, no example products, no reference to seller's segment.
                         Enforced by CONTAMINATION_GATE (§8) against FORBIDDEN_TOKENS (§2.3).
I3  COLD_RUNS            each model call: fresh context, fixed system prompt (§2.1), no tools, no browsing, no retrieval,
                         no prior turns, no seller data. Temperature/seed fixed & logged.
I4  RAW_LOGGED_VERBATIM  every response stored unmodified (bytes) + sha256 + model_id + params + ts. Published.
I5  ANCHORS_BEFORE_NAME  response schema forces anchor fields to be emitted before any judgement/ranking field.
I6  REJECTIONS_REQUIRED  schema requires a non-empty `rejected[]` list with reason codes; empty => response invalid.
I7  NO_SELF_ASSESSMENT   prompt never asks model where models are weak/strong or what is "under-served".
I8  CORROBORATE_OR_DROP  every anchor verified by a human/agent against the actual source before publication.
                         Unverified anchor => anchor status UNVERIFIED => does not count toward admission.
I9  SEAT_FILTER_IS_HARD  a division with addressable_seat_cost < THRESHOLD or terminality_tasks < 3 is REJECTED regardless
                         of other anchors.
I10 OWN_CELL_POST_HOC    seller's cell placement + coverage statement live in a separate file, generated after the matrix.
```

## 2. ELICITATION PROMPT

### 2.1 System prompt (fixed)
```
You are an analyst producing a structured decomposition. Output only valid JSON matching the schema provided.
Do not include prose outside the JSON. Do not ask questions.
```

### 2.2 User prompt (fixed; store as prompt.txt; parameterised only by {THRESHOLD_USD}, {CURRENCY}, {AS_OF_YEAR})
```
Decompose the capital-markets and global-markets business of a large, globally systemically important bank into its
canonical operational divisions. Consider both the bank's own (sell-side) operations and the buy-side counterpart
functions those operations serve. Consider all major regions in which such banks operate.

For EVERY division you propose you must supply the following anchors BEFORE any other field, in this order:

A1 REGULATORY   : at least one specific regulatory regime, rule, or article that governs the division's activity,
                  with jurisdiction and citation (e.g. rule name + section/article number). If none, write null.
A2 SEGMENT      : at least one line item from a G-SIB's published segment or revenue disclosure to which this division
                  maps, naming the bank, the filing type, the fiscal year, and the line-item label as printed. If none, null.
A3 MARKET_SIZE  : at least one published quantitative series for the division's market (notional outstanding, gross
                  market value, daily turnover, AUM, revenue pool), naming the publisher, series name/id, value, unit,
                  and reference date. If none, null.
A4 SEAT         : the principal human operational function(s) that perform the division's work, with:
                  - typical headcount range for that function at a single G-SIB
                  - fully-loaded annual cost per seat, as a range in {CURRENCY}, with the survey/filing you rely on
                  - time decomposition: fraction of the seat's working time spent on DETERMINABLE work
                    (decisions with a checkable right answer given the inputs) vs RELATIONAL work
                    (negotiation, relationship management, discretionary judgement with no checkable answer)
                  - addressable_seat_cost = midpoint(cost_per_seat) * determinable_fraction
                  - TERMINALITY: at least three concrete tasks the function performs whose correct outcome is
                    identifiable after the fact from records the bank retains. For each: task, input records,
                    terminal state, record that evidences correctness.

Admission rule you must apply yourself:
  - At least TWO of A1, A2, A3 must be non-null.
  - addressable_seat_cost must be >= {THRESHOLD_USD} {CURRENCY}.
  - TERMINALITY must list >= 3 tasks.
  Divisions failing any of these go in `rejected` with the reason code(s) from the schema, not in `divisions`.
  You MUST populate `rejected` with every candidate you considered and discarded. An empty `rejected` list is invalid.

Do not rank divisions by importance. Do not comment on model or AI capability. Do not speculate about which
divisions are under-served by tooling or data. Use only what you know as of {AS_OF_YEAR}; do not fabricate citations —
if you are unsure a citation exists, set the anchor to null and note uncertainty in `confidence`.

Output JSON conforming exactly to the schema below.
<SCHEMA>
```
`<SCHEMA>` = JSON Schema in §3, embedded verbatim. Defaults: THRESHOLD_USD=200000, CURRENCY=USD, AS_OF_YEAR=2025.

### 2.3 FORBIDDEN_TOKENS (contamination gate; case-insensitive; applied to prompt.txt + system prompt)
```
prime brokerage, prime broker, PB, equity finance, securities lending, stock loan, single stock swap, single-stock swap,
synthetic, TRS, total return swap, delta one, delta-one, hedge fund, FinExhaust, BankingEnv, PB-Ops, Jefferies,
<any bank name>, <any product name beyond generic asset-class nouns>, "gap", "under-served", "underserved",
"model capability", "benchmark", "eval"
```
Generic asset-class nouns allowed ONLY inside the schema enum (§3 `axis.product`), never as examples in prose.

## 3. RESPONSE SCHEMA (JSON Schema draft 2020-12; field ORDER enforced by post-validation on raw text)

```json
{
  "$id": "bocg.response.v1",
  "type": "object",
  "required": ["divisions", "rejected"],
  "properties": {
    "divisions": {
      "type": "array", "minItems": 1,
      "items": {
        "type": "object",
        "required": ["a1_regulatory","a2_segment","a3_market_size","a4_seat","name","axis","confidence"],
        "properties": {
          "a1_regulatory": {"type":["array","null"], "items": {"type":"object","required":["regime","jurisdiction","citation"],
              "properties":{"regime":{"type":"string"},"jurisdiction":{"type":"string"},"citation":{"type":"string"}}}},
          "a2_segment": {"type":["array","null"], "items": {"type":"object","required":["bank","filing","fiscal_year","line_item"],
              "properties":{"bank":{"type":"string"},"filing":{"type":"string"},"fiscal_year":{"type":"integer"},"line_item":{"type":"string"}}}},
          "a3_market_size": {"type":["array","null"], "items": {"type":"object","required":["publisher","series","value","unit","as_of"],
              "properties":{"publisher":{"type":"string"},"series":{"type":"string"},"value":{"type":"number"},"unit":{"type":"string"},"as_of":{"type":"string"}}}},
          "a4_seat": {"type":"object",
              "required":["function","headcount_range","cost_per_seat","cost_source","determinable_fraction","relational_fraction","addressable_seat_cost","terminality"],
              "properties":{
                "function":{"type":"string"},
                "headcount_range":{"type":"array","items":{"type":"integer"},"minItems":2,"maxItems":2},
                "cost_per_seat":{"type":"array","items":{"type":"number"},"minItems":2,"maxItems":2},
                "cost_source":{"type":"string"},
                "determinable_fraction":{"type":"number","minimum":0,"maximum":1},
                "relational_fraction":{"type":"number","minimum":0,"maximum":1},
                "addressable_seat_cost":{"type":"number"},
                "terminality":{"type":"array","minItems":3,"items":{"type":"object",
                    "required":["task","input_records","terminal_state","evidence_record"],
                    "properties":{"task":{"type":"string"},"input_records":{"type":"string"},"terminal_state":{"type":"string"},"evidence_record":{"type":"string"}}}}}},
          "name": {"type":"string"},
          "axis": {"type":"object","required":["business_line","side","region","product","office"],
              "properties":{
                "business_line":{"type":"string"},
                "side":{"enum":["sell","buy","both"]},
                "region":{"type":"array","items":{"enum":["AMER","EMEA","APAC","GLOBAL"]}},
                "product":{"type":"array","items":{"enum":["rates","credit","fx","equities","commodities","em","securitised","financing","multi"]}},
                "office":{"enum":["front","middle","back","control","multi"]}}},
          "confidence": {"type":"number","minimum":0,"maximum":1}
        }
      }
    },
    "rejected": {
      "type":"array","minItems":1,
      "items":{"type":"object","required":["name","reason_codes","note"],
        "properties":{"name":{"type":"string"},
          "reason_codes":{"type":"array","minItems":1,"items":{"enum":[
            "R_ANCHORS_LT2","R_SEAT_BELOW_THRESHOLD","R_TERMINALITY_LT3","R_RELATIONAL_DOMINANT",
            "R_NOT_CAPITAL_MARKETS","R_DUPLICATE_OF","R_NO_STABLE_DEFINITION","R_UNCERTAIN_CITATIONS"]}},
          "note":{"type":"string"}}}
    }
  }
}
```
Post-validation (I5): in raw text, byte offset of `"a1_regulatory"` < offset of `"name"` for each division object.
Post-validation (I9): recompute addressable_seat_cost from fields; if model's number deviates >5% => flag ARITH_MISMATCH;
use recomputed value. Apply admission rule server-side; model's own placement is advisory only.

## 4. RUN PROTOCOL

```
MODELS      : >= 4 distinct vendors/families. Default panel: [openai:gpt-5*, anthropic:claude-opus*, google:gemini-2.5-pro*,
              deepseek:deepseek-v3*/r1*, xai:grok-4*, meta:llama-4*]. Record exact model_id string returned by API.
SAMPLES     : k >= 3 per model. temperature=0.2 (or provider min), top_p=1, seed fixed per sample index where supported.
CONTEXT     : system prompt §2.1 + user prompt §2.2 only. max_tokens sufficient for >= 25 divisions (>= 16k).
TOOLS       : none. Browsing/retrieval disabled. If provider cannot guarantee off => exclude model, log reason.
RETRY       : on invalid JSON: one repair pass = re-send same prompt (no hints) once; if still invalid => record INVALID, no fix-ups.
LOGGING     : runs/<prompt_sha8>/<model_id>/<sample_idx>.json = {request, response_raw, response_sha256, ts_utc, params, usage}
ORDER       : run all models before any human inspects any response (prevents drift/alias bias).
DRY_RUN     : `--fixtures <dir>` mode replays stored responses; used for tests + reproducibility audit.
```

## 5. NORMALISATION + AGREEMENT MATRIX

```
5.1 CANON_NAME  : lowercase, strip punctuation, collapse whitespace, singularise, drop stopwords {the,of,and,&,desk,business,group}.
5.2 ALIAS_TABLE : aliases.yaml, versioned, authored AFTER all runs complete, maps canon_name -> division_key.
                  Every alias decision logged with rationale. Alias table sha256 published.
5.3 MATRIX      : rows=division_key, cols=model_id; cell = (#samples naming key)/(k). matrix.csv + matrix.json.
5.4 CONSENSUS   : model_support = #models with cell >= 0.5.
                  TIER_STRONG   : model_support >= ceil(0.8*N_models)
                  TIER_MODERATE : model_support >= ceil(0.5*N_models)
                  TIER_WEAK     : else
5.5 AXIS_VOTE   : per division_key, majority vote per axis field across supporting samples; ties => "multi"/"both"/"GLOBAL".
5.6 ANCHOR_POOL : union of all anchors emitted for a division_key across samples, deduped by (type, canon(citation)).
5.7 SEAT_POOL   : median of cost_per_seat midpoints, median determinable_fraction, union of terminality tasks (dedupe by canon).
```

## 6. CORROBORATION LEDGER

```
corroboration.csv columns:
  division_key, anchor_type{A1,A2,A3,A4}, anchor_text, source_url_or_doc, checked_by, checked_ts,
  status{VERIFIED,UNVERIFIED,REFUTED,PARTIAL}, verified_value, note
RULES:
  - A1 VERIFIED iff rule/article exists and governs the described activity (cite URL/doc + section).
  - A2 VERIFIED iff line item string appears in named filing (10-K/ARA/Pillar 3) for named FY.
  - A3 VERIFIED iff series exists at publisher and value within ±25% of published for as_of date.
  - A4 VERIFIED iff comp range overlaps a named survey/filing AND >=3 terminality tasks judged record-checkable by
    a practitioner reviewer (reviewer id logged).
  - REFUTED anchor => removed from pool; if division drops below admission => division moves to grid as REJECTED_POST_CORROBORATION.
  - Publication gate: 0 anchors with status UNVERIFIED on any admitted division.
```

## 7. GRID + COVERAGE STATEMENT

```
grid.json : { axes: {business_line[], side[], region[], product[], office[]},
              cells: [{division_key, tier, axis, anchors_verified:{A1:int,A2:int,A3:int,A4:bool},
                       addressable_seat_cost_median, terminality_count, corpus_coverage: null}] }
own_cell.json (I10, post-hoc, separate file):
            { division_keys[], corpus_coverage per task_cluster: {supports_well[], thin[], cannot_speak[]},
              practitioner_divergences: [{division_key, consensus_view, practitioner_view, evidence}] }
coverage_statement.md : rendered from own_cell.json + grid.json. Declares limits explicitly. No claims beyond filled cells.
divergence_report.md  : where practitioner view != consensus; published as finding, not smoothed.
```

## 8. RUNNABLE GATES (exit non-zero on failure; wired as `bocg gate all` pre-publish)

```
G1 CONTAMINATION_GATE : prompt.txt + system.txt contain no FORBIDDEN_TOKENS; prompt sha256 == published sha256.
G2 SCHEMA_GATE        : every stored response validates against §3 or is marked INVALID; no silently edited responses
                        (stored sha256 == recomputed).
G3 ORDER_GATE         : I5 offset check passes on all valid responses.
G4 REJECTION_GATE     : every valid response has rejected.length >= 1.
G5 ADMISSION_GATE     : server-side admission recomputed; model self-placement overridden where it disagrees; diffs logged.
G6 CORROBORATION_GATE : no UNVERIFIED/REFUTED anchors counted; every admitted division has >=2 VERIFIED of A1-A3 + A4 VERIFIED.
G7 ALIAS_GATE         : aliases.yaml sha256 fixed; every division_key in matrix has >=1 alias; no alias maps to 2 keys.
G8 SELF_ASSESS_GATE   : prompt + responses contain no capability/gap language (regex list); violations => response INVALID.
G9 REPRO_GATE         : `--fixtures` replay regenerates matrix.csv byte-identical.
G10 PANEL_GATE        : >= 4 vendors, >= 3 samples each, all cold (params logged).
```

## 9. PUBLICATION BUNDLE

```
bocg-bundle-<prompt_sha8>-<date>/
  prompt.txt  system.txt  prompt.sha256  schema.json
  runs/**                       (raw, verbatim)
  aliases.yaml  aliases.sha256
  matrix.csv  matrix.json
  corroboration.csv
  grid.json
  own_cell.json  coverage_statement.md  divergence_report.md
  methodology.md  limits.md   (limits: "consensus = textual convergence, not economic importance"; "gaps not elicited")
  gates_report.json            (all G1–G10 PASS with evidence)
  MANIFEST.sha256              (sha256 of every file; root hash anchored per SPEC-02 §4 optional)
```

## 10. IMPLEMENTATION TARGET

```
package     : bocg/ (python>=3.11, deps: pydantic|jsonschema, pyyaml, click, httpx; provider SDKs optional)
cli         : bocg run --panel panel.yaml [--fixtures DIR] ; bocg normalise ; bocg matrix ; bocg corroborate --ledger ;
              bocg grid ; bocg coverage --own-cell own_cell.json ; bocg gate all ; bocg bundle
providers   : adapters {openai, anthropic, google, deepseek, xai, generic_openai_compatible}; each returns raw text + usage.
fixtures    : tests/fixtures/<model_id>/<i>.json (synthetic, schema-valid, incl. one INVALID and one seeded-token violation)
tests       : gates G1–G10 each have a failing + passing fixture; matrix determinism test; admission recompute test.
out-of-scope: running real models (needs keys), scoring tasks in cells, any reference to seller's own data.
```
