"""Document API integration tests stay independent of provisioned CLIP weights.

Visual pixel encoding has dedicated tests. A developer installing the optional
checkpoint must not turn ordinary upload fixtures into expensive model runs.
"""
import pytest


@pytest.fixture(autouse=True)
def disable_optional_visual_inference(monkeypatch):
    from documents import routes

    monkeypatch.setattr(routes.settings, "visual_embeddings_enabled", False)


@pytest.fixture(autouse=True)
def isolate_document_provider_io(monkeypatch):
    """Keep ordinary uploads independent of a developer's running Ollama.

    Dedicated graph rebuild tests override this provider boundary with their
    own structured completions/errors and still exercise graph validation.
    """
    from documents import kg_extraction
    from generation.types import GenerationUnavailableError

    async def unavailable(*_args, **_kwargs):
        raise GenerationUnavailableError("No live provider is configured in isolated document tests.")

    monkeypatch.setattr(kg_extraction, "complete_answer", unavailable)
