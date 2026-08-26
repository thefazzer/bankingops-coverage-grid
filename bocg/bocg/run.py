"""§4 RUN PROTOCOL: cold runs, one repair pass, verbatim logging to runs/<prompt_sha8>/<model_id>/<i>.json."""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .prompt import DEFAULT_PARAMS, FrozenPrompt, load_frozen
from .providers import CallParams, FixtureProvider, Provider, make_provider
from .util import BocgError, Workspace, read_json, safe_dirname, sha256_text, utc_now_iso, write_json
from .validate import assess

RUN_RECORD_VERSION = "bocg.run.v1"


@dataclass
class Panel:
    models: list[dict]
    samples: int = 3
    threshold_usd: float = 200000
    currency: str = "USD"
    as_of_year: int = 2025
    temperature: float = 0.2
    top_p: float = 1.0
    max_tokens: int = 16000
    seed_base: int | None = 1000
    timeout_s: float = 600.0
    stream: bool = False

    @classmethod
    def load(cls, path: Path) -> "Panel":
        d = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        p = d.get("params") or {}
        c = d.get("call") or {}
        return cls(models=list(d.get("models") or []), samples=int(d.get("samples", 3)),
                   threshold_usd=float(p.get("threshold_usd", DEFAULT_PARAMS["THRESHOLD_USD"])),
                   currency=str(p.get("currency", DEFAULT_PARAMS["CURRENCY"])),
                   as_of_year=int(p.get("as_of_year", DEFAULT_PARAMS["AS_OF_YEAR"])),
                   temperature=float(c.get("temperature", 0.2)), top_p=float(c.get("top_p", 1.0)),
                   max_tokens=int(c.get("max_tokens", 16000)),
                   seed_base=(None if c.get("seed_base", 1000) is None else int(c.get("seed_base", 1000))),
                   timeout_s=float(c.get("timeout_s", 600.0)), stream=bool(c.get("stream", False)))

    @classmethod
    def default_fixture_panel(cls) -> "Panel":
        return cls(models=[])

    def render_params(self) -> dict:
        return {"THRESHOLD_USD": self.threshold_usd, "CURRENCY": self.currency, "AS_OF_YEAR": self.as_of_year}

    def to_dict(self) -> dict:
        return {"models": self.models, "samples": self.samples,
                "params": {"threshold_usd": self.threshold_usd, "currency": self.currency, "as_of_year": self.as_of_year},
                "call": {"temperature": self.temperature, "top_p": self.top_p, "max_tokens": self.max_tokens,
                         "seed_base": self.seed_base, "timeout_s": self.timeout_s, "stream": self.stream}}


def _call_params(panel: Panel, idx: int) -> CallParams:
    seed = None if panel.seed_base is None else panel.seed_base + idx
    return CallParams(temperature=panel.temperature, top_p=panel.top_p, max_tokens=panel.max_tokens, seed=seed,
                      timeout_s=panel.timeout_s, stream=panel.stream)


def freeze_inputs(ws: Workspace, fp: FrozenPrompt) -> None:
    """Copy the frozen prompt assets into the workspace and publish prompt.sha256 (I1)."""
    ws.root.mkdir(parents=True, exist_ok=True)
    ws.prompt_txt.write_bytes(fp.prompt_text.encode("utf-8"))
    ws.system_txt.write_text(fp.system_text, encoding="utf-8")
    ws.schema_json.write_text(fp.schema_text, encoding="utf-8")
    ws.prompt_sha256.write_text(fp.prompt_sha256 + "  prompt.txt\n", encoding="utf-8")


def _one_call(provider: Provider, system: str, user: str, params: CallParams, idx: int):
    if isinstance(provider, FixtureProvider):
        return provider.complete(system, user, params, sample_idx=idx)
    return provider.complete(system, user, params)


def run_sample(provider: Provider, fp: FrozenPrompt, panel: Panel, idx: int, provider_name: str,
               vendor: str) -> dict:
    """Execute one cold sample with at most one repair pass (re-send same prompt, no hints)."""
    system = fp.system_text
    user = fp.render(panel.threshold_usd, panel.currency, panel.as_of_year)
    params = _call_params(panel, idx)
    record: dict[str, Any] = {
        "schema_version": RUN_RECORD_VERSION,
        "prompt_sha256": fp.prompt_sha256, "prompt_sha8": fp.prompt_sha8,
        "provider": provider_name, "vendor": vendor, "model_requested": provider.model, "model_id": provider.model,
        "sample_idx": idx,
        "request": {"system": system, "user": user, "params": params.to_dict(),
                    "render_params": panel.render_params(),
                    "cold": {"tools": False, "browsing": False, "retrieval": False, "prior_turns": 0,
                             "provider_cold_guarantee": bool(provider.cold_guarantee)}},
        "response_raw": "", "response_sha256": sha256_text(""), "ts_utc": utc_now_iso(), "usage": {},
        "status": "ERROR", "invalid_reasons": [], "repair_pass": None, "error": None, "extra": {},
    }
    try:
        res = _one_call(provider, system, user, params, idx)
    except Exception as e:  # network/HTTP/shape errors are logged, never hidden
        record["error"] = f"{type(e).__name__}: {e}"
        return record
    record.update(response_raw=res.raw_text, response_sha256=sha256_text(res.raw_text), usage=res.usage,
                  model_id=res.model_id, extra=res.extra, ts_utc=utc_now_iso())
    a = assess(res.raw_text, schema=None)
    if a.schema_valid:
        record["status"] = "OK"
        return record
    # RETRY: one repair pass = re-send the same prompt (no hints) once
    first = {"response_raw": res.raw_text, "response_sha256": record["response_sha256"],
             "reasons": a.invalid_reasons()[:2], "ts_utc": record["ts_utc"]}
    try:
        res2 = _one_call(provider, system, user, params, idx)
        record.update(response_raw=res2.raw_text, response_sha256=sha256_text(res2.raw_text), usage=res2.usage,
                      model_id=res2.model_id, extra=res2.extra, ts_utc=utc_now_iso())
        a2 = assess(res2.raw_text, schema=None)
        record["repair_pass"] = {"attempted": True, "first_attempt": first, "second_valid": a2.schema_valid}
        if a2.schema_valid:
            record["status"] = "OK"
        else:
            record["status"] = "INVALID"
            record["invalid_reasons"] = a2.invalid_reasons()
    except Exception as e:
        record["repair_pass"] = {"attempted": True, "first_attempt": first, "error": f"{type(e).__name__}: {e}"}
        record["status"] = "INVALID"
        record["invalid_reasons"] = a.invalid_reasons()
    return record


def build_providers(panel: Panel, fixtures_dir: Path | None) -> list[tuple[Provider, str, str]]:
    """Return [(provider, provider_name, vendor)]."""
    out = []
    if fixtures_dir is not None:
        fixtures_dir = Path(fixtures_dir)
        if not fixtures_dir.is_dir():
            raise BocgError(f"fixtures dir not found: {fixtures_dir}")
        specs = panel.models or [{"provider": "fixture", "model": p.name}
                                 for p in sorted(fixtures_dir.iterdir()) if p.is_dir()]
        for s in specs:
            prov = FixtureProvider(s["model"], fixtures_dir, vendor=s.get("vendor"))
            # vendor: from panel, else from the first fixture file, else provider name
            vendor = s.get("vendor")
            if not vendor:
                idxs = prov.sample_indices()
                vendor = prov.load(idxs[0]).get("vendor", s.get("provider", "fixture")) if idxs else "fixture"
            out.append((prov, "fixture", vendor))
        return out
    if not panel.models:
        raise BocgError("panel.yaml lists no models")
    for s in panel.models:
        prov = make_provider(s)
        out.append((prov, s["provider"], s.get("vendor") or prov.vendor))
    return out


def run_panel(ws: Workspace, panel: Panel, fixtures_dir: Path | None = None, fp: FrozenPrompt | None = None,
              echo=print, concurrency: int = 1) -> dict:
    """Execute the panel. concurrency>1 dispatches independent cold calls in parallel; each call is
    self-contained (fresh context per I3) so parallelism cannot affect any response's content, and the
    spec §4 ORDER rule (all models run before any human inspects a response) is satisfied a fortiori."""
    fp = fp or load_frozen()
    freeze_inputs(ws, fp)
    providers = build_providers(panel, fixtures_dir)
    runs_dir = ws.runs_dir(fp.prompt_sha8)
    jobs = []
    for prov, pname, vendor in providers:
        if isinstance(prov, FixtureProvider):
            indices = prov.sample_indices()
            if not indices:
                raise BocgError(f"fixture model {prov.model} has no samples")
        else:
            indices = list(range(panel.samples))
        for idx in indices:
            jobs.append((prov, pname, vendor, idx, len(indices)))

    def do(job):
        prov, pname, vendor, idx, _k = job
        rec = run_sample(prov, fp, panel, idx, pname, vendor)
        # Persist immediately (I4): a later failure must never lose responses already paid for.
        write_json(runs_dir / safe_dirname(rec["model_id"]) / f"{idx}.json", rec)
        return job, rec

    results: list[tuple[tuple, dict]] = []
    if concurrency > 1 and not fixtures_dir:
        import concurrent.futures as _cf
        with _cf.ThreadPoolExecutor(max_workers=concurrency) as ex:
            for job, rec in ex.map(do, jobs):
                results.append((job, rec))
                echo(f"[run] {rec['model_id']} #{job[3]}: {rec['status']} sha={rec['response_sha256'][:8]}")
    else:
        for job in jobs:
            job, rec = do(job)
            results.append((job, rec))
            echo(f"[run] {rec['model_id']} #{job[3]}: {rec['status']} sha={rec['response_sha256'][:8]}")

    meta_models, seen = [], {}
    for (prov, pname, vendor, idx, k), rec in results:
        model_dir_name = safe_dirname(rec["model_id"])
        key = (pname, prov.model)
        e = seen.setdefault(key, {"provider": pname, "vendor": vendor, "model_requested": prov.model,
                                  "model_dir": model_dir_name, "k": k, "ok": 0})
        e["model_dir"] = model_dir_name
        e["ok"] += rec["status"] == "OK"
    meta_models = list(seen.values())
    meta = {"prompt_sha256": fp.prompt_sha256, "prompt_sha8": fp.prompt_sha8,
            "fixtures_dir": (str(Path(fixtures_dir).resolve()) if fixtures_dir else None),
            "panel": panel.to_dict(), "models": meta_models, "ts_utc": utc_now_iso()}
    write_json(ws.run_meta, meta)
    return meta


def load_runs(ws: Workspace, prompt_sha8: str | None = None) -> list[dict]:
    """Load every run record for the workspace's prompt version, sorted by (model_dir, sample_idx)."""
    sha8 = prompt_sha8 or ws.prompt_sha8_from_meta()
    d = ws.runs_dir(sha8)
    if not d.is_dir():
        raise BocgError(f"no runs under {d}")
    recs = []
    for mdir in sorted(p for p in d.iterdir() if p.is_dir()):
        for f in sorted(mdir.glob("*.json"), key=lambda p: int(p.stem) if p.stem.isdigit() else 10**9):
            rec = read_json(f)
            rec["_path"] = str(f)
            rec["_model_dir"] = mdir.name
            recs.append(rec)
    return recs
