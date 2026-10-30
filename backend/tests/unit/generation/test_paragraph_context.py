"""Long unheaded paragraphs retain their original element membership."""
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from chat.rag import SourceChunk
from documents import routes
from documents.chunking import chunk_elements, CHUNKER_VERSION_STRUCTURE
from documents.processing import ExtractedElement
from generation.provider_prompt import prepare_prompt
from generation.topic_context import assemble_topic_context
from generation.types import AnswerFormat, GenerationUnavailableError


@pytest.mark.parametrize("words", [317, 500, 733])
def test_ingested_paragraph_membership_recovers_its_tail_without_neighbour_text(monkeypatch, words):
    from tests.conftest import _register_all_models
    _register_all_models()
    text = " ".join(f"calibration{i}" + ("." if i % 20 == 19 else "") for i in range(words))
    elements = [ExtractedElement(text, "paragraph", None),
                ExtractedElement("A separate unrelated paragraph describes battery disposal.", "paragraph", None)]
    monkeypatch.setattr(routes, "chunk_elements", lambda values, **kw: chunk_elements(
        values, count_tokens=lambda value: len(value.split()), max_tokens=100,
        target_tokens=80, min_tokens=10, overlap_tokens=0, **kw))
    chunks = routes._build_chunk_objects(elements, uuid4(), CHUNKER_VERSION_STRUCTURE,
                                         SimpleNamespace(add=lambda _: None))
    paragraph = [c for c in chunks if c.source_element_indices == [0]]
    assert len(paragraph) >= 4
    assert chunks[-1].source_element_indices == [1]
    total = sum(len(c.content.encode()) for c in paragraph)
    first = paragraph[0]
    seed = SourceChunk(str(first.id), first.content, .8, str(first.document_id), "notes.txt", None)
    rows = [dict(seed_id=str(first.id), id=str(c.id), chunk_index=c.chunk_index,
                 content=c.content, page=None, heading_path=None, section=None,
                 group_id="paragraph-0", context_kind="paragraph", total_bytes=total)
            for c in paragraph]
    expanded, coverage = assemble_topic_context([seed], rows)
    assert coverage["status"] == "complete"
    assert all(c.topic_context_kind == "paragraph" for c in expanded)
    supplied = prepare_prompt("Explain calibration", expanded, [], workspace="student", task="answer",
                              answer_format=AnswerFormat.FIFTEEN, context_tokens=16384)
    assert len(supplied.sources) == len(paragraph)
    assert all(not block.truncated for block in supplied.blocks)
    assert f"calibration{words - 1}" in supplied.sources[-1].content
    assert "battery disposal" not in " ".join(c.content for c in supplied.sources)
    assert any("larger topic boundaries are unknown" in w for w in supplied.warnings)


@pytest.mark.asyncio
async def test_unavailable_encoder_is_a_sanitized_search_unavailable_error(monkeypatch):
    from chat import rag
    def fail(_):
        raise RuntimeError("sensitive local model path")
    monkeypatch.setattr(rag, "embed_query", fail)
    db = SimpleNamespace(execute=AsyncMock())
    with pytest.raises(GenerationUnavailableError) as error:
        await rag.retrieve_chunks(db, "owner", "query")
    assert "sensitive" not in str(error.value)
    db.execute.assert_not_awaited()
