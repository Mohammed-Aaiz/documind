"""Current engine selection: server-configured Groq, generative alias, retired extractive."""
import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize("engine", [None, "provider", "generative"])
async def test_product_engine_uses_the_shared_conversation_service(client, ask_auth, provider_answer, engine):
    body = {"question": "Explain calibration", "answerFormat": "15", "workspace": "student", "task": "explain"}
    if engine:
        body["engine"] = engine
    answer, run = provider_answer
    answer.marks = 15
    response = await client.post("/api/chat/ask", json=body, headers=ask_auth["headers"])
    assert response.status_code == 200, response.text
    assert response.json()["engine"] == "groq" and response.json()["marks"] == 15
    run.assert_awaited_once()
    args = run.await_args.kwargs
    assert args["user_id"] == ask_auth["user_id"]
    assert args["session_id"] and args["answer_format"] == "15"
    assert args["workspace"] == "student" and args["task"] == "explain"


@pytest.mark.asyncio
async def test_retired_extractive_engine_is_explicitly_gone(client, ask_auth, provider_answer):
    response = await client.post("/api/chat/ask", json={"question": "Anything?", "engine": "extractive"}, headers=ask_auth["headers"])
    assert response.status_code == 410 and "retired" in response.json()["detail"]
    provider_answer[1].assert_not_awaited()


@pytest.mark.asyncio
async def test_unknown_engine_does_not_silently_select_a_provider(client, ask_auth, provider_answer):
    response = await client.post("/api/chat/ask", json={"question": "Anything?", "engine": "magic"}, headers=ask_auth["headers"])
    assert response.status_code == 400 and "engine" in response.json()["detail"]
    provider_answer[1].assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_conversation_request_is_a_client_error(client, ask_auth, provider_answer):
    provider_answer[1].side_effect = ValueError("Unsupported workspace task")
    response = await client.post("/api/chat/ask", json={"question": "Anything?"}, headers=ask_auth["headers"])
    assert response.status_code == 400 and response.json()["detail"] == "Unsupported workspace task"
