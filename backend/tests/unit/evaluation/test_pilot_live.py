"""Research mapping/target admission tests; never opens a database or encoder."""
from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock

import pytest

import config
from evaluation.pilot_live import run as live


def mapping_fixture(body="Alpha links beta.\n\nGamma links delta."):
    page = "Page preface.\n\n" + body
    start = page.index(body)
    prefix = "Topic heading\n\n"
    origin = {"document_id": "d", "page": 2, "start_char": start, "end_char": len(page),
              "content": prefix + body, "body_offset": len(prefix), "source_sha256": "a" * 64}
    docs = {"d": {"pages": [{"page": 2, "canonical_text": page}], "raw_file_sha256": "a" * 64}}
    return origin, docs


def record(text):
    return {"excerpts": [{"chunk_id": "c", "text": text, "context_source": 1}]}


def test_fitted_prefix_maps_only_actual_body_characters():
    origin, docs = mapping_fixture()
    supplied = origin["content"][:origin["body_offset"] + 17]
    result = live.map_record(record(supplied), {"c": origin}, docs)
    assert result["source_mapping"] == "verified_canonical_intervals_v1"
    excerpt = result["excerpts"][0]
    assert excerpt["start_char"] == origin["start_char"]
    assert excerpt["end_char"] == origin["start_char"] + 17
    assert excerpt["text"] == "Alpha links beta." and excerpt["context_source"] == 1


def test_heading_alone_cannot_claim_unseen_paragraph():
    origin, docs = mapping_fixture()
    assert live.map_record(record("Topic heading"), {"c": origin}, docs)["excerpts"] == []


def test_changed_whitespace_mapping_never_fills_source_gaps():
    origin, docs = mapping_fixture()
    supplied = "Alpha links beta. Gamma links delta."
    result = live.map_record(record(supplied), {"c": origin}, docs)
    assert result["source_mapping"] == "exact_fragment_lower_bound"
    spans = result["excerpts"]
    assert len(spans) >= 2
    assert all(e["text"] in supplied for e in spans)
    assert any(a["end_char"] < b["start_char"] for a, b in zip(spans, spans[1:]))
    assert all("\n" not in e["text"] for e in spans)


def test_ambiguous_fragment_and_unknown_chunk_cannot_gain_credit():
    origin, docs = mapping_fixture("Repeated fact. Repeated fact.")
    result = live.map_record(record("Repeated fact."), {"c": origin}, docs)
    assert result["excerpts"] == [] and result["mapping_caveats"]
    with pytest.raises(ValueError, match="no frozen"):
        live.map_record(record("Repeated fact."), {}, docs)


@pytest.mark.asyncio
@pytest.mark.parametrize("target", [None,
    "postgresql+asyncpg://u:unused@remote.example:55433/documind_pilot_20261101",
    "postgresql+asyncpg://u:unused@localhost:55433/documind",
])
async def test_invalid_target_is_rejected_before_engine_creation(monkeypatch, target):
    from sqlalchemy.ext import asyncio as sa_asyncio
    monkeypatch.setattr(config, "get_settings", lambda: SimpleNamespace(
        database_url="postgresql+asyncpg://u:unused@localhost:55433/documind"))
    if target is None: monkeypatch.delenv("DOCUMIND_PILOT_DATABASE_URL", raising=False)
    else: monkeypatch.setenv("DOCUMIND_PILOT_DATABASE_URL", target)
    engine = Mock(side_effect=AssertionError("No connection permitted"))
    monkeypatch.setattr(sa_asyncio, "create_async_engine", engine)
    with pytest.raises(ValueError):
        await live.connect()
    engine.assert_not_called()


@pytest.mark.asyncio
async def test_loopback_alias_does_not_bypass_product_database_guard(monkeypatch):
    from sqlalchemy.ext import asyncio as sa_asyncio
    monkeypatch.setattr(config, "get_settings", lambda: SimpleNamespace(
        database_url="postgresql+asyncpg://u:unused@localhost:55433/" + live.TARGET))
    monkeypatch.setenv("DOCUMIND_PILOT_DATABASE_URL", "postgresql+asyncpg://u:unused@127.0.0.1:55433/" + live.TARGET)
    engine = Mock(side_effect=AssertionError("No connection permitted"))
    monkeypatch.setattr(sa_asyncio, "create_async_engine", engine)
    with pytest.raises(ValueError):
        await live.connect()
    engine.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("identity", [(live.TARGET, "wrong-marker", "018"), (live.TARGET, live.MARKER, "017")])
async def test_target_marker_and_schema_must_match_before_sessions_are_returned(monkeypatch, identity):
    from sqlalchemy.ext import asyncio as sa_asyncio
    monkeypatch.setattr(config, "get_settings", lambda: SimpleNamespace(
        database_url="postgresql+asyncpg://u:unused@localhost:55433/documind"))
    monkeypatch.setenv("DOCUMIND_PILOT_DATABASE_URL", "postgresql+asyncpg://u:unused@127.0.0.1:55433/" + live.TARGET)
    class Context:
        async def __aenter__(self): return SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(one=lambda: identity)))
        async def __aexit__(self, *args): pass
    engine = SimpleNamespace(connect=lambda: Context(), dispose=AsyncMock())
    monkeypatch.setattr(sa_asyncio, "create_async_engine", lambda *a, **k: engine)
    with pytest.raises(ValueError, match="marker or migration"):
        await live.connect()
    engine.dispose.assert_awaited_once()
