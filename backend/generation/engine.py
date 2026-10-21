"""Local, offline generative engine (Flan-T5-base, CPU).

Approved direction: ``google/flan-t5-base`` — a local seq2seq model that runs on
CPU with no external API and no data egress.  It is **additive**: the extractive
DistilBERT QA model stays the default engine and the comparison baseline.

Operational properties:

* **Lazy** — the model is loaded on first use, never at import time, so the API
  starts (and the SQLite test suite runs) without a multi-second model load.
* **Offline-safe** — weights come from the local Hugging Face cache once
  provisioned; a missing model yields an explicit
  :class:`GenerationUnavailableError`, never a silent substitute.
* **Bounded** — the prompt is fitted to the encoder window by dropping the
  lowest-ranked evidence blocks (never by truncating the question), and
  decoding is capped per answer format.
* **Serialised** — generation holds a lock, because one model instance is not
  guaranteed safe for concurrent decoding.
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from typing import Sequence

from generation.planning import ABSTENTION_MARKER, build_prompt
from generation.types import (
    AnswerFormat,
    AnswerPlan,
    EvidenceBlock,
    GenerationResult,
    GenerationUnavailableError,
)

logger = logging.getLogger(__name__)

GENERATOR_MODEL_ENV = "DOCUMIND_GENERATOR_MODEL"
"""Model id or local directory.  Default: ``google/flan-t5-base``."""

GENERATOR_ENABLED_ENV = "DOCUMIND_GENERATOR_ENABLED"
"""Kill switch.  Unset/true/yes/on → enabled; 0/false/no/off → disabled."""

DEFAULT_GENERATOR_MODEL = "google/flan-t5-base"

#: Decoding parameters.  Kept in one mutable mapping so a configuration
#: experiment can measure an alternative without editing the inference path
#: (``evaluation/experiments/run_generation_config_sweep.py``).  Production
#: values are the measured baseline (beams=4, no repeated 3-gram).
DECODE_PARAMS: dict[str, object] = {
    "num_beams": 4,
    "no_repeat_ngram_size": 3,
    "early_stopping": True,
}

#: Flan-T5's encoder window is 512 tokens; leave room for the decoder's start
#: and any tokenizer drift.
MAX_INPUT_TOKENS = 480


def generator_model_name() -> str:
    return os.environ.get(GENERATOR_MODEL_ENV, DEFAULT_GENERATOR_MODEL).strip() or DEFAULT_GENERATOR_MODEL


def generator_enabled() -> bool:
    value = os.environ.get(GENERATOR_ENABLED_ENV)
    if value is None:
        return True
    return value.strip().lower() not in ("0", "false", "no", "off", "")


class _ModelState:
    """Loaded model/tokenizer plus the load error, if any."""

    def __init__(self) -> None:
        self.tokenizer = None
        self.model = None
        self.error: str | None = None

    @property
    def available(self) -> bool:
        return self.tokenizer is not None and self.model is not None


_state = _ModelState()
_load_lock = threading.Lock()
_generate_lock = threading.Lock()


def _load() -> _ModelState:
    """Load the model once.  Never raises; records the error instead."""
    global _state
    if _state.available or _state.error is not None:
        return _state

    with _load_lock:
        if _state.available or _state.error is not None:
            return _state

        model_name = generator_model_name()
        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            logger.info("Loading generative model %s (first use)", model_name)
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
            model.eval()
            _state = _ModelState()
            _state.tokenizer = tokenizer
            _state.model = model
            logger.info("Generative model ready: %s", model_name)
        except Exception as exc:  # pragma: no cover - depends on local weights
            _state = _ModelState()
            _state.error = f"{type(exc).__name__}: {exc}"
            logger.warning("Generative model unavailable (%s): %s", model_name, _state.error)

    return _state


def is_generator_available() -> bool:
    """Whether a generation call can be served right now."""
    if not generator_enabled():
        return False
    return _load().available


def get_generator_status() -> dict:
    """Honest status for ``/api/health`` and the API's 503 body.

    Deliberately does **not** load the model: a health check must stay cheap.
    ``available`` therefore reports the already-loaded state, and ``provisioned``
    is stated separately so a not-yet-loaded model is not misreported as broken.
    """
    enabled = generator_enabled()
    return {
        "enabled": enabled,
        "available": _state.available and enabled,
        "loaded": _state.available,
        "model": generator_model_name(),
        "error": _state.error if enabled else "generation disabled by DOCUMIND_GENERATOR_ENABLED",
    }


def _token_count(tokenizer, text: str) -> int:
    return len(tokenizer(text, add_special_tokens=True)["input_ids"])


def fit_prompt(
    question: str,
    plan: AnswerPlan,
    blocks: Sequence[EvidenceBlock],
    tokenizer=None,
) -> tuple[str, list[EvidenceBlock]]:
    """Drop the lowest-ranked evidence until the prompt fits the encoder.

    Returns the prompt and the blocks it actually contains, so reported
    citations can be restricted to evidence that was really supplied.  The
    question is never truncated; a question that cannot fit raises.
    """
    kept = list(blocks)
    while True:
        prompt = build_prompt(question, plan, kept)
        if tokenizer is None:
            return prompt, kept
        if _token_count(tokenizer, prompt) <= MAX_INPUT_TOKENS:
            return prompt, kept
        if not kept:
            raise GenerationUnavailableError(
                "The question does not fit the generative model's input window."
            )
        kept.pop()


#: Evidence-line prefix printed in the prompt: ``[1] (document.pdf, page 2)``.
#: Flan-T5-base sometimes copies the numbered context line verbatim, so the
#: answer started with that prefix instead of an answer (measured: "[1]
#: (benchmark-context) Key Financial Highlights Revenue: ..." for five rows).
#: Removing an echoed *prompt marker* is formatting only: no answer text is
#: changed, and a real citation inside the answer is untouched.
_EVIDENCE_ECHO_RE = re.compile(r"^\[\d{1,2}\]\s*\([^)]{0,120}\)\s*")


def _clean_output(text: str) -> str:
    """Normalise decoder whitespace and drop an echoed prompt marker."""
    normalised = " ".join(text.replace("\r", " ").replace("\n", " ").split())
    return _EVIDENCE_ECHO_RE.sub("", normalised).strip()


ABSTENTION_PHRASES = (
    ABSTENTION_MARKER.lower(),
    "unanswerable",
    "insufficient evidence",
    "not enough information",
    "no information",
    "cannot be answered",
    "can't be answered",
    "context does not",
)


def is_abstention(text: str) -> bool:
    """Whether the model declined for lack of evidence.

    Flan-T5-base does not always emit the canonical marker, so the equivalent
    short phrases it actually produces are recognised explicitly rather than
    being returned to the user as if they were an answer.
    """
    lowered = text.lower()
    return any(phrase in lowered for phrase in ABSTENTION_PHRASES)


def generate(
    question: str,
    blocks: Sequence[EvidenceBlock],
    *,
    answer_format: AnswerFormat | str | int | None = None,
    plan: AnswerPlan | None = None,
) -> GenerationResult:
    """Generate a grounded answer from ``blocks``.

    Raises :class:`GenerationUnavailableError` when the model cannot be loaded.
    An abstention is a normal result (``abstained=True``), not an error.
    """
    from generation.planning import plan_answer

    fmt = AnswerFormat.coerce(answer_format)
    answer_plan = plan or plan_answer(question, fmt)

    if not generator_enabled():
        raise GenerationUnavailableError("Generation is disabled by DOCUMIND_GENERATOR_ENABLED.")

    state = _load()
    if not state.available:
        raise GenerationUnavailableError(state.error or "Generative model is unavailable.")

    tokenizer, model = state.tokenizer, state.model
    prompt, kept = fit_prompt(question, answer_plan, blocks, tokenizer)

    started = time.perf_counter()
    with _generate_lock:
        import torch

        encoded = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=MAX_INPUT_TOKENS)
        with torch.no_grad():
            output = model.generate(
                **encoded,
                max_new_tokens=answer_plan.max_new_tokens,
                **DECODE_PARAMS,
            )
        text = tokenizer.decode(output[0], skip_special_tokens=True)
    latency_ms = int((time.perf_counter() - started) * 1000)

    cleaned = _clean_output(text)
    abstained = is_abstention(cleaned)
    if abstained:
        cleaned = ""

    # Verification only sees the evidence actually supplied to the model.
    from generation.verification import verify_with_mode

    report = verify_with_mode(cleaned, kept, question=question)

    return GenerationResult(
        answer=cleaned,
        abstained=abstained,
        verification=report,
        model=generator_model_name(),
        marks=answer_plan.marks,
        latency_ms=latency_ms,
        prompt=prompt,
    )
