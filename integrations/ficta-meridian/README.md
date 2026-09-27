# Finexhaust → Ficta Meridian apply pack

Closes the Meridian functional gaps that BOCG alone cannot publish:

1. Pin **cleanroom-eval 1.2.0** in `manifests/latest.json` (`cleanroom_eval`) and the Lab footer.
2. Surface live LLMAJ empty-intersection outcomes for **Mercor / Rogo / BankerToolBench** (`public_eval`).

BOCG ships the source of truth in this repository:

- `reference/cleanroom-eval-companion.v1.json`
- `reference/public-eval-observatory.v1.json`
- `tools/public_eval_observatory.py` (S9-G6)

## Apply (owner / Finexhaust write access)

```bash
# from Finexhaust repo root
cp /path/to/bankingops-coverage-grid/integrations/ficta-meridian/scripts/gen-release-observatory.py \
  ficta-meridian-site/scripts/gen-release-observatory.py

cp /path/to/bankingops-coverage-grid/integrations/ficta-meridian/app/components/PublicEvalObservatory.tsx \
  ficta-meridian-site/app/components/PublicEvalObservatory.tsx

cp /path/to/bankingops-coverage-grid/integrations/ficta-meridian/app/data/public-eval-observatory.ts \
  ficta-meridian-site/app/data/public-eval-observatory.ts
```

### `app/page.tsx` (Lab)

1. Import:

```tsx
import PublicEvalObservatory from './components/PublicEvalObservatory';
import { CLEANROOM_EVAL_PIN } from './data/public-eval-observatory';
```

2. After `<ReferenceExplorer />` (or before `#capability-map`):

```tsx
<PublicEvalObservatory />
```

3. Replace the Lab footer harness clause:

```tsx
{/* was: harness: thefazzer/cleanroom-eval · 2026-09 */}
<footer>
  Ficta Meridian · coverage grid: thefazzer/bankingops-coverage-grid ({RELEASE_OBSERVATORY.bocg.tag})
  · harness: thefazzer/cleanroom-eval · {CLEANROOM_EVAL_PIN.version}
  · {RELEASE_OBSERVATORY.built_at.slice(0, 7)}
</footer>
```

4. Optional: add an inspection-route link to `#public-eval` in the Lab entry nav.

### Release fold

`RELEASE_OBSERVATORY.cleanroom_eval` and `RELEASE_OBSERVATORY.public_eval` are
present after `refresh-public-data.sh`. The release-fold strip can show:

```tsx
<div>
  <small>Cleanroom harness</small>
  <strong>{RELEASE_OBSERVATORY.cleanroom_eval.version}</strong>
  <span>{RELEASE_OBSERVATORY.cleanroom_eval.release_status.replaceAll('_', ' ')}</span>
</div>
```

## Rebuild + deploy

Requires Cursor GitHub App access to `thefazzer/finexhaust` (and ideally
`thefazzer/cleanroom-eval` for cutting the GitHub Release):

```bash
# 1) Prefer a BOCG tag that includes public-eval-observatory.v1.json (this PR / next remint).
#    Until then the patched generator rebuilds public_eval from the v0.6.2 ledger.

# 2) Cut cleanroom GitHub Release if still missing:
cd cleanroom-eval && git checkout main && git pull
git tag -a v1.2.0 -m '1.2.0: FinExhaust sync; BOCG v0.6.2'
git push origin v1.2.0
gh release create v1.2.0 --title 'cleanroom-eval 1.2.0' \
  --notes 'Synced to FinExhaust; BOCG v0.6.2 pointer' \
  RELEASE-MANIFEST.sha256 SECURITY-RELEASE.md

# 3) Redeploy Meridian
gh workflow run 'Ficta Meridian daily manifest release' -R thefazzer/finexhaust

# 4) Verify
curl -sS https://fictameridian.com/manifests/latest.json \
  | jq '{built_at, bocg_tag:.bocg.tag, cleanroom:.cleanroom_eval, llmaj:(.public_eval.llmaj|{case_count,paint_eligible_count,headline})}'
```

## Why this pack lives in BOCG

Finexhaust is private and currently outside the Cursor App selected-repo set.
Shipping the patched generator + UI here lets the owner apply a single drop
without rediscovering the gap list, and keeps Meridian’s eval versioning bound
to the same SPEC-09 artifacts the Lab already verifies.
