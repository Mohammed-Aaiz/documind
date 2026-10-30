# DocuMind --- Product & UX Design Specification

## Current design decision — 2026-10-27

This section supersedes the older cinematic direction below for the owner-requested
rebuild. The working surface is a calm reading and writing tool: warm neutral canvas,
dark ink navigation, teal Student accents and indigo Research accents. Avoid continuous
3D rendering on the main workspace. Use readable line lengths, semantic headings,
visible focus, generous whitespace and reduced-motion support.

Keep the five top-level destinations. Workspace contains a persistent Student/Research
switch, a document library, workspace-specific chat history, a focused answer area and
inspectable source evidence. Switching restores that mode's active chat and unsent
draft, cancels an in-flight text request, and ends any microphone/voice session. Do not
briefly show the previous workspace's messages during loading or apply a late answer
to the newly selected workspace. Explicitly distinguish an empty history from a failed
history request. Histories remain scoped by authenticated account as well as workspace.

Student mode offers exam answers at 5/10/15 marks, explanation, revision and practice.
Marks control required coverage and development, never a promised examination score.
Research mode offers evidence synthesis, source comparison, critical appraisal and
gap exploration. Gaps are gaps in the supplied corpus, not claims of global research
novelty. Both modes can inspect citations and export useful text; generated source
content is rendered as text, never trusted HTML.

Show which answer provider is selected and whether evidence stays local or is sent to
Groq. Provider availability must come from the server; do not display a green ready
state merely because a model name is configured. Keep keys out of browser storage and
the interface. Streamed draft text is provisional. Final citation checks are evidence
checks with stated limits, not proof that all claims are correct.

Voice has visible listening, transcribing, answering, speaking, interrupted and error
states, with an accessible stop control. Microphone use begins only from the user's
action. Offer text entry when voice is unavailable. Switching modes must never carry
an active call into the other mode. Report measured response timings without invented
targets or percentage improvements.

## 01. Design Purpose

DocuMind is a dark, premium, cinematic AI workspace rather than a
generic enterprise dashboard.

The interface should feel focused, technical, trustworthy,
evidence-driven, and calm under complex workflows.

## 02. Visual Direction

Use: - black/deep navy foundation; - electric violet and cyber-cyan
accents; - restrained glassmorphism; - subtle 3D depth; - strong
hierarchy; - purposeful spacing; - readable typography; - high
information density without visual clutter.

Do not turn the interface into a generic admin dashboard.

## 03. Approved Information Architecture

Exactly five pages: 1. Login 2. Home / AI Workspace 3. Media
Verification 4. Reliability Center 5. Settings / Account

## 04. AI Workspace Interaction

The user can: 1. upload/select a document; 2. ask a natural-language
question; 3. see the answer; 4. inspect evidence; 5. understand which
retrieval path contributed; 6. inspect reliability signals when
available.

The UI must not imply certainty when the backend reports marginal,
unresolved, failed, or unavailable states.

## 05. Evidence UX

Useful signals include: - source document; - page; - section/heading
path; - evidence excerpt; - retrieval path; - semantic/structural
contribution; - path agreement; - evidence coverage; - structural hops
where available.

If the backend did not produce a value, do not fabricate it.

## 06. State Design

Important operations need explicit: - idle; - loading/processing; -
success; - empty; - marginal; - unresolved; - unavailable; - error.

Do not use a success visual for an unavailable capability.

## 07. Accessibility

Maintain readable contrast, keyboard-accessible controls, visible focus
states, meaningful labels, useful error associations, and do not encode
critical information only through color.

## 08. Responsive Behavior

Desktop is the primary target. Layouts should degrade gracefully on
smaller screens without creating a separate product concept.

## 09. Component Rules

Prefer reusable components for navigation, document cards, upload
states, chat messages, evidence blocks, reliability indicators, loading
states, empty states, error states, and dialogs.

Do not duplicate API logic across components. Use the central typed API
client.

## 10. API Truthfulness

The UI mirrors backend truth.

Examples: - backend unavailable → UI says unavailable; - no evidence →
no invented source; - no reliability record → no invented score; -
processing error → actual error state.

## 11. Design Review Gate

Before implementation: - confirm user flow; - confirm page ownership; -
confirm component reuse; - confirm API contracts; - identify
loading/empty/error/unavailable states; - identify accessibility
concerns.

After implementation: - run the frontend build; - inspect actual browser
output when available; - verify console/runtime errors; - verify
important non-happy-path states.
