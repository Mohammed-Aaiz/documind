"""STEP 1.6Y: the RRF-calibration runner must not silently replace evidence.

``run_structure_rrf_calibration.py`` is the last of the modules that published its
report to a fixed ``evaluation/reports/`` path with ``Path.write_text``, so a
re-run replaced the previously recorded result without a word.  It now publishes
through ``evaluation.artifacts.write_evidence`` (append-only by default) with an
explicit ``--replace`` opt-in for a deliberate re-publication.

The other converted writers are covered by ``test_writer_collision_*.py`` and by
the append-only contract tests; this module pins the wiring of this runner, which
is read as TEXT and never imported, so no engine, session, model or database is
touched.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from evaluation.artifacts import ArtifactExistsError, write_evidence

BACKEND_DIR = Path(__file__).resolve().parents[3]
RUNNER = BACKEND_DIR / "evaluation" / "experiments" / "run_structure_rrf_calibration.py"

JSON_NAME = "structure_rrf_calibration.json"
MD_NAME = "structure_rrf_calibration_report.md"


def _source() -> str:
    return RUNNER.read_text(encoding="utf-8")


def _main_source() -> str:
    text = _source()
    start = text.index("\nasync def main(")
    end = text.find("\ndef ", start + 1)
    return text[start:] if end == -1 else text[start:end]


# ---------------------------------------------------------------------------
# Source wiring: the runner actually uses the central writer
# ---------------------------------------------------------------------------


def test_fixed_path_writes_go_through_the_central_writer():
    source = _source()
    assert "from evaluation.artifacts import ArtifactExistsError, write_evidence" in source
    assert "write_evidence(json_target, canonical(payload), replace=replace)" in source
    assert (
        "write_evidence(md_target, render_report(payload), replace=replace)" in source
    )


def test_no_bare_write_text_remains_at_the_publication_site():
    """Every remaining ``write_text`` in main() is scratch, not publication.

    Deliberately precise rather than a blanket ban: the ``--smoke`` branch writes
    into a ``tempfile.mkdtemp`` directory, which is caller-scoped scratch output
    rather than recorded evidence, and is left as it is.
    """
    main = _main_source()
    write_lines = [
        line for line in main.splitlines() if ".write_text(" in line
    ]
    assert write_lines, "expected the smoke scratch writes to still exist"
    for line in write_lines:
        assert "REPORTS_DIR" not in line, line
        assert "out_dir" in line, line
    assert 'tempfile.mkdtemp(prefix="rrf-calibration-smoke-")' in main


def test_replace_is_an_explicit_operator_flag():
    main = _main_source()
    assert 'replace = "--replace" in argv' in main
    assert "if not replace:" in main
    assert "return 2" in main


def test_both_destinations_are_checked_before_either_is_written():
    main = _main_source()
    preflight = main.index("if not replace:")
    assert preflight < main.index("write_evidence(json_target"), (
        "the collision pre-flight must precede the first write, so a refusal "
        "cannot leave a fresh .json beside a stale .md"
    )
    assert "except ArtifactExistsError" in main


# ---------------------------------------------------------------------------
# Behaviour: the writer those names go through is append-only by default
# ---------------------------------------------------------------------------


def test_publishing_these_names_refuses_and_preserves_previous_evidence(tmp_path):
    json_path, md_path = tmp_path / JSON_NAME, tmp_path / MD_NAME
    write_evidence(json_path, "{}\n")
    write_evidence(md_path, "# previous\n")

    with pytest.raises(ArtifactExistsError) as refusal:
        write_evidence(json_path, '{"new": true}\n')

    assert JSON_NAME in str(refusal.value)
    assert json_path.read_text(encoding="utf-8") == "{}\n"
    assert md_path.read_text(encoding="utf-8") == "# previous\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == [JSON_NAME, MD_NAME]


def test_replace_republishes_these_names_on_purpose(tmp_path):
    json_path = tmp_path / JSON_NAME
    write_evidence(json_path, "{}\n")
    write_evidence(json_path, '{"new": true}\n', replace=True)
    assert json_path.read_text(encoding="utf-8") == '{"new": true}\n'
    assert sorted(p.name for p in tmp_path.iterdir()) == [JSON_NAME]
