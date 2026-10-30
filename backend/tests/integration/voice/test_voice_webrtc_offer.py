"""Integration tests for the WebRTC voice offer route.

``POST /api/voice/webrtc/offer`` is the signaling surface: it accepts the
browser's SDP offer, builds a real ``aiortc`` peer connection with the Piper
output track, and answers.  These tests drive a *real* aiortc client — no
network is used beyond host ICE candidates, which are loopback/local sockets.

Covers: authentication, session-id and format validation, an invalid SDP, and a
real offer/answer handshake whose answer advertises the audio media section.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from httpx import AsyncClient

import voice_webrtc

AIORTC = pytest.mark.skipif(
    not voice_webrtc.AIORTC_AVAILABLE, reason="aiortc is not installed"
)

OFFER_URL = "/api/voice/webrtc/offer"
LOGIN_URL = "/api/auth/login"


async def _auth_headers(client: AsyncClient, create_test_user, email: str) -> dict:
    await create_test_user(email=email, password="Pass123!", name="Voice User")
    resp = await client.post(LOGIN_URL, json={"email": email, "password": "Pass123!"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_chat_session(
    client: AsyncClient, headers: dict, *, workspace: str = "student"
) -> str:
    """Create the persisted owner-scoped session required by the offer route."""
    response = await client.post(
        "/api/chat/sessions", json={"workspace": workspace}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _unique_email(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}@test.com"


def _offer(session_id: str, **overrides) -> dict:
    body = {
        "sdp": "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n",
        "type": "offer",
        "sessionId": session_id,
        "answerFormat": "10",
    }
    body.update(overrides)
    return body


@pytest.mark.asyncio
async def test_offer_requires_authentication(client: AsyncClient):
    resp = await client.post(OFFER_URL, json=_offer(str(uuid.uuid4())))
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_offer_rejects_an_invalid_session_id(client: AsyncClient, create_test_user):
    headers = await _auth_headers(client, create_test_user, _unique_email("webrtc_badsession"))

    resp = await client.post(
        OFFER_URL, json=_offer("../../etc/passwd"), headers=headers
    )

    assert resp.status_code == 400
    assert "session" in resp.text.lower()


@pytest.mark.asyncio
async def test_offer_rejects_a_non_offer_type(client: AsyncClient, create_test_user):
    headers = await _auth_headers(client, create_test_user, _unique_email("webrtc_type"))

    resp = await client.post(
        OFFER_URL, json=_offer(str(uuid.uuid4()), type="answer"), headers=headers
    )

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_offer_rejects_an_invalid_answer_format(client: AsyncClient, create_test_user):
    headers = await _auth_headers(client, create_test_user, _unique_email("webrtc_format"))

    resp = await client.post(
        OFFER_URL, json=_offer(str(uuid.uuid4()), answerFormat="7"), headers=headers
    )

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_offer_rejects_malformed_sdp_without_leaking_internals(
    client: AsyncClient, create_test_user
):
    headers = await _auth_headers(client, create_test_user, _unique_email("webrtc_sdp"))
    session_id = str(uuid.uuid4())

    resp = await client.post(
        OFFER_URL,
        json=_offer(session_id, sdp="this is not sdp"),
        headers=headers,
    )

    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid SDP offer"
    assert "traceback" not in resp.text.lower()
    # A failed negotiation must not leave a session registered.
    assert not [
        session
        for session in voice_webrtc._sessions.values()
        if session.session_id == session_id
    ]


@AIORTC
@pytest.mark.asyncio
async def test_offer_without_a_control_channel_is_rejected(
    client: AsyncClient, create_test_user
):
    """Without the data channel the server could never report a turn."""
    from aiortc import RTCPeerConnection

    headers = await _auth_headers(client, create_test_user, _unique_email("webrtc_nochannel"))
    session_id = await _create_chat_session(client, headers)

    pc = RTCPeerConnection()
    try:
        pc.addTransceiver("audio", direction="sendrecv")
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)

        resp = await client.post(
            OFFER_URL,
            json=_offer(session_id, sdp=pc.localDescription.sdp),
            headers=headers,
        )
    finally:
        await pc.close()
        await asyncio.sleep(0.1)

    assert resp.status_code == 400
    assert "control" in resp.json()["detail"].lower()


@AIORTC
@pytest.mark.asyncio
async def test_real_offer_answers_with_an_audio_media_section(
    client: AsyncClient, create_test_user
):
    """The browser side of the handshake is exercised with a real aiortc client."""
    from aiortc import RTCPeerConnection, RTCSessionDescription

    headers = await _auth_headers(client, create_test_user, _unique_email("webrtc_ok"))
    session_id = await _create_chat_session(client, headers)

    pc = RTCPeerConnection()
    try:
        pc.addTransceiver("audio", direction="sendrecv")
        # The offer must carry the control channel: an answer cannot add one.
        pc.createDataChannel("control")
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)

        deadline = asyncio.get_running_loop().time() + 10
        while (
            pc.iceGatheringState != "complete"
            and asyncio.get_running_loop().time() < deadline
        ):
            await asyncio.sleep(0.05)

        resp = await client.post(
            OFFER_URL,
            json=_offer(session_id, sdp=pc.localDescription.sdp),
            headers=headers,
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["type"] == "answer"
        assert body["sessionId"] == session_id
        assert body["stt"] == "whisper-local"
        assert body["tts"]
        assert body["vad"]["engine"] == "silero-onnx"
        assert "m=audio" in body["sdp"]

        await pc.setRemoteDescription(
            RTCSessionDescription(sdp=body["sdp"], type="answer")
        )
        assert pc.remoteDescription is not None
        assert pc.remoteDescription.type == "answer"
        assert "m=application" in body["sdp"]

        # The session is live and owned by the authenticated user.
        sessions = [
            session
            for session in voice_webrtc._sessions.values()
            if session.session_id == session_id
        ]
        assert len(sessions) == 1
        assert sessions[0].user_id
        assert sessions[0].pc is not None
    finally:
        await pc.close()
        # aiortc finishes its connection task asynchronously; give it a moment
        # so the loop is not torn down under a pending task.
        await asyncio.sleep(0.1)
        for session in [
            session
            for session in voice_webrtc._sessions.values()
            if session.session_id == session_id
        ]:
            await session.close()
