# bocg — BankingOps Coverage Grid

Implementation of **SPEC-01 — model-consensus taxonomy elicitation** (`specs/SPEC-01-coverage-grid-elicitation.md`).
Python ≥ 3.11; deps: `jsonschema`, `pyyaml`, `click`, `httpx`.

```bash
cd bocg
pip install --break-system-packages -e .        # installs the `bocg` CLI
pip install --break-system-packages pytest && pytest -q
```

## Layout

```
bocg/
  pyproject.toml  README.md
  bocg/                      package (flat layout)
    assets/                  FROZEN inputs shipped with the package
      system.txt             §2.1 system prompt (verbatim)
      prompt.txt             §2.2 user prompt (verbatim; §3 schema embedded at <SCHEMA>; {THRESHOLD_USD},{CURRENCY},{AS_OF_YEAR} kept)
      schema.json            §3 response schema (draft 2020-12)
      forbidden_tokens.txt   §2.3 FORBIDDEN_TOKENS incl. ~50 bank names and ~40 product names
      negative_instruction_allowlist.txt   see "Spec conflict" below
      self_assess_patterns.txt             G8 regex list
      methodology.md  limits.md            copied into every bundle (§9)
    *.py                     modules (table below)
  examples/panel.yaml        live panel example
  tests/                     pytest suite + fixtures (4 synthetic vendors x 3 samples + 1 INVALID + 1 self-assessment)
```

## Spec section → module

| Spec | Module / file |
|---|---|
| §1 invariants I1–I10 | enforced across modules; each gate in `bocg/gates.py` cites the invariant it checks |
| §2.1 / §2.2 prompt, §2.3 forbidden tokens | `bocg/assets/*.txt`, `bocg/prompt.py` (load, render, sha256, token/regex scans) |
| §3 schema + post-validation (order check, seat-cost recompute, server-side admission) | `bocg/assets/schema.json`, `bocg/validate.py` |
| §4 run protocol (cold calls, one repair pass, verbatim logging, `--fixtures`) | `bocg/run.py`, `bocg/providers.py` |
| §5.1 canon name | `bocg/canon.py` |
| §5.2 alias table | `bocg/aliases.py` |
| §5.3–5.7 matrix, tiers, axis vote, anchor pool, seat pool | `bocg/matrix.py` (consumes `bocg/normalise.py` output) |
| §6 corroboration ledger | `bocg/corroborate.py` |
| §7 grid.json | `bocg/grid.py` |
| §7 own_cell.json → coverage_statement.md, divergence_report.md | `bocg/coverage.py` |
| §8 gates G1–G10 | `bocg/gates.py` (`g1_contamination` … `g10_panel`, each returns `{id, status, evidence}`) |
| §9 bundle + MANIFEST.sha256 | `bocg/bundle.py` |
| §10 CLI | `bocg/cli.py` |

## Working directory

Every command takes `-w/--workdir` (default `./bocg_work`). Layout produced:

```
<workdir>/
  prompt.txt system.txt schema.json prompt.sha256      frozen copies written by `bocg run` (I1)
  run_meta.json                                        panel, prompt hash, fixtures dir, per-model k
  runs/<prompt_sha8>/<model_id>/<i>.json               {request, response_raw, response_sha256, ts_utc, params, usage, status, repair_pass} (I4)
  normalised.json canon_names.json                     validation, server-side admission, canon names, alias keys
  aliases.yaml aliases.sha256                          §5.2
  matrix.csv matrix.json                               §5.3–5.7
  corroboration.csv corroboration_summary.json         §6
  grid.json                                            §7
  own_cell.json coverage_statement.md divergence_report.md
  gates_report.json                                    §8
  bundle/bocg-bundle-<prompt_sha8>-<date>/             §9
```

## Fixture mode (no network; what the tests run)

```bash
F=tests/fixtures
bocg run         --fixtures $F --panel $F/panel-fixtures.yaml            -w work   # --panel optional: models are discovered from $F
bocg normalise   --aliases $F/aliases.yaml                                -w work   # omit --aliases => identity AUTO-DRAFT aliases.yaml
bocg matrix                                                               -w work
bocg corroborate --ledger $F/corroboration_all_verified.csv               -w work   # a missing ledger is initialised with UNVERIFIED rows
bocg grid                                                                 -w work
bocg coverage    --own-cell $F/own_cell.json                              -w work
bocg gate all                                                             -w work   # exit 1 on any FAIL; writes gates_report.json
bocg bundle                                                               -w work   # refuses unless gates_report.all_pass (--no-require-gates for drafts)
```

`bocg gate G1 G6` runs a subset (no report written). `tests/fixtures/corroboration_one_unverified.csv` makes G6
fail; `corroboration_refuted.csv` moves `commodities_trading` to `REJECTED_POST_CORROBORATION`.

Fixture file format is the run-record format (`{model_id, vendor, response_raw, usage, params}`), so a live
`runs/<prompt_sha8>/` directory is itself a valid `--fixtures` source — G9 replays from it in live mode.

## Live mode

```bash
export OPENAI_API_KEY=... ANTHROPIC_API_KEY=... GOOGLE_API_KEY=... DEEPSEEK_API_KEY=... XAI_API_KEY=...
bocg run --panel examples/panel.yaml -w live                 # all models, k samples each, cold; nobody inspects yet (§4 ORDER)
bocg normalise -w live                                       # writes canon_names.json + AUTO-DRAFT aliases.yaml
#   -> author live/aliases.yaml AFTER the runs (canon -> division_key, rationale per entry), then:
bocg normalise --aliases live/aliases.yaml -w live
bocg matrix -w live
bocg corroborate --ledger live/corroboration.csv -w live     # first call initialises UNVERIFIED rows
#   -> human/agent verifies every row (status, source_url_or_doc, checked_by, checked_ts, verified_value), then:
bocg corroborate --ledger live/corroboration.csv -w live
bocg grid -w live
bocg coverage --own-cell path/to/own_cell.json -w live       # post hoc, separate file (I10)
bocg gate all -w live && bocg bundle -w live
```

Providers: `openai`, `anthropic`, `google`, `deepseek`, `xai`, `generic_openai_compatible` (set `base_url`,
`api_key_env`, `vendor`). All use REST via `httpx`; no tools/browsing/retrieval fields are ever sent. Responses are
stored as raw text with sha256; invalid JSON/schema triggers exactly one repair pass (same prompt, no hints), then
`status: INVALID`.

## Gates (G1–G10)

| Gate | Check |
|---|---|
| G1 CONTAMINATION | no FORBIDDEN_TOKENS in prompt.txt/system.txt; prompt sha256 == prompt.sha256; every run used that hash |
| G2 SCHEMA | every stored response is schema-valid or marked INVALID; stored sha256 == recomputed |
| G3 ORDER | raw-text offset `"a1_regulatory"` < `"name"` in every division of every valid response |
| G4 REJECTION | every valid response has `rejected.length >= 1` |
| G5 ADMISSION | admission recomputed from raw; normalised.json must agree; overrides + ARITH_MISMATCH logged in evidence |
| G6 CORROBORATION | ledger valid; every admitted division: ≥2 of A1–A3 VERIFIED, A4 VERIFIED, 0 UNVERIFIED/missing rows |
| G7 ALIAS | aliases.yaml sha == aliases.sha256 == matrix.json; every matrix key has an alias; no alias → 2 keys |
| G8 SELF_ASSESS | regex list finds no capability/gap language in prompt; violating responses are marked INVALID |
| G9 REPRO | replay (`--fixtures` dir or `runs/<sha8>/`) regenerates matrix.csv byte-identical |
| G10 PANEL | ≥4 vendors, ≥3 samples each, params logged, cold flags set |

## Spec conflict (documented resolution)

SPEC-01 §2.2 freezes a prompt that contains the phrase *"Do not speculate about which divisions are under-served by
tooling or data"* while §2.3 forbids the token `under-served` and I7/G8 forbid gap language. Editing the prompt is
not allowed (I1), so `assets/negative_instruction_allowlist.txt` lists the exact negative-instruction sentences that
are struck from the prompt text **before** the G1 and G8 scans. The allowlist is shipped with the package and is
part of the published methodology; any change to it is a methodology change.

## Notes / choices

- `k` in the matrix is the number of samples *run* per model (INVALID samples count in the denominator).
- Admitted divisions = server-side admission (I9). WEAK-tier divisions are still admitted and therefore must be fully
  corroborated for G6; consensus tier and admission are orthogonal.
- Axis vote: strict majority per field over supporting samples; ties → `multi` / `both` / `GLOBAL`.
- Anchor dedupe key: A1 `canon(citation)`, A2 `canon(bank filing fiscal_year line_item)`, A3 `canon(publisher series as_of)`.
- `PARTIAL` ledger status does not count as VERIFIED and does not count as UNVERIFIED for the publication gate.
