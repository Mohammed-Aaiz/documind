# Student answer depth repair — 2026-11-09

## Scope and evidence

The owner explicitly requested more detailed 5-, 10-, and 15-mark answers and
completion of that work. This is a production answer-depth repair, not a new
research result or a declaration of general shipping readiness. The frozen
benchmark, model weights, uploaded files, indexes, and environment files are
not changed. Groq remains the sole product LLM.

Specialist ownership: AI_AGENT implements generation/orchestration changes;
TEST_AGENT owns regression tests; VERIFIER independently reviews; COORDINATOR
records evidence and verifies the local runtime. Specialist execution briefly
hit a service usage limit and resumed; incomplete turns were not treated as
successful verification.

Observed before the repair:

- Visible answer allowances were 320/640/1024 tokens. The provider imposed a
  separate 1536-token completion cap, including GPT-OSS reasoning.
- Source-excerpt fallback selected at most 4/6/8 sentences and could omit a
  connected generator step even when it existed in the supplied paragraph.
- Live VAWT generation from the existing module 4.pdf index produced 78 words
  for 5 marks and 83 for 10 marks after claim filtering. A subsequent 15-mark
  call received Groq HTTP 429; it is not a successful baseline result.
- The indexed VAWT parent has separate child headings for each working step.
  Exact full-heading equality returned isolated steps instead of the parent
  topic. Read-only inspection confirmed rotor, shaft, generator, and yaw
  information in chunks 135–144 on PDF pages 12–13.
- Visual retrieval subsequently capped the combined list at eight blocks,
  which could truncate recovered topic evidence again.

## Acceptance and approach

Reuse the existing provider, PostgreSQL hierarchy, and source verifier. Give
each mark format room for developed explanations, preserve intermediate process
steps, and prioritize explicit question parts. Recover only a matching contiguous
parent topic, with owner scope and exact source identity intact. Preserve recovered
text when adding bounded visual candidates. Small context windows must reserve
usable evidence before allocating output. Sparse evidence must not be padded.

No extra inference pass, new dependency, new model, grading claim, or relaxed
verification threshold is required. Larger actual outputs can take longer and
consume more provider quota; ceilings are allowances rather than target lengths.

Context7 documentation consulted: Groq's
[GPT-OSS model documentation](https://console.groq.com/docs/model/openai/gpt-oss-20b)
and [reasoning parameters](https://console.groq.com/docs/reasoning). Hiding reasoning
does not supply additional source evidence or establish answer correctness.

## Verification limits

Unit tests establish code contracts, not human academic quality. The existing
lexical verifier can reject valid paraphrases and accept incorrect relations
that reuse source words. An independent diagnostic reproduced that limitation;
this repair does not describe lexical verification as factual entailment.
The RER/NHRS/ECT1000 hypotheses and independent grading remain separate research
work. Finite context, incomplete extraction, and Groq quota remain operating
limits. Tests and live deployment results are appended below when executed.

## Completed implementation and verification — 2026-11-10

CONFIRMED implementation:

- Student output ceilings are now 640/1280/2048 tokens. The Groq wrapper allows
  the requested ceiling plus a bounded 256-token GPT-OSS reasoning reserve.
  Deadlines and the final context ceiling remain enforced. Small windows can
  reclaim output allowance to retain a usable complete source with its metadata.
- Query-matching heading prefixes recover contiguous descendants, including
  working steps incorrectly represented as separate leaf headings. Selection
  prioritizes the label's own query overlap before inherited overlap and depth;
  this prevents a partially matching leaf from defeating its full-topic parent.
  Specific leaf questions retain their narrower scope. Calls without a question
  keep legacy exact-heading behavior. Overlapping recovered ranges deduplicate
  source IDs while counting already supplied passages toward coverage.
- Diagram retrieval keeps the byte-bounded expanded text when adding up to four
  visual candidates. Prompt fitting reports any later omissions explicitly.
- Extractive fallback permits up to 6/10/14 distinct exact sentences. Matching
  persisted headings retain separate shaft/generator chunks with their own
  citations; explicit multipart questions receive initial coverage per part.
  Full source sentences are preserved, including their causal subjects. Repeated
  excerpts retain every original citation. Independent unheaded blocks are not
  joined into an inferred relationship.

Final command, from backend (environment variable applies only to this process):

```powershell
$env:DOCUMIND_TEST_POSTGRES_CONTAINER='documind-db-1'
.\venv\Scripts\python.exe -m pytest -q tests/unit/generation tests/unit/orchestration tests/integration/generation/test_topic_context_postgres.py
```

Result: **466 passed**, two existing deprecation/future warnings, 20.08 seconds.
The PostgreSQL tests execute the actual topic SQL over synthetic, shadowing CTEs
inside READ ONLY transactions. They neither provision nor mutate a database.
They cover owner isolation, repeated-section boundaries, late seeds under byte
bounds, root/leaf questions, overlapping coverage and exact source provenance.
Regressions demonstrated failure before the fix for actual VAWT headings,
diagram fusion truncation and independently chunked fallback working steps.
Independent role-scoped review found no remaining implementation blocker in
these changes. `git diff --check` passed.

Live retrieval → Groq → final lexical verification checks used the existing
module 4.pdf index and the same question, “Explain Vertical Axis Wind Turbines
(VAWT) with a neat diagram.” No generated answer was persisted to user chats.

| Format | Final words | Fitted sources | Total elapsed | Observed content |
|---|---:|---:|---:|---|
| 5 marks | 70 | 11 | 7883 ms | Wind interaction, rotor rotation, shaft transmission, generator conversion |
| 10 marks | 139 | 13 | 8465 ms | Full working sequence plus lift/drag and wind-alignment explanation |
| 15 marks | 172 | 13 | 7851 ms | Full working sequence, orientation, wind alignment and explicit conversion chain |

All three returned non-abstained answers with valid source references under the
existing lexical verifier. Both shaft and generator evidence reached the model
and appeared in the final answers. These are individual cold-process checks,
not latency percentiles, academic grades or a controlled research improvement.
Word counts are observations, not output targets: the 5-mark answer added missing
mechanism steps despite being shorter than the earlier incomplete sample.

Material observed limits: prompt fitting still omitted some retrieved material;
claim filtering still removed parts of drafts; each of these three stateless
samples rejected its generated text diagram. Existing source-page figure
display is a separate capability; these checks do not establish reliable generated
diagrams or full 15-mark academic completeness. The selected topic's full
working sequence is improved; comprehensive coverage across arbitrary layouts,
all related subtopics and independently graded marks remains unverified.

Local deployment uses a derived backend image containing only the five changed
runtime modules over the existing provisioned image. No dependencies or model
weights were downloaded. The previous image is retained as
`documind-backend:before-depth-20261110` for rollback. Source, environment and
upload files retain their separate repository/data boundaries.

### Final fallback gate and release verification

An additional live fallback check found a formatting failure after duplicate
citations: `Sentence. [1] [10]` was split into a factual claim and an unsupported
reference-only fragment. The fallback now uses the existing citation-placement
helper to render `Sentence [1] [10].` for both initial and duplicate references.
The verifier and its thresholds are unchanged. New regressions require the
complete rendered fallback to pass verification, not just contain the sources.

After this correction, the full command above passed **469 tests**, with the
same two existing warnings, in **22.19 seconds**. Read-only checks against the
actual indexed VAWT chunks confirmed that all three fallback formats include
shaft transmission and generator conversion and pass lexical verification:
6 claims for 5 marks and 7 claims each for 10 and 15 marks. All retain distinct
source references. Final local API health through the frontend proxy returned
HTTP 200. The release image was rebuilt and the backend restarted with the
final citation fix. The prior image remains available for rollback.
