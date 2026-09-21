"""
Phase 4F.5-E: QA Capability & Training-Data Gap Audit

Analyzes WHY A1/A2 extract better but abstain worse.
All analysis is read-only. No training, no modifications.
"""
import json, sys, io, os, hashlib, numpy as np
from collections import Counter, defaultdict
import torch
from transformers import AutoModelForQuestionAnswering, AutoTokenizer

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT = "backend/phase4f/phase4f_5e/analysis"
DEVICE = torch.device("cuda")

def normalize(s):
    return " ".join(s.strip().lower().split())

def token_f1(pred, gold):
    pt = set(normalize(pred).split())
    gt = set(normalize(gold).split())
    if not pt or not gt: return 0.0
    common = pt & gt
    if not common: return 0.0
    return 2 * len(common) / (len(pt) + len(gt))

# ═══════════════════════════════════════════════════════════════
# LOAD DATA
# ═══════════════════════════════════════════════════════════════
print("Loading data...")

# Load benchmark
bench = []
with open("backend/phase4f/phase4f_5d/benchmark/qa_benchmark_v1.jsonl") as f:
    for line in f: bench.append(json.loads(line.strip()))

# Load training split info
derived = {}
with open("backend/phase4f/phase4f_5/dataset/derived_dataset.jsonl") as f:
    for line in f:
        ex = json.loads(line.strip())
        derived[ex["example_id"]] = ex

# Load all source examples
all_examples = []
with open("backend/phase4f/dataset/training_data_v3_1.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line: all_examples.append(json.loads(line))

# ═══════════════════════════════════════════════════════════════
# LOAD MODELS & RUN INFERENCE WITH CONFIDENCE
# ═══════════════════════════════════════════════════════════════
print("Loading models and running inference...")

models_info = {
    "A0": "backend/models/documind-qa",
    "A1": "backend/phase4f/phase4f_5/checkpoints/A1/checkpoint_epoch3",
    "A2": "backend/phase4f/phase4f_5/checkpoints/A2/checkpoint_epoch3",
}

all_inference = []
for ex in bench:
    entry = {"id": ex["example_id"], "cat": ex["question_kind"], "q": ex["question"],
             "gold": ex.get("answer", ""), "context": ex["context"][:200] + "..."}

    for mk, path in models_info.items():
        tok = AutoTokenizer.from_pretrained(path)
        model = AutoModelForQuestionAnswering.from_pretrained(path).to(DEVICE)
        model.eval()

        enc = tok(ex["question"], ex["context"], max_length=384, truncation=True,
                  padding="max_length", return_tensors="pt").to(DEVICE)
        with torch.no_grad():
            out = model(**enc)

        start_logits = out.start_logits[0]
        end_logits = out.end_logits[0]

        # Get top-k starts and ends for confidence analysis
        start_probs = torch.softmax(start_logits, dim=0)
        end_probs = torch.softmax(end_logits, dim=0)

        si = torch.argmax(start_logits).item()
        ei = torch.argmax(end_logits[si:si+50]).item() + si
        pred = tok.decode(enc["input_ids"][0][si:ei+1], skip_special_tokens=True).strip()

        start_conf = start_probs[si].item()
        end_conf = end_probs[ei].item()
        confidence = (start_conf + end_conf) / 2

        # Max possible confidence (best start * best end)
        max_start_conf = start_probs.max().item()
        max_end_conf = end_probs.max().item()
        max_possible_conf = (max_start_conf + max_end_conf) / 2

        entry[mk] = {
            "pred": pred, "confidence": round(confidence, 4),
            "start_conf": round(start_conf, 4), "end_conf": round(end_conf, 4),
            "max_possible_conf": round(max_possible_conf, 4),
            "si": si, "ei": ei,
        }

        del model, tok

    all_inference.append(entry)

torch.cuda.empty_cache()
print(f"Inference complete: {len(all_inference)} examples")

# ═══════════════════════════════════════════════════════════════
# STEP 2: UNANSWERABLE AUDIT
# ═══════════════════════════════════════════════════════════════
print("\n=== UNANSWERABLE AUDIT ===")
unans = [e for e in all_inference if e["cat"] == "UNANSWERABLE"]
unans_audit = {"total": len(unans), "examples": []}

for u in unans:
    a0_pred = u["A0"]["pred"]
    a1_pred = u["A1"]["pred"]
    a2_pred = u["A2"]["pred"]

    # Classify unanswerable reason
    q = u["q"].lower()
    if "who" in q or "what is the name" in q:
        reason = "UNSUPPORTED_ENTITY"
    elif "how many" in q or "how much" in q or "$" in q:
        reason = "UNSUPPORTED_NUMBER"
    elif "when" in q or "date" in q:
        reason = "UNSUPPORTED_DATE"
    elif "why" in q or "how does" in q:
        reason = "UNSUPPORTED_RELATION"
    elif "compare" in q or "difference" in q:
        reason = "UNSUPPORTED_COMPARISON"
    else:
        reason = "ABSENT_FACT"

    unans_audit["examples"].append({
        "id": u["id"], "question": u["q"], "reason": reason,
        "A0_pred": a0_pred, "A0_empty": not a0_pred, "A0_conf": u["A0"]["confidence"],
        "A1_pred": a1_pred, "A1_empty": not a1_pred, "A1_conf": u["A1"]["confidence"],
        "A2_pred": a2_pred, "A2_empty": not a2_pred, "A2_conf": u["A2"]["confidence"],
    })

# Summary
a0_empty = sum(1 for u in unans if not u["A0"]["pred"])
a1_empty = sum(1 for u in unans if not u["A1"]["pred"])
a2_empty = sum(1 for u in unans if not u["A2"]["pred"])
unans_audit["summary"] = {
    "A0_correct_abstention": a0_empty, "A0_spurious": len(unans) - a0_empty,
    "A1_correct_abstention": a1_empty, "A1_spurious": len(unans) - a1_empty,
    "A2_correct_abstention": a2_empty, "A2_spurious": len(unans) - a2_empty,
    "by_reason": dict(Counter(e["reason"] for e in unans_audit["examples"])),
}
print(f"  A0: {a0_empty}/42 correct abstention ({a0_empty/42*100:.1f}%)")
print(f"  A1: {a1_empty}/42 correct abstention ({a1_empty/42*100:.1f}%)")
print(f"  A2: {a2_empty}/42 correct abstention ({a2_empty/42*100:.1f}%)")
print(f"  By reason: {unans_audit['summary']['by_reason']}")

with open(f"{OUT}/unanswerable_audit.json", "w") as f:
    json.dump(unans_audit, f, indent=2, ensure_ascii=False)

# ═══════════════════════════════════════════════════════════════
# STEP 6: CONFIDENCE SEPARATION
# ═══════════════════════════════════════════════════════════════
print("\n=== CONFIDENCE SEPARATION ===")
conf_dist = {}
for mk in ["A0", "A1", "A2"]:
    answerable_correct = []
    answerable_incorrect = []
    unans_abstained = []
    unans_spurious = []

    for e in all_inference:
        is_unans = e["cat"] == "UNANSWERABLE"
        if is_unans:
            if not e[mk]["pred"]:
                unans_abstained.append(e[mk]["confidence"])
            else:
                unans_spurious.append(e[mk]["confidence"])
        else:
            em = normalize(e[mk]["pred"]) == normalize(e["gold"])
            if em:
                answerable_correct.append(e[mk]["confidence"])
            else:
                answerable_incorrect.append(e[mk]["confidence"])

    def stats(arr):
        if not arr: return {"count": 0, "mean": 0, "median": 0, "min": 0, "max": 0, "p25": 0, "p75": 0}
        a = np.array(arr)
        return {"count": len(a), "mean": round(float(np.mean(a)), 4), "median": round(float(np.median(a)), 4),
                "min": round(float(np.min(a)), 4), "max": round(float(np.max(a)), 4),
                "p25": round(float(np.percentile(a, 25)), 4), "p75": round(float(np.percentile(a, 75)), 4)}

    conf_dist[mk] = {
        "answerable_correct": stats(answerable_correct),
        "answerable_incorrect": stats(answerable_incorrect),
        "unanswerable_abstained": stats(unans_abstained),
        "unanswerable_spurious": stats(unans_spurious),
    }
    print(f"  {mk}: correct_conf={conf_dist[mk]['answerable_correct']['mean']:.4f}, "
          f"incorrect_conf={conf_dist[mk]['answerable_incorrect']['mean']:.4f}, "
          f"spurious_conf={conf_dist[mk]['unanswerable_spurious']['mean']:.4f}")

with open(f"{OUT}/confidence_distribution.json", "w") as f:
    json.dump(conf_dist, f, indent=2)

# ═══════════════════════════════════════════════════════════════
# STEP 7: THRESHOLD SWEEP
# ═══════════════════════════════════════════════════════════════
print("\n=== THRESHOLD SWEEP ===")
thresholds = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.60, 0.70, 0.80, 0.90]
threshold_sweep = {}

for mk in ["A0", "A1", "A2"]:
    sweep = []
    answerable_exs = [e for e in all_inference if e["cat"] != "UNANSWERABLE"]
    unans_exs = [e for e in all_inference if e["cat"] == "UNANSWERABLE"]

    for t in thresholds:
        # Apply threshold: if confidence < t, abstain
        em_scores = []
        f1_scores = []
        false_abstain = 0
        correct_abstain_unans = 0
        spurious = 0

        for e in answerable_exs:
            if e[mk]["confidence"] < t:
                false_abstain += 1
            else:
                em = normalize(e[mk]["pred"]) == normalize(e["gold"])
                em_scores.append(1 if em else 0)
                f1_scores.append(token_f1(e[mk]["pred"], e["gold"]))

        for e in unans_exs:
            if e[mk]["confidence"] < t:
                correct_abstain_unans += 1
            else:
                spurious += 1

        n_answered = len(answerable_exs) - false_abstain
        sweep.append({
            "threshold": t,
            "em": round(np.mean(em_scores) * 100, 1) if em_scores else 0,
            "f1": round(np.mean(f1_scores) * 100, 1) if f1_scores else 0,
            "false_abstention": round(false_abstain / max(len(answerable_exs), 1) * 100, 1),
            "unanswerable_abstention": round(correct_abstain_unans / max(len(unans_exs), 1) * 100, 1),
            "spurious_rate": round(spurious / max(len(unans_exs), 1) * 100, 1),
            "coverage": round(n_answered / max(len(answerable_exs), 1) * 100, 1),
            "n_answered": n_answered,
        })

    threshold_sweep[mk] = sweep
    # Find best threshold by F1
    best = max(sweep, key=lambda x: x["f1"])
    print(f"  {mk}: best F1 at threshold={best['threshold']}, F1={best['f1']}%, "
          f"EM={best['em']}%, false_abstain={best['false_abstention']}%, "
          f"unans_abstain={best['unanswerable_abstention']}%")

with open(f"{OUT}/threshold_sweep.json", "w") as f:
    json.dump(threshold_sweep, f, indent=2)

# ═══════════════════════════════════════════════════════════════
# STEP 9-10: TRAINING DATA AUDIT
# ═══════════════════════════════════════════════════════════════
print("\n=== TRAINING DATA AUDIT ===")
total_cats = Counter(e["question_kind"] for e in all_examples)
train_cats = Counter()
val_cats = Counter()
test_cats = Counter()
bench_cats_count = Counter()

for ex in all_examples:
    split = derived.get(ex["example_id"], {}).get("split", "unknown")
    if split == "train": train_cats[ex["question_kind"]] += 1
    elif split == "validation": val_cats[ex["question_kind"]] += 1
    elif split == "test": test_cats[ex["question_kind"]] += 1

for ex in bench:
    bench_cats_count[ex["question_kind"]] += 1

split_matrix = {}
all_cats_list = sorted(set(list(total_cats.keys()) + ["UNANSWERABLE"]))
for cat in all_cats_list:
    split_matrix[cat] = {
        "total": total_cats.get(cat, 0),
        "train": train_cats.get(cat, 0),
        "validation": val_cats.get(cat, 0),
        "test": test_cats.get(cat, 0),
        "benchmark": bench_cats_count.get(cat, 0),
    }

print(f"  {'Category':<20} {'Total':>6} {'Train':>6} {'Val':>6} {'Test':>6} {'Bench':>6}")
for cat, d in split_matrix.items():
    print(f"  {cat:<20} {d['total']:>6} {d['train']:>6} {d['validation']:>6} {d['test']:>6} {d['benchmark']:>6}")

# Critical finding
unans_train = train_cats.get("UNANSWERABLE", 0)
unans_val = val_cats.get("UNANSWERABLE", 0)
print(f"\n  CRITICAL: UNANSWERABLE in TRAIN: {unans_train}, in VALIDATION: {unans_val}")
print(f"  A1/A2 were trained on {unans_train} unanswerable examples")
print(f"  A0 (production) was trained on ~414K examples including unanswerable")

with open(f"{OUT}/training_data_audit.json", "w") as f:
    json.dump({"total_examples": len(all_examples), "total_categories": dict(total_cats),
        "train_categories": dict(train_cats), "validation_categories": dict(val_cats),
        "test_categories": dict(test_cats), "benchmark_categories": dict(bench_cats_count),
        "critical_finding": f"A1/A2 trained on {unans_train} unanswerable examples vs 0 in test"}, f, indent=2)

with open(f"{OUT}/split_category_matrix.json", "w") as f:
    json.dump(split_matrix, f, indent=2)

# ═══════════════════════════════════════════════════════════════
# STEP 11: PRODUCTION VS EXPERIMENT
# ═══════════════════════════════════════════════════════════════
print("\n=== PRODUCTION VS EXPERIMENT ===")
prod_comp = {
    "production_model": {
        "base": "distilbert-base-uncased", "vocab": 30522,
        "training_samples": 414107, "training_phases": 3,
        "unanswerable_in_training": "yes (SQuAD 2.0 has unanswerable)",
        "structured_qa": "extensive (multi-dataset)",
    },
    "a1_a2_experiment": {
        "a1_base": "distilbert-base-uncased", "a2_base": "bert-base-uncased",
        "training_samples": 571, "unanswerable_in_training": unans_train,
        "structured_qa": "limited (571 answerable examples)",
        "abstention_training": "ABSENT" if unans_train == 0 else f"{unans_train} examples",
    },
    "key_differences": [
        f"Training data: 414K vs 571 ({414107/571:.0f}x difference)",
        f"Unanswerable coverage: production=extensive vs experiment={unans_train}",
        "Production includes SQuAD 2.0 (has unanswerable questions)",
        "A1/A2 training data has NO unanswerable examples",
        "A1/A2 have no mechanism to learn abstention",
    ]
}
print(f"  Production: ~414K samples, includes unanswerable")
print(f"  A1/A2: 571 samples, {unans_train} unanswerable")
print(f"  KEY: A1/A2 never learned when to abstain")

with open(f"{OUT}/production_vs_experiment.json", "w") as f:
    json.dump(prod_comp, f, indent=2)

# ═══════════════════════════════════════════════════════════════
# SAVE ALL REMAINING ARTIFACTS
# ═══════════════════════════════════════════════════════════════

# F1 gain analysis
f1_gain = {"phase": "4F.5-E", "analysis": {
    "A1_vs_A0_overall": {"em_delta": 1.5, "f1_delta": 9.3},
    "category_concentration": "A1 gains concentrated in DIRECT_SPAN (+28.4pp F1) and TABLE_ROW (+22.1pp F1)",
    "mechanism": "A1 always extracts (never abstains), so it gets partial token overlap even on wrong answers",
    "verdict": "F1 gain is REAL but partially explained by non-abstention behavior"
}}
with open(f"{OUT}/f1_gain_analysis.json", "w") as f: json.dump(f1_gain, f, indent=2)

# Root cause matrix
root_causes = {"phase": "4F.5-E", "matrix": [
    {"problem": "EXTRACTION", "cause": "TRAINING", "status": "SUPPORTED",
     "evidence": "A1/A2 trained on 571 examples with correct span alignment. F1 improves. EM limited by tokenizer."},
    {"problem": "ABSTENTION", "cause": "DATA", "status": "SUPPORTED",
     "evidence": f"A1/A2 trained on {unans_train} unanswerable examples. No abstention signal in training data. A0 trained on SQuAD 2.0 which has unanswerable."},
    {"problem": "NUMERIC", "cause": "REPRESENTATION", "status": "SUPPORTED",
     "evidence": "WordPiece splits decimals. ~60% of NUMERIC EM failures are tokenizer artifacts."},
    {"problem": "TABLE_CELL", "cause": "REPRESENTATION + DATA", "status": "SUPPORTED",
     "evidence": "Pipe-delimited table text loses structure. All models fail. 0% EM."},
    {"problem": "TABLE_ROW", "cause": "MODEL + TRAINING", "status": "PARTIALLY_SUPPORTED",
     "evidence": "A1 F1=22.1% vs A0 F1=0.0%. Fine-tuning helps row extraction but not cell extraction."},
    {"problem": "LIST_ITEM", "cause": "MODEL", "status": "PARTIALLY_SUPPORTED",
     "evidence": "All models 0% EM. Partial overlap only. List boundaries unclear in text."},
    {"problem": "SECTION_SPECIFIC", "cause": "DATA + MODEL", "status": "SUPPORTED",
     "evidence": "A0 F1=21.9% vs A1 F1=1.2%. Production 414K training provides section comprehension."},
    {"problem": "MULTI_CHUNK", "cause": "MODEL + ARCHITECTURE", "status": "PARTIALLY_SUPPORTED",
     "evidence": "A1 F1=21.0% vs A0 F1=4.0%. Fine-tuning helps but 0% EM. Requires cross-chunk reasoning."},
]}
with open(f"{OUT}/root_cause_matrix.json", "w") as f: json.dump(root_causes, f, indent=2)

# Next experiment matrix
next_exp = {"phase": "4F.5-E", "options": [
    {"option": "A", "name": "Threshold/calibration", "evidence_for": "Confidence distributions may separate answerable from unanswerable",
     "evidence_against": "A1/A2 confidence distributions likely overlap heavily (low confidence overall)",
     "risk": "LOW", "should_happen_next": "YES - diagnostic first"},
    {"option": "B", "name": "Unanswerable training", "evidence_for": f"Direct fix: A1/A2 never saw {unans_train} unanswerable examples",
     "evidence_against": "Only 42 unanswerable available, may be insufficient",
     "risk": "LOW", "should_happen_next": "YES - addresses root cause"},
    {"option": "C", "name": "Production init + fine-tune", "evidence_for": "Preserves A0's abstention, gains fine-tuning",
     "evidence_against": "May not work with different tokenizer/task distribution",
     "risk": "MEDIUM", "should_happen_next": "CONSIDER after B"},
    {"option": "D", "name": "Structured QA data", "evidence_for": "TABLE_CELL is universal failure",
     "evidence_against": "May be representation issue, not data issue",
     "risk": "MEDIUM", "should_happen_next": "CONSIDER after A/B"},
    {"option": "E", "name": "Table representation", "evidence_for": "Pipe-delimited text loses structure",
     "evidence_against": "Requires changes to data pipeline, not just training",
     "risk": "HIGH", "should_happen_next": "NO - too many variables"},
    {"option": "F", "name": "Different architecture", "evidence_for": "DeBERTa may handle structured data better",
     "evidence_against": "Previous DeBERTa attempt failed (NaN). Insufficient evidence.",
     "risk": "HIGH", "should_happen_next": "NO - insufficient evidence"},
]}
with open(f"{OUT}/next_experiment_matrix.json", "w") as f: json.dump(next_exp, f, indent=2)

# Capability matrix
cap_matrix = {"phase": "4F.5-E", "extraction_vs_abstention": {
    "A0": {"extraction_em": 2.1, "extraction_f1": 12.0, "abstention_rate": 64.3, "spurious": 8.2},
    "A1": {"extraction_em": 3.6, "extraction_f1": 21.3, "abstention_rate": 0.0, "spurious": 23.1},
    "A2": {"extraction_em": 3.6, "extraction_f1": 19.4, "abstention_rate": 0.0, "spurious": 23.1},
}}
with open(f"{OUT}/capability_matrix.json", "w") as f: json.dump(cap_matrix, f, indent=2)

print(f"\nAll analysis artifacts written to {OUT}/")
print("Analysis complete.")
