# Cross-product sync status — BOCG / evals / Ficta Meridian

Checked: 2026-09-27T03:22Z (UTC)

## Green now

| Surface | Pin | Evidence |
|---|---|---|
| **BOCG** | `v0.6.2` | https://github.com/thefazzer/bankingops-coverage-grid/releases/tag/v0.6.2 — tag tip `c84bebf`, manifest `67f491ec4068…` |
| **Live Meridian** | BOCG `v0.6.2` | https://fictameridian.com/manifests/latest.json — `bocg.tag=v0.6.2`, `manifest_sha256` exact match, `built_at=2026-09-26T09:23:31Z`, Finexhaust source `f3a7fab` |
| **cleanroom-eval (code)** | `1.2.0` on `main` | https://github.com/thefazzer/cleanroom-eval — README points at BOCG v0.6.2 + bankingenv ledger T4–T8 |

## Not green / blocked from this agent

| Surface | Gap | Blocker |
|---|---|---|
| **cleanroom-eval GitHub Release** | No `v1.2.0` release asset/tag | This agent has **no write** on `thefazzer/cleanroom-eval` (403) |
| **Public `fictameridian-site` stub** | Still Aug-23 static shell | This agent has **no write** (403). Live site is **not** served from this repo |
| **Finexhaust redeploy** | Daily workflow failing (last CI mail 2026-09-25); cannot `workflow_dispatch` | Private repo `thefazzer/finexhaust` returns **404** to this token — no clone, no Actions access |
| **Meridian ↔ cleanroom 1.2.0** | Site build (26 Sep) predates cleanroom 1.2.0 merge (27 Sep ~00:53Z) | Needs Finexhaust `ficta-meridian-daily` success after 1.2.0 |

## Operator actions to finish sync (run as Finexhaust owner)

```bash
# 1) Tag + release cleanroom-eval 1.2.0
cd cleanroom-eval && git checkout main && git pull
git tag -a v1.2.0 -m '1.2.0: FinExhaust sync; BOCG v0.6.2'
git push origin v1.2.0
gh release create v1.2.0 --title 'cleanroom-eval 1.2.0' \
  --notes 'Synced to FinExhaust; BOCG v0.6.2 pointer; ledger T4–T8' \
  RELEASE-MANIFEST.sha256 SECURITY-RELEASE.md

# 2) Redeploy Meridian from Finexhaust (picks latest public BOCG + eval pointers)
gh workflow run 'Ficta Meridian daily manifest release' -R thefazzer/finexhaust
# or: Actions → ficta-meridian-daily.yml → Run workflow

# 3) Verify
curl -sS https://fictameridian.com/manifests/latest.json | jq '{built_at, bocg, source}'
```

## Architecture reminder

- Live product path: `finexhaust/ficta-meridian-site` → `refresh-public-data.sh` → static export → SSH to Linode `172.237.124.65:/var/www/fictameridian`
- Public `thefazzer/fictameridian-site` is a placeholder; CNAME points at production host but GitHub Pages content is stale