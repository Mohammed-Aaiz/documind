"""
Phase 4F.5-D: Build evaluation benchmark from frozen dataset.

Creates a balanced, versioned evaluation benchmark with:
- Document-level holdout from training
- Meaningful unanswerable set
- Category balance
- Gold span validation
- Tier classification
"""
import hashlib
import json
import os
import random
import re
import sys
import io
from collections import Counter, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SEED = 42
OUT = "backend/phase4f/phase4f_5d"
BENCH = f"{OUT}/benchmark"
ANALYSIS = f"{OUT}/analysis"

# ─── Load data ────────────────────────────────────────────────────
examples = []
with open("backend/phase4f/dataset/training_data_v3_1.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line: examples.append(json.loads(line))

# Load current split
derived = {}
with open("backend/phase4f/phase4f_5/dataset/derived_dataset.jsonl") as f:
    for line in f:
        ex = json.loads(line.strip())
        derived[ex["example_id"]] = ex

# Identify training documents (from current split)
train_docs = set()
for ex in derived.values():
    if ex.get("split") == "train":
        train_docs.add(ex["document_id"])

print(f"Training documents (excluded from benchmark): {sorted(train_docs)}")

# ─── Select benchmark documents ──────────────────────────────────
# All documents NOT in training
all_docs = defaultdict(list)
for ex in examples:
    all_docs[ex["document_id"]].append(ex)

bench_docs = {doc: exs for doc, exs in all_docs.items() if doc not in train_docs}
print(f"\nAvailable benchmark documents: {len(bench_docs)}")
for doc, exs in sorted(bench_docs.items()):
    cats = Counter(e["question_kind"] for e in exs)
    print(f"  {doc}: {len(exs)} examples, {dict(cats)}")

# ─── Collect all candidate examples ──────────────────────────────
# All examples from non-training documents
candidates = []
for doc, exs in bench_docs.items():
    candidates.extend(exs)

# Also include ALL unanswerable examples (they're standalone)
unanswerable_all = [e for e in examples if e["question_kind"] == "UNANSWERABLE"]
answerable_candidates = [e for e in candidates if e["question_kind"] != "UNANSWERABLE"]

print(f"\nCandidate pool: {len(candidates)} total, {len(answerable_candidates)} answerable, {len(unanswerable_all)} unanswerable")

# ─── Build balanced benchmark ────────────────────────────────────
# Target: ~300 examples, balanced categories, meaningful unanswerable

# Include ALL 42 unanswerable
benchmark_unanswerable = list(unanswerable_all)

# For answerable: sample from each category to achieve balance
# Available answerable categories from non-training documents
avail_cats = defaultdict(list)
for ex in answerable_candidates:
    avail_cats[ex["question_kind"]].append(ex)

# Target distribution (adjusted to available data)
target_pct = {
    "DIRECT_SPAN": 0.12, "DATE": 0.08, "ENTITY": 0.08, "NUMERIC": 0.10,
    "TABLE_CELL": 0.12, "TABLE_ROW": 0.08, "LIST_ITEM": 0.10,
    "SECTION_SPECIFIC": 0.08, "MULTI_CHUNK": 0.07, "LONG_CONTEXT": 0.05,
}

# Target ~200 answerable + 42 unanswerable = ~242 total
# Adjust based on available
TARGET_ANSWERABLE = 200
benchmark_answerable = []

rng = random.Random(SEED)
for cat, pct in sorted(target_pct.items(), key=lambda x: -x[1]):
    target_n = int(TARGET_ANSWERABLE * pct)
    avail = avail_cats.get(cat, [])
    n = min(target_n, len(avail))
    selected = rng.sample(avail, n) if n > 0 else []
    benchmark_answerable.extend(selected)
    print(f"  {cat}: target={target_n}, available={len(avail)}, selected={n}")

# Combine
benchmark = benchmark_answerable + benchmark_unanswerable
rng.shuffle(benchmark)

print(f"\nBenchmark: {len(benchmark)} total ({len(benchmark_answerable)} answerable + {len(benchmark_unanswerable)} unanswerable)")

# ─── Add metadata ────────────────────────────────────────────────
def add_metadata(ex):
    """Add benchmark metadata to an example."""
    m = dict(ex)  # copy
    m["benchmark_version"] = "v1"
    m["split"] = "benchmark"  # mark as benchmark (not train/val/test)

    # Tier classification
    cat = m["question_kind"]
    if cat in ("DIRECT_SPAN", "ENTITY", "DATE", "SECTION_SPECIFIC"):
        m["tier"] = "TIER_1_CORE"
    elif cat in ("TABLE_CELL", "TABLE_ROW", "LIST_ITEM", "NUMERIC"):
        m["tier"] = "TIER_2_STRUCTURED"
    elif cat in ("MULTI_CHUNK", "LONG_CONTEXT", "UNANSWERABLE"):
        m["tier"] = "TIER_3_HARD"
    else:
        m["tier"] = "TIER_2_STRUCTURED"

    # Numeric format diagnostic
    if cat == "NUMERIC":
        ans = m.get("answer", "")
        if "%" in ans or "percent" in ans.lower():
            m["numeric_format"] = "PERCENT"
        elif "$" in ans:
            m["numeric_format"] = "CURRENCY"
        elif "." in ans and any(c.isdigit() for c in ans):
            m["numeric_format"] = "DECIMAL"
        elif ans.strip().isdigit():
            m["numeric_format"] = "INTEGER"
        else:
            m["numeric_format"] = "UNIT_VALUE"
    else:
        m["numeric_format"] = None

    # Unanswerable reason
    if cat == "UNANSWERABLE":
        m["unanswerable_reason"] = "entity_absent_or_unsupported"

    return m

benchmark = [add_metadata(ex) for ex in benchmark]

# ─── Gold span validation ────────────────────────────────────────
print(f"\n=== GOLD SPAN VALIDATION ===")
valid_count = 0
invalid_count = 0
invalid_ids = []
from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained("distilbert-base-uncased")

for ex in benchmark:
    if ex["question_kind"] == "UNANSWERABLE":
        valid_count += 1
        continue
    ctx = ex["context"]
    ans = ex["answer"]
    start = ex["answer_start"]
    end = ex["answer_end"]

    extracted = ctx[start:end] if start >= 0 and end <= len(ctx) else ""
    if extracted == ans:
        valid_count += 1
    else:
        invalid_count += 1
        invalid_ids.append(ex["example_id"])

print(f"  Valid: {valid_count}/{len(benchmark)} ({valid_count/len(benchmark)*100:.1f}%)")
print(f"  Invalid: {invalid_count}")
if invalid_ids:
    print(f"  Invalid IDs: {invalid_ids[:10]}")

# ─── Token span validation ───────────────────────────────────────
print(f"\n=== TOKEN SPAN VALIDATION ===")
from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained("distilbert-base-uncased")

token_valid = 0
token_invalid = 0
for ex in benchmark:
    if ex["question_kind"] == "UNANSWERABLE":
        token_valid += 1
        continue
    enc = tok(ex["question"], ex["context"], max_length=384, truncation=True,
              padding="max_length", return_offsets_mapping=True, return_tensors="pt")
    om = [(int(s), int(e)) for s, e in enc["offset_mapping"][0].tolist()]
    input_ids = enc["input_ids"][0].tolist()

    # Find [SEP]
    sep_idx = None
    for i, tid in enumerate(input_ids):
        if tid == tok.sep_token_id:
            sep_idx = i
            break

    ans_start = ex["answer_start"]
    ans_end_trimmed = ans_start + len(ex["answer"].strip())

    start_token = None
    end_token = None
    if sep_idx is not None:
        for i in range(sep_idx + 1, len(om)):
            if input_ids[i] in (tok.pad_token_id, tok.sep_token_id):
                break
            s, e = om[i]
            if s <= ans_start < e:
                start_token = i
            if s < ans_end_trimmed <= e:
                end_token = i
                break

    if start_token is not None and end_token is not None:
        token_valid += 1
    else:
        token_invalid += 1
        if token_invalid <= 5:
            print(f"  Invalid token span: {ex['example_id']} answer=[{ex['answer'][:30]}]")

print(f"  Token valid: {token_valid}/{len(benchmark)} ({token_valid/len(benchmark)*100:.1f}%)")
print(f"  Token invalid: {token_invalid}")

# ─── Leakage audit ────────────────────────────────────────────────
print(f"\n=== LEAKAGE AUDIT ===")
bench_doc_ids = set(ex["document_id"] for ex in benchmark)
leakage = bench_doc_ids & train_docs
print(f"  Document overlap with training: {len(leakage)}")
if leakage:
    print(f"  LEAKED: {leakage}")

bench_q_ids = set(ex["example_id"] for ex in benchmark)
train_q_ids = set(ex["example_id"] for ex in derived.values() if ex.get("split") == "train")
q_leakage = bench_q_ids & train_q_ids
print(f"  Question overlap with training: {len(q_leakage)}")

# ─── Duplicate audit ──────────────────────────────────────────────
print(f"\n=== DUPLICATE AUDIT ===")
q_texts = Counter(ex["question"] for ex in benchmark)
exact_dups = {q: cnt for q, cnt in q_texts.items() if cnt > 1}
print(f"  Exact question duplicates: {len(exact_dups)}")
for q, cnt in list(exact_dups.items())[:5]:
    print(f"    [{cnt}x] {q[:60]}")

# ─── Write benchmark ──────────────────────────────────────────────
print(f"\n=== WRITING BENCHMARK ===")
os.makedirs(BENCH, exist_ok=True)

with open(f"{BENCH}/qa_benchmark_v1.jsonl", "w", encoding="utf-8") as f:
    for ex in benchmark:
        f.write(json.dumps(ex, ensure_ascii=False) + "\n")

# Compute hash
with open(f"{BENCH}/qa_benchmark_v1.jsonl", "rb") as f:
    bench_hash = hashlib.sha256(f.read()).hexdigest()

with open(f"{BENCH}/benchmark_checksum.txt", "w") as f:
    f.write(f"SHA-256: {bench_hash}\nExamples: {len(benchmark)}\n")

# ─── Benchmark manifest ──────────────────────────────────────────
bench_cats = Counter(ex["question_kind"] for ex in benchmark)
bench_docs_count = Counter(ex["document_id"] for ex in benchmark)
bench_tiers = Counter(ex.get("tier", "UNKNOWN") for ex in benchmark)

manifest = {
    "phase": "4F.5-D",
    "benchmark_version": "v1",
    "sha256": bench_hash,
    "total_examples": len(benchmark),
    "answerable": len(benchmark_answerable),
    "unanswerable": len(benchmark_unanswerable),
    "document_count": len(bench_docs_count),
    "documents": dict(bench_docs_count),
    "category_distribution": dict(bench_cats),
    "tier_distribution": dict(bench_tiers),
    "train_excluded_documents": sorted(train_docs),
    "gold_span_validation": {"valid": valid_count, "invalid": invalid_count},
    "token_span_validation": {"valid": token_valid, "invalid": token_invalid},
    "leakage": {"document_overlap": len(leakage), "question_overlap": len(q_leakage)},
    "duplicates": {"exact_question_duplicates": len(exact_dups)},
    "source_dataset_hash": "a517530354fc9bcaeef6f1aa16c3fb9ce92f1967668386bc66781e6e6bbf2e97",
}
with open(f"{BENCH}/benchmark_manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)

print(f"  Written: {BENCH}/qa_benchmark_v1.jsonl ({len(benchmark)} examples)")
print(f"  Hash: {bench_hash[:16]}...")
print(f"  Categories: {dict(bench_cats)}")
print(f"  Tiers: {dict(bench_tiers)}")
print(f"  Documents: {dict(bench_docs_count)}")

# ─── Analysis artifacts ───────────────────────────────────────────
os.makedirs(ANALYSIS, exist_ok=True)

# test_composition
with open(f"{ANALYSIS}/test_composition.json", "w") as f:
    json.dump({"old_benchmark": {"total": 221, "answerable": 221, "unanswerable": 0, "docs": 4},
               "new_benchmark": {"total": len(benchmark), "answerable": len(benchmark_answerable),
                   "unanswerable": len(benchmark_unanswerable), "docs": len(bench_docs_count)}}, f, indent=2)

# category_balance
cat_balance = {}
for cat in sorted(bench_cats.keys()):
    cat_exs = [e for e in benchmark if e["question_kind"] == cat]
    cat_balance[cat] = {"count": len(cat_exs), "pct": round(len(cat_exs)/len(benchmark)*100, 1),
        "tier": cat_exs[0].get("tier", "?") if cat_exs else "?",
        "docs": list(set(e["document_id"] for e in cat_exs))}
with open(f"{ANALYSIS}/category_balance.json", "w") as f:
    json.dump(cat_balance, f, indent=2)

# unanswerable_audit
unans_bench = [e for e in benchmark if e["question_kind"] == "UNANSWERABLE"]
with open(f"{ANALYSIS}/unanswerable_audit.json", "w") as f:
    json.dump({"total": len(unans_bench),
        "examples": [{"id": e["example_id"], "question": e["question"][:80], "reason": e.get("unanswerable_reason", "?")} for e in unans_bench[:10]]}, f, indent=2)

# leakage_audit
with open(f"{ANALYSIS}/leakage_audit.json", "w") as f:
    json.dump({"document_overlap": len(leakage), "leaked_docs": list(leakage),
        "question_overlap": len(q_leakage), "status": "PASS" if len(leakage) == 0 and len(q_leakage) == 0 else "FAIL"}, f, indent=2)

# duplicate_audit
with open(f"{ANALYSIS}/duplicate_audit.json", "w") as f:
    json.dump({"exact_duplicates": len(exact_dups), "examples": [{"question": q[:60], "count": c} for q, c in list(exact_dups.items())[:10]]}, f, indent=2)

# gold_span_validation
with open(f"{ANALYSIS}/gold_span_validation.json", "w") as f:
    json.dump({"valid": valid_count, "invalid": invalid_count, "invalid_ids": invalid_ids,
        "token_valid": token_valid, "token_invalid": token_invalid}, f, indent=2)

print(f"\nAnalysis artifacts written to {ANALYSIS}/")
print(f"\n=== BENCHMARK READY ===")
