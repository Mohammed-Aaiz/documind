"""STEP 1.6X / 1.6Z: an inline destructive block must not be an ungated entry point.

The lifecycle policy is function-level: a callable that deletes rows carries
``assert_cleanup_execution_authorized`` on its own code path, not merely whatever
gate the runner performed earlier.  Three runners issue row deletions *inline*
inside ``main()``:

* ``run_phase3d_upload_integration.py`` — an inline block of raw ``DELETE FROM``
  statements (gated in Step 1.6X);
* ``run_phase3e_integration.py`` — an inline ``delete(DocumentChunk)`` /
  ``delete(Document)`` block scoped to the one id that step created (gated in
  Step 1.6Z);
* ``run_phase3e_validation.py`` — the same shape for the two ids that step
  created (gated in Step 1.6Z).

All three are unreachable today because ``assert_disposal_authorized`` refuses
unconditionally at the top of ``main()``; the gates exist so that enabling
lifecycle authorization later cannot silently create an ungated deletion.

Like the other guard-order tests in this directory, each runner is read as text
and never imported: no engine, session, settings read, application import or
database connection happens here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[3]
RUNNER_DIR = BACKEND_DIR / "evaluation" / "experiments"
RUNNER = "run_phase3d_upload_integration.py"

#: Runner file -> the operation string its inline block is gated as.  Keyed by
#: file so a gate that names the wrong phase cannot pass.
EXPECTED_OPERATIONS = {
    "run_phase3d_upload_integration.py": "Phase 3D upload inline raw-SQL row cleanup",
    "run_phase3e_integration.py": "Phase 3E integration inline document-row cleanup",
    "run_phase3e_validation.py": "Phase 3E validation inline document-row cleanup",
}

#: An ORM delete of a model, e.g. ``delete(DocumentChunk)``.  Deliberately
#: requires a capitalised model name so ``delete_upload`` / ``delete(...)`` of a
#: lowercase local cannot match.
_ORM_DELETE = re.compile(r"\bdelete\(\s*[A-Z]\w*")


def _source(filename: str = RUNNER) -> str:
    return (RUNNER_DIR / filename).read_text(encoding="utf-8")


def _main_source(filename: str = RUNNER) -> str:
    """The text of ``main()``, read without importing the runner."""
    text = _source(filename)
    start = text.index("\nasync def main(")
    end = text.find("\ndef ", start + 1)
    return text[start:] if end == -1 else text[start:end]


def _inline_delete_positions(main: str) -> list[int]:
    """Positions of inline destructive statements issued directly by ``main()``.

    Anchored on ``await db.execute(`` and then narrowed to statements carrying
    either raw ``DELETE FROM`` text or an ORM ``delete(Model)`` argument, so
    unrelated names (``delete_upload``, ``os.unlink``, ``ZipFile``) and prose in
    a comment cannot be mistaken for a deletion.
    """
    positions: list[int] = []
    for match in re.finditer(r"await db\.execute\(", main):
        window = main[match.start() : match.start() + 200]
        if "DELETE FROM" in window or _ORM_DELETE.search(window):
            positions.append(match.start())
    return positions


# ---------------------------------------------------------------------------
# The original Step 1.6X assertions (raw SQL, upload runner)
# ---------------------------------------------------------------------------


def test_inline_raw_sql_deletes_are_gated():
    """Every inline raw ``DELETE FROM`` in ``main()`` follows the cleanup gate."""
    main = _main_source()
    gate = main.index("assert_cleanup_execution_authorized(")
    deletes = [
        position
        for position in range(len(main))
        if main.startswith("DELETE FROM", position)
    ]
    assert deletes, (
        "the inline raw-SQL cleanup statements are expected to still exist; if "
        "they were removed, delete this test rather than leaving it vacuous"
    )
    assert all(gate < position for position in deletes), (
        "the function-level cleanup authorization gate must precede every inline "
        "raw-SQL DELETE in main()"
    )


def test_inline_gate_names_its_own_operation():
    """The inline block is gated as its own operation, not folded into another."""
    assert 'operation="Phase 3D upload inline raw-SQL row cleanup"' in _main_source()


def test_gate_symbol_is_imported_at_module_level():
    """The gate is a real module-level import, not an unresolved name."""
    imports = _source().split("PASSED:")[0]
    assert "assert_cleanup_execution_authorized," in imports


# ---------------------------------------------------------------------------
# Step 1.6Z: the same property for every runner with an inline deletion block
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("runner_name", sorted(EXPECTED_OPERATIONS))
def test_every_inline_delete_is_preceded_by_its_gate(runner_name):
    """Each runner's inline deletion carries its own gate, on its own path."""
    main = _main_source(runner_name)
    positions = _inline_delete_positions(main)
    assert positions, (
        f"{runner_name}: expected an inline destructive block in main(); if it "
        "was removed, delete this test rather than leaving it vacuous"
    )
    assert "assert_cleanup_execution_authorized(" in main, (
        f"{runner_name}: the inline deletion has no function-level gate"
    )
    gate = main.index("assert_cleanup_execution_authorized(")
    assert all(gate < position for position in positions), (
        f"{runner_name}: the inline cleanup gate must precede every inline delete"
    )


@pytest.mark.parametrize("runner_name", sorted(EXPECTED_OPERATIONS))
def test_each_inline_gate_names_its_own_operation(runner_name):
    """A gate naming another phase's operation would not identify this block."""
    main = _main_source(runner_name)
    assert (
        f'operation="{EXPECTED_OPERATIONS[runner_name]}"' in main
    ), f"{runner_name}: inline gate operation string missing or renamed"


@pytest.mark.parametrize("runner_name", sorted(EXPECTED_OPERATIONS))
def test_each_gate_symbol_is_imported_at_module_level(runner_name):
    """The gate is a real module-level import in every runner."""
    imports = _source(runner_name).split("PASSED:")[0]
    assert "assert_cleanup_execution_authorized," in imports, f"{runner_name}"


def test_detector_has_positive_and_negative_controls():
    """The detector cannot go vacuous or over-broad."""
    # positive controls: both statement forms must be found
    assert _inline_delete_positions("    await db.execute(delete(Document))\n")
    assert _inline_delete_positions(
        "    await db.execute(\n        text(\"DELETE FROM users WHERE id = :i\")\n    )\n"
    )
    # negative controls: reads, other helpers and prose must not be found
    assert _inline_delete_positions("    await db.execute(select(Document))\n") == []
    assert _inline_delete_positions("    cleanup_new_file(delete_upload(path))\n") == []
    assert _inline_delete_positions("    # delete(Document) is gated below\n") == []
    assert _inline_delete_positions("    await db.execute(insert(Document))\n") == []
