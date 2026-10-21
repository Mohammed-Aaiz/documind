"""STEP 1.6Y Workstream A — collision refusal for two fixed-path writers.

``run_phase4c_diagnostics`` and ``synthesize_structure_discriminating`` both
published to fixed destinations with ``Path.write_text``, which silently replaced
a previously recorded result.  They now write through the central
``evaluation.artifacts.write_evidence`` rule (exclusive create, refusal on
collision) with an explicit ``replace`` opt-in.

What is exercised here:

* the Phase 4C writer end to end through its own ``save_results`` seam, into a
  temporary working directory;
* the synthesis writer's two artifacts, into a temporary reports directory;
* the refusal paths (existing artifact preserved byte-for-byte, no stray or
  partial artifact created) and the explicit ``replace=True`` re-publication;
* the serialization contract, so report *content* is unchanged.

The synthesis module's ``render_markdown`` is stubbed in those tests: its input is
the module's full analysis structure, which cannot be constructed here without
re-implementing ``build_analysis``.  The renderer is not what is under test — the
write path is — and the JSON half of the same writer is asserted against the real
serialization expression.

Nothing here writes to ``evaluation/reports/`` or anywhere in the repository.
"""

from __future__ import annotations

import inspect
import json

import pytest

from evaluation.artifacts import ArtifactExistsError, write_evidence
from evaluation.experiments import run_phase4c_diagnostics as p4c
from evaluation.experiments import synthesize_structure_discriminating as synth

JSON_NAME = "structure_discriminating_analysis.json"
MD_NAME = "structure_discriminating_ablation_report.md"


def _names(directory):
    return sorted(path.name for path in directory.iterdir())


@pytest.fixture
def analysis() -> dict:
    """The minimum payload ``write_reports`` actually touches."""
    return {"corpusVersion": "test-v1", "analysisVersion": "test-synthesis"}


@pytest.fixture
def stub_renderer(monkeypatch):
    """Replace the rich-payload markdown renderer with a deterministic stub."""
    monkeypatch.setattr(synth, "render_markdown", lambda payload: "# rendered\n")


# ---------------------------------------------------------------------------
# The shared rule both writers now depend on
# ---------------------------------------------------------------------------


class TestWriteEvidenceContract:
    def test_existing_artifact_is_refused_and_preserved(self, tmp_path):
        target = tmp_path / "artifact.json"
        write_evidence(target, "first\n")
        with pytest.raises(ArtifactExistsError):
            write_evidence(target, "second\n")
        assert target.read_text(encoding="utf-8") == "first\n"

    def test_replace_is_explicit_only(self, tmp_path):
        target = tmp_path / "artifact.json"
        write_evidence(target, "first\n")
        write_evidence(target, "second\n", replace=True)
        assert target.read_text(encoding="utf-8") == "second\n"

    def test_refusal_creates_no_file_and_no_directory(self, tmp_path):
        missing = tmp_path / "nested" / "artifact.json"
        write_evidence(missing, "first\n")
        before = _names(tmp_path / "nested")
        with pytest.raises(ArtifactExistsError):
            write_evidence(missing, "second\n")
        assert _names(tmp_path / "nested") == before


# ---------------------------------------------------------------------------
# Phase 4C diagnostics — the module's own save path
# ---------------------------------------------------------------------------


class TestPhase4cWriter:
    def test_second_write_is_refused_and_the_first_is_preserved(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        results = {"failures": [{"qid": "q1", "failure_primary": "RET_MISS"}]}
        first = p4c.save_results(results)
        original = first.read_bytes()
        assert json.loads(original.decode("utf-8")) == results

        with pytest.raises(ArtifactExistsError):
            p4c.save_results({"failures": []})

        assert first.read_bytes() == original

    def test_replace_re_publishes_only_when_asked(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        p4c.save_results({"version": 1})
        second = p4c.save_results({"version": 2}, replace=True)
        assert json.loads(second.read_text(encoding="utf-8")) == {"version": 2}

    def test_refusal_leaves_the_directory_exactly_as_it_was(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        p4c.save_results({"version": 1})
        before = _names(tmp_path)
        with pytest.raises(ArtifactExistsError):
            p4c.save_results({"version": "partial"})
        assert _names(tmp_path) == before

    def test_serialization_is_unchanged(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        results = {"a": 1, "nested": {"b": [1, 2]}, "unsupported": None}
        path = p4c.save_results(results)
        # The exact pre-1.6Y expression, so the recorded content is unchanged.
        assert path.read_text(encoding="utf-8") == json.dumps(results, indent=2, default=str)

    def test_destination_and_operator_flag_are_wired(self):
        source = inspect.getsource(p4c)
        assert 'Path("phase4c_failure_matrix.json")' in source
        assert "json.dumps(results, indent=2, default=str)" in source
        assert "write_evidence(" in source
        assert "replace=replace" in source
        assert '"--replace"' in source
        assert "except ArtifactExistsError" in source
        # No direct, silently replacing write remains in the module.
        assert ".write_text(" not in source


# ---------------------------------------------------------------------------
# Structure-discriminating synthesis — both artifacts
# ---------------------------------------------------------------------------


class TestSynthesisWriter:
    def test_second_write_is_refused_and_both_artifacts_are_preserved(
        self, tmp_path, analysis, stub_renderer
    ):
        paths = synth.write_reports(analysis, tmp_path)
        json_bytes = paths["json"].read_bytes()
        md_bytes = paths["md"].read_bytes()

        with pytest.raises(ArtifactExistsError):
            synth.write_reports(analysis, tmp_path)

        assert paths["json"].read_bytes() == json_bytes
        assert paths["md"].read_bytes() == md_bytes

    def test_replace_re_publishes_only_when_asked(self, tmp_path, analysis, monkeypatch):
        monkeypatch.setattr(synth, "render_markdown", lambda payload: "# first\n")
        synth.write_reports(analysis, tmp_path)
        monkeypatch.setattr(synth, "render_markdown", lambda payload: "# second\n")
        paths = synth.write_reports(analysis, tmp_path, replace=True)
        assert paths["md"].read_text(encoding="utf-8") == "# second\n"

    def test_a_refusal_leaves_no_partial_artifact_set(self, tmp_path, analysis, stub_renderer):
        """A pre-existing JSON artifact must not leave a freshly written markdown."""
        (tmp_path / JSON_NAME).write_text("previous\n", encoding="utf-8")
        before = _names(tmp_path)

        with pytest.raises(ArtifactExistsError):
            synth.write_reports(analysis, tmp_path)

        assert _names(tmp_path) == before
        assert (tmp_path / JSON_NAME).read_text(encoding="utf-8") == "previous\n"
        assert not (tmp_path / MD_NAME).exists()

    def test_json_content_is_the_unchanged_serialization(self, tmp_path, analysis, stub_renderer):
        paths = synth.write_reports(analysis, tmp_path)
        assert paths["json"].read_text(encoding="utf-8") == json.dumps(
            dict(analysis), indent=2, sort_keys=True
        )
        assert paths["md"].read_text(encoding="utf-8") == "# rendered\n"

    def test_timestamp_flag_still_controls_generated_at(self, tmp_path, analysis, stub_renderer):
        paths = synth.write_reports(analysis, tmp_path, timestamp=True)
        payload = json.loads(paths["json"].read_text(encoding="utf-8"))
        assert payload["corpusVersion"] == "test-v1"
        assert payload["generated_at"]

    def test_module_is_wired_to_the_central_writer(self):
        source = inspect.getsource(synth)
        assert 'out_dir / "structure_discriminating_analysis.json"' in source
        assert 'out_dir / "structure_discriminating_ablation_report.md"' in source
        assert "json.dumps(payload, indent=2, sort_keys=True)" in source
        assert "render_markdown(payload)" in source
        assert "write_evidence(" in source
        assert "replace=replace" in source
        assert '"--replace"' in source
        assert "except ArtifactExistsError" in source
        assert ".write_text(" not in source
