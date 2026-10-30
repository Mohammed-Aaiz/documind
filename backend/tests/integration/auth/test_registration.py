"""New-user entry through the real ASGI auth routes and isolated SQLite store."""
import uuid

import pytest
from sqlalchemy import select

from auth.models import User
from auth.routes import verify_password


def registration(**changes):
    payload = {"name": "  New Student  ", "email": f"new-{uuid.uuid4().hex}@example.com", "password": "StudySafely123!"}
    payload.update(changes)
    return payload


@pytest.mark.asyncio
async def test_register_hashes_password_and_authenticates(client, db_session):
    body = registration()
    body["email"] = "  " + body["email"].upper() + "  "
    response = await client.post("/api/auth/register", json=body)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["user"]["name"] == "New Student"
    assert data["user"]["email"] == body["email"].strip().lower()
    assert "hashed_password" not in data["user"]
    assert body["password"] not in response.text
    user = (await db_session.execute(select(User).where(User.email == data["user"]["email"]))).scalar_one()
    assert user.hashed_password != body["password"]
    assert verify_password(body["password"], user.hashed_password)
    profile = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"})
    assert profile.status_code == 200
    assert profile.json()["email"] == data["user"]["email"]
    login = await client.post("/api/auth/login", json={"email": body["email"], "password": body["password"]})
    assert login.status_code == 200, login.text


@pytest.mark.asyncio
async def test_case_insensitive_duplicate_registration_is_rejected(client):
    body = registration()
    assert (await client.post("/api/auth/register", json=body)).status_code == 201
    body["email"] = body["email"].upper()
    response = await client.post("/api/auth/register", json=body)
    assert response.status_code == 409
    assert "access_token" not in response.json()


@pytest.mark.parametrize("change", [
    {"name": "   "}, {"name": "x" * 256}, {"email": "not-an-email"},
    {"email": "wrong@@example.com"}, {"password": "short"},
    {"password": "x" * 73}, {"password": "🔒" * 19},
])
@pytest.mark.asyncio
async def test_invalid_registration_is_rejected_without_echoing_secret(client, change):
    body = registration(**change)
    response = await client.post("/api/auth/register", json=body)
    assert response.status_code == 422, response.text
    payload = response.json()
    assert "access_token" not in payload
    # Pydantic's safe error type `string_too_short` contains the word
    # "short", so inspect structured error values instead of searching the
    # serialized response for a substring of the supplied password.
    assert all("input" not in error for error in payload["detail"])
    assert all(error.get("input") != body["password"] for error in payload["detail"])


@pytest.mark.asyncio
async def test_two_accounts_have_distinct_identities(client):
    first = await client.post("/api/auth/register", json=registration(name="First"))
    second = await client.post("/api/auth/register", json=registration(name="Second"))
    assert first.status_code == second.status_code == 201
    first_profile = await client.get("/api/auth/me", headers={"Authorization": "Bearer " + first.json()["access_token"]})
    second_profile = await client.get("/api/auth/me", headers={"Authorization": "Bearer " + second.json()["access_token"]})
    assert first_profile.json()["email"] != second_profile.json()["email"]
