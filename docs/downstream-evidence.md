# Downstream evidence note: how the grid's division keys have been exercised

```
ARTIFACT : evidence note (non-normative; not a manifest artifact; not a coverage claim)
AS OF    : 2026-09-03
SOURCE   : a preregistered evaluation lane run privately by the grid's author
DATA     : a private calibration corpus (one institution, not released)
RULE     : the grid is a model-consensus prior; the lane's results are calibration
           evidence about that corpus, not validation of the grid
```

## 0. Why this note exists

SPEC-01 §0 says the grid is the MAP and that competency gaps are never elicited from
models; `bocg/bocg/assets/limits.md` says gaps "can only come from measured task
scores in a later phase; nothing in this bundle is such a score". This note is the
first public record of such a later phase touching the grid: a preregistered
evaluation lane that pins a BOCG release manifest (SPEC-04 §5) and joins its material
to the grid only through admitted division keys. It records which keys were exercised
and what was measured, in the lane's own status language, so that nobody reads more
into the grid than the grid claims.

Everything below is scoped to one institution, two loci and model judges only. The
live run in `live-run-20260826/` remains PROVISIONAL (G6 corroboration outstanding);
nothing here changes an admitted key, a tier, or that status.

## 1. Division keys exercised

A locus is one topic area of the private corpus, with its own curated material. Two
loci were evaluated. The lane assigns each locus to admitted division keys of the
locked coverage matrix (42 keys, `live-run-20260826/matrix.csv`). The assignment is
the lane author's, recorded in the lane's private registry; it is not a grid output.

| Locus | Subject matter (generic) | Division key(s) | Live-run consensus (`matrix.csv`) |
|---|---|---|---|
| A | client financing within prime brokerage: portfolio-swap (synthetic) financing operations | `prime_brokerage_financing` (primary); `repo_secfin_collateral` (secondary) | primary: model_support 5, tier MODERATE, named by all 5 vendors on the board (`RUN_SUMMARY.json` `support_5_of_5`); secondary: model_support 2, tier WEAK |
| B | support procedures for a swaps application (trade-support runbook material) | `trade_lifecycle_operations` | model_support 3, tier WEAK |

Reading notes:

- Both keys are sell-side operational divisions of the institution; neither is a
  `buyside_*` key. That follows the role/facing rule in
  `specs/common-semantic-profile.yaml` (`division_key_interpretation`): assigning a key
  asserts the institution holds the role the division belongs to.
- Locus A is swaps-flavoured financing and sits under `prime_brokerage_financing`, not
  `rates_trading` or `fx_trading`. That is the reading the profile's non-normative
  candidate note on the equity-financing hierarchy asks consumers to keep.
- Locus B is application-support material assigned to `trade_lifecycle_operations`,
  whose alias pool in `live-run-20260826/aliases.yaml` covers trade support,
  confirmation and settlement lifecycle work. No admitted key names application
  support as such. That is a vocabulary observation, not a proposal.
- The lane's internal locus labels, task identifiers and doctrine titles are withheld
  from this note.

## 2. What the lane measures (design, in brief)

The unit of measurement is task-level work product. The same evidence model answers
institution-specific questions generated from the corpus, once per arm and replicate,
and each written answer is scored as the fraction of rubric criteria passed, by a
primary model judge with a second model judge for sensitivity. Arms differ only in the
reference material pasted into the prompt:

| Arm | Reference material |
|---|---|
| unaided | none |
| pack | the locus's curated rule file, about 8,000 to 12,000 characters, distilled from the corpus with verbatim evidence lines |
| wrong-locus pack | the other locus's pack, same format and budget (content-specificity control) |
| retrieval | question-keyed passages of the corpus, cut to the pack's budget (matched) or to twice it (twice-budget) |
| quotes | the pack stripped to its verbatim evidence lines |
| union | the pack followed by retrieval |

Statistics: paired per-task deltas between arms; exact one-sided sign-flip
permutation test; alpha 0.05 per component. A claim passes only if every
preregistered component rejects (intersection-union), both loci are positive under
the primary judge, and the second judge agrees in direction. Hypotheses, contrasts,
falsifiers and decision rules are hash-locked before any scored answer exists; failed
sheets are never written; freeze integrity (one runner hash, clean tree) is logged on
every call.

The public environment for tasks of this class is the synthetic clean-room
evaluation repository, https://github.com/thefazzer/cleanroom-eval (sealed synthetic
episodes, task contracts, reward-hacking gates, hash-bound run evidence). The lane's
results are calibration evidence only. None of its questions, records or packs is in
that repository, and the corpus is not released.

## 3. Measured outcomes as of 2026-09-03

Deltas are differences in mean task score (fraction of criteria passed, 0 to 1)
between the first-named arm and the second; p is the exact one-sided sign-flip
permutation p-value; intervals are BCa 95% where the lane reports them. Status labels
are quoted from the lane's results ledger. "Per locus" lists locus A, then locus B.

### T4 v8 (complete 2026-09-01; 10 tasks over the 2 loci; judge agreement 95.8%)

Status: **canonical claim NOT passed** (the C3 component failed).

| Contrast | Delta | p | Reading |
|---|---|---|---|
| C1 pack vs unaided | +0.408 | 0.0020 | task-level uplift exists |
| C2 pack vs wrong-locus pack | +0.467 | 0.0078 | content-specific |
| C3 pack vs matched-length raw excerpts | +0.108 | 0.256 | not established; interval spans 0 |
| C4 pack vs quotes-only | +0.367 | 0.0059 | VOID (erratum 2026-09-02): the quotes-only context was empty, so the arm was byte-identical to unaided |

Honest count after the erratum: two of three valid contrasts supported. Diagnostics
recorded strong locus heterogeneity (per-locus deltas +0.65 and +0.17); one refusal
(retried), no missing judge outputs, no excluded tasks.

### T5 v1 (complete 2026-09-02; 9 tasks after one exclusion for nine API refusals; 621 calls; judge agreement 686/708, kappa 0.94)

Status: **canonical claim NOT passed** (C3b and C4 did not reject).

| Contrast | Delta | p | Reading |
|---|---|---|---|
| C1 pack vs unaided | +0.537 | 0.0059 | replicates |
| C2 pack vs wrong-locus pack | +0.593 | 0.0039 | replicates |
| C3b pack vs question-keyed equal-length retrieval | +0.269 | 0.152 | not established; interval spans 0; the preregistered falsifier fired and the "compact representation" line is closed |
| C4 pack vs quotes-only (first non-empty quotes arm, 16 to 20% of pack characters) | +0.148 | 0.172 | not established; interval spans 0 |
| C3a pack vs oracle raw window (descriptive) | +0.046 | 0.461 | descriptive only |

Disclosed by the lane: the excluded task is not a conservative exclusion (the pack
also scored 0.00 on it); the quotes arm was partial (format mismatch, generous to the
pack); a provider-wall pause with a same-version resume. Descriptively, on 6 of 10
tasks one of pack and retrieval scored at least 0.83 while the other scored at most
0.25: coverage is largely complementary.

### T6 v2 (complete 2026-09-02; 20 tasks; 3,139 logged calls; 420 sheets; 0 refusals; judge agreement 1,536/1,596, kappa 0.92)

Status: **canonical claim NOT passed** (U1 did not reject at alpha 0.05; U2 rejected).

| Contrast | Delta | p | BCa 95% | Per locus | Second judge (n=19) |
|---|---|---|---|---|---|
| U1 union vs twice-budget retrieval (gate) | +0.158 | 0.061 | [-0.004, 0.358] | +0.267, +0.050 | +0.184, p=0.055 |
| U2 union vs wrong-locus pack + same retrieval (gate) | +0.179 | 0.041 | [0.017, 0.379] | +0.275, +0.083 | +0.197, p=0.046 |
| U3 union vs pack (descriptive) | +0.104 | 0.042 | [0.017, 0.242] | -0.025, +0.233 | +0.105, p=0.055 |
| C1r pack vs unaided (descriptive; third replication) | +0.454 | 0.00003 | [0.288, 0.625] | +0.500, +0.408 | +0.465, p=0.00006 |
| C3b-r pack vs matched retrieval (descriptive) | +0.100 | 0.225 | [-0.129, 0.358] | +0.350, -0.150 | +0.092, p=0.255 |
| C4f pack vs fixed quotes (descriptive; first valid quotes control) | +0.063 | 0.206 | [-0.033, 0.225] | +0.192, -0.067 | +0.061, p=0.229 |

The preregistered falsifier applies as written: standalone pack authoring stops as a
product activity; curation continues for retrieval, evidence selection, routing and
adjudication. Two of the twenty tasks scored zero in every arm (8 retained zero deltas
on U1). The second judge is missing on one task's sheets, hence n=19. Doubling the
retrieval budget changed the score on five of twenty tasks, by +0.05 on average, so
the U1 delta is not a length effect.

### T7-v3 COMPLETE 2026-09-03; union claim PASSED narrowly

T7-v3 COMPLETE 2026-09-03 (freeze intact). Union claim PASSED narrowly under the
intersection-union rule. Estimand: conditional on oracle answerability (union uplift
over retrieval for institution-specific tasks demonstrably answerable from the source
corpus). n=27 admitted tasks from 2 loci.

| Contrast | Delta | p | BCa 95% | Standing |
|---|---|---|---|---|
| U1 union vs twice-budget retrieval (gate) | +0.130 | 0.047 | [0.009, 0.296] | rejects (narrowly) |
| U2 union vs wrong-locus pack + same retrieval (gate) | +0.228 | 0.003 | [0.096, 0.395] | rejects |

Decision-tree branch reached: untouched-locus replication, not another optimisation
run. Part A admitted no routing signal (best gain +0.032 under the +0.05 bar); no
routed arm ran. Two earlier T7 versions halted before any scored answer (v1 Gate A,
v2 admission instrument defect).

### Pattern across runs (descriptive, never a gate)

- Pack over unaided has replicated three times (+0.408, +0.537, +0.454). Pack over
  the wrong-locus pack has replicated twice (+0.467, +0.593) and the union form once
  (+0.179): the gain depends on the content being the right content.
- Pack over equal-length retrieval has not been established in any run (+0.108,
  +0.269, +0.100). Union over twice-budget retrieval was not established in T6
  (+0.158, p=0.061) and PASSED narrowly in T7 on oracle-answerable tasks (+0.130,
  p=0.047); next is untouched-locus replication.
- The two loci disagree. Locus A rewards the pack in T4, T5 and T6 (in T6 the union
  beats twice-budget retrieval there by +0.267); on locus B retrieval already answers
  most tasks and the pack adds +0.050. Per-task pack effects range from +1.0 to -0.5,
  so a twenty-task mean is unstable: the lane's planning estimate gives a twenty-task
  run about a 50 percent chance of passing U1 if the true effect is what T6 measured,
  and thirty admitted tasks about 70 percent.

## 4. Honest labels

The lane's results ledger fixes the language: until a complete report exists, the
words "citable", "decided", "validated" and "pure uplift" (and equivalents) are banned
for any result, and predictions are not findings. T4, T5 and T6 canonical claims are labelled **NOT passed**; T7-v3 union claim is
labelled **PASSED narrowly**. The supported statements, each scoped to two loci, one
institution and model judges only, are:

1. The curated pack beats the unaided model (three replications).
2. The curated pack beats a wrong-locus pack of identical format (content
   specificity), and the union form beats the wrong-locus union (T6 U2).
3. The pack does not demonstrably beat equal-length retrieval (T4 C3, T5 C3b, T6
   C3b-r). Union over twice-budget retrieval failed narrowly at T6 (U1) and PASSED
   narrowly at T7-v3 on oracle-answerable tasks (U1 +0.130, p=0.047; U2 +0.228,
   p=0.003); next is untouched-locus replication.

What the lane licenses on this evidence, in its own words: "standalone pack authoring
stops as a product activity; curation continues for retrieval, evidence selection,
routing and adjudication."

## 5. What this evidence is, and is not, for the grid

- **The grid is a model-consensus prior.** A division key exists because several
  frozen models, under one cold prompt, converged on a name that maps to it
  (`limits.md`: "consensus = textual convergence, not economic importance"). No anchor
  in the live run has yet been hand-corroborated (G6), so the grid is a prior in the
  plain sense: a starting map, published so it can be argued with.
- **The lane's results are calibration evidence from a private corpus.** They measure
  how much different reference material helps a model on institution-specific tasks
  inside two division keys. They are evidence about that corpus and that material.
- **They are not validation of the grid.** No run tested whether a division key is
  correctly named, correctly bounded, complete or economically important; the loci
  were assigned to keys by the lane's author, not derived from the grid; and two loci
  at one institution cannot speak for 42 keys. A key being exercised is not a key
  being confirmed.
- **This note is not a coverage claim.** Under SPEC-01 I10 and SPEC-03 I5, coverage
  claims live in separate post-hoc files, one per claimant. No grid cell's
  `corpus_coverage` is filled by this note, and no cell, benchmark or environment is
  asserted to satisfy any control point.
- **Nothing here crosses the profile boundary.** The common semantic profile permits
  no occurrence claims and no institution-specific workflow at the public layer. This
  note carries aggregate statistics only: no corpus text, no task text, no pack text,
  no system, desk, person or client identifiers, and no description of how the
  institution performs any activity.
- **Not citable as a grid result.** Anyone citing the grid should cite the live run's
  PROVISIONAL status and nothing here; anyone citing the lane should cite the lane's
  own reports, which this note only summarises.

## 6. Sources and maintenance

Figures are transcribed from the lane's private documents as they stood on
2026-09-04: its results-status ledger (labels, T4/T5/T6/T7 summaries and the T4
erratum), the T6 report (sections 1, 2, 6 and 7), T7-REPORT.md section 1,
out-t7/report.json, the T7 preregistration v3 (sections 2 to 7, 11 and 12) and a
viability read dated 2026-09-03 (locus descriptions, pack size, budget-doubling and
power estimates). Division-key assignments are from the lane's registry; live-run
support figures are from `live-run-20260826/RUN_SUMMARY.json` and `matrix.csv`.

This note is non-normative and is not listed in the release manifest; it may be
revised without a release. Any figure here that disagrees with a lane report is an
error in this note.
