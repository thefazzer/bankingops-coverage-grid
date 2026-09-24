# Plan: public rubric / benchmark / eval surface overlay on BOCG

```
ARTIFACT : plan draft (non-normative; not a release-manifest asset)
STATUS   : SUPERSEDED by SPEC-09 implementation (inventory, map, choropleth, S9 gates)
GOAL_REF : Supplement BOCG with a global surface overlay of public rubric/benchmark/evals,
           likelihood-matched to the SPEC-08 episode surface, so a choropleth-style read
           shows voids BOCG already treats as valid/valuable vs where public-eval
           saturation concentrates — consistent and explainable, not perfect
AS OF    : 2026-09-24
```

## 0. One-sentence purpose

Publish a **supplementary overlay** that projects *public* rubrics, benchmarks and
evals onto the same surface the episode surface already uses
(division → function concept → task concept → terminal task → control point), so
a reader can see — choropleth-style — where the public eval landscape is dense
and where BOCG admits operational surface that public evals barely touch.

## 1. Why this is a supplement, not a rewrite

| Existing BOCG claim | What this overlay does **not** do |
|---|---|
| Grid = map of operational divisions (SPEC-01); gaps are **not** model-elicited (I7) | Does not invent competency gaps from model self-assessment |
| Episode surface = consumer-owned touchpoints + depth rule (SPEC-08) | Does not replace episode surfaces or raise evidence depth |
| `own_cell` / coverage statements are post-hoc and seller-scoped (I10) | Does not become a coverage claim about any institution |
| CONFORMANCE.md peers (BetterBench, Inspect, Harvey LAB, Datasheets) | Does not assert conformance of those peers to BOCG |
| Downstream evidence note is private-lane calibration | Does not republish private locus scores as public saturation |

The overlay is a **public-side density map** of what already exists outside the
seller's cell. It answers: *given the BOCG surface, where do public evals
already sit, and where is the surface empty of public eval touch?*

## 2. Coordinate system (must match episode mapping)

Every overlay atom binds to exactly one BOCG surface depth, using the same
ordered depth ladder as SPEC-08 §3.1:

```
none < division < function_concept < task_concept < terminal_task < control_point
```

| Overlay claim depth | Allowed identifiers | Parallel to episode surface |
|---|---|---|
| `division` | admitted `division_key` | touchpoint at division |
| `function_concept` | `function_concept:<div>:<hex>` | function_concept touchpoint |
| `task_concept` | `task_concept:<div>:<hex>` | task_concept touchpoint |
| `terminal_task` | `task:<div>:<hex>` (released catalogue) | terminal_task touchpoint |
| `control_point` | `cp_*` cell id | control_point touchpoint |

Rules:

1. **Same release pin.** Overlay rows name `bocg_release.tag` +
   `task_concepts_sha256` (and optionally catalogue / cell digests) exactly as
   episode surfaces do. Stale overlays fail the gate.
2. **No cross-division pooling.** A public eval that spans two desks yields two
   rows (or a deferred row), never a blended cell.
3. **Depth is the claim, not a score.** Deeper mapping is more specific about
   *where* the public artifact sits on the grid; it is not a quality rating of
   the eval.
4. **AUTO vs REVIEWED visibility.** Wherever a concept id is shown, the
   division's `review_status` from SPEC-08 must be shown beside it (AUTO is a
   machine prior; REVIEWED is argued, not independently validated).

## 3. Likelihood matching (consistent + explainable, not perfect)

"Likelihood matching" here means: a **reproducible, auditable mapping confidence**
from a public artifact's stated scope to a BOCG surface atom — not a trained
similarity model and not a hidden LLM vote.

### 3.1 Mapping status (reuse SPEC-08 vocabulary where it fits)

| Status | When used for public-eval overlay |
|---|---|
| `PROPOSED` | Lexical / catalogue match only; no human ruling |
| `PENDING` | Queued for argued ruling |
| `QUALIFIED_MAPPING` | Argued match with named limits (partial coverage, different unit of work) |
| `RATIFIED_MAPPING` | Argued match under a named ruling; public artifact clearly exercises that surface |
| `REJECTED_MAPPING` | Explicitly not the same work; kept for audit |
| `DEFERRED_MAPPING` | Ambiguous / multi-division; not painted until split or rejected |

Candidates (`PROPOSED` / `PENDING`) may be listed in a side table; **only
`QUALIFIED_MAPPING` and `RATIFIED_MAPPING` paint the choropleth.**

### 3.2 Confidence band (the "likelihood" channel)

Each painted row carries a discrete band derived from **named evidence rules**,
not a continuous opaque score:

| Band | Code | Evidence required (all must hold) |
|---|---|---|
| High | `L3` | Public artifact names the operational work in terms that match a released label or argued concept; at least one concrete task/criterion aligns with a terminality task or control-point citation; ruling recorded |
| Medium | `L2` | Division (and preferably function/task concept) is clear; task-level alignment is partial or by close-match policy only; ruling recorded |
| Low | `L1` | Division-level only, or concept match under `AUTO` clustering without a per-alias ruling for this eval; still requires a written rationale |

Bands are **explainability handles**: every `L*` row must cite (a) the public
URL or archival citation, (b) the BOCG identifier, (c) the matching rule id from
§3.3, (d) a one-paragraph rationale. If any of those is missing, the row cannot
paint.

### 3.3 Matching rules (fixed catalogue; versioned)

Publish a small, numbered rule list (e.g. in `specs/` or `reference/` once this
leaves draft). Initial set:

| Rule id | Match when | Max depth | Max band |
|---|---|---|---|
| `R-DIV-KEY` | Artifact explicitly names a BOCG admitted division key or a listed alias from `aliases.yaml` / catalogue labels | `division` | `L2` |
| `R-TERM-TASK` | Artifact task/criterion text is a close paraphrase of a released terminal task (Jaccard / argued synonym under ruling) | `terminal_task` | `L3` |
| `R-CONCEPT` | Artifact scope matches a task/function concept label or argued alias set | `task_concept` / `function_concept` | `L3` if REVIEWED else `L2` |
| `R-CTRL-CITE` | Artifact cites the same public standard/reg as a control-point cell's required citation | `control_point` | `L3` |
| `R-PEER-SHAPE` | Peer harness/task shape (Inspect, LAB, BetterBench criterion) is about eval method, not banking ops — map only if the *task content* also hits R-TERM-TASK / R-CTRL-CITE | depth of the content rule | content rule's max |
| `R-REJECT` | Same words, different operational role (e.g. generic "risk" leaderboard vs `market_risk_management` desk work) | n/a | n/a (status `REJECTED_MAPPING`) |

**Consistency bar:** the same public artifact + same release bytes must always
yield the same painted rows. Machine assists (token overlap against catalogue)
may draft `PROPOSED` rows; only a named ruling promotes them to paint.

**Explainability bar:** a reader must be able to answer, from the row alone:
*why this cell is coloured, which rule fired, and what would falsify the map.*

## 4. Choropleth encoding

### 4.1 Two visual channels (one job each)

| Channel | Question | Encoding |
|---|---|---|
| **Saturation** | Where do public evals concentrate on the BOCG surface? | Fill intensity / colour value ∝ count of painted rows (optionally weighted by band: L3=3, L2=2, L1=1) at that surface atom, rolled up to the display grain |
| **Void** | Where does BOCG admit surface that public evals do not paint? | Distinct void treatment (e.g. hatch / muted empty) for admitted divisions — and optionally REVIEWED concepts / published control points — with **zero** painted rows |

Display grain defaults:

1. **Division choropleth** (primary): one cell per admitted `division_key` (42 in
   the live run). Saturation = roll-up of all painted rows under that division
   at any depth. Void = admitted key with roll-up zero.
2. **Concept / control inset** (secondary): within a selected division, show
   task-concept and control-point saturation so voids are not only
   division-coarse.

### 4.2 What counts as a "void recognised by BOCG as valid/valuable"

A void is **not** "models said this is under-served" (forbidden by I7). A void
is an admitted BOCG surface atom that the overlay leaves unpainted:

- **Division void:** admitted key in the coverage matrix / catalogue with no
  painted public-eval rows.
- **Control-point void:** published `cp_*` cell with no `R-CTRL-CITE` /
  `R-TERM-TASK` painted row.
- **Concept void (optional grain):** REVIEWED concept with no painted row
  (AUTO concept voids are shown only with an AUTO caveat — they are machine
  priors, not curated value claims).

"Valid/valuable" here means: **BOCG already admits the surface** (seat filter,
terminality, anchors, consensus tier as published) — not that the overlay
assigns economic importance. Tier (STRONG / MODERATE / WEAK) may be shown as a
second legend mark so readers do not confuse panel consensus with eval density.

### 4.3 Legend (must ship with any figure)

Every published choropleth or table view MUST include:

1. Release tag + digests pinned
2. Paint rule: only QUALIFIED / RATIFIED
3. Band weights if used
4. Void definition (admitted ∩ unpainted)
5. Statement: *overlay is not a competency score; gaps remain unevaluated until
   measured tasks exist*
6. AUTO / REVIEWED cue for concept-grain views

## 5. Public corpus in scope (inventory, not endorsement)

Seed inventory classes (each row needs a dated public citation):

| Class | Examples already named in-repo | Overlay role |
|---|---|---|
| Peer eval frameworks / criteria | BetterBench; Inspect; Harvey LAB task shape (`CONFORMANCE.md`) | Method peers; paint only when task *content* maps via §3.3 |
| In-repo rubrics | `specs/rubrics/five-families.yaml`; `episode-feasibility.yaml` | Map to insight-construction / episode feasibility surface; usually shallow or deferred unless tied to a division |
| Control-point citations | Public regs/standards already on `cp_*` cells | Natural `R-CTRL-CITE` anchors |
| SPEC-04 standards map | ISDA CDM/FpML/DSB, ISO 20022, etc. | Related-match only; never identity; may support control-point depth |
| Declared later-phase evals | PB-Ops Eval (post-hoc cell only; I2/G1); FinExhaust prereg discipline | PB-Ops stays out of elicitation assets; may appear on overlay as seller-cell saturation **labelled as own-cell**, never as neutral public density |
| External capital-markets / risk / compliance public benches | To be listed in a living inventory file when authored | Only with stable URLs + dated check |

Out of scope for painting: private downstream-evidence loci, unreleased corpora,
any institution instance, any score that cannot be cited from a public page or
archival DOI.

## 6. Proposed deliverables (when implementation starts)

Ordered so each step is reviewable without claiming perfection:

1. **`reference/public-eval-inventory.v1.yaml`** — living list of public artifacts
   (id, title, URL, checked_at, license/access note).
2. **`reference/public-eval-surface-map.v1.json`** — rows: inventory id → BOCG
   identifiers → depth → mapping_status → band → rule_id → rationale → ruling
   metadata; pinned to release digests.
3. **Schema + fixture** — `specs/public-eval-surface-overlay.schema.json` +
   synthetic fixture (mirrors episode-surface discipline: no institution fields).
4. **Builder / checker** — `tools/public_eval_overlay.py` (validate, roll up
   saturation, emit void list, refuse stale release pins).
5. **Render** — deterministic markdown (and optional SVG/HTML) choropleth tables
   from the JSON; figures are derived artifacts, not hand-drawn claims.
6. **Gates** — S9-style conformance: schema validity; only admitted ids; paint
   filter; deny-list (SPEC-03 I3); inventory citations present; reproduction of
   roll-ups.
7. **SPEC stub** — SPEC-09 (or annex to SPEC-08) once the shape stabilises;
   bind into release manifest only then.
8. **CONFORMANCE.md row** — disclose overlay purpose and limits (peer density
   map ≠ construct-validity claim for BOCG).

## 7. Non-goals

- Perfect or complete coverage of all public finance/ML benchmarks
- Treating saturation as model capability or BOCG validation
- Changing admitted keys, tiers, aliases, cells or episode depth rules
- Painting from private lanes or seller-only scores without an explicit
  own-cell channel
- Continuous learned embeddings as the sole match basis
- Choropleth as a product UI commitment beyond reproducible static render

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Lexical false friends ("risk", "trading", "compliance") | R-REJECT + QUALIFIED limits; concept REVIEWED preferred for L3 |
| AUTO concepts overstate voids or saturation | Concept-grain voids optional; AUTO always labelled |
| Own-cell / PB-Ops leakage into "public" density | Separate channel or excluded from default saturation roll-up |
| Stale overlay after catalogue change | Release pin + gate failure on digest mismatch |
| Readers treat voids as "under-served" claims | Legend + limits text; I7 restated on every render |

## 9. Acceptance for this planning draft

This draft is done when:

- [x] Goal is stated as a supplement with episode-surface-aligned coordinates
- [x] Likelihood bands and matching rules are explicit enough to implement without
      inventing hidden scores
- [x] Choropleth channels distinguish saturation vs BOCG-admitted voids
- [x] Boundaries respect I7, I10, SPEC-03 floor and SPEC-08 depth semantics
- [ ] Inventory file and schema exist (implementation phase — not this draft)

## 10. Suggested first implementation slice

1. Inventory the CONFORMANCE.md peers + in-repo rubrics + all `cp_*` citation
   targets (no new web claims beyond what cells already cite).
2. Hand-map ≤ 20 rows under written rulings, preferring
   `prime_brokerage_financing` (REVIEWED) and ISDA-adjacent control points.
3. Emit division-grain saturation + void table for the 42 keys; publish as a
   draft figure with full legend.
4. Only then generalise schema/gates.
