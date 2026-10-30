"""Offline OCR for pages that carry no usable text layer.

Why this module exists
----------------------
A scanned PDF — or the scanned pages of a mixed one — has no text layer, so
native extraction returns nothing for those pages and the document is reported
as having "no text layer".  Before this module existed that was the end of the
story: the page was unaccounted and its content could never be retrieved or
cited.  This module reads such a page and hands the recognised text back to
``documents.processing``, which treats it exactly like native text — same
elements, same chunking, same embedding path — so nothing downstream has to
know where the characters came from beyond the page they belong to.

Engine choice (recorded, measured — not assumed)
-----------------------------------------------
RapidOCR on the ONNX Runtime.  The evidence is in
``backend/architecture/DOCUMIND_OCR_ENGINE_DECISION_2026-10-24.md`` and in the
Phase 1a decision record's Addendum 1/2 (``DOCUMIND_PHASE1A_DECISION_RECORD_2026-10-15.md``
§14, §17), measured on this machine:

* ``rapidocr 3.10.0`` ships its three ONNX models inside the wheel (31.75 MB),
  needs no system binary, and runs offline — verified with the proxy pointed at
  a dead port.
* On a 300-dpi digital-quality scan it measured **CER 0.000**, ~2.5-3 s/page,
  ~1.2 GB peak RSS, using the ``onnxruntime`` this project already shipped.
* EasyOCR, measured on the same corpus, needed 4.3-4.5 GB and ~15 s/page for a
  marginally lower CER — more device for no useful gain.
* Vision-language OCR (PaddleOCR-VL and its peers) scores higher on layout
  benchmarks but needs a GPU and a much heavier dependency; it is recorded as a
  future option, not a silent substitution.

Latency is bounded, never unbounded: one page at a time on a single worker,
``PAGE_TIMEOUT_S`` per page and ``DOCUMENT_BUDGET_S`` per document.  A document
that exhausts its budget is reported ``partial`` with the remaining pages
unaccounted — it is never silently completed.

Orientation — measured behaviour, deterministic correction
----------------------------------------------------------
RapidOCR does not reliably recover a rotated page.  Measured on a 300-dpi page
rotated in 90-degree steps (same probe as the decision record):

===========  =================  ===================================
Rotation     median box w/h     outcome
===========  =================  ===================================
0 (upright)  12.6               CER 0.000, confidence 0.994
90            0.08               CER 0.551, confidence 0.861
180          12.5                CER 0.785, confidence 0.785
270           0.07               CER 0.785, confidence 0.998
===========  =================  ===================================

Two facts follow from that table, and they are what this module uses:

* **Box geometry tells you whether the page is sideways.**  A sideways line is
  detected as a tall box (w/h < 1); an upright one as a wide box.  Confidence
  alone would not have caught the 270-degree case (0.998 on wrong text).
* **Per-line confidence tells you whether an upright page is upside down —
  provided the first pass does not pre-empt the question.**  The engine ships a
  line-angle classifier that silently flips upside-down line crops, which
  repairs the text but reverses the reading order and hides the defect
  (measured: 0.991 minimum confidence with the classifier, on a page whose
  lines came out bottom-to-top).  The first pass therefore runs **without** the
  classifier: an upright page is unaffected (measured 0.998 minimum), while an
  upside-down page garbles and collapses (0.623 minimum).  The correction pass
  then reads at 180 degrees with the classifier on and wins outright
  (0.999 minimum).

So: if the boxes are tall, try the two 90-degree rotations and keep the one
that reads; if any line's confidence is low, try 180 degrees and keep the
better reading.  A noisy but upright scan can therefore cost two passes — the
second one reads worse and is discarded — while an ordinary scan costs one.
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass
from typing import Any, Sequence

logger = logging.getLogger(__name__)

#: Rendering resolution for a page that is about to be OCR'd.  Measured: 150 dpi
#: and 300 dpi agreed on the clean-scan corpus, and 300 dpi is where the
#: one-line-loss page and the layout-heavy page reached CER 0.000.  Higher
#: resolutions cost memory and time for no measured accuracy gain.
DEFAULT_DPI = 300

#: Hard ceiling on the rendered page area (pixels) so a pathological page cannot
#: exhaust memory before the timeout applies. A4 at 300 dpi is ~8.7 Mpx;
#: preserve that measured OCR resolution while bounding oversized scans.
MAX_PIXELS = 12_000_000

# The detector only locates lines; recognition still crops the original RGB
# image. RapidOCR's default ``min:736`` does not downsize large pages, making
# detector activation memory grow with a 300-dpi page's full area. Cap the
# detector longest side while retaining original-resolution glyph crops.
OCR_RUNTIME_PARAMS = {
    "Det.limit_type": "max",
    "Det.limit_side_len": 1536,
    "Rec.rec_batch_num": 2,
    "EngineConfig.onnxruntime.intra_op_num_threads": 2,
    "EngineConfig.onnxruntime.inter_op_num_threads": 1,
    "EngineConfig.onnxruntime.enable_cpu_mem_arena": False,
}

#: One page's OCR work must finish within this many seconds, or the page is
#: reported as failed and the document is not completed by it.
PAGE_TIMEOUT_S = 25.0

#: A document's total OCR work must finish within this many seconds.  Real scans
#: measured ~2.5-3 s/page, so this is roughly 60 pages; beyond it the remaining
#: pages stay unaccounted and the document is ``partial``.
DOCUMENT_BUDGET_S = 180.0

#: A recognised line below this confidence is dropped.  It is a floor against
#: noise, not a quality gate: measured scores on real text were 0.99+.
MIN_LINE_CONFIDENCE = 0.30

#: Lowest line confidence that still counts as a clean reading.  A page whose
#: worst line falls below it may be upside down, so a 180-degree retry is made
#: and the better reading kept.  Measured on the same page, first pass without
#: the line-angle classifier: minimum 0.998 upright, 0.623 upside down.
UPSIDE_DOWN_LINE_CONFIDENCE = 0.90

#: Median box width/height below this means the text lines are vertical, i.e.
#: the page is sideways.  Measured: 12.6 upright, 0.07-0.08 sideways.
VERTICAL_BOX_ASPECT = 1.0

ENGINE_NAME = "rapidocr"


class OcrUnavailable(RuntimeError):
    """The configured OCR engine cannot run here (missing package or models)."""


class OcrBudgetExhausted(RuntimeError):
    """The document's OCR time budget is spent; this page was not read."""


class OcrPageFailed(RuntimeError):
    """OCR ran on the page and did not produce usable text."""


@dataclass(frozen=True)
class OcrPolicy:
    """What OCR is allowed to do for one document.

    ``engine="off"`` is a real, supported configuration: the pipeline then
    reports pages as having no readable text layer instead of attempting OCR.
    """

    engine: str = ENGINE_NAME
    dpi: int = DEFAULT_DPI
    page_timeout_s: float = PAGE_TIMEOUT_S
    budget_s: float = DOCUMENT_BUDGET_S

    @property
    def enabled(self) -> bool:
        return self.engine.strip().lower() not in ("", "off", "none", "disabled")

    @classmethod
    def disabled(cls) -> "OcrPolicy":
        return cls(engine="off")

    @classmethod
    def from_settings(cls) -> "OcrPolicy":
        """Build the policy from application settings, without importing cycles."""
        try:
            from config import get_settings

            settings = get_settings()
        except Exception:  # pragma: no cover - settings are importable in practice
            return cls()
        return cls(
            engine=settings.ocr_engine,
            dpi=settings.ocr_dpi,
            page_timeout_s=settings.ocr_page_timeout_seconds,
            budget_s=settings.ocr_document_budget_seconds,
        )


@dataclass(frozen=True)
class OcrPageResult:
    """What OCR recovered from one page — facts, no estimates."""

    text: str
    """Recognised lines joined by newlines, in reading order."""

    mean_confidence: float
    """Mean confidence of the kept lines; 0.0 when nothing was kept."""

    lines: int
    seconds: float
    rotation: int
    """Degrees by which the page had to be rotated to be read (0/90/180/270)."""

    engine: str
    engine_version: str
    regions: tuple[dict, ...] = ()
    """Detected text-line boxes in the original page's normalized coordinates."""


# ---------------------------------------------------------------------------
# Engine (one process-wide instance; construction is cheap, inference loads it)
# ---------------------------------------------------------------------------

_engine: Any = None
_engine_version: str = "unknown"
_engine_lock = threading.Lock()
_executor: ThreadPoolExecutor | None = None
_executor_lock = threading.Lock()


def _get_executor() -> ThreadPoolExecutor:
    """One worker: OCR is CPU-bound, and serialising it bounds peak memory."""
    global _executor
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ocr")
        return _executor


def ocr_available() -> bool:
    """Whether an OCR engine can be imported here.  Never raises."""
    try:
        import rapidocr  # noqa: F401
    except Exception:
        return False
    return True


def _get_engine() -> Any:
    """The shared engine, or raise :class:`OcrUnavailable`."""
    global _engine, _engine_version
    with _engine_lock:
        if _engine is not None:
            return _engine
        try:
            from rapidocr import RapidOCR
        except Exception as exc:  # pragma: no cover - exercised by the unavailable path
            raise OcrUnavailable(f"rapidocr is not installed: {exc}") from exc
        try:
            _engine = RapidOCR(params=dict(OCR_RUNTIME_PARAMS))
        except Exception as exc:  # pragma: no cover - model provisioning failure
            raise OcrUnavailable(f"rapidocr could not be initialised: {exc}") from exc
        try:
            from importlib.metadata import version

            _engine_version = version("rapidocr")
        except Exception:  # pragma: no cover - metadata absent in an editable install
            _engine_version = "unknown"
        logger.info("OCR engine ready: %s %s", ENGINE_NAME, _engine_version)
        return _engine


def reset_engine_for_tests() -> None:
    """Drop the cached engine.  Tests only; production loads it once."""
    global _engine, _engine_version
    with _engine_lock:
        _engine = None
        _engine_version = "unknown"


# ---------------------------------------------------------------------------
# Reading one page
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Pass:
    text: str
    lines: int
    mean_confidence: float
    min_confidence: float
    rotation: int
    sideways: bool
    regions: tuple[dict, ...] = ()


def _rotate(image: Any, degrees: int) -> Any:
    """Rotate a numpy image counter-clockwise by ``degrees`` (0/90/180/270)."""
    import numpy as np

    steps = {0: 0, 90: 1, 180: 2, 270: 3}[degrees]
    return np.ascontiguousarray(np.rot90(image, steps))


def _median_box_aspect(output: Any) -> float:
    """Median width/height of the recognised line boxes; 0.0 when none."""
    boxes = getattr(output, "boxes", None)
    if boxes is None or len(boxes) == 0:
        return 0.0
    import numpy as np

    arr = np.asarray(boxes, dtype=float)
    widths = arr[:, 1, 0] - arr[:, 0, 0]
    heights = arr[:, 3, 1] - arr[:, 0, 1]
    ratios = widths / np.maximum(heights, 1e-6)
    return float(np.median(ratios))


def _read_pass(
    engine: Any, image: Any, rotation: int, *, use_cls: bool = True
) -> _Pass:
    """Run the engine once on ``image`` and reduce its output to a pass.

    ``use_cls`` toggles the engine's own line-angle classifier.  The first pass
    disables it on purpose (see the module docstring): with it on, an
    upside-down page is silently repaired line by line and the reversed reading
    order can no longer be detected.
    """
    output = engine(image, use_cls=use_cls)
    texts: Sequence[str] = getattr(output, "txts", None) or ()
    scores: Sequence[float] = getattr(output, "scores", None) or ()

    kept: list[str] = []
    kept_scores: list[float] = []
    boxes = getattr(output, "boxes", None)
    regions = []
    height, width = image.shape[:2]
    for line_index, (text, score) in enumerate(zip(texts, scores)):
        cleaned = " ".join(str(text).split())
        if not cleaned:
            continue
        if float(score) < MIN_LINE_CONFIDENCE:
            continue
        kept.append(cleaned)
        kept_scores.append(float(score))
        if boxes is not None and line_index < len(boxes) and len(regions) < 1500:
            points = []
            reading_points = []
            for px, py in boxes[line_index]:
                x, y = float(px) / width, float(py) / height
                reading_points.append((max(0., min(1., x)), max(0., min(1., y))))
                if rotation == 90:
                    x, y = 1 - y, x
                elif rotation == 180:
                    x, y = 1 - x, 1 - y
                elif rotation == 270:
                    x, y = y, 1 - x
                points.append((max(0., min(1., x)), max(0., min(1., y))))
            if points:
                regions.append({"id": f"ocr-{line_index}", "kind": "text", "text": cleaned,
                                "confidence": round(float(score), 4),
                                "reading_bbox": [min(p[0] for p in reading_points), min(p[1] for p in reading_points),
                                                 max(p[0] for p in reading_points), max(p[1] for p in reading_points)],
                                "bbox": [min(p[0] for p in points), min(p[1] for p in points),
                                         max(p[0] for p in points), max(p[1] for p in points)]})

    mean_confidence = sum(kept_scores) / len(kept_scores) if kept_scores else 0.0
    min_confidence = min(kept_scores) if kept_scores else 0.0
    aspect = _median_box_aspect(output)
    return _Pass(
        text="\n".join(kept),
        lines=len(kept),
        mean_confidence=mean_confidence,
        min_confidence=min_confidence,
        rotation=rotation,
        sideways=aspect < VERTICAL_BOX_ASPECT,
        regions=tuple(regions),
    )


def _read_page(engine: Any, image: Any, policy: OcrPolicy) -> OcrPageResult:
    """OCR one page, correcting orientation as measured above."""
    started = time.monotonic()
    first = _read_pass(engine, image, 0, use_cls=False)
    best = first
    best_image = image

    if first.sideways:
        # The lines are vertical: the page is sideways.  Both candidates are
        # read and the better one wins — box geometry cannot tell 90 from 270.
        candidates = []
        for degrees in (90, 270):
            rotated = _rotate(image, degrees)
            passed = _read_pass(engine, rotated, degrees)
            candidates.append((passed, rotated))
            if not passed.sideways:
                break
        readable = [c for c in candidates if not c[0].sideways]
        pool = readable or candidates
        best, best_image = max(pool, key=lambda c: c[0].mean_confidence)

    if best.min_confidence < UPSIDE_DOWN_LINE_CONFIDENCE:
        # Compare worst-line first, then mean: the reading that has no poor line
        # wins even when both means are high.  Measured on an upside-down page:
        # worst line 0.623 as rendered vs 0.999 once flipped.
        flipped_image = _rotate(best_image, 180)
        flipped = _read_pass(engine, flipped_image, (best.rotation + 180) % 360)
        if (flipped.min_confidence, flipped.mean_confidence) > (
            best.min_confidence,
            best.mean_confidence,
        ):
            best = flipped

    return OcrPageResult(
        text=best.text,
        mean_confidence=round(best.mean_confidence, 4),
        lines=best.lines,
        seconds=round(time.monotonic() - started, 3),
        rotation=best.rotation,
        engine=ENGINE_NAME,
        engine_version=_engine_version,
        regions=best.regions,
    )


class OcrSession:
    """OCR work for one document: shared engine, per-document time budget.

    A session is created per document.  It does nothing until the first page
    needs OCR, so a digital PDF never pays for engine loading.
    """

    def __init__(self, policy: OcrPolicy | None = None) -> None:
        self.policy = policy or OcrPolicy.from_settings()
        self._deadline = time.monotonic() + max(0.0, self.policy.budget_s)

    @property
    def enabled(self) -> bool:
        return self.policy.enabled

    def pages_left(self) -> float:
        return max(0.0, self._deadline - time.monotonic())

    def read(self, image: Any) -> OcrPageResult:
        """OCR one rendered page (numpy array).

        Raises :class:`OcrUnavailable` when the engine cannot run,
        :class:`OcrBudgetExhausted` when the document budget is spent, and
        :class:`OcrPageFailed` when the page produced no usable text.
        """
        if not self.enabled:
            raise OcrUnavailable("OCR is disabled for this document")
        if time.monotonic() >= self._deadline:
            raise OcrBudgetExhausted("document OCR budget exhausted")

        engine = _get_engine()
        timeout = min(self.policy.page_timeout_s, self.pages_left())
        future = _get_executor().submit(_read_page, engine, image, self.policy)
        try:
            result = future.result(timeout=timeout)
        except FutureTimeout as exc:
            # The worker cannot be interrupted; it is left to finish on its own
            # single-threaded executor, and every later page of this document
            # queues behind it and times out too — bounded, and reported.
            raise OcrPageFailed(
                f"OCR exceeded {timeout:.0f}s on this page"
            ) from exc
        except Exception as exc:
            raise OcrPageFailed(f"OCR failed on this page: {exc}") from exc

        if not result.text.strip():
            raise OcrPageFailed("OCR found no text on this page")
        return result
