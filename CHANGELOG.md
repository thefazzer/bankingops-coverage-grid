# Release changes

## Unreleased

- Add ISDA-adjacent public standards (CDM, FpML, DSB UPI/ISDA product taxonomy,
  ISO 20022) to the SPEC-04 common semantic profile standards layer.
- Extend SPEC-04 mapping-policy usage notes to state that all declared
  standards, including the new ISDA-adjacent entries, are only ever mapped with
  `close-match`, `related-match`, `narrower-than` or `schema-correspondence`,
  never identity.

## v0.4.0 — 2026-09-08

- Add operating reference contract 1.0.0: public division/function/task/control-point identifiers and a schema for private, dated operating-unit registers.
- Derive and verify the reference catalogue from existing matrix/cell bytes; preserve the grid's model-consensus and curation limits.
- Bind the new contract, schema and catalogue into the release manifest. Require catalogue reproduction before release.
- Include the canonical entity semantics and CI conftest repair already merged since v0.3.0.

The public release contains definitions only. It does not contain institutional desks, local settings, private evidence or a compliance attestation. Existing division keys and control-point cells are preserved.
