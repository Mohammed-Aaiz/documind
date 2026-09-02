import React, { useEffect, useState } from 'react';
import { Page, ReliabilityQueryData } from '../types';
import { apiGetLastQueryReliability, ApiReliabilityQueryData } from '../lib/api';

interface ReliabilityPageProps {
  onNavigate: (page: Page) => void;
}

const GLASS = {
  background: 'rgba(5,7,10,0.70)',
  backdropFilter: 'blur(24px)',
  WebkitBackdropFilter: 'blur(24px)',
  borderTop: '1px solid rgba(255,255,255,0.1)',
  borderLeft: '1px solid rgba(255,255,255,0.1)',
};

function apiToReliability(data: ApiReliabilityQueryData): ReliabilityQueryData {
  return {
    question: data.question,
    answer: data.answer,
    qaConfidence: data.qaConfidence,
    retrievalScore: data.retrievalScore,
    avgRetrievalScore: data.avgRetrievalScore,
    sourceCount: data.sourceCount,
    uniqueDocuments: data.uniqueDocuments,
    factualGrounded: data.factualGrounded,
    insufficientContext: data.insufficientContext,
    sources: data.sources.map((s) => ({
      id: s.id,
      documentId: s.documentId,
      documentName: s.documentName,
      content: s.content,
      relevanceScore: s.relevanceScore,
      page: s.page,
      status: s.status,
    })),
  };
}

const statusColor = (s: string) => {
  if (s === 'VERIFIED') return '#4cd7f6';
  if (s === 'MARGINAL') return '#958ea0';
  return '#ffb4ab';
};

export const ReliabilityPage: React.FC<ReliabilityPageProps> = () => {
  const [data, setData] = useState<ReliabilityQueryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const raw = await apiGetLastQueryReliability();
      setData(apiToReliability(raw));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load reliability data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const confidencePercent = data ? Math.round(data.qaConfidence * 100) : 0;
  const groundingLabel = data
    ? data.insufficientContext
      ? 'Insufficient'
      : data.factualGrounded
        ? 'Grounded'
        : 'Ungrounded'
    : 'No Data';
  const groundingColor = data
    ? data.insufficientContext
      ? '#ffb4ab'
      : data.factualGrounded
        ? '#4cd7f6'
        : '#958ea0'
    : '#555';
  const groundingBarWidth = data
    ? data.insufficientContext
      ? 0
      : data.factualGrounded
        ? 100
        : 30
    : 0;

  return (
    <div className="pt-28 px-8 pb-8 min-h-screen relative z-10 flex flex-col gap-8">

      {/* Header */}
      <header className="flex justify-between items-end">
        <div>
          <h2 className="font-bold text-on-surface mb-2" style={{ fontFamily: 'Geist', fontSize: '56px', lineHeight: 1.1, letterSpacing: '-0.04em' }}>
            Reliability Center
          </h2>
          <p className="font-body-base text-on-surface-variant max-w-2xl">
            Real-time fidelity monitoring and structural verification of generated cognitive responses.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchData}
            className="px-4 py-2 rounded-lg flex items-center gap-2 text-cyber-cyan hover:bg-surface-bright/10 transition-colors"
            style={{ ...GLASS, border: '1px solid rgba(255,255,255,0.1)' }}
          >
            <span className="material-symbols-outlined text-[16px]">refresh</span>
            <span className="font-label-code text-label-code">REFRESH</span>
          </button>
          <div className="px-4 py-2 rounded-lg flex items-center gap-2" style={{ ...GLASS, border: '1px solid rgba(255,255,255,0.1)' }}>
            <span className="w-2 h-2 rounded-full bg-cyber-cyan animate-pulse" />
            <span className="font-label-code text-label-code text-cyber-cyan">NODE_SYNC_ACTIVE</span>
          </div>
        </div>
      </header>

      {loading && (
        <div className="flex items-center justify-center py-20">
          <span className="material-symbols-outlined text-electric-violet animate-spin text-[32px]">progress_activity</span>
          <span className="ml-3 font-body-base text-on-surface-variant">Loading reliability data...</span>
        </div>
      )}

      {error && (
        <div className="rounded-xl p-6" style={{ ...GLASS, border: '1px solid rgba(255,180,171,0.3)' }}>
          <span className="font-body-base text-on-surface">{error}</span>
        </div>
      )}

      {!loading && !error && data && (
        <div className="grid grid-cols-12 gap-8 flex-1">

          {/* Cognitive Pathway Tracer — col-span-8 */}
          <div className="col-span-12 xl:col-span-8 rounded-xl relative overflow-hidden flex flex-col" style={{ ...GLASS, minHeight: 500 }}>
            {/* Header bar */}
            <div className="p-6 flex justify-between items-center z-10 absolute top-0 w-full"
              style={{ background: 'rgba(5,7,10,0.40)', backdropFilter: 'blur(12px)', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
              <h3 className="font-semibold text-on-surface" style={{ fontFamily: 'Geist', fontSize: '24px' }}>
                Cognitive Pathway Tracer
              </h3>
              <div className="flex gap-2">
                <button className="p-2 rounded-md hover:bg-surface-bright/20 text-outline hover:text-on-surface transition-colors">
                  <span className="material-symbols-outlined text-[20px]">zoom_in</span>
                </button>
                <button className="p-2 rounded-md hover:bg-surface-bright/20 text-outline hover:text-on-surface transition-colors">
                  <span className="material-symbols-outlined text-[20px]">center_focus_strong</span>
                </button>
              </div>
            </div>

            {/* Node map canvas */}
            <div className="flex-1 w-full relative flex items-center justify-center pt-24 pb-6 px-6">
              <div className="w-full h-full relative">
                {/* Nodes in horizontal flow */}
                <div className="absolute inset-0 flex items-center justify-between px-8">

                  {/* QUESTION node */}
                  <div className="flex flex-col items-center gap-2 z-10">
                    <div className="w-16 h-16 rounded-full flex items-center justify-center"
                      style={{ background: 'rgba(40,42,46,0.80)', backdropFilter: 'blur(4px)', border: '1px solid rgba(255,255,255,0.1)', boxShadow: '0 0 20px rgba(255,255,255,0.05)' }}>
                      <span className="material-symbols-outlined text-outline">help_center</span>
                    </div>
                    <span className="font-label-caps text-label-caps text-on-surface-variant">QUESTION</span>
                    {data.question && (
                      <span className="font-body-xs text-on-surface-variant max-w-[120px] text-center truncate" title={data.question}>
                        {data.question.length > 30 ? data.question.slice(0, 30) + '…' : data.question}
                      </span>
                    )}
                  </div>

                  {/* Connector 1 */}
                  <div className="h-px flex-1 relative mx-2" style={{ background: 'linear-gradient(90deg, rgba(73,68,84,0.6), rgba(139,92,246,0.5))' }}>
                    <div className="absolute -top-1.5 left-1/4 w-3 h-3 rounded-full bg-electric-violet" style={{ boxShadow: '0 0 10px #8B5CF6' }} />
                  </div>

                  {/* RETRIEVAL node */}
                  <div className="flex flex-col items-center gap-2 z-10" style={{ marginTop: '80px' }}>
                    <div className="w-20 h-20 rounded-full flex items-center justify-center"
                      style={{ background: 'rgba(40,42,46,0.80)', backdropFilter: 'blur(4px)', border: '1px solid rgba(139,92,246,0.5)', boxShadow: '0 0 30px rgba(139,92,246,0.2)' }}>
                      <span className="material-symbols-outlined text-electric-violet text-[32px]">database_search</span>
                    </div>
                    <span className="font-label-caps text-label-caps text-electric-violet">RETRIEVAL</span>
                    <span className="font-body-xs text-on-surface-variant">{data.sourceCount} chunks</span>
                  </div>

                  {/* Connector 2 */}
                  <div className="h-px flex-1 relative mx-2" style={{ background: 'linear-gradient(90deg, rgba(139,92,246,0.5), rgba(6,182,212,0.5))' }} />

                  {/* EVIDENCE node */}
                  <div className="flex flex-col items-center gap-2 z-10" style={{ marginBottom: '40px' }}>
                    <div className="w-16 h-16 rounded-full flex items-center justify-center"
                      style={{ background: 'rgba(40,42,46,0.80)', backdropFilter: 'blur(4px)', border: `1px solid ${data.factualGrounded ? 'rgba(6,182,212,0.5)' : 'rgba(255,180,171,0.3)'}`, boxShadow: `0 0 20px ${data.factualGrounded ? 'rgba(6,182,212,0.2)' : 'rgba(255,180,171,0.1)'}` }}>
                      <span className={`material-symbols-outlined ${data.factualGrounded ? 'text-cyber-cyan' : 'text-red-400'}`}>policy</span>
                    </div>
                    <span className={`font-label-caps text-label-caps ${data.factualGrounded ? 'text-cyber-cyan' : 'text-red-400'}`}>EVIDENCE</span>
                    <span className="font-body-xs text-on-surface-variant">{data.factualGrounded ? 'Grounded' : 'Not Grounded'}</span>
                  </div>

                  {/* Connector 3 */}
                  <div className="h-px flex-1 relative mx-2" style={{ background: 'linear-gradient(90deg, rgba(6,182,212,0.5), rgba(160,120,255,0.5))' }}>
                    <div className="absolute -top-1.5 right-1/4 w-3 h-3 rounded-full bg-cyber-cyan" style={{ boxShadow: '0 0 10px #06B6D4' }} />
                  </div>

                  {/* ANSWER node */}
                  <div className="flex flex-col items-center gap-2 z-10">
                    <div className="w-24 h-24 rounded-full flex items-center justify-center"
                      style={{ background: 'rgba(40,42,46,0.90)', backdropFilter: 'blur(8px)', border: data.insufficientContext ? '2px solid #ffb4ab' : '2px solid #a078ff', boxShadow: data.insufficientContext ? '0 0 40px rgba(255,180,171,0.3)' : '0 0 40px rgba(160,120,255,0.3)' }}>
                      <span className={`material-symbols-outlined text-[40px]`} style={{ color: data.insufficientContext ? '#ffb4ab' : '#a078ff' }}>
                        {data.insufficientContext ? 'warning' : 'check_circle'}
                      </span>
                    </div>
                    <span className="font-label-caps text-label-caps font-bold" style={{ color: data.insufficientContext ? '#ffb4ab' : '#a078ff' }}>ANSWER</span>
                    {data.answer && (
                      <span className="font-body-xs text-on-surface-variant max-w-[140px] text-center truncate" title={data.answer}>
                        {data.answer.length > 30 ? data.answer.slice(0, 30) + '…' : data.answer}
                      </span>
                    )}
                  </div>
                </div>

                {/* Floating data labels */}
                <div className="absolute top-1/4 left-1/3 w-28 p-3 rounded text-center"
                  style={{ ...GLASS, border: '1px solid rgba(255,255,255,0.1)' }}>
                  <span className="font-label-code text-label-code text-electric-violet block mb-1">Retrieval</span>
                  <span className="font-body-sm text-on-surface">{data.retrievalScore.toFixed(3)}</span>
                </div>
                <div className="absolute bottom-1/3 right-1/4 w-28 p-3 rounded text-center"
                  style={{ ...GLASS, border: '1px solid rgba(255,255,255,0.1)' }}>
                  <span className="font-label-code text-label-code text-cyber-cyan block mb-1">Avg Score</span>
                  <span className="font-body-sm text-on-surface">{data.avgRetrievalScore.toFixed(3)}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Right metrics column — col-span-4 */}
          <div className="col-span-12 xl:col-span-4 flex flex-col gap-8">

            {/* Answer Confidence */}
            <div className="rounded-xl p-6 flex flex-col justify-between relative overflow-hidden" style={{ ...GLASS, height: '192px' }}>
              <div className="absolute top-0 right-0 w-32 h-32 rounded-full blur-3xl pointer-events-none"
                style={{ background: 'rgba(139,92,246,0.10)' }} />
              <div className="relative z-10">
                <div className="flex justify-between items-start mb-2">
                  <h3 className="font-label-caps text-label-caps text-outline">Answer Confidence</h3>
                  <span className="material-symbols-outlined text-electric-violet text-[20px]">psychology_alt</span>
                </div>
                <p className="font-body-sm text-on-surface-variant">QA model confidence from the actual DocuMind model output.</p>
              </div>
              <div className="flex items-end gap-3 mt-4 relative z-10">
                <span className="text-on-surface font-bold leading-none" style={{ fontFamily: 'Geist', fontSize: '64px', letterSpacing: '-0.05em' }}>
                  {confidencePercent}
                </span>
                <span className="font-semibold text-electric-violet leading-none pb-2" style={{ fontFamily: 'Geist', fontSize: '28px' }}>%</span>
              </div>
            </div>

            {/* Factual Grounding */}
            <div className="rounded-xl p-6 flex flex-col justify-between relative overflow-hidden" style={{ ...GLASS, height: '192px' }}>
              <div className="absolute bottom-0 left-0 w-32 h-32 rounded-full blur-3xl pointer-events-none"
                style={{ background: 'rgba(6,182,212,0.10)' }} />
              <div className="relative z-10">
                <div className="flex justify-between items-start mb-2">
                  <h3 className="font-label-caps text-label-caps text-outline">Factual Grounding</h3>
                  <span className="material-symbols-outlined text-cyber-cyan text-[20px]">verified</span>
                </div>
                <p className="font-body-sm text-on-surface-variant">Whether the answer span is found within the retrieved context.</p>
              </div>
              <div className="flex items-center gap-4 mt-4 relative z-10">
                <div className="px-4 py-2 rounded inline-flex" style={{ border: `1px solid ${groundingColor}40`, background: `${groundingColor}15` }}>
                  <span className="font-semibold" style={{ color: groundingColor, fontFamily: 'Geist', fontSize: '24px' }}>{groundingLabel}</span>
                </div>
                <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ background: 'rgba(29,32,35,1)' }}>
                  <div className="h-full rounded-full transition-all" style={{ width: `${groundingBarWidth}%`, background: groundingColor }} />
                </div>
              </div>
            </div>
          </div>

          {/* Source References table — col-span-12 */}
          <div className="col-span-12 rounded-xl flex flex-col overflow-hidden" style={GLASS}>
            <div className="p-6 flex justify-between items-center"
              style={{ background: 'rgba(5,7,10,0.40)', backdropFilter: 'blur(12px)', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
              <div>
                <h3 className="font-semibold text-on-surface" style={{ fontFamily: 'Geist', fontSize: '24px' }}>
                  Source References &amp; Traceability
                </h3>
                <p className="font-body-sm text-on-surface-variant mt-1">
                  {data.sources.length} source{data.sources.length !== 1 ? 's' : ''} from {data.uniqueDocuments} document{data.uniqueDocuments !== 1 ? 's' : ''}
                </p>
              </div>
            </div>
            <div className="overflow-x-auto">
              {data.sources.length === 0 ? (
                <div className="p-8 text-center">
                  <span className="material-symbols-outlined text-outline text-[48px] mb-3 block">search_off</span>
                  <p className="font-body-base text-on-surface-variant">
                    No source references yet. Ask a question in the workspace to see real evidence here.
                  </p>
                </div>
              ) : (
                <table className="w-full text-left">
                  <thead>
                    <tr style={{ borderBottom: '1px solid rgba(73,68,84,0.3)' }}>
                      <th className="font-label-caps text-label-caps text-outline p-4 font-normal">Document</th>
                      <th className="font-label-caps text-label-caps text-outline p-4 font-normal">Relevance</th>
                      <th className="font-label-caps text-label-caps text-outline p-4 font-normal">Content Snippet</th>
                      <th className="font-label-caps text-label-caps text-outline p-4 font-normal">Page</th>
                      <th className="font-label-caps text-label-caps text-outline p-4 font-normal text-right">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.sources.map((ref, i) => (
                      <tr
                        key={ref.id}
                        className="hover:bg-surface-bright/10 transition-colors cursor-pointer group"
                        style={{ borderBottom: i < data.sources.length - 1 ? '1px solid rgba(73,68,84,0.2)' : 'none' }}
                      >
                        <td className="p-4 font-label-code text-label-code text-on-surface flex items-center gap-3">
                          <span className="material-symbols-outlined text-outline group-hover:text-cyber-cyan transition-colors">
                            description
                          </span>
                          <span className="max-w-[180px] truncate" title={ref.documentName}>{ref.documentName}</span>
                        </td>
                        <td className="p-4">
                          <div className="flex items-center gap-2">
                            <span className="font-body-sm text-on-surface-variant">{ref.relevanceScore.toFixed(2)}</span>
                            <div className="w-16 h-1 rounded-full overflow-hidden" style={{ background: 'rgba(29,32,35,1)' }}>
                              <div className="h-full rounded-full"
                                style={{ width: `${ref.relevanceScore * 100}%`, background: ref.status === 'MARGINAL' ? '#958ea0' : '#8B5CF6' }} />
                            </div>
                          </div>
                        </td>
                        <td className="p-4 font-body-sm text-on-surface-variant max-w-[200px] truncate" title={ref.content}>
                          {ref.content || '—'}
                        </td>
                        <td className="p-4 font-body-sm text-on-surface-variant">
                          {ref.page !== null ? ref.page : '—'}
                        </td>
                        <td className="p-4 text-right">
                          <span className="inline-flex items-center gap-1 font-label-code text-label-code" style={{ color: statusColor(ref.status) }}>
                            <span className="w-1.5 h-1.5 rounded-full" style={{ background: statusColor(ref.status) }} />
                            {ref.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}

      {!loading && !error && !data && (
        <div className="rounded-xl p-12 text-center" style={GLASS}>
          <span className="material-symbols-outlined text-outline text-[64px] mb-4 block">analytics</span>
          <h3 className="font-semibold text-on-surface mb-2" style={{ fontFamily: 'Geist', fontSize: '28px' }}>No Query Data</h3>
          <p className="font-body-base text-on-surface-variant max-w-md mx-auto">
            Ask a question in the workspace to see real reliability data here. All metrics come from the actual RAG pipeline — nothing is fabricated.
          </p>
        </div>
      )}
    </div>
  );
};
