# LAT — Lineage Attestation Toolkit (SPEC-02, v0.1)

Makes the SPEC-02 claims C1–C7 machine-verifiable by a party who never sees source material:
span commitments over redacted banking-operations documents, per-atom lineage classes, recomputable
ratios, per-recipient salted canaries, a sealed holdout commitment, and a two-mode verifier
(buyer without the vault, examiner with the nonce vault) that produces a narrowly scoped, signed finding.

Python ≥ 3.11. Dependencies: `cryptography` (Ed25519, AES-GCM), `click`, `regex`, `datasketch` (MinHash).
No spaCy and no network: NER is a pluggable interface with a rule/gazetteer default detector.

```bash
pip install --break-system-packages -e .      # installs the `lat` CLI
pytest -q                                      # network-free test suite
```

## Quick start (seller → buyer → examiner)

```bash
export LAT_VAULT_KEY_FILE=$PWD/vault.key     # or LAT_VAULT_KEY=<64 hex>; created on `lat vault init`
lat fixtures generate -w . --n-docs 12 --seed 1      # synthetic docs/gazetteers/episodes/holdout/audit log (NO real data)
lat vault init -w .                                   # K_pseud + seller Ed25519 key, AES-GCM encrypted at rest
lat manifest build -w .                               # manifest.json + manifest.sha + anchor_proof.ots (OpenTimestamps STUB)
lat redact -w . --mode pseudonymise                   # segmentation/, redacted/, roots.json(.sig), vault/<doc_id>.json.enc
lat lineage build -w .                                # lineage.jsonl(.sig) + episodes.jsonl from source/episodes_spec.json
lat ratios -w .                                       # ratios.json (canonical JSON) + .sig
lat canary register -w . --package-id P001 --recipient buyer-acme    # append-only signed registry
lat holdout commit -w .                               # holdout/commit.json (public); items+nonce_h sealed in the vault
lat package build -w . --package-id P001 --recipient buyer-acme      # pkg-P001/ (§9 layout) + gates_report.json; exit 1 on FAIL

lat verify --mode buyer --package pkg-P001            # V1..V7 -> pkg-P001/verify_buyer.json
lat keygen --out examiner.key
lat verify --mode examiner --package pkg-P001 --vault vault --sample 50 --seed 7 \
    --examiner-key examiner.key --gazetteers gazetteers                # E1..E7 -> report.json(.sig) + report.md
lat gate all -w . --package pkg-P001                  # G1..G9 -> gates_report.json; exit 1 on FAIL
lat canary detect pkg-P001/lineage.jsonl --registry canary/registry.jsonl    # recovers recipient from >=3 carriers
lat holdout reveal -w . --holdout-id HOLD-2024Q3 --out reveal.json && lat holdout verify --commit pkg-P001/holdout/commit.json --reveal reveal.json
```

Other commands: `lat manifest verify|anchor`, `lat anchor verify`, `lat redact --mode synthesise --docs <file>`,
`lat canary apply`, `lat residual scan`, `lat report`. Every command has `--help`.

## Workspace / package layout

```
<ws>/source/docs/*.txt, origins.json, episodes_spec.json, holdout_items.json, audit_log.json
<ws>/gazetteers/{counterparties,clients,internal_systems,locations,persons,allowlist,products,venues}.txt
<ws>/manifest.json manifest.sha anchor_proof.ots     <ws>/vault/ (encrypted)   <ws>/vault.key (never shipped)
<ws>/work/ (roots.json, segmentation/, redacted/, lineage.jsonl, episodes.jsonl, ratios.json, pubkeys/)
<ws>/canary/registry.jsonl   <ws>/holdout/commit.json
<ws>/pkg-<id>/  = §9: manifest.json manifest.sha anchor_proof.ots roots.json(.sig) segmentation/<doc_id>.json
                 redacted/<doc_id>.txt lineage.jsonl(.sig) episodes.jsonl ratios.json(.sig)
                 canary/registry_entry.json(.sig) holdout/commit.json pubkeys/seller.pub gates_report.json
                 README-VERIFY.md package.json (+ verify_buyer.json / report.json(.sig) / report.md written by verifiers)
```

## Spec section → module

| Spec | Module(s) | Notes |
|---|---|---|
| §2 objects | `models.py` | SourceDoc (doc_id = sha256 of NFC UTF-8 bytes), Segment (byte offsets), Segmentation, Atom, Episode, VaultEntry |
| §2 Manifest, §3.6 anchor | `manifest.py` | build/verify, v0 import, superset/subset with `diff_log`, `OpenTimestampsStub` (interface only) |
| §2 Commitment/KeepLeaf/DocRoot, §3.1–3.4 | `encoding.py`, `crypto.py` | `lp()` = u32-BE length prefix; ints u64-BE; DS tags; Merkle with DS_NODE + duplicate-last |
| §2 RedactedDoc/Replacement/NonceVault, §4 policies | `redact.py`, `classes.py`, `vault.py` | ⟦CLASS:pseudonym_id⟧ (base32 HMAC[:10]); DATE `shift_per_doc_v1` / `bucket_month_v1`; ⟦AMOUNT:band⟧; AES-GCM vault; nonce reuse for G8 |
| §4 detection | `ner.py` | `Detector` protocol; `RuleDetector` (regex + gazetteer + capitalised heuristics); `CompositeDetector`, `StaticDetector` |
| §4 examiner class predicate | `classes.py::class_predicate` | E3 |
| §2 Atom/Episode, C3 | `lineage.py` | op→class mapping, substring checks (after `strip_carriers` + NFC), `check_modes` (G7) |
| §5 ratios | `ratios.py` | canonical JSON bytes, `tier` with TIER_FLOOR 0.80 |
| §2 Canary, C6, T5 | `canary.py` | ZW_SEQ + PSEUD_SUFFIX carriers (invisible code points), 32-bit tag, ≥3 carriers, hash-chained signed registry |
| §2 Holdout, C7, T6 | `holdout.py` | commit/reveal/verify, MinHash sketches for near-dup |
| §6 verifier | `verify.py`, `pkgio.py` | buyer V1–V7 → `verify_buyer.json`; examiner E1–E7 → signed `report.json` + `report.md` |
| §7 residual scan | `residual.py` | R1–R5, severity gate |
| §8 gates | `gates.py` | G1–G9, `gates_report.json`, non-zero exit |
| §9 package | `package.py`, `workspace.py` | layout, canary applied + re-signed lineage, `README-VERIFY.md`, `package.json` metadata |
| §11 fixtures | `fixtures.py` | synthetic corpora (fake names / counterparties / ids / dates / amounts) |
| §11 CLI | `cli.py` | all commands above |

### Encoding details worth knowing (for independent re-implementation)

* `commit = SHA256(lp(DS_COMMIT) ‖ lp(doc_id_hex_utf8) ‖ lp(u64 idx) ‖ lp(u64 start) ‖ lp(u64 end) ‖ lp(class) ‖ lp(original_bytes) ‖ lp(nonce32))`
* `leaf = SHA256(lp(DS_KEEP) ‖ lp(doc_id) ‖ lp(u64 idx) ‖ lp(u64 start) ‖ lp(u64 end) ‖ lp(bytes))`; `node = SHA256(lp(DS_NODE) ‖ lp(L) ‖ lp(R))`; single leaf = root; empty doc = node("", "").
* Manifest merkle leaves are `SHA256(lp(DS_MAN) ‖ lp(doc_id))` over sorted doc_ids; `manifest.sha = SHA256(canonical_json(manifest))`.
* `segmentation/<doc_id>.json` carries `start,end,kind,class,token,commit` per segment (no originals, no nonces). The buyer rebuilds keep leaves by walking the redacted bytes with the segmentation.
* Atom `content_sha256 = SHA256(NFC(strip_carriers(content)))`; canary code points (U+200B/C/D, U+2060–2064, U+FEFF) are stripped before every substring/hash check, so canaries never break lineage.
* Signatures are detached base64 Ed25519 over the exact file bytes (`*.sig`); public keys are base64 raw 32 bytes.
* Determinism (G8): a re-run with the same vault reuses stored nonces for identical `(idx,start,end,class,original)` and derives DATE shifts and pseudonyms from `K_pseud`, so RedactedDoc and roots reproduce byte-for-byte.

## What this proves / does not prove

**Proves (machine-checkable, given the crypto assumptions in §3):**

* C1 INTEGRITY — the examiner (not the buyer) reconstructs each source doc from kept bytes + vault originals and checks `sha256 == doc_id ∈ manifest` (E5); the buyer checks the manifest hash/merkle root and that every shipped doc is listed (V1).
* C2 DELTA_ONLY — every redacted doc's root recomputes from the redacted bytes + segmentation + commitments and matches the signed `roots.json` (V2): bytes outside committed positions are identical to source, each REDACT segment has exactly one class.
* C3 LINEAGE — every atom carries a lineage class consistent with its derivation op; SPAN_VERIFIED / PSEUDONYMISED_TRACEABLE content is a substring of the referenced committed segments and refs resolve to leaves/commits in the root data (V3).
* C4 RATIOS — `ratios.json` is byte-identical to a recomputation from `lineage.jsonl` (V4).
* C5 EXAMINER — commitments open (E2), opened originals satisfy their class predicate (E3), pseudonyms are consistent and collision-free (E4), doc ids bind (E5), origin is within the declared scope (E7); the finding is dated, scoped to the sample and signed.
* C6 CANARY — a package cannot be built without a registered per-recipient salt (G2); the canary is recoverable from the package itself (V5) and from leaked, lightly edited copies (T5 test) as long as ≥3 carriers survive.
* C7 HOLDOUT — holdout items + answers are committed before external review (G9) and never shipped; swapping them after the fact fails `holdout verify` (T6).

**Does not prove (SPEC-02 §0 non-claims and T7):**

* Semantic safety of kept text, correctness of any doctrine or content, or absence of re-identification via operational detail (product, size, dates, venue combinations). The residual scan (R1–R5) is heuristic: it *flags*, it never certifies. R3 k-anonymity checks are approximate and gazetteer-dependent.
* Quality of the default detector. `RuleDetector` is a regex/gazetteer/heuristic baseline; anything it misses is committed as KEEP and only caught (maybe) by the residual scan. Plug in a stronger `Detector` for production.
* That a canary survives a determined adversary: anyone who strips all invisible code points removes the carriers (V5 then fails on the stripped package, but a leaked stripped copy is untraceable).
* Blockchain anchoring. `anchor_proof.ots` is produced by an **OpenTimestamps stub** (interface only, no network); `lat anchor verify` reports `STUB` explicitly. Real anchoring requires a provider implementation.
* Confidentiality beyond the crypto assumptions: commitments hide originals only because of the 256-bit CSPRNG nonce and `K_pseud` secrecy (T1 tests); the vault and key files must stay with the seller/examiner.

## Threat-model coverage in `tests/`

| Threat | Test |
|---|---|
| T1 recover identifiers from commitments/tokens | `test_crypto_vectors.py::test_t1_*` |
| T2 swap original after anchoring | `test_verify_buyer.py::test_t2_*`, `test_verify_examiner.py::test_e5_*` |
| T3 class mislabel | `test_verify_examiner.py::test_t3_class_mislabel_detected_by_examiner` |
| T4 inflate SPAN_VERIFIED | `test_verify_buyer.py::test_t4_*`, `test_lineage_ratios.py::test_check_atom_detects_inflation` |
| T5 leaked package traced / canary stripped | `test_canary.py`, `test_verify_buyer.py::test_t5_*` |
| T6 holdout swapped | `test_holdout.py`, `test_cli_e2e.py::test_cli_holdout_reveal_verify` |
| T7 residual re-identification | not prevented; `test_gates_residual.py` shows R1–R5 flagging only |
| G8 determinism | `test_redact.py::test_determinism_same_vault_same_output`, `test_gates_residual.py::test_g8_*` |
| Vault absence (V7/G6) | `test_verify_buyer.py::test_v7_vault_material_in_package` |
| Merkle / encoding vectors | `test_crypto_vectors.py` |
