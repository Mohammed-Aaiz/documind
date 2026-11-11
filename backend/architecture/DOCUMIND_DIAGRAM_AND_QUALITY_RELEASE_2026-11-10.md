# Grounded diagrams and answer-quality review — 2026-11-10

## Decision and authorization

The owner explicitly requested completion of reliable generated diagrams and
independently graded answer quality after the student answer-depth update.
AI_AGENT owns generation/orchestration repairs, TEST_AGENT owns regressions,
EVALUATION_AGENT owns the new development quality pilot, FRONTEND_AGENT owns
any necessary rendering changes, and COORDINATOR records verification and
publishes scoped changes. Independent review is delegated separately from
implementation and reference-authoring.

Production changes remain Groq-only and preserve exact evidence provenance.
No frozen research dataset, score, model weight, environment file or uploaded
document is overwritten. The existing benchmark specification still governs
RER/NHRS/ECT1000 claims and the requirement for qualified human review.

## Failure evidence and minimal approach

The prior three VAWT samples each rejected their generated diagram. A new raw
capture from the existing index reproduced the issue: the model placed a figure
caption inside an unlabelled fence, wrapped labels across Unicode box rows and
mixed labelled and unlabelled connectors. The existing validator discarded it.
Separately, a regression demonstrated that individually supported labels could
pass despite an unsupported connection between them. Readable formatting must
not bypass relationship grounding.

Repair the existing diagram path and preserve it through final prose repair.
Where a model drawing cannot be accepted, derive a bounded generic sequence
diagram from explicit arrow chains or numbered working steps in supplied source
evidence. Preserve the source identity for every step. Explain that such a
figure represents a source-described process; do not infer physical geometry or
mechanical topology. A missing or unsupported subtopic receives an explicit
evidence gap instead of an invented figure. No subject-specific hardcoded
diagram, external image provider, extra generative call, dependency or relaxed
lexical-verification threshold is required.

## Acceptance and evaluation

- Actual VAWT and HAWT working questions produce a supported diagram that
  survives final answer verification in the shared product paths.
- Malformed, reversed or unsupported relationships remain rejected. Explicit
  multipart requests receive separate supported figures or named evidence gaps.
- Diagram derivation stays bounded and adds no provider round trip. Context,
  output, latency and source omissions remain visible and measured honestly.
- A new development-only quality pilot freezes source-backed rubrics before
  collecting final outputs and gives anonymized packets to two separate AI
  reviewers. It reports AI rubric assessments separately from human NHRS.
- Human review sheets remain blank until actual qualified reviewers submit
  them. The user previously volunteered for review; a second reviewer has been
  requested. Neither a model grade nor a coding-agent review fills a human slot.

The small development pilot is a release diagnostic, not the proposed reviewed
360-question benchmark or evidence that H1–H4 are confirmed. Local source notes
and candidate outputs remain outside Git publication pending source-rights
verification. Executed results and remaining limitations are appended below.

## First live pilot and targeted repairs — 2026-11-11

The development rubrics were frozen before generating answers. The first
read-only capture used the actual stateless product retrieval and answer service
on 12 prompts: VAWT, HAWT, multipart HAWT/VAWT, and an unsupported request,
each at 5/10/15 marks. There were 11 completed calls and one Groq HTTP 429
(HAWT 15). All three VAWT outputs retained a diagram; the HAWT and multipart
outputs did not. All three unsupported questions abstained. The first run is
preserved as failure evidence. It is not an NHRS or an improvement result.

Observed cause: the HAWT definition was indexed as a sibling of its working
paragraphs, and a page header split the second half into a different heading
root. Generic wind/turbine terms could select the VAWT parent for a HAWT query.
The mixed question could lose both named definitions during reranking. Repair
uses exact named-definition anchors, a bounded source window for damaged
heading metadata, and interleaved context for explicit question parts. Original
document, page, chunk, headings and text are retained; an inferred window is
reported as partial. No document is reprocessed and no model or index is changed.

An actual-corpus diagnostic with routing forced to semantic and no provider
calls recovered all six HAWT working steps. A wrapped label was rejected by
existing verification even though the same supplied evidence contained a valid
explicit six-component arrow chain. The diagram builder tries another verified
source representation when its first candidate cannot pass. This does not
relax the claim verifier or manufacture physical geometry.

Read-aloud and duplex speech skip fenced text diagrams. Written answers,
citations, export and copy retain them. Diagram-only speech points to the
written figure. The frontend production build and focused speech checks pass;
the production dependency audit reported zero issues with dev packages excluded.

## Final scoped implementation check — 2026-11-11

The source-derived diagram repair now renders concise cited step labels from
numbered source headings, so long wrapped source sentences do not turn into
uncited-looking fragments. Numbered design facts under a broad chapter heading
cannot invalidate a working sequence; non-process alignment statements are not
drawn as conversion steps. The final verifier still checks every label and
directed connection. On the actual frozen pilot excerpts, a zero-provider-call
replay of this final post-processor produced two separately verified figures
for the captured two-topic 10-mark response, and one verified figure for each
single-topic HAWT/VAWT 10-mark response. This replay changes diagrams only; the
original Groq capture remains preserved.

The live read-only pilot matched the pinned course PDF to one ready indexed
document. It produced 10 completed responses and two Groq HTTP 413 failures
(HAWT 15 marks and multipart 15 marks). The 5-mark multipart response abstained;
the three deliberately unsupported capacity/date prompts also abstained. These
failures remain in the private run and were not silently retried. A separate
post-processed review packet was graded by two isolated AI reviewers. The
tool-reported diagnostic mean normalized rubric scores were 0.567 for 5 marks,
0.900 for 10 marks, and 0.795 for 15 marks; the 15-mark figure contains only
one answerable response, and the 5-mark mean includes a withheld multipart
answer. These are small-sample AI diagnostics from AI-assisted rubrics, not
human NHRS, a comparative benchmark, or evidence that higher-mark answers are
consistently better.

Both offline human review forms remain blank (`not_measured`). The owner offered
to review, but the benchmark's independent-review requirement still needs a
second qualified human; AI reviewers do not fill that role. The 360-question
research dataset and comparative runs remain pending. The final scoped backend
gate passed 562 tests with two pre-existing dependency/fixture deprecation
warnings; the frontend production build and 32 focused voice/answer UI tests
also passed. The final source adjustment was verified against the actual
captured HAWT/VAWT passages without another hosted generation call.
