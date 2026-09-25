# SPEC-09 — Public-eval surface overlay

```
ARTIFACT : inventory + likelihood-mapped overlay + division choropleth of public
           rubrics / benchmarks / evals onto the BOCG episode surface
STATUS   : v1.0.0 normative shape; first painted seed in BOCG release workstream
SOURCES  : reference/public-eval-inventory.v1.yaml,
           reference/public-eval-surface-map.v1.json,
           reference/public-eval-choropleth.v1.md,
           specs/public-eval-surface-overlay.schema.json,
           tools/public_eval_overlay.py
BOUNDARY : public citations and argued mappings only; no institution instance,
           no private corpus, no competency score, no I7 gap elicitation
```

## 0. Purpose

SPEC-08 defines how a consumer Episode binds to the grid. This specification
adds a **supplementary public overlay**: which *public* rubrics, benchmarks and
evals touch the same surface, at what depth, and with what explainable
likelihood band — so a choropleth can show where public-eval saturation
concentrates and which admitted divisions remain voids.

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

## 2. Likelihood matching

| Band | Code | Weight | Meaning |
|---|---|---|---|
| Low | `L1` | 1 | Division-level or peer-shape with limits |
| Medium | `L2` | 2 | Concept/task/control match with named limits (QUALIFIED) |
| High | `L3` | 3 | Direct public citation or clear terminal-task alignment (usually RATIFIED) |

Matching rules: `R-DIV-KEY`, `R-TERM-TASK`, `R-CONCEPT`, `R-CTRL-CITE`,
`R-PEER-SHAPE`, `R-REJECT` (see plan draft
`drafts/2026-09-24-public-eval-surface-overlay.md` §3.3).

Only `QUALIFIED_MAPPING` and `RATIFIED_MAPPING` on `channel=public` paint the
choropleth. `PROPOSED` / `PENDING` are candidates; `REJECTED_MAPPING` /
`DEFERRED_MAPPING` stay on the audit trail without paint.

Every painted row MUST carry: inventory id (public URL), BOCG identifier(s),
rule id, band, rationale, and a dated ruling role.

## 3. Choropleth

Division grain is primary. For each admitted division:

- **saturation** = sum of band weights of painted rows under that division
- **void** = admitted division with saturation 0

Matrix tier (STRONG/MODERATE/WEAK) may be shown beside saturation so panel
consensus is not confused with public-eval density. Concept `review_status`
(AUTO/REVIEWED) is shown for explainability.

## 4. Runnable gates (S9)

| Gate | Check |
|---|---|
| S9-G1 | Overlay validates against `public-eval-surface-overlay.schema.json`. |
| S9-G2 | Release pin, inventory digest, identifiers and paint rules pass `tools/public_eval_overlay.py check`. |
| S9-G3 | Choropleth markdown reproduces from the map. |
| S9-G4 | Deny list (SPEC-03 I3) covers inventory, map, choropleth and this specification. |

## 5. Seed scope (v1)

The first map paints from CONFORMANCE peers (reject/defer/qualify), in-repo
rubrics (defer), published `cp_*` citation bindings (control_point depth), and
a REVIEWED prime-brokerage margin concept/task qualified from ISDA SIMM. Most
admitted divisions remain voids by construction until further public artifacts
are ruled in.
