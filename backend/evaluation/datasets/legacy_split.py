"""Frozen copy of the v1 claim splitter (production behavior before 2026-10-18).

``answer_claims_v1`` was annotated against this extraction.  The production
splitter in :func:`generation.planning.split_claims` was later corrected to stop
splitting after honorifics/initialisms, which lowers the claim count on the same
recorded answers.  This module exists so the v1 evaluation can be re-run on its
original claim population instead of silently drifting.

Do not change this function: it is evidence, not implementation.  New datasets
must use ``generation.planning.split_claims`` and record the splitter version.
"""

from __future__ import annotations

import re

VERSION = "legacy-v1 (pre-abbreviation-fix, 2026-10-18)"


def split_claims(answer: str) -> list[str]:
    """Split generated prose into claim-sized sentences (frozen v1 behavior)."""
    text = answer.replace("\r\n", "\n").strip()
    if not text:
        return []
    pieces: list[str] = []
    for line in text.split("\n"):
        line = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s+", "", line).strip()
        if not line:
            continue
        for part in re.split(r"(?<=[.!?])\s+", line):
            part = part.strip()
            # A fragment that is only a citation marker is not a claim; counting
            # it would report an uncited claim that does not exist.
            if part and not re.fullmatch(r"\[\d{1,2}\]", part):
                pieces.append(part)
    return pieces
