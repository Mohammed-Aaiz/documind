import React, { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { apiGetDocumentInsights, ApiDocumentInsights, ApiError } from '../../lib/api';

interface DocumentInsightsPanelProps {
  documentId: string;
  onClose: () => void;
}

const GLASS = {
  background: 'rgba(5,7,10,0.70)',
  backdropFilter: 'blur(24px)',
  WebkitBackdropFilter: 'blur(24px)',
  borderTop: '1px solid rgba(255,255,255,0.1)',
  borderLeft: '1px solid rgba(255,255,255,0.1)',
};

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString();
}

/**
 * The backend's fixed failure vocabulary for a page that produced no usable
 * text. Unknown values are shown verbatim rather than guessed at, so a newer
 * server can add a reason without this panel mislabelling it.
 */
const FAILURE_REASON_LABEL: Record<string, string> = {
  no_text_layer: 'No text layer',
  ocr_disabled: 'OCR disabled',
  ocr_unavailable: 'OCR unavailable',
  ocr_failed: 'OCR found no text',
  ocr_budget_exhausted: 'OCR time budget spent',
};

const statusColor = (status: string) => {
  if (status === 'ready') return '#4cd7f6';
  if (status === 'processing') return '#d0bcff';
  if (status === 'uploading') return '#06B6D4';
  if (status === 'error' || status === 'failed') return '#ffb4ab';
  return '#958ea0';
};

const embeddingStatusColor = (status: string) => {
  if (status === 'ready' || status === 'embedded' || status === 'complete') return '#4cd7f6';
  if (status === 'processing' || status === 'pending') return '#d0bcff';
  if (status === 'error' || status === 'failed') return '#ffb4ab';
  return '#958ea0';
};

const StatCard: React.FC<{ label: string; value: React.ReactNode; hint?: string }> = ({
  label,
  value,
  hint,
}) => (
  <div className="rounded-lg p-3" style={{ ...GLASS }}>
    <span
      className="block text-outline mb-1"
      style={{ fontFamily: 'JetBrains Mono', fontSize: '9px', letterSpacing: '0.1em', fontWeight: 700 }}
    >
      {label}
    </span>
    <span className="text-on-surface font-semibold" style={{ fontFamily: 'Geist', fontSize: '22px', lineHeight: 1.1 }}>
      {value}
    </span>
    {hint && (
      <span className="block text-outline mt-1" style={{ fontFamily: 'JetBrains Mono', fontSize: '9px' }}>
        {hint}
      </span>
    )}
  </div>
);

const SectionHeading: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <h3
    className="text-outline mb-3"
    style={{ fontFamily: 'JetBrains Mono', fontSize: '10px', letterSpacing: '0.1em', fontWeight: 700 }}
  >
    {children}
  </h3>
);

const ProgressBar: React.FC<{ value: number; label: string; color?: string }> = ({
  value,
  label,
  color = '#06B6D4',
}) => {
  const pct = Math.max(0, Math.min(100, Math.round(value * 100)));
  return (
    <div
      role="progressbar"
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
      className="w-full h-2 rounded-full overflow-hidden"
      style={{ background: 'rgba(29,32,35,1)' }}
    >
      <div
        className="h-full rounded-full transition-all"
        style={{ width: `${pct}%`, background: color }}
      />
    </div>
  );
};

export const DocumentInsightsPanel: React.FC<DocumentInsightsPanelProps> = ({
  documentId,
  onClose,
}) => {
  const [data, setData] = useState<ApiDocumentInsights | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  const panelRef = useRef<HTMLDivElement>(null);
  const [entered, setEntered] = useState(false);

  const fetchInsights = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      setNotFound(false);
      const res = await apiGetDocumentInsights(documentId);
      setData(res);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setNotFound(true);
        setData(null);
      } else {
        setError(err instanceof Error ? err.message : 'Failed to load insights');
      }
    } finally {
      setLoading(false);
    }
  }, [documentId]);

  // Fetch only when the document changes — no polling, no per-render fetch.
  useEffect(() => {
    fetchInsights();
  }, [fetchInsights]);

  // Slide-in on mount.
  useEffect(() => {
    const id = requestAnimationFrame(() => setEntered(true));
    return () => cancelAnimationFrame(id);
  }, []);

  // Move focus into the panel on open.
  useEffect(() => {
    panelRef.current?.focus();
  }, []);

  // Escape closes the panel.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  const headingId = 'document-insights-heading';

  // Render through a portal so the panel is not confined to the workspace's
  // stacking context — otherwise the fixed TopNavBar paints over its controls.
  return createPortal(
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/50 transition-opacity"
        aria-hidden="true"
        onClick={onClose}
      />

      {/* Panel */}
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={headingId}
        tabIndex={-1}
        className="fixed top-0 right-0 bottom-0 z-50 w-full max-w-md flex flex-col transition-transform duration-300 ease-in-out focus:outline-none"
        style={{
          background: 'rgba(5,7,10,0.92)',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          borderLeft: '1px solid rgba(255,255,255,0.1)',
          boxShadow: '-4px 0 40px rgba(0,0,0,0.6)',
          transform: entered ? 'translateX(0)' : 'translateX(100%)',
        }}
      >
        {/* Header */}
        <div className="p-4 border-b border-white/5 flex items-start gap-3 flex-shrink-0">
          <div className="flex-1 min-w-0">
            <h2
              id={headingId}
              className="text-on-surface font-semibold truncate"
              style={{ fontFamily: 'Geist', fontSize: '18px' }}
              title={data?.name ?? 'Document Insights'}
            >
              {data?.name ?? 'Document Insights'}
            </h2>
            {data && (
              <div className="flex flex-wrap items-center gap-2 mt-2">
                <span
                  className="px-2 py-1 rounded border text-on-surface-variant"
                  style={{ fontFamily: 'JetBrains Mono', fontSize: '10px', borderColor: 'rgba(255,255,255,0.15)' }}
                >
                  {data.fileType.toUpperCase()}
                </span>
                <span className="text-outline" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px' }}>
                  {formatBytes(data.fileSize)}
                </span>
                <span
                  className="inline-flex items-center gap-1 px-2 py-1 rounded border"
                  style={{
                    fontFamily: 'JetBrains Mono',
                    fontSize: '10px',
                    color: statusColor(data.status),
                    borderColor: `${statusColor(data.status)}40`,
                    background: `${statusColor(data.status)}15`,
                  }}
                >
                  <span className="w-1.5 h-1.5 rounded-full" style={{ background: statusColor(data.status) }} />
                  {data.status.toUpperCase()}
                </span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-1 flex-shrink-0">
            <button
              onClick={fetchInsights}
              className="p-2 rounded-lg text-outline hover:text-cyber-cyan hover:bg-surface-bright/20 transition-colors"
              title="Refresh insights"
              aria-label="Refresh insights"
            >
              <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>refresh</span>
            </button>
            <button
              onClick={onClose}
              className="p-2 rounded-lg text-outline hover:text-on-surface hover:bg-surface-bright/20 transition-colors"
              title="Close insights"
              aria-label="Close insights panel"
            >
              <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>close</span>
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          {loading && (
            <div className="flex items-center justify-center py-16">
              <span className="material-symbols-outlined text-electric-violet animate-spin text-[28px]">
                progress_activity
              </span>
              <span className="ml-3" style={{ fontFamily: 'Inter', fontSize: '14px', color: '#cbc3d7' }}>
                Loading insights...
              </span>
            </div>
          )}

          {!loading && notFound && (
            <div className="rounded-xl p-6" style={{ ...GLASS, border: '1px solid rgba(255,180,171,0.3)' }}>
              <span className="material-symbols-outlined text-error block mb-2" style={{ fontSize: '28px' }}>
                search_off
              </span>
              <p className="text-on-surface mb-4" style={{ fontFamily: 'Inter', fontSize: '14px' }}>
                Document not found
              </p>
              <button
                onClick={fetchInsights}
                className="px-4 py-2 rounded-lg text-cyber-cyan hover:bg-surface-bright/10 transition-colors"
                style={{ ...GLASS, border: '1px solid rgba(255,255,255,0.1)', fontFamily: 'JetBrains Mono', fontSize: '11px' }}
              >
                RETRY
              </button>
            </div>
          )}

          {!loading && !notFound && error && (
            <div className="rounded-xl p-6" style={{ ...GLASS, border: '1px solid rgba(255,180,171,0.3)' }}>
              <p className="text-on-surface mb-4" style={{ fontFamily: 'Inter', fontSize: '14px' }}>
                {error}
              </p>
              <button
                onClick={fetchInsights}
                className="px-4 py-2 rounded-lg text-cyber-cyan hover:bg-surface-bright/10 transition-colors"
                style={{ ...GLASS, border: '1px solid rgba(255,255,255,0.1)', fontFamily: 'JetBrains Mono', fontSize: '11px' }}
              >
                RETRY
              </button>
            </div>
          )}

          {!loading && !notFound && !error && data && (
            <>
              {/* Document */}
              <section aria-labelledby="insights-doc-heading">
                <SectionHeading>DOCUMENT</SectionHeading>
                <div className="rounded-lg p-3 space-y-2" style={{ ...GLASS }}>
                  <div className="flex justify-between items-center gap-3">
                    <span className="text-outline" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px' }}>STATUS</span>
                    <span style={{ fontFamily: 'JetBrains Mono', fontSize: '11px', color: statusColor(data.status) }}>
                      {data.status.toUpperCase()}
                    </span>
                  </div>
                  <div className="flex justify-between items-center gap-3">
                    <span className="text-outline" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px' }}>EMBEDDING</span>
                    <span style={{ fontFamily: 'JetBrains Mono', fontSize: '11px', color: embeddingStatusColor(data.embeddingStatus) }}>
                      {data.embeddingStatus.toUpperCase()}
                    </span>
                  </div>
                  <div className="flex justify-between items-center gap-3">
                    <span className="text-outline" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px' }}>CHUNKS</span>
                    <span className="text-on-surface" style={{ fontFamily: 'JetBrains Mono', fontSize: '11px' }}>{data.chunkCount}</span>
                  </div>
                  <div className="flex justify-between items-center gap-3">
                    <span className="text-outline" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px' }}>CREATED</span>
                    <span className="text-on-surface-variant" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px' }}>{formatDate(data.createdAt)}</span>
                  </div>
                </div>
              </section>

              {/* Structure */}
              <section aria-labelledby="insights-structure-heading">
                <SectionHeading>STRUCTURE</SectionHeading>
                <div className="grid grid-cols-2 gap-2">
                  <StatCard label="TOTAL CHUNKS" value={data.structure.totalChunks} />
                  <StatCard label="PAGES REPRESENTED" value={data.structure.pagesRepresented} />
                  <StatCard
                    label="PAGE COUNT"
                    value={data.structure.pageCount === null ? '—' : data.structure.pageCount}
                  />
                  <StatCard label="SECTIONS" value={data.structure.sectionsRepresented} />
                  <StatCard label="HEADING PATHS" value={data.structure.headingPathsRepresented} />
                  <StatCard
                    label="AVG CHUNK LENGTH"
                    value={data.structure.avgChunkLength === null ? '—' : data.structure.avgChunkLength.toFixed(1)}
                  />
                  <StatCard
                    label="AVG TOKEN COUNT"
                    value={data.structure.avgTokenCount === null ? '—' : data.structure.avgTokenCount.toFixed(1)}
                  />
                  <StatCard label="TOTAL TOKENS" value={data.structure.totalTokenCount} />
                </div>
              </section>

              {/* Page extraction — which pages were read, and how */}
              {data.pages && (
                <section aria-labelledby="insights-pages-heading">
                  <SectionHeading>PAGE EXTRACTION</SectionHeading>
                  {!data.pages.recorded ? (
                    <div className="rounded-lg p-3" style={{ ...GLASS }}>
                      <span
                        className="text-outline"
                        style={{ fontFamily: 'JetBrains Mono', fontSize: '11px' }}
                      >
                        Not recorded for this document — it was processed before
                        per-page extraction provenance was stored.
                      </span>
                    </div>
                  ) : (
                    <>
                      <div className="grid grid-cols-3 gap-2">
                        <StatCard label="PAGES" value={data.pages.pagesTotal} />
                        <StatCard label="NATIVE TEXT" value={data.pages.nativePageCount} />
                        <StatCard label="READ BY OCR" value={data.pages.ocrPageCount} />
                        <StatCard
                          label="UNACCOUNTED"
                          value={data.pages.unaccountedPageCount}
                        />
                      </div>
                      <div className="rounded-lg p-3 mt-2" style={{ ...GLASS }}>
                        {data.pages.ocrPages.length === 0 &&
                        data.pages.unaccountedPages.length === 0 ? (
                          <span
                            className="text-outline"
                            style={{ fontFamily: 'JetBrains Mono', fontSize: '11px' }}
                          >
                            <span>Every page had a usable text layer.</span>{' '}
                            <span>{data.pages.nativePageCount} page{data.pages.nativePageCount === 1 ? '' : 's'} read from a native text layer.</span>
                          </span>
                        ) : (
                          <ul
                            className="space-y-2"
                            aria-label="Page extraction details"
                          >
                            {data.pages.ocrPages.map((page) => {
                              // One deterministic sentence per page, built from
                              // the recorded facts only — no estimates.
                              const meta = [
                                [page.ocrEngine, page.ocrEngineVersion]
                                  .filter(Boolean)
                                  .join(' '),
                                page.ocrRotation
                                  ? `read rotated ${page.ocrRotation}°`
                                  : null,
                                page.ocrSeconds !== null
                                  ? `${page.ocrSeconds.toFixed(1)}s`
                                  : null,
                                `${page.textChars} chars`,
                              ]
                                .filter(Boolean)
                                .join(' · ');
                              return (
                              <li
                                key={`ocr-${page.pageNumber}`}
                                className="flex items-start justify-between gap-3"
                              >
                                <div className="min-w-0">
                                  <span
                                    className="block text-on-surface-variant"
                                    style={{ fontFamily: 'JetBrains Mono', fontSize: '11px' }}
                                  >
                                    PAGE {page.pageNumber} · OCR
                                  </span>
                                  <span
                                    className="block text-outline truncate"
                                    style={{ fontFamily: 'JetBrains Mono', fontSize: '10px' }}
                                    title={meta}
                                  >
                                    {meta}
                                  </span>
                                </div>
                                <span
                                  className="flex-shrink-0"
                                  title="Mean line confidence of the recognised text"
                                  style={{ fontFamily: 'JetBrains Mono', fontSize: '11px', color: '#d0bcff' }}
                                >
                                  {page.ocrConfidence === null
                                    ? '—'
                                    : page.ocrConfidence.toFixed(3)}
                                </span>
                              </li>
                              );
                            })}
                            {data.pages.unaccountedPages.map((page) => (
                              <li
                                key={`unaccounted-${page.pageNumber}`}
                                className="flex items-start justify-between gap-3"
                              >
                                <span
                                  className="text-on-surface-variant"
                                  style={{ fontFamily: 'JetBrains Mono', fontSize: '11px' }}
                                >
                                  PAGE {page.pageNumber}
                                </span>
                                <span
                                  className="flex-shrink-0"
                                  style={{ fontFamily: 'JetBrains Mono', fontSize: '10px', color: '#ffb4ab' }}
                                >
                                  {FAILURE_REASON_LABEL[page.failureReason ?? ''] ??
                                    page.failureReason ??
                                    'Not usable'}
                                </span>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    </>
                  )}
                </section>
              )}

              {/* Element Types */}
              <section aria-labelledby="insights-elements-heading">
                <SectionHeading>ELEMENT TYPES</SectionHeading>
                <div className="rounded-lg p-3" style={{ ...GLASS }}>
                  {Object.keys(data.structure.elementTypeCounts).length === 0 ? (
                    <span className="text-outline" style={{ fontFamily: 'JetBrains Mono', fontSize: '11px' }}>
                      No element data
                    </span>
                  ) : (
                    <ul className="space-y-1">
                      {Object.entries(data.structure.elementTypeCounts).map(([type, count]) => (
                        <li key={type} className="flex justify-between items-center gap-3">
                          <span className="text-on-surface-variant truncate" style={{ fontFamily: 'JetBrains Mono', fontSize: '11px' }}>
                            {type}
                          </span>
                          <span className="text-on-surface" style={{ fontFamily: 'JetBrains Mono', fontSize: '11px' }}>{count}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </section>

              {/* Embeddings */}
              <section aria-labelledby="insights-embedding-heading">
                <SectionHeading>EMBEDDINGS</SectionHeading>
                <div className="rounded-lg p-3 space-y-3" style={{ ...GLASS }}>
                  <div className="flex justify-between items-center gap-3">
                    <span className="text-outline" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px' }}>EMBEDDED CHUNKS</span>
                    <span className="text-on-surface" style={{ fontFamily: 'JetBrains Mono', fontSize: '11px' }}>
                      {data.embedding.embeddedChunkCount} / {data.structure.totalChunks}
                    </span>
                  </div>
                  <ProgressBar value={data.embedding.coverage} label="Embedding coverage" color="#8B5CF6" />
                  <span className="block text-outline" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px' }}>
                    {Math.round(data.embedding.coverage * 100)}% coverage
                  </span>
                </div>
              </section>

              {/* Graph */}
              <section aria-labelledby="insights-graph-heading">
                <SectionHeading>GRAPH</SectionHeading>
                <div className="rounded-lg p-3 space-y-3" style={{ ...GLASS }}>
                  <div className="grid grid-cols-2 gap-2">
                    <StatCard label="NODES" value={data.graph.nodeCount} />
                    <StatCard label="EDGES" value={data.graph.edgeCount} />
                  </div>
                  <ProgressBar value={data.graph.coverage} label="Graph coverage" color="#06B6D4" />
                  <span className="block text-outline" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px' }}>
                    {Math.round(data.graph.coverage * 100)}% coverage
                  </span>
                  <div>
                    <span className="block text-outline mb-1" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px' }}>
                      RELATIONSHIPS
                    </span>
                    {Object.keys(data.graph.relationCounts).length === 0 ? (
                      <span className="text-outline" style={{ fontFamily: 'JetBrains Mono', fontSize: '11px' }}>
                        No relationships
                      </span>
                    ) : (
                      <ul className="space-y-1">
                        {Object.entries(data.graph.relationCounts).map(([relation, count]) => (
                          <li key={relation} className="flex justify-between items-center gap-3">
                            <span className="text-on-surface-variant truncate" style={{ fontFamily: 'JetBrains Mono', fontSize: '11px' }}>
                              {relation}
                            </span>
                            <span className="text-on-surface" style={{ fontFamily: 'JetBrains Mono', fontSize: '11px' }}>{count}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              </section>

              {/* Provenance */}
              <section aria-labelledby="insights-provenance-heading">
                <SectionHeading>PROVENANCE</SectionHeading>
                <div className="rounded-lg p-3 space-y-2" style={{ ...GLASS }}>
                  {[
                    { label: 'PARSER', value: data.provenance.parserVersion },
                    { label: 'CHUNKER', value: data.provenance.chunkerVersion },
                    { label: 'EMBEDDING MODEL', value: data.provenance.embeddingModel },
                  ].map((row) => (
                    <div key={row.label} className="flex justify-between items-center gap-3">
                      <span className="text-outline" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px' }}>{row.label}</span>
                      <span
                        className="truncate"
                        style={{ fontFamily: 'JetBrains Mono', fontSize: '11px', color: row.value ? '#cbc3d7' : '#958ea0' }}
                        title={row.value ?? 'Not recorded'}
                      >
                        {row.value ?? 'Not recorded'}
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            </>
          )}
        </div>
      </div>
    </>,
    document.body,
  );
};
