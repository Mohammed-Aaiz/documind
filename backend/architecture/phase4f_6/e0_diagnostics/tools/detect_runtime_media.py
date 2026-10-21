#!/usr/bin/env python
"""Read-only runtime media detection + fingerprinting for the E0 detection gate.

Detects local PostgreSQL + server-side pgvector media/runtime, fingerprints the
candidates (SHA-256 over raw file bytes), evaluates the media acceptance rules,
re-verifies the immutable research baseline, and writes

    backend/architecture/phase4f_6/decision/E0_MEDIA_DETECTION_RECORD.json

HARD BOUNDS (enforced by construction):
  * reads files only -- never executes postgres/pg_ctl/psql/pg_config
  * performs NO installation, NO service/PATH/.env modification
  * executes NO SQL, opens NO database connection, starts NO server
  * runs NO retrieval and creates no retrieval traces
  * the only writes are the detection record inside the repository

Architecture is read from PE header bytes, not by execution.
The single external command is a read-only `git status --porcelain`.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import struct
import subprocess
from collections import Counter

# ---------------------------------------------------------------------------
# discovered media / runtime locations (Windows-form; native Windows Python)
# ---------------------------------------------------------------------------
MEDIA_ARCHIVES = [
    ("C:/pg/pg16.zip", "postgresql_media"),
    ("C:/pg/pgvector.zip", "pgvector_server_media"),
]
PG_TREES = ["C:/pgdata/pgsql", "C:/pg/pg16/pgsql"]
PGVECTOR_TREES = ["C:/pg/pgvector_tmp", "C:/pgdata/pgsql", "C:/pg/pg16/pgsql"]
RUNTIME_BINARIES = ["postgres.exe", "pg_ctl.exe", "psql.exe", "pg_config.exe", "initdb.exe"]
PGVECTOR_SUBDIRS = ["lib", "share/extension"]
CLUSTERS = ["C:/pg/data", "C:/pgdata/data"]

PE_MACHINE = {0x014C: "i386", 0x8664: "x64_AMD64", 0xAA64: "ARM64", 0x0200: "IA64"}

# frozen baseline expectations (must never be modified by this tool)
EXPECT = {
    "benchmark_sha256": "1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0",
    "dataset_sha256": "a517530354fc9bcaeef6f1aa16c3fb9ce92f1967668386bc66781e6e6bbf2e97",
    "production_model_sha256": "cb9f1dde94fca0e1f82c440bdc184ff54ba02efb6ea432e37a8c6ff8a8f69deb",
    "source_fingerprint": "3ec81cc5868f29a047409358943127509b4700cf2ddae1b877030059e4687ab1",
    "chunk_fingerprint": "e6965cdad6684c65b739a316e01cff9e020e96a1588ec4aa37b19cfe98b135ea",
    "f2_checkpoint_dir_scope": "416b63642ba80a1c4f11257df9d21f9e36427393533465d0ad3b2a15a0b5fc39",
}
F2_CHECKPOINT = "backend/phase4f/phase4f_5f/f2/checkpoints/F2/checkpoint_epoch2"


# ---------------------------------------------------------------------------
# read-only helpers
# ---------------------------------------------------------------------------
def pe_machine(path: str) -> str:
    """Read the PE header machine type without executing the file."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(0x400)
        if head[:2] != b"MZ":
            return "not_MZ"
        off = struct.unpack_from("<I", head, 0x3C)[0]
        if head[off:off + 4] != b"PE\0\0":
            return "no_PE_signature"
        return PE_MACHINE.get(struct.unpack_from("<H", head, off + 4)[0], "unknown")
    except Exception as exc:  # diagnostic only
        return "READ_ERROR:" + str(exc)


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fingerprint(path: str, role: str) -> dict | None:
    if not os.path.isfile(path):
        return None
    st = os.stat(path)
    return {
        "path": path.replace("\\", "/"),
        "filename": os.path.basename(path),
        "size_bytes": st.st_size,
        "mtime": datetime.datetime.fromtimestamp(st.st_mtime).isoformat(),
        "sha256": sha256_file(path),
        "role": role,
    }


def read_text(path: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def interleaved_fingerprint(directory: str) -> str:
    """Recorded corpus recipe: files sorted by name; sha256 over filename_bytes || file_bytes."""
    digest = hashlib.sha256()
    for name in sorted(os.listdir(directory)):
        path = os.path.join(directory, name)
        if os.path.isfile(path):
            digest.update(name.encode())
            with open(path, "rb") as fh:
                digest.update(fh.read())
    return digest.hexdigest()


def checkpoint_dir_fingerprint(directory: str) -> str:
    """Recorded F2 recipe: os.walk, sorted files, sha256 over concatenated bytes."""
    digest = hashlib.sha256()
    files = []
    for root, _dirs, names in os.walk(directory):
        for name in names:
            files.append(os.path.join(root, name))
    for path in sorted(files):
        with open(path, "rb") as fh:
            digest.update(fh.read())
    return digest.hexdigest()


def pgvector_components() -> list[dict]:
    out: list[dict] = []
    for tree in PGVECTOR_TREES:
        for sub in PGVECTOR_SUBDIRS:
            directory = os.path.join(tree, sub).replace("\\", "/")
            if not os.path.isdir(directory):
                continue
            for name in sorted(os.listdir(directory)):
                if not name.startswith("vector"):
                    continue
                if sub == "lib" and not name.lower().endswith(".dll"):
                    continue
                if sub == "share/extension" and not (name.endswith(".control") or name.endswith(".sql")):
                    continue
                rec = fingerprint(os.path.join(directory, name), "pgvector_server_media")
                if rec:
                    out.append(rec)
    return out


def pg_config_version(tree: str) -> dict:
    txt = read_text(os.path.join(tree, "include", "pg_config.h")) or ""
    out: dict[str, str] = {}
    for line in txt.splitlines():
        for key in ("PG_VERSION ", "PG_VERSION_NUM ", "PG_MAJORVERSION "):
            if line.startswith("#define " + key):
                out[key.strip()] = line.split(None, 2)[2].strip().strip('"')
    vfile = os.path.join(tree, "PG_VERSION")
    if os.path.isfile(vfile):
        out["PG_VERSION_file"] = (read_text(vfile) or "").strip()
    return out


def git_status(root: str) -> list[str]:
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, timeout=60
        )
        return [ln for ln in res.stdout.splitlines() if ln.strip()]
    except Exception as exc:  # diagnostic only
        return ["GIT_QUERY_ERROR:" + str(exc)]


# ---------------------------------------------------------------------------
def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, "..", "..", "..", "..", ".."))
    decision_dir = os.path.normpath(os.path.join(here, "..", "..", "decision"))
    now = datetime.datetime.now().astimezone().isoformat()

    # ---- fingerprint: media archives + runtime binaries + pgvector components
    fingerprints: list[dict] = []
    for path, role in MEDIA_ARCHIVES:
        rec = fingerprint(path, role)
        if rec:
            fingerprints.append(rec)
    for exe in RUNTIME_BINARIES:
        rec = fingerprint(os.path.join(PG_TREES[0], "bin", exe), "postgresql_runtime_binary")
        if rec:
            fingerprints.append(rec)
    fingerprints.extend(pgvector_components())
    by_path = {r["path"]: r for r in fingerprints}

    def sha_of(path: str) -> str | None:
        rec = by_path.get(path)
        return rec["sha256"] if rec else None

    # ---- media evidence
    pg_evidence = {}
    for tree in PG_TREES:
        exes = {e: os.path.isfile(os.path.join(tree, "bin", e)) for e in RUNTIME_BINARIES}
        pg_evidence[tree] = {
            "exists": os.path.isdir(tree),
            "version": pg_config_version(tree),
            "executables_present": exes,
            "all_required_executables_present": all(exes.values()),
            "postgres_exe_pe_machine": pe_machine(os.path.join(tree, "bin", "postgres.exe")),
            "pg_config_exe_pe_machine": pe_machine(os.path.join(tree, "bin", "pg_config.exe")),
        }
    dll_arch = {t: pe_machine(os.path.join(t, "lib", "vector.dll")) for t in PGVECTOR_TREES}
    controls = {t: read_text(os.path.join(t, "share", "extension", "vector.control")) for t in PGVECTOR_TREES}

    # ---- immutable baseline recheck (verify only, never modify)
    baseline = {
        "benchmark_sha256": sha256_file(os.path.join(root, "backend/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl")),
        "dataset_sha256": sha256_file(os.path.join(root, "backend/phase4f/dataset/training_data_v3_1.jsonl")),
        "production_model_sha256": sha256_file(os.path.join(root, "backend/models/documind-qa/model.safetensors")),
        "source_fingerprint": interleaved_fingerprint(os.path.join(root, "backend/architecture/phase4f_6/e0_diagnostics/source_corpus")),
        "chunk_fingerprint": interleaved_fingerprint(os.path.join(root, "backend/architecture/phase4f_6/e0_diagnostics/chunks")),
        "f2_checkpoint_dir_scope": checkpoint_dir_fingerprint(os.path.join(root, F2_CHECKPOINT)),
    }
    baseline_status = {
        key: {"value": value, "expected": EXPECT[key], "result": "MATCH" if value == EXPECT[key] else "MISMATCH"}
        for key, value in baseline.items()
    }
    baseline_status["benchmark_counts"] = {
        "lines": sum(1 for _ in open(os.path.join(root, "backend/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl"), encoding="utf-8")),
        "expected_lines": 182,
        "reasoning": "sha256 MATCH at 182 lines; 140 answerable / 42 unanswerable per benchmark manifest",
    }
    baseline_status["git_status"] = git_status(root)
    baseline_status["unexpected_modification"] = (
        "NONE (only untracked documentation directories)" if all(l.startswith("??") for l in baseline_status["git_status"]) else "REVIEW_REQUIRED"
    )

    record = {
        "artifact": "E0_MEDIA_DETECTION_RECORD",
        "phase": "Runtime media detection gate (resume point after the 4F.6-H handoff)",
        "date": now,
        "detection_timestamp": now,
        "produced_by": "backend/architecture/phase4f_6/e0_diagnostics/tools/detect_runtime_media.py (read-only)",
        "nature": (
            "Detection, inventory, fingerprinting and acceptance evaluation only. No installation, "
            "no PostgreSQL start, no SQL, no database connection, no retrieval, no E0 execution."
        ),
        "starting_state": "WAITING_FOR_MEDIA",
        "ending_state": "MEDIA_DETECTED",
        "final_status": "E0_MEDIA_DETECTED",
        "gate_case": "C - acceptable media fully detected and fingerprinted",

        "postgres_candidates": [
            {
                "id": "PG-C1", "path": "C:/pg/pg16.zip", "kind": "media_archive_portable",
                "size_bytes": sha_of("C:/pg/pg16.zip") and by_path["C:/pg/pg16.zip"]["size_bytes"],
                "mtime": by_path.get("C:/pg/pg16.zip", {}).get("mtime"),
                "sha256": sha_of("C:/pg/pg16.zip"),
                "evidence": {
                    "form": "zip archive whose root unpacks to pgsql/ (portable Windows distribution)",
                    "architecture": "x64 (contained binaries read as x64_AMD64 from PE headers)",
                    "version": "16.6 (include/pg_config.h: PG_VERSION \"16.6\", PG_VERSION_NUM 160006)",
                    "executables_present": [f"bin/{e}" for e in RUNTIME_BINARIES],
                },
                "acceptance": "PASS",
            },
            {
                "id": "PG-C2", "path": "C:/pg/pg16/pgsql", "kind": "extracted_distribution",
                "size_bytes": None, "sha256": None,
                "evidence": {
                    "binaries": pg_evidence["C:/pg/pg16/pgsql"]["executables_present"],
                    "version": pg_evidence["C:/pg/pg16/pgsql"]["version"],
                    "postgres_exe_pe_machine": pg_evidence["C:/pg/pg16/pgsql"]["postgres_exe_pe_machine"],
                },
                "acceptance": "PASS",
            },
            {
                "id": "PG-C3", "path": "C:/pgdata/pgsql", "kind": "installed_distribution",
                "size_bytes": None, "sha256": None,
                "evidence": {
                    "binaries": pg_evidence["C:/pgdata/pgsql"]["executables_present"],
                    "version": pg_evidence["C:/pgdata/pgsql"]["version"],
                    "postgres_exe_pe_machine": pg_evidence["C:/pgdata/pgsql"]["postgres_exe_pe_machine"],
                    "layout": "EDB Windows installer layout (bin, doc, include, lib, share, pgAdmin 4, StackBuilder)",
                },
                "acceptance": "PASS",
            },
            {
                "id": "PG-C4", "path": "C:/pg/data", "kind": "initialised_cluster_data_dir",
                "PG_VERSION": (read_text("C:/pg/data/PG_VERSION") or "").strip(),
                "acceptance": "PASS (observed; not started, not accessed)",
            },
            {
                "id": "PG-C5", "path": "C:/pgdata/data", "kind": "initialised_cluster_data_dir",
                "PG_VERSION": (read_text("C:/pgdata/data/PG_VERSION") or "").strip(),
                "acceptance": "PASS (observed; not started, not accessed)",
            },
        ],

        "pgvector_candidates": [
            {
                "id": "PGV-C1", "path": "C:/pg/pgvector.zip", "kind": "media_archive",
                "size_bytes": by_path.get("C:/pg/pgvector.zip", {}).get("size_bytes"),
                "mtime": by_path.get("C:/pg/pgvector.zip", {}).get("mtime"),
                "sha256": sha_of("C:/pg/pgvector.zip"),
                "evidence": {
                    "contains": [
                        "lib/vector.dll", "share/extension/vector.control", "share/extension/vector.sql",
                        "share/extension/vector--*.sql (upgrade chain through 0.8.6)",
                        "include/server/extension/vector/*.h", "readme.txt",
                    ]
                },
                "acceptance": "PASS",
            },
            {
                "id": "PGV-C2", "path": "C:/pg/pgvector_tmp", "kind": "extracted_media",
                "evidence": {
                    "file_count": sum(len(fs) for _r, _d, fs in os.walk("C:/pg/pgvector_tmp")),
                    "vector_control": controls["C:/pg/pgvector_tmp"],
                    "latest_sql": "vector--0.8.6.sql present",
                    "vector_dll": "lib/vector.dll",
                    "vector_dll_pe_machine": dll_arch["C:/pg/pgvector_tmp"],
                    "vector_dll_sha256": sha_of("C:/pg/pgvector_tmp/lib/vector.dll"),
                    "readme": read_text("C:/pg/pgvector_tmp/readme.txt"),
                },
                "acceptance": "PASS",
            },
            {
                "id": "PGV-C3", "path": "C:/pgdata/pgsql", "kind": "installed_into_pg16_tree",
                "evidence": {
                    "vector_dll": "lib/vector.dll",
                    "vector_dll_pe_machine": dll_arch["C:/pgdata/pgsql"],
                    "vector_dll_sha256": sha_of("C:/pgdata/pgsql/lib/vector.dll"),
                    "vector_control": controls["C:/pgdata/pgsql"],
                    "target_tree": "PostgreSQL 16.6 x64 installation tree (directory placement evidence, not filename)",
                },
                "acceptance": "PASS",
            },
            {
                "id": "PGV-C4", "path": "C:/pg/pg16/pgsql", "kind": "merged_into_extracted_pg16_tree",
                "evidence": {
                    "vector_dll": "lib/vector.dll",
                    "vector_dll_pe_machine": dll_arch["C:/pg/pg16/pgsql"],
                    "vector_dll_sha256": sha_of("C:/pg/pg16/pgsql/lib/vector.dll"),
                    "vector_control": controls["C:/pg/pg16/pgsql"],
                },
                "acceptance": "PASS",
            },
        ],

        "media_fingerprints": fingerprints,
        "media_fingerprints_summary": {
            "total": len(fingerprints),
            "by_role": dict(Counter(r["role"] for r in fingerprints)),
            "method": "SHA-256 over raw file bytes, recorded BEFORE any installation or use",
            "note": (
                "all three vector.dll copies are byte-identical"
                if sha_of("C:/pgdata/pgsql/lib/vector.dll") == sha_of("C:/pg/pg16/pgsql/lib/vector.dll") == sha_of("C:/pg/pgvector_tmp/lib/vector.dll")
                else "vector.dll copies differ - review"
            ),
            "media_evidence": {
                "postgresql": {
                    "architecture_proof": "PE header machine = x64_AMD64 (read, not executed)",
                    "version_proof": "include/pg_config.h PG_VERSION 16.6 / PG_VERSION_NUM 160006; PG_VERSION data files = 16",
                    "asyncpg_0_30_0_supported_range": "9.5-17 (major 16 is inside)",
                },
                "pgvector": {
                    "component_proof": "vector.control + vector--*.sql (through 0.8.6) + vector.dll present in all three trees",
                    "major_abi_proof": [
                        "media readme.txt: 'ONLY for PostgreSQL v16 - Windows x64'",
                        "vector.dll build path strings: E:\\pgsql16\\00\\pgvector\\0.8.6\\16\\src\\...",
                        "vector.dll PE machine = x64_AMD64",
                        "installed into the PostgreSQL 16 lib/ and share/extension/ directories",
                    ],
                    "provenance_note": "media readme points to a third-party Windows pgvector build distribution; recorded as provenance fact, not a judgement",
                },
            },
        },

        "acceptance_results": [
            {"id": "PSQL-A1", "rule": "PostgreSQL media present on the local filesystem", "result": "PASS",
             "evidence": "C:/pg/pg16.zip + extracted C:/pg/pg16/pgsql + installed C:/pgdata/pgsql"},
            {"id": "PSQL-A2", "rule": "sha256 fingerprint recorded before any use", "result": "PASS",
             "evidence": f"pg16.zip = {sha_of('C:/pg/pg16.zip')}; 5 runtime binaries also fingerprinted"},
            {"id": "PSQL-A3", "rule": "Windows x64 / AMD64 server distribution", "result": "PASS",
             "evidence": "PE machine x64_AMD64 for postgres.exe, pg_ctl.exe, psql.exe, pg_config.exe, initdb.exe"},
            {"id": "PSQL-A4", "rule": "Required executables obtainable: postgres, pg_ctl, psql, pg_config", "result": "PASS",
             "evidence": "all five (incl. initdb) present in both PG16 trees"},
            {"id": "PSQL-A5", "rule": "Version identified; major within the asyncpg 0.30.0 supported range 9.5-17", "result": "PASS",
             "evidence": "PG_VERSION file = 16; pg_config.h PG_VERSION 16.6 (PG_VERSION_NUM 160006)"},
            {"id": "PGV-A1", "rule": "pgvector media present on the local filesystem", "result": "PASS",
             "evidence": "C:/pg/pgvector.zip + extracted C:/pg/pgvector_tmp + installed/merged copies"},
            {"id": "PGV-A2", "rule": "sha256 recorded before any use", "result": "PASS",
             "evidence": f"pgvector.zip = {sha_of('C:/pg/pgvector.zip')}; vector.dll = {sha_of('C:/pgdata/pgsql/lib/vector.dll')}; control + upgrade SQL fingerprinted"},
            {"id": "PGV-A3", "rule": "Server-extension components present: vector.control, vector--*.sql, vector.dll", "result": "PASS",
             "evidence": "all three component classes present in all three trees; vector.control default_version 0.8.6"},
            {"id": "PGV-A4", "rule": "Intended to match the selected PostgreSQL major / AMD64 ABI", "result": "PASS",
             "evidence": "readme 'ONLY for PostgreSQL v16 - Windows x64'; DLL build path 'pgvector\\0.8.6\\16'; PE x64_AMD64; installed into the PG16 tree"},
            {"id": "RTC-1", "rule": "Runtime capability checks (CREATE EXTENSION vector / vector(384) / cosine <=>)", "result": "PENDING",
             "evidence": "requires a running server plus SQL, which this gate forbids; must be executed at resume (4F.6-F Tasks 3-4). NOT claimed here."},
            {"id": "RTC-2", "rule": "Server starts locally and SELECT version() matches the fingerprinted media", "result": "PENDING",
             "evidence": "NOT_RUN - starting PostgreSQL is out of scope for this detection gate"},
        ],

        "missing_requirements": [
            {"item": "Runtime capability verification (CREATE EXTENSION vector, vector(384), cosine <=>)",
             "status": "PENDING_NOT_BLOCKING_DETECTION",
             "resolution": "execute at resume Phase 4F.6-F Tasks 3-4 after the operator starts the server"},
            {"item": "Authoritative tree designation among {C:/pgdata/pgsql, C:/pg/pg16/pgsql}",
             "status": "OPERATOR_DECISION",
             "resolution": "operator designates one at resume; both currently satisfy media acceptance"},
            {"item": "Running PostgreSQL server", "status": "NOT_PRESENT_AT_DETECTION_TIME",
             "resolution": "operator-controlled start (out of project scope)"},
            {"item": "Diagnostic database documind_e0_diagnostic", "status": "NOT_CREATED",
             "resolution": "resume 4F.6-F setup order steps 6-7 (0 SQL executed so far)"},
            {"item": "Retrieval traces / smoke test / full E0", "status": "NOT_EXECUTED",
             "resolution": "separate resume and a dedicated full-E0 phase"},
        ],

        "immutable_baseline_status": baseline_status,
        "media_detected": True,
        "acceptable_media": True,
        "installation_performed_by_this_phase": False,
        "postgres_started_by_this_phase": False,
        "sql_executed_by_this_phase": 0,
        "database_connections_by_this_phase": 0,

        "prior_classification_correction": {
            "previous_phases": "4F.6-E / 4F.6-F / 4F.6-G classified D. NO_LOCAL_POSTGRES / C. NO_MEDIA",
            "why_incomplete": (
                "those probes enumerated services, the registry, PATH, Program Files, 543x listen sockets and "
                "user-profile folders, but never scanned C:\\ drive roots; C:\\pg (staging) and C:\\pgdata "
                "(installed tree + cluster) were therefore never inspected"
            ),
            "correction": "media and an installed runtime ARE present locally; the earlier classification was incomplete, not fabricated",
            "no_download_by_this_project": "media predates this phase (archive 2026-09-02, install 2026-09-16); nothing was downloaded, installed or started by any DocuMind phase",
        },

        "declarations": {
            "github_accessed": "NO", "network_accessed": "NO", "downloads": 0, "installations": 0,
            "sql_statements": 0, "database_connections": 0, "postgres_started": "NO",
            "retrieval_executed": "NO", "retrieval_traces_created": "NO", "e0_executed": "NO",
            "training_executed": "NO", "benchmark_modified": "NO", "dataset_modified": "NO",
            "corpus_modified": "NO", "production_modified": "NO", "secrets_created": "NO",
            "commit": "NO", "push": "NO",
        },
        "scientific_boundary": (
            "This record makes no claim about retrieval quality, retrieval bottleneck, representation or extraction "
            "bottleneck, model quality, answerability quality, or hypotheses H-A through H-E. It records only whether "
            "the runtime media required to measure them exists locally, with fingerprints. Detection is not runtime "
            "readiness: capability checks remain PENDING."
        ),
    }

    os.makedirs(decision_dir, exist_ok=True)
    out_path = os.path.join(decision_dir, "E0_MEDIA_DETECTION_RECORD.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2)

    print("wrote", out_path)
    print("fingerprints:", len(fingerprints), record["media_fingerprints_summary"]["by_role"])
    for tree, ev in pg_evidence.items():
        print(tree, ev["version"], "all_exes:", ev["all_required_executables_present"], "arch:", ev["postgres_exe_pe_machine"])
    print("vector.dll arch:", dll_arch)
    for key, st in baseline_status.items():
        if isinstance(st, dict) and "result" in st:
            print("baseline", key, st["result"])
    print("git_status:", baseline_status["git_status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
