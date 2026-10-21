"""Append-only run artifacts for research runners: output directories, exclusive
writes and reproducibility manifests.

Two problems this module removes:

* **Report paths were fixed.**  ``evaluation/runner.py`` wrote every report into
  ``evaluation/reports/`` with no override, so re-running a measurement silently
  replaced a recorded result.  :class:`RunOutput` takes a caller-supplied
  directory, refuses to overwrite anything, and never touches the historical
  reports.
* **Runs were not reproducible.**  Nothing recorded which commit, corpus,
  benchmark, model or configuration produced a report.  :func:`collect_run_manifest`
  captures what can actually be determined and records ``"unavailable"`` for
  what cannot — it never invents a value.

Safety rules
------------
* ``RunOutput`` creates nothing until the first write: a run that refuses to
  start (guard, preflight collision) leaves the filesystem untouched.
* Every write uses ``open(path, "x")`` — exclusive create — so even a race
  between two concurrent runs cannot overwrite an artifact.
* A multi-file report is *pre-flighted* with :meth:`RunOutput.reserve` before the
  first byte is written, so a name collision fails the whole run rather than
  half-writing it.  The manifest is written last: a directory that contains
  reports but no ``run_manifest.json`` is by definition an interrupted run.
* Credentials never enter an artifact: the manifest records database
  *identities* (host, port, database), never DSNs with user info, and no
  environment value is copied into a report.

Research code: never imported by production modules and never collected by
pytest (``pytest.ini`` sets ``testpaths = tests``).
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from uuid import uuid4

#: ``evaluation/artifacts.py`` -> ``evaluation`` -> ``backend``.
BACKEND_DIR = Path(__file__).resolve().parents[1]

#: The frozen, read-only QA benchmark.  Recorded in every manifest so a report
#: can be tied to the exact benchmark revision that produced it.  It is never
#: written to.
FROZEN_BENCHMARK = (
    BACKEND_DIR
    / "phases"
    / "phase4f"
    / "phase4f_5d"
    / "benchmark"
    / "qa_benchmark_v1.jsonl"
)

#: Name of the manifest every instrumented run writes into its output directory.
MANIFEST_NAME = "run_manifest.json"

#: Manifest schema version, so a later reader can tell how to interpret one.
MANIFEST_SCHEMA_VERSION = 1

#: Candidate weight files inside a local QA model directory, in preference order.
_WEIGHT_FILES = ("model.safetensors", "pytorch_model.bin", "model.onnx")

_HASH_CHUNK = 1024 * 1024


class ArtifactExistsError(RuntimeError):
    """A write would overwrite an existing evaluation artifact."""


def new_run_id(now: datetime | None = None) -> str:
    """A sortable, unique run identifier: ``YYYYMMDDTHHMMSSZ-<8 hex>``."""
    stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return f"{stamp.strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"


def _relative_to_backend(path: Path) -> str:
    """``path`` relative to ``backend/`` when possible.

    Reports stay machine-independent: an absolute path from one developer's
    checkout is not reproducible evidence anywhere else.
    """
    resolved = path.resolve()
    try:
        return resolved.relative_to(BACKEND_DIR.resolve()).as_posix()
    except ValueError:
        return path.name


class RunOutput:
    """A caller-specified, append-only output directory.

    ``directory`` is used exactly as given (so a caller who passes a relative
    path gets a relative path recorded in the manifest).
    """

    def __init__(self, directory: Path | str):
        self.directory = Path(directory)
        self.reserved: list[Path] = []
        self.written: list[Path] = []

    # -- planning ---------------------------------------------------------

    def reserve(self, *names: str) -> list[Path]:
        """Reserve destinations, refusing if any of them already exists.

        Call this for *all* files a run will produce before writing any of them:
        a collision then fails the run before a partial artifact set exists.
        """
        targets = [self.directory / name for name in names]
        collisions = [str(target) for target in targets if target.exists()]
        if collisions:
            raise ArtifactExistsError(
                "refusing to overwrite existing evaluation artifacts: "
                + ", ".join(collisions)
                + ". Evaluation artifacts are append-only — choose a new --out "
                "directory (or a new file name) rather than replacing a recorded "
                "result."
            )
        self.reserved.extend(targets)
        return targets

    def path(self, name: str) -> Path:
        return self.directory / name

    # -- writing ----------------------------------------------------------

    def write_text(self, name: str, text: str, *, reserved: bool = False) -> Path:
        """Write ``name`` with an exclusive create; never replaces a file.

        ``newline="\\n"`` keeps the bytes identical on every platform, so a
        recorded digest matches what a later reader hashes.
        """
        path = self.directory / name
        if not reserved and path not in self.reserved:
            raise ArtifactExistsError(
                f"{name!r} was not reserved on this RunOutput; call reserve() (or "
                "pass reserved=True) so a name collision cannot half-write a run"
            )
        self.directory.mkdir(parents=True, exist_ok=True)
        try:
            # "x" — exclusive create: fails rather than replacing a file that
            # appeared between reserve() and this write.
            with open(path, "x", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
        except FileExistsError as error:
            raise ArtifactExistsError(
                f"refusing to overwrite {path}: evaluation artifacts are append-only"
            ) from error
        self.written.append(path)
        return path

    def write_json(self, name: str, payload: Any, *, reserved: bool = False) -> Path:
        """Write a machine-readable artifact, deterministically formatted."""
        return self.write_text(
            name,
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            reserved=reserved,
        )

    def names(self, paths: Iterable[Path]) -> list[str]:
        """The bare file names of ``paths`` (what the manifest records)."""
        return sorted(path.name for path in paths)


# ---------------------------------------------------------------------------
# Fixed-path evidence: the same exclusive-create rule, without a run directory
# ---------------------------------------------------------------------------


def write_evidence(path: Path, text: str, *, replace: bool = False) -> Path:
    """Write ONE evidence file at ``path``, refusing to replace an existing one.

    :class:`RunOutput` covers a run that owns a whole output directory.  Several
    measurement modules instead publish to a fixed location
    (``evaluation/reports/<name>.json``) and used to do it with
    ``Path.write_text``, which silently replaced the previous run's recorded
    result.  This is the *same* rule as ``RunOutput.write_text`` — exclusive
    create, ``ArtifactExistsError`` on a collision, never a partial file —
    applied to a single known destination.  It is deliberately not a second
    artifact-writing abstraction: it shares the error type, the encoding and the
    ``newline="\n"`` reproducibility guarantee with ``RunOutput``, and it exists
    only so a fixed-path writer does not have to invent a run directory.

    ``replace=True`` is an explicit, visible opt-in for a *deliberate*
    re-publication (for example a module whose documented contract is to re-run
    for a byte-determinism comparison).  It must be requested at the call site
    or by an operator flag: it is never the default and never inferred, so an
    existing artifact is preserved and the caller is told rather than the
    evidence being lost quietly.

    A deliberate re-publication never truncates the evidence it replaces: the
    content goes to a uniquely named sibling first — ``<name>.<pid>.<hex>.tmp``,
    so two concurrent re-publications cannot share a temporary and an unrelated
    file that happens to be called ``<name>.tmp`` is never touched — and is then
    moved into place with :func:`os.replace`.  A failing write leaves the
    previous artifact intact and removes its own temporary; only a hard crash
    between the two steps can leave a stray temporary behind, and the
    destination is untouched even then.

    A failure of :func:`os.replace` itself (for example a cross-device move)
    propagates as :class:`OSError` rather than being reported as a collision:
    the nine callers catch :class:`ArtifactExistsError`, so such a failure ends
    the run loudly instead of looking like a successful publication.
    """
    destination = Path(path)
    if destination.exists() and not replace:
        raise ArtifactExistsError(
            f"refusing to replace existing evaluation evidence: {destination}. "
            "Evaluation artifacts are append-only — write to a new name, or pass "
            "replace=True for a deliberate re-publication."
        )

    destination.parent.mkdir(parents=True, exist_ok=True)

    if replace:
        # Deliberate re-publication: write the sibling first, then swap it in.
        # The name carries this process's pid and a random suffix so a concurrent
        # re-publication cannot share it and a pre-existing ``<name>.tmp`` (which
        # might be somebody's real file) is never opened for writing.
        temporary = destination.with_name(
            f"{destination.name}.{os.getpid()}.{uuid4().hex[:8]}.tmp"
        )
        try:
            with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
            os.replace(temporary, destination)
        except OSError:
            try:
                temporary.unlink()
            except OSError:
                pass
            raise
        return destination

    try:
        # "x" — exclusive create: a file that appears between the check above
        # and this write is still refused rather than replaced.
        with open(destination, "x", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    except FileExistsError as error:
        raise ArtifactExistsError(
            f"refusing to replace {destination}: evaluation artifacts are "
            "append-only"
        ) from error
    return destination


# ---------------------------------------------------------------------------
# Provenance: repository, benchmark, model
# ---------------------------------------------------------------------------


def _git(*args: str, cwd: Path | None = None) -> str | None:
    """Run a git command, returning stdout or ``None`` when it cannot be read."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd or BACKEND_DIR),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):  # git absent, not a repo, hung
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def repository_state(*, cwd: Path | None = None) -> dict[str, Any]:
    """Commit, branch and working-tree status at the moment of the run.

    Records ``"unavailable"`` rather than guessing when git cannot be read.
    """
    commit = _git("rev-parse", "HEAD", cwd=cwd)
    if not commit:
        return {"status": "unavailable"}

    porcelain = _git("status", "--porcelain", cwd=cwd)
    changed = [line for line in (porcelain or "").splitlines() if line.strip()]

    state: dict[str, Any] = {
        "commit": commit,
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd) or "unavailable",
    }
    if porcelain is None:
        state["workingTree"] = "unavailable"
    else:
        state["workingTree"] = "clean" if not changed else "dirty"
        state["changedPathCount"] = len(changed)
    return state


def sha256_file(path: Path) -> str:
    """SHA-256 of a file, read in chunks so a large artifact is never loaded whole."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(_HASH_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def benchmark_digest(path: Path | None = None) -> dict[str, Any]:
    """Identity of a benchmark file: path, size, SHA-256 and example count.

    Read-only.  The frozen benchmark must never be modified, so this only ever
    reads it.
    """
    target = FROZEN_BENCHMARK if path is None else Path(path)

    if not target.is_file():
        return {"status": "unavailable", "path": _relative_to_backend(target)}

    raw = target.read_bytes()
    return {
        "path": _relative_to_backend(target),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "examples": sum(1 for line in raw.splitlines() if line.strip()),
    }


def model_provenance(
    qa_model_path: str | Path | None = None,
    *,
    embedding_model: str | None = None,
    embedding_dimensions: int | None = None,
) -> dict[str, Any]:
    """Identifiers and digest of the local models a run used.

    The QA model's weight file is hashed: a path alone says nothing about which
    revision of the weights produced a number.  Anything that cannot be
    determined is recorded as ``"unavailable"``.
    """
    raw_path = qa_model_path or os.environ.get("QA_MODEL_NAME") or "./models/documind-qa"
    directory = Path(raw_path)
    if not directory.is_absolute():
        directory = (BACKEND_DIR / directory).resolve()

    provenance: dict[str, Any] = {
        "qaModelPath": _relative_to_backend(directory),
        "qaModelWeights": "unavailable",
        "qaModelWeightsSha256": "unavailable",
    }

    if directory.is_dir():
        for name in _WEIGHT_FILES:
            candidate = directory / name
            if candidate.is_file():
                provenance["qaModelWeights"] = name
                provenance["qaModelWeightsSha256"] = sha256_file(candidate)
                provenance["qaModelWeightsBytes"] = candidate.stat().st_size
                break

    if embedding_model:
        provenance["embeddingModel"] = embedding_model
    if embedding_dimensions is not None:
        provenance["embeddingDimensions"] = embedding_dimensions
    return provenance


# ---------------------------------------------------------------------------
# The manifest
# ---------------------------------------------------------------------------


def collect_run_manifest(
    *,
    run_id: str,
    runner: str,
    protocol: str,
    output: RunOutput,
    result: Mapping[str, Any],
    database: Mapping[str, Any] | None = None,
    dataset: Mapping[str, Any] | None = None,
    configuration: Mapping[str, Any] | None = None,
    model: Mapping[str, Any] | None = None,
    benchmark_path: Path | None = None,
    extras: Mapping[str, Any] | None = None,
    cwd: Path | None = None,
) -> dict[str, Any]:
    """Everything needed to reproduce (or to distrust) one evaluation run.

    Contains no credentials, no ``.env`` contents, no document text and no
    absolute checkout paths: database entries are identities, dataset entries
    are counts and identifiers, and paths are relative to ``backend/``.
    """
    manifest: dict[str, Any] = {
        "schemaVersion": MANIFEST_SCHEMA_VERSION,
        "runId": run_id,
        "runner": runner,
        "protocol": protocol,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "repository": repository_state(cwd=cwd),
        "database": dict(database) if database else {"status": "unavailable"},
        "dataset": dict(dataset) if dataset else {"status": "unavailable"},
        "benchmark": benchmark_digest(benchmark_path),
        "configuration": dict(configuration) if configuration else {"status": "unavailable"},
        "model": dict(model) if model else {"status": "unavailable"},
        "output": {
            # Repository-relative when the run wrote inside the repository,
            # otherwise just the base name the caller asked for: a recorded
            # manifest must not carry a developer's absolute home directory.
            "directory": _relative_to_backend(output.directory),
            "plannedFiles": output.names(output.reserved),
            "filesWritten": output.names(output.written),
        },
        "result": dict(result),
    }
    if extras:
        manifest["extras"] = dict(extras)
    return manifest


def write_manifest(output: RunOutput, manifest: Mapping[str, Any]) -> Path:
    """Write the manifest — always last, so its absence marks an incomplete run.

    ``run_manifest.json`` is reserved by the caller together with the other
    artifacts, so this respects the same no-overwrite rule as every other write.
    """
    return output.write_json(MANIFEST_NAME, manifest)
