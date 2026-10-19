# BOCG regeneration: 19 October 2026

This is a fresh generation using models available from the configured providers on 19 October 2026, Europe/London. It is a **provisional taxonomy with an incomplete independent panel**, not a corroborated finding about banking work or seat economics.

The released matrix has 25 business areas, grouped from 62 admitted labels. Only DeepSeek V4.1 Flash (provider ID `deepseek-flash`) and Qwen 3.8 27B returned three protocol-valid samples. The requirement for at least four independent vendors is **not met**. Kimi K3 supplied two valid samples and MiMo v2.6 Pro one; their other samples put division names before evidence, contrary to I5. Neither family contributes to this release's consensus or seat pools. GLM 5.3 returned transport errors; GPT 6 Astra was unavailable because both configured OpenAI accounts exhausted credit. See [exclusions](exclusions.json), [sample summary](RUN_SUMMARY.json) and [every raw response](runs/efd90b74/).

The [system prompt](system.txt) and [user prompt](prompt.txt) are unchanged. Prompt SHA-256 is recorded in [prompt.sha256](prompt.sha256); rendered year is 2026, seat admission floor USD 200,000. Each model has three planned samples. [Panel parameters](panel.yaml), [provider model listings](provider-models.json), effective request parameters and any provider adaptations are public. Browsing and retrieval are off. No institution holdings were sent to this panel.

The initial panel and MiMo increment completed before response content was inspected or aliases authored. Only interrupted Qwen transport slots were repeated. Successful responses were not rerun to improve agreement. Additional unsuccessful OpenAI attempts, original Qwen errors and exact initial/incremental panels remain in [attempt history](attempt-history/); replacement slots retain the earlier receipt and its hash. [Assembly receipt](generation-receipt.json) records the producer, Prefect run and input hashes.

[Aliases](aliases.yaml) are provisional automated decisions, not human rulings. Composite activity names that cannot be safely narrowed stand alone. The old task-concept ruling is archived under `reference/history/`; new roles and tasks remain AUTO and unreviewed. Old public-eval overlays retain their original catalogue bindings and are historical, not evidence of coverage of this new taxonomy.

The new explicit `eligible-models/v1` policy excludes ineligible models from the consensus denominator and from axis, anchor and seat pools. All attempted model columns remain visible. Historical matrices are unchanged. With two eligible models, Strong means two supporting models and Moderate one. These are agreement labels, not confidence estimates. See [matrix](matrix.csv) and SPEC-01 section 5.

Each area's seat estimate is the median of admitted model claims: annual cost-range midpoint multiplied by the claimed fraction of work with checkable outcomes. The prompt's admission floor biases the pool upwards. It is neither a product price nor measured savings. [All 291 anchor/seat rows](corroboration.csv) remain UNVERIFIED. Citations, compensation amounts and work shares have not been independently checked.

## Reproduce from retained responses

From the repository root, with its Python dependencies installed:

```sh
PYTHONPATH=bocg python -m bocg.cli normalise -w live-run-20261019
PYTHONPATH=bocg python -m bocg.cli matrix -w live-run-20261019
PYTHONPATH=bocg python -m bocg.cli corroborate --ledger live-run-20261019/corroboration.csv -w live-run-20261019
PYTHONPATH=bocg python -m bocg.cli grid -w live-run-20261019
python tools/build_operating_catalogue.py
python tools/build_task_concepts.py
```

`reference/taxonomy-source.json` selects this run. Use Finexhaust's generation, retry and assembly flows to create another run; do not overwrite this one. The generation receipt pins the original generation code separately from later normalisation and catalogue code. The release manifest pins all published evidence.

No test suite or gate suite was run, as requested. Production schema, response-hash, field-order and admission checks were applied while normalising actual responses. G6 and G10 are recorded as failures from the unverified ledger and insufficient eligible vendors; other gate results are NOT_RUN. No earlier gate result is carried forward.
