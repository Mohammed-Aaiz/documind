"""Small, explicit student-RAG evaluation commands; no database writes.

Embedding comparisons never modify the application's vector space. Live runs
require an owner UUID and qrels containing that owner's existing chunk UUIDs.
The production variant may send a query to its configured Groq router. Generation
is opt-in because it additionally sends source excerpts to the Groq API.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import re
import statistics
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from evaluation.retrieval_metrics import ndcg_at_k, recall_at_k, reciprocal_rank

DEFAULT_DATASET = Path(__file__).with_name("datasets") / "student_rag_v1.json"


def load_dataset(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    queries = data.get("queries", [])
    ids = [str(q.get("id", "")) for q in queries]
    if not queries or any(not value for value in ids) or len(set(ids)) != len(ids):
        raise ValueError("Dataset requires queries with unique nonempty IDs")
    for query in queries:
        if not isinstance(query.get("question"), str) or not query["question"].strip():
            raise ValueError("Each query requires a nonempty question")
        if not isinstance(query.get("relevant_ids"), list):
            raise ValueError("Each query requires a relevant_ids list (empty for unanswerable)")
        rubric = query.get("keypoints", {})
        if not isinstance(rubric, dict) or any(
            str(mark) not in {"5", "10", "15"} or not isinstance(points, list)
            or any(not isinstance(point, str) or not point.strip() for point in points)
            for mark, points in rubric.items()
        ):
            raise ValueError("keypoints must map 5/10/15 to lists of nonempty phrases")
    return data


def retrieval_metrics(ids: list[str], relevant: list[str], k: int) -> dict:
    # No relevant evidence means retrieval recall is undefined, not a zero that
    # should penalize a retriever for a deliberately unanswerable question.
    return {"recall": recall_at_k(ids, relevant, k),
            "mrr": reciprocal_rank(ids, relevant),
            "ndcg": ndcg_at_k(ids, relevant, k)} if relevant else {}


def percentile(values: list[float], fraction: float) -> float | None:
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)] if values else None


def summarize(rows: list[dict]) -> dict:
    metrics = {name: statistics.mean(row[name] for row in rows if name in row)
               for name in ("recall", "mrr", "ndcg") if any(name in row for row in rows)}
    latency = [row["retrieval_ms"] for row in rows]
    answer_metrics = {}
    for marks in ("5", "10", "15"):
        answers = [row["answers"][marks] for row in rows if "answers" in row]
        if not answers:
            continue
        unsupported = [answer for answer in answers if answer["unanswerable_abstention"] is not None]
        coverage = [answer["keypoint_phrase_coverage"] for answer in answers if answer["keypoint_phrase_coverage"] is not None]
        times = [answer["generation_ms"] for answer in answers]
        answer_metrics[marks] = {"generation_p50_ms": percentile(times, .5), "generation_p95_ms": percentile(times, .95),
            "lexically_verified_fraction": statistics.mean(bool(answer["verification"]["verified"]) for answer in answers),
            "unanswerable_abstention_rate": statistics.mean(answer["unanswerable_abstention"] for answer in unsupported) if unsupported else None,
            "keypoint_phrase_coverage": statistics.mean(coverage) if coverage else None}
    return {**metrics, "queries": len(rows), "answerable_queries": sum("recall" in row for row in rows),
            "answers_by_marks": answer_metrics,
            "retrieval_p50_ms": percentile(latency, .5),
            "retrieval_p95_ms": percentile(latency, .95),
            "latency_note": "nearest-rank percentiles; small smoke datasets are not production latency evidence"}


def keypoint_coverage(answer: str, points: list[str]) -> float | None:
    normalize = lambda text: " ".join(re.findall(r"\w+", text.casefold()))
    return sum(normalize(point) in normalize(answer) for point in points) / len(points) if points else None


def compare_embeddings(data: dict, models: list[str], k: int, query_prefixes: dict | None = None) -> dict:
    import numpy as np
    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(4)
    corpus = data.get("corpus", [])
    if not corpus or len({item["id"] for item in corpus}) != len(corpus):
        raise ValueError("Embedding dataset requires a corpus with unique IDs")
    corpus_ids = [str(item["id"]) for item in corpus]
    if any(set(q["relevant_ids"]) - set(corpus_ids) for q in data["queries"]):
        raise ValueError("Embedding qrels reference IDs absent from corpus")
    results = {}
    for specification in models:
        if "=" not in specification:
            raise ValueError("Models use label=local_path_or_cached_HuggingFace_ID")
        label, source = specification.split("=", 1)
        if not label or not source or label in results:
            raise ValueError("Model labels and sources must be nonempty and labels unique")
        try:
            started = time.perf_counter()
            model = SentenceTransformer(source, local_files_only=True, device="cpu")
            loaded_ms = (time.perf_counter() - started) * 1000
            started = time.perf_counter()
            vectors = model.encode([item["text"] for item in corpus], normalize_embeddings=True,
                                   show_progress_bar=False, convert_to_numpy=True)
            corpus_ms = (time.perf_counter() - started) * 1000
            rows = []
            for query in data["queries"]:
                started = time.perf_counter()
                query_vector = model.encode((query_prefixes or {}).get(label, "") + query["question"], normalize_embeddings=True,
                                            show_progress_bar=False, convert_to_numpy=True)
                order = np.argsort(-(vectors @ query_vector), kind="stable")[:k]
                ids = [corpus_ids[int(index)] for index in order]
                rows.append({"id": query["id"], "retrieved_ids": ids,
                             "retrieval_ms": (time.perf_counter() - started) * 1000,
                             **retrieval_metrics(ids, query["relevant_ids"], k)})
            manifest = Path(source) / "documind_manifest.json"
            pin = json.loads(manifest.read_text(encoding="utf-8")) if manifest.is_file() else {}
            results[label] = {"status": "measured", "source": source,
                "query_prefix": (query_prefixes or {}).get(label, ""),
                "dimensions": int(vectors.shape[1]), "max_seq_length": model.max_seq_length,
                "revision": pin.get("revision") or getattr(getattr(getattr(model[0], "auto_model", None), "config", None), "_commit_hash", None),
                "normalized": True, "similarity": "cosine", "model_load_ms": loaded_ms,
                "corpus_encode_ms": corpus_ms, "summary": summarize(rows), "rows": rows}
            del model
        except (OSError, RuntimeError, ValueError) as exc:
            # Never download implicitly or imply an absent candidate was measured.
            results[label] = {"status": "unavailable", "source": source, "error_type": type(exc).__name__}
    return {"mode": "offline-embedding-comparison", "models": results,
            "limitations": "Synthetic smoke data unless replaced; no production embedding switch, reranker or generation is measured here."}


async def evaluate_pipeline(data: dict, owner: str, variants: list[str], k: int, generate: bool) -> dict:
    # Importing the app registers ORM models; its lifespan and migrations are not
    # started. Every evaluation transaction below is explicitly READ ONLY.
    import main  # noqa: F401
    from sqlalchemy import text
    from storage.database import async_session, engine
    from chat.rag import SourceChunk, retrieve_chunks, retrieve_hybrid_chunks
    from generation.service import answer_from_evidence, retrieve_evidence

    owner = str(uuid.UUID(owner))
    qrel_ids = {str(uuid.UUID(value)) for query in data["queries"] for value in query["relevant_ids"]}
    results = {}
    from generation.reranking import warm_reranker
    warmup = await warm_reranker() if any(v in variants for v in ("rerank", "production")) else None
    try:
        async with async_session() as db:
            await db.execute(text("SET TRANSACTION READ ONLY"))
            if qrel_ids:
                owned = set((await db.execute(text("""
                    SELECT c.id::text FROM document_chunks c JOIN documents d ON d.id=c.document_id
                    WHERE d.user_id=CAST(:owner AS uuid) AND c.id IN
                    (SELECT value::uuid FROM jsonb_array_elements_text(CAST(:ids AS jsonb)))
                """), {"owner": owner, "ids": json.dumps(sorted(qrel_ids))})).scalars())
                if owned != qrel_ids:
                    raise ValueError("Some qrels are missing or do not belong to the requested owner")
            for variant in variants:
                # An exact baseline stays exact after an ANN index is installed.
                await db.execute(text("SELECT set_config('enable_indexscan', :mode, true)"),
                                 {"mode": "off" if variant == "dense" else "on"})
                rows = []
                for query in data["queries"]:
                    started = time.perf_counter()
                    stage = {}
                    if variant == "dense":
                        sources = await retrieve_chunks(db, owner, query["question"], top_k=k)
                    elif variant == "hybrid":
                        sources = await retrieve_hybrid_chunks(db, owner, query["question"], top_k=k)
                    elif variant == "rerank":
                        from generation.reranking import rerank_candidates
                        candidates = await retrieve_hybrid_chunks(db, owner, query["question"], top_k=20)
                        sources, stage["reranker"] = await rerank_candidates(query["question"], candidates, top_k=k)
                    elif variant == "topic":
                        from generation.topic_context import expand_topic_context
                        candidates = await retrieve_hybrid_chunks(db, owner, query["question"], top_k=k)
                        sources, stage["topicContext"] = await expand_topic_context(db, owner, candidates)
                    elif variant == "graph":
                        from graph.service import retrieve_knowledge_graph_candidates
                        candidates = await retrieve_knowledge_graph_candidates(db, owner, query["question"], max_candidates=k)
                        sources = [SourceChunk(item.chunk_id, item.content, 0.0, item.document_id,
                                   item.document_name, item.page, heading_path=item.heading_path,
                                   section=item.section, retrieval_path="knowledge_graph",
                                   knowledge_graph_path=item.graph_path, knowledge_graph_hops=item.hops,
                                   knowledge_graph_predicate=item.predicate, knowledge_graph_quote=item.evidence_quote)
                                   for item in candidates]
                    else:
                        sources = await retrieve_evidence(db, owner, query["question"], top_k=k,
                                                          answer_format="15", query_routing=True)
                    ids = [str(item.chunk_id) for item in sources]
                    row = {"id": query["id"], "retrieved_ids": ids,
                           "retrieval_ms": (time.perf_counter() - started) * 1000,
                           **retrieval_metrics(ids, query["relevant_ids"], k),
                           "routing": {**getattr(sources, "routing", {}), **stage},
                           "expanded_evidence_recall": recall_at_k(ids, query["relevant_ids"], len(ids))
                           if query["relevant_ids"] else None}
                    if generate:
                        answers = {}
                        for marks in ("5", "10", "15"):
                            started = time.perf_counter()
                            supplied, answer = await answer_from_evidence(query["question"], sources, marks)
                            answers[marks] = {"generation_ms": (time.perf_counter() - started) * 1000,
                                "abstained": answer.abstained, "verification": answer.verification,
                                "supplied_sources": len(supplied), "warnings": answer.warnings,
                                "unanswerable_abstention": answer.abstained if not query["relevant_ids"] else None,
                                "keypoint_phrase_coverage": keypoint_coverage(answer.answer, query.get("keypoints", {}).get(marks, [])),
                                "coverage_note": "literal normalized phrase coverage; not an entailment or grading score",
                                "answer": answer.answer,
                                "model": answer.model}
                        row["answers"] = answers
                    rows.append(row)
                results[variant] = {"summary": summarize(rows), "rows": rows}
            await db.rollback()
    finally:
        await engine.dispose()
    return {"mode": "read-only-production-pipeline", "variants": results, "reranker_warmup": warmup,
            "llm_judge": "not measured", "human_grading": "not measured", "generation_enabled": generate}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("embeddings", "pipeline"):
        command = sub.add_parser(name)
        command.add_argument("--dataset", type=Path, default=DEFAULT_DATASET if name == "embeddings" else None,
                             required=name == "pipeline")
        command.add_argument("--output", type=Path, required=True, help="New report path; never overwritten")
        command.add_argument("--k", type=int, choices=range(1, 21), default=5)
    sub.choices["embeddings"].add_argument("--model", action="append", required=True,
        help="label=local_path_or_cached_ID; repeat for baseline and candidate. Never downloads.")
    sub.choices["embeddings"].add_argument("--query-prefix", action="append", default=[],
        help="label=prefix; apply the model's documented query instruction only to queries")
    live = sub.choices["pipeline"]
    live.add_argument("--owner", required=True)
    live.add_argument("--variant", choices=("dense", "hybrid", "rerank", "graph", "topic", "production"), action="append")
    live.add_argument("--generate", action="store_true", help="Send questions/evidence to Groq; evaluate all mark formats")
    sub.add_parser("self-check")
    args = parser.parse_args()
    if args.command == "self-check":
        assert retrieval_metrics(["b", "a"], ["a"], 2) == {"recall": 1.0, "mrr": .5, "ndcg": 1 / math.log2(3)}
        assert keypoint_coverage("Kinetic energy depends on mass.", ["kinetic energy", "angular momentum"]) == .5
        assert percentile([4, 1, 3, 2], .95) == 4
        print("production evaluation self-check passed")
        return
    if args.output.exists():
        parser.error("Output already exists; choose a new report path")
    data = load_dataset(args.dataset)
    prefixes = {}
    for item in getattr(args, "query_prefix", []):
        if "=" not in item:
            parser.error("Query prefixes use label=prefix")
        label, prefix = item.split("=", 1)
        if label not in {model.split("=", 1)[0] for model in args.model}:
            parser.error("Query prefix label must name one of the compared models")
        prefixes[label] = prefix
    report = compare_embeddings(data, args.model, args.k, prefixes) if args.command == "embeddings" else asyncio.run(
        evaluate_pipeline(data, args.owner, list(dict.fromkeys(args.variant or ["dense", "hybrid", "production"])), args.k, args.generate))
    report.update(dataset=str(args.dataset.resolve()), dataset_sha256=hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
                  dataset_version=data.get("version"), runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  observed_at=datetime.now(timezone.utc).isoformat(), k=args.k)
    with args.output.open("x", encoding="utf-8") as target:
        json.dump(report, target, indent=2)
    print(json.dumps({"report": str(args.output.resolve()), "mode": report["mode"]}))


if __name__ == "__main__":
    main()
