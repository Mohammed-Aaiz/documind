"""
RAG (Retrieval-Augmented Generation) orchestration for DocuMind.

Flow:
  User question → query embedding → pgvector retrieval → relevant chunks
  → QA model receives question + concatenated context → answer + evidence
"""

from dataclasses import dataclass
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from embeddings.model import embed_query
from chat.qa_model import answer_question, is_model_available


@dataclass
class SourceChunk:
    chunk_id: str
    content: str
    score: float
    document_id: str
    document_name: str
    page: int | None


@dataclass
class RagResult:
    answer: str
    confidence: float
    sources: list[SourceChunk]
    insufficient_context: bool
    context_used: str
    # Reliability evidence fields
    retrieval_scores: list[float]  # raw similarity scores from pgvector
    avg_retrieval_score: float     # mean of retrieval scores
    best_retrieval_score: float    # top chunk similarity
    factual_grounded: bool         # whether the answer span appears in context
    source_count: int              # number of sources retrieved
    unique_documents: int          # number of distinct source documents


async def retrieve_chunks(
    db: AsyncSession,
    user_id: str,
    query: str,
    top_k: int = 5,
) -> list[SourceChunk]:
    """Retrieve the most relevant chunks from the user's documents."""
    query_embedding = embed_query(query)
    emb_str = str(query_embedding)

    search_sql = text(
        f"SELECT"
        f"  dc.id as chunk_id,"
        f"  dc.content,"
        f"  dc.document_id,"
        f"  d.name as document_name,"
        f"  dc.page,"
        f"  1 - (dc.embedding <=> '{emb_str}'::vector) as similarity"
        f" FROM document_chunks dc"
        f" JOIN documents d ON d.id = dc.document_id"
        f" WHERE d.user_id = '{user_id}'"
        f"   AND d.embedding_status = 'ready'"
        f"   AND dc.embedding IS NOT NULL"
        f" ORDER BY dc.embedding <=> '{emb_str}'::vector"
        f" LIMIT {top_k}"
    )

    result = await db.execute(search_sql)
    rows = result.fetchall()

    return [
        SourceChunk(
            chunk_id=str(row.chunk_id),
            content=row.content,
            score=round(float(row.similarity), 4),
            document_id=str(row.document_id),
            document_name=row.document_name,
            page=row.page,
        )
        for row in rows
    ]


def build_context(chunks: list[SourceChunk], max_chars: int = 4000) -> str:
    """Build a context string from retrieved chunks, respecting a max char limit."""
    parts = []
    total = 0
    for chunk in chunks:
        if total + len(chunk.content) > max_chars:
            break
        parts.append(chunk.content)
        total += len(chunk.content)
    return "\n\n".join(parts)


def rag_answer(
    question: str,
    chunks: list[SourceChunk],
    relevance_threshold: float = 0.15,
) -> RagResult:
    """
    Run RAG: combine retrieved chunks into context, then use QA model.

    If no chunks are retrieved or the top chunk score is below the threshold,
    we flag insufficient context.
    """
    if not chunks:
        return RagResult(
            answer="",
            confidence=0.0,
            sources=[],
            insufficient_context=True,
            context_used="",
            retrieval_scores=[],
            avg_retrieval_score=0.0,
            best_retrieval_score=0.0,
            factual_grounded=False,
            source_count=0,
            unique_documents=0,
        )

    all_scores = [c.score for c in chunks]
    avg_score = sum(all_scores) / len(all_scores) if all_scores else 0.0
    best_score = max(all_scores) if all_scores else 0.0
    unique_docs = len({c.document_id for c in chunks})

    # Check if retrieved chunks are relevant enough
    if chunks[0].score < relevance_threshold:
        return RagResult(
            answer="",
            confidence=max(0.0, chunks[0].score),
            sources=chunks,
            insufficient_context=True,
            context_used="",
            retrieval_scores=all_scores,
            avg_retrieval_score=round(avg_score, 4),
            best_retrieval_score=round(best_score, 4),
            factual_grounded=False,
            source_count=len(chunks),
            unique_documents=unique_docs,
        )

    context = build_context(chunks)
    if not context.strip():
        return RagResult(
            answer="",
            confidence=0.0,
            sources=chunks,
            insufficient_context=True,
            context_used="",
            retrieval_scores=all_scores,
            avg_retrieval_score=round(avg_score, 4),
            best_retrieval_score=round(best_score, 4),
            factual_grounded=False,
            source_count=len(chunks),
            unique_documents=unique_docs,
        )

    # Run QA model
    qa_result = answer_question(question, context)
    answer = qa_result["answer"]
    # Clamp confidence to [0, 1] — raw scores can be slightly negative
    score = max(0.0, min(1.0, qa_result["score"]))

    # ------------------------------------------------------------------
    # Answerability gate: distinguish genuinely supported answers from
    # guesses based on superficially related context.
    #
    # Two real signals, no fabrication:
    #
    #   1. QA confidence: the model's own probability that its extracted
    #      span is correct. Supported answers score 0.39–0.89. Unsupported
    #      guesses score <0.11.
    #
    #   2. Retrieval score: how semantically similar the top chunk is to
    #      the question. Truly relevant context scores ≥0.50. Superficial
    #      matches (e.g. a year near a year-related question) score <0.20.
    #
    # An answer is flagged insufficient when BOTH signals are weak:
    # low QA confidence AND low retrieval — meaning the model extracted
    # a span from context that is only superficially related to the
    # question.
    #
    # This preserves low-confidence answers that ARE grounded (e.g.
    # definition questions where retrieval is high but the model extracts
    # a partial span).
    # ------------------------------------------------------------------

    # Factual grounding: check if the extracted answer span appears
    # in the retrieved context.
    factual_grounded = False
    if answer.strip():
        answer_lower = answer.strip().lower()
        context_lower = context.lower()
        factual_grounded = answer_lower in context_lower

    insufficient = not answer.strip() or (
        score < 0.30 and best_score < 0.50
    )

    return RagResult(
        answer=answer,
        confidence=score,
        sources=chunks,
        insufficient_context=insufficient,
        context_used=context,
        retrieval_scores=all_scores,
        avg_retrieval_score=round(avg_score, 4),
        best_retrieval_score=round(best_score, 4),
        factual_grounded=factual_grounded,
        source_count=len(chunks),
        unique_documents=unique_docs,
    )
