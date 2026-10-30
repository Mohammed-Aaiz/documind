"""Groq-only resilience contracts replacing the retired Ollama failover path."""
import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr

from generation import providers
from generation.types import GenerationUnavailableError


def config(**changes):
    values = dict(answer_provider="groq", answer_auto_fallback=False,
                  groq_model="hosted-model", groq_api_key=SecretStr("fake-private-key"),
                  answer_timeout_seconds=5, groq_timeout_seconds=2)
    values.update(changes)
    return SimpleNamespace(**values)


def install_transport(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(providers.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))


def response(text):
    event = json.dumps({"model": "hosted-model", "choices": [{"delta": {"content": text}, "finish_reason": "stop"}]})
    return httpx.Response(200, text=f"data: {event}\n\ndata: [DONE]\n\n")


@pytest.mark.asyncio
async def test_partial_upstream_failure_does_not_release_unfinished_draft(monkeypatch):
    class PartialStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'data: {"choices":[{"delta":{"content":"UNFINISHED DRAFT"}}]}\n\n'
            raise httpx.ReadError("private transport detail")
    install_transport(monkeypatch, lambda request: httpx.Response(200, stream=PartialStream()))
    visible = []
    with pytest.raises(GenerationUnavailableError) as caught:
        async for delta in providers.stream_answer([], max_tokens=128, settings=config()):
            visible.append(delta.text)
    assert visible == []
    assert "private transport detail" not in str(caught.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("budget", ["total", "provider", "caller"])
async def test_hanging_groq_stream_obeys_each_deadline_and_closes(monkeypatch, budget):
    closed = asyncio.Event()
    class HangingStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            await asyncio.Event().wait()
            yield b""
        async def aclose(self):
            closed.set()
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, stream=HangingStream())
    install_transport(monkeypatch, handler)
    changes = {"answer_timeout_seconds": .02} if budget == "total" else {"groq_timeout_seconds": .02} if budget == "provider" else {}
    options = {"timeout_seconds": .02} if budget == "caller" else {}
    async def consume():
        return [delta async for delta in providers.stream_answer([], max_tokens=128, settings=config(**changes), **options)]
    with pytest.raises(GenerationUnavailableError):
        await asyncio.wait_for(consume(), .5)
    assert closed.is_set()
    assert len(requests) == 1 and requests[0].url.host == "api.groq.com"


@pytest.mark.asyncio
async def test_structured_completion_is_single_groq_request(monkeypatch):
    requests = []
    def handler(request):
        requests.append(request)
        assert request.url.host == "api.groq.com"
        assert json.loads(request.content)["response_format"] == {"type": "json_object"}
        return response('{"path":"both"}')
    install_transport(monkeypatch, handler)
    result = await providers.complete_answer([], max_tokens=64, settings=config(), json_mode=True, purpose="query-routing")
    assert json.loads(result.text) == {"path": "both"}
    assert result.provider == "groq" and result.model == "hosted-model"
    assert result.fallback_used is False and len(requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["not JSON", "[]", "null"])
async def test_invalid_structured_result_fails_without_provider_switch(monkeypatch, text):
    requests = []
    def handler(request):
        requests.append(request)
        return response(text)
    install_transport(monkeypatch, handler)
    with pytest.raises(GenerationUnavailableError):
        await providers.complete_answer([], max_tokens=64, settings=config(), json_mode=True)
    assert [request.url.host for request in requests] == ["api.groq.com"]


@pytest.mark.asyncio
async def test_failed_routing_does_not_disable_subsequent_answer_request(monkeypatch):
    requests = []
    def handler(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(503, text="private failure")
        return response("The supported answer [1]")
    install_transport(monkeypatch, handler)
    trace = {}
    with pytest.raises(GenerationUnavailableError):
        await providers.complete_answer([], max_tokens=64, settings=config(), purpose="query-routing", attempt_state=trace)
    assert trace["hosted_attempted"] is True and trace["provider"] == "groq"
    answer = await providers.complete_answer([], max_tokens=128, settings=config(), purpose="answer")
    assert answer.text == "The supported answer [1]"
    assert len(requests) == 2
    assert {request.url.host for request in requests} == {"api.groq.com"}
