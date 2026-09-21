# Release changes

## v0.5.0 — 2026-09-20

- Close ISDA regulatory overlap gaps (EPIC #6):
  - Add ISDA public standards (CDM, FpML, DSB UPI, ISO 20022) to SPEC-04.
  - Document in SPEC-04 that CDM/FpML model trade, event and legal agreement
    while the grid models division, function and control point, and that
    mappings are never identity assertions.
  - Extend mapping-policy usage notes so all declared standards, including the
    ISDA-adjacent entries, use only `close-match`, `related-match`,
    `narrower-than` or `schema-correspondence`.
  - Promote `derivatives_documentation_control` to `candidate_vocabulary_gaps`.
  - Author five PROPOSED control-point cells for ISDA-native margin, reporting,
    confirmation, Determinations Committee and documentation controls.
  - Add SPEC-07 replayable compliance scenario contract and scenario run ledger
    schema (model release, manifest hash, scenario hash, verdict).
  - Add time and deadline semantics for SPEC-05 lifecycle states.
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
