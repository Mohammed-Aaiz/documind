# Multi-document evidence evaluation slice v1

Status: **proposed**. This document defines a diagnostic slice for the
DocuMind Benchmark Specification v1.0. It is not a reviewed dataset, an
executed evaluation, or a finding about the production pipeline. The current
20-question physics pilot uses one source bundle and has no conflicting
revisions; it cannot establish these multi-document outcomes.

## Dataset and review protocol

Select independently authored educational documents or permitted revisions
with recorded source rights. Keep related revisions and all questions that
share source material in the same document bundle and the same train/development
or held-out split. Freeze the source bytes and canonical text hashes before
annotation, with one-based page references, exact source offsets, document IDs,
document titles, and dates or revision identifiers where the source provides
them. Preserve missing or ambiguous dates as unknown. Do not invent source dates
or treat ingestion time as publication time.

Create separately tagged development and held-out questions covering:

1. **Repeated evidence**: distinct documents repeat the same fact with the same
   scope and conditions. Include both exact copies and independently authored
   quotations where rights permit.
2. **Paraphrases**: differently worded passages express the same claim, with
   matching entities, conditions, units, negation and scope.
3. **Updates**: revisions give different facts at different dates or under
   different versions. Ask both for the latest applicable revision and for a
   comparison of revisions; include missing-date and ambiguous-date cases.
4. **Contradictions**: documents make incompatible claims about the same entity,
   metric and conditions. Ask for the disagreement, and include superficially
   similar statements that differ only in a material number, condition, or
   negation.
5. **Distinct contributions**: related documents each supply a different
   required aspect, including named-document comparisons and corpus-wide
   synthesis, so repeated passages can compete with unique evidence.

Use overlapping tags rather than new mutually exclusive benchmark categories.
The five cases above can overlap. Record mark level, task, source universe,
answerability, reference answer and marking rubric. Label every claim with its
entity, predicate, value, unit, time, conditions and source revision where
relevant. Record explicit requested source IDs and distinguish a missing source
from an unanswered question. Annotate exact supporting and contradicting spans,
including table headers and surrounding qualifiers. Group only independently
reviewed equivalent claims; lexical similarity alone does not establish
equivalence. Mark one-sided or incomplete conflicts as incomplete evidence.

Two qualified reviewers independently annotate evidence requirements, citation
support, equivalence, conflict, revision applicability and the reference rubric.
Record their separate decisions and qualifications; adjudicate material
disagreements without overwriting originals. Reviewers must independently verify
the source dates and answerability. The current assistant cannot supply the two
independent human approvals. Freeze a new version and hashes before running the
held-out comparison; retain the existing pilot and benchmark assets unchanged.

## Measures

Use the existing RER, NHRS by marks, and ECT1000 definitions and paired
bundle-level analysis from the benchmark specification. The measures below are
additional diagnostics, reported with their denominators and missing cases:

* **Required-source recall**: distinct required document revisions represented
  by at least one qualifying final-context evidence span divided by required
  document revisions. A source counts only when the relevant annotated span is
  present, not merely its name or a duplicate's attribution. Where the question
  permits alternatives, use the smallest complete approved alternative source
  set and state that policy before scoring.
* **Unique-evidence retention**: required nonduplicate evidence units surviving
  final context fitting divided by required nonduplicate units available among
  retrieved candidates. Report candidate-stage and final-context RER beside it;
  the denominator is conditional on retrieval and cannot represent end-to-end
  recall. A zero denominator is undefined.
* **Duplicate context share**: tokens spent on independently annotated
  redundant evidence copies divided by total serialized evidence-context tokens.
  Record the approved tokenization and whether retained source labels are
  counted. Repetition needed to attribute an answer to a separately requested
  document is not automatically redundant. Report this only with positive exact
  context-token counts and report RER alongside it.
* **Conflict disclosure**: conflicts for which both supported sides are
  accurately described and attributed in the final answer divided by reviewed
  conflicts required by the question. Separately report false conflict and
  unresolved-conflict counts. No conflict in the denominator means undefined.
* **Citation attribution precision**: factual claim–source links judged supported
  by the cited passage and correct source revision divided by all emitted
  factual claim–source links. Separately report citation completeness as factual
  claims with at least one correct supporting citation divided by factual claims
  requiring one. Treat uncited claims as incomplete; no emitted links yields
  undefined precision, not a perfect score. Blind reviewers to system identity.

Also record wrong-revision selections, invented document-wide claims, missed
named documents, missed unique units, invalid citations, context truncations,
answer and provider failures, and review disagreements. Score the final
user-visible answer and exact final prompt context. A question requesting the
latest policy is correct only when the source's verified applicability and
version evidence justify that selection; unresolved dates should be disclosed.

Run the seven matched systems on identical frozen documents, source identities,
questions, per-mark context budgets, model settings and evaluation rules.
Report all questions and failures, per-category and per-mark counts, paired
bundle-level comparisons and uncertainty where the preregistered sample permits.
Do not turn pilot diagnostics into a claim of reliable multi-document behavior.
