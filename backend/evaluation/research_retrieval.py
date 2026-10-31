"""Seven controlled text-only research compositions of production primitives.

This is NOT a claim of production-equivalent DocuMind or an executed benchmark.
No app imports, configuration reads, model loads or DB calls occur at import.
The caller supplies a READ ONLY session; production bindings are loaded explicitly.
Run the offline wiring check: python -m evaluation.research_retrieval self-check
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Callable


VARIANTS = {
    "dense": {"hybrid": False, "structure": False, "graph": False, "topic": False, "parent": False},
    "hybrid": {"hybrid": True, "structure": False, "graph": False, "topic": False, "parent": False},
    "parent": {"hybrid": True, "structure": False, "graph": False, "topic": False, "parent": True},
    "graph": {"hybrid": True, "structure": False, "graph": True, "topic": False, "parent": False},
    "documind_no_topic": {"hybrid": True, "structure": True, "graph": True, "topic": False, "parent": False},
    "documind_no_graph": {"hybrid": True, "structure": True, "graph": False, "topic": True, "parent": False},
    "documind_full": {"hybrid": True, "structure": True, "graph": True, "topic": True, "parent": False},
}


@dataclass(frozen=True)
class Controls:
    candidate_depth: int = 32
    seeds: int = 8
    context_ceiling: int = 16384
    graph_hops: int = 3
    parent_target_tokens: int = 1024

    def validate(self):
        if any(type(value) is not int for value in asdict(self).values()):
            raise ValueError("Research controls must be integers, not booleans or estimates")
        if not (1 <= self.seeds <= min(20, self.candidate_depth) and self.candidate_depth <= 32):
            raise ValueError("Common seeds must be 1..20 and no greater than candidate depth <= 32")
        if not (2048 <= self.context_ceiling <= 32768 and 1 <= self.graph_hops <= 3):
            raise ValueError("Invalid common context or graph controls")
        if self.parent_target_tokens != 1024:
            raise ValueError("This registered fixed-parent baseline targets 1024 tokens")


class BenchmarkUnavailable(RuntimeError):
    """A controlled component is missing; do not silently change the experiment."""


def fit_prompt(question: str, values: list, marks: int, cap: int) -> dict:
    """Pure production prompt wrapper; no config/app/model/database imports."""
    from generation.provider_prompt import prepare_prompt
    from generation.types import AnswerFormat
    prepared = prepare_prompt(question, values, [], workspace="student", task="answer",
                              answer_format=AnswerFormat.coerce(marks), context_tokens=cap)
    content = prepared.messages[-1]["content"].split("\nSource data (JSON):\n", 1)[1]
    return {"sources": prepared.sources, "messages": prepared.messages,
            "context_text": content, "context_format": "jsonl_evidence", "warnings": prepared.warnings}


def source_fingerprint() -> dict:
    root = Path(__file__).resolve().parents[1]
    names = ("evaluation/research_retrieval.py", "chat/rag.py", "graph/service.py",
             "generation/provider_prompt.py", "generation/query_router.py",
             "generation/reranking.py", "generation/topic_context.py")
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}


def freeze_router(router: Callable) -> Callable:
    """Freeze one routing decision per exact question for one comparison run.

    Reuse this wrapper/factory instance across all arms. The production router's
    expiring cache is not an experimental control. Copies prevent callers from
    mutating the stored decision; the hash identifies its exact original fields.
    """
    snapshots = {}
    lock = asyncio.Lock()

    async def frozen(question):
        async with lock:
            if question not in snapshots:
                decision = await router(question)
                payload = json.dumps(decision, sort_keys=True, separators=(",", ":"), allow_nan=False)
                snapshots[question] = json.dumps({**json.loads(payload),
                    "routing_snapshot_sha256": hashlib.sha256(payload.encode()).hexdigest(),
                    "routing_control": "immutable_per_run_question_snapshot"}, allow_nan=False)
            return json.loads(snapshots[question])

    return frozen


def fuse_graph(primary: list, graph: list) -> list:
    """Same 0.5/0.5, k=60 rank formula as generation.service, preserving cosine."""
    primary, graph = _unique(primary), _unique(graph)
    by_id = {str(item.chunk_id): item for item in primary}
    primary_rank = {str(item.chunk_id): i + 1 for i, item in enumerate(primary)}
    graph_rank = {str(item.chunk_id): i + 1 for i, item in enumerate(graph)}
    for item in graph:
        key = str(item.chunk_id)
        if key in by_id:
            by_id[key] = replace(by_id[key], **{name: getattr(item, name, None) for name in (
                "knowledge_graph_path", "knowledge_graph_hops", "knowledge_graph_predicate", "knowledge_graph_quote")})
        else:
            by_id[key] = item
    result = [replace(item, fusion_score=(.5 / (60 + primary_rank[key]) if key in primary_rank else 0)
                      + (.5 / (60 + graph_rank[key]) if key in graph_rank else 0)) for key, item in by_id.items()]
    return sorted(result, key=lambda item: (-item.fusion_score,
                  min(primary_rank.get(str(item.chunk_id), 1000), graph_rank.get(str(item.chunk_id), 1000)), str(item.chunk_id)))


def _unique(items: list) -> list:
    by_id = {}
    for item in items:
        by_id.setdefault(str(item.chunk_id), item)
    return list(by_id.values())


async def compare(db, owner: str, question: str, marks: int, system: str, *,
                  functions: dict, controls: Controls = Controls(),
                  token_counter: Callable[[str], int] | None = None,
                  tokenizer_identity: str | None = None) -> dict:
    """No gold/reference/rubric parameter: runtime receives the public query only.

    All DocuMind arms run the same base/structure/router stages. The router may
    suppress KG search; it never suppresses the common base search in this
    controlled composition. This differs from production's graph-only routing.
    Table/visual/15-mark neighbor extras are OFF in every arm, not selectively.
    """
    controls.validate()
    if system not in VARIANTS or type(marks) is not int or marks not in (5, 10, 15):
        raise ValueError("Unknown system or academic marks")
    if not isinstance(question, str) or not question.strip() or not owner:
        raise ValueError("Question and owner scope are required")
    if token_counter is not None and not tokenizer_identity:
        raise ValueError("Exact context counter needs a frozen tokenizer identity")
    selected = VARIANTS[system]
    started = time.perf_counter()
    trace = []
    record = {"system_id": system, "question": question, "marks": marks,
              "pipeline_version": "controlled-text-composition-v1", "source_sha256": source_fingerprint(),
              "mode": "controlled_text_composition", "controls": asdict(controls),
              "component_flags": dict(selected), "status": "blocked", "trace": trace,
              "production_equivalent": False, "source_mapping": "not_supplied",
              "limitations": ["Common table, visual and 15-mark neighbor enrichments are disabled.",
                              "Common base retrieval runs even when the router predicts graph-only.",
                              "No canonical evidence mapping or independent labels are inferred from chunk IDs."]}
    record["configuration_sha256"] = hashlib.sha256(json.dumps({
        "system": system, "flags": selected, "marks": marks, "controls": asdict(controls),
        "tokenizer_identity": tokenizer_identity, "sources": record["source_sha256"],
    }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    try:
        await functions["readonly"](db)
        trace.append({"stage": "read_only_exact_search", "status": "ready"})
        base_name = "hybrid" if selected["hybrid"] else "dense"
        values = _unique(await functions[base_name](db, owner, question, controls.candidate_depth))
        trace.append({"stage": base_name, "chunk_ids": [str(c.chunk_id) for c in values]})
        if selected["structure"]:
            values = _unique(await functions["structure"](db, owner, question, values, controls.candidate_depth))
            trace.append({"stage": "structure", "chunk_ids": [str(c.chunk_id) for c in values]})
        decision = {"path": "both", "source": "registered_graph_baseline"}
        if selected["structure"]:
            decision = await functions["route"](question)
            if decision.get("path") not in ("semantic", "graph", "both"):
                raise BenchmarkUnavailable("invalid_router_decision")
            trace.append({"stage": "route", **decision})
            record["routing_snapshot_sha256"] = decision.get("routing_snapshot_sha256")
        if selected["graph"]:
            status = await functions["graph_status"](db, owner)
            trace.append({"stage": "graph_readiness", "status": status})
            if status != "ready":
                raise BenchmarkUnavailable("complete_graph_snapshot_required")
            if decision["path"] != "semantic":
                graph = _unique(await functions["graph"](db, owner, question, controls.candidate_depth, controls.graph_hops))
                values = fuse_graph(values, graph)[:controls.candidate_depth]
                trace.append({"stage": "graph", "chunk_ids": [str(c.chunk_id) for c in graph]})
        reranked, state = await functions["rerank"](question, values[:controls.candidate_depth], controls.seeds)
        trace.append({"stage": "rerank", **state})
        if state.get("status") != "ready" and values:
            raise BenchmarkUnavailable("common_reranker_not_ready")
        values = _unique(reranked)[:controls.seeds]
        if selected["topic"]:
            values, coverage = await functions["topic"](db, owner, values)
            trace.append({"stage": "topic", **coverage})
        elif selected["parent"]:
            values, coverage = await functions["parent"](db, owner, values, controls.parent_target_tokens)
            trace.append({"stage": "fixed_parent", **coverage})
        values = _unique(values)
        cap = min(controls.context_ceiling, {5: 8192, 10: 12288, 15: 16384}[marks])
        prepared = functions["fit"](question, values, marks, cap)
        count = None
        prompt_proxy_tokens = None
        budget_status = "byte_estimated_production_fitter; full_prompt_tokens_not_measured"
        if token_counter is not None:
            # Count actual question/system content, not a fixed guessed 512-token
            # allowance. JSON message-envelope counting +32 is still a proxy for
            # provider chat serialization, explicitly NOT an exact full-window
            # claim. Exact context-only ECT uses the original JSONL separately.
            input_cap = cap - {5: 320, 10: 640, 15: 1024}[marks] - 256
            budget_status = "serialized_message_proxy_plus_32; provider_chat_template_unverified"
            while True:
                count = token_counter(prepared["context_text"])
                if type(count) is not int or count < 0 or (prepared["context_text"] and count == 0):
                    raise ValueError("Invalid exact context token count")
                messages = prepared.get("messages") or [{"role": "user", "content":
                    question + "\nSource data:\n" + prepared["context_text"]}]
                prompt_proxy_tokens = token_counter(json.dumps(messages, ensure_ascii=False, separators=(",", ":")))
                if type(prompt_proxy_tokens) is not int or prompt_proxy_tokens <= 0:
                    raise ValueError("Invalid serialized prompt proxy token count")
                if prompt_proxy_tokens + 32 <= input_cap:
                    break
                previous_size = len(prepared["sources"])
                values = list(prepared["sources"])[:-1]
                if not values:
                    raise BenchmarkUnavailable("no_source_fits_exact_context_budget")
                prepared = functions["fit"](question, values, marks, cap)
                if len(prepared["sources"]) >= previous_size:
                    raise BenchmarkUnavailable("prompt_fitter_did_not_reduce_sources")
        trace.append({"stage": "prompt_fit", "marks": marks, "context_ceiling": cap,
                      "supplied_chunk_ids": [str(c.chunk_id) for c in prepared["sources"]]})
        record.update(status="measured_retrieval_only", context_text=prepared["context_text"],
                      context_format=prepared.get("context_format", "plain"),
                      context_tokens=count, tokenizer_identity=tokenizer_identity,
                      prompt_budget_status=budget_status, serialized_prompt_proxy_tokens=prompt_proxy_tokens,
                      token_count_status="exact_caller_counter" if token_counter else "not_measured",
                      warnings=prepared.get("warnings", []), messages=prepared.get("messages", []),
                      excerpts=[{"chunk_id": str(c.chunk_id), "document_id": str(c.document_id),
                                 "page": c.page, "text": c.content, "context_source": index}
                                for index, c in enumerate(prepared["sources"], 1)],
                      answer=None, human_grading="not_measured")
    except BenchmarkUnavailable as exc:
        record.update(reason=str(exc), context_text="", excerpts=[], answer=None)
    record["retrieval_ms"] = (time.perf_counter() - started) * 1000
    return record


def production_functions() -> dict:
    """Explicit lazy bindings. Never imports main or starts migrations/lifespan.

    SQL is owner-scoped and SELECT-only. The caller must first begin its own
    READ ONLY transaction. Missing tables/models cause an error, never new setup.
    Reuse ONE returned dictionary across all systems/questions in a comparison
    run so routing snapshots cannot expire or change between ablation arms.
    """
    from sqlalchemy import text
    from chat.rag import SourceChunk, retrieve_chunks, retrieve_hybrid_chunks, retrieve_dual_path
    from graph.service import retrieve_knowledge_graph_candidates
    from generation.reranking import rerank_candidates
    from generation.topic_context import expand_topic_context
    from generation.query_router import route_query

    async def readonly(db):
        if (await db.execute(text("SELECT current_setting('transaction_read_only')"))).scalar_one() != "on":
            raise BenchmarkUnavailable("caller_session_must_be_read_only")
        await db.execute(text("SELECT set_config('enable_indexscan','off',true)"))

    async def dense(db, owner, question, depth):
        return await retrieve_chunks(db, owner, question, top_k=depth, iterative_scan=False)

    async def hybrid(db, owner, question, depth):
        return await retrieve_hybrid_chunks(db, owner, question, top_k=depth, candidate_limit=depth)

    async def structure(db, owner, question, values, depth):
        return await retrieve_dual_path(db, owner, question, top_k=depth, semantic_chunks=values)

    async def graph_status(db, owner):
        # Production's account status treats a PARTIAL graph as available. A
        # controlled ready-graph experiment requires all indexed sources ready.
        row = (await db.execute(text("""SELECT count(*) AS total,
            count(*) FILTER (WHERE g.status='ready') AS ready
            FROM documents d LEFT JOIN kg_extraction_status g
            ON g.document_id=d.id AND g.user_id=d.user_id
            WHERE d.user_id=CAST(:owner AS uuid) AND d.embedding_status='ready'"""), {"owner": owner})).one()
        return "ready" if row.total > 0 and row.total == row.ready else "incomplete_or_missing"

    async def graph(db, owner, question, depth, hops):
        rows = await retrieve_knowledge_graph_candidates(db, owner, question, max_hops=hops, max_candidates=depth)
        return [SourceChunk(item.chunk_id, item.content, 0., item.document_id, item.document_name,
                    item.page, heading_path=item.heading_path, section=item.section,
                    retrieval_path="knowledge_graph", knowledge_graph_path=item.graph_path,
                    knowledge_graph_hops=item.hops, knowledge_graph_predicate=item.predicate,
                    knowledge_graph_quote=item.evidence_quote) for item in rows]

    async def route(question):
        return asdict(await route_query(question))

    async def rerank(question, values, seeds):
        return await rerank_candidates(question, values, top_k=seeds)

    async def parent(db, owner, values, target):
        ids = [str(c.chunk_id) for c in values if getattr(c, "evidence_kind", "chunk") == "chunk"]
        if len(ids) != len(values):
            raise BenchmarkUnavailable("fixed_parent_requires_chunk_seeds")
        if not ids:
            return [], {"status": "empty"}
        result = await db.execute(text("""WITH requested AS (
          SELECT value::uuid id FROM jsonb_array_elements_text(CAST(:ids AS jsonb))
        ), owned AS (
          SELECT c.id,c.document_id,c.chunk_index,c.content,c.page,c.token_count,
            d.name AS document_name,
            sum(c.token_count) OVER (PARTITION BY c.document_id ORDER BY c.chunk_index,c.id
                 ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)-c.token_count AS token_start,
            count(*) FILTER (WHERE c.token_count IS NULL OR c.token_count<=0)
                 OVER (PARTITION BY c.document_id) AS missing_tokens
          FROM document_chunks c JOIN documents d ON d.id=c.document_id
          WHERE d.user_id=CAST(:owner AS uuid) AND c.document_id IN
            (SELECT p.document_id FROM document_chunks p JOIN requested r ON r.id=p.id)
        ), seeds AS (SELECT o.* FROM owned o JOIN requested r ON r.id=o.id)
        SELECT DISTINCT o.id,o.content,o.page,o.document_id,o.document_name,o.chunk_index,
               o.token_count,o.missing_tokens
        FROM owned o JOIN seeds s ON s.document_id=o.document_id
          AND floor(o.token_start/CAST(:target AS numeric))=floor(s.token_start/CAST(:target AS numeric))
        ORDER BY o.document_id,o.chunk_index,o.id"""), {"owner": owner, "ids": json.dumps(ids), "target": target})
        rows = result.mappings().all()
        if not rows or any(row["missing_tokens"] for row in rows):
            raise BenchmarkUnavailable("fixed_parent_token_metadata_missing")
        original = {str(c.chunk_id): c for c in values}
        expanded = [original.get(str(row["id"])) or SourceChunk(str(row["id"]), row["content"],
                    0., str(row["document_id"]), row["document_name"], row["page"],
                    token_count=row["token_count"]) for row in rows]
        return expanded, {"status": "ready", "target_tokens": target,
                          "policy": "fixed_document_token_start_buckets; indivisible children may cross target"}

    return {"readonly": readonly, "dense": dense, "hybrid": hybrid, "structure": structure,
            "graph_status": graph_status, "graph": graph, "route": freeze_router(route), "rerank": rerank,
            "topic": expand_topic_context, "parent": parent, "fit": fit_prompt}


async def self_check() -> None:
    """Synthetic wiring only: no neural scores, database or benchmark claims."""
    @dataclass
    class Chunk:
        chunk_id: str
        content: str
        document_id: str = "fixture"
        page: int = 1
        fusion_score: float = 0.
        knowledge_graph_path: str | None = None
        knowledge_graph_hops: int | None = None
        knowledge_graph_predicate: str | None = None
        knowledge_graph_quote: str | None = None
    chunks = [Chunk("base", "Source base."), Chunk("structure", "Structure evidence."),
              Chunk("graph", "Graph evidence."), Chunk("topic", "Topic tail."), Chunk("parent", "Other parent text.")]
    calls = []
    async def readonly(db): calls.append("readonly")
    async def base(*args): return chunks[:1]
    async def structure(db, owner, question, values, depth): return values + chunks[1:2]
    async def graph(*args): calls.append("graph"); return chunks[2:3]
    async def status(*args): return "ready"
    route_calls = []
    async def route(question):
        route_calls.append(question)
        return {"path": "both", "source": "synthetic_fixture"}
    async def rerank(question, values, seeds): return values[:seeds], {"status": "ready"}
    async def topic(db, owner, values): return values + chunks[3:4], {"status": "complete"}
    async def parent(db, owner, values, target): return values + chunks[4:5], {"status": "ready"}
    def fit(question, values, marks, cap):
        return {"sources": values, "context_text": "\n".join(c.content for c in values), "messages": []}
    functions = {"readonly": readonly, "dense": base, "hybrid": base, "structure": structure,
        "graph_status": status, "graph": graph, "route": freeze_router(route), "rerank": rerank,
        "topic": topic, "parent": parent, "fit": fit}
    rows = {}
    for system in VARIANTS:
        calls.clear()
        rows[system] = await compare(None, "fixture-owner", "Question?", 10, system, functions=functions)
        assert rows[system]["status"] == "measured_retrieval_only"
        assert rows[system]["token_count_status"] == "not_measured"
        if not VARIANTS[system]["graph"]:
            assert "graph" not in calls
    ids = lambda system: {e["chunk_id"] for e in rows[system]["excerpts"]}
    assert ids("documind_full") - ids("documind_no_topic") == {"topic"}
    assert ids("documind_full") - ids("documind_no_graph") == {"graph"}
    assert route_calls == ["Question?"]
    assert len({rows[name]["routing_snapshot_sha256"] for name in (
        "documind_full", "documind_no_graph", "documind_no_topic")}) == 1
    assert ids("parent") == {"base", "parent"}
    assert len(fuse_graph(chunks[:1] * 2, chunks[:1] * 2)) == 1
    for marks, expected in ((5, 8192), (10, 12288), (15, 16384)):
        row = await compare(None, "fixture-owner", "Question?", marks, "dense", functions=functions)
        assert row["trace"][-1]["context_ceiling"] == expected
    async def missing(*args): return "partial"
    blocked = await compare(None, "fixture-owner", "Question?", 10, "graph", functions={**functions, "graph_status": missing})
    assert blocked["status"] == "blocked" and blocked["reason"] == "complete_graph_snapshot_required"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("self-check", "configs"))
    args = parser.parse_args()
    if args.command == "configs":
        print(json.dumps({"mode": "controlled_text_composition", "production_equivalent": False,
                          "systems": VARIANTS, "controls": asdict(Controls())}, indent=2))
    else:
        asyncio.run(self_check())
        print("Seven-adapter synthetic wiring check passed; no neural or research-quality result measured.")


if __name__ == "__main__":
    main()
