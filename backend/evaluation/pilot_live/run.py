"""Explicit isolated PostgreSQL pilot index and read-only seven-arm diagnostics.

Never creates/drops databases or runs migrations. DATABASE_AGENT must provision
the named, marked research target first. Only the selected open textbook pages
are imported; gold questions/rubrics/evidence never enter the search index.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import gzip
from difflib import SequenceMatcher
import json
import os
import re
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "evaluation/pilot_v1/dataset.json"
TARGET = "documind_pilot_20261101"
MARKER = "documind-isolated-pilot-20261101"
OWNER = uuid.uuid5(uuid.NAMESPACE_URL, MARKER + "/owner")


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_new(path: Path, value: dict) -> None:
    payload = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    if path.suffix == ".gz":
        payload = gzip.compress(payload, mtime=0)
    with path.open("xb") as stream:
        stream.write(payload)


def load_data() -> dict:
    from evaluation.research_scoring import validate_dataset
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    validate_dataset(data)
    return data


def elements_for(doc: dict):
    """Page/paragraph import, using source headings rather than gold annotations."""
    from documents.processing import ExtractedElement
    elements, origins, heading = [], [], []
    for page in doc["pages"]:
        text = page["canonical_text"]
        for match in re.finditer(r"\S(?:.*?\S)?(?=\n\n|\Z)", text, re.DOTALL):
            content = match.group()
            is_heading = bool(re.fullmatch(r"\d{1,2}\.\d{1,2} [^\n]{2,120}", content))
            if is_heading:
                heading = [content]
            elements.append(ExtractedElement(content, "heading" if is_heading else "paragraph", page["page"],
                heading_level=1 if is_heading else None, heading_path=list(heading),
                section=heading[-1] if heading else None))
            origins.append({"document_id": doc["id"], "page": page["page"],
                            "start_char": match.start(), "end_char": match.end()})
    return elements, origins


def make_plan(data: dict) -> tuple[list, dict]:
    """Create real structure-v2 children plus exact immutable character mappings."""
    from documents.chunking import chunk_elements
    from tokenization import is_tokenizer_available
    if not is_tokenizer_available():
        raise ValueError("Pinned embedding tokenizer required; approximate chunk budgets are forbidden for this study")
    indexed, maps = [], {}
    for doc in data["documents"]:
        doc_id = uuid.uuid5(OWNER, doc["id"] + doc["raw_file_sha256"])
        elements, origins = elements_for(doc)
        chunks = chunk_elements(elements, version="structure-v2")
        pages = {p["page"]: p["canonical_text"] for p in doc["pages"]}
        planned = []
        for index, chunk in enumerate(chunks):
            indices = chunk.meta.source_indices
            if not indices:
                raise ValueError("A chunk lacks source provenance")
            first, last = origins[indices[0]], origins[indices[-1]]
            if first["page"] != last["page"]:
                raise ValueError("A chunk crosses canonical pages without a mapping")
            start = first["start_char"] + (chunk.meta.source_start or 0)
            end = first["start_char"] + chunk.meta.source_end if chunk.meta.exact else last["end_char"]
            body = pages[first["page"]][start:end]
            if not body or not chunk.content.endswith(body):
                raise ValueError("Chunk text does not preserve its canonical source body")
            cid = uuid.uuid5(doc_id, f"chunk/{index}")
            maps[str(cid)] = {**first, "start_char": start, "end_char": end,
                "content": chunk.content, "body_offset": len(chunk.content) - len(body),
                "source_sha256": doc["raw_file_sha256"], "kind": "chunk"}
            planned.append((cid, index, chunk))
        indexed.append((doc, doc_id, elements, origins, planned))
    return indexed, maps


def map_record(record: dict, mapping: dict, documents: dict) -> dict:
    """Map only actual returned content to exact source intervals; never use gold."""
    mapped, partial = [], []
    for excerpt in record.get("excerpts", []):
        origin = mapping.get(str(excerpt["chunk_id"]))
        if origin is None:
            raise ValueError("Returned source has no frozen index mapping")
        supplied, original = excerpt["text"], origin["content"]
        offset = original.find(supplied)
        if offset >= 0 and original.find(supplied, offset + 1) >= 0:
            partial.append({"chunk_id": excerpt["chunk_id"], "reason": "ambiguous_fitted_fragment_no_credit"})
            continue
        if offset >= 0:
            fragments = [(offset, len(supplied))]
        else:
            # The production fitter can join retained sentences with spaces.
            # Credit only literal monotonic source fragments, never fill the
            # changed whitespace/omitted words between them. Consequently RER
            # is a conservative lower bound for these explicitly flagged rows.
            fragments = [(block.a, block.size) for block in SequenceMatcher(None, original, supplied,
                          autojunk=False).get_matching_blocks() if block.size >= 8]
            partial.append({"chunk_id": excerpt["chunk_id"], "reason": "fitter_changed_text_exact_fragments_only"})
        for offset, length in fragments:
            lo = max(offset, origin["body_offset"])
            hi = min(offset + length, origin["body_offset"] + origin["end_char"] - origin["start_char"])
            if lo >= hi:
                continue  # a heading prefix alone cannot claim its missing paragraph
            start = origin["start_char"] + lo - origin["body_offset"]
            end = origin["start_char"] + hi - origin["body_offset"]
            doc = documents[origin["document_id"]]
            page = next(p for p in doc["pages"] if p["page"] == origin["page"])
            text = page["canonical_text"][start:end]
            if text not in supplied:
                raise ValueError("Source mapping would credit text the provider did not receive")
            mapped.append({"document_id": origin["document_id"], "page": origin["page"],
                "start_char": start, "end_char": end, "text": text,
                "source_sha256": origin["source_sha256"], "context_source": excerpt["context_source"]})
    return {**record, "excerpts": mapped, "mapping_caveats": partial,
            "source_mapping": "exact_fragment_lower_bound" if partial else "verified_canonical_intervals_v1"}


def register_models():
    # ORM registration only: no app import, lifespan, schema creation or migrations.
    import auth.models, documents.models, chat.models, verification.models, reliability.models, user.models, graph.models  # noqa:F401


async def connect():
    from sqlalchemy import text
    from sqlalchemy.engine import make_url
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from config import get_settings
    raw = os.environ.get("DOCUMIND_PILOT_DATABASE_URL", "")
    if not raw:
        raise ValueError("DATABASE_AGENT must explicitly supply DOCUMIND_PILOT_DATABASE_URL")
    target, production = make_url(raw), make_url(get_settings().database_url)
    if target.database != TARGET or target.host not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("Only the fixed local isolated research database is accepted")
    if production.database == TARGET:
        raise ValueError("Research target must differ from the product database")
    engine = create_async_engine(raw, pool_pre_ping=True)
    async with engine.connect() as db:
        actual, marker, revision = (await db.execute(text("""SELECT current_database(),
            shobj_description((SELECT oid FROM pg_database WHERE datname=current_database()), 'pg_database'),
            (SELECT version_num FROM alembic_version)"""))).one()
        if actual != TARGET or marker != MARKER or revision != "018":
            await engine.dispose()
            raise ValueError("Research target lacks the owner-provisioned marker or migration 018")
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def seed(output: Path):
    if output.exists() or output.suffix != ".json":
        raise ValueError("Seed manifest requires a new .json path before indexing")
    from sqlalchemy import select
    register_models()
    from auth.models import User
    from documents.models import Document, DocumentChunk
    from documents.parser import parse_extracted_elements
    from documents.structure import replace_document_structure
    from graph.service import ChunkView, replace_document_graph
    from embeddings.model import embed_texts, get_embedding_descriptor
    data = load_data()
    indexed, mapping = make_plan(data)
    engine, sessions = await connect()
    try:
        async with sessions() as db:
            if await db.scalar(select(User.id).limit(1)) is not None:
                raise ValueError("Seed requires a completely fresh research database; no replacement is allowed")
            db.add(User(id=OWNER, email="pilot-20261101@research.invalid", name="Isolated OpenStax pilot",
                        hashed_password="!research-only-disabled-login", is_active=False))
            await db.flush()
            descriptor = get_embedding_descriptor()
            for doc, did, elements, origins, planned in indexed:
                db.add(Document(id=did, user_id=OWNER, name=doc["title"], file_type="pdf",
                    file_size=sum(len(p["canonical_text"].encode()) for p in doc["pages"]),
                    stored_path="research-canonical://" + doc["id"], content_hash=doc["raw_file_sha256"],
                    parser_version="pilot-canonical-paragraph-v1", chunker_version="structure-v2",
                    embedding_model=descriptor["identityKey"], chunk_count=len(planned), status="ready", embedding_status="ready"))
                await db.flush()
                vectors = await asyncio.to_thread(embed_texts, [c.content for _, _, c in planned])
                for (cid, index, chunk), vector in zip(planned, vectors, strict=True):
                    db.add(DocumentChunk(id=cid, document_id=did, chunk_index=index, content=chunk.content,
                        page=chunk.meta.page, heading_path=list(chunk.meta.heading_path) or None, section=chunk.meta.section,
                        element_type=chunk.meta.element_type, chunker_version=chunk.meta.chunker_version,
                        token_count=chunk.meta.token_count, source_element_indices=list(chunk.meta.source_indices), embedding=vector))
                await db.flush()
                parsed = parse_extracted_elements(elements, page_count=doc["raw_pdf_page_count"], source="research-canonical://" + doc["id"])
                persisted = await replace_document_structure(db, did, parsed)
                for element, origin in zip(parsed.elements, origins, strict=True):
                    row = persisted[element.source_id]
                    mapping[str(row.id)] = {**origin, "content": element.content, "body_offset": 0,
                        "source_sha256": doc["raw_file_sha256"], "kind": "structure_element"}
                await replace_document_graph(db, did, [ChunkView(str(cid), index, c.meta.page, c.meta.heading_path) for cid,index,c in planned])
            manifest = {"schema_version": "documind-isolated-pilot-index-v1", "database": TARGET,
                "database_marker": MARKER, "owner_id": str(OWNER), "dataset_sha256": digest(DATASET.read_bytes()),
                "embedding": descriptor, "documents": [str(item[1]) for item in indexed], "source_map": mapping,
                "index_policy": "canonical development pages; deterministic paragraph/heading import; production structure-v2 children",
                "human_review": "not_measured", "gold_used_for_indexing": False,
                "runner_source_sha256": digest(Path(__file__).read_bytes())}
            # Reserve output before commit; an existing artifact prevents mutation.
            with output.open("x", encoding="utf-8") as stream:
                await db.commit()
                json.dump(manifest, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write("\n")
        print(json.dumps({"status": "isolated_index_seeded", "chunks": sum(len(x[4]) for x in indexed), "mapping_entries": len(mapping)}))
    finally:
        await engine.dispose()


async def graph_batch():
    from sqlalchemy import select
    register_models()
    from documents.models import Document, DocumentChunk
    from documents.kg_extraction import replace_document_knowledge_graph
    from graph.models import KnowledgeGraphExtraction
    engine, sessions = await connect()
    try:
        async with sessions() as db:
            docs = (await db.execute(select(Document).where(Document.user_id == OWNER))).scalars().all()
            for doc in docs:
                chunks = (await db.execute(select(DocumentChunk).where(DocumentChunk.document_id == doc.id).order_by(DocumentChunk.chunk_index))).scalars().all()
                await replace_document_knowledge_graph(db, user_id=OWNER, document_id=doc.id, chunks=chunks, resume=True)
            await db.commit()
            rows = (await db.execute(select(KnowledgeGraphExtraction).where(KnowledgeGraphExtraction.user_id == OWNER))).scalars().all()
            print(json.dumps([{"status":r.status,"processed":r.processed_chunk_count,"failure":r.failure_code} for r in rows]))
    finally:
        await engine.dispose()


async def status(output: Path):
    from sqlalchemy import text
    engine, sessions = await connect()
    try:
        async with sessions() as db:
            await db.execute(text("SET TRANSACTION READ ONLY"))
            counts = (await db.execute(text("""SELECT count(*) AS chunks,
                count(*) FILTER (WHERE jsonb_array_length(CASE WHEN jsonb_typeof(heading_path::jsonb)='array'
                    THEN heading_path::jsonb ELSE '[]'::jsonb END)>0) AS heading_chunks,
                count(*) FILTER (WHERE section IS NOT NULL AND section<>'') AS section_chunks,
                count(*) FILTER (WHERE source_element_indices IS NOT NULL) AS paragraph_provenance_chunks
                FROM document_chunks"""))).mappings().one()
            structural = (await db.execute(text("SELECT element_type,count(*) AS count FROM document_structure_elements GROUP BY element_type"))).mappings().all()
            tables = {}
            for name in ("documents", "document_graph_edges", "document_structure_edges", "kg_entities", "kg_relations"):
                tables[name] = await db.scalar(text(f"SELECT count(*) FROM {name}"))  # fixed internal names only
            graph = (await db.execute(text("SELECT status,processed_chunk_count,failure_code,extractor_model,extractor_version FROM kg_extraction_status"))).mappings().all()
            extension = await db.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
            await db.rollback()
        value = {"database":TARGET,"dataset_sha256":digest(DATASET.read_bytes()),"chunk_metadata":dict(counts),
            "source_elements":[dict(row) for row in structural],"tables":tables,"graph":[dict(row) for row in graph],
            "pgvector_version":extension,"index_policy":"source paragraph/heading regex import; no gold topic labels used",
            "status":"development_index_readiness_not_scientific_validation"}
        write_new(output,value)
        print(json.dumps(value))
    finally:
        await engine.dispose()


async def benchmark(index_path: Path, output: Path, score_path: Path, systems: list[str] | None):
    from sqlalchemy import text
    from evaluation.research_retrieval import VARIANTS, compare, production_functions
    from evaluation.research_scoring import load_local_tokenizer, score_run
    register_models()
    data = load_data()
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if index["database"] != TARGET or index["dataset_sha256"] != digest(DATASET.read_bytes()):
        raise ValueError("Index mapping differs from this immutable pilot dataset")
    if output.exists() or score_path.exists():
        raise ValueError("Research outputs must be new paths")
    counter, tokenizer = load_local_tokenizer(ROOT / "evaluation/assets/gpt-oss-tokenizer", "openai/gpt-oss-20b@6cee5e81ee83917806bbde320786a8fb61efebee")
    functions = production_functions()
    # Warmup is outside retrieval timing and does not download any artifact.
    from generation.reranking import warm_reranker
    warmup = await warm_reranker()
    engine, sessions = await connect()
    rows, failures = [], []
    try:
        async with sessions() as db:
            await db.execute(text("SET TRANSACTION READ ONLY"))
            for question in data["questions"]:
                for system in systems or list(VARIANTS):
                    try:
                        record = await compare(db, str(OWNER), question["question"], question["designated_marks"], system,
                            functions=functions, token_counter=counter, tokenizer_identity=f"{tokenizer['model']}@{tokenizer['revision']}")
                        record["question_id"] = question["id"]
                        if record["status"] != "measured_retrieval_only":
                            failures.append({"question_id": question["id"], "system_id": system, "reason": record.get("reason")})
                        else:
                            record = map_record(record, index["source_map"], {d["id"]:d for d in data["documents"]})
                            rows.append(record)
                    except Exception as exc:
                        await db.rollback()
                        await db.execute(text("SET TRANSACTION READ ONLY"))
                        failures.append({"question_id":question["id"],"system_id":system,"error_type":type(exc).__name__})
                    print(json.dumps({"question":question["id"],"system":system,"measured":len(rows),"failures":len(failures)}), flush=True)
            await db.rollback()
        run = {"schema_version":"documind-isolated-pilot-run-v1", "annotation_status": data["status"],
            "mode":"controlled_text_composition_not_full_production", "index_manifest_sha256":digest(index_path.read_bytes()),
            "dataset_sha256":digest(DATASET.read_bytes()), "reranker_warmup":warmup,"records":rows,"failures":failures,
            "mapping_partial_records":sum(bool(row.get("mapping_caveats")) for row in rows),
            "mapping_partial_sources":sum(len(row.get("mapping_caveats",[])) for row in rows),
            "limitation":"Unreviewed development diagnostics only; exact fragment mapping is a conservative lower bound where fitting changed whitespace. No human grades, inferential statistics or improvement claim."}
        write_new(output, run)
        report = score_run(data, run, counter, tokenizer) if rows else {"status":"not_measured","failures":failures}
        report["failures"] = failures
        report["run_artifact_sha256"] = digest(output.read_bytes())
        report["mapping_partial_records"] = run["mapping_partial_records"]
        report["mapping_partial_sources"] = run["mapping_partial_sources"]
        write_new(score_path, report)
        print(json.dumps({"status":report["status"],"records":len(rows),"failures":len(failures)}))
    finally:
        await engine.dispose()


def main():
    from evaluation.research_retrieval import VARIANTS
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    seed_args=sub.add_parser("seed"); seed_args.add_argument("--output",type=Path,required=True)
    sub.add_parser("graph-batch")
    status_args=sub.add_parser("status"); status_args.add_argument("--output",type=Path,required=True)
    run_args=sub.add_parser("run")
    run_args.add_argument("--index",type=Path,required=True);run_args.add_argument("--output",type=Path,required=True)
    run_args.add_argument("--scores",type=Path,required=True);run_args.add_argument("--system",action="append",choices=tuple(VARIANTS))
    args=parser.parse_args()
    if args.command=="seed": asyncio.run(seed(args.output))
    elif args.command=="graph-batch": asyncio.run(graph_batch())
    elif args.command=="status": asyncio.run(status(args.output))
    else: asyncio.run(benchmark(args.index,args.output,args.scores,args.system))


if __name__ == "__main__":
    main()
