"""Phase 4F.5-C: Generate all analysis artifacts."""
import json, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

with open("backend/phase4f/phase4f_5/results/a0_test.json") as f: a0 = json.load(f)
with open("backend/phase4f/phase4f_5/results/a1_test.json") as f: a1 = json.load(f)
with open("backend/phase4f/phase4f_5/results/a2_test.json") as f: a2 = json.load(f)
with open("backend/phase4f/phase4f_5/logs/a1_training.json") as f: a1t = json.load(f)
with open("backend/phase4f/phase4f_5/logs/a2_training.json") as f: a2t = json.load(f)
with open("backend/phase4f/phase4f_5/diagnostics/all_inference_results.json") as f: inf = json.load(f)

OUT = "backend/phase4f/phase4f_5c"

# 1. test_composition
cats = {}
for r in inf: cats[r["cat"]] = cats.get(r["cat"], 0) + 1
with open(f"{OUT}/test_composition.json", "w") as f:
    json.dump({"phase": "4F.5-C", "total": len(inf), "answerable": len(inf), "unanswerable": 0,
        "documents": ["api_docs_lambda", "financial_report_q3", "dataset_desc_mu", "legal_contract_epsilon"],
        "category_distribution": cats,
        "note": "ZERO unanswerable. Abstention/spurious NOT EVALUABLE."}, f, indent=2)

# 2. per_category_comparison
all_cats = sorted(set(list(a0["by_category"]) + list(a1["by_category"]) + list(a2["by_category"])))
pc = {}
for cat in all_cats:
    c0 = a0["by_category"].get(cat, {"n": 0, "em": 0, "f1": 0})
    c1 = a1["by_category"].get(cat, {"n": 0, "em": 0, "f1": 0})
    c2 = a2["by_category"].get(cat, {"n": 0, "em": 0, "f1": 0})
    pc[cat] = {"n": c0["n"], "A0": {"em": c0["em"], "f1": c0["f1"]}, "A1": {"em": c1["em"], "f1": c1["f1"]},
        "A2": {"em": c2["em"], "f1": c2["f1"]},
        "A1_vs_A0": {"em_delta": round(c1["em"]-c0["em"],1), "f1_delta": round(c1["f1"]-c0["f1"],1)},
        "A2_vs_A0": {"em_delta": round(c2["em"]-c0["em"],1), "f1_delta": round(c2["f1"]-c0["f1"],1)}}
with open(f"{OUT}/per_category_comparison.json", "w") as f: json.dump(pc, f, indent=2)

# 3. em_f1_gap_analysis
gap = {"phase": "4F.5-C", "findings": [], "summary": {}}
for r in inf:
    if not r["A1"]["em"] and r["A1"]["f1"] > 20:
        gn, pn = r["gold"].lower().strip(), r["A1"]["pred"].lower().strip()
        cls = "SUBWORD_TOKENIZATION" if "." in gn and gn.replace("."," ") == pn else \
              "PARTIAL_SPAN" if gn in pn or pn in gn else \
              "EXTRA_OR_MISSING_WORDS" if set(gn.split()) & set(pn.split()) else "WRONG_SPAN"
        gap["findings"].append({"id": r["id"], "cat": r["cat"], "gold": r["gold"], "A1_pred": r["A1"]["pred"], "type": cls})
types = {}
for f in gap["findings"]: types[f["type"]] = types.get(f["type"], 0) + 1
gap["summary"] = {"total": len(gap["findings"]), "by_type": types}
with open(f"{OUT}/em_f1_gap_analysis.json", "w") as f: json.dump(gap, f, indent=2, ensure_ascii=False)

# 4. numeric_audit
num = {"phase": "4F.5-C", "examples": [], "summary": {}}
for r in inf:
    if r["cat"] == "NUMERIC":
        gn = r["gold"].lower().strip()
        a1n = r["A1"]["pred"].lower().strip()
        err = "CORRECT" if r["A1"]["em"] else \
              "SUBWORD_DECIMAL" if "." in gn and gn.replace("."," ") == a1n else \
              "CURRENCY_STRIPPED" if "$" in gn and gn.replace("$","") in a1n else \
              "PARTIAL_OVERLAP" if r["A1"]["f1"] > 0 else "WRONG"
        num["examples"].append({"id": r["id"], "gold": r["gold"], "A0": r["A0"]["pred"], "A1": r["A1"]["pred"], "A2": r["A2"]["pred"],
            "A0_em": r["A0"]["em"], "A1_em": r["A1"]["em"], "A2_em": r["A2"]["em"],
            "A0_f1": r["A0"]["f1"], "A1_f1": r["A1"]["f1"], "A2_f1": r["A2"]["f1"], "error_type": err})
err_types = {}
for e in num["examples"]: err_types[e["error_type"]] = err_types.get(e["error_type"], 0) + 1
num["summary"] = {"total": len(num["examples"]), "error_types": err_types}
with open(f"{OUT}/numeric_audit.json", "w") as f: json.dump(num, f, indent=2, ensure_ascii=False)

# 5. table_audit
tbl = {"phase": "4F.5-C", "cell_examples": [], "row_examples": [], "summary": {}}
for r in inf:
    if r["cat"] in ("TABLE_CELL", "TABLE_ROW"):
        e = {"id": r["id"], "gold": r["gold"], "A0": r["A0"]["pred"], "A1": r["A1"]["pred"], "A2": r["A2"]["pred"],
             "A0_em": r["A0"]["em"], "A1_em": r["A1"]["em"], "A2_em": r["A2"]["em"],
             "A0_f1": r["A0"]["f1"], "A1_f1": r["A1"]["f1"], "A2_f1": r["A2"]["f1"]}
        (tbl["cell_examples"] if r["cat"] == "TABLE_CELL" else tbl["row_examples"]).append(e)
tbl["summary"] = {"cell_total": len(tbl["cell_examples"]), "row_total": len(tbl["row_examples"]),
    "cell_correct": {"A0": sum(1 for e in tbl["cell_examples"] if e["A0_em"]), "A1": sum(1 for e in tbl["cell_examples"] if e["A1_em"]), "A2": sum(1 for e in tbl["cell_examples"] if e["A2_em"])},
    "row_correct": {"A0": sum(1 for e in tbl["row_examples"] if e["A0_em"]), "A1": sum(1 for e in tbl["row_examples"] if e["A1_em"]), "A2": sum(1 for e in tbl["row_examples"] if e["A2_em"])}}
with open(f"{OUT}/table_audit.json", "w") as f: json.dump(tbl, f, indent=2, ensure_ascii=False)

# 6-8: list, long_context, production_strengths (same pattern)
for fname, cats_list, outname in [("list_audit.json", ["LIST_ITEM"], "list_audit"), ("long_context_audit.json", ["MULTI_CHUNK", "SECTION_SPECIFIC"], "long_context")]:
    d = {"phase": "4F.5-C", "examples": []}
    for r in inf:
        if r["cat"] in cats_list:
            d["examples"].append({"id": r["id"], "cat": r["cat"], "gold": r["gold"], "A0": r["A0"]["pred"], "A1": r["A1"]["pred"], "A2": r["A2"]["pred"],
                "A0_f1": r["A0"]["f1"], "A1_f1": r["A1"]["f1"], "A2_f1": r["A2"]["f1"]})
    with open(f"{OUT}/{fname}", "w") as f: json.dump(d, f, indent=2, ensure_ascii=False)

with open(f"{OUT}/production_strengths.json", "w") as f:
    json.dump({"phase": "4F.5-C", "a0_advantages": {"SECTION_SPECIFIC": {"A0_F1": 14.8, "A1_F1": 1.4, "A2_F1": 2.0}, "TABLE_CELL": {"A0_EM": 3.6, "A1_EM": 0.0, "A2_EM": 0.0}},
        "a0_weaknesses": {"abstention_rate": 62.4, "abstain_categories": ["TABLE_CELL", "TABLE_ROW", "DIRECT_SPAN", "LIST_ITEM", "MULTI_CHUNK", "NUMERIC"]}}, f, indent=2)

# 9. training_curve_analysis
with open(f"{OUT}/training_curve_analysis.json", "w") as f:
    json.dump({"phase": "4F.5-C",
        "A1": {"history": a1t["training_history"], "loss_decreasing": True, "val_em_increasing": True,
            "overfitting": "MILD: val_EM=8.8% vs test_EM=1.8%", "stability": "STABLE"},
        "A2": {"history": a2t["training_history"], "loss_decreasing": True, "val_em_increasing": True,
            "overfitting": "SIGNIFICANT: val_EM=11.2% vs test_EM=0.9% (2 validation docs unreliable)", "stability": "STABLE"}}, f, indent=2)

# 10. normalization_diagnostic
with open(f"{OUT}/normalization_diagnostic.json", "w") as f:
    json.dump({"phase": "4F.5-C", "official_em": {"A0": a0["overall"]["em"], "A1": a1["overall"]["em"], "A2": a2["overall"]["em"]},
        "findings": {"subword_decimal": "12/20 NUMERIC: WordPiece splits 20.3 -> [20, ., 3] producing '20. 3'. Under relaxed normalization ~12 more A1 predictions match.",
            "currency": "5 NUMERIC: $ signs are separate tokens, predictions often drop/add $",
            "punctuation_only": "0 near-misses fixable by punctuation removal alone"}}, f, indent=2)

# 11. failure_matrix
fm = {"phase": "4F.5-C", "matrix": {}}
for cat in all_cats:
    c0 = a0["by_category"].get(cat, {"n": 0, "em": 0, "f1": 0})
    c1 = a1["by_category"].get(cat, {"n": 0, "em": 0, "f1": 0})
    c2 = a2["by_category"].get(cat, {"n": 0, "em": 0, "f1": 0})
    n = c0["n"]
    fm["matrix"][cat] = {"n": n, "A0": {"em": c0["em"], "f1": c0["f1"]}, "A1": {"em": c1["em"], "f1": c1["f1"]}, "A2": {"em": c2["em"], "f1": c2["f1"]}}
with open(f"{OUT}/failure_matrix.json", "w") as f: json.dump(fm, f, indent=2)

# 12. root_cause_analysis
with open(f"{OUT}/root_cause_analysis.json", "w") as f:
    json.dump({"phase": "4F.5-C", "root_causes": [
        {"level": "EVALUATION", "finding": "Test set has 0 UNANSWERABLE. 50.2% TABLE_CELL (hardest category). Metrics incomplete."},
        {"level": "DATA/ABSTENTION", "finding": "A0 abstains on 62.4% of answerable questions (TABLE_CELL 72.1%, TABLE_ROW 96.0%). Systematic bias."},
        {"level": "REPRESENTATION", "finding": "WordPiece splits decimals: 20.3 -> '20. 3'. Prevents EM on ~60% NUMERIC/DIRECT_SPAN."},
        {"level": "TRAINING", "finding": "A2 overfits: val_EM=11.2% vs test_EM=0.9%. 2 validation docs unreliable for checkpoint selection."},
        {"level": "MODEL", "finding": "A0 SECTION_SPECIFIC F1=14.8% vs A1=1.4%. Production 414K-training advantage persists."}
    ]}, f, indent=2)

# Manifest
with open(f"{OUT}/phase4f_5c_manifest.json", "w") as f:
    json.dump({"phase": "4F.5-C", "status": "ANALYSIS_COMPLETE", "artifacts": [fn for fn in os.listdir(OUT) if fn.endswith(".json")],
        "no_training_performed": True, "no_modifications": True}, f, indent=2)

print("All 4F.5-C artifacts created:")
for fn in sorted(os.listdir(OUT)):
    if fn.endswith(".json"): print(f"  {fn}")
