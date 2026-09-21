"""Phase 4B — Expanded evaluation corpus.

Extends the Phase 3F corpus with additional documents and questions to
reach 100+ questions across 20+ documents.  Covers:
  - Dense prose, short factual, long paragraphs
  - Tables (small, medium, large, nested)
  - Lists (bullet, numbered, nested, long)
  - Multi-page PDFs
  - Multi-chunk answers
  - Numeric/date/entity/unit answers
  - Section-specific questions
  - Surrounding-context questions
  - Unanswerable questions
  - Adversarial questions
  - Comparative questions
  - Definition questions

The Phase 3F corpus (12 documents, 42 questions) is preserved exactly.
New documents and questions are added separately.

Document provenance:
  - All documents are SYNTHETIC (programmatic)
  - No real-world documents are included
  - REAL_CORPUS_STATUS = NOT_AVAILABLE
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import docx
import fitz  # PyMuPDF


# ---------------------------------------------------------------------------
# Types (same as Phase 3F)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Question:
    qid: str
    text: str
    answerable: bool = True
    expected_answer: str | None = None
    evidence: tuple[str, ...] = ()
    kind: str = "factual"
    notes: str = ""


@dataclass
class CorpusDoc:
    name: str
    file_type: str
    builder: Callable[[Path], None]
    questions: list[Question] = field(default_factory=list)
    notes: str = ""

    def write(self, directory: Path) -> Path:
        path = directory / self.name
        self.builder(path)
        return path


# ---------------------------------------------------------------------------
# Document metadata
# ---------------------------------------------------------------------------

DOCUMENT_METADATA = {
    # Phase 3F documents (preserved)
    "short_sections.docx": {"synthetic": True, "kind": "short_sections", "format": "docx"},
    "heading_heavy.docx": {"synthetic": True, "kind": "heading_heavy", "format": "docx"},
    "tables_small.docx": {"synthetic": True, "kind": "tables", "format": "docx"},
    "tables_large.docx": {"synthetic": True, "kind": "tables", "format": "docx"},
    "lists.docx": {"synthetic": True, "kind": "lists", "format": "docx"},
    "mixed.docx": {"synthetic": True, "kind": "mixed", "format": "docx"},
    "long_paragraph.txt": {"synthetic": True, "kind": "long_paragraph", "format": "txt"},
    "dense_prose.txt": {"synthetic": True, "kind": "dense_prose", "format": "txt"},
    "unpunctuated.txt": {"synthetic": True, "kind": "unpunctuated", "format": "txt"},
    "markdown_sections.txt": {"synthetic": True, "kind": "markdown", "format": "txt"},
    "multipage_section.pdf": {"synthetic": True, "kind": "multipage", "format": "pdf"},
    "academic_two_column.pdf": {"synthetic": True, "kind": "academic", "format": "pdf"},
    # Phase 4B new documents
    "tables_medium.docx": {"synthetic": True, "kind": "tables", "format": "docx"},
    "tables_nested.docx": {"synthetic": True, "kind": "tables", "format": "docx"},
    "lists_nested.docx": {"synthetic": True, "kind": "lists", "format": "docx"},
    "lists_long.docx": {"synthetic": True, "kind": "lists", "format": "docx"},
    "technical_manual.docx": {"synthetic": True, "kind": "technical", "format": "docx"},
    "research_paper.txt": {"synthetic": True, "kind": "academic", "format": "txt"},
    "faq_document.txt": {"synthetic": True, "kind": "faq", "format": "txt"},
    "multi_page_report.pdf": {"synthetic": True, "kind": "multipage", "format": "pdf"},
    "timeline_data.txt": {"synthetic": True, "kind": "timeline", "format": "txt"},
    "mixed_structured.docx": {"synthetic": True, "kind": "mixed", "format": "docx"},
    "glossary.txt": {"synthetic": True, "kind": "glossary", "format": "txt"},
    "comparison_data.txt": {"synthetic": True, "kind": "comparison", "format": "txt"},
}


# ---------------------------------------------------------------------------
# DOCX builders — new Phase 4B documents
# ---------------------------------------------------------------------------

def _write_docx(path: Path, add) -> None:
    document = docx.Document()
    add(document)
    document.save(str(path))


def _build_tables_medium(path: Path) -> None:
    """10-row, 4-column table with header repetition."""
    def add(document):
        document.add_heading("Performance Benchmarks", level=1)
        document.add_paragraph(
            "The following table shows benchmark results across "
            "different configurations."
        )
        table = document.add_table(rows=11, cols=4)
        headers = ["Configuration", "Accuracy", "Latency (ms)", "Memory (MB)"]
        for i, h in enumerate(headers):
            table.cell(0, i).text = h
        data = [
            ("Baseline", "78.2", "120", "512"),
            ("Config A", "82.5", "95", "480"),
            ("Config B", "85.1", "110", "520"),
            ("Config C", "79.8", "88", "460"),
            ("Config D", "91.3", "150", "640"),
            ("Config E", "88.7", "130", "590"),
            ("Config F", "76.4", "85", "440"),
            ("Config G", "93.2", "180", "720"),
            ("Config H", "81.0", "100", "500"),
            ("Config I", "87.6", "140", "610"),
        ]
        for i, (cfg, acc, lat, mem) in enumerate(data, 1):
            table.cell(i, 0).text = cfg
            table.cell(i, 1).text = acc
            table.cell(i, 2).text = lat
            table.cell(i, 3).text = mem
    _write_docx(path, add)


def _build_tables_nested(path: Path) -> None:
    """Multiple tables in one document."""
    def add(document):
        document.add_heading("Survey Results", level=1)
        document.add_paragraph("Two surveys were conducted in different regions.")

        document.add_heading("Region Alpha", level=2)
        table1 = document.add_table(rows=4, cols=3)
        headers1 = ["Station", "Temperature", "Humidity"]
        for i, h in enumerate(headers1):
            table1.cell(0, i).text = h
        data1 = [
            ("Alpha-1", "22.5 degrees", "65%"),
            ("Alpha-2", "19.8 degrees", "72%"),
            ("Alpha-3", "24.1 degrees", "58%"),
        ]
        for i, (s, t, h) in enumerate(data1, 1):
            table1.cell(i, 0).text = s
            table1.cell(i, 1).text = t
            table1.cell(i, 2).text = h

        document.add_heading("Region Beta", level=2)
        table2 = document.add_table(rows=4, cols=3)
        headers2 = ["Station", "Temperature", "Humidity"]
        for i, h in enumerate(headers2):
            table2.cell(0, i).text = h
        data2 = [
            ("Beta-1", "18.3 degrees", "80%"),
            ("Beta-2", "21.7 degrees", "68%"),
            ("Beta-3", "16.9 degrees", "85%"),
        ]
        for i, (s, t, h) in enumerate(data2, 1):
            table2.cell(i, 0).text = s
            table2.cell(i, 1).text = t
            table2.cell(i, 2).text = h

        document.add_paragraph(
            "Region Beta had consistently higher humidity than Region Alpha."
        )
    _write_docx(path, add)


def _build_lists_nested(path: Path) -> None:
    """Nested bullet and numbered lists."""
    def add(document):
        document.add_heading("Setup Procedure", level=1)

        document.add_heading("Prerequisites", level=2)
        document.add_paragraph("Before beginning, ensure you have:", style="List Bullet")
        document.add_paragraph("Python 3.10 or later", style="List Bullet 2")
        document.add_paragraph("PostgreSQL 14 or later", style="List Bullet 2")
        document.add_paragraph("At least 8 GB RAM", style="List Bullet 2")
        document.add_paragraph("Valid API credentials", style="List Bullet")

        document.add_heading("Installation Steps", level=2)
        steps = [
            "Clone the repository from the main branch",
            "Install dependencies using pip install -r requirements.txt",
            "Configure the database connection in .env",
            "Run the migration script: alembic upgrade head",
            "Start the server with: python start_server.py",
            "Verify the health check at /api/health",
        ]
        for i, step in enumerate(steps, 1):
            document.add_paragraph(f"{step}", style="List Number")

        document.add_heading("Troubleshooting", level=2)
        document.add_paragraph("Common issues:", style="List Bullet")
        document.add_paragraph(
            "Database connection refused: check PostgreSQL is running",
            style="List Bullet 2",
        )
        document.add_paragraph(
            "Port 8000 in use: change the port in start_server.py",
            style="List Bullet 2",
        )
        document.add_paragraph(
            "Model not found: ensure models/documind-qa directory exists",
            style="List Bullet 2",
        )
    _write_docx(path, add)


def _build_lists_long(path: Path) -> None:
    """Long list with 12 items."""
    def add(document):
        document.add_heading("Server Components", level=1)
        document.add_paragraph("The system consists of the following components:")

        components = [
            "FastAPI web server handling HTTP requests",
            "PostgreSQL database with pgvector extension",
            "Sentence transformer model for embeddings",
            "DistilBERT model for question answering",
            "File storage system for uploaded documents",
            "JWT authentication module",
            "Brain orchestration layer",
            "Evidence gate for answer validation",
            "Context builder for QA input preparation",
            "Document chunker for text segmentation",
            "Embedding indexer for vector storage",
            "Health check endpoint for monitoring",
        ]
        for comp in components:
            document.add_paragraph(comp, style="List Bullet")

        document.add_paragraph(
            "Each component is independently testable and follows "
            "the single-responsibility principle."
        )
    _write_docx(path, add)


def _build_technical_manual(path: Path) -> None:
    """Mixed headings, tables, lists, paragraphs."""
    def add(document):
        document.add_heading("Calibration Guide", level=1)
        document.add_paragraph(
            "This guide covers the calibration procedure for "
            "the Meridian sensor array."
        )

        document.add_heading("Equipment", level=2)
        document.add_paragraph("Required equipment:", style="List Bullet")
        document.add_paragraph("Meridian calibration kit (MC-200)", style="List Bullet")
        document.add_paragraph("Reference signal generator", style="List Bullet")
        document.add_paragraph("Oscilloscope with 100 MHz bandwidth", style="List Bullet")

        document.add_heading("Calibration Data", level=2)
        table = document.add_table(rows=5, cols=3)
        table.cell(0, 0).text = "Parameter"
        table.cell(0, 1).text = "Nominal"
        table.cell(0, 2).text = "Tolerance"
        params = [
            ("Voltage", "5.0 V", "±0.1 V"),
            ("Current", "2.5 A", "±0.05 A"),
            ("Frequency", "1000 Hz", "±10 Hz"),
            ("Temperature", "25.0 C", "±0.5 C"),
        ]
        for i, (p, n, t) in enumerate(params, 1):
            table.cell(i, 0).text = p
            table.cell(i, 1).text = n
            table.cell(i, 2).text = t

        document.add_heading("Procedure", level=2)
        proc_steps = [
            "Power on the reference signal generator",
            "Set output to 5.0 V at 1000 Hz",
            "Connect to Meridian input channel A",
            "Record the measured voltage on the oscilloscope",
            "Compare against the nominal value of 5.0 V",
            "Adjust the trimmer capacitor until within tolerance",
            "Repeat for channels B, C, and D",
            "Log all calibration values in the calibration report",
        ]
        for step in proc_steps:
            document.add_paragraph(step, style="List Number")

        document.add_heading("Acceptance Criteria", level=2)
        document.add_paragraph(
            "All four channels must be within the specified tolerance "
            "after calibration.  If any channel fails, the unit must "
            "be returned to the manufacturer for repair."
        )
        document.add_paragraph(
            "The calibration is valid for 12 months from the date of "
            "the last successful calibration."
        )
    _write_docx(path, add)


def _build_mixed_structured(path: Path) -> None:
    """Tables + lists + prose + headings in one document."""
    def add(document):
        document.add_heading("Quarterly Report Q3 2025", level=1)
        document.add_paragraph(
            "This report summarises the key findings from the "
            "third quarter of 2025."
        )

        document.add_heading("Revenue Summary", level=2)
        table = document.add_table(rows=4, cols=3)
        table.cell(0, 0).text = "Month"
        table.cell(0, 1).text = "Revenue"
        table.cell(0, 2).text = "Growth"
        table.cell(1, 0).text = "July"
        table.cell(1, 1).text = "1.2 million"
        table.cell(1, 2).text = "8.5%"
        table.cell(2, 0).text = "August"
        table.cell(2, 1).text = "1.4 million"
        table.cell(2, 2).text = "12.3%"
        table.cell(3, 0).text = "September"
        table.cell(3, 1).text = "1.1 million"
        table.cell(3, 2).text = "-3.2%"

        document.add_heading("Key Achievements", level=2)
        for item in [
            "Launched the new document processing pipeline",
            "Reduced average query latency by 35%",
            "Expanded the evaluation corpus to 22 documents",
            "Achieved 95% uptime across all services",
        ]:
            document.add_paragraph(item, style="List Bullet")

        document.add_heading("Challenges", level=2)
        document.add_paragraph(
            "The September revenue decline was attributed to seasonal "
            "factors and the scheduled maintenance window.  "
            "The team addressed the latency regression in Config F "
            "by optimising the context builder."
        )

        document.add_heading("Next Quarter Goals", level=2)
        goals = [
            "Increase revenue to 1.5 million per month",
            "Reduce QA model latency by 20%",
            "Expand to 50+ evaluation questions",
            "Complete the security audit",
        ]
        for g in goals:
            document.add_paragraph(g, style="List Number")
    _write_docx(path, add)


# ---------------------------------------------------------------------------
# TXT builders — new Phase 4B documents
# ---------------------------------------------------------------------------

def _build_research_paper(path: Path) -> None:
    """Academic-style prose with sections."""
    path.write_text(
        "# Abstract\n\n"
        "We present the Falcon estimator, a novel approach to sparse signal "
        "recovery in high-dimensional spaces.  The estimator achieves 94.7% "
        "accuracy on the standard benchmark dataset, outperforming the "
        "previous state of the art by 3.2 percentage points.\n\n"
        "# Introduction\n\n"
        "Signal recovery in high-dimensional spaces is a fundamental "
        "problem in compressed sensing.  Traditional approaches rely on "
        "the restricted isometry property, which is often difficult to "
        "verify in practice.\n\n"
        "The Falcon estimator relaxes this requirement by using a "
        "learned dictionary that adapts to the signal structure.  "
        "This allows recovery of signals that violate the RIP.\n\n"
        "# Method\n\n"
        "The Falcon estimator consists of three stages:\n\n"
        "1. Dictionary learning: Learn a sparse dictionary D from training "
        "signals using K-SVD with 1000 iterations.\n\n"
        "2. Sparse coding: For each new signal y, find the sparse "
        "representation x such that y ≈ Dx using OMP with sparsity "
        "level k = 20.\n\n"
        "3. Recovery: Reconstruct the original signal from the sparse "
        "code using the learned dictionary.\n\n"
        "The key innovation is the adaptive dictionary, which captures "
        "signal-specific patterns that fixed dictionaries miss.\n\n"
        "# Results\n\n"
        "We evaluate on three benchmark datasets:\n\n"
        "- MNIST: 98.2% accuracy (baseline: 96.1%)\n"
        "- CIFAR-10: 87.4% accuracy (baseline: 84.1%)\n"
        "- ImageNet subset: 72.8% accuracy (baseline: 69.5%)\n\n"
        "The Falcon estimator consistently outperforms baselines across "
        "all datasets.  The improvement is most pronounced on ImageNet, "
        "where the adaptive dictionary captures complex visual patterns.\n\n"
        "# Conclusion\n\n"
        "The Falcon estimator provides a practical approach to sparse "
        "signal recovery that outperforms existing methods.  Future work "
        "will explore online dictionary learning for real-time applications.\n",
        encoding="utf-8",
    )


def _build_faq_document(path: Path) -> None:
    """Q&A format document."""
    path.write_text(
        "# Frequently Asked Questions\n\n"
        "## General\n\n"
        "Q: What is DocuMind?\n"
        "A: DocuMind is a document intelligence platform that allows "
        "users to ask natural language questions about their documents "
        "and receive accurate, evidence-backed answers.\n\n"
        "Q: What file formats does DocuMind support?\n"
        "A: DocuMind supports PDF, DOCX, and TXT file formats.  "
        "Additional formats may be added in future releases.\n\n"
        "Q: How large can uploaded documents be?\n"
        "A: The default maximum upload size is 50 MB per document.  "
        "This can be configured via the MAX_UPLOAD_SIZE_MB environment "
        "variable.\n\n"
        "## Technical\n\n"
        "Q: What embedding model does DocuMind use?\n"
        "A: DocuMind uses the all-MiniLM-L6-v2 model from sentence-transformers, "
        "which produces 384-dimensional embeddings.\n\n"
        "Q: What QA model is used for answer extraction?\n"
        "A: DocuMind uses a custom DistilBERT model fine-tuned on SQuAD 2.0 "
        "and additional QA datasets.  The model is local and does not "
        "require external API calls.\n\n"
        "Q: How does the evidence gate work?\n"
        "A: The evidence gate evaluates QA confidence and retrieval scores "
        "to determine whether an answer is strongly supported (SUCCESS), "
        "weakly supported (PARTIAL), or unsupported (INSUFFICIENT_EVIDENCE).\n\n"
        "## Troubleshooting\n\n"
        "Q: Why am I getting empty answers?\n"
        "A: Empty answers typically indicate that the QA model could not "
        "find relevant evidence in the retrieved chunks.  Try rephrasing "
        "your question or uploading different documents.\n\n"
        "Q: Why is the system slow?\n"
        "A: First queries may be slow due to model loading.  Subsequent "
        "queries should be faster.  If latency persists, check the "
        "server resources and database connection.\n\n"
        "## Security\n\n"
        "Q: Is my data secure?\n"
        "A: DocuMind stores documents locally and does not send data to "
        "external services.  Authentication is handled via JWT tokens.  "
        "All database queries use parameterised statements.\n\n"
        "Q: Can I delete my documents?\n"
        "A: Yes, documents can be deleted through the API.  Deletion "
        "removes the document, its chunks, and embeddings from the "
        "database and file storage.\n",
        encoding="utf-8",
    )


def _build_timeline_data(path: Path) -> None:
    """Dates and events timeline."""
    path.write_text(
        "# Project Timeline\n\n"
        "## 2024\n\n"
        "January 2024: Project inception.  Team of 3 engineers "
        "assembled.\n\n"
        "March 2024: First prototype completed.  Basic document "
        "upload and search functionality.\n\n"
        "June 2024: QA model trained on SQuAD 2.0.  Initial accuracy "
        "of 72% on internal benchmark.\n\n"
        "September 2024: Embedding pipeline integrated.  pgvector "
        "deployment completed.\n\n"
        "December 2024: Version 1.0 released.  Supports PDF, DOCX, "
        "TXT formats.\n\n"
        "## 2025\n\n"
        "February 2025: Brain orchestration layer implemented.  "
        "Deterministic planning and evidence gating.\n\n"
        "April 2025: Structure-aware chunking introduced.  Heading, "
        "table, and list preservation.\n\n"
        "July 2025: Phase 3D evaluation completed.  79 chunks, "
        "89.7% recall@5.\n\n"
        "August 2025: Phase 3F evaluation completed.  Structure-v2 "
        "achieves 100% recall@5.\n\n"
        "September 2025: QA failure audit completed.  28.2% QA_EXTRACT "
        "failure rate identified.\n\n"
        "## 2026\n\n"
        "January 2026: Expanded evaluation corpus planned.  Target: "
        "100+ questions across 22+ documents.\n\n"
        "March 2026: QA model retraining scheduled with table and "
        "list training data.\n\n"
        "June 2026: Production deployment of structure-v2 planned, "
        "pending broader validation.\n\n"
        "September 2026: Security audit and observability improvements "
        "scheduled.\n",
        encoding="utf-8",
    )


def _build_glossary(path: Path) -> None:
    """Definitions and terms."""
    path.write_text(
        "# Technical Glossary\n\n"
        "## A\n\n"
        "Abstention: The system's decision to withhold an answer when "
        "evidence is insufficient.  A correct abstention is a successful "
        "outcome, not a failure.\n\n"
        "Answerability: A binary classification indicating whether a "
        "question can be answered from the available documents.\n\n"
        "## B\n\n"
        "Brain: The orchestration layer that classifies intent, builds "
        "execution plans, and coordinates service execution.\n\n"
        "Chunk: A segment of document text produced by the chunking "
        "pipeline, ready for embedding and retrieval.\n\n"
        "## C\n\n"
        "Context window: The maximum number of tokens the QA model can "
        "process as input (question + context).  Currently 384 tokens.\n\n"
        "CTX_TRUNC: Failure category where relevant evidence was retrieved "
        "but exceeded the QA context window.\n\n"
        "## E\n\n"
        "EVID_OMIT: Failure category where relevant evidence was retrieved "
        "but not included in the QA context.\n\n"
        "Evidence gate: Component that evaluates evidence signals to "
        "determine the final outcome (SUCCESS, PARTIAL, or "
        "INSUFFICIENT_EVIDENCE).\n\n"
        "## F\n\n"
        "False abstention: When the system abstains on a question that "
        "could have been answered correctly.\n\n"
        "## M\n\n"
        "MRR: Mean Reciprocal Rank — the average of 1/rank for the first "
        "relevant result across all queries.\n\n"
        "## Q\n\n"
        "QA_EXTRACT: Failure category where the QA model extracted the "
        "wrong answer span despite correct evidence being in the context.\n\n"
        "## R\n\n"
        "Recall@K: The fraction of answerable questions where at least "
        "one relevant chunk appears in the top-K retrieval results.\n\n"
        "RET_MISS: Failure category where no relevant chunk appears in "
        "the top-K retrieval results.\n\n"
        "## S\n\n"
        "Spurious answer: When the system provides an answer to a "
        "question that cannot be supported by the documents.\n\n"
        "Structure-v2: The candidate chunking strategy that preserves "
        "heading, table, and list structure in chunks.\n",
        encoding="utf-8",
    )


def _build_comparison_data(path: Path) -> None:
    """ASCII table format with comparisons."""
    path.write_text(
        "# Model Comparison\n\n"
        "The following models were evaluated on the DocuMind benchmark:\n\n"
        "Model          | Parameters | Accuracy | Latency\n"
        "---------------|------------|----------|--------\n"
        "DistilBERT     | 66M        | 78.3%    | 15ms\n"
        "BERT-base      | 110M       | 82.1%    | 28ms\n"
        "BERT-large     | 340M       | 85.7%    | 65ms\n"
        "DeBERTa-base   | 86M        | 84.2%    | 22ms\n"
        "DeBERTa-large  | 304M       | 87.9%    | 58ms\n"
        "RoBERTa-base   | 125M       | 81.5%    | 25ms\n"
        "Longformer     | 149M       | 83.8%    | 45ms\n\n"
        "Notes:\n"
        "- All models were evaluated with max_input_length = 384\n"
        "- Latency measured on a single NVIDIA T4 GPU\n"
        "- Accuracy measured on the DocuMind QA benchmark (100 questions)\n"
        "- DistilBERT is the current production model\n"
        "- DeBERTa-large achieves the highest accuracy but at 3.9x latency\n\n"
        "Recommendation:\n"
        "For production use, DeBERTa-base offers the best accuracy-latency "
        "tradeoff.  However, the DistilBERT model is sufficient for the "
        "current workload and has lower resource requirements.\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# PDF builders — new Phase 4B documents
# ---------------------------------------------------------------------------

def _pdf_text(page, x, y, text, size=11.0, bold=False):
    font = fitz.Font("hebo" if bold else "helv")
    writer = fitz.TextWriter(page.rect)
    writer.append((x, y), text, font=font, fontsize=size)
    writer.write_text(page)


def _build_multi_page_report(path: Path) -> None:
    """4-page PDF with sections, tables, and lists."""
    doc = fitz.open()

    # Page 1: Title and introduction
    p1 = doc.new_page(width=595, height=842)
    _pdf_text(p1, 50, 60, "Quarterly Performance Report", size=16, bold=True)
    _pdf_text(p1, 50, 90, "Prepared by the Analytics Team")
    _pdf_text(p1, 50, 120, "")
    _pdf_text(p1, 50, 140, "Executive Summary")
    _pdf_text(p1, 50, 160, "This report covers Q3 2025 performance metrics")
    _pdf_text(p1, 50, 180, "across all service components.  Key findings")
    _pdf_text(p1, 50, 200, "include a 35% reduction in query latency and")
    _pdf_text(p1, 50, 220, "an improvement in answer accuracy from 78% to")
    _pdf_text(p1, 50, 240, "85% following the structure-v2 chunking upgrade.")

    # Page 2: Metrics table
    p2 = doc.new_page(width=595, height=842)
    _pdf_text(p2, 50, 60, "Performance Metrics", size=14, bold=True)
    _pdf_text(p2, 50, 90, "Metric               | Before  | After   | Change")
    _pdf_text(p2, 50, 110, "---------------------|---------|---------|--------")
    _pdf_text(p2, 50, 130, "Query Latency (ms)  | 120     | 78      | -35%")
    _pdf_text(p2, 50, 150, "Ingestion Time (ms) | 7359    | 1360    | -82%")
    _pdf_text(p2, 50, 170, "Recall@5            | 0.897   | 1.000   | +12%")
    _pdf_text(p2, 50, 190, "Answer Accuracy     | 0.783   | 0.851   | +9%")
    _pdf_text(p2, 50, 210, "Chunk Count         | 79      | 42      | -47%")
    _pdf_text(p2, 50, 240, "")
    _pdf_text(p2, 50, 260, "The structure-v2 chunker significantly improved")
    _pdf_text(p2, 50, 280, "all metrics while reducing resource usage.")

    # Page 3: Component analysis
    p3 = doc.new_page(width=595, height=842)
    _pdf_text(p3, 50, 60, "Component Analysis", size=14, bold=True)
    _pdf_text(p3, 50, 90, "The following components were analysed:")
    _pdf_text(p3, 50, 120, "1. Document extraction: 100% accuracy on synthetic")
    _pdf_text(p3, 50, 140, "   documents.  Real-world accuracy unknown.")
    _pdf_text(p3, 50, 170, "2. Embedding model: all-MiniLM-L6-v2 produces")
    _pdf_text(p3, 50, 190, "   384-dimensional embeddings with 256 token limit.")
    _pdf_text(p3, 50, 220, "3. Retrieval: pgvector cosine similarity search")
    _pdf_text(p3, 50, 240, "   achieves perfect recall on the evaluation corpus.")
    _pdf_text(p3, 50, 270, "4. QA model: DistilBERT with 66M parameters.")
    _pdf_text(p3, 50, 290, "   28.2% QA_EXTRACT failure rate on table/list")
    _pdf_text(p3, 50, 310, "   questions due to training data mismatch.")

    # Page 4: Recommendations
    p4 = doc.new_page(width=595, height=842)
    _pdf_text(p4, 50, 60, "Recommendations", size=14, bold=True)
    _pdf_text(p4, 50, 90, "Based on the analysis, we recommend:")
    _pdf_text(p4, 50, 120, "1. Expand the evaluation corpus to 100+ questions")
    _pdf_text(p4, 50, 140, "   across 22+ documents.")
    _pdf_text(p4, 50, 170, "2. Retrain the QA model with table and list")
    _pdf_text(p4, 50, 190, "   training data to address QA_EXTRACT failures.")
    _pdf_text(p4, 50, 220, "3. Promote structure-v2 to production default")
    _pdf_text(p4, 50, 240, "   pending broader validation.")
    _pdf_text(p4, 50, 270, "4. Implement observability and structured")
    _pdf_text(p4, 50, 290, "   metrics collection for production monitoring.")
    _pdf_text(p4, 50, 320, "Estimated timeline: Q1 2026 for corpus expansion,")
    _pdf_text(p4, 50, 340, "Q2 2026 for QA model retraining.")

    doc.save(str(path))
    doc.close()


# ---------------------------------------------------------------------------
# Corpus assembly
# ---------------------------------------------------------------------------

def build_phase4b_corpus() -> list[CorpusDoc]:
    """Return the Phase 4B expanded corpus.

    Includes all Phase 3F documents (12) plus new Phase 4B documents (10),
    for a total of 22 documents.
    """
    # Import Phase 3F corpus
    from tests.phase3d_corpus import build_corpus as _build_p3f

    p3f_docs = _build_p3f()

    # Phase 4B new documents
    new_docs = [
        CorpusDoc(
            name="tables_medium.docx",
            file_type="docx",
            builder=_build_tables_medium,
            notes="10-row, 4-column table with header.  Tests row/column lookup.",
            questions=[
                Question("tm_1", "What is the accuracy of Config D?",
                         expected_answer="91.3 percent", evidence=("Config D", "91.3"),
                         kind="table"),
                Question("tm_2", "Which configuration has the highest accuracy?",
                         expected_answer="Config G", evidence=("Config G", "93.2"),
                         kind="table"),
                Question("tm_3", "What is the latency of Config F?",
                         expected_answer="85 milliseconds", evidence=("Config F", "85"),
                         kind="table"),
                Question("tm_4", "How much memory does Config D use?",
                         expected_answer="640 MB", evidence=("Config D", "640"),
                         kind="table"),
                Question("tm_5", "Which configuration has the lowest latency?",
                         expected_answer="Config F", evidence=("Config F", "85"),
                         kind="table"),
            ],
        ),
        CorpusDoc(
            name="tables_nested.docx",
            file_type="docx",
            builder=_build_tables_nested,
            notes="Multiple tables in one document.  Tests cross-table questions.",
            questions=[
                Question("tn_1", "What is the temperature at Alpha-2?",
                         expected_answer="19.8 degrees", evidence=("Alpha-2", "19.8"),
                         kind="table"),
                Question("tn_2", "Which station has the highest humidity in Region Beta?",
                         expected_answer="Beta-3", evidence=("Beta-3", "85%"),
                         kind="table"),
                Question("tn_3", "What is the temperature difference between Alpha-1 and Beta-1?",
                         expected_answer="4.2 degrees", evidence=("22.5", "18.3"),
                         kind="table"),
                Question("tn_4", "Which region had consistently higher humidity?",
                         expected_answer="Region Beta", evidence=("Region Beta", "higher humidity"),
                         kind="section_specific"),
            ],
        ),
        CorpusDoc(
            name="lists_nested.docx",
            file_type="docx",
            builder=_build_lists_nested,
            notes="Nested bullet and numbered lists.",
            questions=[
                Question("ln_1", "What Python version is required?",
                         expected_answer="3.10", evidence=("Python 3.10",),
                         kind="list"),
                Question("ln_2", "What is the third installation step?",
                         expected_answer="Configure the database connection in .env",
                         evidence=("Configure the database connection",),
                         kind="list"),
                Question("ln_3", "What should you check if the database connection is refused?",
                         expected_answer="PostgreSQL is running",
                         evidence=("Database connection refused", "PostgreSQL"),
                         kind="list"),
                Question("ln_4", "How many prerequisites are listed?",
                         expected_answer="4", evidence=("Python", "PostgreSQL", "RAM", "API"),
                         kind="list"),
            ],
        ),
        CorpusDoc(
            name="lists_long.docx",
            file_type="docx",
            builder=_build_lists_long,
            notes="Long list with 12 items.",
            questions=[
                Question("ll_1", "What is the sixth component in the list?",
                         expected_answer="JWT authentication module",
                         evidence=("JWT authentication",),
                         kind="list"),
                Question("ll_2", "Which component handles HTTP requests?",
                         expected_answer="FastAPI web server",
                         evidence=("FastAPI web server",),
                         kind="list"),
                Question("ll_3", "What is the last component listed?",
                         expected_answer="Health check endpoint",
                         evidence=("Health check endpoint",),
                         kind="list"),
                Question("ll_4", "How many components are listed?",
                         expected_answer="12", evidence=("FastAPI", "PostgreSQL", "Health check"),
                         kind="list"),
            ],
        ),
        CorpusDoc(
            name="technical_manual.docx",
            file_type="docx",
            builder=_build_technical_manual,
            notes="Mixed headings, tables, lists, paragraphs.",
            questions=[
                Question("tm_manual_1", "What is the nominal voltage?",
                         expected_answer="5.0 V", evidence=("Voltage", "5.0 V"),
                         kind="table"),
                Question("tm_manual_2", "What tolerance is specified for current?",
                         expected_answer="±0.05 A", evidence=("Current", "2.5 A", "0.05"),
                         kind="table"),
                Question("tm_manual_3", "What is the fourth calibration step?",
                         expected_answer="Record the measured voltage on the oscilloscope",
                         evidence=("Record the measured voltage",),
                         kind="list"),
                Question("tm_manual_4", "How long is the calibration valid?",
                         expected_answer="12 months", evidence=("12 months",),
                         kind="factual"),
                Question("tm_manual_5", "What equipment is required for calibration?",
                         expected_answer="Meridian calibration kit",
                         evidence=("Meridian calibration kit",),
                         kind="list"),
            ],
        ),
        CorpusDoc(
            name="research_paper.txt",
            file_type="txt",
            builder=_build_research_paper,
            notes="Academic-style prose with sections.",
            questions=[
                Question("rp_1", "What accuracy does the Falcon estimator achieve on MNIST?",
                         expected_answer="98.2 percent", evidence=("98.2%", "MNIST"),
                         kind="factual"),
                Question("rp_2", "What is the improvement over baseline on CIFAR-10?",
                         expected_answer="3.3 percentage points",
                         evidence=("87.4%", "84.1%"),
                         kind="table"),
                Question("rp_3", "What sparsity level is used in sparse coding?",
                         expected_answer="20", evidence=("sparsity level k = 20",),
                         kind="factual"),
                Question("rp_4", "How many iterations does dictionary learning use?",
                         expected_answer="1000", evidence=("1000 iterations",),
                         kind="factual"),
                Question("rp_5", "What is the baseline accuracy on ImageNet?",
                         expected_answer="69.5 percent", evidence=("69.5%",),
                         kind="factual"),
            ],
        ),
        CorpusDoc(
            name="faq_document.txt",
            file_type="txt",
            builder=_build_faq_document,
            notes="Q&A format document.",
            questions=[
                Question("faq_1", "What file formats does DocuMind support?",
                         expected_answer="PDF, DOCX, and TXT",
                         evidence=("PDF, DOCX, and TXT",),
                         kind="factual"),
                Question("faq_2", "What embedding model does DocuMind use?",
                         expected_answer="all-MiniLM-L6-v2",
                         evidence=("all-MiniLM-L6-v2",),
                         kind="factual"),
                Question("faq_3", "What is the default maximum upload size?",
                         expected_answer="50 MB", evidence=("50 MB",),
                         kind="factual"),
                Question("faq_4", "What authentication method is used?",
                         expected_answer="JWT tokens", evidence=("JWT tokens",),
                         kind="factual"),
            ],
        ),
        CorpusDoc(
            name="multi_page_report.pdf",
            file_type="pdf",
            builder=_build_multi_page_report,
            notes="4-page PDF with sections, tables, and lists.",
            questions=[
                Question("mpr_1", "What was the reduction in query latency?",
                         expected_answer="35%", evidence=("35%", "query latency"),
                         kind="factual"),
                Question("mpr_2", "What is the chunk count after the upgrade?",
                         expected_answer="42", evidence=("Chunk Count", "42"),
                         kind="table"),
                Question("mpr_3", "When is the corpus expansion estimated?",
                         expected_answer="Q1 2026", evidence=("Q1 2026",),
                         kind="factual"),
                Question("mpr_4", "What is the QA_EXTRACT failure rate?",
                         expected_answer="28.2 percent", evidence=("28.2%", "QA_EXTRACT"),
                         kind="factual"),
                Question("mpr_5", "How many parameters does the QA model have?",
                         expected_answer="66 million", evidence=("66M", "parameters"),
                         kind="factual"),
            ],
        ),
        CorpusDoc(
            name="timeline_data.txt",
            file_type="txt",
            builder=_build_timeline_data,
            notes="Dates and events timeline.",
            questions=[
                Question("tl_1", "When was the first prototype completed?",
                         expected_answer="March 2024", evidence=("March 2024", "prototype"),
                         kind="factual"),
                Question("tl_2", "When was version 1.0 released?",
                         expected_answer="December 2024",
                         evidence=("December 2024", "Version 1.0"),
                         kind="factual"),
                Question("tl_3", "What was the initial QA model accuracy?",
                         expected_answer="72%", evidence=("72%", "initial accuracy"),
                         kind="factual"),
                Question("tl_4", "When is the QA model retraining scheduled?",
                         expected_answer="March 2026",
                         evidence=("March 2026", "retraining"),
                         kind="factual"),
            ],
        ),
        CorpusDoc(
            name="mixed_structured.docx",
            file_type="docx",
            builder=_build_mixed_structured,
            notes="Tables + lists + prose + headings.",
            questions=[
                Question("ms_1", "What was the revenue in August?",
                         expected_answer="1.4 million", evidence=("August", "1.4 million"),
                         kind="table"),
                Question("ms_2", "Which month had negative growth?",
                         expected_answer="September", evidence=("September", "-3.2%"),
                         kind="table"),
                Question("ms_3", "What was the first key achievement?",
                         expected_answer="new document processing pipeline",
                         evidence=("new document processing pipeline",),
                         kind="list"),
                Question("ms_4", "What caused the September revenue decline?",
                         expected_answer="seasonal factors",
                         evidence=("seasonal factors",),
                         kind="factual"),
                Question("ms_5", "What is the first next quarter goal?",
                         expected_answer="1.5 million per month",
                         evidence=("1.5 million per month",),
                         kind="list"),
            ],
        ),
        CorpusDoc(
            name="glossary.txt",
            file_type="txt",
            builder=_build_glossary,
            notes="Definitions and terms.",
            questions=[
                Question("gl_1", "What is abstention?",
                         expected_answer="withhold an answer",
                         evidence=("withhold an answer",),
                         kind="factual"),
                Question("gl_2", "What is the current context window size?",
                         expected_answer="384 tokens", evidence=("384 tokens",),
                         kind="factual"),
                Question("gl_3", "What does CTX_TRUNC stand for?",
                         expected_answer="context truncation",
                         evidence=("CTX_TRUNC", "context"),
                         kind="factual"),
                Question("gl_4", "What is MRR?",
                         expected_answer="Mean Reciprocal Rank",
                         evidence=("Mean Reciprocal Rank",),
                         kind="factual"),
            ],
        ),
        CorpusDoc(
            name="comparison_data.txt",
            file_type="txt",
            builder=_build_comparison_data,
            notes="ASCII table format with comparisons.",
            questions=[
                Question("cd_1", "What is the accuracy of DeBERTa-large?",
                         expected_answer="87.9 percent", evidence=("DeBERTa-large", "87.9%"),
                         kind="table"),
                Question("cd_2", "Which model has the fewest parameters?",
                         expected_answer="DistilBERT", evidence=("DistilBERT", "66M"),
                         kind="table"),
                Question("cd_3", "What is the latency of BERT-large?",
                         expected_answer="65 ms", evidence=("BERT-large", "65ms"),
                         kind="table"),
                Question("cd_4", "What is the recommended model for production?",
                         expected_answer="DeBERTa-base",
                         evidence=("DeBERTa-base", "best accuracy-latency"),
                         kind="factual"),
            ],
        ),
    ]

    return p3f_docs + new_docs


def build_phase4b_unanswerable() -> list[Question]:
    """Unanswerable questions for Phase 4B evaluation."""
    from tests.phase3d_corpus import unanswerable_questions as _p3f_unsup

    p3f_unsup = _p3f_unsup()

    new_unsup = [
        Question("un_4", "What is the population of Tokyo?", answerable=False,
                 kind="unsupported"),
        Question("un_5", "What is the chemical formula for glucose?",
                 answerable=False, kind="unsupported"),
        Question("un_6", "How many planets are in the solar system?",
                 answerable=False, kind="unsupported"),
        Question("un_7", "What year was the internet invented?",
                 answerable=False, kind="unsupported"),
        Question("un_8", "What is the fastest land animal?",
                 answerable=False, kind="unsupported"),
        Question("un_9", "What is the boiling point of mercury?",
                 answerable=False, kind="unsupported"),
        Question("un_10", "How many chromosomes do humans have?",
                 answerable=False, kind="unsupported"),
    ]

    return list(p3f_unsup) + new_unsup


def get_all_phase4b_questions() -> list[Question]:
    """Return all questions (answerable + unanswerable)."""
    corpus = build_phase4b_corpus()
    unsup = build_phase4b_unanswerable()
    return [q for doc in corpus for q in doc.questions] + unsup
