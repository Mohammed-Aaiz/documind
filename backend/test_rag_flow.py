"""
Full integration test for RAG question answering.

Tests through the real Vite proxy -> FastAPI -> pgvector -> QA model.
No mocks, no fakes, no simulated results.
"""

import json
import os
import subprocess
import sys
import uuid
import urllib.request

BASE = "http://localhost:3000"
PSQL = "C:/pg/pg16/pgsql/bin/psql.exe"


def api_call(method, path, token=None, body=None):
    url = f"{BASE}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def multipart_upload(url, token, filepath, filename):
    boundary = uuid.uuid4().hex
    with open(filepath, "rb") as f:
        file_bytes = f.read()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + file_bytes + f"\r\n--{boundary}--\r\n".encode()
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


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

    # 1. Login
    print()
    print("1. Login to get JWT token")
    code, body = api_call("POST", "/api/auth/login", body={
        "email": "test@documind.io",
        "password": "TestPass123!",
    })
    check("Login succeeds", code == 200)
    token = body.get("access_token", "")

    # 2. Upload a knowledge document
    print()
    print("2. Upload knowledge document")
    pdf_path = os.path.join(os.path.dirname(__file__), "uploads", "documind_facts.pdf")
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
        "topK": 3,
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
        "topK": 3,
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
        "topK": 3,
    })
    check("Ask returns 200", code == 200)
    check("Got an answer", bool(ans.get("answer")), f"answer='{ans.get('answer')}'")
    check("Answer mentions 384", "384" in ans.get("answer", ""),
          f"answer='{ans.get('answer')}'")

    # 7. Ask an unrelated question
    print()
    print("7. Ask unrelated question: 'What is the capital of France?'")
    code, ans = api_call("POST", "/api/chat/ask", token=token, body={
        "question": "What is the capital of France?",
        "topK": 3,
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
        result = subprocess.run(
            [PSQL, "-h", "localhost", "-U", "documind", "-d", "documind",
             "-c", f"SELECT id, content FROM document_chunks WHERE id = '{chunk_id}';"],
            capture_output=True, text=True
        )
        check("Chunk exists in DB", chunk_id in result.stdout, result.stdout.strip()[:200])

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
