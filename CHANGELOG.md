# Release changes

## Unreleased

## v0.6.2 — 2026-09-25

- SPEC-09 public-eval LLMAJ purity: front-loaded prereg + observable frozen prompt:
  - Lock prompt, rubric, inventory/catalogue digests, band weights, call settings
    and non-influence rules in `reference/public-eval-llmaj-prereg.v1.json`
    (`prereg_sha256` `dfcc901848f8…`).
  - Forbid owner-authored PENDING/PROPOSED `public_benchmark` rows and per-artifact
    prompt variants (would steer relative saturation or seller own coverage).
  - Live primary+sensitivity run under the locked prereg
    (`live-run-public-eval-llmaj/dfcc901848f8/`): four public_benchmark cards
    (Mercor Apex1 IB, Mercor Apex Agents, Rogo Big Finance Bench, Handshake
    BankerToolBench). Exact mapping-key intersection was empty on every card;
    ledger records four `paint_eligible: false` cases; no `public_benchmark`
    QUALIFIED paint promoted. Harvey LAB peer-shape L1 seed remains the only paint.

## v0.6.1 — 2026-09-25

- SPEC-09 public-eval surface overlay (correct paint scope):
  - Inventory is public peers / public rubrics-benchmarks-evals only; BOCG
    control-point citations and own rubrics do not paint saturation.
  - Likelihood-matched map (`L1`–`L3`) onto the SPEC-08 depth ladder; derived
    `division_rollup` for saturation vs voids (no presentation-standard artifact).
  - S9 gates; CONFORMANCE.md row 19; release-manifest binding.
- Catalogue, matrix, cells and task concepts remain byte-compatible with v0.6.0
  for evidence bindings; overlay is a supplement.

## v0.6.0 — 2026-09-24

- Add SPEC-08 task concepts and episode surface:
  - Group the released function and task definitions into concepts, one
    division at a time, with per-division provenance. `AUTO` divisions are
    machine-clustered by a deterministic, parameter-hashed method and are
    labelled as unread; `REVIEWED` divisions carry argued merges from
    `reference/task-concept-rulings.yaml` with a named reviewer, a date and a
    rationale per alias.
  - Rule `prime_brokerage_financing` REVIEWED: the released margin tasks split
    into compute-requirement and issue-and-collect concepts by terminal state,
    and nine composite role labels merge into one function concept (23
    aliases). The other 41 divisions stay AUTO.
  - Publish `reference/task-concepts.v1.json`, its schema, the rulings, the
    episode-surface schema, a synthetic surface fixture and the depth rule
    (`tools/episode_surface.py`): evidence depth is the deepest ratified
    touchpoint; candidates never raise it.
  - Add S8 gates and CI reproduction of the concept file; bind the new
    artifacts into the release manifest.
- The operating catalogue, coverage matrix, control-point cells and semantic
  profile are byte-identical to v0.5.0. Consumers pinned to an earlier release
  keep their evidence bindings.
- All changes remain above the SPEC-03 floor: definitions, schemas and rubrics
  only. No institution instance, corpus material or workflow claim is included.

## v0.5.0 — 2026-09-20

- Close ISDA regulatory overlap gaps (EPIC #6):
  - Add ISDA public standards (CDM, FpML, DSB UPI, ISO 20022) to SPEC-04.
  - Document in SPEC-04 that CDM/FpML model trade, event and legal agreement
    while the grid models division, function and control point, and that
    mappings are never identity assertions.
  - Extend mapping-policy usage notes so all declared standards, including the
    ISDA-adjacent entries, use only `close-match`, `related-match`,
    `narrower-than` or `schema-correspondence`.
  - Promote `derivatives_documentation_control` to `candidate_vocabulary_gaps`
    and record the non-normative derivatives trading documentation control
    candidate draft.
  - Author PROPOSED control-point cells for ISDA-native margin, reporting,
    confirmation, Determinations Committee and documentation controls, including
    a dedicated DC outcome-application cell under credit trading, four
    additional UMR/SIMM/CSA margin cells, and
    six reporting/confirmation cells (CFTC Part 43, EMIR REFIT UTI pairing,
    MiFIR Art. 26, OTC confirmation timeliness, portfolio reconciliation and
    reporting-error remediation).
  - Add SPEC-07 replayable compliance scenario contract and scenario run ledger
    schema (model release, manifest hash, scenario hash, verdict), plus the
    operational scenario schema, synthetic fixture, append-only row ledger and
    S7 conformance gates.
  - Add time and deadline semantics for SPEC-05 lifecycle states, including
    optional per-state `occurred_at` / `deadline_ref` / `calendar_ref`
    transitions alongside episode-level temporal anchors.
  - Publish G6 corroboration priority draft for ISDA-adjacent division keys and
    `docs/isda-overlap.md`.
  - Initialise the live-run corroboration ledger (1015 UNVERIFIED rows) so G6
    can be evaluated; keep the `glm-5.2` exclusion after an unsuccessful retry.
- Rebuild release manifest to bind new specs, schemas, cells and documentation.
- All changes remain above the SPEC-03 floor: definitions, schemas, rubrics and
  public citations only. No institution instances, corpus material or workflow
  claims are included.

## v0.4.0 — 2026-09-08

- Add operating reference contract 1.0.0: public division/function/task/control-point identifiers and a schema for private, dated operating-unit registers.
- Derive and verify the reference catalogue from existing matrix/cell bytes; preserve the grid's model-consensus and curation limits.
- Bind the new contract, schema and catalogue into the release manifest. Require catalogue reproduction before release.
- Include the canonical entity semantics and CI conftest repair already merged since v0.3.0.

The public release contains definitions only. It does not contain institutional desks, local settings, private evidence or a compliance attestation. Existing division keys and control-point cells are preserved.
