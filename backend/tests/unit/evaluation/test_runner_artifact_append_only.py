"""STEP 1.6X (Workstream E): the Phase 3D/3F/4B runners record their report
through the append-only artifact writer.

Each of those runners used to end with a bare::

    out = Path("<phase>_evaluation_report.json")
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

against a fixed file name in the *working directory*, so re-running a harness
silently replaced the previous run's recorded evidence with the new numbers and
left no trace that anything had been lost.

These tests pin the replacement contract:

* an artifact name that already exists is refused, and the existing bytes are
  left exactly as they were;
* a file that appears between the reservation and the write is not replaced
  either (the writer uses an exclusive create, not an existence check);
* a name that was never reserved is refused *before* any file is created, so a
  collision cannot half-write a run;
* the three runners no longer contain a bare ``write_text`` for their report and
  do route it through the writer's reservation call.

The runner assertions are source-level on purpose: executing these harnesses
needs a disposable PostgreSQL target, a QA model and a benchmark run, none of
which belongs in a unit test.  They follow the style of
``tests/unit/documents/test_phase3e_processing.py::TestDeleteConsistency``.
"""

from __future__ import annotations

import importlib
import inspect

import pytest

from evaluation.artifacts import ArtifactExistsError, RunOutput

#: Runner module -> the report file name it records in the working directory.
RUNNER_REPORTS = {
    "evaluation.experiments.run_phase3d_evaluation": "phase3d_evaluation_report.json",
    "evaluation.experiments.run_phase3f_evaluation": "phase3f_evaluation_report.json",
    "evaluation.experiments.run_phase4b_evaluation": "phase4b_evaluation_report.json",
}

#: The three report names, de-duplicated, for the parametrised writer tests.
REPORT_NAMES = sorted(set(RUNNER_REPORTS.values()))


# ---------------------------------------------------------------------------
# The writer contract the runners now rely on
# ---------------------------------------------------------------------------


class TestAppendOnlyWriterContract:
    def test_existing_artifact_is_refused_and_left_untouched(self, tmp_path):
        original = b'{"run": "first"}\n'
        (tmp_path / "report.json").write_bytes(original)

        output = RunOutput(tmp_path)

        with pytest.raises(ArtifactExistsError, match="append-only"):
            output.reserve("report.json")

        assert (tmp_path / "report.json").read_bytes() == original

    def test_file_appearing_after_reservation_is_not_replaced(self, tmp_path):
        """An existence check would pass here; the exclusive create must not."""
        output = RunOutput(tmp_path)
        output.reserve("report.json")

        (tmp_path / "report.json").write_bytes(b'{"winner": "first"}')

        with pytest.raises(ArtifactExistsError):
            output.write_text("report.json", '{"winner": "second"}')

        assert (tmp_path / "report.json").read_bytes() == b'{"winner": "first"}'

    def test_unreserved_name_is_refused_before_any_file_exists(self, tmp_path):
        output = RunOutput(tmp_path)

        with pytest.raises(ArtifactExistsError, match="not reserved"):
            output.write_text("report.json", "{}")

        assert list(tmp_path.iterdir()) == []

    @pytest.mark.parametrize("report_name", REPORT_NAMES)
    def test_a_recorded_runner_report_is_never_replaced(self, tmp_path, report_name):
        original = b'{"run": "previously recorded"}\n'
        target = tmp_path / report_name
        target.write_bytes(original)

        with pytest.raises(ArtifactExistsError):
            RunOutput(tmp_path).reserve(report_name)

        assert target.read_bytes() == original

    def test_a_refused_run_leaves_no_partial_artifact_set(self, tmp_path):
        """All three names already recorded: nothing new, nothing truncated."""
        seeded = {name: b'{"recorded": true}\n' for name in REPORT_NAMES}
        for name, payload in seeded.items():
            (tmp_path / name).write_bytes(payload)

        refused = 0
        for name in REPORT_NAMES:
            output = RunOutput(tmp_path)
            try:
                output.reserve(name)
                output.write_text(name, '{"recorded": false}')
            except ArtifactExistsError:
                refused += 1

        assert refused == len(REPORT_NAMES)
        assert {p.name for p in tmp_path.iterdir()} == set(seeded)
        for name, payload in seeded.items():
            assert (tmp_path / name).read_bytes() == payload


# ---------------------------------------------------------------------------
# The three runners use it
# ---------------------------------------------------------------------------


class TestPhaseRunnersRecordThroughTheWriter:
    @pytest.mark.parametrize("module_path", sorted(RUNNER_REPORTS))
    def test_report_is_reserved_before_it_is_written(self, module_path):
        report_name = RUNNER_REPORTS[module_path]
        source = inspect.getsource(importlib.import_module(module_path).main)

        assert f'"{report_name}"' in source, "the recorded report name changed"
        assert "output.reserve(report_name)" in source
        assert "output.write_text(report_name," in source

    @pytest.mark.parametrize("module_path", sorted(RUNNER_REPORTS))
    def test_no_bare_write_text_remains_for_the_report(self, module_path):
        """No single line both names the report and writes it directly."""
        report_name = RUNNER_REPORTS[module_path]
        source = inspect.getsource(importlib.import_module(module_path).main)

        offenders = [
            line.strip()
            for line in source.splitlines()
            if report_name in line and ".write_text(" in line
        ]
        assert offenders == [], f"direct report write remains: {offenders}"

    @pytest.mark.parametrize("module_path", sorted(RUNNER_REPORTS))
    def test_a_collision_fails_the_run_instead_of_continuing(self, module_path):
        module = importlib.import_module(module_path)
        source = inspect.getsource(module.main)

        assert "from evaluation.artifacts import ArtifactExistsError, RunOutput" in (
            inspect.getsource(module)
        )
        assert "except ArtifactExistsError as error:" in source
        assert "return 2" in source, "a refused write must not report success"

    @pytest.mark.parametrize("module_path", sorted(RUNNER_REPORTS))
    def test_the_report_is_still_written_to_the_working_directory(self, module_path):
        """Output semantics are preserved: same file name, same directory, same
        json.dumps arguments — only the write mechanism changed."""
        source = inspect.getsource(importlib.import_module(module_path).main)

        assert "RunOutput(Path(\".\"))" in source
        assert "json.dumps(report, indent=2)" in source
