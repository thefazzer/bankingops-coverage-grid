# Cross-product sync status — BOCG / evals / Ficta Meridian

Checked: 2026-09-27T03:45Z (UTC)  
Owner signal: **APPROVED GO** — Finexhaust / cleanroom GitHub writes still blocked for this agent.

## Green now (BOCG-side gaps closed in this branch)

| Surface | Pin | Evidence |
|---|---|---|
| **BOCG observatory** | `reference/public-eval-observatory.v1.json` | S9-G6; Mercor / Rogo / BankerToolBench live LLMAJ cases, `paint_eligible: 0` |
| **cleanroom companion pin** | `1.2.0` / `d01e56e35dd1…` | `reference/cleanroom-eval-companion.v1.json` |
| **Finexhaust apply pack** | `integrations/ficta-meridian/` | Patched `gen-release-observatory.py`, Lab `PublicEvalObservatory` UI, footer version pin |
| **BOCG** | `v0.6.2` live; observatory on this branch for next remint | https://github.com/thefazzer/bankingops-coverage-grid/releases/tag/v0.6.2 |
| **Live Meridian (today)** | BOCG `v0.6.2` only | https://fictameridian.com/manifests/latest.json — **no** `cleanroom_eval` / `public_eval` keys yet; footer still `cleanroom-eval · 2026-09` |
| **cleanroom-eval** | `v1.2.0` released 2026-09-27 (tag on `d01e56e35dd1…`) | https://github.com/thefazzer/cleanroom-eval/releases/tag/v1.2.0 |

## Hard blocker (production publish)

Cursor GitHub App installation for this agent is **`repository_selection=selected`** and currently includes **only** `thefazzer/bankingops-coverage-grid`.

| Target | Result with current token |
|---|---|
| `thefazzer/finexhaust` | **404** (no clone, no Actions, no workflow_dispatch) |
| `thefazzer/cleanroom-eval` write / tag / release | **403** (moot: owner cut `v1.2.0` 2026-09-27) |
| `thefazzer/fictameridian-site` write | **403** |
| SSH deploy to `172.237.124.65` | **denied** |

Production Meridian path: private Finexhaust → `ficta-meridian-site/` → workflow **Ficta Meridian daily manifest release** → rsync → Linode `172.237.124.65:/var/www/fictameridian` (Caddy).

## Unblock + finish (owner)

### Option A — expand GitHub App (preferred)

GitHub → Settings → Applications → **Cursor** → Repository access → add:

1. `thefazzer/finexhaust`
2. `thefazzer/cleanroom-eval`

Then reply **PROCEED** on the cloud agent (it will apply `integrations/ficta-meridian/`, remint/redeploy; cleanroom `v1.2.0` is already released).

### Option B — owner runs now

```bash
# 1) Apply Meridian pack into Finexhaust (see integrations/ficta-meridian/README.md)
# 2) cleanroom release — DONE 2026-09-27 (https://github.com/thefazzer/cleanroom-eval/releases/tag/v1.2.0)
cd cleanroom-eval && git checkout main && git pull
git tag -a v1.2.0 -m '1.2.0: FinExhaust sync; BOCG v0.6.2'
git push origin v1.2.0
gh release create v1.2.0 --title 'cleanroom-eval 1.2.0' \
  --notes 'Synced to FinExhaust; BOCG v0.6.2 pointer' \
  RELEASE-MANIFEST.sha256 SECURITY-RELEASE.md

# 3) Meridian redeploy
gh workflow run 'Ficta Meridian daily manifest release' -R thefazzer/finexhaust

# 4) verify
curl -sS https://fictameridian.com/manifests/latest.json \
  | jq '{built_at, bocg:.bocg.tag, cleanroom:.cleanroom_eval.version, llmaj:.public_eval.llmaj.paint_eligible_count}'
```

## Acceptance once live

1. `latest.json` has `cleanroom_eval.version == "1.2.0"`.
2. `latest.json` has `public_eval.llmaj.cases` length 4 with all `paint_eligible: false`.
3. Lab footer shows `cleanroom-eval · 1.2.0`.
4. Lab `#public-eval` names Mercor, Rogo, BankerToolBench as recorded non-paint.
