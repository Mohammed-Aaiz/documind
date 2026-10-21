"""Phase 4F.6-D — E0 PREREQUISITE RECOVERY (diagnostic builder).

LOCAL FILESYSTEM ONLY.  Forces HF/transformers OFFLINE mode before any
imports so no network access can occur.

This script performs PREREQUISITE verification only:
  * verifies the frozen benchmark / dataset / production-model hashes
  * reconstructs the six P3 source documents from the local generator
    definitions (classification B: DETERMINISTIC_SOURCE_RECONSTRUCTIBLE)
  * verifies benchmark-context -> source-span provenance (Task 4)
  * builds an ISOLATED chunk corpus with the EXISTING production legacy
    chunker (Task 5) — never touching production storage or the database
  * verifies gold-evidence presence in source and chunks using multi-
    criterion NORM-v1-style matching (Task 6)
  * pins the model-input configuration for the recorded F2 predictions
    and runs ONE labelled methodology probe (Task 11) — no aggregate L4
    measurement, no inference, no E0 stage attribution
  * probes context-assembly determinism (Task 10)
  * records the retrieval execution blocker (Tasks 7-9: STOP, no traces)

Explicitly NOT done here: E0 execution, failure-stage decomposition,
conditional EM/F1, retrieval runs, inference, training, benchmark or
dataset modification, production modification.
"""

from __future__ import annotations

import os
import sys
import json
import re
import hashlib
import socket
import shutil
import platform
import traceback
from collections import Counter, defaultdict
from pathlib import Path

# --- offline hard-guards (before any HF/transformers import) ---------------
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_DATASETS_OFFLINE", "1")

TOOL_FILE = Path(__file__).resolve()
BACKEND = TOOL_FILE.parents[4]          # .../backend
REPO = TOOL_FILE.parents[5]             # repo root
sys.path.insert(0, str(BACKEND))

OUT_ROOT = TOOL_FILE.parents[1]         # .../e0_diagnostics
SRC_DIR = OUT_ROOT / "source_corpus"
CHUNK_DIR = OUT_ROOT / "chunks"
DIAG_DIR = OUT_ROOT / "diagnostics"
DECISION_DIR = TOOL_FILE.parents[2] / "decision"   # phase4f_6/decision
for d in (SRC_DIR, CHUNK_DIR, DIAG_DIR):
    d.mkdir(parents=True, exist_ok=True)

DIAGNOSTIC_VERSION = "e0-prerequisite-v1"
CANON_RULE_ID = "CANON-v1"

# --- frozen constants (expected values; recomputed, never written) ---------
EXPECTED_BENCH_SHA = "1166bf4ff38265c209614ac20261417b7eeb43653f4482dfdf94721fd50a41d0"
EXPECTED_DATASET_SHA = "a517530354fc9bcaeef6f1aa16c3fb9ce92f1967668386bc66781e6e6bbf2e97"
EXPECTED_MODEL_SHA = "cb9f1dde94fca0e1f82c440bdc184ff54ba02efb6ea432e37a8c6ff8a8f69deb"
EXPECTED_COUNTS = {"total": 182, "answerable": 140, "unanswerable": 42, "documents": 6}
EXPECTED_DOC_COUNTS = {
    "unanswerable_corpus": 42,
    "company_history_eta": 44,
    "financial_report_q3": 38,
    "api_docs_lambda": 20,
    "dataset_desc_mu": 22,
    "legal_contract_epsilon": 16,
}
SIX_DOCS = list(EXPECTED_DOC_COUNTS.keys())
CONTENT_DOCS = [d for d in SIX_DOCS if d != "unanswerable_corpus"]

BENCH_PATH = BACKEND / "phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl"
BENCH_MANIFEST = BACKEND / "phase4f/phase4f_5d/benchmark/benchmark_manifest.json"
DATASET_PATH = BACKEND / "phase4f/dataset/training_data_v3_1.jsonl"
MODEL_PATH = BACKEND / "models/documind-qa/model.safetensors"
GEN_PATH = BACKEND / "phase4f/dataset/expand_and_audit.py"
F2_DIR = BACKEND / "phase4f/phase4f_5f/f2"
F2_CKPT = F2_DIR / "checkpoints/F2/checkpoint_epoch2"
RUN_F2 = F2_DIR / "run_f2.py"
RUN_THRESH = F2_DIR / "threshold_experiment/run_threshold_experiment.py"
INFERENCE_CONFIG = BACKEND / "models/documind-qa/inference_config.json"

RESULTS: dict = {
    "diagnostic_version": DIAGNOSTIC_VERSION,
    "phase": "4F.6-D",
    "created_utc": None,
    "boundary": {
        "e0_executed": False, "retrieval_run": False, "inference_run": False,
        "training_run": False, "benchmark_modified": False,
        "dataset_modified": False, "production_modified": False,
        "network_accessed": False, "github_accessed": False,
        "stage_attribution_computed": False,
    },
}
CHECKS: dict = {}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def jdump(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def jlines(path: Path, rows) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# =========================================================================
# 1. FROZEN VERIFICATION (Task 1)
# =========================================================================
def verify_frozen() -> dict:
    bench_sha = sha256_file(BENCH_PATH)
    lines = [ln for ln in BENCH_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]
    examples = [json.loads(ln) for ln in lines]
    impossible = sum(1 for e in examples if e.get("is_impossible") or e.get("question_kind") == "UNANSWERABLE")
    doc_counts = Counter(e["document_id"] for e in examples)
    dataset_sha = sha256_file(DATASET_PATH)
    model_sha = sha256_file(MODEL_PATH)
    out = {
        "benchmark_sha256": bench_sha,
        "benchmark_hash_matches_frozen": bench_sha == EXPECTED_BENCH_SHA,
        "benchmark_lines": len(lines),
        "benchmark_unanswerable": impossible,
        "benchmark_answerable": len(lines) - impossible,
        "document_counts": dict(doc_counts),
        "document_counts_match_manifest": dict(doc_counts) == EXPECTED_DOC_COUNTS,
        "six_identities_verified": set(doc_counts) == set(SIX_DOCS),
        "counts_match_expected": (
            len(lines) == EXPECTED_COUNTS["total"]
            and impossible == EXPECTED_COUNTS["unanswerable"]
            and len(lines) - impossible == EXPECTED_COUNTS["answerable"]
        ),
        "dataset_sha256": dataset_sha,
        "dataset_hash_matches_manifest": dataset_sha == EXPECTED_DATASET_SHA,
        "production_model_sha256": model_sha,
        "production_model_hash_unchanged": model_sha == EXPECTED_MODEL_SHA,
    }
    manifest = json.loads(BENCH_MANIFEST.read_text(encoding="utf-8"))
    out["manifest_sha256_field_matches"] = manifest.get("sha256") == EXPECTED_BENCH_SHA
    out["manifest_source_dataset_hash_matches"] = manifest.get("source_dataset_hash") == EXPECTED_DATASET_SHA
    CHECKS["frozen_integrity"] = all(
        out[k] for k in (
            "benchmark_hash_matches_frozen", "document_counts_match_manifest",
            "six_identities_verified", "counts_match_expected",
            "dataset_hash_matches_manifest", "production_model_hash_unchanged",
            "manifest_sha256_field_matches", "manifest_source_dataset_hash_matches",
        )
    )
    return out, examples


# =========================================================================
# 2. SOURCE RECONSTRUCTION (Tasks 2-3)  — CANON-v1 serialization
# =========================================================================
# CANON-v1 (diagnostic definition, validated empirically by Task 4):
#   section block = "\n\n".join([heading?] + paragraphs + [table blocks]
#                               + [list blocks])         # DOCUMENTS key order
#   table block   = "\n".join(" | ".join(row) for row in [headers] + rows)
#   list block    = _list_str(list)  (heading + items, "\n"-joined)
#   document text = "\n\n".join(section blocks)
# Section-body stream (generator view, used only for MULTI classification):
#   "\n\n".join(_section_text(s) for s in sections)  where
#   _section_text = "\n\n".join([heading?] + paragraphs)   (expand_and_audit:934)


def _list_str(lst: dict) -> str:                     # exact copy: expand:926
    lines = []
    if lst.get("heading"):
        lines.append(lst["heading"])
    for item in lst["items"]:
        lines.append(item)
    return "\n".join(lines)


def _section_text(section: dict) -> str:             # exact copy: expand:934
    parts = []
    if section.get("heading"):
        parts.append(section["heading"])
    for p in section.get("paragraphs", []):
        parts.append(p)
    return "\n\n".join(parts)


def ser_table(headers, rows) -> str:
    return "\n".join(" | ".join(r) for r in [list(headers)] + [list(r) for r in rows])


def serialize_document(doc: dict) -> tuple[str, dict]:
    """CANON-v1 text + span index for every structural element."""
    idx = {"sections": [], "paragraphs": [], "tables": [], "lists": []}
    out: list[str] = []
    cursor = 0

    def emit(s: str) -> tuple[int, int]:
        nonlocal cursor
        if out:
            out.append("\n\n")
            cursor += 2
        start = cursor
        out.append(s)
        cursor += len(s)
        return start, cursor

    for si, section in enumerate(doc["sections"]):
        sec_id = f"{doc['doc_id']}#s{si}"
        sec_start = cursor
        heading = section.get("heading", "")
        heading_span = None
        parts_done = 0

        if heading:
            heading_span = emit(heading)
            parts_done = 1

        for para in section.get("paragraphs", []):
            s, e = emit(para)
            idx["paragraphs"].append({"id": f"{sec_id}#p{parts_done}", "section_id": sec_id, "start": s, "end": e})
            parts_done += 1

        for ti, table in enumerate(section.get("tables", [])):
            block = ser_table(table["headers"], table["rows"])
            s, e = emit(block)
            t_id = f"{sec_id}#t{ti}"
            # per-line spans inside the block
            line_cursor = s
            line_spans = []
            for line in block.split("\n"):
                line_spans.append((line_cursor, line_cursor + len(line)))
                line_cursor += len(line) + 1
            rows_meta = []
            for ri, row in enumerate([table["headers"]] + table["rows"]):
                rs, re_ = line_spans[ri]
                cells = []
                base = rs
                # compute cell spans precisely within this line
                line_text = block[rs - s: re_ - s]
                offset_in_line = 0
                for ci, cell in enumerate(row):
                    rel = line_text.find(cell, offset_in_line)
                    if rel < 0:
                        rel = line_text.find(cell)
                    cells.append({
                        "col": ci, "start": base + rel, "end": base + rel + len(cell),
                        "value": cell, "is_header": ri == 0,
                    })
                    offset_in_line = rel + len(cell)
                rows_meta.append({
                    "row_index": ri - 1 if ri > 0 else -1,  # -1 = header row
                    "is_header": ri == 0,
                    "line_start": rs, "line_end": re_,
                    "serialized_line": block[rs - s: re_ - s],
                    "cells": cells,
                })
            idx["tables"].append({
                "id": t_id, "section_id": sec_id, "start": s, "end": e,
                "headers": list(table["headers"]), "rows": rows_meta,
            })
            parts_done += 1

        for li, lst in enumerate(section.get("lists", [])):
            block = _list_str(lst)
            s, e = emit(block)
            l_id = f"{sec_id}#l{li}"
            items_meta = []
            line_cursor = s
            for ii, item in enumerate(lst["items"]):
                # item positions: after optional heading line
                rel = block.find(item, max(0, line_cursor - s))
                if rel < 0:
                    rel = -1
                if rel >= 0:
                    items_meta.append({"index": ii, "start": s + rel, "end": s + rel + len(item), "text": item})
                    line_cursor = s + rel + len(item)
            idx["lists"].append({
                "id": l_id, "section_id": sec_id, "start": s, "end": e,
                "heading": lst.get("heading", ""), "items": items_meta,
            })
            parts_done += 1

        idx["sections"].append({
            "id": sec_id, "index": si, "heading": heading,
            "start": sec_start, "end": cursor,
            "heading_start": heading_span[0] if heading_span else None,
            "heading_end": heading_span[1] if heading_span else None,
        })

    return "".join(out), idx


def build_source_corpus(examples: list[dict]) -> tuple[dict, dict, dict]:
    from phase4f.dataset.expand_and_audit import DOCUMENTS, RANDOM_SEED

    doc_by_id = {d["doc_id"]: d for d in DOCUMENTS}
    canon: dict[str, str] = {}
    index: dict[str, dict] = {}
    corpus_records = []

    gen_src = GEN_PATH.read_text(encoding="utf-8")

    for doc_id in CONTENT_DOCS:
        doc = doc_by_id[doc_id]
        text, idx = serialize_document(doc)
        canon[doc_id] = text
        index[doc_id] = idx
        ans = sum(1 for e in examples if e["document_id"] == doc_id and e["question_kind"] != "UNANSWERABLE")
        unans = sum(1 for e in examples if e["document_id"] == doc_id and e["question_kind"] == "UNANSWERABLE")
        rec = {
            "document_id": doc_id,
            "source_type": "GENERATOR_DEFINED_SYNTHETIC_DOCUMENT",
            "classification": "B_DETERMINISTIC_SOURCE_RECONSTRUCTIBLE",
            "generator_provenance": {
                "path": "backend/phase4f/dataset/expand_and_audit.py",
                "symbols": ["DOCUMENTS", "_add_doc"],
                "doc_definition_in_source": f'_add_doc("{doc_id}"' in gen_src,
                "example_seed": RANDOM_SEED,
                "seed_scope": "seed affects example sampling only; document text is static data (no RNG)",
                "required_inputs": "module import only (no external data, no network)",
                "reconstruction_method": "CANON-v1 serialization of the static section tree",
            },
            "document_text": text,
            "document_sha256": sha256_text(text),
            "document_bytes": len(text.encode("utf-8")),
            "structure": {
                "doc_type": doc["doc_type"], "doc_structure": doc["doc_structure"],
                "sections": len(doc["sections"]),
                "paragraphs": sum(len(s.get("paragraphs", [])) for s in doc["sections"]),
                "tables": sum(len(s.get("tables", [])) for s in doc["sections"]),
                "lists": sum(len(s.get("lists", [])) for s in doc["sections"]),
            },
            "benchmark_document_id_mapping": {
                "benchmark_version": "v1",
                "answerable_examples": ans,
                "unanswerable_examples": unans,
                "total": ans + unans,
                "expected_from_manifest": EXPECTED_DOC_COUNTS[doc_id],
                "matches_manifest": (ans + unans) == EXPECTED_DOC_COUNTS[doc_id],
            },
            "isolated_artifact": True,
            "production_storage_touched": False,
        }
        corpus_records.append(rec)

    # unanswerable_corpus — virtual corpus, texts carried by the benchmark
    unans_examples = [e for e in examples if e["document_id"] == "unanswerable_corpus"]
    unans_texts = [e["context"] for e in unans_examples]
    all_in_generator = all(t in gen_src for t in unans_texts)
    vtext = "\n\n".join(unans_texts)
    vrec = {
        "document_id": "unanswerable_corpus",
        "source_type": "VIRTUAL_CORPUS (not a coherent document)",
        "classification": "B_DETERMINISTIC_SOURCE_RECONSTRUCTIBLE",
        "generator_provenance": {
            "path": "backend/phase4f/dataset/expand_and_audit.py",
            "symbols": ["ExampleGenerator.gen_unanswerable", "unanswerable_pairs (static list)"],
            "all_42_context_literals_present_in_generator_source": all_in_generator,
            "required_inputs": "benchmark records (authoritative carrier) + generator source (cross-check)",
            "reconstruction_method": (
                "document_text = the 42 benchmark distractor contexts in benchmark order; "
                "each literal verified present in the generator's static pair list"
            ),
        },
        "document_text": vtext,
        "document_sha256": sha256_text(vtext),
        "document_bytes": len(vtext.encode("utf-8")),
        "structure": {"sections": 0, "paragraphs": len(unans_texts), "tables": 0, "lists": 0, "virtual": True},
        "benchmark_document_id_mapping": {
            "benchmark_version": "v1",
            "answerable_examples": 0,
            "unanswerable_examples": len(unans_texts),
            "total": len(unans_texts),
            "expected_from_manifest": EXPECTED_DOC_COUNTS["unanswerable_corpus"],
            "matches_manifest": len(unans_texts) == EXPECTED_DOC_COUNTS["unanswerable_corpus"],
        },
        "notes": (
            "Virtual corpus: contexts are standalone distractor sentences, not spans of one "
            "source document. Chunked as flat paragraphs for corpus completeness. No gold "
            "evidence is asserted for its (unanswerable) examples."
        ),
        "isolated_artifact": True,
        "production_storage_touched": False,
    }
    corpus_records.append(vrec)
    canon["unanswerable_corpus"] = vtext
    index["unanswerable_corpus"] = {"sections": [], "paragraphs": [
        {"id": f"unanswerable_corpus#u{i}", "section_id": None, "start": -1, "end": -1}
        for i in range(len(unans_texts))
    ], "tables": [], "lists": []}
    # paragraph spans for virtual doc
    cur = 0
    for i, t in enumerate(unans_texts):
        index["unanswerable_corpus"]["paragraphs"][i]["start"] = cur
        index["unanswerable_corpus"]["paragraphs"][i]["end"] = cur + len(t)
        cur += len(t) + 2

    # write full records (with text) into source_corpus/
    for rec in corpus_records:
        (SRC_DIR / f"{rec['document_id']}.json").write_text(
            json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")

    CHECKS["source_reconstruction"] = (
        all(r["classification"].startswith("B_") for r in corpus_records)
        and all(r["generator_provenance"].get("doc_definition_in_source", True) for r in corpus_records)
        and all(r["benchmark_document_id_mapping"]["matches_manifest"] for r in corpus_records)
        and all_in_generator
    )
    return canon, index, corpus_records


# =========================================================================
# 3. TASK 4 — benchmark -> source provenance
# =========================================================================
def all_occ(hay: str, needle: str) -> list[int]:
    out, i = [], hay.find(needle)
    while i >= 0:
        out.append(i)
        i = hay.find(needle, i + 1)
    return out


def norm_text(s: str) -> str:
    return " ".join(s.casefold().split())


def numeric_values(s: str) -> list[float]:
    vals = []
    for m in re.finditer(r"[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|[-+]?\d+(?:\.\d+)?", s):
        try:
            vals.append(float(m.group(0).replace(",", "")))
        except ValueError:
            pass
    return vals


def numeric_presence(answer: str, text: str) -> dict:
    """NORM-v1 numeric class (rule ids N2/N3): value-presence with comma/
    currency variants; percent class checked in a +/-12 char window.
    No unit conversion, no rounding, en-US locale."""
    vals = numeric_values(answer)
    if not vals:
        return {"applied": False, "found": None}
    has_pct = bool(re.search(r"%|percent", answer, re.IGNORECASE))
    found_flags, pct_flags, candidates = [], [], 0
    for v in vals:
        cands = set()
        plain = f"{v:g}"
        cands.add(plain)
        if v == int(v):
            cands.add(f"{int(v):,}")
            cands.add(str(int(v)))
        cands.add(str(v))
        hit = False
        for c in cands:
            esc = re.escape(c)
            for m in re.finditer(r"(?<![\d.])" + esc + r"(?![\d])", text):
                candidates += 1
                hit = True
                if has_pct:
                    window = text[max(0, m.start() - 12): m.end() + 12]
                    pct_flags.append(bool(re.search(r"%|percent|pct", window, re.IGNORECASE)))
                break
            if hit:
                break
        found_flags.append(hit)
    percent_ok = all(pct_flags) if (has_pct and pct_flags) else (not has_pct)
    return {
        "applied": True,
        "values": vals,
        "all_values_present": all(found_flags),
        "percent_class_ok": percent_ok,
        "candidate_occurrences": candidates,
        "rule_ids": ["N2-value-present", "N3-percent-window"] if has_pct else ["N2-value-present"],
    }


def structural_membership(answer: str, doc_id: str, index: dict) -> dict:
    """NORM-v1 structural class (rule id N4): membership in generator table/
    list structures of the resolved document."""
    idx = index[doc_id]
    hits = []
    for t in idx["tables"]:
        for row in t["rows"]:
            for cell in row["cells"]:
                if cell["value"] == answer:
                    hits.append({"element": t["id"], "kind": "table_cell",
                                 "row_index": row["row_index"], "col": cell["col"]})
            if row["serialized_line"] == answer:
                hits.append({"element": t["id"], "kind": "table_row", "row_index": row["row_index"]})
    for l in idx["lists"]:
        for it in l["items"]:
            if it["text"] == answer:
                hits.append({"element": l["id"], "kind": "list_item", "item_index": it["index"]})
    return {"applied": bool(hits), "hits": hits}


def verify_provenance(examples: list[dict], canon: dict, index: dict) -> list[dict]:
    rows = []
    answerable = [e for e in examples if e["question_kind"] != "UNANSWERABLE"]
    for e in answerable:
        doc_id, ctx, kind = e["document_id"], e["context"], e["question_kind"]
        row = {
            "example_id": e["example_id"], "document_id": doc_id, "question_kind": kind,
            "tier": e.get("tier"), "context_chars": len(ctx),
        }
        if doc_id not in canon:
            row.update(provenance_class="SOURCE_UNRESOLVED", context_nature="unresolved_document")
            rows.append(row)
            continue

        text = canon[doc_id]
        positions = all_occ(text, ctx)
        cross_doc = [d for d in canon if d != doc_id and ctx in canon[d]]

        stream = "\n\n".join(
            _section_text(s) for s in
            next(d for d in __DOCS__ if d["doc_id"] == doc_id)["sections"]
        ) if doc_id in __DOC_BY_ID__ else ""
        stream_pos = all_occ(stream, ctx) if stream else []

        nature, stream_meta = None, None
        if len(positions) == 1 and not cross_doc:
            cls = "SOURCE_SPAN_VERIFIED"
            nature = "one_source_span"
        elif len(positions) > 1 or (positions and cross_doc):
            cls = "SOURCE_MAPPING_AMBIGUOUS"
            nature = "one_source_span_ambiguous_mapping"
        elif stream_pos:
            cls = "SOURCE_SPAN_NOT_FOUND"
            sp = stream_pos[0]
            # section ranges in stream -> boundary crossing?
            bounds, acc = [], 0
            for s in __DOC_BY_ID__[doc_id]["sections"]:
                st = _section_text(s)
                bounds.append((acc, acc + len(st), s.get("heading", "")))
                acc += len(st) + 2
            sec_a = next((b for b in bounds if b[0] <= sp < b[1]), None)
            sec_b = next((b for b in bounds if b[0] < sp + len(ctx) <= b[1] or b[0] <= sp + len(ctx) < b[1]), None)
            crossing = bool(sec_a and sec_b and sec_a[2] != sec_b[2])
            nature = "synthetic_section_body_concatenation"
            stream_meta = {"stream_position": sp, "crosses_section_boundary": crossing,
                           "sections": sorted({sec_a[2] if sec_a else "?", sec_b[2] if sec_b else "?"})}
        else:
            cls = "SOURCE_SPAN_NOT_FOUND"
            # structural context-pair check for tables
            pair = None
            if kind in ("TABLE_CELL", "TABLE_ROW") and "\n" in ctx:
                h_line, r_line = ctx.split("\n", 1)
                for t in index[doc_id]["tables"]:
                    if " | ".join(t["headers"]) == h_line and any(
                        row["serialized_line"] == r_line for row in t["rows"]
                    ):
                        pair = {"element": t["id"], "header": True,
                                "row": next(row["row_index"] for row in t["rows"]
                                            if row["serialized_line"] == r_line)}
                        break
                nature = "synthetic_header_row_pair" if pair else "unknown_fragment"
            elif kind == "NUMERIC":
                nature = "static_fact_fragment"
            else:
                nature = "unknown_fragment"
            row["structural_context_pair"] = pair

        # MULTI_CHUNK explicit three-way nature (Task 4 requirement)
        if kind == "MULTI_CHUNK":
            if nature == "one_source_span":
                row["multi_chunk_nature"] = "one_source_span"
            elif nature == "synthetic_section_body_concatenation":
                row["multi_chunk_nature"] = "synthetic_concatenation"  # section-body view, tables/lists excluded
            else:
                segs = [s for s in ctx.split("\n\n") if len(s) > 40]
                if len(segs) >= 2 and all(s in text for s in segs):
                    row["multi_chunk_nature"] = "multiple_source_spans"
                else:
                    row["multi_chunk_nature"] = "synthetic_concatenation"

        row.update({
            "provenance_class": cls,
            "context_nature": nature,
            "context_occurrences_in_document": len(positions),
            "context_positions": positions[:5],
            "cross_document_context_hits": cross_doc,
            "stream_match_positions": stream_pos[:5],
            "stream_meta": stream_meta,
        })

        # structural provenance for table/list examples (separate check)
        if kind in ("TABLE_CELL", "TABLE_ROW", "LIST_ITEM"):
            row["structural_provenance"] = structural_membership(e["answer"], doc_id, index)
        rows.append(row)
    return rows


# =========================================================================
# 4. TASK 5 — isolated chunk corpus via EXISTING legacy chunker
# =========================================================================
def build_elements(doc: dict) -> list:
    from documents.processing import ExtractedElement
    elements = []
    for section in doc["sections"]:
        heading = section.get("heading", "")
        path = [heading] if heading else []
        if heading:
            elements.append(ExtractedElement(
                content=heading, element_type="heading", page=None,
                heading_path=list(path[:-1]), section=None, heading_level=2))
        for para in section.get("paragraphs", []):
            elements.append(ExtractedElement(
                content=para, element_type="paragraph", page=None,
                heading_path=list(path), section=heading))
        for table in section.get("tables", []):
            elements.append(ExtractedElement(
                content=ser_table(table["headers"], table["rows"]),
                element_type="table", page=None, heading_path=list(path),
                section=heading, table_data=[list(table["headers"])] + [list(r) for r in table["rows"]]))
        for lst in section.get("lists", []):
            elements.append(ExtractedElement(
                content=_list_str(lst), element_type="list", page=None,
                heading_path=list(path), section=heading, list_items=list(lst["items"])))
    return elements


def build_chunks(canon: dict, index: dict, corpus_records: list) -> tuple[list[dict], dict]:
    from documents.processing import chunk_text, CHUNK_SIZE, CHUNK_OVERLAP

    chunk_rows: list[dict] = []
    per_doc = {}
    rec_by_id = {r["document_id"]: r for r in corpus_records}
    docs_by_id = {d["doc_id"]: d for d in __DOCS__}

    for doc_id in SIX_DOCS:
        text = canon[doc_id]
        if doc_id == "unanswerable_corpus":
            from documents.processing import ExtractedElement
            elements = [ExtractedElement(content=t, element_type="paragraph", page=None)
                        for t in text.split("\n\n")]
        else:
            elements = build_elements(docs_by_id[doc_id])
        raw = chunk_text(elements)                      # EXISTING production impl
        seq, floor, resolved = 0, 0, 0
        struct_cov = Counter()
        for page, ctext in raw:
            body = ctext
            prefix_dropped = False
            pos = text.find(ctext, floor)
            if pos < 0 and "\n\n" in ctext:
                maybe = ctext.split("\n\n", 1)[1]
                pos = text.find(maybe, floor)
                if pos >= 0:
                    body, prefix_dropped = maybe, True
            if pos >= 0:
                resolved += 1
                cs, ce = pos, pos + len(body)
                floor = max(floor, max(0, pos - CHUNK_OVERLAP))
            else:
                cs = ce = None
            rec = {
                "chunk_id": f"{doc_id}::c{seq:03d}",
                "document_id": doc_id,
                "sequence": seq,
                "source_start": cs,
                "source_end": ce,
                "offset_resolution": "resolved" if cs is not None else "UNRESOLVED",
                "heading_prefix_dropped": prefix_dropped,
                "text": ctext,
                "chunker_version": "chunk-v1-legacy-chars-1000-200",
                "chunk_char_len": len(ctext),
                "source_document_hash": rec_by_id[doc_id]["document_sha256"],
            }
            if cs is not None:
                si = index[doc_id]
                rec["structure"] = {
                    "section_ids": [s["id"] for s in si["sections"] if s["start"] < ce and s["end"] > cs],
                    "paragraph_ids": [p["id"] for p in si["paragraphs"] if p["start"] < ce and p["end"] > cs],
                    "table_ids": [t["id"] for t in si["tables"] if t["start"] < ce and t["end"] > cs],
                    "row_ids": [f'{t["id"]}@{r["row_index"]}' for t in si["tables"] for r in t["rows"]
                                if r["line_start"] < ce and r["line_end"] > cs],
                    "cell_ids": [f'{t["id"]}@{r["row_index"]}:{c["col"]}'
                                 for t in si["tables"] for r in t["rows"] for c in r["cells"]
                                 if c["start"] < ce and c["end"] > cs],
                    "list_ids": [l["id"] for l in si["lists"] if l["start"] < ce and l["end"] > cs],
                    "list_item_ids": [f'{l["id"]}#{it["index"]}' for l in si["lists"] for it in l["items"]
                                      if it["start"] < ce and it["end"] > cs],
                }
                for k, v in rec["structure"].items():
                    if v:
                        struct_cov[k] += 1
            else:
                rec["structure"] = None
            chunk_rows.append(rec)
            seq += 1
        per_doc[doc_id] = {
            "chunk_count": seq,
            "offsets_resolved": resolved,
            "offset_resolution_rate": round(resolved / seq, 4) if seq else None,
            "structure_coverage": dict(struct_cov),
            "virtual": doc_id == "unanswerable_corpus",
        }
        # per-doc jsonl
        with open(CHUNK_DIR / f"{doc_id}.jsonl", "w", encoding="utf-8") as f:
            for r in chunk_rows:
                if r["document_id"] == doc_id:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")

    total = sum(v["chunk_count"] for v in per_doc.values())
    total_res = sum(v["offsets_resolved"] for v in per_doc.values())
    CHECKS["chunk_corpus"] = total > 0 and total_res == total
    return chunk_rows, {"per_document": per_doc, "total_chunks": total,
                        "total_offsets_resolved": total_res}


# =========================================================================
# 5. TASK 6 — chunk-level gold-evidence presence (multi-criterion)
# =========================================================================
def chunk_evidence(examples: list[dict], canon: dict, index: dict,
                   prov_rows: list[dict], chunk_rows: list[dict]) -> list[dict]:
    prov_by_id = {r["example_id"]: r for r in prov_rows}
    chunks_by_doc = defaultdict(list)
    for c in chunk_rows:
        if c["source_start"] is not None:
            chunks_by_doc[c["document_id"]].append(c)

    rows = []
    answerable = [e for e in examples if e["question_kind"] != "UNANSWERABLE"]
    for e in answerable:
        doc_id, ctx, ans = e["document_id"], e["context"], e["answer"]
        kind = e["question_kind"]
        prov = prov_by_id.get(e["example_id"], {})
        text = canon[doc_id]
        rec = {"example_id": e["example_id"], "document_id": doc_id, "question_kind": kind,
               "answer_chars": len(ans)}

        # --- evidence in reconstructed document (Task 6 Q1) ---------------
        ans_exact_pos = all_occ(text, ans)
        ans_norm = norm_text(ans) in norm_text(text)
        num = numeric_presence(ans, text)
        struct = structural_membership(ans, doc_id, index)
        ambiguity = []
        if len(ans_exact_pos) > 1:
            ambiguity.append(f"answer_occurs_{len(ans_exact_pos)}_times_in_document")
        if num.get("applied") and num.get("candidate_occurrences", 0) > 1:
            ambiguity.append(f"numeric_candidates_{num['candidate_occurrences']}")
        if len(struct.get("hits", [])) > 1:
            ambiguity.append(f"structural_hits_{len(struct['hits'])}")

        rec["textual_match"] = {"exact_occurrences": len(ans_exact_pos),
                                "normalized_present": ans_norm,
                                "rule_ids": ["N1-textual-fold"]}
        rec["numeric_match"] = num
        rec["structural_match"] = struct
        rec["in_source_document"] = bool(ans_exact_pos) or ans_norm or bool(struct["applied"]) or bool(
            num.get("all_values_present"))

        # --- gold source span from provenance position (offset check) -----
        gold_span, source_offset_match, offset_reason = None, False, None
        positions = prov.get("context_positions") or []
        if prov.get("provenance_class") == "SOURCE_SPAN_VERIFIED" and len(positions) == 1:
            gs = positions[0] + e["answer_start"]
            ge = positions[0] + e["answer_end"]
            gold_span = [gs, ge]
            sliced = text[gs:ge]
            source_offset_match = sliced == ans
            offset_reason = "context_position_plus_answer_start" if source_offset_match else \
                f"slice_mismatch:{sliced[:40]!r}"
        elif positions:
            offset_reason = "context_not_uniquely_located_offset_unusable"
        else:
            offset_reason = "context_not_a_source_span_offsets_unavailable"

        # answer-level fallback span (exact occurrence) for chunk mapping
        chunk_anchor = gold_span or ([ans_exact_pos[0], ans_exact_pos[0] + len(ans)]
                                     if ans_exact_pos else None)

        # --- evidence in stored chunks (Task 6 Q2-Q5) ---------------------
        covering, fully, cross = [], [], None
        if chunk_anchor:
            gs, ge = chunk_anchor
            for c in chunks_by_doc[doc_id]:
                if c["source_start"] < ge and c["source_end"] > gs:
                    covering.append(c["chunk_id"])
                    if c["source_start"] <= gs and c["source_end"] >= ge:
                        fully.append(c["chunk_id"])
            cross = bool(covering) and not bool(fully)

        text_hits = [c["chunk_id"] for c in chunks_by_doc[doc_id] if ans in c["text"]]
        norm_hits = [c["chunk_id"] for c in chunks_by_doc[doc_id] if norm_text(ans) in norm_text(c["text"])]

        # structural context preserved inside covering chunks?
        struct_ctx = None
        if kind in ("TABLE_CELL", "TABLE_ROW"):
            t_ids = [h["element"] for h in struct.get("hits", []) if h["kind"].startswith("table")]
            t_id = t_ids[0] if t_ids else (prov.get("structural_context_pair") or {}).get("element")
            if t_id:
                t = next((t for t in index[doc_id]["tables"] if t["id"] == t_id), None)
                if t:
                    header_line = " | ".join(t["headers"])
                    struct_ctx = any(header_line in c["text"] for c in chunks_by_doc[doc_id]
                                     if c["chunk_id"] in covering) or \
                        any(header_line in c["text"] for c in chunks_by_doc[doc_id] if ans in c["text"])
        elif kind == "LIST_ITEM":
            l_ids = [h["element"] for h in struct.get("hits", []) if h["kind"] == "list_item"]
            if l_ids:
                l = next((l for l in index[doc_id]["lists"] if l["id"] == l_ids[0]), None)
                if l and l.get("heading"):
                    struct_ctx = any(l["heading"] in c["text"] for c in chunks_by_doc[doc_id]
                                     if c["chunk_id"] in covering or ans in c["text"])

        rec.update({
            "gold_span_in_document": gold_span,
            "source_offset_match": source_offset_match,
            "source_offset_reason": offset_reason,
            "chunks": {
                "denominator_chunks_in_document": len(chunks_by_doc[doc_id]),
                "covering_chunk_ids": covering,
                "fully_containing_chunk_ids": fully,
                "gold_text_chunk_hits": text_hits,
                "normalized_chunk_hits": norm_hits,
                "gold_span_crosses_chunk_boundary": cross,
                "evidence_present_in_stored_chunks": bool(fully or text_hits or norm_hits),
                "structural_context_in_chunk": struct_ctx,
            },
            "ambiguity_flags": ambiguity,
        })
        rows.append(rec)
    return rows


# =========================================================================
# 6. AGGREGATES (prerequisite verification counts ONLY — no E0 stages)
# =========================================================================
def aggregate_prov(rows: list[dict]) -> dict:
    total = len(rows)
    by_class = Counter(r["provenance_class"] for r in rows)
    per_kind = defaultdict(Counter)
    for r in rows:
        per_kind[r["question_kind"]][r["provenance_class"]] += 1
    multi = [r for r in rows if r["question_kind"] == "MULTI_CHUNK"]
    tables = [r for r in rows if r["question_kind"] in ("TABLE_CELL", "TABLE_ROW")]
    lists = [r for r in rows if r["question_kind"] == "LIST_ITEM"]
    return {
        "denominator_answerable_examples": total,
        "provenance_class_counts": dict(by_class),
        "provenance_rate": round(by_class.get("SOURCE_SPAN_VERIFIED", 0) / total, 4) if total else None,
        "per_category_class_counts": {k: dict(v) for k, v in sorted(per_kind.items())},
        "multi_chunk_nature_counts": dict(Counter(r.get("multi_chunk_nature", "n/a") for r in multi)),
        "multi_chunk_denominator": len(multi),
        "table_structural_provenance_verified": sum(
            1 for r in tables if (r.get("structural_provenance") or {}).get("applied")),
        "table_denominator": len(tables),
        "list_structural_provenance_verified": sum(
            1 for r in lists if (r.get("structural_provenance") or {}).get("applied")),
        "list_denominator": len(lists),
        "cross_document_context_ambiguity": sum(1 for r in rows if r.get("cross_document_context_hits")),
        "context_nature_counts": dict(Counter(r.get("context_nature") for r in rows)),
    }


def aggregate_evidence(rows: list[dict]) -> dict:
    total = len(rows)
    in_src = sum(1 for r in rows if r["in_source_document"])
    in_chunk = sum(1 for r in rows if r["chunks"]["evidence_present_in_stored_chunks"])
    offset_ok = sum(1 for r in rows if r["source_offset_match"])
    contained = sum(1 for r in rows if r["chunks"]["fully_containing_chunk_ids"])
    crossing = sum(1 for r in rows if r["chunks"]["gold_span_crosses_chunk_boundary"])
    per_kind = defaultdict(lambda: Counter())
    for r in rows:
        c = per_kind[r["question_kind"]]
        c["n"] += 1
        c["in_source"] += bool(r["in_source_document"])
        c["in_chunks"] += bool(r["chunks"]["evidence_present_in_stored_chunks"])
        c["offset_ok"] += bool(r["source_offset_match"])
    return {
        "denominator_answerable_examples": total,
        "evidence_in_source_document": {"count": in_src, "denominator": total,
                                        "rate": round(in_src / total, 4) if total else None},
        "evidence_in_stored_chunks": {"count": in_chunk, "denominator": total,
                                      "rate": round(in_chunk / total, 4) if total else None},
        "source_offset_match": {"count": offset_ok, "denominator": total,
                                "rate": round(offset_ok / total, 4) if total else None},
        "gold_span_fully_inside_one_chunk": {"count": contained, "denominator": total},
        "gold_span_crosses_chunk_boundary": {"count": crossing, "denominator": total},
        "per_category": {k: dict(v) for k, v in sorted(per_kind.items())},
        "structural_context_preserved_in_covering_chunk": {
            "table_cell": {"count": sum(1 for r in rows if r["question_kind"] == "TABLE_CELL"
                                        and r["chunks"]["structural_context_in_chunk"]),
                           "denominator": sum(1 for r in rows if r["question_kind"] == "TABLE_CELL")},
            "table_row": {"count": sum(1 for r in rows if r["question_kind"] == "TABLE_ROW"
                                       and r["chunks"]["structural_context_in_chunk"]),
                          "denominator": sum(1 for r in rows if r["question_kind"] == "TABLE_ROW")},
            "list_item": {"count": sum(1 for r in rows if r["question_kind"] == "LIST_ITEM"
                                       and r["chunks"]["structural_context_in_chunk"]),
                          "denominator": sum(1 for r in rows if r["question_kind"] == "LIST_ITEM")},
        },
        "ambiguity_flagged_examples": sum(1 for r in rows if r["ambiguity_flags"]),
        "scope_note": ("prerequisite evidence-chain verification counts only; NOT E0 "
                       "stage attribution, no failure decomposition, no conditional EM/F1"),
    }


# =========================================================================
# 7. TASK 11 — model-input config pinning + single labelled L4 probe
# =========================================================================
def pin_model_input_config() -> dict:
    def grab(path: Path, pattern: str):
        m = re.search(pattern, path.read_text(encoding="utf-8"))
        return m.group(1) if m else None

    ckpt_files = {}
    for p in sorted(F2_CKPT.iterdir()):
        if p.is_file():
            ckpt_files[p.name] = {"sha256": sha256_file(p), "bytes": p.stat().st_size}
    inf = json.loads(INFERENCE_CONFIG.read_text(encoding="utf-8"))
    out = {
        "diagnostic_target": "recorded F2 benchmark predictions (P3)",
        "f2_recorded_predictions": {
            "producer_scripts": {
                "raw_predictions_benchmark.json": "phase4f_5f/f2/threshold_experiment/run_threshold_experiment.py:303",
                "f2_benchmark.json": "phase4f_5f/f2/run_f2.py:610",
            },
            "checkpoint_used_by_threshold_script": str(F2_CKPT.relative_to(REPO)),
            "checkpoint_files": ckpt_files,
            "tokenizer_path": str(F2_CKPT.relative_to(REPO)),
            "model_path": str(F2_CKPT.relative_to(REPO)),
            "max_length": int(grab(RUN_THRESH, r"MAX_LENGTH\s*=\s*(\d+)") or 0),
            "max_length_source": "run_threshold_experiment.py:35 and run_f2.py:47 (=384)",
            "truncation_strategy": "truncation=True (right truncation, tokenizer default)",
            "padding_strategy": "padding=\"max_length\" (padded to 384)",
            "max_answer_length": int(grab(RUN_THRESH, r"MAX_ANSWER_LENGTH\s*=\s*(\d+)") or 0),
            "max_answer_length_run_f2": int(grab(RUN_F2, r"MAX_ANSWER_LENGTH\s*=\s*(\d+)") or 0),
            "max_answer_length_applies_to_recorded_f2": 50,
            "max_answer_length_evidence": (
                "run_threshold_experiment.py:36 MAX_ANSWER_LENGTH=50 used at decode "
                "(end_logits[best_start:best_start+50]); run_f2.py:48,157,373 same value"
            ),
            "n_best": "not applicable — argmax span decode (no n_best list in F2 chain)",
            "decode_strategy": "argmax start, argmax end within [start, start+50), CLS masked in threshold script",
        },
        "production_a0_scope": {
            "component": "chat/qa_model.py answer_question (production inference)",
            "max_answer_length": inf.get("max_answer_length"),
            "n_best": inf.get("n_best"),
            "max_input_length": inf.get("max_input_length"),
            "model_path_field": inf.get("model_path"),
            "config_file": str(INFERENCE_CONFIG.relative_to(REPO)),
            "applies_to": "production A0 serving only — NOT to recorded F2 benchmark predictions",
        },
        "p1_experiment_family_scope": {
            "max_answer_length_default_50": "phase4f/experiments/evaluate.py:200 ex.get('max_answer_length', 50)",
            "recorded_50": "phase4f/quality_gate.py:615; phase4f/experiments/train.py:55",
            "applies_to": "P1 experiment family records — separate scope",
        },
        "discrepancy_resolution": (
            "NO CONFLICT once scoped: recorded F2 benchmark predictions were decoded with "
            "max_answer_length=50 (code evidence); the value 100 is production A0's "
            "inference_config setting for qa_model.answer_question; 50 in evaluate.py is the "
            "P1-family example-field default. Both values recorded with scopes; neither "
            "silently chosen."
        ),
        "versions": {},
    }
    try:
        import transformers, tokenizers
        out["versions"] = {"python": platform.python_version(),
                           "transformers": transformers.__version__,
                           "tokenizers": tokenizers.__version__}
    except Exception as exc:  # pragma: no cover
        out["versions"] = {"error": str(exc)}

    # --- ONE labelled methodology probe (single example; no aggregates) ---
    probe = {"label": "L4_CAPABILITY_PROBE_SINGLE_EXAMPLE", "aggregate_l4_measurement": False,
             "examples_used": 1, "inference": False}
    try:
        from transformers import AutoTokenizer
        tok = AutoTokenizer.from_pretrained(str(F2_CKPT), local_files_only=True)
        bench_line = BENCH_PATH.read_text(encoding="utf-8").splitlines()
        target = next(json.loads(ln) for ln in bench_line
                      if json.loads(ln)["question_kind"] != "UNANSWERABLE")
        enc = tok(target["question"], target["context"], max_length=384, truncation=True,
                  padding="max_length", return_offsets_mapping=True)
        offsets = enc["offset_mapping"]
        a0, a1 = target["answer_start"], target["answer_end"]
        tok_span = [i for i, (s, e) in enumerate(offsets) if s < a1 and e > a0 and s != e]
        probe.update({
            "example_id": target["example_id"],
            "input_ids_length": len(enc["input_ids"]),
            "padded_to": 384,
            "context_truncated_by_tokenizer": bool(
                tok(target["question"], target["context"], max_length=384,
                    truncation=False)["input_ids"].__len__() > 384),
            "answer_token_span_found": bool(tok_span),
            "answer_token_positions_present": len(tok_span),
            "tokenizer_class": type(tok).__name__,
        })
        probe["status"] = "MODEL_INPUT_RECONSTRUCTIBLE"
    except Exception as exc:
        probe.update(status="PROBE_FAILED", error=f"{type(exc).__name__}: {exc}")
        probe["traceback"] = traceback.format_exc(limit=3)
    out["l4_probe"] = probe
    return out


# =========================================================================
# 8. TASK 10 — context-assembly isolated probe
# =========================================================================
def probe_context_assembly() -> dict:
    out = {"attempted": True}
    try:
        from chat.rag import build_qa_context, build_context, SourceChunk
        from chat.qa_model import get_max_input_length
        chunks = [
            SourceChunk(chunk_id="probe::c000", content="Alpha beta gamma. " * 30, score=0.91,
                        document_id="probe_doc", document_name="probe", page=None),
            SourceChunk(chunk_id="probe::c001", content="Delta epsilon zeta. " * 40, score=0.72,
                        document_id="probe_doc", document_name="probe", page=None),
        ]
        q = "What is the alpha value?"
        r1 = build_qa_context(chunks, q)
        r2 = build_qa_context(chunks, q)
        legacy1 = build_context(chunks)
        legacy2 = build_context(chunks)
        out.update({
            "status": "DETERMINISTICALLY_RECONSTRUCTIBLE",
            "functions_probed": ["chat.rag.build_qa_context", "chat.rag.build_context"],
            "deterministic_across_repeated_runs": (str(r1) == str(r2)) and (legacy1 == legacy2),
            "included_ids": list(r1.included_ids), "omitted_ids": list(r1.omitted_ids),
            "budget_tokens": r1.budget_tokens, "used_tokens": r1.used_tokens,
            "model_input_window": get_max_input_length(),
            "scope": (
                "function-level assembly is executable in isolation and deterministic; the "
                "END-TO-END chain (retrieved chunks -> assembly) remains UNRESOLVED because "
                "retrieval cannot execute (see retrieval manifest)"
            ),
            "observed_end_to_end": False,
        })
    except Exception as exc:
        out.update(status="UNRESOLVED", error=f"{type(exc).__name__}: {exc}")
        out["traceback"] = traceback.format_exc(limit=3)
    return out


# =========================================================================
# 9. TASKS 7-9 — retrieval execution feasibility (STOP on failure)
# =========================================================================
def probe_retrieval_feasibility() -> dict:
    out = {"attempted_locally": True}
    # port probe (localhost only)
    try:
        s = socket.create_connection(("127.0.0.1", 5432), timeout=1.5)
        s.close()
        out["postgres_localhost_5432"] = "OPEN"
    except OSError as exc:
        out["postgres_localhost_5432"] = f"CLOSED ({exc.__class__.__name__})"
    out["postgres_tooling"] = {name: shutil.which(name)
                               for name in ("psql", "pg_ctl", "initdb", "pg_config", "docker")}
    out["program_files_postgresql"] = Path("C:/Program Files/PostgreSQL").exists()
    cache = Path.home() / ".cache/huggingface/hub"
    out["embedding_model_cached"] = (cache / "models--sentence-transformers--all-MiniLM-L6-v2").exists()
    out["production_retrieval_path"] = {
        "function": "chat/rag.py::retrieve_chunks(db, user_id, query, top_k=5)",
        "engine": "PostgreSQL + pgvector cosine (<=>) over document_chunks",
        "embedding": "embeddings/model.py::embed_query (all-MiniLM-L6-v2, 384-dim) — executable locally (cached)",
        "top_k": 5,
        "relevance_threshold": 0.15,
        "sql_dependency": "document_chunks JOIN documents; CAST(:embedding AS vector)",
    }
    blocked = out["postgres_localhost_5432"].startswith("CLOSED") and not any(
        out["postgres_tooling"].values())
    out["executed"] = False
    out["traces_produced"] = 0
    out["fabricated"] = False
    out["status"] = "BLOCKED" if blocked else "BLOCKED_PENDING_MANUAL_CONFIRMATION"
    # CORRECTION (2026-09-27, see decision/E0_ERRATUM_2026-09-27.md C11): the previous
    # text asserted that backend/.env targets localhost:5432 and that no postgres tooling
    # exists on this machine. Both were wrong — localhost is only the config.py /
    # alembic.ini default, and a PostgreSQL 16.6 distribution is present at
    # C:/pgdata/pgsql (just not running and not on PATH). Do not restate a database
    # target as fact here; the target is whatever backend/.env resolves to.
    out["blocker"] = (
        "The existing production retrieval path requires a running PostgreSQL+pgvector "
        "instance (target resolved from backend/.env — do not assume localhost). No "
        "Postgres server was running at probe time, no postgres tooling was on PATH and "
        "no Docker exists on this machine, and no "
        "stored chunk corpus exists for the six isolated documents. Executing retrieval "
        "would require standing up a new database service and an ingestion+embedding "
        "pipeline — infrastructure setup outside this phase's authority, and building a "
        "replacement retrieval implementation is explicitly forbidden by Task 7. "
        "STOP invoked: zero retrieval traces produced; none fabricated."
    )
    CHECKS["retrieval_blocker_confirmed"] = bool(blocked)
    return out


# =========================================================================
# MAIN
# =========================================================================
__DOCS__: list = []
__DOC_BY_ID__: dict = {}


def main() -> int:
    global __DOCS__, __DOC_BY_ID__
    from phase4f.dataset.expand_and_audit import DOCUMENTS
    __DOCS__ = [d for d in DOCUMENTS if d["doc_id"] in CONTENT_DOCS]
    __DOC_BY_ID__ = {d["doc_id"]: d for d in __DOCS__}

    RESULTS["created_utc"] = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc).isoformat()

    frozen, examples = verify_frozen()
    RESULTS["frozen_verification"] = frozen

    canon, index, corpus_records = build_source_corpus(examples)
    RESULTS["source_corpus"] = {
        "documents": [{k: v for k, v in r.items() if k != "document_text"} for r in corpus_records],
        "classifications": dict(Counter(r["classification"] for r in corpus_records)),
        "canonical_rule": CANON_RULE_ID,
    }

    prov_rows = verify_provenance(examples, canon, index)
    jlines(DIAG_DIR / "provenance_results.jsonl", prov_rows)
    RESULTS["task4_provenance"] = aggregate_prov(prov_rows)

    try:
        chunk_rows, chunk_meta = build_chunks(canon, index, corpus_records)
    except Exception as exc:
        chunk_rows, chunk_meta = [], {"status": "BLOCKED", "error": f"{type(exc).__name__}: {exc}",
                                      "traceback": traceback.format_exc(limit=3)}
        CHECKS["chunk_corpus"] = False
    RESULTS["task5_chunk_corpus"] = chunk_meta

    if chunk_rows:
        ev_rows = chunk_evidence(examples, canon, index, prov_rows, chunk_rows)
        jlines(DIAG_DIR / "chunk_evidence_results.jsonl", ev_rows)
        RESULTS["task6_chunk_evidence"] = aggregate_evidence(ev_rows)
    else:
        RESULTS["task6_chunk_evidence"] = {"status": "NOT_RUN", "reason": "chunk corpus blocked"}

    RESULTS["task11_model_input"] = pin_model_input_config()
    RESULTS["task10_context_assembly"] = probe_context_assembly()
    RESULTS["tasks7_9_retrieval"] = probe_retrieval_feasibility()

    try:
        import torch, transformers, sentence_transformers
        RESULTS["environment"] = {
            "python": platform.python_version(), "platform": platform.platform(),
            "torch": torch.__version__, "transformers": transformers.__version__,
            "sentence_transformers": sentence_transformers.__version__,
            "offline_env": {k: os.environ.get(k) for k in
                            ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")},
        }
    except Exception as exc:
        RESULTS["environment"] = {"error": str(exc)}

    RESULTS["checks"] = CHECKS
    RESULTS["all_checks_pass"] = all(CHECKS.values()) and len(CHECKS) >= 3

    jdump(DIAG_DIR / "summary.json", RESULTS)

    # ---- E0_CORPUS_MANIFEST.json (decision/) ----------------------------
    corpus_manifest = {
        "artifact": "E0_CORPUS_MANIFEST.json",
        "phase": "4F.6-D",
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "created_utc": RESULTS["created_utc"],
        "isolated": True,
        "location": "backend/architecture/phase4f_6/e0_diagnostics/source_corpus/",
        "production_storage_used": False,
        "canonical_serialization_rule": {
            "id": CANON_RULE_ID,
            "section_block": 'join([heading?] + paragraphs + [table blocks] + [list blocks], "\\n\\n")  (DOCUMENTS key order)',
            "table_block": 'join over [headers]+rows of " | ".join(row), lines joined "\\n"',
            "list_block": "expand_and_audit._list_str (heading + items, newline-joined)",
            "document_text": 'join(section blocks, "\\n\\n")',
            "validation": "empirically validated by Task 4 provenance results (see E0_SOURCE_PROVENANCE.md)",
        },
        "frozen_benchmark": {
            "path": str(BENCH_PATH.relative_to(REPO)),
            "sha256": frozen["benchmark_sha256"],
            "hash_unchanged": frozen["benchmark_hash_matches_frozen"],
            "counts": {"total": frozen["benchmark_lines"],
                       "answerable": frozen["benchmark_answerable"],
                       "unanswerable": frozen["benchmark_unanswerable"],
                       "documents": len(frozen["document_counts"])},
        },
        "documents": RESULTS["source_corpus"]["documents"],
        "checks": CHECKS,
    }
    jdump(DECISION_DIR / "E0_CORPUS_MANIFEST.json", corpus_manifest)

    # ---- E0_CHUNK_MANIFEST.json (decision/) -----------------------------
    if chunk_rows:
        chunk_manifest = {
            "artifact": "E0_CHUNK_MANIFEST.json",
            "phase": "4F.6-D",
            "diagnostic_version": DIAGNOSTIC_VERSION,
            "created_utc": RESULTS["created_utc"],
            "isolated": True,
            "location": "backend/architecture/phase4f_6/e0_diagnostics/chunks/",
            "chunker": {
                "version_recorded_before_execution": "chunk-v1-legacy-chars-1000-200",
                "production_default": 'config.py chunker_version="legacy" (structure-v2 is the '
                                      "candidate, NOT production)",
                "implementation": "documents/processing.py::chunk_text (EXISTING, unmodified)",
                "chunk_size_chars": 1000, "chunk_overlap_chars": 200,
                "chunk_size_source": "documents/processing.py:607-608",
                "enrichment": '_prepend_heading_context: "Section > Subsection\\n\\nContent" '
                              "(not applied to heading elements)",
                "configuration_changed": False,
            },
            "element_decomposition": (
                "reconstructed documents decomposed to ExtractedElement (heading/paragraph/"
                "table/list) mirroring DOCUMENTS key order; table content = CANON-v1 block; "
                "list content = _list_str — both byte-identical to canonical spans"
            ),
            "per_document": RESULTS["task5_chunk_corpus"]["per_document"],
            "totals": {
                "chunks": RESULTS["task5_chunk_corpus"]["total_chunks"],
                "offsets_resolved": RESULTS["task5_chunk_corpus"]["total_offsets_resolved"],
            },
            "structure_metadata_note": (
                "legacy chunker stores no structure columns; structure ids (section/table/row/"
                "cell/list/item) were computed post-hoc by span intersection and are recorded "
                "per chunk — diagnostic provenance only, not a production schema change"
            ),
            "production_isolation": {
                "production_database_accessed": False,
                "production_uploads_touched": False,
                "production_chunker_unmodified": True,
            },
            "checks": CHECKS,
        }
        jdump(DECISION_DIR / "E0_CHUNK_MANIFEST.json", chunk_manifest)

    print(json.dumps({
        "frozen_ok": CHECKS.get("frozen_integrity"),
        "source_ok": CHECKS.get("source_reconstruction"),
        "chunks_ok": CHECKS.get("chunk_corpus"),
        "retrieval_blocker": CHECKS.get("retrieval_blocker_confirmed"),
        "provenance": RESULTS["task4_provenance"]["provenance_class_counts"],
        "chunks_total": RESULTS["task5_chunk_corpus"].get("total_chunks"),
        "context_assembly": RESULTS["task10_context_assembly"].get("status"),
        "l4_probe": RESULTS["task11_model_input"]["l4_probe"].get("status"),
        "retrieval": RESULTS["tasks7_9_retrieval"]["status"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
