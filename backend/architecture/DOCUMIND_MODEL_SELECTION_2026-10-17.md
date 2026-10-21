# DocuMind model selection record — 2026-10-17

Scope: the local generative answering engine only. The extractive DistilBERT QA
model (`backend/models/documind-qa`) remains the default engine and the baseline.
Nothing in this record authorises a production model change.

---

## 1. Hardware and runtime (measured on this machine)

| Item | Value |
|---|---|
| CPU | 8 physical / 12 logical cores (Windows 10 10.0.26300) |
| RAM | 16.9 GB total, **4.3 GB available** at measurement time |
| GPU | none — `torch.cuda.is_available() == False` (`torch 2.13.0+cpu`) |
| Disk free (C:) | 65.6 GB |
| Python / transformers | 3.11.0 / 5.16.1 |
| Current generator | `google/flan-t5-base`, CPU fp32, lazy load, beams=4, no_repeat_ngram=3, max_new_tokens 48/96/192, 512-token encoder |

The 4.3 GB *available* figure is the binding constraint: a 780M-parameter model in
fp32 needs ≈3.1 GB of weights plus activations, and a 1.5B model needs ≈6 GB.
There is no CUDA device, so GPU-resident quantisation (4-bit GPTQ/AWQ) is not an
option here; CPU int8 would need an additional runtime (llama.cpp / optimum) that
is not installed and would have to be justified as a new dependency.

## 2. Local model inventory (no download required)

`~/.cache/huggingface/hub` holds only encoder/QA/embedding models plus the current
generator:

| Cached model | Size | Role |
|---|---|---|
| `google/flan-t5-base` | 948 MB | **current generator** |
| `distilbert-base-*` | 252–257 MB | encoders |
| `bert-base-*` | 417–421 MB | encoders |
| `microsoft/deberta-v3-base` | 711 MB | encoder |
| `deepset/roberta-base-squad2` | 795 MB | extractive QA comparison |
| `sentence-transformers/all-MiniLM-L6-v2` | 88 MB | embeddings |
| `Systran/faster-whisper-small` | metadata only | voice STT |

No larger generative model is cached, so any replacement needs a download.

## 3. Configuration sweep (no replacement, same frozen benchmark)

`python -m evaluation.experiments.run_generation_config_sweep` — 182 frozen rows,
5-mark format, production `answer_generatively` path (gate, withholding,
verification, elaboration identical across variants), report
`backend/evaluation/reports/generation_config_sweep_2026-10-17/`. This sweep ran
**before** the single-token verification fix below, so its absolute numbers are not
the current incumbent baseline (EM 0.129 / F1 0.257 at 10 marks); the variant-to-variant
comparison is what it establishes.

| Variant | EM | F1 | Empty (answerable) | Abstain (unanswerable) | Spurious | Unsupported | p50 | Correct only here / only in current |
|---|---|---|---|---|---|---|---|---|
| `v0_current` beams=4 | 0.121 | 0.216 | 0.614 | 0.976 | 0.024 | 0.415 | 220 ms | — |
| `v1_greedy` beams=1 | 0.129 | 0.231 | 0.593 | 0.976 | 0.024 | 0.379 | **133 ms** | 2 / 1 |
| `v2_short_answer` cue | **0.136** | **0.248** | 0.593 | 0.976 | 0.024 | 0.390 | 223 ms | 3 / 1 |
| `v3_context_first` | 0.114 | 0.222 | 0.586 | 0.952 | 0.048 | 0.381 | 205 ms | 3 / 4 |

Reading: the "improvements" are **+1 to +2 net correct answers out of 140**. That is
noise, not evidence, so no prompt or decoding change was adopted. Two facts are
worth keeping:

* `v1_greedy` is **39% faster** (220 → 133 ms p50) at indistinguishable accuracy —
  a possible *efficiency* change, still requiring owner sign-off because decoding
  is production behaviour.
* `v3_context_first` is worse and raises spurious answers to 0.048 — rejected.

Independent reproduction: the earlier full 5-mark run (`..._fmt5`) and this sweep's
`v0_current` (separate process, separate run) both give EM 0.121 / F1 0.216,
so the baseline is reproducible across runs.

## 4. Candidate shortlist (none downloaded — approval required)

| Candidate | Params | Licence (per model card) | fp32 weights | Fit at 4.3 GB free | Rationale |
|---|---|---|---|---|---|
| `google/flan-t5-base` (current) | 250M | Apache-2.0 | ~1.0 GB | yes | incumbent baseline |
| `google/flan-t5-large` | 780M | Apache-2.0 | ~3.1 GB | marginal (≈4 GB peak) | same family/decoding path, directly comparable, known to be stronger at QA; would need the machine freed of other processes |
| `Qwen2.5-0.5B-Instruct` | 494M | Apache-2.0 | ~2.0 GB | yes | instruction-following chat model; likely lower short-span EM but may ground/format better |
| `HuggingFaceTB/SmolLM2-360M-Instruct` | 362M | Apache-2.0 | ~1.5 GB | yes | smallest modern instruct model; low risk experiment |
| `microsoft/Phi-3-mini-4k-instruct` | 3.8B | MIT | ~15 GB | **no** | exceeds RAM and CPU feasibility |
| `meta-llama/Llama-3.2-1B-Instruct` | 1.2B | Llama 3.2 Community Licence | ~5 GB | **no** at current free RAM | gated licence + memory |
| `mistralai/Mistral-7B-Instruct-v0.3` | 7.2B | Apache-2.0 | ~28 GB | **no** | far beyond the machine |

Excluded without experiment: Phi-3-mini, Llama-3.2-1B, Mistral-7B (resource
infeasible on a CPU-only 16.9 GB machine), and any 4-bit GPU path (no CUDA).

## 5. Candidate experiment — `Qwen/Qwen2.5-0.5B-Instruct` (approved download)

Downloaded and evaluated 2026-10-17 with the owner's approval (~1 GB, Apache-2.0
per its model card; 494.0M parameters, loaded in bfloat16). Runner:
`evaluation/experiments/run_candidate_model_evaluation.py`; report
`evaluation/reports/candidate_qwen25_05b_instruct_2026-10-17/`.

Protocol: same frozen rows, same production answerability gate, same verifier and
the same 10-mark elaboration as the incumbent; system prompt asks for the shortest
correct phrase and for `INSUFFICIENT_EVIDENCE` when the context lacks the answer;
greedy decoding, `max_new_tokens=64`, 1024-token input window.

| Metric (10 marks, 182 rows) | Extractive | Incumbent flan-t5-base | Candidate Qwen2.5-0.5B |
|---|---|---|---|
| Exact match (answerable) | 0.157 | **0.129** | 0.093 |
| Token F1 (answerable) | 0.387 | **0.257** | 0.189 |
| Abstention on unanswerable | 0.000 | 0.952 | 0.976 |
| Spurious on unanswerable | 1.000 | 0.048 | 0.024 |
| Empty answer rate (all) | — | 0.577 | 0.681 |
| SUPPORTED rate (all) | — | 0.286 | 0.280 |
| Unsupported-claim rate | — | 0.198 | **0.100** |
| Withheld (unattributable) | — | 22 | 36 |
| Answerability-gate abstentions | — | 83 | 83 |
| Model refusals | — | — | 5 |
| Latency p50 / p95 | — | **220 / 1173 ms** | 1918 / 4218 ms |
| Peak process RSS | — | ~1.0 GB | 1699 MB |
| Load time | — | lazy, ~2 s | 2.6 s |

The candidate produces **fewer unsupported claims per claim** (0.10 vs 0.198), but it
answers less accurately (EM 0.093 vs 0.129; F1 0.189 vs 0.257) and is **8.7× slower**
on this CPU. 36 of its answers were withheld as unattributable because the lexical
verifier requires 60% word overlap — a good paraphrase fails it. That is a limitation
of the verifier for *any* non-copying model, and an argument against swapping in a
chat model until claim-level entailment exists.

### Verifier defect found by this experiment (fixed)

Six of the first 20 candidate rows were withheld as "claim too short to verify" —
`MIN_CLAIM_TOKENS` was 2, so single-token gold answers (`2010`, `45`, `Endpoints`)
could never be supported. The incumbent had the same defect. Fixed to 1 with the
numeric check still enforced; the incumbent re-run on the same rows improved F1
(0.245 → 0.257), unsupported-claim rate (0.304 → 0.198) and empty rate (0.648 → 0.577),
while abstention on unanswerable rows moved 0.976 → 0.952 and spurious answers
0.024 → 0.048 (one additional false answer out of 42). That trade is recorded, not
hidden. Regression tests: `tests/unit/generation/test_generation_mark_depth.py::TestShortAnswersAreClaims`.

## 6. Decision

**RETAIN CURRENT MODEL.** The candidate fails the pre-declared accuracy gate
(EM and F1 both above 0.129 / 0.257) by a wide margin and is much slower;
no configuration variant cleared the noise threshold either. `google/flan-t5-base`
remains the generator and remains **below the extractive baseline** on frozen P3.
The candidate stays documented as a rejected experiment — it is not wired into
production, and no route can load it.

## 7. Remaining candidates and exact next steps

The next candidate remains `google/flan-t5-large` (780M, Apache-2.0, ~3.1 GB) — it
shares the incumbent's architecture and decoding path, so the comparison needs no new
adapter. It needs ≈4 GB peak RAM, which this machine only has after other processes
are closed.

```
cd backend
./venv/Scripts/python.exe - <<'PY'
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
m = "google/flan-t5-large"
AutoTokenizer.from_pretrained(m)
AutoModelForSeq2SeqLM.from_pretrained(m)
PY
DOCUMIND_GENERATOR_MODEL=google/flan-t5-large \
  ./venv/Scripts/python.exe -m evaluation.experiments.run_generation_benchmark --format 10
```

Acceptance for any switch (unchanged, pre-declared): EM **and** F1 above the current
0.129 / 0.257, unsupported-claim rate not worse than 0.198, unanswerable abstention
not below 0.952, latency not worse than 220 ms p50 on this CPU. Otherwise the
incumbent stays.

## 7. Status

| Item | Status |
|---|---|
| Baseline reproduced | **VERIFIED** (`..._fmt5` and sweep `v0_current` agree) |
| Config sweep | **VERIFIED** (`generation_config_sweep_2026-10-17/`) |
| Candidate shortlist with licences/resources | **DOCUMENTED**, licences to be re-checked at download time |
| Candidate evaluation — Qwen2.5-0.5B-Instruct | **DONE — REJECTED** (EM 0.093 / F1 0.189 vs incumbent 0.129 / 0.257; 8.7× slower) |
| Verifier short-claim defect found by the experiment | **FIXED AND MEASURED** (F1 0.245 → 0.257, unsupported 0.304 → 0.198) |
| Candidate evaluation — flan-t5-large | **BLOCKED** — needs ≈4 GB free RAM and a second download |
| Production model change | **NOT DONE** (not justified by the measured evidence) |
