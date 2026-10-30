"""Topic expansion retains provenance and reports bounded/inferred coverage."""
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest

from chat.rag import SourceChunk
from generation.topic_context import assemble_topic_context, expand_topic_context


def seed(cid="last", **kw):
    return SourceChunk(cid, f"Exact original content for {cid}.", .91, "document-1", "manual.pdf", 12,
                       heading_path=("Calibration",), **kw)


def row(seed_id, cid, index, *, group="document-1:0", kind="section", total=None, content=None):
    content = content or f"Exact original content for {cid}."
    return dict(seed_id=seed_id, id=cid, content=content, page=index,
                heading_path=["Calibration"], section="Calibration", element_type="paragraph",
                token_count=None, chunker_version="structure-v2", chunk_index=index,
                group_id=group, context_kind=kind, total_bytes=total or len(content.encode()))


def test_late_match_recovers_a_complete_topic_and_keeps_its_graph_provenance():
    original = seed(knowledge_graph_path="Rig calibrates Sensor", knowledge_graph_quote="Exact original content for last.")
    rows = [row("last", str(i), i) for i in range(1, 12)] + [row("last", "last", 12)]
    total = sum(len(r["content"].encode()) for r in rows)
    for r in rows:
        r["total_bytes"] = total
    expanded, coverage = assemble_topic_context([original], rows)
    assert len(expanded) == 12 and coverage["status"] == "complete"
    assert [chunk.page for chunk in expanded] == list(range(1, 13))
    assert expanded[-1].knowledge_graph_path == original.knowledge_graph_path
    assert expanded[-1].chunk_id == original.chunk_id
    assert all(chunk.topic_context_complete for chunk in expanded)


def test_duplicate_seed_ranges_do_not_duplicate_passages():
    seeds = [seed("one"), seed("two")]
    rows = [row(s.chunk_id, cid, i, total=80) for s in seeds for i, cid in enumerate(("one", "two"), 1)]
    expanded, _ = assemble_topic_context(seeds, rows)
    assert [chunk.chunk_id for chunk in expanded] == ["one", "two"]


def test_distinct_occurrences_of_the_same_heading_keep_separate_groups():
    seeds = [seed("early"), seed("later")]
    rows = [row("early", "early", 1, group="document-1:0"),
            row("later", "later", 10, group="document-1:9")]
    expanded, coverage = assemble_topic_context(seeds, rows)
    assert coverage["groups"] == 2
    assert expanded[0].topic_context_id != expanded[1].topic_context_id


def test_byte_bound_does_not_drop_a_late_seed_in_an_already_seen_group():
    seeds = [seed("early"), seed("later")]
    rows = [row("early", "early", 1, total=1000), row("later", "early", 1, total=1000),
            row("later", "later", 20, total=1000)]
    expanded, coverage = assemble_topic_context(seeds, rows, max_bytes=10)
    assert {chunk.chunk_id for chunk in expanded} == {"early", "later"}
    assert coverage["status"] == "partial"
    assert not any(chunk.topic_context_complete for chunk in expanded)


def test_headingless_neighbours_never_claim_a_complete_topic():
    original = seed()
    expanded, coverage = assemble_topic_context([original], [row("last", "last", 12, kind="neighbour")])
    assert not expanded[0].topic_context_complete
    assert expanded[0].topic_context_kind == "neighbour"
    assert coverage["status"] != "complete"


def test_unexpanded_seed_prevents_global_complete_coverage():
    expanded, coverage = assemble_topic_context([seed("known"), seed("unknown")], [row("known", "known", 1)])
    assert {chunk.chunk_id for chunk in expanded} == {"known", "unknown"}
    assert coverage["status"] != "complete"


@pytest.mark.asyncio
async def test_expand_uses_one_parameter_bound_owner_scoped_request():
    owner, cid = str(uuid4()), str(uuid4())
    calls = []

    class Database:
        @asynccontextmanager
        async def begin_nested(self):
            yield

        async def execute(self, sql, params):
            calls.append((str(sql), params))
            class Result:
                def fetchall(self):
                    return [row(cid, cid, 12)]
            return Result()

    await expand_topic_context(Database(), owner, [seed(cid), seed(cid)])
    assert len(calls) == 1
    sql, params = calls[0]
    assert params["user_id"] == owner and cid in params["seed_ids"]
    assert owner not in sql and cid not in sql
    assert "d.user_id=CAST(:user_id AS uuid)" in sql
