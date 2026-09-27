'use client';

import { PUBLIC_EVAL_OBSERVATORY, CLEANROOM_EVAL_PIN } from '../data/public-eval-observatory';

type LlmajCase = {
  case_id: string;
  inventory_id: string;
  title: string;
  url?: string | null;
  case_verdict: string;
  paint_eligible: boolean;
  disagreement_note?: string | null;
};

/**
 * Lab section: cleanroom harness pin + live LLMAJ public-benchmark outcomes.
 * Empty-intersection cases (Mercor / Rogo / BankerToolBench) stay visible and
 * explicitly non-paint — never promoted to QUALIFIED from this surface.
 */
export default function PublicEvalObservatory() {
  const llmaj = PUBLIC_EVAL_OBSERVATORY.llmaj;
  const cases = (llmaj?.cases ?? []) as ReadonlyArray<LlmajCase>;
  const paint = PUBLIC_EVAL_OBSERVATORY.overlay_paint;
  const cleanroom = CLEANROOM_EVAL_PIN;

  return (
    <section className="section" id="public-eval" aria-labelledby="public-eval-title">
      <p className="kicker">Public-eval surface · SPEC-09 LLMAJ · cleanroom harness pin</p>
      <div className="rule" />
      <div className="why">
        <div>
          <h2 id="public-eval-title">What public benches bind — and what does not paint</h2>
        </div>
        <div>
          <p>
            Live primary+sensitivity LLMAJ under the locked prereg. Only
            intersection-union PASS may QUALIFY a <code>public_benchmark</code> row.
            Empty mapping-key intersection is a recorded outcome, not a void to
            fill with owner PENDING maps.
          </p>
        </div>
      </div>

      <div className="capability-receipt" aria-label="Cleanroom and LLMAJ pins">
        <div>
          <strong>{cleanroom.version}</strong>
          <span>
            cleanroom-eval · {(cleanroom.commit_sha || '').slice(0, 12)} ·{' '}
            {cleanroom.release_status?.replaceAll('_', ' ')}
          </span>
        </div>
        <div>
          <strong>{llmaj?.case_count ?? 0}</strong>
          <span>LLMAJ cases under prereg {(PUBLIC_EVAL_OBSERVATORY.prereg_sha256 || '').slice(0, 12)}</span>
        </div>
        <div>
          <strong>{llmaj?.paint_eligible_count ?? 0}</strong>
          <span>paint-eligible PASS</span>
        </div>
        <div>
          <strong>{paint?.painted_row_count ?? 0}</strong>
          <span>QUALIFIED / RATIFIED overlay rows</span>
        </div>
      </div>

      <p className="section-note">{llmaj?.headline}</p>

      <header className="plate-head">
        <span>Public benchmark LLMAJ</span>
        <span>primary + sensitivity · intersection-union</span>
        <span>{llmaj?.paint_eligible_count ?? 0} eligible</span>
      </header>
      <div className="contract-grid" role="list">
        {cases.map((item) => (
          <article key={item.case_id} role="listitem" data-paint={item.paint_eligible ? 'eligible' : 'none'}>
            <small>{item.paint_eligible ? 'paint-eligible PASS' : `no paint · ${item.case_verdict}`}</small>
            <strong>{item.title}</strong>
            <span>
              {item.inventory_id}
              {item.disagreement_note ? ` · ${item.disagreement_note}` : ''}
            </span>
            {item.url ? (
              <a href={item.url} target="_blank" rel="noreferrer">
                Open public artifact →
              </a>
            ) : null}
          </article>
        ))}
      </div>

      {(paint?.rows?.length ?? 0) > 0 && (
        <>
          <header className="plate-head">
            <span>Painted overlay rows</span>
            <span>QUALIFIED / RATIFIED only</span>
            <span>{paint?.painted_row_count}</span>
          </header>
          <div className="contract-grid" role="list">
            {(paint?.rows ?? []).map((row: { row_id: string; title: string; mapping_status: string; division_key?: string | null; band?: string | null; rationale?: string | null }) => (
              <article key={row.row_id} role="listitem">
                <small>{row.mapping_status.replaceAll('_', ' ')} · {row.band} · {row.division_key}</small>
                <strong>{row.title}</strong>
                <span>{row.rationale}</span>
              </article>
            ))}
          </div>
        </>
      )}

      <p className="section-note">
        Harness:{' '}
        <a href={cleanroom.url || 'https://github.com/thefazzer/cleanroom-eval'}>
          {cleanroom.repository || 'thefazzer/cleanroom-eval'}
        </a>{' '}
        · {cleanroom.version}. Companion BOCG tag {cleanroom.bocg_companion_tag}. Inspect{' '}
        <a href="/manifests/latest.json">latest.json → cleanroom_eval / public_eval</a>.
      </p>
    </section>
  );
}
