"""Phase 5 unit tests: table-row provenance serialization.

These exercise the pure mapping layers that carry a retrieved source into the
Reliability Center — ``brain.response._build_reliability`` (SourceRef → persisted
source dict) and ``reliability.routes.ReliabilitySourceRef`` (persisted dict →
API model).  No database, no HTTP.

The contract under test: a table-row source's ``evidenceKind`` / ``tableElementId``
/ ``rowIndex`` / ``headerRepeated`` / ``page`` / ``section`` / ``retrievalPath``
are copied verbatim from the persisted row's provenance and are never derived
from the row text; every other evidence kind keeps its established meaning and
simply has no table-row fields (``None``), so old records never break.
"""

from __future__ import annotations

import json

from brain.response import _build_reliability
from brain.types import EvidenceBundle, SourceRef
from reliability.routes import ReliabilitySourceRef

TABLE_ELEMENT_ID = "11111111-1111-5111-8111-111111111111"
SECTION = "5. Maintenance Schedule"

TABLE_ROW = SourceRef(
    chunk_id=f"table_row:{TABLE_ELEMENT_ID}:1",
    content=(
        "Component | Calibration Interval | Operating Range | Failure Threshold "
        "| Recommended Action\n"
        "Lidar Array LR-9 | 250 h | 0-80 m | > 2.5 mm error | Recalibrate on "
        "reference rig"
    ),
    score=0.0,
    document_id="doc-1",
    document_name="demo.pdf",
    page=4,
    heading_path=(SECTION,),
    section=SECTION,
    element_type="table",
    retrieval_path="structural",
    fusion_score=None,
    evidence_kind="table_row",
    table_element_id=TABLE_ELEMENT_ID,
    row_index=1,
    header_repeated=True,
)


def _bundle(*sources: SourceRef) -> EvidenceBundle:
    return EvidenceBundle(
        sources=list(sources),
        retrieval_scores=[s.score for s in sources],
    )


class TestBuildReliabilityTableRow:
    def test_table_row_provenance_is_serialized_verbatim(self):
        reliability = _build_reliability(_bundle(TABLE_ROW), insufficient=False)
        source = reliability["sources"][0]

        assert source["evidenceKind"] == "table_row"
        assert source["tableElementId"] == TABLE_ELEMENT_ID
        assert source["rowIndex"] == 1
        assert source["headerRepeated"] is True
        assert source["page"] == 4
        assert source["section"] == SECTION
        assert source["elementType"] == "table"
        assert source["retrievalPath"] == "structural"
        # A row carries no similarity and never an RRF score.
        assert source["relevanceScore"] == 0.0
        assert source["fusionScore"] is None

    def test_payload_is_json_serializable(self):
        reliability = _build_reliability(_bundle(TABLE_ROW), insufficient=False)
        # The persisted ``sources_json`` column requires a JSON-serialisable
        # payload; this must not raise.
        json.dumps(reliability["sources"])


class TestExistingKindsUnchanged:
    def test_chunk_source_has_no_table_provenance(self):
        chunk = SourceRef(
            chunk_id="c1",
            content="plain text",
            score=0.8,
            document_id="d",
            document_name="n",
            page=1,
        )
        reliability = _build_reliability(_bundle(chunk), insufficient=False)
        source = reliability["sources"][0]

        assert source["evidenceKind"] == "chunk"
        assert source["retrievalPath"] == "semantic"
        assert source["tableElementId"] is None
        assert source["rowIndex"] is None
        assert source["headerRepeated"] is None

    def test_structure_element_kind_and_section_are_preserved(self):
        element = SourceRef(
            chunk_id="structure:e1",
            content="heading text",
            score=0.0,
            document_id="d",
            document_name="n",
            page=2,
            heading_path=("A",),
            section="A",
            element_type="section",
            retrieval_path="structural",
            evidence_kind="structure_element",
        )
        reliability = _build_reliability(_bundle(element), insufficient=False)
        source = reliability["sources"][0]

        assert source["evidenceKind"] == "structure_element"
        assert source["section"] == "A"
        assert source["elementType"] == "section"
        assert source["tableElementId"] is None
        assert source["rowIndex"] is None
        assert source["headerRepeated"] is None


class TestReliabilitySourceRefBackwardCompatibility:
    def test_old_record_without_new_fields_is_accepted(self):
        """A record persisted before Phase 5 (no table/structure fields)."""
        old = ReliabilitySourceRef(
            id="c1",
            documentId="d",
            documentName="n",
            content="c",
            relevanceScore=0.5,
            page=None,
            status="UNRESOLVED",
            retrievalPath="semantic",
            evidenceKind="chunk",
        )
        assert old.evidenceKind == "chunk"
        assert old.section is None
        assert old.elementType is None
        assert old.tableElementId is None
        assert old.rowIndex is None
        assert old.headerRepeated is None

    def test_table_row_record_round_trips_exactly(self):
        ref = ReliabilitySourceRef(
            id=f"table_row:{TABLE_ELEMENT_ID}:1",
            documentId="d",
            documentName="n",
            content="c",
            relevanceScore=0.0,
            page=4,
            status="UNRESOLVED",
            retrievalPath="structural",
            evidenceKind="table_row",
            section=SECTION,
            elementType="table",
            tableElementId=TABLE_ELEMENT_ID,
            rowIndex=1,
            headerRepeated=True,
        )
        assert ref.evidenceKind == "table_row"
        assert ref.tableElementId == TABLE_ELEMENT_ID
        assert ref.rowIndex == 1
        assert ref.headerRepeated is True
        assert ref.page == 4
        assert ref.section == SECTION
        assert ref.retrievalPath == "structural"
