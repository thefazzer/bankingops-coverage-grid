# Mercor APEX-Agents recheck — 4 October 2026

## Citation-ready finding

Mercor reports Gemini 4 Argon at 82.2% Pass@1 overall and 80.9% for investment banking on its current APEX-Agents leaderboard [1]. Those are performance measurements on the benchmark's selected tasks, not measurements of coverage of BOCG's admitted operational divisions. No post-25 September expansion of the task/rubric surface was established by this recheck. This is **not** a verified byte-identical surface: BOCG's September inventory did not pin Mercor task/rubric revisions, the task files are access-gated, and the public runner changed on 30 September [4–8]. The defensible conclusion is that the new score alone supplies no basis for collapsing BOCG's public-eval voids.

BOCG's existing APEX-Agents LLMAJ outcome is UNCERTAIN/non-paint, with an empty primary/sensitivity mapping-key intersection [9]. Its judges explicitly found insufficient division/task detail in the six-field inventory card. This establishes no admitted mapping under that frozen procedure; it does **not** establish that Mercor has no relevant operational tasks, that frontier models cannot perform those tasks, that BOCG is exhaustive, or that its voids establish unmet demand or commercial value.

## Artifact comparison

Baseline: BOCG main commit `5996b01`; inventory 1.3.0, checked 2026-09-25; prereg `dfcc901848f814fc078891590ecce94e288bd39e968baa42968df280a9ef9441`.

| Evidence | Observed surface / change | Interpretation |
|---|---|---|
| September BOCG card [10] | Generic investment-banking analyst job-family title and mutable leaderboard URL; no Mercor release, task/rubric hash or content snapshot | Cannot reconstruct a task-by-task September baseline from this card |
| Mercor 8 September release [2] | APEX-Agents 1.1 selected/refined 80 tasks per domain; clarified world files; added scattergunning-aware judging and explicit system instructions; tooling reliability changes | Real task/environment/grading change, **before** the inventory date; the card does not establish which version was inspected |
| Current v1.1 dataset card [3] | 240 tasks, 31 worlds, 955 binary criteria; banking: 80 tasks across 8 worlds; 100 turns and 10,800-second agent timeout | Matches current leaderboard's 240-task/31-world description; describes project-based professional work, not blanket banking-operations coverage |
| Older dataset card [11] | 480 tasks across 33 worlds, banking 160 tasks across 10 worlds | Different release, not evidence of a newly doubled October surface |
| Current leaderboard [1] | Argon 82.2% overall; 80.9% banking; banking described as modeling, valuation, research, transaction support and pitch preparation | A score on this job-family sample cannot identify which BOCG operational units are assessed |
| Five public runner commits after 25 September [4–8] | 30 September: LiteLLM/Responses bridge and reasoning-effort fixes, error/retry handling, image limits, system-prompt digest correction and version bump | Execution/reproduction changes; inspected patches do not contain a task-bank or rubric expansion. Runner-repository history cannot certify dataset history |

Access/verification limits: public dataset cards were readable, but both datasets require login/acceptance for underlying files; original dataset history returned HTTP 401. No gated task/rubric corpus was downloaded. The leaderboard also says both that the entire dataset is open-source and that only an open subset is reproducible while the full task set is private. Those statements do not establish an immutable public task snapshot. The claimed **3 October publication date** was supplied in the request; the accessible leaderboard confirms the figures but does not independently timestamp their addition. No numerical uplift versus September is inferred without a pinned prior score and comparable settings.

## SPEC-09 disposition

No new coverage paint, owner-authored candidate, mapping promotion, or modified judge sheet is warranted by a model-score update. Preserve the frozen inventory, prereg, ledger, surface map and observatory. Changing even `checked_at` in the locked inventory changes its digest and requires a new prereg under SPEC-09; this dated evidence note records the recheck separately.

If an identified task/rubric revision establishes a surface change, capture immutable old/new task IDs, prompts, rubrics, world overlays and grader/runtime revisions; update the inventory under a new front-loaded prereg; render the same frozen card procedure for both required judges; preserve both sheets and require their intersection-union PASS before promotion. A runner version label alone is insufficient evidence of a new operational unit of work. A richer task-evidence mapping would also require an explicitly revised, prospectively frozen protocol rather than treating the September coarse-card rejection as an exhaustive artifact audit.

Existing check results: LLMAJ check (fixture 2, ledger 4), prereg-check, promote-gate, overlay check and observatory check passed their available structural checks. Overlay remains 1 painted division and 41 void divisions; all four benchmark cases remain non-paint. These counts describe this inventory and admission method, not the universe of public or private evaluations.

## Sources

Accessed 4 October 2026. Mutable pages are observation-date citations, not archival task hashes.

1. [Mercor APEX-Agents leaderboard](https://www.mercor.com/apex/apex-agents-leaderboard/).
2. [Introducing APEX-Agents 1.1, 8 September 2026](https://www.mercor.com/blog/introducing-apex-agents-1-1/).
3. [Mercor APEX-Agents v1.1 dataset card](https://huggingface.co/datasets/mercor/apex-agents-v1.1).
4. [Runner release / bridge / effort changes, 6a3bd8c](https://github.com/Mercor-Intelligence/apex_loop_truncated_tools_agent/commit/6a3bd8c7d813249bc16813e58de8cf4a4cf52547).
5. [Image limit change, 51a78a4](https://github.com/Mercor-Intelligence/apex_loop_truncated_tools_agent/commit/51a78a44658d9111f484740f5736ffdfa6b89f85).
6. [Error handling and model settings, 213d584](https://github.com/Mercor-Intelligence/apex_loop_truncated_tools_agent/commit/213d58461f2bc85eb121b1e9a340c1963acd5add).
7. [System-prompt digest correction, 01a2586](https://github.com/Mercor-Intelligence/apex_loop_truncated_tools_agent/commit/01a2586db733d1fc538242c1649c3218a15c71fc).
8. [Vendored runner version bump, 44ded89](https://github.com/Mercor-Intelligence/apex_loop_truncated_tools_agent/commit/44ded89d896b6369f517ae91400378cd3cf6eaad).
9. [Pinned BOCG LLMAJ ledger](https://github.com/thefazzer/bankingops-coverage-grid/blob/5996b01/reference/public-eval-llmaj-ledger.v1.json) and [SPEC-09](https://github.com/thefazzer/bankingops-coverage-grid/blob/5996b01/specs/SPEC-09-public-eval-surface-overlay.md).
10. [Pinned September inventory](https://github.com/thefazzer/bankingops-coverage-grid/blob/5996b01/reference/public-eval-inventory.v1.yaml).
11. [Original APEX-Agents dataset card](https://huggingface.co/datasets/mercor/apex-agents).
