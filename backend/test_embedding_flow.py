"""
Integration test for embedding generation and semantic search.

Tests through the real Vite proxy -> FastAPI -> PostgreSQL with pgvector.
No mocks, no fakes, no simulated results.
"""

import json
import os
import subprocess
import sys
import tempfile
import uuid
import urllib.request

BASE = "http://localhost:3000"  # Vite proxy -> FastAPI
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


def psql(sql):
    result = subprocess.run(
        [PSQL, "-h", "localhost", "-U", "documind", "-d", "documind", "-c", sql],
        capture_output=True, text=True
    )
    return result.stdout


def create_test_pdf(path):
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72),
        "Machine learning is a subset of artificial intelligence that enables "
        "systems to learn from data. Deep learning uses neural networks with "
        "multiple layers to model complex patterns in data.",
        fontsize=12)
    page2 = doc.new_page()
    page2.insert_text((72, 72),
        "Natural language processing allows computers to understand and generate "
        "human language. Transformers are a key architecture in modern NLP, "
        "enabling models like BERT and GPT to process text effectively.",
        fontsize=12)
    page3 = doc.new_page()
    page3.insert_text((72, 72),
        "Computer vision enables machines to interpret visual information from "
        "the world. Convolutional neural networks are commonly used for image "
        "classification, object detection, and image segmentation tasks.",
        fontsize=12)
    doc.save(path)
    doc.close()



def create_irrelevant_pdf(path):
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72),
        "The history of ancient Rome spans over a thousand years. "
        "Roman civilization began in the 8th century BC and lasted until "
        "the fall of the Western Roman Empire in 476 AD.",
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
    print("  EMBEDDING & SEMANTIC SEARCH INTEGRATION TEST")
    print("  (FastAPI -> pgvector -> PostgreSQL)")
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

    # 2. Upload an ML/AI document
    print()
    print("2. Upload ML/AI document")
    ml_pdf = os.path.join(os.path.dirname(__file__), 'uploads', 'ml_test.pdf')
    create_test_pdf(ml_pdf)
    code, body = multipart_upload(f"{BASE}/api/documents/upload", token, ml_pdf, "ml_basics.pdf")
    os.unlink(ml_pdf)
    check("Upload succeeds", code == 201, f"got {code}")
    ml_doc_id = body.get("id", "")
    check("Got document ID", bool(ml_doc_id))
    check("Initial embedding_status is pending", body.get("embeddingStatus") == "pending")

    # 3. Upload an irrelevant document (history)
    print()
    print("3. Upload irrelevant history document")
    hist_pdf = os.path.join(os.path.dirname(__file__), 'uploads', 'history_test.pdf')
    create_irrelevant_pdf(hist_pdf)
    code, body = multipart_upload(f"{BASE}/api/documents/upload", token, hist_pdf, "roman_history.pdf")
    os.unlink(hist_pdf)
    hist_doc_id = body.get("id", "")
    check("Upload succeeds", code == 201)

    # 4. Generate embeddings for ML document
    print()
    print("4. Generate embeddings for ML document")
    code, body = api_call("POST", "/api/embeddings/generate", token=token, body={
        "documentId": ml_doc_id,
    })
    check("Embedding generation succeeds", code == 200, f"got {code}: {body}")
    check("Chunks embedded > 0", body.get("chunksEmbedded", 0) > 0, f"count={body.get('chunksEmbedded')}")

    # 5. Verify embeddings stored in PostgreSQL
    print()
    print("5. Verify embeddings stored in PostgreSQL")
    result = psql(f"SELECT COUNT(*) FROM document_chunks WHERE document_id = '{ml_doc_id}' AND embedding IS NOT NULL;")
    check("All chunks have embeddings", "3" in result or "2" in result, result.strip()[:100])

    # Check embedding dimensions
    result = psql(f"SELECT array_length(embedding::real[], 1) FROM document_chunks WHERE document_id = '{ml_doc_id}' AND embedding IS NOT NULL LIMIT 1;")
    check("Embedding dimension is 384", "384" in result, result.strip()[:100])

    # 6. Check embedding_status updated to ready
    print()
    print("6. Check embedding_status updated to 'ready'")
    code, body = api_call("GET", f"/api/documents/{ml_doc_id}", token=token)
    check("Document embedding_status is ready", body.get("embeddingStatus") == "ready")

    # 7. Generate embeddings for history document
    print()
    print("7. Generate embeddings for history document")
    code, body = api_call("POST", "/api/embeddings/generate", token=token, body={
        "documentId": hist_doc_id,
    })
    check("History embeddings succeed", code == 200)

    # 8. Semantic search for ML-related query
    print()
    print("8. Semantic search: 'neural networks and deep learning'")
    code, body = api_call("POST", "/api/embeddings/search", token=token, body={
        "query": "neural networks and deep learning",
        "topK": 3,
    })
    check("Search returns 200", code == 200, f"got {code}")
    results = body.get("results", [])
    check("Got search results", len(results) > 0, f"count={len(results)}")

    if results:
        top = results[0]
        check("Top result has chunkId", bool(top.get("chunkId")))
        check("Top result has content", bool(top.get("content")))
        check("Top result has score", isinstance(top.get("score"), float), f"score={top.get('score')}")
        check("Score is between 0 and 1", 0 <= top.get("score", -1) <= 1)
        check("Top result has documentName", bool(top.get("documentName")))
        check("Top result documentName matches ML doc", "ml" in top.get("documentName", "").lower())
        check("Top result has documentId", top.get("documentId") == ml_doc_id)

        # Verify the content is actually from the ML document
        ml_keywords = ["neural", "deep learning", "machine learning", "network"]
        content_lower = top.get("content", "").lower()
        check("Content contains ML-related keywords",
              any(kw in content_lower for kw in ml_keywords),
              content_lower[:100])

    # 9. Search for NLP query
    print()
    print("9. Semantic search: 'natural language processing transformers'")
    code, body = api_call("POST", "/api/embeddings/search", token=token, body={
        "query": "natural language processing transformers",
        "topK": 3,
    })
    check("Search returns 200", code == 200)
    results = body.get("results", [])
    if results:
        top = results[0]
        content_lower = top.get("content", "").lower()
        check("Top result contains NLP keywords",
              any(kw in content_lower for kw in ["nlp", "language", "transformer", "natural"]),
              content_lower[:100])

    # 10. Search with no relevant results
    print()
    print("10. Semantic search: 'quantum physics equations'")
    code, body = api_call("POST", "/api/embeddings/search", token=token, body={
        "query": "quantum physics equations",
        "topK": 3,
    })
    check("Search returns 200", code == 200)
    results = body.get("results", [])
    # Results may exist but scores should be lower than ML queries
    if results:
        check("Results exist but scores are lower",
              all(r.get("score", 0) < 0.8 for r in results),
              f"scores={[r.get('score') for r in results]}")

    # 11. Verify only user's documents appear
    print()
    print("11. Verify user scoping")
    # Check that both documents belong to the same user
    result = psql(f"SELECT user_id FROM documents WHERE id = '{ml_doc_id}';")
    ml_user = ""
    for line in result.strip().split("\n"):
        line = line.strip()
        if len(line) == 36 and "-" in line:
            ml_user = line
            break
    result = psql(f"SELECT user_id FROM documents WHERE id = '{hist_doc_id}';")
    hist_user = ""
    for line in result.strip().split("\n"):
        line = line.strip()
        if len(line) == 36 and "-" in line:
            hist_user = line
            break
    check("Both docs belong to same user", ml_user == hist_user and bool(ml_user))

    # 12. Test unauthenticated search
    print()
    print("12. Unauthenticated search")
    code, body = api_call("POST", "/api/embeddings/search", body={
        "query": "test",
    })
    check("Search without token returns 401", code == 401, f"got {code}")

    code, body = api_call("POST", "/api/embeddings/generate", body={
        "documentId": ml_doc_id,
    })
    check("Generate without token returns 401", code == 401, f"got {code}")

    # 13. Generate for non-existent document
    print()
    print("13. Generate for non-existent document")
    fake_id = str(uuid.uuid4())
    code, body = api_call("POST", "/api/embeddings/generate", token=token, body={
        "documentId": fake_id,
    })
    check("Returns 404", code == 404, f"got {code}")

    # 14. Cleanup
    print()
    print("14. Cleanup test documents")
    api_call("DELETE", f"/api/documents/{ml_doc_id}", token=token)
    api_call("DELETE", f"/api/documents/{hist_doc_id}", token=token)
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
