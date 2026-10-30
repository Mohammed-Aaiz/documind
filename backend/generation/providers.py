"""Deadline-bounded Groq inference.

Attempts are buffered atomically. Cancellation closes the active response.
Provider bodies and credentials never appear in public errors.
"""
from __future__ import annotations

import asyncio
import json
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import AsyncIterator, Sequence

import httpx

from generation.types import GenerationUnavailableError

MAX_OUTPUT_CHARS = 8000


@dataclass(frozen=True)
class ProviderDelta:
    text: str = ""
    done: bool = False
    model: str = ""
    finish_reason: str = ""
    provider: str = ""
    fallback_used: bool = False


@dataclass(frozen=True)
class ProviderCompletion:
    text: str
    provider: str
    model: str
    finish_reason: str = ""
    fallback_used: bool = False


def clear_provider_circuits() -> None:
    """Compatibility hook; Groq-only inference has no fallback circuit state."""


def _secret(value: object) -> str:
    return str(value.get_secret_value() if hasattr(value, "get_secret_value") else value or "")


def provider_status(settings=None) -> dict:
    if settings is None:
        from config import get_settings
        settings = get_settings()
    provider = str(getattr(settings, "answer_provider", "groq")).lower()
    hosted = provider == "groq"
    model = str(getattr(settings, "groq_model", "openai/gpt-oss-20b"))
    configured = provider == "groq" and bool(model)
    error = None
    if provider != "groq":
        error = "Unsupported answer provider. Configure groq."
    elif hosted and not _secret(getattr(settings, "groq_api_key", "")):
        configured = False
        error = "Groq is selected but its server API key is not configured."
    fallback = False
    return {"provider": provider, "model": model, "configured": configured,
            "available": None if configured else False, "loaded": False,
            "hosted": hosted, "error": error,
            "availabilityChecked": False,
            "fallbackConfigured": fallback, "fallbackProvider": "groq" if fallback else None,
            "mayUseHosted": hosted or fallback,
            "privacy": "Evidence and conversation are sent to Groq."}


async def probe_provider(settings=None) -> dict:
    """Check credentials and Groq model inventory without sending user evidence."""
    if settings is None:
        from config import get_settings
        settings = get_settings()
    status = provider_status(settings)
    if not status["configured"]:
        return status
    try:
        async with httpx.AsyncClient(timeout=3.0, follow_redirects=False) as client:
            response = await client.get("https://api.groq.com/openai/v1/models",
                headers={"Authorization": "Bearer " + _secret(settings.groq_api_key)})
            response.raise_for_status()
            models = response.json().get("data", [])
            names = {str(item.get("id", "")) for item in models if isinstance(item, dict)}
        available = status["model"] in names
        status.update(available=available, availabilityChecked=True,
                      error=None if available else "The configured model is not available from Groq.")
    except httpx.HTTPStatusError as exc:
        status.update(available=False, availabilityChecked=True,
                      error="Groq rejected the configured API key." if exc.response.status_code in (401, 403)
                      else "Groq model availability could not be checked. Try again shortly.")
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        status.update(available=False, availabilityChecked=True,
                      error="Groq is unreachable or returned an invalid model inventory.")
    return status


async def _stream_single(messages: Sequence[dict[str, str]], *, max_tokens: int, settings,
                         provider: str, timeout_seconds: float, json_mode: bool = False,
                         http_client: httpx.AsyncClient | None = None) -> AsyncIterator[ProviderDelta]:
    """Yield content only, then a required completion marker; cancellation closes HTTP."""
    if provider != "groq":
        raise GenerationUnavailableError("Unsupported answer provider. Configure groq.")
    model = str(getattr(settings, "groq_model", "openai/gpt-oss-20b"))
    if provider == "groq" and not _secret(getattr(settings, "groq_api_key", "")):
        raise GenerationUnavailableError("Groq is selected but its server API key is not configured.")
    timeout = max(0.01, min(float(timeout_seconds), 300.0))
    max_tokens = max(64, min(int(max_tokens), 1536))
    headers = {"Content-Type": "application/json"}
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers["Authorization"] = "Bearer " + _secret(getattr(settings, "groq_api_key", ""))
    payload = {"model": model, "messages": list(messages), "stream": True,
               "temperature": 0.2, "max_completion_tokens": max_tokens}
    if model.startswith("openai/gpt-oss-"):
        # GPT-OSS budgets reasoning inside max_completion_tokens. Reserve a
        # small amount so a tiny routing JSON is not starved by reasoning.
        payload.update(reasoning_effort="low", include_reasoning=False,
                       max_completion_tokens=min(1536, max_tokens + 256))
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    length = 0
    completed = False
    finish_reason = ""
    try:
        async with asyncio.timeout(timeout):
            async with AsyncExitStack() as stack:
                client = http_client if http_client is not None else await stack.enter_async_context(
                    httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=min(5.0, timeout)), follow_redirects=False))
                async with client.stream("POST", url, json=payload, headers=headers,
                                         timeout=httpx.Timeout(timeout, connect=min(5.0, timeout))) as response:
                    if response.status_code >= 400:
                        code = response.status_code
                        hint = "Check the server API key." if code in (401, 403) else (
                            "The provider is rate limited; try again shortly." if code == 429 else
                            "Check that the configured service and model are available.")
                        raise GenerationUnavailableError(f"{provider.title()} request failed ({code}). {hint}")
                    async for raw in response.aiter_lines():
                        if not raw or raw.startswith(":"):
                            continue
                        if len(raw) > 131072:
                            raise GenerationUnavailableError("Answer provider returned an oversized response.")
                        if not raw.startswith("data:"):
                            continue
                        raw = raw[5:].strip()
                        if raw == "[DONE]":
                            completed = True
                            break
                        data = json.loads(raw)
                        if not isinstance(data, dict) or data.get("error"):
                            raise GenerationUnavailableError("Answer provider reported an inference error.")
                        reported_model = data.get("model")
                        if isinstance(reported_model, str) and reported_model:
                            model = reported_model
                        choices = data.get("choices") or []
                        choice = choices[0] if choices else {}
                        token = (choice.get("delta") or {}).get("content") or ""
                        if choice.get("finish_reason"):
                            finish_reason = str(choice["finish_reason"])
                        if not isinstance(token, str):
                            raise GenerationUnavailableError("Answer provider returned invalid text.")
                        length += len(token)
                        if length > MAX_OUTPUT_CHARS:
                            raise GenerationUnavailableError("The answer exceeded the permitted output size.")
                        if token:
                            yield ProviderDelta(text=token, model=model, provider=provider)
                        if completed:
                            break
    except (TimeoutError, httpx.TimeoutException) as exc:
        raise GenerationUnavailableError("The answer provider timed out. Try a shorter question or smaller model.") from exc
    except httpx.HTTPError as exc:
        raise GenerationUnavailableError(f"Could not reach {provider.title()}. Check the configured service.") from exc
    except (json.JSONDecodeError, TypeError, AttributeError, IndexError) as exc:
        raise GenerationUnavailableError("The answer provider returned an invalid stream.") from exc
    if not completed:
        raise GenerationUnavailableError("The answer stream ended before completion. Please retry.")
    if not length:
        raise GenerationUnavailableError("The answer provider returned no answer text.")
    yield ProviderDelta(done=True, model=model, finish_reason=finish_reason, provider=provider)


async def stream_answer(messages: Sequence[dict[str, str]], *, max_tokens: int, settings=None,
                        timeout_seconds: float | None = None, json_mode: bool = False,
                        purpose: str = "answer", http_client: httpx.AsyncClient | None = None,
                        attempt_state: dict | None = None) -> AsyncIterator[ProviderDelta]:
    """Complete one bounded Groq attempt without a local model or fallback.

    Buffering preserves atomic completion: consumers never receive partial
    output from a failed stream. The conversation layer verifies the completed
    answer before displaying text or speaking it.
    """
    if settings is None:
        from config import get_settings
        settings = get_settings()
    status = provider_status(settings)
    if not status["configured"]:
        raise GenerationUnavailableError(status["error"] or "Answer provider is not configured.")
    total = max(0.01, min(float(timeout_seconds if timeout_seconds is not None else
                              getattr(settings, "answer_timeout_seconds", 120)), 300.0))
    timeout = min(total, max(0.01, float(getattr(settings, "groq_timeout_seconds", total))))
    if attempt_state is not None:
        # Report possible egress even if an outer router deadline cancels us.
        # This trace never retains prompts or credentials.
        attempt_state["provider"] = "groq"
        attempt_state["hosted_attempted"] = True
    try:
        buffered = [delta async for delta in _stream_single(
            messages, max_tokens=max_tokens, settings=settings, provider="groq",
            timeout_seconds=timeout, json_mode=json_mode, http_client=http_client)]
        if json_mode:
            try:
                parsed = json.loads("".join(delta.text for delta in buffered))
                if not isinstance(parsed, dict):
                    raise ValueError("not an object")
            except (ValueError, TypeError) as exc:
                raise GenerationUnavailableError("The provider returned invalid structured output.") from exc
    except GenerationUnavailableError as exc:
        exc.hosted_attempted = True
        raise
    for delta in buffered:
        yield ProviderDelta(text=delta.text, done=delta.done, model=delta.model,
                            finish_reason=delta.finish_reason, provider="groq",
                            fallback_used=False)


async def complete_answer(messages: Sequence[dict[str, str]], *, max_tokens: int, settings=None,
                          timeout_seconds: float | None = None, json_mode: bool = False,
                          purpose: str = "answer", http_client: httpx.AsyncClient | None = None,
                          attempt_state: dict | None = None) -> ProviderCompletion:
    """Shared bounded completion for answer synthesis, routing and graph indexing."""
    pieces: list[str] = []
    final = ProviderDelta()
    async for delta in stream_answer(messages, max_tokens=max_tokens, settings=settings,
                                     timeout_seconds=timeout_seconds, json_mode=json_mode, purpose=purpose,
                                     http_client=http_client, attempt_state=attempt_state):
        pieces.append(delta.text)
        final = delta
    return ProviderCompletion("".join(pieces), final.provider, final.model,
                              final.finish_reason, final.fallback_used)
