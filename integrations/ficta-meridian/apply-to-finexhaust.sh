#!/usr/bin/env bash
# Apply BOCG Meridian eval-observatory pack into a Finexhaust checkout.
# Usage (from Finexhaust repo root):
#   BOCG_ROOT=/path/to/bankingops-coverage-grid bash path/to/apply-to-finexhaust.sh
# Or with Finexhaust and bankingops-coverage-grid as siblings:
#   bash ../bankingops-coverage-grid/integrations/ficta-meridian/apply-to-finexhaust.sh
set -euo pipefail

FINE_ROOT=$(pwd)
if [[ ! -d ficta-meridian-site ]]; then
  echo "Run from Finexhaust repo root (expected ./ficta-meridian-site)" >&2
  exit 2
fi

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
BOCG_ROOT=${BOCG_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}
PACK="$BOCG_ROOT/integrations/ficta-meridian"
if [[ ! -f "$PACK/scripts/gen-release-observatory.py" ]]; then
  echo "BOCG pack not found at $PACK (set BOCG_ROOT)" >&2
  exit 2
fi

install -m 0644 "$PACK/scripts/gen-release-observatory.py" \
  ficta-meridian-site/scripts/gen-release-observatory.py
install -m 0644 "$PACK/app/components/PublicEvalObservatory.tsx" \
  ficta-meridian-site/app/components/PublicEvalObservatory.tsx
install -m 0644 "$PACK/app/data/public-eval-observatory.ts" \
  ficta-meridian-site/app/data/public-eval-observatory.ts

PAGE=ficta-meridian-site/app/page.tsx
if ! grep -q "PublicEvalObservatory" "$PAGE"; then
  python3 - "$PAGE" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
needle = "import ReferenceExplorer from './components/ReferenceExplorer';\n"
insert = needle + (
    "import PublicEvalObservatory from './components/PublicEvalObservatory';\n"
    "import { CLEANROOM_EVAL_PIN } from './data/public-eval-observatory';\n"
)
if needle not in text:
    raise SystemExit("import anchor not found in page.tsx")
if "PublicEvalObservatory" not in text:
    text = text.replace(needle, insert, 1)
anchor = "      <ReferenceExplorer />\n"
if anchor in text and "<PublicEvalObservatory />" not in text:
    text = text.replace(anchor, anchor + "\n      <PublicEvalObservatory />\n", 1)
old = "harness: thefazzer/cleanroom-eval · 2026-09"
new = "harness: thefazzer/cleanroom-eval · {CLEANROOM_EVAL_PIN.version} · {RELEASE_OBSERVATORY.built_at.slice(0, 7)}"
# footer is JSX text — replace month-only clause when present
if "CLEANROOM_EVAL_PIN.version" not in text:
    text = text.replace(
        "· harness: thefazzer/cleanroom-eval · 2026-09</footer>",
        "· harness: thefazzer/cleanroom-eval · {CLEANROOM_EVAL_PIN.version} · {RELEASE_OBSERVATORY.built_at.slice(0, 7)}</footer>",
        1,
    )
path.write_text(text, encoding="utf-8")
print(f"patched {path}")
PY
else
  echo "page.tsx already references PublicEvalObservatory — left as-is"
fi

echo "Applied Meridian observatory pack from $PACK"
echo "Next: commit, then: gh workflow run 'Ficta Meridian daily manifest release'"
