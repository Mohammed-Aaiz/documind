"""Shared helpers for the Phase 4F dataset quality gates.

Canonical owner for the code that ``balance_gate``, ``quality_gate`` and
``freeze_gate`` previously copy-pasted: the ``QAExample`` record, the JSONL /
JSON io helpers, the text-span finder and the SHA-256 digest helpers.

This is pipeline infrastructure, not a general-purpose utility module. Only add
a helper here when more than one gate genuinely shares it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class QAExample:
    example_id: str
    source: str
    document_id: str
    question: str
    context: str
    answer: str
    answer_start: int
    answer_end: int
    question_kind: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Text spans
# ---------------------------------------------------------------------------
def find_span(text: str, answer: str) -> tuple[int, int]:
    """Locate ``answer`` in ``text``, falling back to a case-insensitive search.

    Returns ``(-1, -1)`` when the answer cannot be located.
    """
    if not answer:
        return 0, 0
    idx = text.find(answer)
    if idx >= 0:
        return idx, idx + len(answer)
    idx = text.lower().find(answer.lower())
    if idx >= 0:
        return idx, idx + len(answer)
    return -1, -1


# ---------------------------------------------------------------------------
# JSONL / JSON io
# ---------------------------------------------------------------------------
def load_jsonl(path: Path) -> list[QAExample]:
    examples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data = json.loads(line)
                examples.append(QAExample(**data))
    return examples


def save_jsonl(examples: list[QAExample], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex.to_dict(), ensure_ascii=False) + "\n")


def save_json(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# SHA-256 digests
#
# The text and bytes variants are deliberately kept separate: the gates hash
# UTF-8 text in some places and raw file bytes in others, and those digests are
# recorded inside frozen audit artifacts.
# ---------------------------------------------------------------------------
def sha256_short_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def sha256_full_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_short_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]
