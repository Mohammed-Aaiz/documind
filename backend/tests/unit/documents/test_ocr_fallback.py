"""OCR fallback — the adapter's own decisions, exercised with a stub engine.

What is tested here is *policy*, not recognition: which pages get OCR'd, how a
misoriented page is corrected, what happens when the engine is missing, slow,
out of budget or finds nothing, and which lines are dropped.  Recognition
quality is measured on real pages in
``tests/integration/documents/test_ocr_scanned_pdf.py`` — repeating it here
with a stub would prove nothing.
"""

from __future__ import annotations

import sys
import time
from types import SimpleNamespace

import numpy as np
import pytest

from config import get_settings
from documents import ocr


def test_engine_load_uses_bounded_detector_batch_and_thread_configuration(monkeypatch):
    calls = []
    instance = object()

    def construct(**kwargs):
        calls.append(kwargs)
        return instance

    monkeypatch.setitem(sys.modules, "rapidocr", SimpleNamespace(RapidOCR=construct))
    monkeypatch.setattr(ocr, "_engine", None)
    monkeypatch.setattr(ocr, "_engine_version", "")
    assert ocr._get_engine() is instance
    assert ocr._get_engine() is instance
    assert len(calls) == 1
    assert calls[0]["params"] == {
        "Det.limit_type": "max", "Det.limit_side_len": 1536,
        "Rec.rec_batch_num": 2,
        "EngineConfig.onnxruntime.intra_op_num_threads": 2,
        "EngineConfig.onnxruntime.inter_op_num_threads": 1,
        "EngineConfig.onnxruntime.enable_cpu_mem_arena": False,
    }


class _Output:
    """The subset of RapidOCR's output object this adapter reads."""

    def __init__(self, txts, scores, widths=400.0, heights=30.0):
        self.txts = list(txts)
        self.scores = list(scores)
        self.boxes = [
            [[0.0, 0.0], [widths, 0.0], [widths, heights], [0.0, heights]]
            for _ in txts
        ]


def _upright(text="The lidar calibration interval is 6 months.") -> _Output:
    return _Output([text], [0.995], widths=400.0, heights=30.0)


def _sideways(text="The lidar calibration interval is 6 months.") -> _Output:
    return _Output([text], [0.90], widths=30.0, heights=400.0)


class _ScriptedEngine:
    """Returns canned outputs in call order and records what it was given."""

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.call_count = 0
        self.use_cls: list[bool] = []

    def __call__(self, image, use_cls=True):
        self.call_count += 1
        self.use_cls.append(use_cls)
        return self.outputs.pop(0)


class _SleepingEngine:
    def __call__(self, image, use_cls=True):
        time.sleep(0.4)
        return _upright()


@pytest.fixture
def page():
    """A plain image array; its pixels are irrelevant to the stub engine."""
    return np.zeros((200, 300, 3), dtype=np.uint8)


# ---------------------------------------------------------------------------
# Reading one pass
# ---------------------------------------------------------------------------


class TestLineFiltering:
    def test_low_confidence_and_empty_lines_are_dropped(self, page):
        engine = _ScriptedEngine(
            [_Output(["good line", "", "noise"], [0.99, 0.99, 0.10])]
        )

        result = ocr._read_page(engine, page, ocr.OcrPolicy())

        assert result.text == "good line"
        assert result.lines == 1
        assert result.mean_confidence == 0.99

    def test_box_aspect_separates_upright_from_sideways(self):
        upright = _Output(["a"], [0.99], widths=400.0, heights=30.0)
        sideways = _Output(["a"], [0.99], widths=30.0, heights=400.0)

        assert ocr._median_box_aspect(upright) > ocr.VERTICAL_BOX_ASPECT
        assert ocr._median_box_aspect(sideways) < ocr.VERTICAL_BOX_ASPECT

    def test_no_boxes_is_zero_aspect_not_a_crash(self):
        assert ocr._median_box_aspect(_Output([], [])) == 0.0


# ---------------------------------------------------------------------------
# Orientation correction
# ---------------------------------------------------------------------------


class TestOrientationCorrection:
    def test_upright_page_costs_one_pass(self, page):
        engine = _ScriptedEngine([_upright()])

        result = ocr._read_page(engine, page, ocr.OcrPolicy())

        assert engine.call_count == 1
        assert result.rotation == 0
        assert "lidar" in result.text
        assert engine.use_cls == [False], (
            "the first pass must not let the angle classifier hide an upside-down page"
        )

    def test_sideways_page_is_rotated_until_the_lines_read(self, page):
        """A tall-box page is retried at 90/270 and the readable pass is kept."""
        engine = _ScriptedEngine([_sideways(), _upright("rotated back to readable")])

        result = ocr._read_page(engine, page, ocr.OcrPolicy())

        assert engine.call_count == 2
        assert result.rotation == 90
        assert result.text == "rotated back to readable"

    def test_upside_down_page_is_retried_and_the_better_reading_kept(self, page):
        """Wide boxes plus one poor line means "maybe upside down" — retry it."""
        upside_down = _Output(["Douns o onnal", "The warranty period is 24 months."],
                              [0.61, 0.99])
        engine = _ScriptedEngine([upside_down, _upright("The warranty period is 24 months.")])

        result = ocr._read_page(engine, page, ocr.OcrPolicy())

        assert engine.call_count == 2
        assert result.rotation == 180
        assert result.text == "The warranty period is 24 months."
        assert engine.use_cls == [False, True], (
            "the correction pass reads with the classifier on"
        )

    def test_a_worse_upside_down_reading_is_discarded(self, page):
        """Noisy upright scans must not be replaced by a worse 180 reading."""
        noisy = _Output(["a noisy but correct line"], [0.70])
        worse = _Output(["a", "worse"], [0.40, 0.41])
        engine = _ScriptedEngine([noisy, worse])

        result = ocr._read_page(engine, page, ocr.OcrPolicy())

        assert engine.call_count == 2, "the retry is made…"
        assert result.text == "a noisy but correct line", "…and rejected"
        assert result.rotation == 0


# ---------------------------------------------------------------------------
# Engine availability, budget and timeouts
# ---------------------------------------------------------------------------


class TestSessionLimits:
    def test_disabled_policy_refuses_to_read(self, page):
        session = ocr.OcrSession(ocr.OcrPolicy.disabled())

        assert session.enabled is False
        with pytest.raises(ocr.OcrUnavailable):
            session.read(page)

    def test_missing_engine_is_reported_as_unavailable(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "rapidocr", None)

        assert ocr.ocr_available() is False

    def test_engine_failure_is_reported_as_unavailable(self, page, monkeypatch):
        def _explode():
            raise ocr.OcrUnavailable("rapidocr could not be initialised")

        monkeypatch.setattr(ocr, "_get_engine", _explode)
        session = ocr.OcrSession(ocr.OcrPolicy())

        with pytest.raises(ocr.OcrUnavailable):
            session.read(page)

    def test_spent_budget_refuses_to_read(self, page):
        session = ocr.OcrSession(ocr.OcrPolicy(budget_s=0.0))

        with pytest.raises(ocr.OcrBudgetExhausted):
            session.read(page)

    def test_a_slow_page_times_out_instead_of_hanging(self, page, monkeypatch):
        monkeypatch.setattr(ocr, "_get_engine", lambda: _SleepingEngine())
        session = ocr.OcrSession(ocr.OcrPolicy(page_timeout_s=0.05))

        with pytest.raises(ocr.OcrPageFailed):
            session.read(page)

    def test_a_page_with_no_text_is_a_failure_not_an_empty_answer(
        self, page, monkeypatch
    ):
        monkeypatch.setattr(
            ocr, "_get_engine", lambda: _ScriptedEngine([_Output([], [])])
        )
        session = ocr.OcrSession(ocr.OcrPolicy())

        with pytest.raises(ocr.OcrPageFailed):
            session.read(page)


# ---------------------------------------------------------------------------
# Configuration surface
# ---------------------------------------------------------------------------


class TestConfiguration:
    def test_settings_default_to_the_measured_engine(self):
        settings = get_settings()

        assert settings.ocr_engine == "rapidocr"
        assert settings.ocr_dpi == ocr.DEFAULT_DPI
        assert settings.ocr_document_budget_seconds == ocr.DOCUMENT_BUDGET_S

    def test_environment_can_disable_ocr(self, monkeypatch):
        # pydantic-settings maps the ``ocr_engine`` field to ``OCR_ENGINE``.
        monkeypatch.setenv("OCR_ENGINE", "off")
        get_settings.cache_clear()
        try:
            assert ocr.OcrPolicy.from_settings().enabled is False
        finally:
            get_settings.cache_clear()
