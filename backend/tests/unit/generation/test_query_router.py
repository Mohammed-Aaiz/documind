"""Bounded LLM routing, cache isolation and conservative failure policy."""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from generation import query_router
from generation.providers import ProviderCompletion
from generation.types import GenerationUnavailableError


@pytest.fixture(autouse=True)
def reset_router_cache():
    query_router.clear_router_cache()
    yield
    query_router.clear_router_cache()


def config(**changes):
    values = dict(query_router_enabled=True, query_router_timeout_seconds=0.05,
                  answer_provider="groq", groq_model="hosted-model",
                  answer_auto_fallback=False)
    values.update(changes)
    return SimpleNamespace(**values)


def completion(text):
    return ProviderCompletion(text=text, provider="groq", model="hosted-model",
                              finish_reason="stop", fallback_used=False)


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["semantic", "graph", "both"])
async def test_llm_classification_selects_the_requested_path(monkeypatch, path):
    calls = []

    async def classify(messages, **kwargs):
        calls.append((messages, kwargs))
        return completion(json.dumps({"path": path}))

    monkeypatch.setattr(query_router, "complete_answer", classify)
    result = await query_router.route_query("How does Alpha connect to Gamma?", settings=config())
    assert result.path == path
    assert result.source == "llm"
    assert result.latency_ms >= 0
    assert len(calls) == 1
    assert calls[0][1]["max_tokens"] <= 64
    assert calls[0][1]["json_mode"] is True
    assert calls[0][1]["timeout_seconds"] <= 0.05


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["not json", '{"path":"sql"}', '{"path":null}', '["semantic"]'])
async def test_invalid_classifier_output_searches_both_paths(monkeypatch, text):
    async def classify(*_args, **_kwargs):
        return completion(text)

    monkeypatch.setattr(query_router, "complete_answer", classify)
    result = await query_router.route_query("Explain the Kestrel platform", settings=config())
    assert result.path == "both"
    assert result.source == "fallback"


@pytest.mark.asyncio
async def test_unavailable_classifier_searches_both_paths(monkeypatch):
    async def unavailable(*_args, **_kwargs):
        raise GenerationUnavailableError("configured provider unavailable")

    monkeypatch.setattr(query_router, "complete_answer", unavailable)
    result = await query_router.route_query("Explain the Kestrel platform", settings=config())
    assert (result.path, result.source) == ("both", "fallback")


@pytest.mark.asyncio
async def test_hanging_classifier_cannot_block_retrieval(monkeypatch):
    async def hanging(*_args, **_kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr(query_router, "complete_answer", hanging)
    result = await asyncio.wait_for(
        query_router.route_query("Explain Kestrel", settings=config(query_router_timeout_seconds=0.02)),
        timeout=0.5,
    )
    assert (result.path, result.source) == ("both", "fallback")


@pytest.mark.asyncio
async def test_cached_decision_avoids_a_second_inference_but_not_a_model_change(monkeypatch):
    calls = []

    async def classify(*_args, **kwargs):
        calls.append(kwargs)
        return completion('{"path":"graph"}')

    monkeypatch.setattr(query_router, "complete_answer", classify)
    first = await query_router.route_query("How does Alpha reach Gamma?", settings=config())
    second = await query_router.route_query("How does Alpha reach Gamma?", settings=config())
    third = await query_router.route_query("How does Alpha reach Gamma?", settings=config(groq_model="another-model"))
    assert (first.source, second.source, third.source) == ("llm", "cache", "llm")
    assert first.path == second.path == third.path == "graph"
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_disabled_classifier_searches_both_without_inference(monkeypatch):
    async def forbidden(*_args, **_kwargs):
        pytest.fail("A disabled router must not call an LLM")

    monkeypatch.setattr(query_router, "complete_answer", forbidden)
    result = await query_router.route_query("Explain Kestrel", settings=config(query_router_enabled=False))
    assert (result.path, result.source) == ("both", "disabled")


@pytest.mark.asyncio
@pytest.mark.parametrize("question", ["", "   ", "x" * 2001])
async def test_invalid_question_is_rejected_before_inference(monkeypatch, question):
    async def forbidden(*_args, **_kwargs):
        pytest.fail("An invalid question must not reach the provider")

    monkeypatch.setattr(query_router, "complete_answer", forbidden)
    with pytest.raises(ValueError):
        await query_router.route_query(question, settings=config())


@pytest.mark.asyncio
async def test_cancellation_is_not_relabelled_as_a_fallback_decision(monkeypatch):
    entered = asyncio.Event()

    async def hanging(*_args, **_kwargs):
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(query_router, "complete_answer", hanging)
    task = asyncio.create_task(query_router.route_query("Explain Kestrel", settings=config(query_router_timeout_seconds=5)))
    await asyncio.wait_for(entered.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["outer-timeout", "provider-error"])
async def test_failed_hosted_router_attempt_is_disclosed_even_when_no_result_returns(monkeypatch, failure):
    async def attempted(*_args, **kwargs):
        kwargs["attempt_state"].update(provider="groq", hosted_attempted=True)
        if failure == "outer-timeout":
            await asyncio.Event().wait()
        raise GenerationUnavailableError("sanitized provider failure")

    monkeypatch.setattr(query_router, "complete_answer", attempted)
    result = await asyncio.wait_for(query_router.route_query("How is Alpha connected to Beta?",
        settings=config(query_router_timeout_seconds=.02)), .5)
    assert (result.path, result.source) == ("both", "fallback")
    assert result.hosted is True and result.provider == "groq"
