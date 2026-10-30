"""Load-plan selection for the instruct conversation model (no weights needed).

The 4-bit path is verified as a *configuration* decision: with CUDA and
``bitsandbytes`` reported available, the loader must ask transformers for an
NF4 4-bit model with ``device_map="auto"``; otherwise it must fall back to
float32 on CPU and say why.  No model is downloaded and no GPU is touched.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import generation.causal as causal
from generation.types import AnswerFormat, EvidenceBlock


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    monkeypatch.setattr(causal, "_state", causal._ModelState())
    monkeypatch.setenv(causal.CONVERSATION_MODEL_ENV, "Qwen/Qwen2.5-1.5B-Instruct")
    yield


def _hardware(monkeypatch, *, cuda: bool, bnb: bool, four_bit: bool = True):
    monkeypatch.setattr(causal, "bitsandbytes_available", lambda: bnb)
    monkeypatch.setattr(causal, "four_bit_enabled", lambda: four_bit)

    import torch

    monkeypatch.setattr(torch.cuda, "is_available", lambda: cuda)


class TestPlanSelection:
    def test_cuda_with_bitsandbytes_selects_4bit(self, monkeypatch):
        _hardware(monkeypatch, cuda=True, bnb=True)
        plan = causal.plan_loading()
        assert plan.kind == "4bit"
        assert plan.device == "cuda"
        assert plan.dtype == "float16"
        assert plan.device_map == "auto"
        assert "bitsandbytes" in plan.reason

    def test_cuda_without_bitsandbytes_falls_back_to_cpu(self, monkeypatch):
        _hardware(monkeypatch, cuda=True, bnb=False)
        plan = causal.plan_loading()
        assert plan.kind == "fp32-cpu"
        assert plan.device == "cpu"
        assert plan.device_map is None
        assert "bitsandbytes is not installed" in plan.reason

    def test_no_cuda_falls_back_to_cpu(self, monkeypatch):
        _hardware(monkeypatch, cuda=False, bnb=True)
        plan = causal.plan_loading()
        assert plan.kind == "fp32-cpu"
        assert "CUDA is not available" in plan.reason

    def test_kill_switch_disables_4bit(self, monkeypatch):
        _hardware(monkeypatch, cuda=True, bnb=True, four_bit=False)
        plan = causal.plan_loading()
        assert plan.kind == "fp32-cpu"
        assert causal.FOUR_BIT_ENV in plan.reason

    def test_four_bit_enabled_reads_the_environment(self, monkeypatch):
        monkeypatch.delenv(causal.FOUR_BIT_ENV, raising=False)
        assert causal.four_bit_enabled() is True
        for value in ("0", "false", "no", "off", ""):
            monkeypatch.setenv(causal.FOUR_BIT_ENV, value)
            assert causal.four_bit_enabled() is False
        monkeypatch.setenv(causal.FOUR_BIT_ENV, "1")
        assert causal.four_bit_enabled() is True


class TestVramCeiling:
    """The 3.0 GiB budget is enforced, not just reported.

    ``cuda_peak_mib`` is the one place a measurement enters, so it is patched
    here: these tests assert the *decision* (fail above the ceiling, pass at or
    below it, never claim a CPU run met a GPU budget) without needing a GPU.
    """

    def test_a_peak_above_the_ceiling_raises(self, monkeypatch):
        monkeypatch.setattr(causal, "cuda_peak_mib", lambda: 3000.1)
        with pytest.raises(causal.VramBudgetExceeded) as excinfo:
            causal.enforce_vram_ceiling(3000.1, phase="generating a 15-mark answer")
        assert "3000" in str(excinfo.value)
        assert "15-mark" in str(excinfo.value)

    def test_the_ceiling_itself_is_allowed(self, monkeypatch):
        monkeypatch.setattr(causal, "cuda_peak_mib", lambda: causal.VRAM_CEILING_MIB)
        causal.enforce_vram_ceiling(causal.VRAM_CEILING_MIB, phase="loading the weights")

    def test_a_peak_below_the_ceiling_passes(self):
        causal.enforce_vram_ceiling(1156.0, phase="loading the weights")
        assert causal.vram_within_ceiling(1156.0) is True

    def test_an_unmeasured_peak_is_not_treated_as_zero(self):
        # CPU runs have no VRAM figure: nothing to enforce, and the verdict is
        # "not measured" rather than a fabricated pass.
        assert causal.vram_within_ceiling(None) is True
        causal.enforce_vram_ceiling(None, phase="loading the weights")

    def test_the_error_is_a_generation_unavailability(self):
        from generation.types import GenerationUnavailableError

        assert issubclass(causal.VramBudgetExceeded, causal.ConversationModelUnavailable)
        assert issubclass(causal.VramBudgetExceeded, GenerationUnavailableError)

    def test_status_reports_the_ceiling_and_the_verdict(self, monkeypatch):
        _hardware(monkeypatch, cuda=True, bnb=True)
        monkeypatch.setattr(causal, "cuda_peak_mib", lambda: 1156.0)

        status = causal.conversation_model_status()

        assert status["vramPeakMiB"] == 1156.0
        assert status["vramCeilingMiB"] == 3000.0
        assert status["vramWithinCeiling"] is True

    def test_status_reports_a_violation_honestly(self, monkeypatch):
        _hardware(monkeypatch, cuda=True, bnb=True)
        monkeypatch.setattr(causal, "cuda_peak_mib", lambda: 3100.0)

        status = causal.conversation_model_status()

        assert status["vramWithinCeiling"] is False

    def test_no_configured_model_reports_no_vram_claim(self, monkeypatch):
        monkeypatch.delenv(causal.CONVERSATION_MODEL_ENV, raising=False)
        monkeypatch.setattr(causal, "conversation_model_name", lambda: "")

        status = causal.conversation_model_status()

        assert status["vramPeakMiB"] is None
        assert status["vramWithinCeiling"] is None
        assert status["vramCeilingMiB"] == 3000.0

    def test_a_load_that_exceeds_the_ceiling_is_unloaded_and_refused(self, monkeypatch):
        _hardware(monkeypatch, cuda=True, bnb=True)
        monkeypatch.setattr(causal, "cuda_peak_mib", lambda: 3100.0)

        import transformers

        def fake_model_from_pretrained(source, **kwargs):
            return SimpleNamespace(
                eval=lambda: None,
                to=lambda device: None,
                parameters=lambda: iter([SimpleNamespace(device="cuda")]),
                generate=None,
            )

        monkeypatch.setattr(
            transformers.AutoModelForCausalLM,
            "from_pretrained",
            staticmethod(fake_model_from_pretrained),
        )
        monkeypatch.setattr(
            transformers.AutoTokenizer,
            "from_pretrained",
            staticmethod(lambda source, **kwargs: SimpleNamespace(pad_token_id=0, eos_token_id=1)),
        )

        state = causal._load()

        assert state.available is False
        assert state.error is not None and "exceeded" in state.error


class TestBudgetEnvelope:
    """The caps the ceiling depends on, pinned so a later edit cannot widen them.

    Measured 2026-10-24 (RTX 3050, ``Qwen2.5-1.5B-Instruct`` NF4, 640 forced new
    tokens): 1440 prompt tokens → 1577 MiB driver peak, 2048 → 1815, 2560 → 2129,
    3072 → 2481, 4096 → 3433 MiB (over the ceiling).  A 2560-token cap is only
    safe while the generation budget stays at 640, so both are asserted here.
    """

    def test_the_ceiling_is_three_gigabytes(self):
        assert causal.VRAM_CEILING_MIB == 3000.0

    def test_input_cap_stays_in_the_measured_envelope(self):
        assert causal.MAX_INPUT_TOKENS == 2560

    def test_generation_budget_is_fifteen_marks_at_most(self):
        assert causal.MAX_NEW_TOKENS[AnswerFormat.FIFTEEN] == 640
        assert max(causal.MAX_NEW_TOKENS.values()) == 640

    def test_a_huge_question_is_cut_to_the_prompt_budget(self):
        messages = causal.build_messages("q" * 5000, ())
        question_line = messages[-1]["content"].split("Question: ", 1)[1]
        assert question_line == "q" * causal.MAX_QUESTION_CHARS

    def test_evidence_and_history_are_capped(self):
        blocks = tuple(
            EvidenceBlock(
                index=index + 1,
                content="x" * 5000,
                document_name="a.pdf",
                page=1,
            )
            for index in range(20)
        )
        history = tuple(
            {"role": "user" if turn % 2 == 0 else "assistant", "content": "y" * 5000}
            for turn in range(40)
        )
        messages = causal.build_messages("what?", blocks, history=history)
        # system + at most MAX_HISTORY_TURNS turns + the final user message
        assert len(messages) == 2 + causal.MAX_HISTORY_TURNS
        assert all(len(message["content"]) <= 600 for message in messages[1:-1])
        evidence_lines = messages[-1]["content"].split("Evidence:\n", 1)[1]
        assert evidence_lines.count("\n[") + 1 == causal.MAX_PROMPT_BLOCKS


class TestStatus:
    def test_status_reports_the_plan_without_loading(self, monkeypatch):
        _hardware(monkeypatch, cuda=False, bnb=False)
        status = causal.conversation_model_status()
        assert status["configured"] is True
        assert status["loaded"] is False
        assert status["plan"] == "fp32-cpu"
        assert status["quantization"] is None
        assert status["cudaAvailable"] is False
        assert "CUDA is not available" in status["planReason"]
        assert status["vramPeakMiB"] is None


class TestLoadKwargs:
    def _fake_transformers(self, monkeypatch, *, to_calls: list):
        import transformers

        captured: dict = {}

        def fake_model_from_pretrained(source, **kwargs):
            captured["source"] = source
            captured["kwargs"] = kwargs
            return SimpleNamespace(
                eval=lambda: None,
                to=lambda device: to_calls.append(device),
                parameters=lambda: iter([SimpleNamespace(device="cpu")]),
                generate=None,
            )

        def fake_tokenizer_from_pretrained(source, **kwargs):
            return SimpleNamespace(pad_token_id=0, eos_token_id=1)

        monkeypatch.setattr(
            transformers.AutoModelForCausalLM,
            "from_pretrained",
            staticmethod(fake_model_from_pretrained),
        )
        monkeypatch.setattr(
            transformers.AutoTokenizer,
            "from_pretrained",
            staticmethod(fake_tokenizer_from_pretrained),
        )
        return captured

    def test_4bit_config_is_requested_with_cuda(self, monkeypatch):
        _hardware(monkeypatch, cuda=True, bnb=True)
        to_calls: list = []
        captured = self._fake_transformers(monkeypatch, to_calls=to_calls)

        state = causal._load()

        assert state.available is True
        assert state.quantization == "4bit-nf4"
        assert state.plan is not None and state.plan.kind == "4bit"
        config = captured["kwargs"]["quantization_config"]
        assert config.load_in_4bit is True
        assert config.bnb_4bit_quant_type == "nf4"
        assert config.bnb_4bit_use_double_quant is True
        assert captured["kwargs"]["device_map"] == "auto"
        # A device-mapped model must not be moved again.
        assert to_calls == []

    def test_cpu_fallback_uses_float32_and_moves_the_model(self, monkeypatch):
        _hardware(monkeypatch, cuda=False, bnb=False)
        to_calls: list = []
        captured = self._fake_transformers(monkeypatch, to_calls=to_calls)

        state = causal._load()

        assert state.available is True
        assert state.quantization is None
        assert "quantization_config" not in captured["kwargs"]
        assert "device_map" not in captured["kwargs"]
        assert str(captured["kwargs"]["dtype"]).endswith("float32")
        assert to_calls == ["cpu"]

    def test_no_configured_model_reports_why(self, monkeypatch):
        monkeypatch.delenv(causal.CONVERSATION_MODEL_ENV, raising=False)
        monkeypatch.setattr(causal, "conversation_model_name", lambda: "")
        state = causal._load()
        assert state.available is False
        assert causal.CONVERSATION_MODEL_ENV in state.error
