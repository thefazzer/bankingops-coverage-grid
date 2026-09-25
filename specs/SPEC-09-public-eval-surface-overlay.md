# SPEC-09 — Public-eval surface overlay

```
ARTIFACT : inventory + likelihood-mapped overlay of public rubrics / benchmarks /
           evals onto the BOCG episode surface, with a division roll-up of
           saturation vs voids
STATUS   : v1.3.0 normative shape
SOURCES  : reference/public-eval-inventory.v1.yaml,
           reference/public-eval-surface-map.v1.json,
           reference/public-eval-llmaj-ledger.v1.json,
           specs/public-eval-surface-overlay.schema.json,
           specs/public-eval-llmaj.schema.json,
           specs/rubrics/public-eval-mapping.yaml,
           tools/public_eval_overlay.py,
           tools/public_eval_llmaj.py
BOUNDARY : third-party public rubrics/benchmarks/evals only for paint; no institution
           instance, no private corpus, no BOCG cell-citation coverage as eval
           density, no competency score, no I7 gap elicitation; no one-pass
           QUALIFIED paint for public_benchmark inventory
```

## 0. Purpose

SPEC-08 defines how a consumer Episode binds to the grid. This specification
adds a **supplementary overlay**: which *public* rubrics, benchmarks and evals
touch the same surface, at what depth, and with what explainable likelihood
band. A derived **division roll-up** reports where public-eval saturation
concentrates and which admitted divisions remain voids.

Presentation style (tables, maps, heatmaps) is a consumer choice. This
specification does not define a presentation standard.

The overlay does not change admitted keys, tiers, concepts, cells or episode
depth. It is not validation of the grid and not a claim that voids are
under-served.

## 1. Coordinate system

Overlay rows use the SPEC-08 depth ladder:

```
division < function_concept < task_concept < terminal_task < control_point
```

Identifiers must exist in the pinned release (catalogue, task-concepts, cells).
Rows never cross a division.

## 2. What may paint

Only rows that satisfy **all** of:

1. `mapping_status` ∈ {`QUALIFIED_MAPPING`, `RATIFIED_MAPPING`}
2. `channel` = `public`
3. inventory `class` ∈ {`peer_framework`, `peer_task_shape`, `public_benchmark`, `public_rubric`}
4. If inventory `class` = `public_benchmark`: a live LLMAJ case
   (`llmaj_pass_ref`) whose primary + sensitivity sheets jointly PASS under
   `public-eval-mapping/intersection-union/v1` (see §3.1)

Must **not** paint:

- BOCG control-point cells or their regulatory/standard citations (that is BOCG
  coverage, not public-eval density)
- Own rubrics / own evals (`channel=own_artifact` or `own_cell`; inventory class
  `own_rubric` / `own_eval`)
- Method peers with no banking-ops task content (`REJECTED_MAPPING` / `R-PEER-SHAPE`)
- `public_benchmark` rows promoted by a one-pass owner ruling (PROPOSED/PENDING
  only until LLMAJ passes)

## 3. Likelihood matching

| Band | Code | Weight | Meaning |
|---|---|---|---|
| Low | `L1` | 1 | Division-level or peer-shape with limits |
| Medium | `L2` | 2 | Concept/task match with named limits (QUALIFIED) |
| High | `L3` | 3 | Clear terminal-task alignment to a public eval (usually RATIFIED) |

Matching rules: `R-DIV-KEY`, `R-TERM-TASK`, `R-CONCEPT`, `R-PEER-SHAPE`,
`R-REJECT`. `R-CTRL-CITE` may appear only as supporting rationale on a public-eval
row; a citation alone never paints.

Every painted row MUST carry: inventory id (public URL), BOCG identifier(s),
rule id, band, rationale, and a dated ruling role. Painted `public_benchmark`
rows MUST also carry `llmaj_pass_ref`.

### 3.1 LLMAJ multi-pass (required for `public_benchmark`)

Capital-markets / IB public benches (and any other `public_benchmark`) are
qualitative surface claims. They use the same discipline as five-families /
downstream-evidence model judges — **not** a one-pass owner map:

1. Inventory the artifact (`reference/public-eval-inventory.v1.yaml`).
2. Stage a candidate overlay row as `PROPOSED` or `PENDING` (may carry a
   proposed division/depth/band; candidates never paint).
3. Run **judge-primary** and **judge-sensitivity** against
   `specs/rubrics/public-eval-mapping.yaml` (five families; append-only sheets).
4. Aggregate under `public-eval-mapping/intersection-union/v1`:
   both assessors must PASS promotion; disagreement is preserved as
   `UNCERTAIN` and **does not paint** (never averaged silently).
5. Only then may an SME/owner overlay promote the row to QUALIFIED/RATIFIED
   with `llmaj_pass_ref` bound to the live ledger case.

Runnable tools: `python3 tools/public_eval_llmaj.py check|candidates|promote-gate`.

Synthetic fixture `specs/fixtures/public-eval-llmaj-synthetic.json` demonstrates
disagreement retention and agreement shape; fixture model ids never paint
production rows.

## 4. Division roll-up

For each admitted division:

- **saturation** = sum of band weights of painted public-eval rows under that division
- **void** = admitted division with saturation 0

Matrix tier (STRONG/MODERATE/WEAK) may be shown beside saturation so panel
consensus is not confused with public-eval density.

## 5. Runnable gates (S9)

| Gate | Check |
|---|---|
| S9-G1 | Overlay validates against `public-eval-surface-overlay.schema.json`. |
| S9-G2 | Release pin, inventory digest, identifiers and paint rules pass `tools/public_eval_overlay.py check`. |
| S9-G3 | Deny list (SPEC-03 I3) covers inventory, map, LLMAJ ledger/rubric/fixture and this specification. |
| S9-G5 | LLMAJ fixture + live ledger validate; `public_benchmark` paint requires live `llmaj_pass_ref` PASS (`promote-gate`). |

## 6. Seed scope (v1.3)

Inventory includes CONFORMANCE peers, capital-markets / IB public benches
(Mercor APEX, Rogo Big Finance Bench, Handshake BankerToolBench), plus own
rubrics listed only for audit (`own_artifact`, never paint).

| Inventory | Overlay status | Notes |
|---|---|---|
| Method peers without banking-ops content | `REJECTED_MAPPING` | Datasheets, BetterBench, Inspect |
| Harvey LAB (peer task-shape) | `QUALIFIED_MAPPING` L1 → `trade_lifecycle_operations` | CONFORMANCE peer seed; not `public_benchmark` |
| Mercor / Rogo / BankerToolBench | `PENDING` candidate rows | Inventory hydrated; **await LLMAJ** primary+sensitivity before paint |

Remaining admitted divisions stay voids until further *public* eval artifacts
clear LLMAJ (for `public_benchmark`) or an argued method-peer ruling. Private
corpora and BOCG cell citations still do not paint.
