# SPEC-02 — Lineage Attestation: span commitments, per-atom lineage, examiner verification

```
ARTIFACT  : Lineage Attestation Toolkit (LAT)
PROJECT   : FinExhaust / BankingEnv
STATUS    : v0.1 goal spec for implementing agent
TAGS      : FinExhaust, BankingEnv, lineage attestation, span commitment, salted canary, sealed holdout,
            pseudonymisation, clean room, buyer-counsel attestation, runnable gates, provenance manifest
```

## 0. GOAL

Make the following claims machine-verifiable by a party who never sees source material:

```
C1 INTEGRITY   : source documents are exactly those committed in an anchored manifest (no post-hoc substitution).
C2 DELTA_ONLY  : a redacted document differs from its source ONLY at committed positions, each tagged with a
                 redaction class ∈ CLASS; all other bytes are identical to source.
C3 LINEAGE     : every atom in every shipped episode carries a lineage class {SPAN_VERIFIED, PSEUDONYMISED_TRACEABLE,
                 SYNTHETIC_UNPROVABLE} and, for the first two, resolvable references to committed source segments.
C4 RATIOS      : corpus-level and per-episode lineage ratios (by atom count and bytes) are recomputable by the buyer.
C5 EXAMINER    : a buyer-side examiner holding the nonce vault can open every commitment and confirm each redacted
                 original belongs to its declared class, pseudonyms are consistent, and no residual identifiers survive
                 in kept text — producing a narrowly scoped, signed, dated finding for counsel.
C6 CANARY      : every outbound package is uniquely salted per recipient and registered; unsalted packages cannot be built.
C7 HOLDOUT     : the sealed holdout's items+answer key are committed (hash) before any external review; never shipped.
```
Explicit NON-claims: LAT does not prove semantic safety of kept text, correctness of doctrine, or absence of
re-identification via operational detail. Those are flagged heuristically (§7 RESIDUAL_SCAN), not proven.

## 1. HARD BOUNDARY (design decision)

```
PIPELINE_MODE = PSEUDONYMISE (verifiable)  |  SYNTHESISE (unprovable)
A document is processed in exactly one mode. SYNTHESISE output atoms are class SYNTHETIC_UNPROVABLE, always.
No mixed-mode atoms. Mode recorded per atom (derivation_op).
```

## 2. OBJECTS

```
SourceDoc      { doc_id (=sha256 of bytes), bytes, origin{institution_code, period_start, period_end, channel} }
Manifest       { version, created_utc, docs:[doc_id...] sorted, merkle_root, anchor:{chain, txid, block, ts} | null }
                 Existing BTC-anchored hash set of the source corpus (~15k hashes) is imported as manifest v0; new manifests
                 must be supersets or explicit subsets with diff log.
Segment        { doc_id, idx, start, end, kind ∈ {KEEP, REDACT} }        ; segments partition [0,len) in order, no gaps.
Commitment     { doc_id, idx, class ∈ CLASS, commit = H(DS_COMMIT || doc_id || idx || start || end || class || original_bytes || nonce) }
                 H = SHA-256; nonce = 32 random bytes (CSPRNG); DS_* = domain separation tags (§3.1).
KeepLeaf       { doc_id, idx, leaf = H(DS_KEEP || doc_id || idx || start || end || bytes) }
DocRoot        root = Merkle(ordered leaves: KEEP→KeepLeaf.leaf, REDACT→Commitment.commit) with DS_NODE; duplicate-last for odd.
                 INVARIANT: DocRoot MUST equal a deterministic function of doc bytes+segmentation; manifest binds doc_id, and
                 `segmentation.json` (start/end/kind/class per segment, no originals) binds the partition.
                 PROOF OF C2: verifier recomputes KeepLeaves from redacted doc text (kept spans are byte-identical, positions from
                 segmentation.json), takes commitments as given, recomputes root, checks root ∈ roots.json signed by seller
                 AND that H(original doc) == doc_id is attested by examiner (buyer cannot; examiner can — §6).
RedactedDoc    { doc_id, text: concat over segments of (KEEP→original bytes | REDACT→replacement_token) , roots_ref }
Replacement    token format: ⟦CLASS:pseudonym_id⟧  ; pseudonym_id = base32(HMAC(K_pseud, class || canonical(original)))[:10]
                 => same entity → same token corpus-wide (consistency), K_pseud lives in NonceVault, never shipped.
NonceVault     { doc_id → [{idx, nonce, original_bytes, class}], K_pseud }  ; encrypted at rest (age/AES-GCM); examiner-only.
Atom           { atom_id, episode_id, content, derivation_op ∈ {QUOTE, PSEUDONYMISE, PARAPHRASE, SYNTHESISE},
                 lineage_class, span_refs:[{doc_id, idx, leaf_or_commit}], generator_version, content_sha256 }
                 lineage_class := QUOTE→SPAN_VERIFIED ; PSEUDONYMISE→PSEUDONYMISED_TRACEABLE ; PARAPHRASE|SYNTHESISE→SYNTHETIC_UNPROVABLE
                 SPAN_VERIFIED requires: content is exact substring of concat(KEEP segments referenced) (bytes-equal after NFC).
                 PSEUDONYMISED_TRACEABLE requires: content equals substring of RedactedDoc over referenced segments (may include ⟦⟧ tokens).
Episode        { episode_id, task_id, atoms:[atom_id...], trace_ref, verifier_ref, lineage_summary }
Canary         { package_id, recipient_id, salt (16B), positions:[(atom_id, method)], registry_sig }
                 methods: zero-width char sequence, invisible pseudonym-suffix variant, ordering permutation of non-semantic fields.
                 Detection: `lat canary detect <file>` recovers recipient_id from any ≥3 surviving carriers.
Holdout        { holdout_id, items_commit = H(DS_HOLD || canonical_json(items+answers) || nonce_h), created_utc, anchor|null }
                 items never leave seller. Reveal = publish items+answers+nonce_h; verifier recomputes commit.
```

## 3. CRYPTO PARAMETERS

```
3.1 DS_COMMIT="LAT/commit/v1", DS_KEEP="LAT/keep/v1", DS_NODE="LAT/node/v1", DS_HOLD="LAT/holdout/v1", DS_MAN="LAT/manifest/v1"
3.2 Encoding: length-prefixed fields (u32 BE len || bytes) for every || above. Integers as u64 BE. Strings UTF-8 NFC.
3.3 Hiding: 256-bit nonce ⇒ commitment reveals nothing about original (buyer cannot brute-force names/dates).
3.4 Binding: SHA-256 collision resistance ⇒ seller cannot open a commitment to a different original.
3.5 Signing: seller signs roots.json, lineage.jsonl, ratios.json, canary registry with Ed25519 (pubkey published).
             Examiner signs report.json with own key. Signatures detached, `*.sig`, base64.
3.6 Manifest merkle root optionally anchored (OpenTimestamps or raw OP_RETURN); anchor proof stored, verified by `lat anchor verify`.
```

## 4. CLASS (redaction classes) + classifier obligations

```
CLASS = { PERSON, COUNTERPARTY, CLIENT, LEGAL_ENTITY, INTERNAL_SYSTEM, ACCOUNT_ID, TRADE_ID, EMAIL, PHONE, DATE,
          AMOUNT_EXACT, LOCATION, FREE_TEXT_QUOTE }
Detection: rule/NER pipeline (regex for ids/emails/phones/dates; NER for PERSON/ORG; seller-supplied gazetteer for
COUNTERPARTY/CLIENT/INTERNAL_SYSTEM). Every REDACT segment must have exactly one class.
DATE policy: shift-by-constant-per-doc (consistent intervals) OR bucket-to-month; policy id recorded; token ⟦DATE:…⟧.
AMOUNT_EXACT policy: keep unless flagged re-identifying by RESIDUAL_SCAN; if redacted, replace by banded ⟦AMOUNT:band⟧.
Examiner class check (§6): opened original must satisfy class predicate (regex/NER/gazetteer) — mismatch => CLASS_VIOLATION.
```

## 5. RATIOS (recomputable by buyer from lineage.jsonl alone)

```
ratios.json = {
  by_atoms:  {SPAN_VERIFIED: n, PSEUDONYMISED_TRACEABLE: n, SYNTHETIC_UNPROVABLE: n, total: n, pct: {...}},
  by_bytes:  {...same...},
  per_episode: [{episode_id, pct_span_verified, pct_pseud, pct_synth, n_atoms}],
  tier: "VERIFIED" if pct(SPAN_VERIFIED+PSEUDONYMISED_TRACEABLE by bytes) >= TIER_FLOOR else "MIXED"   (TIER_FLOOR default 0.80)
}
```

## 6. VERIFIER — two modes, one CLI

```
lat verify --mode buyer    --package PKG                       (no vault)
   V1 manifest: recompute H(MANIFEST canonical) == manifest.sha; anchor proof valid if present.
   V2 roots:    for each RedactedDoc: rebuild leaves from redacted text + segmentation.json + commitments; root == roots.json[doc_id]; sig ok.
   V3 lineage:  every atom: class consistent with derivation_op; SPAN_VERIFIED/PSEUD substring checks pass against RedactedDoc;
                span_refs resolve to leaves/commits present in roots data; content_sha256 matches.
   V4 ratios:   recompute ratios.json == shipped (byte-identical canonical JSON).
   V5 canary:   package carries a registered canary for stated recipient (registry sig ok); recovery succeeds on the package itself.
   V6 holdout:  holdout commitment present, dated, (anchored); no holdout item ids appear in package (id-level + near-dup on task text).
   V7 vault_absent: package contains no nonces / K_pseud / originals (entropy + filename + magic scans).
   OUT: verify_buyer.json {checks:[{id,status,evidence}], overall}

lat verify --mode examiner --package PKG --vault VAULT [--sample N --seed S]
   E1 = V1..V7
   E2 open:     for each commitment (all, or seeded sample N): H(...original||nonce) == commit  → OPEN_OK/OPEN_FAIL
   E3 class:    opened original satisfies class predicate → CLASS_OK/CLASS_VIOLATION
   E4 pseud:    for every original value, token == HMAC-derived token; same original never maps to two tokens, two originals
                never map to one token → PSEUD_OK/PSEUD_COLLISION/PSEUD_INCONSISTENT
   E5 doc_id:   H(reconstructed original from vault + kept text) == doc_id ∈ manifest → DOC_OK   (this is what binds C1 for buyer)
   E6 residual: RESIDUAL_SCAN (§7) over kept text → counts by severity; CRITICAL>0 fails.
   E7 origin:   doc.origin ∈ declared institution/period set (attest scope statement).
   OUT: report.json (signed) + report.md, statements scoped as:
        "On <date>, over sample S of N commitments (seed s) in package <id>: E2 x/x OPEN_OK; E3 ...; ratios (recomputed): ...;
         residual scan: ...; origin: all sampled docs within <institutions>/<period>."   No general blessing language.
```

## 7. RESIDUAL_SCAN (heuristic; never claimed as proof)

```
R1 NER re-run over kept text → any PERSON/ORG not in allowlist(generic terms) => HIGH
R2 regex ids/emails/phones/IBAN/LEI/ISIN-with-name-context => CRITICAL
R3 quasi-identifier k-check: tuples (product, size_band, date_bucket, venue) with corpus frequency k<K_MIN (default 5) => MEDIUM
R4 pseudonym-context leak: ⟦COUNTERPARTY:x⟧ within 40 chars of a surviving proper noun => MEDIUM
R5 near-dup vs holdout (MinHash/Jaccard>=0.8 on task text) => CRITICAL
Severity gates: CRITICAL=0 required; HIGH<=0.1% of kept segments; MEDIUM reported.
```

## 8. RUNNABLE GATES (`lat gate all` pre-package; exit non-zero on failure)

```
G1 LEAKAGE_GATE     : no doc_id, entity token, or near-dup shared between shipped package and sealed holdout.
G2 CANARY_GATE      : refuse to build package without registered per-recipient salt; registry append-only, signed.
G3 MANIFEST_GATE    : all doc_ids in package ∈ manifest; roots recompute; sigs valid.
G4 CLASS_FLOOR_GATE : ratios.tier == "VERIFIED" for packages marketed as verified; else label MIXED in package metadata.
G5 RESIDUAL_GATE    : §7 severity thresholds.
G6 VAULT_GATE       : V7.
G7 MODE_GATE        : no atom with derivation_op ∈ {PARAPHRASE,SYNTHESISE} carries class ≠ SYNTHETIC_UNPROVABLE; no mixed-mode docs.
G8 DETERMINISM_GATE : re-running redaction with same vault reproduces identical RedactedDoc + roots.
G9 HOLDOUT_GATE     : holdout commit created_utc < earliest external_review_ts in audit log.
```

## 9. PACKAGE LAYOUT

```
pkg-<package_id>/
  manifest.json  manifest.sha  anchor_proof.ots|null
  roots.json  roots.json.sig
  segmentation/<doc_id>.json          (start,end,kind,class per segment; NO originals, NO nonces)
  redacted/<doc_id>.txt
  lineage.jsonl  lineage.jsonl.sig     (atoms)
  episodes.jsonl
  ratios.json  ratios.json.sig
  canary/registry_entry.json  registry_entry.sig
  holdout/commit.json
  pubkeys/seller.pub
  gates_report.json
  README-VERIFY.md                     (exact commands for buyer + examiner)
VAULT (never in package): vault/<doc_id>.json (nonces, originals, classes) + K_pseud + seller signing key — encrypted.
```

## 10. THREAT MODEL (assert in tests)

```
T1 buyer recovers identifiers from commitments/tokens      → infeasible (256-bit nonce; HMAC key secret).
T2 seller swaps original after anchoring                    → detected: doc_id ∉ manifest / root mismatch (E5, V2).
T3 seller mislabels class (e.g. hides substantive text as DATE) → examiner E3 CLASS_VIOLATION.
T4 seller inflates SPAN_VERIFIED ratio                      → V3 substring checks fail; V4 recompute mismatch.
T5 leaked package traced                                     → canary detect recovers recipient (≥3 carriers survive edits).
T6 holdout swapped after scores seen                          → commit mismatch on reveal.
T7 residual re-identification via operational detail          → NOT prevented; R3 flags; documented in limits.
```

## 11. IMPLEMENTATION TARGET

```
package  : lat/ (python>=3.11; deps: cryptography|pynacl (Ed25519, AES-GCM), click, regex, datasketch (MinHash), optional spaCy)
cli      : lat manifest build|verify|anchor ; lat redact --mode pseudonymise|synthesise --vault V ;
           lat lineage build ; lat ratios ; lat canary register|apply|detect ; lat holdout commit|reveal|verify ;
           lat verify --mode buyer|examiner ; lat gate all ; lat package build ; lat report
tests    : each claim C1–C7 has positive test + tamper test (T1–T6); determinism test; substring/lineage class tests;
           merkle vectors; canary survives paraphrase-lite edits; vault-absence scanner.
fixtures : synthetic docs (NO real data) with fake names/counterparties/dates/ids generated by faker-like code.
out-of-scope: NER model quality, legal opinion text, blockchain broadcast (interface only; OpenTimestamps stub).
```
