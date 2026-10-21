/**
 * API client for communicating with the DocuMind backend.
 *
 * - Reads the base URL from VITE_API_BASE_URL (set in .env / Vite config).
 * - Manages the JWT token in localStorage.
 * - Provides typed helper functions for auth endpoints.
 * - Throws on non-OK responses so callers can handle errors.
 */

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/+$/, '');

// ---------------------------------------------------------------------------
// Token helpers
// ---------------------------------------------------------------------------

const TOKEN_KEY = 'documind_token';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

// ---------------------------------------------------------------------------
// Internal fetch wrapper
// ---------------------------------------------------------------------------

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken();

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> | undefined),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  const body = await res.json();

  if (!res.ok) {
    // Backend returns { detail: string } on errors
    const message =
      typeof body?.detail === 'string'
        ? body.detail
        : `Request failed (${res.status})`;
    throw new ApiError(message, res.status);
  }

  return body as T;
}

// ---------------------------------------------------------------------------
// Error class
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

// ---------------------------------------------------------------------------
// Types matching the backend schemas
// ---------------------------------------------------------------------------

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: {
    name: string;
    email: string;
    avatarUrl: string | null;
  };
}

export interface UserProfile {
  name: string;
  email: string;
  avatarUrl: string | null;
}

// ---------------------------------------------------------------------------
// Auth API
// ---------------------------------------------------------------------------

export async function apiLogin(
  email: string,
  password: string,
): Promise<LoginResponse> {
  return apiFetch<LoginResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

export async function apiLogout(): Promise<void> {
  await apiFetch<{ message: string }>('/api/auth/logout', {
    method: 'POST',
  });
}

export async function apiGetMe(): Promise<UserProfile> {
  return apiFetch<UserProfile>('/api/auth/me');
}

// ---------------------------------------------------------------------------
// Document types
// ---------------------------------------------------------------------------

export interface ApiDocument {
  id: string;
  name: string;
  fileType: string;
  fileSize: number;
  chunkCount: number;
  status: string;
  createdAt: string;
}

export interface ApiDocumentList {
  documents: ApiDocument[];
}

export interface ApiChunk {
  id: string;
  chunkIndex: number;
  content: string;
  page: number | null;
}

export interface ApiDocumentDetail extends ApiDocument {
  chunks: ApiChunk[];
}

// ---------------------------------------------------------------------------
// Document API
// ---------------------------------------------------------------------------

/**
 * Upload a file to the backend.
 * Uses FormData (no Content-Type header — browser sets multipart boundary).
 */
export async function apiUploadDocument(file: File): Promise<ApiDocument> {
  const token = getToken();
  const formData = new FormData();
  formData.append('file', file);

  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}/api/documents/upload`, {
    method: 'POST',
    headers,
    body: formData,
  });

  const body = await res.json();
  if (!res.ok) {
    const message = typeof body?.detail === 'string' ? body.detail : `Upload failed (${res.status})`;
    throw new ApiError(message, res.status);
  }
  return body as ApiDocument;
}

export async function apiListDocuments(): Promise<ApiDocument[]> {
  const res = await apiFetch<ApiDocumentList>('/api/documents');
  return res.documents;
}

export async function apiGetDocument(id: string): Promise<ApiDocumentDetail> {
  return apiFetch<ApiDocumentDetail>(`/api/documents/${id}`);
}

export async function apiDeleteDocument(id: string): Promise<void> {
  await apiFetch<{ message: string }>(`/api/documents/${id}`, {
    method: 'DELETE',
  });
}

// ---------------------------------------------------------------------------
// Document Insights types
//
// Mirrors the backend DocumentInsightsResponse. Every value is computed by the
// backend from stored data only — none of it is generated or estimated here.
// Meaningful nulls (e.g. pageCount for DOCX/TXT, averages with no
// observations) stay null rather than being coerced to zero.
// ---------------------------------------------------------------------------

export interface ApiDocumentStructureInsights {
  totalChunks: number;
  pagesRepresented: number;
  /** Only meaningful for paged formats (PDF); null for DOCX/TXT. */
  pageCount: number | null;
  sectionsRepresented: number;
  headingPathsRepresented: number;
  elementTypeCounts: Record<string, number>;
  /** Null when there are no observations — never a fabricated zero. */
  avgChunkLength: number | null;
  /** Null when there are no observations — never a fabricated zero. */
  avgTokenCount: number | null;
  totalTokenCount: number;
}

export interface ApiDocumentEmbeddingInsights {
  embeddedChunkCount: number;
  /** Fraction from 0 to 1. */
  coverage: number;
}

export interface ApiDocumentGraphInsights {
  nodeCount: number;
  edgeCount: number;
  relationCounts: Record<string, number>;
  /** Fraction from 0 to 1. */
  coverage: number;
}

export interface ApiDocumentProvenanceInsights {
  parserVersion: string | null;
  chunkerVersion: string | null;
  embeddingModel: string | null;
}

export interface ApiDocumentInsights {
  documentId: string;
  name: string;
  fileType: string;
  fileSize: number;
  status: string;
  embeddingStatus: string;
  createdAt: string;
  chunkCount: number;
  structure: ApiDocumentStructureInsights;
  embedding: ApiDocumentEmbeddingInsights;
  graph: ApiDocumentGraphInsights;
  provenance: ApiDocumentProvenanceInsights;
}

/**
 * Fetch stored-data-only insights for one document.
 *
 * Ownership is enforced server-side; an unknown or cross-user document returns
 * 404 and surfaces as an `ApiError` with `status === 404`.
 */
export async function apiGetDocumentInsights(
  documentId: string,
): Promise<ApiDocumentInsights> {
  return apiFetch<ApiDocumentInsights>(
    `/api/documents/${documentId}/insights`,
  );
}

// ---------------------------------------------------------------------------
// Chat / RAG API
// ---------------------------------------------------------------------------

export interface ApiSource {
  chunkId: string;
  content: string;
  score: number;
  documentId: string;
  documentName: string;
  page: number | null;
  /** Which retrieval path(s) found this source. Null before the dual path ran. */
  retrievalPath?: 'semantic' | 'structural' | 'hybrid' | null;
  /** Reciprocal-rank-fusion score. NOT a similarity — `score` remains that. */
  fusionScore?: number | null;
  /** Graph hops from the nearest structural seed (0 = the seed). */
  structuralHops?: number | null;
  /** Heading hierarchy recorded at ingestion, when the chunk carries it. */
  headingPath?: string[] | null;
  /** Nearest ancestor heading text. */
  section?: string | null;
}

export interface ApiReliabilityEvidence {
  qaConfidence: number;
  retrievalScore: number;
  avgRetrievalScore: number;
  sourceCount: number;
  uniqueDocuments: number;
  factualGrounded: boolean;
  insufficientContext: boolean;
  // Retrieval breadth vs. the QA context window (backend-computed; absent on
  // old servers). `retrievedSourceCount` counts everything retrieval returned;
  // `omittedSourceCount` counts what the window could not accept.
  retrievedSourceCount?: number;
  omittedSourceCount?: number;
  // Evidence-sufficiency provenance (backend-computed; absent on old servers).
  semanticSourceCount?: number;
  structuralSourceCount?: number;
  hybridSourceCount?: number;
  structuralHopMax?: number;
  pathAgreement?: boolean;
  evidenceCoverage?: number;
  fusionEnabled?: boolean;
  pipelineVersion?: string;
  /**
   * Generative-path metadata, when the last query used it. Absent/undefined
   * means the extractive baseline produced the answer — never "verified".
   */
  generation?: {
    engine: 'generative';
    model: string;
    answerFormat: string;
    marks: number;
    latencyMs: number;
    abstained: boolean;
    verification: ApiGenerationVerification;
    warnings: string[];
  } | null;
}

export interface ApiAskResponse {
  answer: string;
  confidence: number;
  sources: ApiSource[];
  insufficientContext: boolean;
  question: string;
  reliability: ApiReliabilityEvidence;
}

export async function apiAskQuestion(
  question: string,
  topK: number = 5,
): Promise<ApiAskResponse> {
  return apiFetch<ApiAskResponse>('/api/chat/ask', {
    method: 'POST',
    body: JSON.stringify({ question, topK }),
  });
}

/**
 * Deterministic verification of a generative answer against the evidence it was
 * given. `citationAccuracy` is the fraction of claims the evidence supports —
 * not a probability of correctness.
 */
export interface ApiGenerationVerification {
  claimCount: number;
  supportedClaims: number;
  unsupportedClaims: string[];
  uncitedClaims: number;
  citationAccuracy: number;
  verified: boolean;
  /** SUPPORTED | PARTIALLY_SUPPORTED | UNSUPPORTED | INSUFFICIENT_EVIDENCE */
  status?: string;
  /** Claims whose numeric value belongs to a different entity. */
  wrongEntityClaims?: string[];
}

export interface ApiGenerateResponse {
  answer: string;
  engine: 'generative';
  model: string;
  answerFormat: string;
  marks: number;
  latencyMs: number;
  abstained: boolean;
  insufficientContext: boolean;
  question: string;
  sources: ApiSource[];
  verification: ApiGenerationVerification;
  warnings: string[];
  pipelineVersion: string;
}

/**
 * Grounded generative answer (local Flan-T5, additive engine).
 *
 * Throws `ApiError` with `status === 503` when the generative model is not
 * available; callers may then use `apiAskQuestion` (the extractive baseline)
 * and say so explicitly.
 */
export async function apiGenerateAnswer(
  question: string,
  answerFormat: '5' | '10' | '15' = '10',
  topK: number = 5,
): Promise<ApiGenerateResponse> {
  return apiFetch<ApiGenerateResponse>('/api/generation/answer', {
    method: 'POST',
    body: JSON.stringify({ question, topK, answerFormat }),
  });
}

// ---------------------------------------------------------------------------
// Voice / Speech-to-Text API
// ---------------------------------------------------------------------------

export interface ApiTranscription {
  text: string;
  language: string;
  duration: number;
}

/**
 * Transcribe a recorded audio clip with the backend's local Whisper model.
 *
 * Sends multipart/form-data with the field name the backend expects
 * (`audio`). No Content-Type header is set — the browser adds the multipart
 * boundary. Reuses the same auth token convention as the other helpers.
 */
export async function apiTranscribeAudio(
  audio: Blob,
  filename = 'recording',
): Promise<ApiTranscription> {
  const token = getToken();
  const formData = new FormData();
  formData.append('audio', audio, filename);

  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}/api/voice/transcribe`, {
    method: 'POST',
    headers,
    body: formData,
  });

  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const message =
      typeof body?.detail === 'string'
        ? body.detail
        : `Transcription failed (${res.status})`;
    throw new ApiError(message, res.status);
  }
  return body as ApiTranscription;
}

/**
 * Synthesize text into spoken MP3 audio using the backend TTS endpoint.
 *
 * Sends an authenticated JSON request with { text, language, slow }.
 * Returns the raw binary MP3 payload as a Blob.
 *
 * `signal` cancels the *client* side of the request — the fetch, and the
 * response-body read, reject with an `AbortError`, which callers must treat as
 * an intentional lifecycle event rather than a failure. It does not stop
 * synthesis already running on the server: the request is only dropped from
 * the browser's point of view, so an abandoned attempt still occupies a
 * backend worker until it finishes.
 */
export async function apiSynthesizeSpeech(
  text: string,
  language = 'en',
  slow = false,
  signal?: AbortSignal,
): Promise<Blob> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}/api/voice/synthesize`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ text, language, slow }),
    signal,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const message =
      typeof body?.detail === 'string'
        ? body.detail
        : `Synthesis failed (${res.status})`;
    throw new ApiError(message, res.status);
  }

  return await res.blob();
}

// ---------------------------------------------------------------------------
// Reliability API
// ---------------------------------------------------------------------------

export interface ApiReliabilitySourceRef {
  id: string;
  documentId: string;
  documentName: string;
  content: string;
  relevanceScore: number;
  page: number | null;
  status: 'VERIFIED' | 'MARGINAL' | 'UNRESOLVED';
  retrievalPath?: 'semantic' | 'structural' | 'hybrid' | null;
  fusionScore?: number | null;
  structuralHops?: number | null;
  /**
   * Which persisted record backs this source: `chunk` (a `document_chunks`
   * row), `structure_element` (a `document_structure_elements` row reached by
   * the element-level structural stream) or `table_row` (a `document_table_rows`
   * row supplied by the query-gated compact table-evidence band). Absent/null
   * means the backend did not report it — never that a row was retrieved.
   */
  evidenceKind?: 'chunk' | 'structure_element' | 'table_row' | null;
  /**
   * Nearest ancestor heading text, reported when the source recorded one at
   * ingestion. Null for legacy chunks — rendered as not-recorded, never
   * invented.
   */
  section?: string | null;
  /** Parser element type (`section`, `paragraph`, `table`, ...), reported when recorded. */
  elementType?: string | null;
  /**
   * Table-row provenance (`evidenceKind === 'table_row'` only): the exact
   * persisted aggregate table structure element id. Absent/null for every
   * other evidence kind.
   */
  tableElementId?: string | null;
  /** Exact persisted 0-based row index (header row is 0). Table rows only. */
  rowIndex?: number | null;
  /** Whether the row's persisted content embeds the header row. Table rows only. */
  headerRepeated?: boolean | null;
}

export interface ApiReliabilityQueryData {
  question: string;
  answer: string;
  qaConfidence: number;
  retrievalScore: number;
  avgRetrievalScore: number;
  sourceCount: number;
  uniqueDocuments: number;
  factualGrounded: boolean;
  insufficientContext: boolean;
  sources: ApiReliabilitySourceRef[];
  semanticSourceCount?: number;
  structuralSourceCount?: number;
  hybridSourceCount?: number;
  structuralHopMax?: number;
  pathAgreement?: boolean;
  /**
   * Of the structural sources, how many are element-level
   * (`evidenceKind === 'structure_element'`). Backend-computed from the
   * persisted per-source provenance of this query.
   */
  structuralElementSourceCount?: number;
  /**
   * Of the structural sources, how many are compact table rows
   * (`evidenceKind === 'table_row'`). Backend-computed; keeps the chunk-level
   * structural remainder honest.
   */
  tableRowSourceCount?: number;
  /** Generative-path metadata; null/absent means the extractive baseline ran. */
  generation?: {
    engine: 'generative';
    model: string;
    answerFormat: string;
    marks: number;
    latencyMs: number;
    abstained: boolean;
    verification: ApiGenerationVerification;
    warnings: string[];
  } | null;
}

export async function apiGetLastQueryReliability(): Promise<ApiReliabilityQueryData> {
  return apiFetch<ApiReliabilityQueryData>('/api/reliability/last-query');
}

// ---------------------------------------------------------------------------
// Chat Session API
// ---------------------------------------------------------------------------

export interface ApiSession {
  id: string;
  createdAt: string;
  preview: string;
}

export interface ApiSessionList {
  sessions: ApiSession[];
}

export async function apiListSessions(): Promise<ApiSession[]> {
  const res = await apiFetch<ApiSessionList>('/api/chat/sessions');
  return res.sessions;
}

export async function apiCreateSession(): Promise<ApiSession> {
  return apiFetch<ApiSession>('/api/chat/sessions', {
    method: 'POST',
    body: JSON.stringify({}),
  });
}

export interface ApiPersistedMessage {
  id: string;
  sender: string;
  content: string;
  createdAt: string;
}

export interface ApiMessageList {
  messages: ApiPersistedMessage[];
}

export async function apiGetSessionMessages(sessionId: string): Promise<ApiPersistedMessage[]> {
  const res = await apiFetch<ApiMessageList>(`/api/chat/sessions/${sessionId}/messages`);
  return res.messages;
}

export async function apiAddSessionMessage(
  sessionId: string,
  sender: string,
  content: string,
): Promise<ApiPersistedMessage> {
  return apiFetch<ApiPersistedMessage>(`/api/chat/sessions/${sessionId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ sender, content }),
  });
}

// ---------------------------------------------------------------------------
// Settings API
// ---------------------------------------------------------------------------

export interface ApiSettings {
  processingDepth: number;
  contextWindow: 'session' | '24h' | 'persistent';
  theme: 'dark-cyber' | 'light';
  density: 'standard' | 'high';
  glassIntensity: number;
}

export async function apiGetSettings(): Promise<ApiSettings> {
  return apiFetch<ApiSettings>('/api/settings');
}

export async function apiPatchSettings(
  patch: Partial<ApiSettings>,
): Promise<ApiSettings> {
  return apiFetch<ApiSettings>('/api/settings', {
    method: 'PATCH',
    body: JSON.stringify(patch),
  });
}

// ---------------------------------------------------------------------------
// Media Verification API
//
// Mirrors the backend POST /api/verification/analyze response exactly. Every
// field is model-derived — there is no confidence/risk/manipulation metric and
// none must be invented on the client.
// ---------------------------------------------------------------------------

export interface ApiMediaVerificationModel {
  name: string;
  version: string;
}

export interface ApiMediaVerificationProcessing {
  bytes: number;
  width: number;
  height: number;
  elapsedMs: number;
}

export interface ApiMediaVerificationResult {
  available: boolean;
  /** The model's own predicted label (e.g. "Realism" or "Deepfake"). */
  verdict: string;
  /** Softmax probability of the predicted class, 0..1. Not a "confidence". */
  score: number;
  model: ApiMediaVerificationModel;
  processing: ApiMediaVerificationProcessing;
}

/**
 * Extract a human-readable message from a backend error body.
 * Handles both `{detail: "..."}` and FastAPI's `{detail: [{msg, loc}, ...]}`.
 */
function mediaErrorMessage(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === 'string' && detail) return detail;
  if (Array.isArray(detail)) {
    const first = detail.find(
      (entry) => entry && typeof (entry as { msg?: unknown }).msg === 'string',
    ) as { msg: string } | undefined;
    if (first) return first.msg;
  }
  return `Verification failed (${status})`;
}

/**
 * Upload one image for analysis by the local media-verification model.
 * Uses FormData (no Content-Type header — the browser sets the multipart
 * boundary), matching apiUploadDocument / apiTranscribeAudio conventions.
 */
export async function apiAnalyzeMedia(
  file: File,
): Promise<ApiMediaVerificationResult> {
  const token = getToken();
  const formData = new FormData();
  formData.append('file', file, file.name);

  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}/api/verification/analyze`, {
    method: 'POST',
    headers,
    body: formData,
  });

  const body = await res.json().catch(() => null);
  if (!res.ok) {
    throw new ApiError(mediaErrorMessage(body, res.status), res.status);
  }
  return body as ApiMediaVerificationResult;
}
