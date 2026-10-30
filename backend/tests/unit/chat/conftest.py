"""Current chat HTTP tests isolate the shared Groq conversation boundary."""
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def ask_auth(client, create_test_user):
    user = await create_test_user(email=f"ask-{uuid.uuid4().hex}@test.com", password="Pass123!")
    login = await client.post("/api/auth/login", json={"email": user.email, "password": "Pass123!"})
    assert login.status_code == 200
    return {"headers": {"Authorization": "Bearer " + login.json()["access_token"]}, "user_id": str(user.id)}


@pytest.fixture
def provider_answer(monkeypatch):
    from orchestration import service
    result = SimpleNamespace(answer="The interval is six months [1].", sources=[],
        insufficient_context=False, abstained=False, engine="groq", marks=10,
        verification={"verified": True, "status": "SUPPORTED"}, warnings=[],
        pipeline_version="visual-spatial-dual-path-v3")
    mock = AsyncMock(return_value=result)
    monkeypatch.setattr(service, "answer_with_memory", mock)
    return result, mock
