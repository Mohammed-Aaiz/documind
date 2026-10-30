"""Groq transport, credential, error and cancellation contracts; no network."""
import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr

from generation import providers
from generation.types import GenerationUnavailableError


def settings(provider="groq", **changes):
    values = dict(answer_provider=provider, answer_auto_fallback=False,
                  groq_model="openai/gpt-oss-20b", groq_timeout_seconds=5,
                  groq_api_key=SecretStr("fake-test-key-must-not-leak"), answer_timeout_seconds=5)
    values.update(changes)
    return SimpleNamespace(**values)


def transport(monkeypatch, handler):
    client_class = httpx.AsyncClient
    monkeypatch.setattr(providers.httpx, "AsyncClient", lambda **kwargs: client_class(transport=httpx.MockTransport(handler), **kwargs))


def stream(text="Supported [1]", *, model="openai/gpt-oss-20b"):
    event = json.dumps({"model": model, "choices": [{"delta": {"content": text}, "finish_reason": "stop"}]})
    return f"data: {event}\n\ndata: [DONE]\n\n"


async def collect(config):
    return [delta async for delta in providers.stream_answer([{"role": "user", "content": "Question"}], max_tokens=128, settings=config)]


@pytest.mark.asyncio
async def test_groq_stream_uses_server_key_and_reports_provider(monkeypatch):
    requests = []
    def handler(request):
        requests.append(request)
        assert request.url.host == "api.groq.com"
        assert request.url.path == "/openai/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer fake-test-key-must-not-leak"
        payload = json.loads(request.content)
        assert payload["model"] == "openai/gpt-oss-20b"
        assert payload["stream"] is True
        assert payload["reasoning_effort"] == "low"
        assert payload["include_reasoning"] is False
        return httpx.Response(200, text=stream())
    transport(monkeypatch, handler)
    deltas = await collect(settings())
    assert "".join(d.text for d in deltas) == "Supported [1]"
    assert deltas[-1].done and deltas[-1].finish_reason == "stop"
    assert all(d.provider == "groq" and not d.fallback_used for d in deltas)
    assert len(requests) == 1
    assert "fake-test-key-must-not-leak" not in str(providers.provider_status(settings()))


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["ollama", "unknown"])
async def test_non_groq_selection_is_rejected_before_network(monkeypatch, provider):
    def handler(request):
        pytest.fail("A retired provider must not make a network request")
    transport(monkeypatch, handler)
    status = providers.provider_status(settings(provider))
    assert status["configured"] is False
    assert status["fallbackConfigured"] is False
    with pytest.raises(GenerationUnavailableError):
        await collect(settings(provider))


@pytest.mark.asyncio
async def test_groq_connection_failure_never_contacts_local_service(monkeypatch):
    requests = []
    def handler(request):
        requests.append(request)
        raise httpx.ConnectError("private connection details", request=request)
    transport(monkeypatch, handler)
    with pytest.raises(GenerationUnavailableError) as error:
        await collect(settings(answer_auto_fallback=True))
    assert len(requests) == 1 and requests[0].url.host == "api.groq.com"
    assert "private connection details" not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("header,expected", [("3", 3), ("9999", 300), ("-5", 0), ("nan", None), ("not-a-delay", None)])
async def test_rate_limit_exposes_only_bounded_retry_metadata_without_retrying(monkeypatch, header, expected):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(429, headers={"Retry-After": header}, text="private upstream key and body")
    transport(monkeypatch, handler)
    with pytest.raises(GenerationUnavailableError) as error:
        await collect(settings())
    assert error.value.status_code == 429
    assert error.value.retry_after_seconds == expected
    assert len(requests) == 1
    assert "private upstream" not in str(error.value) and "fake-test-key" not in str(error.value)


@pytest.mark.parametrize("response", [
    "data: not-json\n\n",
    'data: {"choices":[{"delta":{"content":"incomplete"}}]}\n\n',
    'data: {"choices":[{"delta":{"content":7}}]}\n\ndata: [DONE]\n\n',
    'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n',
    'data: {"error":"private upstream detail"}\n\n',
])
@pytest.mark.asyncio
async def test_malformed_empty_and_incomplete_streams_fail(monkeypatch, response):
    transport(monkeypatch, lambda request: httpx.Response(200, text=response))
    with pytest.raises(GenerationUnavailableError):
        await collect(settings())


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 429, 500])
async def test_upstream_error_body_does_not_escape(monkeypatch, status):
    transport(monkeypatch, lambda request: httpx.Response(status, text="fake-test-key-must-not-leak private account info"))
    with pytest.raises(GenerationUnavailableError) as error:
        await collect(settings())
    assert str(status) in str(error.value)
    assert "test-key" not in str(error.value) and "private account" not in str(error.value)


@pytest.mark.asyncio
async def test_missing_groq_key_makes_no_network_request(monkeypatch):
    def handler(request):
        pytest.fail("Missing credentials must be rejected before network access")
    transport(monkeypatch, handler)
    with pytest.raises(GenerationUnavailableError):
        await collect(settings(groq_api_key=SecretStr("")))


@pytest.mark.asyncio
async def test_cancellation_closes_provider_response(monkeypatch):
    waiting, closed = asyncio.Event(), asyncio.Event()
    class BlockingStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'data: {"choices":[{"delta":{"content":"draft"}}]}\n\n'
            waiting.set()
            await asyncio.Event().wait()
        async def aclose(self):
            closed.set()
    transport(monkeypatch, lambda request: httpx.Response(200, stream=BlockingStream()))
    task = asyncio.create_task(collect(settings()))
    await asyncio.wait_for(waiting.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert closed.is_set()


@pytest.mark.asyncio
@pytest.mark.parametrize("installed", [True, False])
async def test_availability_probe_checks_groq_inventory_without_inference(monkeypatch, installed):
    def handler(request):
        assert request.method == "GET" and request.url.host == "api.groq.com"
        assert request.url.path == "/openai/v1/models"
        assert request.content == b""
        return httpx.Response(200, json={"data": [{"id": "openai/gpt-oss-20b" if installed else "other-model"}]})
    transport(monkeypatch, handler)
    status = await providers.probe_provider(settings())
    assert status["hosted"] is True and status["configured"] is True
    assert status["availabilityChecked"] is True
    assert status["available"] is installed
    assert status["fallbackConfigured"] is False


@pytest.mark.asyncio
async def test_probe_invalid_key_reports_safe_error(monkeypatch):
    transport(monkeypatch, lambda request: httpx.Response(401, text="fake-test-key-must-not-leak private account details"))
    status = await providers.probe_provider(settings())
    assert status["available"] is False and status["availabilityChecked"] is True
    assert "key" in status["error"].lower()
    assert "fake-test-key" not in str(status) and "private account" not in str(status)
