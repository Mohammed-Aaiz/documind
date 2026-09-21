"""Phase 4D — Training Data Generator.

Generates targeted QA training examples to address the gaps identified
in Phase 4A/4B/4C:
  - Table cell extraction (0% training coverage)
  - List item extraction (0% training coverage)
  - Numeric/unit extraction (~5% training coverage)
  - Date extraction (limited)
  - Section-aware questions
  - Unanswerable questions

Every example is traceable with:
  - example_id
  - source (dataset name)
  - question_kind
  - document_id
  - question
  - context
  - answer
  - answer_start
  - answer_end

Training examples are SYNTHETIC but structurally justified.
They are NOT fabricated from evaluation data.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TrainingExample:
    """One training example for extractive QA."""
    example_id: str
    source: str
    document_id: str
    question: str
    context: str
    answer: str
    answer_start: int
    answer_end: int
    question_kind: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Table training data generator
# ---------------------------------------------------------------------------

_TABLE_TEMPLATES = [
    # (headers, rows, question_template, answer_idx_row, answer_idx_col)
    {
        "headers": ["Method", "Accuracy", "Latency (ms)"],
        "rows": [
            ["Logistic Regression", "78.5%", "12"],
            ["Random Forest", "82.1%", "45"],
            ["SVM", "85.3%", "28"],
            ["Neural Network", "91.7%", "150"],
            ["Gradient Boosting", "89.2%", "35"],
        ],
        "questions": [
            ("What accuracy does the SVM achieve?", "85.3%", "SVM"),
            ("What is the latency of the Neural Network?", "150", "Neural Network"),
            ("Which method achieves the highest accuracy?", "Neural Network", "highest accuracy"),
            ("What is the accuracy of Logistic Regression?", "78.5%", "Logistic Regression"),
            ("What latency does Random Forest have?", "45", "Random Forest"),
        ],
        "doc_id": "table_benchmarks",
    },
    {
        "headers": ["Station", "Temperature", "Humidity", "Pressure"],
        "rows": [
            ["Alpha-1", "22.5°C", "65%", "1013 hPa"],
            ["Alpha-2", "19.8°C", "72%", "1015 hPa"],
            ["Alpha-3", "24.1°C", "58%", "1011 hPa"],
            ["Beta-1", "18.3°C", "80%", "1018 hPa"],
            ["Beta-2", "21.7°C", "68%", "1014 hPa"],
            ["Beta-3", "16.9°C", "85%", "1020 hPa"],
        ],
        "questions": [
            ("What is the temperature at Alpha-2?", "19.8°C", "Alpha-2"),
            ("Which station has the highest humidity?", "Beta-3", "highest humidity"),
            ("What is the pressure at Beta-1?", "1018 hPa", "Beta-1"),
            ("What is the humidity at Alpha-3?", "58%", "Alpha-3"),
            ("Which station has the lowest temperature?", "Beta-3", "lowest temperature"),
        ],
        "doc_id": "table_weather",
    },
    {
        "headers": ["Quarter", "Revenue", "Expenses", "Profit"],
        "rows": [
            ["Q1 2025", "1.2 million", "0.8 million", "0.4 million"],
            ["Q2 2025", "1.5 million", "0.9 million", "0.6 million"],
            ["Q3 2025", "1.1 million", "0.85 million", "0.25 million"],
            ["Q4 2025", "1.8 million", "1.0 million", "0.8 million"],
        ],
        "questions": [
            ("What was the revenue in Q2 2025?", "1.5 million", "Q2 2025"),
            ("Which quarter had the highest profit?", "Q4 2025", "highest profit"),
            ("What were the expenses in Q3 2025?", "0.85 million", "Q3 2025"),
            ("What was the profit in Q1 2025?", "0.4 million", "Q1 2025"),
            ("Which quarter had the lowest revenue?", "Q3 2025", "lowest revenue"),
        ],
        "doc_id": "table_financials",
    },
    {
        "headers": ["Model", "Parameters", "Accuracy", "Inference Time"],
        "rows": [
            ["BERT-base", "110M", "82.1%", "28 ms"],
            ["BERT-large", "340M", "85.7%", "65 ms"],
            ["DistilBERT", "66M", "78.3%", "15 ms"],
            ["RoBERTa-base", "125M", "81.5%", "25 ms"],
            ["DeBERTa-base", "86M", "84.2%", "22 ms"],
            ["DeBERTa-large", "304M", "87.9%", "58 ms"],
        ],
        "questions": [
            ("How many parameters does BERT-base have?", "110M", "BERT-base"),
            ("What is the accuracy of DeBERTa-large?", "87.9%", "DeBERTa-large"),
            ("Which model has the fastest inference time?", "DistilBERT", "fastest"),
            ("What is the inference time of BERT-large?", "65 ms", "BERT-large"),
            ("How many parameters does DistilBERT have?", "66M", "DistilBERT"),
        ],
        "doc_id": "table_models",
    },
    {
        "headers": ["Component", "Status", "Priority", "Owner"],
        "rows": [
            ["Authentication", "Complete", "High", "Alice"],
            ["Database Migration", "In Progress", "High", "Bob"],
            ["API Gateway", "Not Started", "Medium", "Charlie"],
            ["Monitoring", "In Progress", "Low", "Diana"],
            ["Load Testing", "Not Started", "Medium", "Alice"],
        ],
        "questions": [
            ("Who owns the Authentication component?", "Alice", "Authentication"),
            ("What is the status of the Database Migration?", "In Progress", "Database Migration"),
            ("Which components are owned by Alice?", "Authentication and Load Testing", "Alice"),
            ("What is the priority of Monitoring?", "Low", "Monitoring"),
            ("Which component has not been started?", "API Gateway and Load Testing", "Not Started"),
        ],
        "doc_id": "table_projects",
    },
]


def _serialize_table(headers: list[str], rows: list[list[str]]) -> str:
    """Serialize a table as pipe-delimited text (matching production format)."""
    lines = [" | ".join(headers)]
    for row in rows:
        lines.append(" | ".join(row))
    return "\n".join(lines)


def _generate_table_examples() -> list[TrainingExample]:
    """Generate training examples from table templates."""
    examples = []
    for template in _TABLE_TEMPLATES:
        context = _serialize_table(template["headers"], template["rows"])
        for q_text, answer, anchor in template["questions"]:
            # Find the answer in context
            start = context.lower().find(answer.lower())
            if start == -1:
                # Try finding just the anchor
                start = context.lower().find(anchor.lower())
                if start == -1:
                    continue
                end = start + len(anchor)
            else:
                end = start + len(answer)

            ex_id = f"train_table_{template['doc_id']}_{hashlib.md5(q_text.encode()).hexdigest()[:8]}"
            examples.append(TrainingExample(
                example_id=ex_id,
                source="synthetic_table",
                document_id=template["doc_id"],
                question=q_text,
                context=context,
                answer=answer,
                answer_start=start,
                answer_end=end,
                question_kind="table_cell",
                metadata={"table_headers": template["headers"], "anchor": anchor},
            ))
    return examples


# ---------------------------------------------------------------------------
# List training data generator
# ---------------------------------------------------------------------------

_LIST_TEMPLATES = [
    {
        "heading": "Installation Steps",
        "items": [
            "Clone the repository from the main branch",
            "Install dependencies using pip install -r requirements.txt",
            "Configure the database connection in .env",
            "Run the migration script: alembic upgrade head",
            "Start the server with: python start_server.py",
            "Verify the health check at /api/health",
        ],
        "questions": [
            ("What is the first installation step?", "Clone the repository", "first"),
            ("What is the third installation step?", "Configure the database connection", "third"),
            ("What is the last installation step?", "Verify the health check", "last"),
            ("What command starts the server?", "python start_server.py", "start"),
            ("How many installation steps are there?", "6", "how many"),
        ],
        "doc_id": "list_installation",
    },
    {
        "heading": "Server Components",
        "items": [
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
        ],
        "questions": [
            ("What is the sixth component?", "JWT authentication module", "sixth"),
            ("Which component handles HTTP requests?", "FastAPI web server", "HTTP requests"),
            ("What is the last component listed?", "Document chunker", "last"),
            ("How many components are listed?", "10", "how many"),
            ("What component manages embeddings?", "Sentence transformer model", "embeddings"),
        ],
        "doc_id": "list_components",
    },
    {
        "heading": "Prerequisites",
        "items": [
            "Python 3.10 or later",
            "PostgreSQL 14 or later",
            "At least 8 GB RAM",
            "Valid API credentials",
            "Git version control",
        ],
        "questions": [
            ("What Python version is required?", "3.10", "Python"),
            ("What database version is needed?", "14", "PostgreSQL"),
            ("How much RAM is required?", "8 GB", "RAM"),
            ("What is the second prerequisite?", "PostgreSQL 14 or later", "second"),
            ("What is the last prerequisite?", "Git version control", "last"),
        ],
        "doc_id": "list_prerequisites",
    },
    {
        "heading": "Troubleshooting",
        "items": [
            "Database connection refused: check PostgreSQL is running",
            "Port 8000 in use: change the port in start_server.py",
            "Model not found: ensure models/documind-qa directory exists",
            "Authentication failed: verify JWT token is valid",
            "Slow response: check database connection pool size",
        ],
        "questions": [
            ("What should you check if the database connection is refused?", "PostgreSQL is running", "refused"),
            ("How do you fix port 8000 in use?", "change the port in start_server.py", "Port 8000"),
            ("What does model not found mean?", "ensure models/documind-qa directory exists", "Model not found"),
            ("What is the third troubleshooting item?", "Model not found: ensure models/documind-qa directory exists", "third"),
            ("What should you check for slow response?", "database connection pool size", "slow response"),
        ],
        "doc_id": "list_troubleshooting",
    },
]


def _serialize_list(items: list[str], heading: str = "") -> str:
    """Serialize a list as newline-delimited items (matching production format)."""
    lines = []
    if heading:
        lines.append(heading)
    for item in items:
        lines.append(item)
    return "\n".join(lines)


def _generate_list_examples() -> list[TrainingExample]:
    """Generate training examples from list templates."""
    examples = []
    for template in _LIST_TEMPLATES:
        context = _serialize_list(template["items"], template["heading"])
        for q_text, answer, anchor in template["questions"]:
            start = context.lower().find(answer.lower())
            if start == -1:
                start = context.lower().find(anchor.lower())
                if start == -1:
                    continue
                end = start + len(anchor)
            else:
                end = start + len(answer)

            ex_id = f"train_list_{template['doc_id']}_{hashlib.md5(q_text.encode()).hexdigest()[:8]}"
            examples.append(TrainingExample(
                example_id=ex_id,
                source="synthetic_list",
                document_id=template["doc_id"],
                question=q_text,
                context=context,
                answer=answer,
                answer_start=start,
                answer_end=end,
                question_kind="list_item",
                metadata={"item_count": len(template["items"]), "anchor": anchor},
            ))
    return examples


# ---------------------------------------------------------------------------
# Numeric/date/unit training data generator
# ---------------------------------------------------------------------------

_NUMERIC_TEMPLATES = [
    {
        "context": "The experiment measured a transport rate of 1.4 kilograms per metre per day. "
                   "This value was consistent across all three measurement sites.",
        "questions": [
            ("What was the transport rate?", "1.4 kilograms per metre per day"),
            ("What unit was used for the transport rate?", "kilograms per metre per day"),
        ],
        "doc_id": "numeric_transport",
    },
    {
        "context": "The device operates at a frequency of 2.4 GHz and a power output of 100 milliwatts. "
                   "The maximum range is 50 metres in open space.",
        "questions": [
            ("What is the operating frequency?", "2.4 GHz"),
            ("What is the power output?", "100 milliwatts"),
            ("What is the maximum range?", "50 metres"),
        ],
        "doc_id": "numeric_device",
    },
    {
        "context": "The project started on March 15, 2024 and was completed on September 30, 2024. "
                   "The total duration was approximately 6.5 months.",
        "questions": [
            ("When did the project start?", "March 15, 2024"),
            ("When was the project completed?", "September 30, 2024"),
            ("How long was the project?", "6.5 months"),
        ],
        "doc_id": "numeric_dates",
    },
    {
        "context": "The protein concentration was measured at 2.5 milligrams per millilitre. "
                   "After dilution, the concentration dropped to 0.5 milligrams per millilitre.",
        "questions": [
            ("What was the initial protein concentration?", "2.5 milligrams per millilitre"),
            ("What was the concentration after dilution?", "0.5 milligrams per millilitre"),
        ],
        "doc_id": "numeric_protein",
    },
    {
        "context": "The system achieved an accuracy of 94.7 percent on the test set. "
                   "The precision was 92.3 percent and the recall was 96.1 percent.",
        "questions": [
            ("What accuracy did the system achieve?", "94.7 percent"),
            ("What was the precision?", "92.3 percent"),
            ("What was the recall?", "96.1 percent"),
        ],
        "doc_id": "numeric_metrics",
    },
]


def _generate_numeric_examples() -> list[TrainingExample]:
    """Generate training examples for numeric/date/unit extraction."""
    examples = []
    for template in _NUMERIC_TEMPLATES:
        for q_text, answer in template["questions"]:
            start = template["context"].lower().find(answer.lower())
            if start == -1:
                continue
            end = start + len(answer)

            ex_id = f"train_numeric_{template['doc_id']}_{hashlib.md5(q_text.encode()).hexdigest()[:8]}"
            examples.append(TrainingExample(
                example_id=ex_id,
                source="synthetic_numeric",
                document_id=template["doc_id"],
                question=q_text,
                context=template["context"],
                answer=answer,
                answer_start=start,
                answer_end=end,
                question_kind="numeric",
                metadata={},
            ))
    return examples


# ---------------------------------------------------------------------------
# Unanswerable training data generator
# ---------------------------------------------------------------------------

_UNANSWERABLE_TEMPLATES = [
    {
        "context": "The system supports PDF, DOCX, and TXT file formats. Maximum upload size is 50 MB.",
        "question": "What image formats are supported?",
        "doc_id": "unanswerable_formats",
    },
    {
        "context": "The server runs on port 8000 by default. Authentication uses JWT tokens.",
        "question": "What is the database password?",
        "doc_id": "unanswerable_config",
    },
    {
        "context": "The model achieves 85% accuracy on the benchmark. Training took 3 hours on a T4 GPU.",
        "question": "What is the model's architecture?",
        "doc_id": "unanswerable_model",
    },
    {
        "context": "The project uses Python 3.10, FastAPI, and PostgreSQL. No external AI services are used.",
        "question": "What cloud provider is used for deployment?",
        "doc_id": "unanswerable_infra",
    },
]


def _generate_unanswerable_examples() -> list[TrainingExample]:
    """Generate unanswerable training examples (no valid span)."""
    examples = []
    for template in _UNANSWERABLE_TEMPLATES:
        ex_id = f"train_unanswerable_{template['doc_id']}_{hashlib.md5(template['question'].encode()).hexdigest()[:8]}"
        examples.append(TrainingExample(
            example_id=ex_id,
            source="synthetic_unanswerable",
            document_id=template["doc_id"],
            question=template["question"],
            context=template["context"],
            answer="",  # no answer
            answer_start=0,
            answer_end=0,
            question_kind="unanswerable",
            metadata={"is_impossible": True},
        ))
    return examples


# ---------------------------------------------------------------------------
# Prose training data (SQuAD-like synthetic)
# ---------------------------------------------------------------------------

_PROSE_TEMPLATES = [
    {
        "context": "The DocuMind platform was designed to help researchers quickly find relevant "
                   "information in large document collections. It uses a retrieval-augmented "
                   "generation approach, combining vector search with extractive question answering. "
                   "The system processes documents into chunks, embeds them using sentence transformers, "
                   "and stores them in a pgvector database for efficient similarity search.",
        "questions": [
            ("What approach does DocuMind use?", "retrieval-augmented generation"),
            ("How are documents processed?", "into chunks"),
            ("What embedding model is used?", "sentence transformers"),
            ("Where are embeddings stored?", "pgvector database"),
        ],
        "doc_id": "prose_platform",
    },
    {
        "context": "The calibration procedure requires the Meridian calibration kit (MC-200), "
                   "a reference signal generator, and an oscilloscope with 100 MHz bandwidth. "
                   "Set the output to 5.0 volts at 1000 hertz and connect to input channel A. "
                   "Record the measured voltage and compare against the nominal value of 5.0 V.",
        "questions": [
            ("What kit is required?", "Meridian calibration kit (MC-200)"),
            ("What bandwidth is needed?", "100 MHz"),
            ("What voltage should be set?", "5.0 volts"),
            ("What frequency should be used?", "1000 hertz"),
        ],
        "doc_id": "prose_calibration",
    },
]


def _generate_prose_examples() -> list[TrainingExample]:
    """Generate SQuAD-like synthetic prose QA examples."""
    examples = []
    for template in _PROSE_TEMPLATES:
        for q_text, answer in template["questions"]:
            start = template["context"].lower().find(answer.lower())
            if start == -1:
                continue
            end = start + len(answer)

            ex_id = f"train_prose_{template['doc_id']}_{hashlib.md5(q_text.encode()).hexdigest()[:8]}"
            examples.append(TrainingExample(
                example_id=ex_id,
                source="synthetic_prose",
                document_id=template["doc_id"],
                question=q_text,
                context=template["context"],
                answer=answer,
                answer_start=start,
                answer_end=end,
                question_kind="factual",
                metadata={},
            ))
    return examples


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_all_training_data() -> list[TrainingExample]:
    """Generate the complete Phase 4D training dataset."""
    examples = []
    examples.extend(_generate_table_examples())
    examples.extend(_generate_list_examples())
    examples.extend(_generate_numeric_examples())
    examples.extend(_generate_unanswerable_examples())
    examples.extend(_generate_prose_examples())
    return examples


def generate_experiment_datasets(
    seed: int = 42,
    train_ratio: float = 0.8,
    val_ratio: float = 0.2,
) -> dict[str, list[TrainingExample]]:
    """Generate train/validation split for experiments.

    CRITICAL: No evaluation document appears in training data.
    All training data uses dedicated document_ids not in the eval corpus.
    """
    all_examples = generate_all_training_data()

    # Separate by kind for stratified splitting
    rng = random.Random(seed)
    rng.shuffle(all_examples)

    split_idx = int(len(all_examples) * train_ratio)
    train = all_examples[:split_idx]
    val = all_examples[split_idx:]

    return {"train": train, "val": val}


def save_dataset(examples: list[TrainingExample], path: Path) -> None:
    """Save a dataset to JSON Lines format."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex.to_dict(), ensure_ascii=False) + "\n")


def load_dataset(path: Path) -> list[TrainingExample]:
    """Load a dataset from JSON Lines format."""
    examples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data = json.loads(line)
                examples.append(TrainingExample(**data))
    return examples


def dataset_stats(examples: list[TrainingExample]) -> dict:
    """Compute statistics for a dataset."""
    from collections import Counter
    kind_counts = Counter(ex.question_kind for ex in examples)
    source_counts = Counter(ex.source for ex in examples)
    doc_counts = Counter(ex.document_id for ex in examples)
    answer_lengths = [len(ex.answer) for ex in examples if ex.answer]
    context_lengths = [len(ex.context) for ex in examples]

    return {
        "total_examples": len(examples),
        "by_kind": dict(kind_counts),
        "by_source": dict(source_counts),
        "by_document": dict(doc_counts),
        "answer_length_mean": sum(answer_lengths) / len(answer_lengths) if answer_lengths else 0,
        "answer_length_max": max(answer_lengths) if answer_lengths else 0,
        "context_length_mean": sum(context_lengths) / len(context_lengths) if context_lengths else 0,
        "context_length_max": max(context_lengths) if context_lengths else 0,
        "unanswerable_count": sum(1 for ex in examples if not ex.answer),
    }


def compute_dataset_hash(examples: list[TrainingExample]) -> str:
    """Compute a deterministic hash of the dataset for provenance."""
    data = json.dumps([ex.to_dict() for ex in examples], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(data.encode()).hexdigest()[:16]
