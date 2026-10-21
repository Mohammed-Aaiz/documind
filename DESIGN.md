# DocuMind --- Product & UX Design Specification

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
