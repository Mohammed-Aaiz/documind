# AI review of the educational pilot — 2026-11-01

Status: AI-assisted editorial/source review, **not independent qualified human
review**, not adjudicated gold and not NHRS. The owner explicitly asked whether
the assistant could perform the review. It can perform this additional check;
it cannot honestly supply two human reviewers or certify their qualifications.

Reviewed artifact: `backend/evaluation/pilot_v1/dataset.json`, SHA256
`1315cbb287e4650a109a82aa7fad8908c1673d1b54a63c74061961712e48866a`.
All 20 questions, reference answers, designated rubrics and supplied evidence
bundles were inspected. Exact-offset/hash checks are covered separately by the
software tests. This review compares the supplied canonical excerpts; it does
not independently re-transcribe every original PDF page or establish subject
expertise. Earlier AI verification visually checked the table on PDF page 871.

No annotations, review approvals, reference answers or frozen results have been
changed. Findings below are revision proposals for a separately versioned draft,
not retrospective edits made to improve measured scores.

## Findings applying across the pack

1. **Rubric anchors need finer detail.** Current content criteria commonly award
   full credit for the whole requirement, half for a material part and zero for
   omission/contradiction. That leaves materially different partial answers with
   the same broad score and risks disagreement. Specify subpoints and examples
   appropriate to each question, especially 10/15-mark answers. Organization and
   accuracy must not silently double-count a missing content point.
2. **Evidence-unit granularity is inconsistent.** A table unit bundles two values,
   two labels, units, category and temperature, while another unit may represent
   one conceptual claim. A partial table retrieval receives zero for that unit.
   Adopt an explicit atomic-requirement guide before freezing the larger dataset;
   retain joint-support bundles where the logical comparison genuinely requires
   both sides. Do not change the current denominator after seeing system scores.
3. **Math extraction is incomplete.** Some source quotations have missing symbols
   or incomplete clauses. Prose references can be physically sensible while the
   annotated evidence does not fully state their assumptions or equations. Repair
   these source/evidence gaps through a documented new canonical release or narrow
   the reference, rather than crediting information absent from the quoted source.
4. **Relational definitions need expert agreement.** R1–R4 are causal/variable
   chains across textbook topics. They are valid candidates for relational study,
   but they are not automatically equivalent to named-entity graph path questions.
   Reviewers must decide whether this matches H2's intended population before
   claiming that a GraphRAG result generalizes to educational multi-hop reasoning.
5. **Marks are expectations, not verified difficulty.** A short fact lookup can
   be designated five marks and an unanswerable item ten marks in this draft, but
   those allocations need examiner review. The presence of a rubric totalling
   5/10/15 does not establish its academic validity.

## Question-by-question review

“Provisionally consistent” means no material contradiction was found in the
inspected excerpts. It is an AI finding, not final scientific approval.

| ID | Finding | Required follow-up before a reviewed release |
|---|---|---|
| L1 | Provisionally consistent: positive-charge convention and opposite electron motion are explicitly supported. | Keep the metal/negative-carrier scope; a five-mark rubric should separately credit convention, carrier charge and direction. |
| L2 | Provisionally consistent: the quote defines ohmic behavior and rejects universal validity. | State fixed physical conditions, especially temperature, so independence from voltage/current is not read as independence from every operating condition. |
| L3 | Values and conductor category match the disclosed table transcription. | Two qualified reviewers must verify values, exponent, units and 20°C against the original table. Split content anchors and decide evidence-unit granularity consistently. AI transcription is not an independent gold label. |
| L4 | Provisionally consistent with the textbook's resistor/capacitor and charge-storage description. | Check whether this scope merits five marks; clarify that “stores charge” is the textbook convention and does not imply arbitrary net charge on an ideal complete capacitor. |
| D1 | Provisionally consistent: field propagation, slow drift, collisions and continuous input are supported across the page boundary. | Preserve the ordinary-conductor assumption and explicit superconducting exception; distinguish signal speed from carrier speed in the scoring anchors. |
| D2 | Provisionally consistent: length/area/material effects and the listed semiconductor contrast are supported. | Keep “listed semiconductors,” not all materials/temperatures. Add explicit partial-credit points for each geometric dependence and each temperature mechanism. |
| D3 | Provisionally consistent series/parallel comparison; required passages are separated by several pages. | Restore or explicitly exclude lost equation glyphs. Add separately scorable current, voltage and equivalent-resistance facts for both arrangements. |
| D4 | Reference physics is plausible, but the selected 0.632/0.368 quotations have missing time-constant symbols. | Add an intact definition linking the quoted time interval to one RC time constant, or repair the canonical math under a new release. Explicitly grade charging/discharging conditions and distinguish capacitor voltage from current. |
| M1 | Provisionally consistent: intended energy conversion, unwanted heating and shock are different concepts in the excerpts. | Keep this a qualitative source interpretation, not an operational electrical-safety certification; grade the distinctions separately. |
| M2 | Provisionally consistent: sign convention and time reversal distinguish different properties. | Do not generalize the excerpt's “steady state” phrasing into a claim that every one-direction current must have constant magnitude. |
| M3 | **Evidence alignment needs revision.** The simple-circuit quotation ends mid-clause; the reference additionally states larger internal resistance reduces current/terminal voltage without fully including that relationship in this question's annotated support. | Add complete source clauses supporting the load/wire assumption and internal-resistance relationship, or remove the extra claims from the reference. Preserve fixed-emf/load assumptions; increasing current at fixed internal resistance is a different comparison from changing resistance. |
| M4 | Provisionally consistent contrast between dissipation/current limitation and charge storage. | Keep an ideal/simple RC interpretation, and avoid treating charge storage and energy dissipation as interchangeable rubric points. |
| R1 | Provisionally consistent causal chain under a fixed voltage source; example powers are correctly described as example-specific. | Make the fixed-voltage assumption an explicit criterion and avoid demanding the textbook example's numbers when the question only asks for the mechanism. Confirm that each required graph relation is actually source-grounded. |
| R2 | Provisionally consistent battery-depletion → internal-resistance → charging-time chain is supported by the camera paragraph. | Preserve “can”/model assumptions rather than claiming every battery chemistry ages identically. Decide whether the later camera passage alone is an acceptable alternative support bundle; current gold may overrequire redundant earlier support. |
| R3 | Provisionally consistent fixed-power voltage/current/loss explanation and the textbook's AC rationale. | Keep line resistance and fixed transmitted power explicit. Do not extend the excerpt into a universal claim that AC is always preferable to DC or silently require transformer theory absent from the selected support. |
| R4 | Provisionally consistent within the shared-wire-resistance circuit example. | Explicitly constrain the explanation to this model. Real motor-start dimming has additional possible mechanisms; do not grade a universal real-world causal claim as if the simplified example proved it. |
| U1 | The requested numerical uncertainty is not given by the supplied table. | Do not infer a confidence interval merely from displayed significant figures. Confirm absence in the bounded selected corpus and grade a justified limitation, not a guessed value. |
| U2 | Exact device-specific recharge time after 1,000 cycles is unsupported. | A correct answer can still state qualitative RC dependencies; missing device values/condition and a recharge criterion must be identified rather than saying nothing useful can be inferred. |
| U3 | A graphene resistivity is not supplied by the selected table. | Keep the claim bounded to the selected source, not all physics literature; importing an external value would fail this source-grounded task. |
| U4 | The selected qualitative temperature/impurity discussion does not define a universal numerical dopant/temperature function. | Allow the supported qualitative explanation while refusing the requested unidentifiable numerical function; specify required material/model parameters and validity ranges in the rubric. |

## Result and next gate

The AI review found meaningful revision needs, especially M3 evidence alignment,
D4 math/context linkage, generic partial-credit anchors and R2's potentially
redundant required support. This is useful quality control, but it is not grounds
to mark the pack as independently reviewed. The existing diagnostic runs retain
their original draft dataset hash and limitations. There are still **zero human
annotation approvals and zero human answer grades**.

If qualified reviewers are unavailable, DocuMind can publish clearly labelled
AI-assisted development diagnostics and limitations. It cannot publish NHRS or
describe this review as two independent human assessments. A future revised draft
must receive a new version/hash, preserve this v1 and rerun the comparisons under
its own preregistered labels before any confirmatory research claim.

## Supplemental category-window check

Using the pinned GPT-OSS tokenizer and the current canonical page order, the
enclosing window from the first to last required span contains 82/88/53/26 tokens
for L1/L2/L3/L4 and 619/1505/1178/1080 for D1/D2/D3/D4. Thus these particular
annotated span sets match the proposed <=256 versus >256 contiguous-window split.
This mechanical check does not prove that every annotated span is necessary or
that a shorter, unannotated alternative would be insufficient. Those remain
annotation questions, particularly the redundant-support issue identified above.
