"""Test policy for destructive expectations that are blocked by design.

STEP 1.6X, Workstream A.  ``evaluation.isolation`` refuses every destructive
cleanup until a genuine, connection-bound lifecycle authorization exists, so a
test that asserts destructive success cannot hold — and must not be made to pass
by relaxing that gate.  Tests in that position are marked here rather than being
deleted or excluded wholesale, so that:

* the skip is visible in ``pytest -rs`` together with the exact unmet
  requirement;
* the test body is preserved intact and runs unchanged once a disposable target
  and a real authorization authority exist;
* the companion safety property — refusal happens before any mutation — is
  asserted by an executable test in the same module.

Removing a marker from a test is only correct after the authorization
requirement named in the reason string is actually satisfied.
"""

from __future__ import annotations

import pytest

#: Why a destructive-success expectation cannot run today.  Names the missing
#: infrastructure precisely; do not shorten it to "skipped".
BLOCKED_REASON = (
    "BLOCKED (STEP1_6X Workstream A/B): this test asserts that destructive row "
    "cleanup SUCCEEDS, but evaluation.isolation refuses every cleanup execution "
    "until a genuine connection-bound lifecycle authorization exists. Requires a "
    "verified disposable PostgreSQL target plus a documented identity/privilege "
    "model (see backend/architecture/STEP1_6X_REMAINING_SAFETY_BLOCKERS_2026-10-13.md). "
    "The refusal gate must not be relaxed to make this pass."
)

#: Apply to an individual test that asserts destructive success.
requires_disposable_database = pytest.mark.skip(reason=BLOCKED_REASON)
