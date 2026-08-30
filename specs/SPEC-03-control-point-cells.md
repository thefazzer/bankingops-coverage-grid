# SPEC-03 — Control-point cells: the sub-division floor

```
ARTIFACT : BOCG control-point cell layer (extends SPEC-01 divisions downward)
STATUS   : v0.1 goal spec — Phase 1 ships schema + gates; generation is Phase 2
DEPTH    : division -> function -> CONTROL POINT. Stops there. Workflow-level knowledge is
           doctrinal by definition and lives outside this public artifact (see I4).
CURATION : SOTA-model generated, practitioner-curated; every release names the curator
           and the generating model+date in its methods block.
```

## 0. GOAL

Extend the model-consensus division taxonomy to the level of named CONTROL POINTS: the
costly, operationally common checkpoints where a job function can fail in a way an
external, citable authority already prices. Each cell places a public competency floor:
a benchmark or environment either exercises the control point or visibly does not.
Cells assert EXISTENCE and GOVERNANCE of a control point — never how any institution
implements it.

## 1. NON-NEGOTIABLE INVARIANTS

```
S3-I1 CITATION_REQUIRED       every cell carries >= 1 public, dated, web-accessible citation
                              (regulation article, industry-standard clause, market-practice doc).
                              No citation => cell invalid. Enforced by S3-G1.
S3-I2 CONSEQUENCE_ANCHORED    every cell names a failure consequence with a PUBLIC cost anchor
                              (e.g. CSDR cash-penalty regime, TMPG fails charge, published fine).
                              "Costly" is demonstrated, never asserted. Enforced by S3-G2.
S3-I3 PRIVATE_NAMESPACE_DENY  no cell text may reference the seller's private corpus, systems,
                              counterparties or file paths. FORBIDDEN_TOKENS list applies
                              (SPEC-01 §2.3 plus tools/forbidden_cells.txt). Enforced by S3-G3.
S3-I4 STOP_ABOVE_WORKFLOW     cells name WHAT is controlled and WHO governs it, never HOW a
                              specific desk executes it. A cell containing procedure steps,
                              orderings, or thresholds not present verbatim in a cited public
                              source is REJECTED.
S3-I5 SOLUTION_NEUTRAL        no cell references any benchmark, environment, product or vendor
                              as satisfying it. Coverage claims live in separate, post-hoc
                              coverage-map files (SPEC-01 I10 pattern), one per claimant.
S3-I6 CURATED_OR_ABSENT       a generated cell not yet practitioner-reviewed is status:PROPOSED
                              and excluded from release bundles. Only status:CURATED ships.
```

## 2. CELL SCHEMA

See `specs/control-point-cell.schema.json` (JSON Schema 2020-12). Field order mirrors
SPEC-01 anchors-before-judgement: citations and consequence anchor precede all prose.

## 3. RUNNABLE GATES (exit non-zero; wired pre-publish)

```
S3-G1 CITATION_GATE     every cells/*.json validates against the schema AND every citation
                        has source_name + url + accessed date.
S3-G2 CONSEQUENCE_GATE  every cell's consequence_anchor names a public source; magnitude
                        field present (may be qualitative band, never invented precision).
S3-G3 DENY_GATE         forbidden-token scan over all cell files and this spec.
S3-G4 CONFORMANCE_GATE  CONFORMANCE.md parses; every row EVIDENCED/PARTIAL/NOT MET; no row
                        removed relative to the committed baseline row count.
```
