# SPEC-06 — Operating units and versioned reference data

Contract version: 1.0.0. Introduced in BOCG release v0.4.0.

BOCG owns reusable definitions of divisions, functions, terminal tasks and control
points. Institutions own the particular units that perform that work, their
people, books, systems and settings. The public contract defines their exchange
shape; it contains no institution register or occurrence claim.

## Public reference catalogue

`reference/operating-catalogue.v1.json` is deterministically derived from the
existing matrix and curated cells. Run `python3 tools/build_operating_catalogue.py`
and verify with `--check`. The catalogue retains model-consensus status, source
hashes and task descriptions. Derivation does not validate or ratify the grid.

Division identifiers preserve the admitted key. Function and task identifiers
use a 96-bit prefix of SHA-256 over the exact kind, division key and source
canonical label. Control points retain their existing cell identifier. Collisions
fail the build. A changed label yields a new identifier. A stable identifier does
not prove unchanged meaning: consumers compare the complete definition digest.
Functions and tasks are grouped under their division; no ungrounded function-to-
task hierarchy or institution workflow is inferred.

## Private consumer register

`specs/operating-unit-register.schema.json` defines a consumer-owned register.
Units have issuer-scoped identities, legal entities, optional parents, evidence,
validity and review state. Functional assignments are many-to-many and link to
released reference identifiers. Typed relationships connect units to people,
books, systems, owner roles, locations, calendars and reference datasets.
Settings carry explicit value types, context, owner and evidence.

Every assertion retains source references and review status. Reviewed/rejected
assertions require a named reviewer, time and reason; that records a disposition
and does not certify independent review. Synthetic fixtures cannot establish
record-plane facts. A legal entity, unit and function are distinct objects.
Regulatory applicability cannot be inferred solely from a division assignment.

Validity intervals are half open. A missing bound is unknown; it must not become
unlimited validity or be substituted with observation time. Effective-at queries
exclude unknown bounds and rejected assertions; they distinguish proposed from
reviewed. Settings with the same unit, key and context may not have overlapping
validity, including intervals whose separation cannot be established. Parent
links must be acyclic, remain within the same legal entity, and cover the child
interval when both are known.

## Versioning and upgrades

Registry revisions are immutable snapshots with a predecessor digest. A consumer
binds each revision to the BOCG release, manifest and catalogue digests, and the
contract version. Compare-and-swap prevents concurrent writers from overwriting
history. Tenant and dataset identities cannot change along a revision chain.

A BOCG upgrade verifies the published release commit, manifest, all artifact
bytes, and the registry schema. Added definitions do not imply new local
assignments. Changed or removed definitions produce a review report and block
automatic migration of affected registers. Even when all used definitions are
unchanged, migration creates a new revision and preserves the previous release
binding. Old SKU evidence and scores are immutable.

`specs/operating-reference-contract.json` carries the machine-readable policy.
Consumers enforce its cross-record rules in addition to JSON Schema validation.
