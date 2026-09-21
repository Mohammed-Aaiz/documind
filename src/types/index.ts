export type Page = 'login' | 'workspace' | 'verification' | 'reliability' | 'settings';

export interface DocumentFile {
  id: string;
  name: string;
  size: string;
  type: 'pdf' | 'docx' | 'txt';
  status: 'uploading' | 'processing' | 'ready' | 'error';
  chunkCount: number;
}

export interface ChatSource {
  chunkId: string;
  content: string;
  score: number;
  documentId: string;
  documentName: string;
  page: number | null;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'oracle';
  text: string;
  timestamp: string;
  sources?: ChatSource[];
  insufficientContext?: boolean;
}

/**
 * Media verification result — currently unavailable.
 * The backend analysis pipeline is not implemented yet.
 * The frontend must never fabricate these values.
 */
export interface VerificationResult {
  /** Analysis score from 0-100. Null when pipeline is unavailable. */
  score: number | null;
  /** Verdict from the detector. Null when pipeline is unavailable. */
  verdict: 'SYNTHETIC' | 'AUTHENTIC' | 'SUSPICIOUS' | null;
  /** Lip-sync drift measurement. Null when pipeline is unavailable. */
  lipSyncDrift: 'High' | 'Medium' | 'Low' | null;
  /** Blink rate measurement. Null when pipeline is unavailable. */
  blinkRate: 'Abnormal' | 'Normal' | null;
}

export interface ReliabilityEvidence {
  qaConfidence: number;
  retrievalScore: number;
  avgRetrievalScore: number;
  sourceCount: number;
  uniqueDocuments: number;
  factualGrounded: boolean;
  insufficientContext: boolean;
}

export interface ReliabilitySourceRef {
  id: string;
  documentId: string;
  documentName: string;
  content: string;
  relevanceScore: number;
  page: number | null;
  status: 'VERIFIED' | 'MARGINAL' | 'UNRESOLVED';
}

export interface ReliabilityQueryData {
  question: string;
  answer: string;
  qaConfidence: number;
  retrievalScore: number;
  avgRetrievalScore: number;
  sourceCount: number;
  uniqueDocuments: number;
  factualGrounded: boolean;
  insufficientContext: boolean;
  sources: ReliabilitySourceRef[];
}

export interface SourceRef {
  id: string;
  docId: string;
  relevanceScore: number;
  extractionNode: string;
  status: 'VERIFIED' | 'MARGINAL' | 'UNRESOLVED';
}

export interface ChatSession {
  id: string;
  createdAt: string;
  preview: string;
}

export interface PersistedMessage {
  id: string;
  sender: 'user' | 'oracle';
  content: string;
  createdAt: string;
}

export interface UserProfile {
  name: string;
  email: string;
  avatarUrl?: string;
}

export interface AppSettings {
  profile: {
    name: string;
    email: string;
    avatarUrl: string;
    clearance: string;
  };
  security: {
    twoFactor: boolean;
    e2eEncryption: boolean;
  };
  aiProcessing: {
    depth: number; // 1–5
    contextWindow: 'session' | '24h' | 'persistent';
  };
  environment: {
    theme: 'dark-cyber' | 'light';
    density: 'standard' | 'high';
    glassIntensity: number; // 0–100
  };
}
