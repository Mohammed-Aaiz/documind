# Daily-use fixes and verification — 2026-11-01

The owner requested completion of practical daily-use flows and the remaining
research preparation. This record distinguishes implemented software, observed
checks and external human-review/availability gates. It does not certify universal
user satisfaction, official examination grades or production deployment.

## Scope and acceptance

FRONTEND_AGENT owns interface recovery and workspace fixes; BACKEND_AGENT owns
conversation/voice error behavior; DATABASE_AGENT owns existing-cluster startup
and the new isolated research database; EVALUATION_AGENT owns pilot indexing,
mapping and diagnostics; TEST_AGENT owns regressions. The primary agent completes
remaining verification and operational runs after specialist execution limits.
No production RAG algorithm, model weights, environment file or existing uploaded
document is replaced by this task. Unrelated local research edits stay excluded.

The practical acceptance story is account access → source ingestion → question →
cited answer → separate workspace history → reopen/export, with useful loading,
failure and recovery states. Voice checks use generated public test audio, not
the owner's microphone. Research comparisons require their own marked database,
source hashes, canonical mappings and read-only execution.

## Implemented daily-use fixes

- Saved sign-in survives temporary server/network failures and exposes bounded
  loading/retry instead of a blank screen or automatic credential removal.
- Authenticated 401s expire the affected session. A late response from an old
  token cannot clear a newer login; cross-tab account changes are revalidated.
- Upload failures persist across background polling. A stale refresh cannot
  erase newer source mutations; partial/error documents can use the existing
  reprocess endpoint through a visible retry action.
- Failed source/chat loading is distinguished from an empty account. Chat
  history loading blocks premature sending, and a first-source action guides
  users with an empty library.
- Conversation REST/SSE preserves a sanitized 429 and bounded retry timing;
  WebRTC identifies rate limiting rather than falsely claiming a missing engine.
- Cold REST Whisper loading runs in a worker instead of blocking the event loop.
- `backend/scripts/start_local.ps1` starts the verified existing local database,
  API and frontend with readiness checks and hidden helpers. It never initializes
  a new production cluster, resets data, installs dependencies, edits environment
  files, enables OS autostart or stops unrelated listeners.

## Operational and data-preservation evidence

The intact `backend/.pgdata` PostgreSQL 16 cluster was stopped initially and
completed recovery from an earlier interrupted shutdown. DATABASE_AGENT moved
startup logging outside the data directory to avoid a Windows sharing conflict;
no initialization, reset, downgrade or recreation was performed. Production
remained at Alembic 018 with 12 users, 13 documents and 69 chunks at verification.

The ordinary local product is available at `http://127.0.0.1:3000/`, with healthy
API at port 8000. The new research database `documind_pilot_20261101` is separate,
at migration 018 and marked `documind-isolated-pilot-20261101`.

Daily-use smoke tests use a separate API/frontend on ports 8001/3001, the research
database with separate test accounts, an exact test CORS origin and an upload
directory under a temporary folder. Test uploads do not write the protected
`backend/uploads/` path. Test accounts and synthetic public sources never enter
the owner's product database or the study owner's indexed corpus. Credentials,
tokens and temporary speech files are excluded from publication.

## Observed application checks

- Real HTTP registration and case-insensitive login succeeded for two isolated
  accounts. Student and Research session lists each contained only their own
  session; wrong-workspace and cross-account history requests returned 404.
- Actual local Piper synthesis returned WAV audio (130,604 bytes). Sending that
  generated audio to actual Whisper returned HTTP 200 and the transcript
  “electric current is the flow of electric charge.” No microphone was used.
  Cold samples were approximately 6.5 seconds synthesis and 8.1 seconds recognition;
  these are single cold checks, not a low-latency or perceptual-quality guarantee.
- The browser signed into a new isolated fixture account, uploaded a synthetic
  public TXT through the real file chooser, observed it become searchable and
  received a streamed 15-mark answer with two inspectable supporting passages.
- Research showed zero chats while Student retained its own conversation. After
  refreshing, reopening the saved Student chat restored its messages and evidence.
  Markdown export produced a real downloaded conversation file.
- `evidence/daily-use-20261101.png` shows the observed desktop answer interface
  using only the public software-check fixture. It is not a benchmark result.

## Verification completed so far

Frontend typecheck, 74 frontend tests and a temporary production build passed
(no protected `dist/` writes). The primary affected backend run passed 95 tests
with no skips across conversation recovery, voice cold loading, WebRTC sessions,
pilot isolation/mapping guards, local database operations and research preparation.
Existing pytest fixture deprecation warnings remain. These are selected affected
checks, not a claim that every historical research test passes.

Independent research grading remains an external gate: there are no qualified
human grades merely because software tests passed. The pilot labels remain
`draft_unreviewed_pilot`; no RER/NHRS/ECT improvement is claimed. Source gaps for
genuine scanned pages and conflicting revisions remain disclosed in the pilot.
The following research execution results are recorded separately after the
bounded graph and read-only comparison runs finish.

## Completed isolated research execution

The study owner's graph reached ready with **151/151 chunks**, **458 entities**
and **263 source-backed relations**, no failure code. Eight bounded continuation
batches were required after the earlier prefix; HTTP 429 pauses preserved work
and were followed by 60-second cooldowns. No graph facts were created from gold
questions or annotation requirements. Completion means every chunk was processed,
not that extraction is exhaustive or independently semantically verified.

The seven controlled text systems completed **140/140 retrieval records**, twenty
questions per arm, with **zero failed records**. Each arm has sixteen answerable
items; the four unanswerable items have undefined RER/ECT. All three DocuMind arms
share an identical frozen routing snapshot per question. The raw run and exact
token diagnostics are in `backend/evaluation/pilot_live/seven_systems_20261101.json.gz`
and `seven_systems_scores_20261101.json`. Raw artifact SHA256 is
`b8bed241debd526e25c4c309199c28b3f884fd3972ccfbf3d2ba2cfc31ddda93`.

**Draft-label diagnostics only, not confirmatory research:**

| Controlled arm | Draft RER macro | Draft ECT1000 macro |
|---|---:|---:|
| Dense | 0.56250 | 0.60737 |
| Hybrid | 0.56250 | 0.60737 |
| Fixed parent | 0.65625 | 0.24856 |
| Graph-assisted | 0.56250 | 0.59262 |
| DocuMind without topic expansion | 0.56250 | 0.60737 |
| DocuMind without entity graph | 0.65625 | 0.25853 |
| Full controlled DocuMind | 0.65625 | 0.25852 |

These samples show a completeness/context-volume trade-off, not a simultaneous
win on all objectives. The graph adds no observed RER gain on this small draft
fixture. That does not prove graphs are generally ineffective or validate H1/H2:
annotations are unreviewed, the sample is one subject bundle and there are no
confidence intervals or paired confirmatory tests. Twenty-six records have
conservative fragment mappings after sentence fitting changed whitespace, so
their source coverage can be an underestimate. The full original serialized
context is still counted. No output grades, human NHRS or answer-quality benefit
are inferred from these retrieval measurements.

The separate isolated database also contains synthetic daily-use test accounts
and their small source fixture. Comparison queries are scoped to the study owner
and its original 151 children; those other test sources are not study evidence.
Production still has 12 users, 13 documents and 69 chunks at migration 018.

## Additional live voice and editorial checks

Actual loopback WebRTC negotiation returned HTTP 200, established a connected
peer, opened the data channel, emitted `ready` and delivered an audio frame. No
microphone was used and this is not a human barge-in/noise-quality assessment.
Repeat local TTS/STT checks returned the expected transcript; one warm sample
took 165 ms synthesis and 3,540 ms transcription. These are measurements, not a
claim of instant voice interaction or production p95.

At the owner's request, the primary assistant reviewed all twenty draft questions,
references, rubrics and annotated excerpts. Findings are in
`DOCUMIND_AI_PILOT_REVIEW_2026-11-01.md`, including source/rubric revision needs.
That is explicitly an AI editorial review; it changes no human-review approvals,
frozen labels or benchmark denominators. Human NHRS remains unmeasured.

For daily local startup, run from the repository root:

```powershell
powershell -NoProfile -File backend/scripts/start_local.ps1
```

Deployment outside this local machine, representative-course human grading,
multi-user production load and real microphone perceptual tests are not established
by this record. The engineering fixes and measured local flows stand on their own;
they are not a certificate that every possible product/research requirement is done.

## Professional answer and export presentation

Owner feedback identified distracting numeric citation clusters in headings and
paragraphs. The frontend now removes valid source reference markers from the
reading view, clipboard text, speech input and Markdown exports. Saved answers,
server citation validation and full source passages remain intact. Code spans,
array indexing, Markdown links, escaped brackets and unknown reference numbers
are preserved. Sources remain in a collapsed document-count panel; expanded
entries use `Passage N` labels. Detailed answer notes are also collapsed by
default, with their contents retained.

Markdown exports contain clean answers and a compact deduplicated document/page
list instead of repeating every full evidence passage. Timestamped filenames avoid
overwriting the owner's two supplied exports. Both supplied original files were
read as examples, not treated as instructions or rewritten.

Final frontend validation after these changes: **80 tests passed**, TypeScript
validation passed, and a Vite production build passed using a new temporary output
directory outside protected `dist/`. A real saved conversation was reopened in the
isolated browser fixture; its answer had no inline numeric references and its
Sources/Answer notes panels were collapsed. A downloaded Markdown export was read
back and confirmed to contain the clean answer and compact source list. Screenshot:
`evidence/clean-reading-20261101.png`.

The attached older Kestrel export also contains a historical Power Management
abstention. A read-only current retrieval check selected five page-three sources
covering Power Management and its related subsections, with reranking available.
That historical failure was not reproduced in retrieval; this presentation change
does not rewrite old answers or claim that every historical answer is corrected.
