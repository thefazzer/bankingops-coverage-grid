"""Provider adapters (§10): openai, anthropic, google, deepseek, xai, generic_openai_compatible, fixture replay.

Each adapter exposes `complete(system, user, params) -> ProviderResult(raw_text, usage, model_id, extra)`.
All live adapters talk to REST endpoints via httpx directly (no vendor SDKs). API keys are read from env.
Tools / browsing / retrieval are never requested (I3). The fixture adapter needs no network (DRY_RUN).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from .util import BocgError, read_json, safe_dirname


@dataclass
class ProviderResult:
    raw_text: str
    usage: dict
    model_id: str                       # exact model id string returned by the API (or requested if absent)
    extra: dict = field(default_factory=dict)


@dataclass
class CallParams:
    temperature: float = 0.2
    top_p: float = 1.0
    max_tokens: int = 16000
    seed: int | None = None
    timeout_s: float = 600.0
    stream: bool = False                # transport only: SSE keeps proxies from timing out on long generations
                                        # (some gateways return Cloudflare 524 on multi-minute non-streamed calls).
                                        # Sampling is unaffected; the reassembled text is logged verbatim.

    def to_dict(self) -> dict:
        return {"temperature": self.temperature, "top_p": self.top_p, "max_tokens": self.max_tokens,
                "seed": self.seed, "stream": self.stream}


class Provider:
    name = "base"
    vendor = "base"
    cold_guarantee = True   # provider can guarantee no tools/browsing/retrieval in this request shape

    def __init__(self, model: str, base_url: str | None = None, api_key_env: str | None = None,
                 client: httpx.Client | None = None):
        self.model = model
        self.base_url = base_url or self.default_base_url()
        self.api_key_env = api_key_env or self.default_key_env()
        self._client = client

    def default_base_url(self) -> str:
        raise NotImplementedError

    def default_key_env(self) -> str:
        raise NotImplementedError

    def api_key(self) -> str:
        key = os.environ.get(self.api_key_env or "")
        if not key:
            raise BocgError(f"missing API key: set env {self.api_key_env} for provider {self.name}")
        return key

    def client(self, timeout: float) -> httpx.Client:
        return self._client or httpx.Client(timeout=timeout)

    def complete(self, system: str, user: str, params: CallParams) -> ProviderResult:
        raise NotImplementedError

    def _post(self, url: str, headers: dict, body: dict, timeout: float) -> dict:
        c = self.client(timeout)
        r = c.post(url, headers=headers, json=body)
        if r.status_code >= 400:
            raise BocgError(f"{self.name} HTTP {r.status_code}: {r.text[:500]}")
        return r.json()

    def _post_sse(self, url: str, headers: dict, body: dict, timeout: float) -> dict:
        """POST with stream=true and reassemble the SSE deltas into a Chat Completions-shaped dict.
        Transport-level only: content is byte-identical to what a non-streamed call would return."""
        c = self.client(timeout)
        parts: list[str] = []
        usage: dict = {}
        model_id = None
        finish = None
        with c.stream("POST", url, headers=headers, json={**body, "stream": True,
                                                          "stream_options": {"include_usage": True}}) as r:
            if r.status_code >= 400:
                r.read()
                raise BocgError(f"{self.name} HTTP {r.status_code}: {r.text[:500]}")
            for line in r.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    ev = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                model_id = ev.get("model") or model_id
                if ev.get("usage"):
                    usage = ev["usage"]
                for ch in ev.get("choices") or []:
                    delta = (ch.get("delta") or {}).get("content")
                    if delta:
                        parts.append(delta)
                    if ch.get("finish_reason"):
                        finish = ch["finish_reason"]
        if not parts:
            raise BocgError(f"{self.name}: stream produced no content deltas")
        return {"choices": [{"message": {"content": "".join(parts)}, "finish_reason": finish}],
                "usage": usage, "model": model_id}


class OpenAICompatible(Provider):
    """Chat Completions shape; used by openai, deepseek, xai and generic endpoints."""
    name = "generic_openai_compatible"
    vendor = "generic"

    def default_base_url(self) -> str:
        return os.environ.get("BOCG_OPENAI_COMPAT_BASE_URL", "https://api.openai.com/v1")

    def default_key_env(self) -> str:
        return "BOCG_OPENAI_COMPAT_API_KEY"

    def complete(self, system: str, user: str, params: CallParams) -> ProviderResult:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": params.temperature,
            "top_p": params.top_p,
            "max_tokens": params.max_tokens,
        }
        if params.seed is not None:
            body["seed"] = params.seed
        # no `tools`, no `tool_choice`, no web search options => cold (I3)
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key()}", "Content-Type": "application/json"}
        dropped: list[str] = []
        # Reasoning-model compatibility: newer OpenAI models reject `max_tokens` (want `max_completion_tokens`)
        # and reject non-default temperature/top_p. Retry by adapting ONLY the rejected parameter, and record
        # every adaptation in `extra.param_adaptations` so the logged params reflect what was actually sent (I3/I4).
        send = self._post_sse if params.stream else self._post
        for _ in range(4):
            try:
                data = send(url, headers, body, params.timeout_s)
                break
            except BocgError as e:
                msg = str(e)
                if "HTTP 400" not in msg or "nsupported" not in msg:
                    raise
                if "'max_tokens'" in msg and "max_tokens" in body:
                    body["max_completion_tokens"] = body.pop("max_tokens"); dropped.append("max_tokens->max_completion_tokens")
                elif "'temperature'" in msg and "temperature" in body:
                    body.pop("temperature"); dropped.append("temperature->default")
                elif "'top_p'" in msg and "top_p" in body:
                    body.pop("top_p"); dropped.append("top_p->default")
                elif "'seed'" in msg and "seed" in body:
                    body.pop("seed"); dropped.append("seed->none")
                else:
                    raise
        else:
            raise BocgError(f"{self.name}: could not adapt request parameters for model {self.model}: {dropped}")
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as e:
            raise BocgError(f"{self.name}: unexpected response shape: {e}: {json.dumps(data)[:300]}")
        return ProviderResult(raw_text=text, usage=data.get("usage") or {}, model_id=data.get("model") or self.model,
                              extra={"system_fingerprint": data.get("system_fingerprint"),
                                     "finish_reason": data["choices"][0].get("finish_reason"),
                                     "param_adaptations": dropped,
                                     "effective_body_params": {k: v for k, v in body.items() if k != "messages"}})


class OpenAI(OpenAICompatible):
    name = "openai"
    vendor = "openai"

    def default_base_url(self) -> str:
        return "https://api.openai.com/v1"

    def default_key_env(self) -> str:
        return "OPENAI_API_KEY"


class DeepSeek(OpenAICompatible):
    name = "deepseek"
    vendor = "deepseek"

    def default_base_url(self) -> str:
        return "https://api.deepseek.com/v1"

    def default_key_env(self) -> str:
        return "DEEPSEEK_API_KEY"


class XAI(OpenAICompatible):
    name = "xai"
    vendor = "xai"

    def default_base_url(self) -> str:
        return "https://api.x.ai/v1"

    def default_key_env(self) -> str:
        return "XAI_API_KEY"


class Anthropic(Provider):
    name = "anthropic"
    vendor = "anthropic"

    def default_base_url(self) -> str:
        return "https://api.anthropic.com/v1"

    def default_key_env(self) -> str:
        return "ANTHROPIC_API_KEY"

    def complete(self, system: str, user: str, params: CallParams) -> ProviderResult:
        body: dict[str, Any] = {
            "model": self.model,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "max_tokens": params.max_tokens,
            "temperature": params.temperature,
        }
        if params.top_p is not None and params.top_p < 1.0:
            body["top_p"] = params.top_p    # API rejects temperature+top_p on some models; only send when != 1
        # seed unsupported by this API: logged as null
        url = f"{self.base_url.rstrip('/')}/messages"
        headers = {"x-api-key": self.api_key(), "anthropic-version": "2023-06-01",
                   "Content-Type": "application/json"}
        # Newer models deprecate `temperature`; drop only the rejected parameter and record the adaptation.
        adaptations: list[str] = []
        for _ in range(3):
            try:
                if params.stream:
                    res = self._messages_sse(url, headers, body, params.timeout_s)
                    res.extra["param_adaptations"] = adaptations
                    res.extra["effective_body_params"] = {k: v for k, v in body.items()
                                                          if k not in ("messages", "system")}
                    return res
                break
            except BocgError as e:
                msg = str(e)
                if "HTTP 400" not in msg or "deprecated" not in msg and "unsupported" not in msg.lower():
                    raise
                if "`temperature`" in msg and "temperature" in body:
                    body.pop("temperature"); adaptations.append("temperature->default")
                elif "`top_p`" in msg and "top_p" in body:
                    body.pop("top_p"); adaptations.append("top_p->default")
                else:
                    raise
        data = self._post(url, headers, body, params.timeout_s)
        try:
            text = "".join(p.get("text", "") for p in data["content"] if p.get("type") == "text")
        except (KeyError, TypeError) as e:
            raise BocgError(f"anthropic: unexpected response shape: {e}: {json.dumps(data)[:300]}")
        return ProviderResult(raw_text=text, usage=data.get("usage") or {}, model_id=data.get("model") or self.model,
                              extra={"stop_reason": data.get("stop_reason")})

    def _messages_sse(self, url: str, headers: dict, body: dict, timeout: float) -> ProviderResult:
        """Messages API over SSE. Transport only — long generations must stream (the API rejects
        non-streamed requests whose expected duration exceeds its limit). Text is reassembled verbatim."""
        c = self.client(timeout)
        parts: list[str] = []
        usage: dict = {}
        model_id = None
        stop_reason = None
        with c.stream("POST", url, headers=headers, json={**body, "stream": True}) as r:
            if r.status_code >= 400:
                r.read()
                raise BocgError(f"anthropic HTTP {r.status_code}: {r.text[:500]}")
            for line in r.iter_lines():
                if not line.startswith("data:"):
                    continue
                try:
                    ev = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                t = ev.get("type")
                if t == "content_block_delta":
                    d = ev.get("delta") or {}
                    if d.get("type") == "text_delta" and d.get("text"):
                        parts.append(d["text"])
                elif t == "message_start":
                    msg = ev.get("message") or {}
                    model_id = msg.get("model") or model_id
                    usage = {**(msg.get("usage") or {})}
                elif t == "message_delta":
                    usage.update(ev.get("usage") or {})
                    stop_reason = ((ev.get("delta") or {}).get("stop_reason")) or stop_reason
                elif t == "error":
                    raise BocgError(f"anthropic stream error: {json.dumps(ev)[:300]}")
        if not parts:
            raise BocgError("anthropic: stream produced no text deltas")
        return ProviderResult(raw_text="".join(parts), usage=usage, model_id=model_id or self.model,
                              extra={"stop_reason": stop_reason, "streamed": True})


class Google(Provider):
    name = "google"
    vendor = "google"

    def default_base_url(self) -> str:
        return "https://generativelanguage.googleapis.com/v1beta"

    def default_key_env(self) -> str:
        return "GOOGLE_API_KEY"

    def complete(self, system: str, user: str, params: CallParams) -> ProviderResult:
        gen: dict[str, Any] = {"temperature": params.temperature, "topP": params.top_p,
                               "maxOutputTokens": params.max_tokens, "responseMimeType": "application/json"}
        if params.seed is not None:
            gen["seed"] = params.seed
        body = {"systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": gen}
        # no `tools` (incl. googleSearch grounding) => cold (I3)
        url = f"{self.base_url.rstrip('/')}/models/{self.model}:generateContent"
        data = self._post(url, {"x-goog-api-key": self.api_key(), "Content-Type": "application/json"},
                          body, params.timeout_s)
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts)
        except (KeyError, IndexError, TypeError) as e:
            raise BocgError(f"google: unexpected response shape: {e}: {json.dumps(data)[:300]}")
        return ProviderResult(raw_text=text, usage=data.get("usageMetadata") or {},
                              model_id=data.get("modelVersion") or self.model,
                              extra={"finish_reason": data["candidates"][0].get("finishReason")})


class FixtureProvider(Provider):
    """DRY_RUN (§4): replays stored responses from <dir>/<model_id>/<i>.json. No network.

    Fixture file format == run-record format (superset accepted): needs `response_raw`; optional `model_id`,
    `vendor`, `usage`, `params`. A run directory `runs/<prompt_sha8>/` is therefore itself a valid fixtures dir.
    """
    name = "fixture"
    cold_guarantee = True

    def __init__(self, model: str, fixtures_dir: Path, vendor: str | None = None):
        self.model = model
        self.dir = Path(fixtures_dir) / safe_dirname(model)
        self.vendor = vendor or "fixture"
        self.base_url = None
        self.api_key_env = None
        self._client = None
        self._calls: dict[int, int] = {}
        if not self.dir.is_dir():
            raise BocgError(f"no fixtures for model {model!r} under {fixtures_dir}")

    def sample_indices(self) -> list[int]:
        return sorted(int(p.stem) for p in self.dir.glob("*.json") if p.stem.isdigit())

    def load(self, idx: int) -> dict:
        p = self.dir / f"{idx}.json"
        if not p.exists():
            raise BocgError(f"missing fixture {p}")
        d = read_json(p)
        if "response_raw" not in d:
            raise BocgError(f"fixture {p} lacks `response_raw`")
        return d

    def complete(self, system: str, user: str, params: CallParams, sample_idx: int = 0) -> ProviderResult:
        d = self.load(sample_idx)
        self._calls[sample_idx] = self._calls.get(sample_idx, 0) + 1
        return ProviderResult(raw_text=d["response_raw"], usage=d.get("usage") or {},
                              model_id=d.get("model_id") or self.model,
                              extra={"fixture": str(self.dir / f"{sample_idx}.json"),
                                     "vendor": d.get("vendor", self.vendor), "replay": True})


PROVIDERS: dict[str, type[Provider]] = {
    "openai": OpenAI,
    "anthropic": Anthropic,
    "google": Google,
    "deepseek": DeepSeek,
    "xai": XAI,
    "generic_openai_compatible": OpenAICompatible,
    "generic": OpenAICompatible,
}


def make_provider(spec: dict, client: httpx.Client | None = None) -> Provider:
    name = spec.get("provider")
    if name not in PROVIDERS:
        raise BocgError(f"unknown provider {name!r}; known: {sorted(PROVIDERS)}")
    return PROVIDERS[name](model=spec["model"], base_url=spec.get("base_url"), api_key_env=spec.get("api_key_env"),
                           client=client)
