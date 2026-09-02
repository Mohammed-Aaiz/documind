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
// Chat / RAG API
// ---------------------------------------------------------------------------

export interface ApiSource {
  chunkId: string;
  content: string;
  score: number;
  documentId: string;
  documentName: string;
  page: number | null;
}

export interface ApiReliabilityEvidence {
  qaConfidence: number;
  retrievalScore: number;
  avgRetrievalScore: number;
  sourceCount: number;
  uniqueDocuments: number;
  factualGrounded: boolean;
  insufficientContext: boolean;
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
}

export async function apiGetLastQueryReliability(): Promise<ApiReliabilityQueryData> {
  return apiFetch<ApiReliabilityQueryData>('/api/reliability/last-query');
}
