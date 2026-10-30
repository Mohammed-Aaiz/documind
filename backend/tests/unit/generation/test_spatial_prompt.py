"""Measured geometry is supplied to the reader inside the context budget."""
import json

from chat.rag import SourceChunk
from generation.provider_prompt import prepare_prompt, estimated_tokens
from generation.types import AnswerFormat


def test_prompt_contains_only_bounded_measured_spatial_metadata_and_exact_text():
    regions = [{"id": f"figure-{i}", "kind": "figure", "bbox": [.1, .2, .8, .6],
                "column": 1, "reading_order": i, "untrusted_extra": "SHOULD NOT ENTER PROMPT"}
               for i in range(8)]
    chunk = SourceChunk("c1", "Figure 1 shows the calibration reference rig beneath the sensor table.",
                        .9, "d1", "rig.pdf", 1, spatial_regions=regions)
    prepared = prepare_prompt("What is below the sensor table?", [chunk], [],
        workspace="student", task="answer", answer_format=AnswerFormat.FIVE, context_tokens=2048)
    data = json.loads(prepared.messages[-1]["content"].split("Source data (JSON):\n", 1)[1])
    assert data["text"] == chunk.content
    assert len(data["spatialRegions"]) == 4
    assert data["spatialRegions"][0]["bbox"] == [.1, .2, .8, .6]
    assert data["spatialRegions"][0]["reading_order"] == 0
    assert "untrusted_extra" not in data["spatialRegions"][0]
    assert sum(estimated_tokens(m["content"]) for m in prepared.messages) + prepared.max_tokens <= 2048


def test_spatial_metadata_over_budget_cannot_bypass_context_limit():
    oversized = [{"id": "x" * 20000, "kind": "figure", "bbox": [.1, .2, .8, .6]}]
    chunk = SourceChunk("c1", "This is an observed figure caption with enough exact text to form an evidence passage.",
                        .9, "d1", "rig.pdf", 1, spatial_regions=oversized)
    prepared = prepare_prompt("Which figure?", [chunk], [], workspace="student", task="answer",
        answer_format=AnswerFormat.FIVE, context_tokens=2048)
    assert not prepared.blocks and not prepared.sources
    assert sum(estimated_tokens(m["content"]) for m in prepared.messages) + prepared.max_tokens <= 2048
    assert "x" * 100 not in str(prepared.messages)
