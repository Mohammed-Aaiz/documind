"""Tests for the append-only run-artifact writer and the run manifest.

A recorded measurement is evidence: a later run must not be able to replace it.
These tests pin the output-directory contract (explicit destination, exclusive
create, pre-flight so a collision cannot half-write a run) and the manifest's
provenance fields — including that no credential can reach an artifact.
"""

from __future__ import annotations

import json

import pytest

from evaluation import artifacts

#: SHA-256 of the frozen, read-only QA benchmark
#: (``phases/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl``).  It is a
#: protected artifact: changing it is a deliberate, gated act, so this test
#: failing is the intended signal that the benchmark moved.
FROZEN_BENCHMARK_SHA256 = (
    "1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0"
)
FROZEN_BENCHMARK_EXAMPLES = 182


class TestRunOutput:
    def test_planned_destination_is_used(self, tmp_path):
        output = artifacts.RunOutput(tmp_path / "run-1")
        output.reserve("report.json")

        path = output.write_json("report.json", {"a": 1})

        assert path == tmp_path / "run-1" / "report.json"
        assert json.loads(path.read_text(encoding="utf-8")) == {"a": 1}

    def test_nothing_is_created_before_the_first_write(self, tmp_path):
        directory = tmp_path / "run-1"
        output = artifacts.RunOutput(directory)
        output.reserve("report.json")

        assert not directory.exists()
        assert not list(tmp_path.iterdir())

    def test_existing_artifact_is_never_overwritten(self, tmp_path):
        recorded = tmp_path / "report.json"
        recorded.write_text("recorded result", encoding="utf-8")
        output = artifacts.RunOutput(tmp_path)

        with pytest.raises(artifacts.ArtifactExistsError, match="append-only"):
            output.reserve("report.json")

        assert recorded.read_text(encoding="utf-8") == "recorded result"

    def test_preflight_refusal_writes_nothing_at_all(self, tmp_path):
        (tmp_path / "b.json").write_text("existing", encoding="utf-8")
        output = artifacts.RunOutput(tmp_path)

        with pytest.raises(artifacts.ArtifactExistsError):
            output.reserve("a.json", "b.json", "c.json")

        assert not (tmp_path / "a.json").exists()
        assert not (tmp_path / "c.json").exists()

    def test_unreserved_write_is_refused(self, tmp_path):
        output = artifacts.RunOutput(tmp_path)

        with pytest.raises(artifacts.ArtifactExistsError, match="not reserved"):
            output.write_json("sneaky.json", {})

        assert not (tmp_path / "sneaky.json").exists()

    def test_a_file_appearing_after_reserve_is_not_replaced(self, tmp_path):
        output = artifacts.RunOutput(tmp_path)
        output.reserve("report.json")
        # Simulates a second run racing the same directory after pre-flight.
        (tmp_path / "report.json").write_text("appeared later", encoding="utf-8")

        with pytest.raises(artifacts.ArtifactExistsError):
            output.write_json("report.json", {"a": 1})

        assert (tmp_path / "report.json").read_text(encoding="utf-8") == "appeared later"

    def test_two_runs_produce_separate_artifacts(self, tmp_path):
        first = artifacts.RunOutput(tmp_path / "run-1")
        second = artifacts.RunOutput(tmp_path / "run-2")
        for output in (first, second):
            output.reserve("report.json")
        first.write_json("report.json", {"run": 1})
        second.write_json("report.json", {"run": 2})

        assert json.loads((tmp_path / "run-1" / "report.json").read_text())["run"] == 1
        assert json.loads((tmp_path / "run-2" / "report.json").read_text())["run"] == 2
        assert (tmp_path / "run-1" / "report.json").read_bytes() != (
            tmp_path / "run-2" / "report.json"
        ).read_bytes()

    def test_written_bytes_are_platform_stable(self, tmp_path):
        output = artifacts.RunOutput(tmp_path)
        output.reserve("x.json")

        output.write_json("x.json", {"b": 1, "a": 2})

        raw = (tmp_path / "x.json").read_bytes()
        assert b"\r\n" not in raw, "a recorded digest must not depend on the platform"
        assert raw.endswith(b"\n")
        assert raw.index(b'"a"') < raw.index(b'"b"'), "sort_keys must be deterministic"


class TestRunManifest:
    def _manifest(self, tmp_path, **overrides):
        output = artifacts.RunOutput(tmp_path / "artifacts")
        output.reserve("report.json", artifacts.MANIFEST_NAME)
        output.write_json("report.json", {"baseline": "B4_dual_path"})

        kwargs = dict(
            run_id="20260101T000000Z-deadbeef",
            runner="evaluation/experiments/run_example.py",
            protocol="example protocol",
            output=output,
            result={"status": "completed"},
            database={
                "evaluation": "localhost:55433/documind_integration",
                "application": "localhost:55433/documind",
                "isolated": True,
            },
            dataset={"identifier": "phase3d", "version": "unavailable", "questions": 42},
            configuration={"topK": 5},
            model={"qaModelPath": "models/documind-qa"},
        )
        kwargs.update(overrides)
        return artifacts.collect_run_manifest(**kwargs)

    def test_records_the_required_provenance(self, tmp_path):
        manifest = self._manifest(tmp_path)

        assert manifest["schemaVersion"] == artifacts.MANIFEST_SCHEMA_VERSION
        assert manifest["runId"] == "20260101T000000Z-deadbeef"
        assert manifest["runner"].endswith("run_example.py")
        assert manifest["protocol"] == "example protocol"
        assert manifest["generatedAt"]
        assert manifest["python"]

        repository = manifest["repository"]
        if repository.get("status") == "unavailable":
            pytest.skip("git metadata is unavailable in this environment")
        assert len(repository["commit"]) == 40
        int(repository["commit"], 16)  # a real hash, not prose
        assert repository["branch"]
        assert repository["workingTree"] in {"clean", "dirty", "unavailable"}
        assert isinstance(repository["changedPathCount"], int)

        assert manifest["dataset"]["identifier"] == "phase3d"
        assert manifest["configuration"]["topK"] == 5
        assert manifest["model"]["qaModelPath"] == "models/documind-qa"
        assert manifest["result"]["status"] == "completed"

    def test_output_block_names_the_artifacts(self, tmp_path):
        manifest = self._manifest(tmp_path)

        output = manifest["output"]
        assert output["directory"] == "artifacts"
        assert output["plannedFiles"] == ["report.json", artifacts.MANIFEST_NAME]
        assert output["filesWritten"] == ["report.json"], (
            "the manifest itself is written after this snapshot — that is how an "
            "interrupted run is recognised"
        )

    def test_undeterminable_values_are_marked_unavailable_not_invented(self, tmp_path):
        manifest = self._manifest(
            tmp_path, database=None, dataset=None, configuration=None, model=None
        )

        for section in ("database", "dataset", "configuration", "model"):
            assert manifest[section] == {"status": "unavailable"}, section

    def test_frozen_benchmark_digest_is_recorded_and_unchanged(self, tmp_path):
        manifest = self._manifest(tmp_path)

        benchmark = manifest["benchmark"]
        assert benchmark["examples"] == FROZEN_BENCHMARK_EXAMPLES
        assert benchmark["sha256"] == FROZEN_BENCHMARK_SHA256
        assert benchmark["path"].endswith("qa_benchmark_v1.jsonl")
        assert not benchmark["path"].startswith("/")

    def test_no_credentials_reach_the_manifest(self, tmp_path, monkeypatch):
        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+asyncpg://documind:sup3r-s3cr3t@localhost:55433/documind",
        )

        payload = json.dumps(self._manifest(tmp_path))

        assert "s3cr3t" not in payload
        assert "sup3r" not in payload
        assert "postgresql" not in payload, "no DSN is copied into a manifest"
        assert "documind:sup3r" not in payload

    def test_manifest_paths_are_not_absolute_checkout_paths(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        manifest = self._manifest(tmp_path)

        assert not str(manifest["output"]["directory"]).startswith(("/", "C:", "\\\\"))


class TestModelProvenance:
    #: SHA-256 of the provisioned QA weights (``models/documind-qa/model.safetensors``),
    #: as recorded by the Phase 0 closure audit.  A changed digest means the model
    #: the reports describe is no longer the model on disk.
    QA_WEIGHTS_SHA256 = "cb9f1dde94fca0e1f82c440bdc184ff54ba02efb6ea432e37a8c6ff8a8f69deb"

    def test_real_weights_are_identified_by_digest_not_by_path(self):
        provenance = artifacts.model_provenance("./models/documind-qa")

        if provenance["qaModelWeights"] == "unavailable":
            pytest.skip("the QA model is not provisioned in this checkout")
        assert provenance["qaModelPath"] == "models/documind-qa"
        assert provenance["qaModelWeightsSha256"] == self.QA_WEIGHTS_SHA256
        assert provenance["qaModelWeightsBytes"] > 0

    def test_missing_model_directory_is_unavailable_not_invented(self, tmp_path):
        provenance = artifacts.model_provenance(tmp_path / "no-such-model")

        assert provenance["qaModelWeights"] == "unavailable"
        assert provenance["qaModelWeightsSha256"] == "unavailable"


class TestManifestWriting:
    def test_manifest_is_the_last_artifact(self, tmp_path):
        output = artifacts.RunOutput(tmp_path)
        output.reserve("report.json", artifacts.MANIFEST_NAME)
        output.write_json("report.json", {})

        written = output.write_json(artifacts.MANIFEST_NAME, {"result": {"status": "completed"}})

        assert written.name == artifacts.MANIFEST_NAME
        assert written.exists()
        assert sorted(path.name for path in output.written) == sorted(
            ["report.json", artifacts.MANIFEST_NAME]
        )

    def test_run_ids_are_unique_and_sortable(self):
        ids = {artifacts.new_run_id() for _ in range(20)}
        assert len(ids) == 20
        assert all(len(run_id) == len("20260101T000000Z-deadbeef") for run_id in ids)
