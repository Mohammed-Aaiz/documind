"""
Full integration test for RAG question answering.

Tests through the real Vite proxy -> FastAPI -> pgvector -> QA model.
No mocks, no fakes, no simulated results.

Corpus isolation: this harness owns a **dedicated** account and an explicitly
purged corpus.  It used to authenticate as the shared ``test@documind.io``,
whose corpus accumulates documents from every other harness; because retrieval
is user-scoped, those unrelated documents reached the QA context and the
extractive model returned a span from one of them instead of from this
harness's own knowledge document.  Isolation belongs here, in the test's
dataset, never in the QA model or the retrieval architecture.
"""

import os
import sys
from functools import partial

import pytest

from tests.fixtures import e2e_config
from tests.fixtures.integration_http import api_call as _api_call
from tests.fixtures.integration_http import multipart_upload
from tests.fixtures.live_server import require_live_server

BASE = e2e_config.base_url()

# Retrieval depth for every ask below.  This is the product's own default:
# the frontend's only ask call site (src/context/WorkspaceContext.tsx) invokes
# apiAskQuestion(text) with no explicit topK, so src/lib/api.ts supplies 5.
# The harness used to pin 3, a depth the product never uses.
ASK_TOP_K = 5

# Bound to this harness's BASE; see tests/integration_http.py.
api_call = partial(_api_call, base=BASE)


def create_knowledge_pdf(path):
    """Create a PDF with specific factual claims for testing."""
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72),
        "The DocuMind system was created by the Acme Corporation in 2024. "
        "It uses advanced neural networks for document analysis. "
        "The system supports PDF, DOCX, and TXT file formats. "
        "Maximum file upload size is 50 megabytes.",
        fontsize=12)
    page2 = doc.new_page()
    page2.insert_text((72, 72),
        "DocuMind uses the all-MiniLM-L6-v2 model for generating embeddings. "
        "This model produces 384-dimensional vectors. "
        "The system stores vectors using PostgreSQL with the pgvector extension. "
        "Semantic search uses cosine distance for similarity matching.",
        fontsize=12)
    page3 = doc.new_page()
    page3.insert_text((72, 72),
        "The Oracle is the AI assistant component of DocuMind. "
        "It answers questions based on uploaded documents using RAG technology. "
        "The QA model extracts answers from retrieved document chunks. "
        "Confidence scores range from 0 to 1, where higher is better.",
        fontsize=12)
    doc.save(path)
    doc.close()


def main():
    passed = 0
    failed = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        status = "PASS" if condition else "FAIL"
        if condition:
            passed += 1
        else:
            failed += 1
        suffix = f" -- {detail}" if detail else ""
        print(f"  [{status}] {name}{suffix}")

    print()
    print("=" * 60)
    print("  RAG QUESTION ANSWERING INTEGRATION TEST")
    print("  (FastAPI -> pgvector -> QA model)")
    print("=" * 60)

    # 0. Corpus isolation — this harness owns a dedicated account.
    #
    # The account is created through the project's canonical user script and
    # its corpus is then emptied through the real API, so the retrieval scope
    # for every assertion below is exactly this harness's own document.
    print()
    print("0. Ensure dedicated E2E user and empty corpus")
    e2e_config.ensure_test_user(
        e2e_config.RAG_TEST_USER_EMAIL,
        e2e_config.RAG_TEST_USER_PASSWORD,
        e2e_config.RAG_TEST_USER_NAME,
    )

    # 1. Login
    print()
    print("1. Login to get JWT token")
    code, body = api_call("POST", "/api/auth/login", body={
        "email": e2e_config.RAG_TEST_USER_EMAIL,
        "password": e2e_config.RAG_TEST_USER_PASSWORD,
    })
    check("Login succeeds", code == 200)
    token = body.get("access_token", "")

    purged = e2e_config.purge_documents(BASE, token=token)
    print(f"  Purged {purged} pre-existing document(s) for {e2e_config.RAG_TEST_USER_EMAIL}")
    remaining = e2e_config.document_names(BASE, token=token)
    check("Corpus isolated (0 documents before ingestion)", remaining == [],
          f"remaining={remaining}")

    # 2. Upload a knowledge document
    print()
    print("2. Upload knowledge document")
    # Generated into the test layer's own scratch directory — never the
    # application's upload root, and never a fixed name in the shared temp dir.
    pdf_path = e2e_config.generated_uploads_dir() / "documind_facts.pdf"
    create_knowledge_pdf(pdf_path)
    code, doc = multipart_upload(f"{BASE}/api/documents/upload", token, pdf_path, "documind_facts.pdf")
    os.unlink(pdf_path)
    check("Upload succeeds", code == 201, f"got {code}")
    doc_id = doc.get("id", "")
    check("Got document ID", bool(doc_id))

    # 3. Generate embeddings
    print()
    print("3. Generate embeddings for document")
    code, gen = api_call("POST", "/api/embeddings/generate", token=token, body={
        "documentId": doc_id,
    })
    check("Embeddings generated", code == 200, f"got {code}: {gen}")
    check("Chunks embedded > 0", gen.get("chunksEmbedded", 0) > 0)

    # 4. Ask a question whose answer is IN the document
    print()
    print("4. Ask: 'Who created DocuMind?'")
    code, ans = api_call("POST", "/api/chat/ask", token=token, body={
        "question": "Who created DocuMind?",
        "topK": ASK_TOP_K,
    })
    check("Ask returns 200", code == 200, f"got {code}")
    check("Got an answer", bool(ans.get("answer")), f"answer='{ans.get('answer')}'")
    check("Answer contains 'Acme'", "acme" in ans.get("answer", "").lower(),
          f"answer='{ans.get('answer')}'")
    check("Has sources", len(ans.get("sources", [])) > 0, f"count={len(ans.get('sources', []))}")
    check("Insufficient context is False", ans.get("insufficientContext") is False)
    check("Confidence > 0", ans.get("confidence", 0) > 0, f"score={ans.get('confidence')}")

    # Check source details
    if ans.get("sources"):
        src = ans["sources"][0]
        check("Source has chunkId", bool(src.get("chunkId")))
        check("Source has content", bool(src.get("content")))
        check("Source has score", isinstance(src.get("score"), float))
        check("Source has documentName", bool(src.get("documentName")))
        check("Source documentName matches", "documind" in src.get("documentName", "").lower())
        check("Source has page number", src.get("page") is not None)

    # 5. Ask another factual question
    print()
    print("5. Ask: 'What embedding model does DocuMind use?'")
    code, ans = api_call("POST", "/api/chat/ask", token=token, body={
        "question": "What embedding model does DocuMind use?",
        "topK": ASK_TOP_K,
    })
    check("Ask returns 200", code == 200)
    check("Got an answer", bool(ans.get("answer")), f"answer='{ans.get('answer')}'")
    answer_lower = ans.get("answer", "").lower()
    check("Answer mentions MiniLM", "minilm" in answer_lower or "mini" in answer_lower,
          f"answer='{ans.get('answer')}'")

    # 6. Ask about vector dimensions
    print()
    print("6. Ask: 'How many dimensions do the embeddings have?'")
    code, ans = api_call("POST", "/api/chat/ask", token=token, body={
        "question": "How many dimensions do the embeddings have?",
        "topK": ASK_TOP_K,
    })
    check("Ask returns 200", code == 200)
    check("Got an answer", bool(ans.get("answer")), f"answer='{ans.get('answer')}'")
    check("Answer mentions 384", "384" in ans.get("answer", ""),
          f"answer='{ans.get('answer')}'")

    # Q6 evidence: show this is the intended RAG behaviour on this harness's
    # own corpus, not accidental cross-test state.
    q6_sources = ans.get("sources", [])
    q6_top = q6_sources[0] if q6_sources else {}
    print()
    print("  Q6 EVIDENCE")
    print(f"    test user            : {e2e_config.RAG_TEST_USER_EMAIL}")
    print(f"    documents in corpus  : {len(e2e_config.document_names(BASE, token=token))}")
    print(f"    retrieved top result : {q6_top.get('documentName')!r} "
          f"(score={q6_top.get('score')}, page={q6_top.get('page')})")
    print(f"    answer               : {ans.get('answer')!r}")
    print(f"    confidence           : {ans.get('confidence')}")

    # 7. Ask an unrelated question
    print()
    print("7. Ask unrelated question: 'What is the capital of France?'")
    code, ans = api_call("POST", "/api/chat/ask", token=token, body={
        "question": "What is the capital of France?",
        "topK": ASK_TOP_K,
    })
    check("Ask returns 200", code == 200)
    # Should either return no answer or indicate insufficient context
    check("Insufficient context flagged or empty answer",
          ans.get("insufficientContext") is True or not ans.get("answer", "").strip(),
          f"insufficientContext={ans.get('insufficientContext')}, answer='{ans.get('answer')}'")

    # 8. Verify sources correspond to real chunks
    print()
    print("8. Verify sources are real chunks from PostgreSQL")
    if ans.get("sources"):
        chunk_id = ans["sources"][0]["chunkId"]
        result = e2e_config.psql(
            f"SELECT id, content FROM document_chunks WHERE id = '{chunk_id}';"
        )
        check("Chunk exists in DB", chunk_id in result, result.strip()[:200])

    # 9. Unauthenticated access
    print()
    print("9. Unauthenticated access")
    code, body = api_call("POST", "/api/chat/ask", body={
        "question": "test",
    })
    check("Ask without token returns 401", code == 401, f"got {code}")

    # 10. Empty question
    print()
    print("10. Empty question")
    code, body = api_call("POST", "/api/chat/ask", token=token, body={
        "question": "",
    })
    check("Empty question returns 400", code == 400, f"got {code}")

    # 11. Cleanup
    print()
    print("11. Cleanup")
    api_call("DELETE", f"/api/documents/{doc_id}", token=token)
    check("Cleanup done", True)

    # Summary
    total = passed + failed
    print()
    print("=" * 60)
    print(f"  RESULTS: {passed}/{total} passed, {failed} failed")
    print("=" * 60)
    print()

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)


# ---------------------------------------------------------------------------
# pytest entry point — the test-isolation contract requires tests to run only
# through pytest.  Skipped unless a live server answers at BASE.
# ---------------------------------------------------------------------------
@pytest.mark.e2e
def test_rag_flow_live_server():
    """Upload -> embed -> ask -> verify sources against real PostgreSQL."""
    require_live_server(BASE)
    assert main() is True
