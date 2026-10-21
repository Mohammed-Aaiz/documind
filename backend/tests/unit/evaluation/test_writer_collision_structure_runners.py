"""STEP 1.6Y: publication by the two structure runners is append-only.

Both runners used to publish their reports with ``Path.write_text`` into FIXED
``evaluation/reports/`` names, so re-running a measurement silently replaced the
recorded evidence.  They now write through
``evaluation.artifacts.write_evidence``, which refuses to replace an existing
artifact unless the operator explicitly passes ``--replace``.

What is proven here
-------------------
* ``write_evidence`` refuses a second write to the same destination and leaves the
  first file byte-identical; the refusal creates nothing, so there is no partial
  artifact and no changed directory listing.
* ``replace=True`` is a deliberate, explicit replacement.
* The text a runner hands over is the text the previous revision wrote: the write
  sites still pass the same ``canonical(...)`` / ``render_report(...)``
  expressions, and ``write_evidence`` writes the string it is given byte for byte
  (no re-serialization, no added newline), so a recorded digest still matches.
* Each runner parses ``--replace``, pre-flights every publication name before the
  first byte, and refuses loudly with a non-zero exit.
* The ``--smoke`` branches still write into a fresh temporary directory: scratch
  output is deliberately not routed through the evidence writer.

The runners are read as TEXT where an assertion is about their source (the
convention ``test_structure_runner_guard_order.py`` already uses for these two
modules, which import heavy experiment dependencies).  Nothing here runs a
runner, contacts a database, or writes into the real ``evaluation/reports/``
directory.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from evaluation import artifacts

EXPERIMENTS_DIR = Path(__file__).resolve().parents[3] / "evaluation" / "experiments"
CONFIRMATION = EXPERIMENTS_DIR / "run_structure_confirmation.py"
ELEMENT = EXPERIMENTS_DIR / "run_structure_element_measurement.py"

RUNNER_FILES = (CONFIRMATION, ELEMENT)
RUNNER_IDS = ("confirmation", "element")

#: The fixed publication names each runner owns.
PUBLICATIONS = {
    CONFIRMATION: (
        "structure_confirmation.json",
        "structure_confirmation_report.md",
    ),
    ELEMENT: (
        "structure_element_measurement_control.json",
        "structure_element_measurement_treatment.json",
        "structure_element_measurement_analysis.json",
    ),
}

#: ``(REPORTS_DIR / <something>).write_text(`` — the direct fixed-path write this
#: change removes.  Kept as a detector with its own positive control below, so it
#: cannot become vacuous silently.
_DIRECT_FIXED_WRITE = re.compile(r"REPORTS_DIR\s*/\s*[^)\n]*\)\.write_text\(")


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestWriteEvidenceIsAppendOnly:
    """The contract the runners now depend on."""

    def test_second_write_refuses_and_preserves_the_first(self, tmp_path):
        target = tmp_path / "reports" / "structure_confirmation.json"
        artifacts.write_evidence(target, '{"run": "first"}')
        before = target.read_bytes()

        with pytest.raises(artifacts.ArtifactExistsError):
            artifacts.write_evidence(target, '{"run": "second"}')

        assert target.read_bytes() == before

    def test_replace_is_an_explicit_deliberate_overwrite(self, tmp_path):
        target = tmp_path / "reports" / "structure_confirmation.json"
        artifacts.write_evidence(target, '{"run": "first"}')

        artifacts.write_evidence(target, '{"run": "second"}', replace=True)

        assert target.read_bytes() == b'{"run": "second"}'

    def test_a_refused_write_leaves_the_directory_unchanged(self, tmp_path):
        directory = tmp_path / "reports"
        directory.mkdir()
        existing = directory / "structure_confirmation_report.md"
        existing.write_bytes(b"# recorded\n")
        listing_before = sorted(entry.name for entry in directory.iterdir())

        with pytest.raises(artifacts.ArtifactExistsError):
            artifacts.write_evidence(existing, "# replacement\n")

        assert sorted(entry.name for entry in directory.iterdir()) == listing_before
        assert existing.read_bytes() == b"# recorded\n"

    def test_the_text_is_written_byte_for_byte(self, tmp_path):
        # The runners hand over the exact string the previous revision wrote
        # (``canonical(...)`` / ``render_report(...)``).  Any re-serialization or
        # added newline would stop a recorded digest from matching.
        text = '{"a": 1}\n'
        with_newline = tmp_path / "reports" / "with_newline.json"
        without_newline = tmp_path / "reports" / "without_newline.json"

        artifacts.write_evidence(with_newline, text)
        artifacts.write_evidence(without_newline, "{}")

        assert with_newline.read_bytes() == text.encode("utf-8")
        assert without_newline.read_bytes() == b"{}"

    def test_parent_directories_are_created(self, tmp_path):
        target = tmp_path / "a" / "b" / "reports.json"

        artifacts.write_evidence(target, "{}")

        assert target.is_file()


class TestNoDirectFixedPathWriteRemains:
    """The removed pattern stays removed, and the detector still detects it."""

    @pytest.mark.parametrize("path", RUNNER_FILES, ids=RUNNER_IDS)
    def test_no_bare_reports_dir_write_remains(self, path):
        source = _source(path)

        assert not _DIRECT_FIXED_WRITE.findall(source), (
            "the fixed publication sites must go through write_evidence, not "
            "Path.write_text"
        )

    def test_the_detector_is_neither_vacuous_nor_over_broad(self):
        # Positive control: the pattern must match the lines it replaced, or the
        # test above would pass for the wrong reason.
        for removed in (
            '(REPORTS_DIR / "structure_confirmation.json").write_text(',
            '(REPORTS_DIR / "structure_confirmation_report.md").write_text(',
            "(REPORTS_DIR / filename).write_text(",
        ):
            assert _DIRECT_FIXED_WRITE.search(removed), removed

        # Negative control: the replacement code assigns the destination first,
        # so it must NOT be reported as a direct write.
        for kept in (
            'json_target = REPORTS_DIR / "structure_confirmation.json"',
            "targets = {filename: REPORTS_DIR / filename for filename in outputs}",
        ):
            assert not _DIRECT_FIXED_WRITE.search(kept), kept

    @pytest.mark.parametrize("path", RUNNER_FILES, ids=RUNNER_IDS)
    def test_the_published_names_are_unchanged(self, path):
        source = _source(path)

        for name in PUBLICATIONS[path]:
            assert f'"{name}"' in source, name


class TestPublicationTextIsUnchanged:
    """The write sites still hand over the same expressions as before."""

    def test_confirmation_text_expressions_are_unchanged(self):
        source = _source(CONFIRMATION)

        assert (
            "write_evidence(json_target, canonical(payload), replace=replace)" in source
        )
        assert (
            "write_evidence(md_target, render_report(payload), replace=replace)" in source
        )

    def test_element_measurement_text_expressions_are_unchanged(self):
        source = _source(ELEMENT)

        assert '"structure_element_measurement_control.json": canonical(' in source
        assert '"structure_element_measurement_treatment.json": canonical(' in source
        assert '"structure_element_measurement_analysis.json": canonical(' in source
        assert "write_evidence(targets[filename], content, replace=replace)" in source

    def test_confirmation_publishes_through_the_evidence_writer(self):
        source = _source(CONFIRMATION)

        assert "from evaluation.artifacts import ArtifactExistsError, write_evidence" in source


class TestCollisionIsRefusedBeforeAnyWrite:
    """A collision must be loud, non-zero, and must happen before the first byte."""

    @pytest.mark.parametrize("path", RUNNER_FILES, ids=RUNNER_IDS)
    def test_each_runner_parses_the_replace_flag(self, path):
        assert 'replace = "--replace" in argv' in _source(path)

    @pytest.mark.parametrize("path", RUNNER_FILES, ids=RUNNER_IDS)
    def test_every_publication_name_is_pre_flighted_before_the_first_write(self, path):
        source = _source(path)

        pre_flight = source.index("if not replace:")
        first_write = source.index("write_evidence(")
        assert pre_flight < first_write, (
            "the collision check must precede the first write so a refusal cannot "
            "half-publish an artifact set"
        )
        assert "path.exists()" in source

    @pytest.mark.parametrize("path", RUNNER_FILES, ids=RUNNER_IDS)
    def test_a_refusal_is_loud_and_non_zero(self, path):
        source = _source(path)

        refusal = source.index("REFUSING to publish")
        assert "return 2" in source[refusal:], (
            "a refused publication must exit non-zero rather than look successful"
        )

    @pytest.mark.parametrize("path", RUNNER_FILES, ids=RUNNER_IDS)
    def test_a_refusal_names_the_escape_hatch(self, path):
        assert "re-run with --replace" in _source(path)

    @pytest.mark.parametrize("path", RUNNER_FILES, ids=RUNNER_IDS)
    def test_the_artifact_exists_error_is_handled(self, path):
        assert "except ArtifactExistsError" in _source(path)


class TestSmokeOutputIsNotEvidence:
    """Scratch output is deliberately left in a temporary directory."""

    def test_confirmation_smoke_writes_to_a_temporary_directory(self):
        source = _source(CONFIRMATION)

        assert 'tempfile.mkdtemp(prefix="structure-confirmation-smoke-")' in source
        assert '(out_dir / "payload.json").write_text(' in source
        assert '(out_dir / "report.md").write_text(' in source

    def test_element_measurement_smoke_writes_to_a_temporary_directory(self):
        source = _source(ELEMENT)

        assert 'tempfile.mkdtemp(prefix="structure-measurement-smoke-")' in source
        assert '(out_dir / "control.json").write_text(' in source
        assert '(out_dir / "treatment.json").write_text(' in source
        assert '(out_dir / "analysis.json").write_text(' in source


class TestRenderedTextRoundTripsThroughWriteEvidence:
    """The runner's own renderer, byte-compared to the file that was written.

    These modules import heavy experiment dependencies, so this class imports them
    defensively: if the import is unavailable the test is SKIPPED with the reason
    rather than silently passing, and the source-level assertions above stay the
    evidence for the text expressions.  ``render_report`` needs a complete
    payload, so only ``canonical`` is round-tripped here; that the report site
    still passes ``render_report(payload)`` is asserted in
    ``TestPublicationTextIsUnchanged``.
    """

    def test_element_measurement_canonical_text_round_trips(self, tmp_path):
        try:
            from evaluation.experiments import (  # noqa: PLC0415
                run_structure_element_measurement as runner,
            )
        except Exception as exc:  # noqa: BLE001 - reported, never hidden
            pytest.skip(
                "runner import unavailable on this host: "
                f"{type(exc).__name__}: {exc}"
            )

        payload = {"control": {"n": 3, "delta": -0.5}, "treatment": {"n": 3}}
        text = runner.canonical(payload)
        target = tmp_path / "reports" / "structure_element_measurement_control.json"

        artifacts.write_evidence(target, text)

        assert target.read_bytes() == text.encode("utf-8")

    def test_confirmation_canonical_text_round_trips(self, tmp_path):
        try:
            from evaluation.experiments import (  # noqa: PLC0415
                run_structure_confirmation as runner,
            )
        except Exception as exc:  # noqa: BLE001 - reported, never hidden
            pytest.skip(
                "runner import unavailable on this host: "
                f"{type(exc).__name__}: {exc}"
            )

        payload = {"a": 1, "nested": {"b": None}, "list": [1, 2, 3]}
        text = runner.canonical(payload)
        target = tmp_path / "reports" / "structure_confirmation.json"

        artifacts.write_evidence(target, text)

        assert target.read_bytes() == text.encode("utf-8")
