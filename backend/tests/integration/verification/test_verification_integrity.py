"""Tests for media verification integrity.

Proves that:
  • The backend verification endpoint enforces authentication and input validation
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
async def test_verify_analyze_unauthenticated_returns_401(client: AsyncClient):
    """Media verification performs real analysis, so auth is now enforced.

    The endpoint previously reported 501 without requiring authentication
    because it did nothing.  It now runs inference, so an unauthenticated
    request must be rejected before any work happens.
    """
    resp = await client.post("/api/verification/analyze")
    assert resp.status_code == 401
    assert resp.json().get("detail") == "Not authenticated"


@pytest.mark.asyncio
async def test_verify_analyze_authenticated_without_upload_returns_422(
    client: AsyncClient, create_test_user
):
    """An authenticated request with no uploaded file fails request validation.

    The obsolete expectation was 501 with an 'unavailable' body; now that the
    endpoint is implemented, the required multipart ``file`` is validated and
    its absence yields 422.
    """
    await create_test_user(email="verify422@test.com", password="Pass123!", name="Verify")
    login_resp = await client.post("/api/auth/login", json={
        "email": "verify422@test.com", "password": "Pass123!",
    })
    token = login_resp.json()["access_token"]

    resp = await client.post(
        "/api/verification/analyze",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    # The missing field is reported for the multipart body, not an internal error.
    detail = resp.json().get("detail")
    assert isinstance(detail, list) and detail
    assert any("file" in entry.get("loc", []) for entry in detail)


# ---------------------------------------------------------------------------\n# Frontend source code inspection tests
# ---------------------------------------------------------------------------

from tests.fixtures.paths import REPO_ROOT

_FRONTEND_PAGE = REPO_ROOT / "src" / "pages" / "VerificationPage.tsx"


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
        """Page must honestly frame model output and never show an unearned result.

        The superseded assertion required the text "not yet available" / "under
        development" because the pipeline used to return a 501 placeholder.
        Media Verification is now implemented with a real local image model, so
        that text is obsolete (and asserting it would demand reverting real
        behaviour). The honesty invariant that holds regardless of whether the
        model is available is:

        * a result is rendered only after a successful backend response — never
          pre-filled or fabricated; and
        * the verdict is presented as the model's own classification, not as
          objective proof that the media is real or fake.
        """
        content = self._read_source()
        assert "not an objective proof" in content.lower(), (
            "VerificationPage must not present a model verdict as objective proof."
        )
        assert "status === 'success' && result" in content, (
            "VerificationPage must render a result only after a successful "
            "backend response — never before analysis runs."
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
