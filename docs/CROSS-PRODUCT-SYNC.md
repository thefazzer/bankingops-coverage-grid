# Cross-product sync status — BOCG / evals / Ficta Meridian

Checked: 2026-09-27T03:24Z (UTC)  
Owner signal: **APPROVED GO** — agent still cannot execute Finexhaust/cleanroom writes.

## Green now

| Surface | Pin | Evidence |
|---|---|---|
| **BOCG** | `v0.6.2` | https://github.com/thefazzer/bankingops-coverage-grid/releases/tag/v0.6.2 — tip `c84bebf`, manifest `67f491ec4068…` |
| **Live Meridian** | BOCG `v0.6.2` | https://fictameridian.com/manifests/latest.json — exact tag + manifest match; `built_at=2026-09-26T09:23:31Z`; Finexhaust `f3a7fab` |
| **cleanroom-eval (code)** | `1.2.0` on `main` | README → BOCG v0.6.2 + bankingenv ledger T4–T8 |

## Hard blocker (why APPROVED GO is not enough yet)

Cursor GitHub App installation for this agent is **`repository_selection=selected`** and currently includes **only** `thefazzer/bankingops-coverage-grid`.

| Target | Result with current token |
|---|---|
| `thefazzer/finexhaust` | **404** (no clone, no Actions, no workflow_dispatch) |
| `thefazzer/cleanroom-eval` write | **403** |
| `thefazzer/fictameridian-site` write | **403** |

Production Meridian is **not** the public `fictameridian-site` stub. Path: private Finexhaust → `ficta-meridian-site/` → workflow **Ficta Meridian daily manifest release** → rsync → Linode `172.237.124.65:/var/www/fictameridian` (Caddy).

Daily workflow has been **failing** (GitHub Actions emails through 2026-09-25). Live v0.6.2 pin was achieved via Finexhaust source `f3a7fab` build on 2026-09-26, not a successful daily CI run visible to this agent.

## Unblock (pick one)

### Option A — expand GitHub App (preferred for agent autonomy)

GitHub → Settings → Applications → **Cursor** → Repository access → add:

1. `thefazzer/finexhaust`
2. `thefazzer/cleanroom-eval`

Then reply **PROCEED** on the cloud agent.

### Option B — owner runs now

```bash
# cleanroom release
cd cleanroom-eval && git checkout main && git pull
git tag -a v1.2.0 -m '1.2.0: FinExhaust sync; BOCG v0.6.2'
git push origin v1.2.0
gh release create v1.2.0 --title 'cleanroom-eval 1.2.0' \
  --notes 'Synced to FinExhaust; BOCG v0.6.2 pointer' \
  RELEASE-MANIFEST.sha256 SECURITY-RELEASE.md

# Meridian redeploy
gh workflow run 'Ficta Meridian daily manifest release' -R thefazzer/finexhaust
# UI: https://github.com/thefazzer/finexhaust/actions/workflows/ficta-meridian-daily.yml

# verify
curl -sS https://fictameridian.com/manifests/latest.json | jq '{built_at, bocg, source}'
```

## Remaining product gaps after unblock

1. Tag/publish **cleanroom-eval v1.2.0** (code already on main; no GitHub Release yet).
2. Successful Finexhaust Meridian rebuild **after** that release (site build 26 Sep predates cleanroom 1.2.0 merge 27 Sep).
3. Optionally refresh public `fictameridian-site` stub so it does not look like the product.