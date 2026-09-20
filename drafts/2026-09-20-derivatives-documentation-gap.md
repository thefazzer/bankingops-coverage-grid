# DRAFT — derivatives legal documentation control vocabulary gap

> **CANDIDATE ONLY**: this draft records a proposed candidate vocabulary gap.
> It is non-normative and does **not** admit a new division key. SPEC-01
> invariants require division keys to come from a re-elicitation run, not from
> an author's assertion.

Staged from issue #11 / live-run-20260826 observation. Local draft only:
committing, pushing, and any future release that re-mints the manifest are
separate owner actions. Contains no corpus text, no client identities, no
personal names.

## Observed gap

The grid has no division for derivatives legal documentation. ISDA Master,
CSA, GMRA and GMSLA execution, term capture and protocol adherence currently
sit under `client_lifecycle_kyc` ("Client Lifecycle Management, KYC and Trading
Documentation Control"), which had **model_support 0** in
`live-run-20260826/matrix.csv`. This is precisely where an ISDA-side AI product
would live.

## Proposed candidate note

A candidate entry in `specs/common-semantic-profile.yaml`
`candidate_vocabulary_gaps.candidates` alongside the existing
margin-terms-governance note:

- derivatives trading documentation control (ISDA Master / CSA / GMRA / GMSLA
  execution and term capture; protocol adherence; netting-opinion coverage);
  nearest existing key `client_lifecycle_kyc`; name left open.

## Why no new division key is admitted here

`candidate_vocabulary_gaps` is explicitly non-normative. Adding a candidate
records the observation for a future re-elicitation run; it does not mint a
key. Under SPEC-01 invariants, new division keys must be produced by the
elicitation and corroboration pipeline, not asserted by an author in a profile
or draft.

## Relationship to existing keys

`client_lifecycle_kyc` remains the nearest admitted key. If a future run
isolates derivatives documentation control as a distinct division, the
candidate note can be superseded by an admitted key with its own semantic
profile mappings.
