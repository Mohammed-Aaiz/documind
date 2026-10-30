"""Offline research baseline inventory; no application imports, secrets or DB calls.

Run from backend: python -m evaluation.research_manifest freeze --output NEW.json
This records the actual working tree, not a claim that an experiment ran.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = Path(__file__).with_name("datasets") / "research_dataset_template_v1.json"
PUBLIC_SETTINGS = (
    "answer_provider", "answer_auto_fallback", "groq_model", "groq_context_tokens",
    "groq_timeout_seconds", "query_router_enabled", "query_router_timeout_seconds",
    "chunker_version", "visual_embeddings_enabled",
)
SOURCE_PREFIXES = tuple(f"backend/{name}/" for name in (
    "auth", "chat", "conversation", "documents", "embeddings", "generation",
    "graph", "orchestration", "storage", "migrations",
))


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _git(*args: str, root: Path = ROOT) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True, encoding="utf-8").strip()


def source_literals(path: Path, names: tuple[str, ...], *, settings: bool = False) -> dict:
    """Read declarations without importing code or resolving environment files."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    nodes = next(node.body for node in tree.body if isinstance(node, ast.ClassDef)
                 and node.name == "Settings") if settings else tree.body
    result = {}
    for node in nodes:
        name = node.target.id if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) else (
            node.targets[0].id if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) else None)
        if name not in names:
            continue
        value = node.value
        if isinstance(value, ast.Call):
            value = next((kw.value for kw in value.keywords if kw.arg == "default"), None)
        try:
            result[name] = ast.literal_eval(value)
        except (ValueError, TypeError):
            raise ValueError(f"Cannot statically inventory declaration {name}") from None
    if set(result) != set(names):
        raise ValueError("Missing expected baseline declarations")
    return result


def validate_settings(values: object, defaults: dict) -> dict:
    """Only explicit public scalar controls; reject unknown keys, never echo values."""
    if not isinstance(values, dict) or set(values) != set(PUBLIC_SETTINGS):
        raise ValueError("Settings JSON must contain exactly the documented public setting keys")
    for name, value in values.items():
        default = defaults[name]
        # This baseline freezes the current provider/model/chunker. A later
        # component experiment needs its own reviewed source/config manifest.
        if type(value) is not type(default) or isinstance(value, str) and value != default:
            raise ValueError("Invalid public setting type or uncontrolled string setting")
        if isinstance(value, (int, float)) and not isinstance(value, bool) and not 0 < value <= 32768:
            raise ValueError("Numeric public settings must be positive and bounded")
    return values


def build_manifest(root: Path = ROOT, settings: dict | None = None) -> dict:
    defaults = source_literals(root / "backend/config.py", PUBLIC_SETTINGS, settings=True)
    tracked = _git("ls-files", "-z", root=root).split("\0")
    selected = [name for name in tracked if (
        name.startswith(SOURCE_PREFIXES) and name.endswith(".py")
        or name.startswith("backend/requirements") and name.endswith(".txt")
        or name in ("backend/config.py", "backend/tokenization.py", "backend/main.py",
                    "backend/evaluation/production_rag.py", "backend/evaluation/retrieval_metrics.py",
                    "pyproject.toml", "package.json", "package-lock.json"))]
    # Include this new research helper and annotation template before their
    # first commit, identifying them by hashes rather than pretending HEAD owns them.
    selected += ["backend/evaluation/research_manifest.py",
                 "backend/evaluation/datasets/research_dataset_template_v1.json"]
    files = {}
    for name in sorted(set(selected)):
        path = root / name
        if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
            raise ValueError("Baseline source escaped the repository")
        files[name] = sha256(path.read_bytes())
    runtime = dict(sorted((item.metadata["Name"], item.version)
                          for item in importlib.metadata.distributions() if item.metadata["Name"]))
    models = {
        "embedding": source_literals(root / "backend/embeddings/model.py",
                                      ("REPOSITORY", "REVISION", "WEIGHTS_SHA256", "_DIMENSIONS")),
        "reranker": source_literals(root / "backend/generation/reranking.py",
                                     ("REPOSITORY", "REVISION", "MAX_CANDIDATES", "TIMEOUT_SECONDS")),
    }
    manifests = {}
    for name in ("minilm", "reranker", "clip"):
        path = root / "backend/embeddings/assets" / name / "documind_manifest.json"
        manifests[name] = {"status": "present", "sha256": sha256(path.read_bytes())} if path.is_file() else {"status": "missing"}
    return {
        "schema_version": "documind-baseline-manifest-v1",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git("rev-parse", "HEAD", root=root),
        "tracked_worktree_status": _git("status", "--porcelain=v1", "--untracked-files=no", root=root).splitlines(),
        "source_sha256": files,
        "source_snapshot_sha256": sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()),
        "declared_model_constants": models,
        "local_asset_manifest_files": manifests,
        "source_configuration_defaults": defaults,
        "effective_configuration": {"status": "operator_supplied_unverified" if settings else "unverified",
                                    "values": validate_settings(settings, defaults) if settings is not None else None},
        "dependencies_installed": runtime,
        "host": {"system": platform.system(), "machine": platform.machine(),
                 "python": platform.python_version(), "logical_cpu_count": os.cpu_count()},
        "runtime_checks": {"database_schema": "unverified_offline", "index_versions": "unverified_offline",
                           "model_asset_availability": "unverified_offline", "provider_availability": "unverified_offline",
                           "ram_gpu_and_thread_limits": "unverified_offline"},
        "limitations": ["No secrets, environment files, network, model loading or database were accessed.",
                        "HEAD plus hashes identify this working snapshot; dirty files are not a clean committed baseline.",
                        "Source defaults are not effective runtime settings; freeze the latter explicitly before experiments.",
                        "Hosted model revisions may change externally; record returned model and request metadata per run."],
    }


def validate_template(data: dict) -> None:
    """Check this synthetic example's integrity, not research release eligibility.

    This is not a general dataset schema, sufficiency judge, annotation-review
    gate or benchmark scorer. Human decisions and experiment adapters remain
    separate work under the specification.
    """
    if data.get("status") != "synthetic_template_not_benchmark":
        raise ValueError("This command validates the synthetic template, not a research dataset")
    def unique_ids(rows: list[dict]) -> dict:
        ids = [row["id"] for row in rows]
        if any(not isinstance(value, str) or not value.strip() for value in ids) or len(ids) != len(set(ids)):
            raise ValueError("Example IDs must be nonempty and unique within their collection")
        return dict(zip(ids, rows))

    documents = unique_ids(data["documents"])
    questions = unique_ids(data["questions"])
    for doc in documents.values():
        if sha256(doc["synthetic_raw_utf8"].encode()) != doc["raw_file_sha256"]:
            raise ValueError("Synthetic raw source hash mismatch")
        numbers = [page["page"] for page in doc["pages"]]
        if any(type(number) is not int or number < 1 for number in numbers) or len(numbers) != len(set(numbers)):
            raise ValueError("Canonical page numbers must be unique positive integers")
        for page in doc["pages"]:
            if sha256(page["canonical_text"].encode()) != page["canonical_text_sha256"]:
                raise ValueError("Canonical page hash mismatch")
    topics = {topic for doc in documents.values() for topic in doc["topic_ids"]}
    categories = {"localized_single_topic", "distributed_single_topic", "multi_topic_synthesis",
                  "relational_multihop", "unanswerable"}
    for question in questions.values():
        if question["split"] != "development" or not question["bundle_id"]:
            raise ValueError("Synthetic examples must identify their development bundle")
        if question["category"] not in categories or type(question["designated_marks"]) is not int or question["designated_marks"] not in (5, 10, 15):
            raise ValueError("Invalid category or designated marks")
        if any(topic not in topics for topic in question["topic_ids"]):
            raise ValueError("Question references an unknown topic")
        if question["answerability"] not in ("answerable", "unanswerable"):
            raise ValueError("Unknown answerability")
        if (question["category"] == "unanswerable") != (question["answerability"] == "unanswerable"):
            raise ValueError("Category and answerability disagree")
        if bool(question["required_evidence_units"]) != (question["answerability"] == "answerable"):
            raise ValueError("Evidence and answerability disagree")
        for unit in unique_ids(question["required_evidence_units"]).values():
            if not unit["alternatives"]:
                raise ValueError("Evidence unit needs a support alternative")
            for alternative in unit["alternatives"]:
                if not alternative["all_of"]:
                    raise ValueError("An alternative must require at least one span")
                for span in alternative["all_of"]:
                    if span["document_id"] not in documents:
                        raise ValueError("Span references an unknown document")
                    doc = documents[span["document_id"]]
                    if doc["bundle_id"] != question["bundle_id"] or doc["split"] != question["split"]:
                        raise ValueError("Span crosses the question's bundle/split")
                    if span["topic_id"] not in doc["topic_ids"]:
                        raise ValueError("Span references an unknown document topic")
                    pages = {page["page"]: page for page in doc["pages"]}
                    if type(span["page"]) is not int or span["page"] not in pages:
                        raise ValueError("Span references an invalid canonical page")
                    page = pages[span["page"]]
                    text = page["canonical_text"]
                    start, end = span["start_char"], span["end_char"]
                    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
                        raise ValueError("Invalid half-open canonical character offsets")
                    if text[start:end] != span["quote"] or sha256(span["quote"].encode()) != span["quote_sha256"]:
                        raise ValueError("Evidence quote/offset/hash mismatch")
        if set(question["rubrics"]) != {"5", "10", "15"}:
            raise ValueError("Missing mark-specific rubric")
        for marks, rubric in question["rubrics"].items():
            maxima = [item["max_marks"] for item in rubric["criteria"]]
            if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0 for value in maxima):
                raise ValueError("Criterion marks must be finite nonnegative numbers")
            if rubric["max_marks"] != int(marks) or sum(maxima) != int(marks):
                raise ValueError("Rubric does not total available marks")
        if len(question["independent_annotation_reviews"]) != 2:
            raise ValueError("Template requires two independent annotation review slots")


def write_new_json(path: Path, data: dict) -> str:
    payload = (json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
    with path.open("xb") as stream:
        stream.write(payload)
    return sha256(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    freeze = sub.add_parser("freeze")
    freeze.add_argument("--output", type=Path, required=True)
    freeze.add_argument("--settings", type=Path, help="Explicit public JSON; never an .env file")
    sub.add_parser("validate-template")
    sub.add_parser("self-check")
    args = parser.parse_args()
    if args.command == "freeze":
        settings = None
        if args.settings is not None:
            if args.settings.suffix != ".json":
                parser.error("--settings accepts only an explicitly prepared public JSON document")
            settings = json.loads(args.settings.read_text(encoding="utf-8"))
        print(write_new_json(args.output, build_manifest(settings=settings)))
    else:
        data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        validate_template(data)
        if args.command == "self-check":
            from copy import deepcopy
            broken_quote = deepcopy(data)
            broken_quote["questions"][0]["required_evidence_units"][0]["alternatives"][0]["all_of"][0]["start_char"] += 1
            broken_rubric = deepcopy(data)
            criteria = broken_rubric["questions"][0]["rubrics"]["5"]["criteria"]
            criteria[0]["max_marks"], criteria[1]["max_marks"] = -1, 6
            for broken in (broken_quote, broken_rubric):
                try:
                    validate_template(broken)
                except ValueError:
                    pass
                else:
                    raise AssertionError("Tampered quote or compensated negative rubric accepted")
            defaults = source_literals(ROOT / "backend/config.py", PUBLIC_SETTINGS, settings=True)
            assert validate_settings(defaults, defaults) == defaults
            try:
                validate_settings({**defaults, "groq_api_key": "do-not-persist"}, defaults)
            except ValueError:
                pass
            else:
                raise AssertionError("Unknown setting accepted")
            import tempfile
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "manifest.json"
                write_new_json(path, {"valid": True})
                try:
                    write_new_json(path, {"valid": False})
                except FileExistsError:
                    pass
                else:
                    raise AssertionError("Existing artifact overwritten")
                assert json.loads(path.read_text()) == {"valid": True}
        print("research manifest/template check passed (offline; no benchmark results)")


if __name__ == "__main__":
    main()
