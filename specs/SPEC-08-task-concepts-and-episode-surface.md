# SPEC-08 — Task concepts and the episode surface

```
ARTIFACT : grouped public definitions (task and function concepts) and one
           consumer-owned projection shape (the episode surface)
STATUS   : v1.0.0 normative; introduced in BOCG release v0.6.0
SOURCES  : reference/task-concepts.v1.json, reference/task-concept-rulings.yaml,
           specs/task-concepts.schema.json, specs/episode-surface.schema.json,
           specs/fixtures/episode-surface-synthetic.json, tools/episode_surface.py
BOUNDARY : definitions and a depth rule only; no institution instance, no
           corpus text, no occurrence claim
```

## 0. Purpose

SPEC-06 releases 217 function labels and 766 terminal task labels exactly as
the live run produced them. Many of them are surface variants of the same
work: five vendors describe one margin task five ways. A consumer that joins
its own evidence to the grid through those labels (SPEC-04 §5, docs/downstream-
evidence.md) then reports coverage per variant, which overstates breadth and
understates depth.

SPEC-08 adds one layer above the released labels and one shape below them:

- a **task concept** (and a **function concept**) groups released definitions of
  one division that denote the same operational work;
- an **episode surface** is the consumer-owned record of which divisions,
  concepts, released tasks and control points one Episode (SPEC-05) touches,
  and how deep the ratified evidence goes.

Neither changes an admitted division key, a released label, a tier or the
provisional status of the live run. The operating catalogue is byte-identical
across this change; concepts refer to it by reference identifier.

## 1. Provenance classes

Every division carries exactly one review status, and no division mixes the two:

| Status | Basis | What it means |
|---|---|---|
| `AUTO` | `machine_clustered` | Concepts were produced by the deterministic method in §1.1. No human has read the groups. They are a machine prior, published so that the grouping is inspectable and reproducible, not because it is right. |
| `REVIEWED` | `argued_merge` / `standalone_under_review` | Every merge in the division is argued in `reference/task-concept-rulings.yaml` with a named reviewer, a date, a division-level basis and a rationale per alias. Definitions the ruling does not merge stand alone under `standalone_under_review`. |

A consumer MUST surface the review status wherever it surfaces a concept. An
`AUTO` concept MUST NOT be described as curated, reviewed or validated. A
`REVIEWED` status records that a named reviewer argued the merges; it does not
record independent review (CONFORMANCE.md row 10 still applies).

In v0.6.0 one division is `REVIEWED` (`prime_brokerage_financing`: two argued
task merges, one argued function merge, 23 aliases) and 41 are `AUTO`.

### 1.1 Machine method (AUTO)

`tools/build_task_concepts.py` clusters the released labels of one division at
a time. Tokens come from `bocg.canon.canon_name` with digits dropped, a fixed
verb/noun variant fold and a fixed stoplist; both lists are hashed into the
output's `method` block. Similarity is Jaccard over token sets. Clustering is
average-linkage agglomerative, merging the most similar pair of clusters while
its mean pairwise similarity is at least `0.4`, ties broken by the sorted
label order. The concept label is the shortest member label, ties alphabetical;
the machine never invents a label. The method is deterministic: the same
catalogue bytes and the same parameters reproduce the same file, and
`--check` fails the release otherwise.

Known limits, stated rather than tuned away: token overlap merges tasks that
share nouns but differ in verb (a rebate calculation and a reconciliation of
the same product), and separates tasks that describe one action in different
vocabulary. That is why the status is `AUTO`.

### 1.2 Rulings (REVIEWED)

A ruling names one division, a `ruled_by`, a `ruled_at` date, a division-level
`basis`, and a list of concepts. Each ruled concept names its kind, its label,
its members (released labels of that division) and a rationale per alias. A
concept label is either a member label (`label_source: member`) or a label the
ruling authors when no member is a natural canonical (`label_source: ruled`).
The builder refuses a member that is not a released definition of the
division, a member named twice, a merge with fewer than two members, and an
alias without a rationale. Members a ruling does not name become standalone
concepts of that division.

## 2. Concept identity and comparison

A concept identifier is `<kind>:<division_key>:<24 hex>` where the digits are the
SHA-256 prefix of the exact kind, division key and concept label, following the
SPEC-06 identity rule. A stable identifier does not prove unchanged membership:
each concept carries `definition_sha256` over its full definition, and consumers
compare digests on upgrade exactly as SPEC-06 requires for catalogue entries.
Concepts never cross a division; a label that appears in two divisions yields
two concepts.

An **alias** is a member whose label differs from the concept label. Alias
counts are reported per division so that a consumer can see how much grouping
each status performed.

## 3. Episode surface

`specs/episode-surface.schema.json` defines the shape a consumer uses to record
which grid surface one Episode touches. It carries identifiers, statuses and
dates only. Every free-text field of SPEC-05 (source spans, atoms, topics)
stays in the consumer's private store; the schema has no property that could
hold them, and `episode_ref` and `source_profile_ref` are opaque hashes by
pattern, never corpus, message, graph or institution identifiers.

A touchpoint names a division and, optionally, a function concept, a task
concept, a released task and a control point, together with its mapping
status and the ruling that produced that status. Its `depth` states which of
those it claims, and the schema requires the matching identifier.

### 3.1 Depth rule

Depth is ordered `none < division < function_concept < task_concept <
terminal_task < control_point`.

- `evidence_depth` is the deepest touchpoint whose status is `RATIFIED_MAPPING`
  or `QUALIFIED_MAPPING`.
- `candidate_depth` is the deepest touchpoint whose status is `PROPOSED` or
  `PENDING`. It is displayed, never counted.
- `REJECTED_MAPPING` and `DEFERRED_MAPPING` touchpoints remain on the record
  and set neither depth.
- Candidates never raise evidence depth. A ratified division mapping with a
  candidate task-concept mapping has evidence depth `division`.

The synthetic fixture binds the task-concept digest of this release and carries
a zero manifest digest: the fixture is itself a manifest artifact, so it cannot
name the digest of the manifest that binds it. Consumers fill both.

`tools/episode_surface.py` implements the rule and the release-bound checks
(concept and task identifiers must exist in the pinned release, in the named
division, and a released task must be a member of the task concept it is paired
with). The S8 gate applies both to the synthetic fixture.

### 3.2 What depth is not

Depth is a statement about how specifically ratified evidence has been bound
to the grid. It is not a coverage claim, not a score, not evidence that the
work occurred as described, and not a ranking of divisions. An Episode at
`control_point` depth in one institution says nothing about another.

## 4. Runnable gates (S8, in `tools/gate_conformance.py`)

| Gate | Check |
|---|---|
| S8-G1 | `reference/task-concepts.v1.json` validates against its schema and reproduces byte-for-byte from the catalogue and rulings. |
| S8-G2 | Every released function and task belongs to exactly one concept of its own division; no concept identifier collides. |
| S8-G3 | A division is `REVIEWED` only under a ruling with a named reviewer, a date and a basis; `AUTO` divisions carry no ruling and no reviewed alias; the reviewed alias count equals the sum over rulings. |
| S8-G4 | `specs/episode-surface.schema.json` is a valid schema; the synthetic fixture validates, follows the depth rule and references only identifiers of this release. |
| S8-G5 | The deny list of SPEC-03 I3 applies to the rulings, the concept file, this specification and the fixture. |

## 5. Release binding

The release manifest binds this specification, both schemas, the rulings, the
concept file and the synthetic fixture. `build_release_manifest.py` refuses to
build while the concept file is stale. Consumers that pin an earlier release
are unaffected: the catalogue, matrix and cells are unchanged, so an evidence
ledger bound to v0.3.0 through the coverage-matrix digest projects onto v0.6.0
without relabelling, exactly as SPEC-06 requires.
