# Finexhaust → Ficta Meridian apply pack

Closes the Meridian functional gaps that BOCG alone cannot publish:

1. Pin **cleanroom-eval 1.2.0** in `manifests/latest.json` (`cleanroom_eval`) and the Lab footer.
2. Surface live LLMAJ empty-intersection outcomes for **Mercor / Rogo / BankerToolBench** (`public_eval`).

BOCG source of truth (on `main`):

- `reference/cleanroom-eval-companion.v1.json` (`release_status: github_release_published`)
- `reference/public-eval-observatory.v1.json`
- `tools/public_eval_observatory.py` (S9-G6)

cleanroom-eval **v1.2.0** is already released:
https://github.com/thefazzer/cleanroom-eval/releases/tag/v1.2.0

## One-shot apply (from Finexhaust repo root)

```bash
# Finexhaust and bankingops-coverage-grid as siblings:
bash ../bankingops-coverage-grid/integrations/ficta-meridian/apply-to-finexhaust.sh

# Or:
BOCG_ROOT=/path/to/bankingops-coverage-grid \
  bash /path/to/bankingops-coverage-grid/integrations/ficta-meridian/apply-to-finexhaust.sh

git add ficta-meridian-site
git commit -m "Meridian: pin cleanroom 1.2.0 + surface LLMAJ empty-intersection"
git push

gh workflow run "Ficta Meridian daily manifest release"
```

## Manual copy (same effect)

```bash
cp "$BOCG_ROOT/integrations/ficta-meridian/scripts/gen-release-observatory.py" \
  ficta-meridian-site/scripts/gen-release-observatory.py
cp "$BOCG_ROOT/integrations/ficta-meridian/app/components/PublicEvalObservatory.tsx" \
  ficta-meridian-site/app/components/PublicEvalObservatory.tsx
cp "$BOCG_ROOT/integrations/ficta-meridian/app/data/public-eval-observatory.ts" \
  ficta-meridian-site/app/data/public-eval-observatory.ts
# then patch app/page.tsx per patches/page.tsx.footer-and-section.diff
```

## Verify

```bash
curl -sS https://fictameridian.com/manifests/latest.json \
  | jq "{built_at, bocg:.bocg.tag, cleanroom:.cleanroom_eval.version, llmaj:.public_eval.llmaj.paint_eligible_count}"
```

Acceptance: `cleanroom == "1.2.0"`, `llmaj == 0`, four non-paint cases in `public_eval.llmaj.cases`.
