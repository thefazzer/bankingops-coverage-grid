# CONFORMANCE — how this artifact maps to its peers' standards

```
STATUS   : living matrix; audited by `python3 tools/gate_conformance.py` (exit non-zero on drift)
RULE     : every row is either EVIDENCED (names the file/gate that satisfies it) or NOT MET (with reason).
           A row may never be silently dropped. Claiming conformance not in this table is prohibited.
VERIFIED : all cited standards checked against the live web 2026-08-30.
```

## Reference standards (web-accessible, dated)

| Ref | Standard | Source | Checked |
|---|---|---|---|
| DS | Datasheets for Datasets, Gebru et al., v8 (Dec 2021) | arxiv.org/abs/1803.09010 | 2026-08-30 |
| BB | BetterBench benchmark-assessment criteria (46 criteria) | betterbench.stanford.edu | 2026-08-30 |
| IN | Inspect evaluation framework (UK AI Security Institute, active) | github.com/UKGovernmentBEIS/inspect_ai | 2026-08-30 |
| LAB | Harvey LAB task format (documents + task.json match-criteria rubrics) | github.com/harveyai/harvey-labs | 2026-08-30 |

## Matrix

| # | Criterion (source) | Status | Evidence |
|---|---|---|---|
| 1 | Motivation, composition, collection process documented (DS §3) | EVIDENCED | SPEC-01 §0–§4; live-run README |
| 2 | Curation/labeling process disclosed, curator named (DS) | EVIDENCED | SPEC-01 I8 CORROBORATE_OR_DROP; practitioner curation declared in SPEC-03 §1 |
| 3 | Known limitations stated in-artifact (DS/BB) | EVIDENCED | live-run-20260826/README "provisional; anchor-corroboration gate not satisfied"; this table's NOT MET rows |
| 4 | Versioning + changelog, immutable releases (BB maintenance) | PARTIAL | git history + hash-fixed inputs (I1, I4); no semver release tags yet — cut at v1.0.0 |
| 5 | Contamination controls (BB implementation) | EVIDENCED | SPEC-01 I2 ZERO_SEEDING + G1 CONTAMINATION_GATE; LAT salted canaries (SPEC-02) |
| 6 | Construct validity: what the benchmark measures is argued, not assumed (BB design) | EVIDENCED | SPEC-01 §0 (anchored divisions, seat-cost + terminality filters I9); gaps NOT model-elicited (I7) |
| 7 | Statistical reporting basis (BB) | EVIDENCED | agreement matrix + corroboration ledger (SPEC-01 §5–§6), all raw responses published verbatim (I4) |
| 8 | Task format executable under a standard harness (IN) | NOT MET | no Inspect adapter yet; planned when PB-Ops Eval tasks publish — grid itself is a taxonomy, not tasks |
| 9 | Peer task-shape conformance (LAB) | EVIDENCED | harvey-labs PR #153: two banking tasks accepted-form in the peer's own schema |
| 10 | Independent review of content (BB; BIG-bench practice) | NOT MET | single practitioner-curator; external PRs invited; second named reviewer sought before v2 |
| 11 | Inter-rater reliability reported (BB) | NOT MET | no second-rater pass yet; required before any grading-reliability claim |
| 12 | Multi-org baselines (BB) | PARTIAL | 5 vendor families in live-run (cold, raw-logged); no external lab has run it |
| 13 | Separation of benchmark authorship from measured product (this project's own bar) | EVIDENCED | I2/I10 + G1; SPEC-03 I3 PRIVATE_NAMESPACE_DENY makes it machine-checked for cells |
| 14 | Preregistration + reproduction of any reported numbers (exceeds peers) | EVIDENCED | FinExhaust eval discipline: preregs sha-bound, results claimed only after reproduction |
| 15 | Every cell/claim carries a public, dated citation (this project's own bar) | EVIDENCED | SPEC-03 I1 CITATION_REQUIRED, gate S3-G1 |
| 16 | Public semantic mappings reuse recognized vocabularies without asserting identity, occurrence or local implementation | EVIDENCED | SPEC-04; `specs/common-semantic-profile.yaml`; S4 gates in `tools/gate_conformance.py` |

NOT MET rows are commitments, not apologies: 8 and 11 gate any "runnable benchmark" claim;
10 gates any "independently reviewed" claim. This file ships with every release.
