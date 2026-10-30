"""Instruct-model answer generation for the stateful conversation path.

The provisioned generator (``generation.engine``, Flan-T5-base) is a seq2seq
summariser: it copies and condenses, which is why table and list questions are
resolved deterministically instead.  Structured 5/10/15-mark answers need an
**instruction-following** causal model, so this module adds one as an *opt-in*
engine:

* ``DOCUMIND_CONVERSATION_MODEL`` (or ``Settings.conversation_model``) names a
  provisioned local model or a Hugging Face id already in the local cache —
  for example ``Qwen/Qwen2.5-1.5B-Instruct``.
* When it is unset or cannot be loaded, :class:`ConversationModelUnavailable`
  is raised.  Nothing silently substitutes another model, and no other engine
  is described as this one.

Loading policy (device + quantisation)
--------------------------------------
One deterministic decision, made once per process and reported verbatim:

1. **CUDA usable and ``bitsandbytes`` importable** → ``load_in_4bit=True``
   (NF4, double quantisation, fp16 compute) with ``device_map="auto"``.  This
   is the only configuration intended for the 1.5B model inside 4 GB of VRAM.
2. **CUDA usable, ``bitsandbytes`` missing** → the unquantised ``float32`` **CPU**
   fallback.  It is deliberately *not* an unquantised GPU load: a 1.5B model in
   float32 is ~6 GB and would exceed the card instead of failing clearly.
3. **No usable CUDA** → ``float32`` CPU, exactly the behaviour this module had
   before 4-bit support existed.

``DOCUMIND_CONVERSATION_4BIT=0`` (or ``false``/``no``/``off``) forces the
fallback even on a CUDA machine.  Whatever is chosen is logged at load time and
returned by :func:`conversation_model_status`, including the reason for a
fallback, the measured ``torch.cuda.max_memory_allocated()`` peak (CUDA only)
and the real device/dtype.  Nothing here claims CUDA, 4-bit or a VRAM figure
that was not measured.

VRAM ceiling
------------
The card this project is developed on has 4 GiB, and the *accepted* budget for
this path is stricter than the card: **3.0 GiB** (:data:`VRAM_CEILING_MIB`).
The model must fit there with room for the desktop's own display memory, so the
ceiling is enforced, not merely documented:

* after the weights load, and again after every generation, the measured
  ``torch.cuda.max_memory_allocated()`` is compared with the ceiling;
* a measurement *above* it raises :class:`VramBudgetExceeded` (a
  :class:`ConversationModelUnavailable`, so the API returns 503 rather than an
  answer produced under a violated constraint) and unloads the weights;
* the context is capped (:data:`MAX_INPUT_TOKENS`, :data:`MAX_PROMPT_BLOCKS`,
  :data:`MAX_HISTORY_TURNS`), because the KV cache — not the text — is what
  grows with context;
* nothing is guessed: on CPU there is no VRAM figure and no check, and
  ``conversation_model_status`` reports ``vramPeakMiB: null`` rather than zero.

The allocator peak is not the whole card (CUDA context and bitsandbytes kernels
sit outside it); ``scripts/measure_conversation_vram.py`` also samples
``nvidia-smi``, which is the driver's own view.  Measured 2026-10-24 for
``Qwen/Qwen2.5-1.5B-Instruct`` in 4-bit NF4: 1156 MiB allocator / 1275 MiB
driver peak for a 15-mark answer (see the decision record).

The engine is serialised by a lock (one model instance is not guaranteed safe
for concurrent decoding), lazy (never at import time), and bounded (per-format
token budget, trimmed history, capped evidence, capped prompt tokens).
"""

from __future__ import annotations

import importlib.util
import logging
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from generation.planning import ABSTENTION_MARKER, classify_question, normalise_evidence_text
from generation.types import (
    AnswerFormat,
    EvidenceBlock,
    GenerationResult,
    GenerationUnavailableError,
)
from generation.verification import verify_with_mode

logger = logging.getLogger(__name__)

VRAM_CEILING_MIB = 3000.0
"""Hard, enforced ceiling for this path's measured CUDA allocator peak.

Not a preference: the development card has 4 GiB, the rest of the desktop needs
some of it, and a run above this figure is treated as a failure instead of an
answer.  Deliberately a constant rather than an environment knob — a limit that
can be raised on the command line does not constrain anything.
"""

FOUR_BIT_ENV = "DOCUMIND_CONVERSATION_4BIT"
"""Kill switch for 4-bit loading.  Unset/true/yes/on → 4-bit is attempted when
CUDA and ``bitsandbytes`` are both available; 0/false/no/off → never quantise."""

CONVERSATION_MODEL_ENV = "DOCUMIND_CONVERSATION_MODEL"
"""Model id or local directory for the instruct generator.  Unset → the
instruct path is unavailable and the caller keeps the existing engine."""

#: Decoder budget per answer format.  Bounds latency; it is not a claim that a
#: longer answer is a better answer (the plan still decides the depth cues).
MAX_NEW_TOKENS: dict[AnswerFormat, int] = {
    AnswerFormat.FIVE: 192,
    AnswerFormat.TEN: 384,
    AnswerFormat.FIFTEEN: 640,
}

#: Evidence blocks handed to an instruct prompt.  The causal window is much
#: larger than Flan-T5's 512 tokens, but the cost is attention over the prompt,
#: so this stays deliberately small.
MAX_PROMPT_BLOCKS = 6

#: Prompt-token cap.  Bounds the prefill transient (the LM head produces
#: ``tokens x vocab`` logits — ~1.2 GiB for 4096 tokens on this model) and the
#: KV cache, which are what actually grow with context on a 4 GB card.
#:
#: Measured 2026-10-24 on the RTX 3050 (15-mark budget, 640 new tokens forced):
#: 1440 prompt tokens → 1577 MiB driver peak; 2048 → 1815; 2560 → 2129;
#: 3072 → 2481; 4096 → 3433 MiB, i.e. **over** the 3000 MiB ceiling.  The cap is
#: therefore 2560, which leaves ~870 MiB of headroom at the worst case the code
#: permits.  The realistic prompt (6 blocks x 900 chars + 6 history turns) is
#: ~1440 tokens, so this cap does not truncate a normal answer's evidence.
MAX_INPUT_TOKENS = 2560

#: Characters per evidence block inside the prompt.
MAX_PROMPT_BLOCK_CHARS = 900

#: Previous turns replayed as chat history.  Multi-turn memory is bounded so one
#: long conversation cannot push the evidence out of the window.
MAX_HISTORY_TURNS = 6

#: Turn characters replayed per message.
MAX_HISTORY_CHARS = 600

#: Question characters kept in the prompt.  A pasted "question" of arbitrary
#: length would otherwise consume the whole prompt budget and be truncated
#: mid-sentence; the user's text is kept well inside the measured envelope.
MAX_QUESTION_CHARS = 1500

_SYSTEM_PROMPT = (
    "You are DocuMind, a document question-answering assistant. "
    "Answer using ONLY the numbered evidence provided. Never add outside "
    "knowledge, never invent numbers, names or units. "
    "Cite the evidence number in square brackets after each factual claim, e.g. [2]. "
    # The prompt shows each block's provenance label (document, page, section).
    # Measured 2026-10-22 with Qwen2.5-1.5B-Instruct in 4-bit: asked only to
    # "cite the number", the model also echoed the label into the answer
    # ("... 6 months, as stated in maintenance.pdf [1], page 4, section: ..."),
    # and the verifier correctly rejected it — "page 4" is a value absent from
    # the cited block.  Naming the label as forbidden text keeps the answer
    # attributable without relaxing any verifier threshold.
    "Name the evidence only by its number: do not repeat its document name, "
    "page or section in the answer. "
    f"If the evidence does not contain the answer, reply exactly {ABSTENTION_MARKER}."
)

_MARK_INSTRUCTION: dict[AnswerFormat, str] = {
    AnswerFormat.FIVE: (
        "This is a 5-mark answer: give the direct answer in one or two sentences."
    ),
    AnswerFormat.TEN: (
        "This is a 10-mark answer: give the answer, then a short explanation "
        "supported by the evidence. Use short paragraphs or a compact list."
    ),
    AnswerFormat.FIFTEEN: (
        "This is a 15-mark answer: use short labelled sections in this order — "
        "the direct answer, how or why it works, the evidence for each step, any "
        "limit the evidence states, and a one-sentence conclusion. "
        "Depth must come from the evidence, never from repetition."
    ),
}

_ANSWER_PREFIX_RE = re.compile(r"^(?:answer|response)\s*:\s*", re.IGNORECASE)


class ConversationModelUnavailable(GenerationUnavailableError):
    """The configured instruct model cannot be used.

    A subclass of :class:`GenerationUnavailableError` so the existing API error
    handling (HTTP 503 with the reason) applies unchanged.
    """


class VramBudgetExceeded(ConversationModelUnavailable):
    """The measured CUDA allocation exceeded :data:`VRAM_CEILING_MIB`.

    Distinct from a missing model: the model exists and ran, but on this device
    it does not fit the accepted budget.  It is raised instead of returning an
    answer so the constraint cannot be silently violated.
    """


def cuda_peak_mib() -> float | None:
    """Measured peak CUDA allocator usage for this process, or ``None``.

    ``None`` means *not measured* — no CUDA device, or torch cannot report it.
    It never means "zero VRAM", and callers must not print it as such.
    """
    try:
        import torch

        if not torch.cuda.is_available():
            return None
        return round(torch.cuda.max_memory_allocated() / (1024**2), 1)
    except Exception:  # pragma: no cover - depends on the torch build
        return None


def vram_within_ceiling(
    peak_mib: float | None, *, ceiling_mib: float = VRAM_CEILING_MIB
) -> bool:
    """Whether a measured peak is inside the ceiling.

    ``None`` (unmeasured, i.e. CPU) is treated as nothing to enforce — the
    ceiling is a GPU constraint, and a CPU run must not claim to have met it.
    """
    return peak_mib is None or float(peak_mib) <= float(ceiling_mib)


def enforce_vram_ceiling(
    peak_mib: float | None, *, phase: str, ceiling_mib: float = VRAM_CEILING_MIB
) -> None:
    """Raise when the measured peak is above the ceiling.

    ``phase`` names what had just finished ("loading the weights", "generating
    a 15-mark answer") so the failure is actionable rather than a bare number.
    """
    if vram_within_ceiling(peak_mib, ceiling_mib=ceiling_mib):
        return
    raise VramBudgetExceeded(
        f"measured CUDA peak {float(peak_mib):.0f} MiB exceeded the "
        f"{float(ceiling_mib):.0f} MiB ceiling after {phase}; refusing to use "
        "the conversation model on this device"
    )


@dataclass(frozen=True)
class LoadPlan:
    """The device/quantisation decision, and why it was taken.

    ``kind`` is ``"4bit"`` or ``"fp32-cpu"``.  The reason is user-visible in
    ``/api/health`` and in the voice socket's ``ready`` frame, so a fallback is
    never silent.
    """

    kind: str
    device: str
    dtype: str
    device_map: str | None
    reason: str


def four_bit_enabled() -> bool:
    """Whether 4-bit loading is allowed (default yes).

    Only consulted when CUDA and ``bitsandbytes`` are available; disabling it
    forces the float32 CPU path everywhere.
    """
    value = os.environ.get(FOUR_BIT_ENV)
    if value is None:
        return True
    return value.strip().lower() not in ("0", "false", "no", "off", "")


def bitsandbytes_available() -> bool:
    """Whether ``bitsandbytes`` is importable, without importing it."""
    return importlib.util.find_spec("bitsandbytes") is not None


def plan_loading() -> LoadPlan:
    """Choose the load configuration from the *actual* hardware state.

    Never raises: a torch that cannot report CUDA is treated as no CUDA.
    """
    try:
        import torch

        cuda = bool(torch.cuda.is_available())
    except Exception:  # pragma: no cover - torch is a hard dependency
        cuda = False

    quantise = four_bit_enabled()
    bnb = bitsandbytes_available()

    if cuda and quantise and bnb:
        return LoadPlan(
            kind="4bit",
            device="cuda",
            dtype="float16",
            device_map="auto",
            reason="CUDA is available and bitsandbytes is importable",
        )

    if cuda and not quantise:
        reason = f"4-bit loading is disabled ({FOUR_BIT_ENV})"
    elif cuda and not bnb:
        reason = "CUDA is available but bitsandbytes is not installed"
    else:
        reason = "CUDA is not available (CPU-only torch build or no usable device)"

    # Deliberately not an unquantised GPU load: a 1.5B model in float32 needs
    # ~6 GB, which would exhaust a 4 GB card instead of failing clearly.
    return LoadPlan(
        kind="fp32-cpu",
        device="cpu",
        dtype="float32",
        device_map=None,
        reason=reason,
    )


class _ModelState:
    def __init__(self) -> None:
        self.tokenizer = None
        self.model = None
        self.device: str | None = None
        self.dtype: str | None = None
        self.quantization: str | None = None
        self.plan: LoadPlan | None = None
        self.error: str | None = None

    @property
    def available(self) -> bool:
        return self.tokenizer is not None and self.model is not None


_state = _ModelState()
_load_lock = threading.Lock()
_generate_lock = threading.Lock()


def conversation_model_name() -> str:
    """Configured instruct model id, or ``""`` when the path is not enabled."""
    value = os.environ.get(CONVERSATION_MODEL_ENV)
    if value is None:
        try:
            from config import get_settings

            value = get_settings().conversation_model
        except Exception:  # pragma: no cover - settings are always importable
            value = ""
    return str(value or "").strip()


def _resolve_source(name: str) -> str:
    """Return a loadable source for ``name``.

    A local directory is used as given.  Otherwise the Hub id is used, but with
    ``local_files_only`` semantics: the weights must already be in the local
    cache.  A request must never trigger a download.
    """
    path = Path(name)
    if path.is_dir():
        return str(path)
    return name


def _load() -> _ModelState:
    """Load the instruct model once; never raises, records the reason."""
    global _state
    if _state.available or _state.error is not None:
        return _state

    name = conversation_model_name()
    if not name:
        _state = _ModelState()
        _state.error = (
            f"no instruct model configured (set {CONVERSATION_MODEL_ENV}); "
            "the existing generator remains in use"
        )
        return _state

    with _load_lock:
        if _state.available or _state.error is not None:
            return _state

        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer

            source = _resolve_source(name)
            plan = plan_loading()

            logger.info(
                "Conversation model hardware: cuda=%s bitsandbytes=%s 4bit_enabled=%s "
                "-> plan=%s device=%s dtype=%s (%s)",
                torch.cuda.is_available(),
                bitsandbytes_available(),
                four_bit_enabled(),
                plan.kind,
                plan.device,
                plan.dtype,
                plan.reason,
            )

            load_kwargs: dict = {"local_files_only": True}
            if plan.kind == "4bit":
                from transformers import BitsAndBytesConfig

                load_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_compute_dtype=torch.float16,
                )
                load_kwargs["device_map"] = plan.device_map
                load_kwargs["dtype"] = torch.float16
            else:
                load_kwargs["dtype"] = torch.float32

            tokenizer = AutoTokenizer.from_pretrained(source, local_files_only=True)
            model = AutoModelForCausalLM.from_pretrained(source, **load_kwargs)
            model.eval()
            if plan.device_map is None:
                model.to(plan.device)

            # Enforce the ceiling on the weights themselves before any answer is
            # attempted: a model that does not fit must be reported, not kept
            # resident and tried anyway.  On CPU this is ``None`` (no check).
            peak = cuda_peak_mib()
            try:
                enforce_vram_ceiling(peak, phase="loading the weights")
            except VramBudgetExceeded:
                logger.error(
                    "Conversation model %s exceeds the VRAM ceiling (%s MiB); "
                    "unloading it",
                    name,
                    peak,
                )
                del model
                if plan.device == "cuda":
                    torch.cuda.empty_cache()
                raise

            _state = _ModelState()
            _state.tokenizer = tokenizer
            _state.model = model
            _state.plan = plan
            _state.device = plan.device
            _state.dtype = plan.dtype
            _state.quantization = "4bit-nf4" if plan.kind == "4bit" else None
            logger.info(
                "Instruct conversation model ready: %s (%s, %s%s)",
                source,
                plan.device,
                plan.dtype,
                ", 4-bit NF4" if plan.kind == "4bit" else "",
            )
        except Exception as exc:  # pragma: no cover - depends on local weights
            _state = _ModelState()
            _state.error = f"{type(exc).__name__}: {exc}"
            logger.warning("Instruct conversation model unavailable (%s): %s", name, _state.error)

    return _state


def is_conversation_model_available() -> bool:
    """Whether an instruct model is configured *and* loadable.

    Loads on first call (the caller is about to generate anyway); health checks
    must use :func:`conversation_model_status` instead.
    """
    return bool(conversation_model_name()) and _load().available


def conversation_model_status() -> dict:
    """Honest status, without loading weights.

    ``vramPeakMiB`` is ``torch.cuda.max_memory_allocated()`` — a measured
    allocator peak, reported only when a CUDA device is actually in use.  It is
    ``None`` on CPU, never a guess.

    When no instruct model is configured **and none has been loaded**, the
    hardware plan is not probed at all: describing a device this process will
    never use would cost the multi-second ``import torch`` on every first
    ``/api/health`` or WebSocket handshake (measured: 4.3 s, during which the
    async event loop was blocked).  Unknown stays unknown (``None``) rather than
    being guessed.
    """
    configured = conversation_model_name()
    if not configured and not _state.available:
        return {
            "configured": False,
            "model": None,
            "loaded": False,
            "device": None,
            "dtype": None,
            "quantization": None,
            # Requires importing torch, which is exactly what is skipped here.
            "cudaAvailable": None,
            "plan": None,
            "planReason": "not probed: no conversation model is configured",
            "bitsandbytesAvailable": bitsandbytes_available(),
            "vramPeakMiB": None,
            "vramCeilingMiB": VRAM_CEILING_MIB,
            "vramWithinCeiling": None,
            "error": None,
        }

    plan = plan_loading()

    vram_peak = cuda_peak_mib() if plan.device == "cuda" else None

    return {
        "configured": bool(configured),
        "model": configured or None,
        "loaded": _state.available,
        "device": _state.device or plan.device,
        "dtype": _state.dtype or plan.dtype,
        "quantization": _state.quantization,
        "cudaAvailable": plan.device == "cuda",
        "bitsandbytesAvailable": bitsandbytes_available(),
        "plan": plan.kind,
        "planReason": plan.reason,
        "vramPeakMiB": vram_peak,
        "vramCeilingMiB": VRAM_CEILING_MIB,
        "vramWithinCeiling": (
            None if vram_peak is None else vram_within_ceiling(vram_peak)
        ),
        "error": _state.error,
    }


def _history_messages(history: Sequence[object]) -> list[dict[str, str]]:
    """Last few turns as chat messages, bounded in count and length."""
    messages: list[dict[str, str]] = []
    for turn in list(history)[-MAX_HISTORY_TURNS:]:
        if isinstance(turn, dict):
            role = str(turn.get("role", "") or "").strip().lower()
            content = str(turn.get("content", "") or "").strip()
        else:
            role = str(getattr(turn, "role", "") or "").strip().lower()
            content = str(getattr(turn, "content", "") or "").strip()
        if role not in ("user", "assistant") or not content:
            continue
        messages.append({"role": role, "content": content[:MAX_HISTORY_CHARS]})
    return messages


def build_messages(
    question: str,
    blocks: Sequence[EvidenceBlock],
    *,
    answer_format: AnswerFormat | str | int | None = None,
    history: Sequence[object] = (),
) -> list[dict[str, str]]:
    """Compose the chat messages for one grounded answer."""
    fmt = AnswerFormat.coerce(answer_format)
    # The block's provenance label is *not* placed in the prompt.  Measured
    # 2026-10-22 with Qwen2.5-1.5B-Instruct in 4-bit: with the label in the
    # evidence line ("[1] (maintenance.pdf, page 4, section: Calibration) ...")
    # the model copied it into every answer, and the verifier correctly
    # rejected those claims — "page 4" is a value the cited block does not
    # contain.  The label is shown to the user from ``blocks`` metadata; the
    # model only needs the number and the text it may quote.
    evidence_lines = [
        f"[{block.index}] {normalise_evidence_text(block.content[:MAX_PROMPT_BLOCK_CHARS])}"
        for block in blocks[:MAX_PROMPT_BLOCKS]
    ]
    context = "\n".join(evidence_lines) if evidence_lines else "(no evidence retrieved)"

    user_content = (
        f"Evidence:\n{context}\n\n"
        f"Question type: {classify_question(question)}\n"
        f"{_MARK_INSTRUCTION[fmt]}\n\n"
        f"Question: {question.strip()[:MAX_QUESTION_CHARS]}"
    )

    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        *_history_messages(history),
        {"role": "user", "content": user_content},
    ]


def _clean(text: str) -> str:
    collapsed = " ".join(text.replace("\r", " ").split())
    return _ANSWER_PREFIX_RE.sub("", collapsed).strip()


def generate_conversation_answer(
    question: str,
    blocks: Sequence[EvidenceBlock],
    *,
    answer_format: AnswerFormat | str | int | None = None,
    history: Sequence[object] = (),
) -> GenerationResult:
    """Generate a grounded, verified answer with the instruct model.

    Raises :class:`ConversationModelUnavailable` when no instruct model is
    configured or it cannot be loaded.  An abstention is a normal result
    (``abstained=True``), not an error.
    """
    fmt = AnswerFormat.coerce(answer_format)
    state = _load()
    if not state.available:
        raise ConversationModelUnavailable(
            state.error or "the instruct conversation model is unavailable"
        )

    tokenizer, model = state.tokenizer, state.model
    messages = build_messages(question, blocks, answer_format=fmt, history=history)

    prompt = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )

    started = time.perf_counter()
    with _generate_lock:
        import torch

        encoded = tokenizer(
            prompt, return_tensors="pt", truncation=True, max_length=MAX_INPUT_TOKENS
        )
        # With ``device_map="auto"`` the input must go to the embedding device,
        # which is not necessarily ``model.device`` for a sharded model.
        if state.plan is not None and state.plan.device_map is not None:
            input_device = next(model.parameters()).device
        else:
            input_device = torch.device(state.plan.device if state.plan else "cpu")
        encoded = {key: value.to(input_device) for key, value in encoded.items()}
        with torch.no_grad():
            output = model.generate(
                **encoded,
                max_new_tokens=MAX_NEW_TOKENS[fmt],
                do_sample=False,
                repetition_penalty=1.05,
                pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
            )
        prompt_length = encoded["input_ids"].shape[1]
        new_tokens = output[0][prompt_length:]
        text = tokenizer.decode(new_tokens, skip_special_tokens=True)
    latency_ms = int((time.perf_counter() - started) * 1000)

    # The ceiling is checked again after decoding: the KV cache and the generated
    # tokens are the parts that grow with context, and a run that crossed the
    # ceiling must fail rather than present an answer under a violated budget.
    enforce_vram_ceiling(cuda_peak_mib(), phase=f"generating a {fmt.marks}-mark answer")

    cleaned = _clean(text)
    abstained = not cleaned or ABSTENTION_MARKER.lower() in cleaned.lower()
    if abstained:
        cleaned = ""

    report = verify_with_mode(cleaned, blocks, question=question)

    return GenerationResult(
        answer=cleaned,
        abstained=abstained,
        verification=report,
        model=conversation_model_name(),
        marks=fmt.marks,
        latency_ms=latency_ms,
        prompt=prompt,
    )


__all__ = [
    "CONVERSATION_MODEL_ENV",
    "MAX_HISTORY_TURNS",
    "MAX_INPUT_TOKENS",
    "MAX_NEW_TOKENS",
    "MAX_PROMPT_BLOCKS",
    "MAX_QUESTION_CHARS",
    "VRAM_CEILING_MIB",
    "ConversationModelUnavailable",
    "VramBudgetExceeded",
    "build_messages",
    "cuda_peak_mib",
    "enforce_vram_ceiling",
    "vram_within_ceiling",
    "conversation_model_name",
    "conversation_model_status",
    "generate_conversation_answer",
    "is_conversation_model_available",
]
