"""Phase 5 integration: table-row provenance through ``/api/reliability/last-query``.

The Reliability Center reads the persisted snapshot, not the live response, so
this test stores a real snapshot with the production write helper
(``store_query_reliability``) and then reads it back through the real endpoint
with a real JWT.  It proves the table-row provenance survives persistence and
normalisation *unchanged*, that the counter partitions stay exact, and that
records written before Phase 5 (no table-row fields) still render.

The payloads used here are exactly what ``brain.response._build_reliability``
produces — the same dict shape ``chat/routes.py`` persists after ``/api/chat/ask``.
"""

from __future__ import annotations

from reliability.routes import store_query_reliability

PASSWORD = "Pass123!"

TABLE_ELEMENT_ID = "eeeeeeee-eeee-5eee-8eee-eeeeeeeeeeee"
TABLE_ROW_ID = f"table_row:{TABLE_ELEMENT_ID}:1"
SECTION = "5. Maintenance Schedule"

#: What ``_build_reliability`` emits for the compact table-row band.
TABLE_ROW_SOURCE = {
    "id": TABLE_ROW_ID,
    "documentId": "doc-1",
    "documentName": "demo.pdf",
    "content": (
        "Component | Calibration Interval\n"
        "Lidar Array LR-9 | 250 h | 0-80 m"
    ),
    "relevanceScore": 0.0,
    "page": 4,
    "status": "UNRESOLVED",
    "retrievalPath": "structural",
    "fusionScore": None,
    "structuralHops": None,
    "evidenceKind": "table_row",
    "section": SECTION,
    "elementType": "table",
    "tableElementId": TABLE_ELEMENT_ID,
    "rowIndex": 1,
    "headerRepeated": True,
}

#: A pre-Phase-5 record: no ``section`` / ``elementType`` / table-row fields.
OLD_CHUNK_SOURCE = {
    "id": "chunk-1",
    "documentId": "doc-1",
    "documentName": "demo.pdf",
    "content": "plain legacy chunk text",
    "relevanceScore": 0.7,
    "page": 2,
    "status": "VERIFIED",
    "retrievalPath": "semantic",
    "fusionScore": 0.0125,
    "structuralHops": None,
    "evidenceKind": "chunk",
}


async def _token(client, email: str, password: str = PASSWORD) -> dict:
    login = await client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _store(db_session, user_id, sources: list[dict]) -> None:
    await store_query_reliability(
        str(user_id),
        {
            "question": "What calibration interval does the Maintenance Schedule "
            "give for the lidar array?",
            "answer": "250 h",
            "qaConfidence": 0.4,
            "retrievalScore": 0.0,
            "avgRetrievalScore": 0.0,
            "sourceCount": len(sources),
            "uniqueDocuments": 1,
            "factualGrounded": True,
            "insufficientContext": False,
            "sources": sources,
        },
        db=db_session,
    )
    await db_session.commit()


class TestTableRowReliabilityProvenance:
    async def test_table_row_provenance_survives_last_query(
        self, client, db_session, create_test_user
    ):
        email = "p5-table-row@test.com"
        user = await create_test_user(email=email, password=PASSWORD)
        await _store(db_session, user.id, [TABLE_ROW_SOURCE])
        headers = await _token(client, email)

        resp = await client.get("/api/reliability/last-query", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()

        assert body["sourceCount"] == 1
        src = body["sources"][0]
        # Exact persisted values — never re-derived from the row text.
        assert src["id"] == TABLE_ROW_ID
        assert src["evidenceKind"] == "table_row"
        assert src["tableElementId"] == TABLE_ELEMENT_ID
        assert src["rowIndex"] == 1
        assert src["headerRepeated"] is True
        assert src["page"] == 4
        assert src["section"] == SECTION
        assert src["elementType"] == "table"
        assert src["retrievalPath"] == "structural"
        assert src["relevanceScore"] == 0.0
        assert src["fusionScore"] is None
        assert "Lidar Array LR-9" in src["content"]
        assert "250 h" in src["content"]

        # The row is structural by *path*, and the backend counts it separately
        # so \"structural chunk\" is not overstated.
        assert body["structuralSourceCount"] == 1
        assert body["structuralElementSourceCount"] == 0
        assert body["tableRowSourceCount"] == 1
        assert body["semanticSourceCount"] == 0
        assert body["hybridSourceCount"] == 0

    async def test_old_record_without_table_fields_still_renders(
        self, client, db_session, create_test_user
    ):
        email = "p5-old-record@test.com"
        user = await create_test_user(email=email, password=PASSWORD)
        await _store(db_session, user.id, [OLD_CHUNK_SOURCE])
        headers = await _token(client, email)

        resp = await client.get("/api/reliability/last-query", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        src = body["sources"][0]

        # The established meaning is unchanged; the new fields are simply absent.
        assert src["evidenceKind"] == "chunk"
        assert src["retrievalPath"] == "semantic"
        assert src["tableElementId"] is None
        assert src["rowIndex"] is None
        assert src["headerRepeated"] is None
        assert src["section"] is None
        assert src["elementType"] is None
        assert body["tableRowSourceCount"] == 0

    async def test_all_evidence_kinds_partition_the_counts(
        self, client, db_session, create_test_user
    ):
        email = "p5-mixed-kinds@test.com"
        user = await create_test_user(email=email, password=PASSWORD)
        hybrid = dict(
            OLD_CHUNK_SOURCE, id="hybrid-1", retrievalPath="hybrid"
        )
        element = dict(
            OLD_CHUNK_SOURCE,
            id="element-1",
            retrievalPath="structural",
            evidenceKind="structure_element",
            section="A",
            elementType="section",
        )
        structural_chunk = dict(
            OLD_CHUNK_SOURCE, id="structural-chunk-1", retrievalPath="structural"
        )
        await _store(
            db_session,
            user.id,
            [OLD_CHUNK_SOURCE, hybrid, element, structural_chunk, TABLE_ROW_SOURCE],
        )
        headers = await _token(client, email)

        body = (
            await client.get("/api/reliability/last-query", headers=headers)
        ).json()
        by_id = {s["id"]: s["evidenceKind"] for s in body["sources"]}

        # Existing kinds are unchanged.
        assert by_id["chunk-1"] == "chunk"
        assert by_id["hybrid-1"] == "chunk"
        assert by_id["element-1"] == "structure_element"
        assert by_id["structural-chunk-1"] == "chunk"
        # The new kind is reported as itself.
        assert by_id[TABLE_ROW_ID] == "table_row"

        # Path counts partition the sources exactly (existing invariant)...
        assert (
            body["semanticSourceCount"]
            + body["structuralSourceCount"]
            + body["hybridSourceCount"]
        ) == body["sourceCount"]
        # ...and the structural bucket partitions into element, table row and
        # chunk-level structural evidence.
        assert body["structuralElementSourceCount"] == 1
        assert body["tableRowSourceCount"] == 1
        assert (
            body["structuralSourceCount"]
            - body["structuralElementSourceCount"]
            - body["tableRowSourceCount"]
        ) == 1  # the single chunk-level structural source
