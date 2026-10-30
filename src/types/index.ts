export type Page = 'login' | 'workspace' | 'verification' | 'reliability' | 'settings';
export type WorkspaceMode = 'student' | 'research';
export type WorkspaceTask = 'answer' | 'explain' | 'revision' | 'practice' | 'synthesis' | 'comparison' | 'critique' | 'gaps';

/**
 * Backend document status as represented in the UI.
 *
 * `partial` = at least one page produced usable content and at least one page
 * did not: the document is searchable but incomplete.
 * `unknown` = a status this UI does not recognise. It is rendered explicitly
 * rather than assumed to be `ready` or still processing.
 */
export type DocumentStatus =
  | 'uploading'
  | 'processing'
  | 'ready'
  | 'partial'
  | 'error'
  | 'unknown';

export interface DocumentFile {
  id: string;
  name: string;
  size: string;
  type: 'pdf' | 'docx' | 'txt';
  status: DocumentStatus;
  chunkCount: number;
}

/**
 * Which retrieval path(s) found a source. `semantic` = pgvector, `structural` =
 * document-graph traversal, `hybrid` = both. Null/undefined means the backend
 * did not report provenance (older server), never that a score was computed.
 */
export type RetrievalPath = 'semantic' | 'structural' | 'hybrid';

/**
 * Granularity of a persisted evidence record. `chunk` = a `document_chunks`
 * row; `structure_element` = a `document_structure_elements` row reached by
 * the element-level structural stream; `table_row` = a `document_table_rows`
 * row offered by the query-gated compact table-evidence band. Null/undefined
 * means the backend did not report it (e.g. an older server), never that an
 * element/row was retrieved.
 */
export type EvidenceKind = 'chunk' | 'structure_element' | 'table_row';

export interface ChatSource {
  chunkId: string;
  content: string;
  score: number;
  documentId: string;
  documentName: string;
  page: number | null;
  /** Retrieval path provenance, when the backend supplies it. */
  retrievalPath?: RetrievalPath | null;
  /** Reciprocal-rank-fusion score. NOT a similarity — `score` remains that. */
  fusionScore?: number | null;
  /** Graph hops from the nearest structural seed (0 = the seed). */
  structuralHops?: number | null;
  /** Heading hierarchy, when the chunk carries structure metadata. */
  headingPath?: string[] | null;
  /** Nearest ancestor heading text. */
  section?: string | null;
  /** Entity-relation knowledge graph traversal trail, when the backend used it. */
  knowledgeGraphPath?: string | null;
  /** Traversal edge count in the entity-relation graph. */
  knowledgeGraphHops?: number | null;
  /** Relation predicate supporting this graph path. */
  knowledgeGraphPredicate?: string | null;
  /** Exact source quote used to support the relation. */
  knowledgeGraphQuote?: string | null;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'oracle';
  text: string;
  timestamp: string;
  sources?: ChatSource[];
  insufficientContext?: boolean;
  /**
   * Sources retrieved before the QA model's context window was applied.
   * Reported by the backend; undefined means the server did not report it
   * (never a guessed value).
   */
  retrievedSourceCount?: number;
  /**
   * Sources that were retrieved but *withheld* from the QA model because the
   * context window was full. They are not evidence for the answer, so the UI
   * states the count instead of presenting them as support.
   */
  omittedSourceCount?: number;
  /**
   * Which engine produced this answer, when the backend reports it.
   *
   * `instruct` is the conversation path's instruction-following model;
   * `deterministic-table` / `deterministic-list` mean the backend read the
   * answer directly from a table cell or list item instead of generating it.
   * All values come from the server — the UI never infers one.
   */
  engine?:
    | 'generative'
    | 'extractive'
    | 'instruct'
    | 'ollama'
    | 'groq'
    | 'deterministic-table'
    | 'deterministic-list';
  /** Requested academic answer format (marks). */
  marks?: number;
  /**
   * Deterministic verification of a generative answer. `undefined` means the
   * answer came from the extractive path or an older server — it does **not**
   * mean the answer was verified.
   */
  verification?: {
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
  };
  /** Honest warnings from the backend (unsupported claims, withheld answer). */
  warnings?: string[];
  model?: string;
  latencyMs?: number;
  streaming?: boolean;
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
  retrievalPath?: RetrievalPath | null;
  fusionScore?: number | null;
  structuralHops?: number | null;
  /**
   * `chunk`, `structure_element` or `table_row` — which persisted record backs
   * this source. Never inferred from the score.
   */
  evidenceKind?: EvidenceKind | null;
  /**
   * Nearest ancestor heading text, reported by the endpoint when the source
   * recorded one at ingestion. Null for legacy chunks that recorded none — an
   * honest not-recorded state, never a fabricated value.
   */
  section?: string | null;
  /** Parser element type (`section`, `paragraph`, `table`, ...), reported when recorded. */
  elementType?: string | null;
  /**
   * Table-row provenance (`evidenceKind === 'table_row'` only): the aggregate
   * `table` structure element the row belongs to. Null for every other kind.
   */
  tableElementId?: string | null;
  /** 0-based row index inside that table (header row is 0). Table rows only. */
  rowIndex?: number | null;
  /** Whether the row's content embeds the table's header row. Table rows only. */
  headerRepeated?: boolean | null;
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
  /** Real path counts computed by the backend — never estimated in the UI. */
  semanticSourceCount?: number;
  structuralSourceCount?: number;
  /** Of the structural sources, how many are element-level (`structure_element`). */
  structuralElementSourceCount?: number;
  /** Of the structural sources, how many are compact table rows (`table_row`). */
  tableRowSourceCount?: number;
  hybridSourceCount?: number;
  structuralHopMax?: number;
  pathAgreement?: boolean;
  /**
   * Generative-path metadata for this query. Absent/null means the extractive
   * baseline produced the answer — never that verification passed.
   */
  generation?: {
    engine: 'generative';
    model: string;
    answerFormat: string;
    marks: number;
    latencyMs: number;
    abstained: boolean;
    verification: {
      claimCount: number;
      supportedClaims: number;
      unsupportedClaims: string[];
      uncitedClaims: number;
      citationAccuracy: number;
      verified: boolean;
      status?: string;
      wrongEntityClaims?: string[];
    };
    warnings: string[];
  } | null;
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
  workspace?: WorkspaceMode;
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
