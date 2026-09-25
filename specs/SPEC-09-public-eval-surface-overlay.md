# SPEC-09 — Public-eval surface overlay

```
ARTIFACT : inventory + likelihood-mapped overlay of public rubrics / benchmarks /
           evals onto the BOCG episode surface, with a division roll-up of
           saturation vs voids
STATUS   : v1.2.0 normative shape
SOURCES  : reference/public-eval-inventory.v1.yaml,
           reference/public-eval-surface-map.v1.json,
           specs/public-eval-surface-overlay.schema.json,
           tools/public_eval_overlay.py
BOUNDARY : third-party public rubrics/benchmarks/evals only for paint; no institution
           instance, no private corpus, no BOCG cell-citation coverage as eval
           density, no competency score, no I7 gap elicitation
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

Must **not** paint:

- BOCG control-point cells or their regulatory/standard citations (that is BOCG
  coverage, not public-eval density)
- Own rubrics / own evals (`channel=own_artifact` or `own_cell`; inventory class
  `own_rubric` / `own_eval`)
- Method peers with no banking-ops task content (`REJECTED_MAPPING` / `R-PEER-SHAPE`)

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
rule id, band, rationale, and a dated ruling role.

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
| S9-G3 | Deny list (SPEC-03 I3) covers inventory, map and this specification. |

## 6. Seed scope (v1.2)

Inventory is CONFORMANCE peers, capital-markets / IB public benches, plus own
rubrics listed only for audit (`own_artifact`, never paint). Method peers without
banking-ops task content are rejected.

Painted public benches (QUALIFIED, channel=public):

| Inventory | Division(s) painted | Band |
|---|---|---|
| Harvey LAB (peer task-shape) | `trade_lifecycle_operations` | L1 |
| Mercor APEX-Agents (IB analyst job) | `ma_advisory` | L2 |
| Mercor APEX-1 IB | `ma_advisory` | L2 |
| Rogo Big Finance Bench | `ma_advisory`, `sellside_research`, `capital_markets_origination_combined` | L2 / L2 / L1 |
| Handshake BankerToolBench | `ma_advisory` | L2 |

Remaining admitted divisions stay voids until further *public* eval artifacts are
ruled in. Private corpora and BOCG cell citations still do not paint.
