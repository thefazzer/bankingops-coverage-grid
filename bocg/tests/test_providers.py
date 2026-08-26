"""Provider adapters (no network: httpx.MockTransport) + fixture replay."""
import json

import httpx
import pytest

from bocg.providers import (Anthropic, CallParams, DeepSeek, FixtureProvider, Google, OpenAI, OpenAICompatible,
                            XAI, make_provider)
from bocg.util import BocgError


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_openai_adapter_shapes_request_and_parses_response(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    seen = {}

    def handler(req: httpx.Request):
        seen["url"] = str(req.url)
        seen["auth"] = req.headers["authorization"]
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"model": "gpt-5-2025-08-07", "choices": [{"message": {"content": "{}"},
                                         "finish_reason": "stop"}], "usage": {"total_tokens": 5}})

    p = OpenAI("gpt-5", client=_client(handler))
    r = p.complete("sys", "user", CallParams(temperature=0.2, top_p=1.0, max_tokens=16000, seed=1001))
    assert r.raw_text == "{}" and r.model_id == "gpt-5-2025-08-07" and r.usage == {"total_tokens": 5}
    assert seen["url"] == "https://api.openai.com/v1/chat/completions" and seen["auth"] == "Bearer k"
    b = seen["body"]
    assert b["messages"][0] == {"role": "system", "content": "sys"} and b["seed"] == 1001
    assert "tools" not in b and "tool_choice" not in b


def test_anthropic_adapter(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    seen = {}

    def handler(req):
        seen["h"] = dict(req.headers)
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"model": "claude-opus-4-1-20250805", "stop_reason": "end_turn",
                                         "content": [{"type": "text", "text": '{"x":1}'}],
                                         "usage": {"input_tokens": 1, "output_tokens": 2}})

    r = Anthropic("claude-opus-4-1", client=_client(handler)).complete("sys", "u", CallParams())
    assert r.raw_text == '{"x":1}' and r.model_id == "claude-opus-4-1-20250805"
    assert seen["h"]["x-api-key"] == "k" and seen["h"]["anthropic-version"] == "2023-06-01"
    assert seen["body"]["system"] == "sys" and "tools" not in seen["body"]


def test_google_adapter(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "k")
    seen = {}

    def handler(req):
        seen["url"] = str(req.url)
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"modelVersion": "gemini-2.5-pro-001",
                                         "candidates": [{"content": {"parts": [{"text": "{}"}]}, "finishReason": "STOP"}],
                                         "usageMetadata": {"totalTokenCount": 3}})

    r = Google("gemini-2.5-pro", client=_client(handler)).complete("sys", "u", CallParams(seed=7))
    assert r.raw_text == "{}" and r.model_id == "gemini-2.5-pro-001"
    assert seen["url"].endswith("/models/gemini-2.5-pro:generateContent")
    assert seen["body"]["systemInstruction"]["parts"][0]["text"] == "sys" and "tools" not in seen["body"]
    assert seen["body"]["generationConfig"]["seed"] == 7


def test_openai_compatible_family_endpoints_and_keys(monkeypatch):
    assert DeepSeek("deepseek-v3").base_url == "https://api.deepseek.com/v1"
    assert DeepSeek("x").api_key_env == "DEEPSEEK_API_KEY"
    assert XAI("grok-4").base_url == "https://api.x.ai/v1" and XAI("x").api_key_env == "XAI_API_KEY"
    g = make_provider({"provider": "generic_openai_compatible", "model": "llama-4", "base_url": "http://localhost:8000/v1",
                       "api_key_env": "MY_KEY"})
    assert isinstance(g, OpenAICompatible) and g.base_url == "http://localhost:8000/v1" and g.api_key_env == "MY_KEY"
    monkeypatch.delenv("MY_KEY", raising=False)
    with pytest.raises(BocgError, match="MY_KEY"):
        g.api_key()
    with pytest.raises(BocgError, match="unknown provider"):
        make_provider({"provider": "meta", "model": "x"})


def test_http_error_is_surfaced(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    p = OpenAI("gpt-5", client=_client(lambda req: httpx.Response(429, text="rate limited")))
    with pytest.raises(BocgError, match="HTTP 429"):
        p.complete("s", "u", CallParams())


def test_fixture_provider_replays_without_network(fixtures_dir):
    p = FixtureProvider("alpha-lm-1.0", fixtures_dir)
    assert p.sample_indices() == [0, 1, 2, 3]
    r = p.complete("s", "u", CallParams(), sample_idx=1)
    assert r.model_id == "alpha-lm-1.0" and r.extra["replay"] and r.extra["vendor"] == "alphalabs"
    assert json.loads(r.raw_text)["divisions"]
    with pytest.raises(BocgError):
        FixtureProvider("no-such-model", fixtures_dir)
