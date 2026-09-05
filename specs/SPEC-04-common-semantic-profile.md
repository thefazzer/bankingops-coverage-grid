# SPEC-04 — Common semantic profile

```
ARTIFACT : standards-backed meanings for existing BOCG objects
STATUS   : v0.1 proposed profile
SOURCE   : specs/common-semantic-profile.yaml
DEPTH    : division -> function -> control point; never institution workflow
```

## 0. Purpose

`common-semantic-profile.yaml` is the portable semantic layer shared by BOCG
producers and consumers. It maps fields that already exist in SPEC-01 and
SPEC-03 to public vocabularies. It does not create another taxonomy, another
control-point schema, or an occurrence ontology.

The machine-readable profile is normative. This document states its boundary
and interpretation rules.

## 1. Reuse rather than recreation

- `division_key` remains the admitted SPEC-01 key. The profile classifies it as
  a SKOS concept; it does not mint a parallel division identifier.
- `job_function`, `control_point`, citations, consequence anchors, status and
  methods remain fields of `control-point-cell.schema.json`.
- Coverage claims remain separate, post-hoc artifacts under SPEC-01 I10 and
  SPEC-03 I5. The profile only supplies their public relationship semantics.
- Mappings are deliberately weaker than identity. A `close-match`,
  `related-match`, `narrower-than` or `schema-correspondence` never means
  `owl:sameAs`.

## 2. Public standards layer

The profile reuses:

- SKOS for taxonomy concepts, schemes, hierarchy and mappings;
- W3C PROV-O for evidence entities, attribution, derivation and generation
  time;
- W3C Organization Ontology for organizational units and roles;
- DCMI Terms for identifiers, descriptions, subjects, references and parts;
- FIBO for financial-business context where a narrower mapping is justified;
- BCBS 239, ISO 37301 and ISO 19011 as governance context for data controls,
  compliance and audit evidence.

These correspondences do not assert that an institution implements a control,
conforms to a standard, has a particular organization structure, or performed
an activity.

## 3. Hard boundary

This repository remains a public coverage taxonomy. The common profile rejects
objects below the SPEC-03 floor, including observation atoms, traces, Episodes,
email-discourse annotations, assessor frameworks and institution-specific
procedures.

The distinction is intentional:

```text
BOCG public layer: division -> function -> control point
consumer layer:    evidence occurrences, workflow, adjudication, implementation
```

Moving a portable mapping here does not move private evidence, implementation
logic, corpus labels or workflow claims with it.

## 4. Conformance

`python3 tools/gate_conformance.py` enforces:

- the profile ID, version, scope ceiling and non-occurrence boundary;
- resolvable references to the existing control-point JSON Schema;
- complete semantic coverage of every required SPEC-03 cell field;
- declared authorities and permitted mapping strengths;
- HTTPS standards references; and
- retention of the prohibited below-floor object list.

The gate validates the contract, not the truth of a future coverage claim.

## 4.1 Canonical entity semantics

The `entity_semantics` contract defines shared business meanings and identity
rules for consumers. BOCG owns these definitions; consumers retain private
instances, observations, evidence and adjudication history. Corpus membership
and equal labels do not create or disprove identity.

A resolved person can hold multiple evidenced employment relationships over
time. A legal entity remains the same entity when its counterparties, roles or
perspective change. FACING and FACED remain directed contextual relationships
under `role_semantics`, with applicable time, party roles and transaction/leg
context preserved. Observation dates never supply missing tenure dates.

Product types represent governed regulatory reference definitions. Their keys
include authority, regime, identifier, version and effective bounds. Aliases
can resolve to the same reference across corpora; a close vocabulary mapping
does not prove regulatory equivalence. Classification of an instrument never
merges distinct instrument, contract or trade instances.

Canonicalisation must identify the standard or reference represented, and
separately record evidence for an actual instance identity. Unresolved labels
remain observations with candidate links until evidence supports resolution.

## 5. Release assertion

Every consumer must select a GitHub release, download its
`bocg-release-manifest.json` asset, validate it against
`bocg-release-manifest.schema.json`, and verify the SHA-256 digest and byte size
of every listed artifact at the release tag. A consumer may cache a previously
verified assertion for resilience, but must not describe it as the latest
release unless it has checked the GitHub latest-release endpoint during the
current refresh window.

The manifest binds the release tag and commit, the semantic-profile identity
and digest, all public control-point cells, normative specs, conformance record
and selected release-run artifacts. The manifest's own digest is calculated
over its canonical JSON form with `manifest_sha256` omitted.
