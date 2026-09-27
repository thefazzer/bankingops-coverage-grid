// GENERATED example — Finexhaust gen-release-observatory.py overwrites this at build.
// Seed content mirrors BOCG reference/public-eval-observatory.v1.json so the Lab
// can typecheck before the first refresh against a BOCG tag that ships the artifact.

export const PUBLIC_EVAL_OBSERVATORY = {
  "prereg_sha256": "dfcc901848f814fc078891590ecce94e288bd39e968baa42968df280a9ef9441",
  "headline": "Live primary+sensitivity LLMAJ under the locked prereg produced 0 paint-eligible PASS case(s) across 4 public_benchmark card(s). Empty mapping-key intersection on Mercor / Rogo / BankerToolBench → no public_benchmark QUALIFIED paint.",
  "llmaj": {
    "case_count": 4,
    "paint_eligible_count": 0,
    "headline": "Live primary+sensitivity LLMAJ under the locked prereg produced 0 paint-eligible PASS case(s) across 4 public_benchmark card(s). Empty mapping-key intersection on Mercor / Rogo / BankerToolBench → no public_benchmark QUALIFIED paint.",
    "cases": [
      {
        "case_id": "llmaj_public_handshake_bankertoolbench_no_intersection",
        "inventory_id": "public.handshake_bankertoolbench",
        "title": "Handshake BankerToolBench",
        "url": "https://github.com/Handshake-AI-Research/bankertoolbench",
        "case_verdict": "UNCERTAIN",
        "paint_eligible": false,
        "disagreement_note": "No exact (division_key, depth, band, rule_id) intersection between primary mappings=[] and sensitivity mappings=[]"
      },
      {
        "case_id": "llmaj_public_mercor_apex1_ib_no_intersection",
        "inventory_id": "public.mercor_apex1_ib",
        "title": "Mercor APEX-1 Investment Banking Analyst",
        "url": "https://www.mercor.com/resources/apex/best-ai-model-for-investment-banking-analyst-tasks/",
        "case_verdict": "UNCERTAIN",
        "paint_eligible": false,
        "disagreement_note": "No exact (division_key, depth, band, rule_id) intersection between primary mappings=[] and sensitivity mappings=[]"
      },
      {
        "case_id": "llmaj_public_mercor_apex_agents_no_intersection",
        "inventory_id": "public.mercor_apex_agents",
        "title": "Mercor APEX-Agents",
        "url": "https://www.mercor.com/apex/apex-agents-leaderboard/",
        "case_verdict": "UNCERTAIN",
        "paint_eligible": false,
        "disagreement_note": "No exact (division_key, depth, band, rule_id) intersection between primary mappings=[] and sensitivity mappings=[]"
      },
      {
        "case_id": "llmaj_public_rogo_big_finance_bench_no_intersection",
        "inventory_id": "public.rogo_big_finance_bench",
        "title": "Rogo Big Finance Bench / BigFinanceBench",
        "url": "https://github.com/Rogo-Technologies/big-finance-benchmark",
        "case_verdict": "UNCERTAIN",
        "paint_eligible": false,
        "disagreement_note": "No exact (division_key, depth, band, rule_id) intersection between primary mappings=[] and sensitivity mappings=[]"
      }
    ]
  },
  "overlay_paint": {
    "painted_row_count": 1,
    "rows": [
      {
        "row_id": "ovr_harvey_lab_trade_lifecycle",
        "inventory_id": "peer.harvey_lab",
        "title": "Harvey LAB task format",
        "mapping_status": "QUALIFIED_MAPPING",
        "division_key": "trade_lifecycle_operations",
        "band": "L1",
        "llmaj_pass_ref": null,
        "rationale": "CONFORMANCE.md records two banking tasks accepted in the Harvey LAB schema. Public peer task-shape only."
      }
    ]
  },
  "source": "seed_from_bocg_observatory"
} as const;

export const CLEANROOM_EVAL_PIN = {
  "repository": "thefazzer/cleanroom-eval",
  "version": "1.2.0",
  "commit_sha": "d01e56e35dd13143a7d3af364b43d59f286a3c50",
  "release_tag": "v1.2.0",
  "release_status": "code_on_main_github_release_pending",
  "bocg_companion_tag": "v0.6.2",
  "url": "https://github.com/thefazzer/cleanroom-eval",
  "notes": "cleanroom-eval 1.2.0 is on main; Meridian must show this version even if the GitHub Release is still pending."
} as const;
