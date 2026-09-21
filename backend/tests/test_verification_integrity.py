"""Tests for media verification integrity.

Proves that:
  • The backend verification endpoint correctly returns unavailable (501)
  • The frontend VerificationPage contains no fabricated metrics/scores/verdicts
  • No fake analysis results are exposed through the API
"""

import re
import pathlib

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------\n# Backend tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_verify_analyze_returns_501(client: AsyncClient, create_test_user):
    """POST /api/verification/analyze must return 501 Not Implemented."""
    await create_test_user(email="verify@test.com", password="Pass123!", name="Verify")
    login_resp = await client.post("/api/auth/login", json={
        "email": "verify@test.com", "password": "Pass123!",
    })
    token = login_resp.json()["access_token"]

    resp = await client.post(
        "/api/verification/analyze",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 501
    body = resp.json()
    assert body["available"] is False
    assert "not yet implemented" in body["message"].lower()


@pytest.mark.asyncio
async def test_verify_analyze_unauthenticated_returns_501(client: AsyncClient):
    """Unauthenticated verification request returns 501 (pipeline unavailable).

    The endpoint does not require authentication because it does not
    perform any analysis — it simply reports that the pipeline is
    unavailable.
    """
    resp = await client.post("/api/verification/analyze")
    assert resp.status_code == 501


# ---------------------------------------------------------------------------\n# Frontend source code inspection tests
# ---------------------------------------------------------------------------

_FRONTEND_PAGE = (
    pathlib.Path(__file__).resolve().parent.parent.parent
    / "src" / "pages" / "VerificationPage.tsx"
)


class TestNoFabricatedVerificationData:
    """Verify that the frontend VerificationPage contains no fabricated metrics."""

    def _read_source(self) -> str:
        return _FRONTEND_PAGE.read_text(encoding="utf-8")

    def test_no_hardcoded_percentage_scores(self):
        """Reject hardcoded score values like 87.4% or 87%."""
        content = self._read_source()
        # Match patterns like 87.4%, 87%, 92%, etc. in JSX
        pattern = re.compile(r">\s*\d+\.?\d*\s*%<")
        matches = pattern.findall(content)
        assert not matches, (
            f"VerificationPage contains hardcoded percentage scores: {matches}. "
            f"The analysis pipeline is not implemented — no scores should be shown."
        )

    def test_no_synthetic_verdict(self):
        """Reject SYNTHETIC verdict display."""
        content = self._read_source()
        assert "SYNTHETIC" not in content, (
            "VerificationPage contains 'SYNTHETIC' — a fabricated verdict."
        )

    def test_no_authentic_verdict(self):
        """Reject AUTHENTIC verdict display."""
        content = self._read_source()
        assert "AUTHENTIC" not in content, (
            "VerificationPage contains 'AUTHENTIC' — a fabricated verdict."
        )

    def test_no_lip_sync_drift_fabrication(self):
        """Reject fake lip-sync drift metrics."""
        content = self._read_source()
        assert "Lip Sync Drift" not in content, (
            "VerificationPage contains 'Lip Sync Drift' — a fabricated metric."
        )

    def test_no_blink_rate_fabrication(self):
        """Reject fake blink rate metric values (e.g., 'Abnormal', 'Normal').

        The label 'Blink Rate Analysis' in a capabilities list with
        'Not available' is acceptable — it honestly describes what the
        pipeline would do.
        """
        content = self._read_source()
        # Reject fabricated metric values — 'Abnormal' or 'Normal' used as
        # blink rate RESULTS, not as honest status labels
        assert "Abnormal" not in content, (
            "VerificationPage contains fabricated 'Abnormal' blink rate value."
        )

    def test_no_anomaly_detected_fabrication(self):
        """Reject 'ANOMALY DETECTED' fabrication."""
        content = self._read_source()
        assert "ANOMALY DETECTED" not in content, (
            "VerificationPage contains 'ANOMALY DETECTED' — a fabricated verdict."
        )

    def test_no_fake_frame_number(self):
        """Reject fake frame counter like FRAME: 02441.9."""
        content = self._read_source()
        assert "FRAME:" not in content, (
            "VerificationPage contains fake frame counter."
        )

    def test_no_facial_nodes_fabrication(self):
        """Reject 'FACIAL NODES: ACQUIRED' fabrication."""
        content = self._read_source()
        assert "FACIAL NODES" not in content, (
            "VerificationPage contains 'FACIAL NODES' — fabricated analysis state."
        )

    def test_honest_unavailable_message_present(self):
        """Page must clearly state the pipeline is not available."""
        content = self._read_source()
        assert "not yet available" in content.lower() or "under development" in content.lower(), (
            "VerificationPage should contain an honest unavailable/under-development message."
        )

    def test_no_fabricated_progress_bars(self):
        """Reject progress bars with hardcoded fake widths (75%, 90%, 85%, etc.)."""
        content = self._read_source()
        # Check for hardcoded width percentages in style attributes
        pattern = re.compile(r"width:\s*['\"]?([\d]+)%['\"]?")
        matches = pattern.findall(content)
        # Allow 0% (empty bar) but reject anything that looks like fake progress
        fake_progress = [m + '%' for m in matches if m != '0']
        assert not fake_progress, (
            f"VerificationPage contains hardcoded progress bar widths: {fake_progress}. "
            f"The analysis pipeline is not implemented — no progress should be shown."
        )
