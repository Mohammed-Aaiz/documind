import React, { useRef, useState } from 'react';
import { Page } from '../types';
import { apiAnalyzeMedia, ApiError, ApiMediaVerificationResult } from '../lib/api';

interface VerificationPageProps {
  onNavigate: (page: Page) => void;
}

const GLASS = {
  background: 'rgba(5,7,10,0.70)',
  backdropFilter: 'blur(24px)',
  WebkitBackdropFilter: 'blur(24px)',
  borderTop: '1px solid rgba(255,255,255,0.1)',
  borderLeft: '1px solid rgba(255,255,255,0.1)',
};

const ACCEPTED_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'];
const ACCEPTED_MIME = [
  'image/png',
  'image/jpeg',
  'image/webp',
  'image/gif',
  'image/bmp',
];
const MAX_UPLOAD_MB = 50;

type AnalysisStatus = 'empty' | 'ready' | 'analyzing' | 'success' | 'error';

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

/** Verdict label → accent colour. Never the only signal — the label is always shown. */
function verdictColor(verdict: string): string {
  const v = verdict.toLowerCase();
  if (v.includes('fake') || v.includes('synthetic') || v.includes('manip')) return '#ffb4ab';
  if (v.includes('real') || v.includes('authentic') || v.includes('human')) return '#4cd7f6';
  return '#958ea0';
}

function verdictIcon(verdict: string): string {
  const v = verdict.toLowerCase();
  if (v.includes('fake') || v.includes('synthetic') || v.includes('manip')) return 'gpp_maybe';
  if (v.includes('real') || v.includes('authentic') || v.includes('human')) return 'verified';
  return 'help';
}

export const VerificationPage: React.FC<VerificationPageProps> = () => {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<AnalysisStatus>('empty');
  const [result, setResult] = useState<ApiMediaVerificationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const analyzing = status === 'analyzing';

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0] ?? null;
    setResult(null);
    setError(null);

    if (!selected) {
      setFile(null);
      setStatus('empty');
      setNotice(null);
      return;
    }

    const ext = `.${(selected.name.split('.').pop() ?? '').toLowerCase()}`;
    // Client-side UX check only — the backend remains authoritative.
    const typeOk = ACCEPTED_MIME.includes(selected.type) || ACCEPTED_EXTENSIONS.includes(ext);
    if (!typeOk) {
      setFile(null);
      setStatus('empty');
      setNotice(`Unsupported file type. Use ${ACCEPTED_EXTENSIONS.join(', ')}.`);
      return;
    }
    if (selected.size > MAX_UPLOAD_MB * 1024 * 1024) {
      setFile(null);
      setStatus('empty');
      setNotice(`File is larger than ${MAX_UPLOAD_MB} MB.`);
      return;
    }

    setNotice(null);
    setFile(selected);
    setStatus('ready');
  };

  const handleAnalyze = async () => {
    if (!file || analyzing) return;
    setStatus('analyzing');
    setError(null);
    try {
      const res = await apiAnalyzeMedia(file);
      setResult(res);
      setStatus('success');
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.status === 401
            ? 'Your session has expired. Please sign in again.'
            : err.message
          : 'Could not reach the verification service. Please try again.';
      setError(message);
      setStatus('error');
    }
  };

  const handleReset = () => {
    if (analyzing) return;
    setFile(null);
    setResult(null);
    setError(null);
    setNotice(null);
    setStatus('empty');
    if (inputRef.current) inputRef.current.value = '';
  };

  return (
    <div className="pt-28 px-8 pb-8 min-h-screen relative z-10 flex flex-col gap-8">
      {/* Header */}
      <header>
        <h1
          className="font-bold text-on-surface mb-2"
          style={{ fontFamily: 'Geist', fontSize: '56px', lineHeight: 1.1, letterSpacing: '-0.04em' }}
        >
          Media Verification
        </h1>
        <p className="font-body-base text-on-surface-variant flex items-center gap-2">
          <span className="material-symbols-outlined text-cyber-cyan" style={{ fontSize: '18px' }}>
            image_search
          </span>
          Image deepfake screening with the local DocuMind verification model
        </p>
      </header>

      <div className="grid grid-cols-12 gap-6 flex-1 min-h-[560px]">
        {/* Left — Upload */}
        <div className="col-span-12 xl:col-span-4 flex flex-col">
          <div className="rounded-xl p-6 flex flex-col gap-4" style={GLASS}>
            <h2 className="font-semibold text-on-surface flex items-center gap-2" style={{ fontFamily: 'Geist', fontSize: '24px' }}>
              <span className="material-symbols-outlined">upload_file</span> Upload
            </h2>

            <label htmlFor="media-upload" className="sr-only">
              Select an image to verify
            </label>
            <input
              id="media-upload"
              ref={inputRef}
              type="file"
              accept=".png,.jpg,.jpeg,.webp,.gif,.bmp,image/png,image/jpeg,image/webp,image/gif,image/bmp"
              onChange={handleFileChange}
              disabled={analyzing}
              aria-describedby="media-upload-help"
              className="block w-full text-on-surface-variant text-sm rounded-lg border border-white/10 p-2 file:mr-3 file:rounded-lg file:border-0 file:px-4 file:py-2 file:text-cyber-cyan file:bg-surface-bright/40 hover:file:bg-surface-bright/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-cyber-cyan/60 disabled:opacity-50"
            />
            <p id="media-upload-help" className="text-outline" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px' }}>
              SUPPORTED: PNG, JPEG, WEBP, GIF, BMP · MAX {MAX_UPLOAD_MB} MB
            </p>

            {notice && (
              <div
                role="alert"
                className="rounded-lg p-3 text-error text-xs"
                style={{ background: 'rgba(255,180,171,0.08)', border: '1px solid rgba(255,180,171,0.3)', fontFamily: 'Inter' }}
              >
                {notice}
              </div>
            )}

            {file && (
              <div className="rounded-lg p-3" style={{ background: 'rgba(29,32,35,0.6)', border: '1px solid rgba(255,255,255,0.08)' }}>
                <p className="text-on-surface truncate" style={{ fontFamily: 'Inter', fontSize: '13px' }} title={file.name}>
                  {file.name}
                </p>
                <p className="text-outline mt-1" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px' }}>
                  {file.type || 'unknown type'} · {formatBytes(file.size)}
                </p>
              </div>
            )}

            <div className="flex gap-3">
              <button
                type="button"
                onClick={handleAnalyze}
                disabled={!file || analyzing}
                aria-busy={analyzing}
                aria-label={analyzing ? 'Analyzing image, please wait' : 'Analyze image'}
                className="flex-1 px-5 py-3 rounded-lg text-white text-center transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-cyber-cyan/70"
                style={{ background: 'linear-gradient(90deg, #8B5CF6, #06B6D4)', fontFamily: 'JetBrains Mono', fontSize: '12px' }}
              >
                {analyzing && (
                  <span className="material-symbols-outlined animate-spin" style={{ fontSize: '16px' }}>
                    progress_activity
                  </span>
                )}
                {analyzing ? 'ANALYZING…' : 'ANALYZE'}
              </button>
              <button
                type="button"
                onClick={handleReset}
                disabled={analyzing || (!file && !result && !error)}
                aria-label="Clear selected file and result"
                className="px-5 py-3 rounded-lg text-on-surface-variant hover:text-on-surface transition-colors disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-cyber-cyan/70"
                style={{ ...GLASS, fontFamily: 'JetBrains Mono', fontSize: '12px' }}
              >
                CLEAR
              </button>
            </div>

            <p className="text-outline" style={{ fontFamily: 'Inter', fontSize: '11px', lineHeight: 1.5 }}>
              Your image is sent to the verification endpoint for analysis and is not stored.
            </p>
          </div>
        </div>

        {/* Right — Result */}
        <div className="col-span-12 xl:col-span-8 flex flex-col">
          <div
            className="rounded-xl p-6 flex-1 flex flex-col"
            style={GLASS}
            aria-live="polite"
          >
            <h2 className="font-semibold text-on-surface mb-4 flex items-center gap-2" style={{ fontFamily: 'Geist', fontSize: '24px' }}>
              <span className="material-symbols-outlined">fact_check</span> Result
            </h2>

            {status === 'empty' && (
              <div className="flex-1 flex flex-col items-center justify-center text-center">
                <span className="material-symbols-outlined text-outline mb-4" style={{ fontSize: '64px', opacity: 0.4 }}>
                  image
                </span>
                <p className="text-on-surface-variant" style={{ fontFamily: 'Inter', fontSize: '14px', maxWidth: 420 }}>
                  Select an image and choose Analyze. The verdict and score are produced by the local
                  deepfake-detection model — no result is shown until analysis actually runs.
                </p>
              </div>
            )}

            {status === 'ready' && (
              <div className="flex-1 flex flex-col items-center justify-center text-center">
                <span className="material-symbols-outlined text-cyber-cyan mb-4" style={{ fontSize: '56px', opacity: 0.7 }}>
                  task_alt
                </span>
                <p className="text-on-surface-variant" style={{ fontFamily: 'Inter', fontSize: '14px' }}>
                  Image selected. Choose Analyze to run verification.
                </p>
              </div>
            )}

            {status === 'analyzing' && (
              <div className="flex-1 flex flex-col items-center justify-center" role="status">
                <span className="material-symbols-outlined text-electric-violet animate-spin" style={{ fontSize: '40px' }}>
                  progress_activity
                </span>
                <p className="mt-4 text-on-surface-variant" style={{ fontFamily: 'Inter', fontSize: '14px' }}>
                  Analyzing image…
                </p>
              </div>
            )}

            {status === 'error' && error && (
              <div
                role="alert"
                className="rounded-xl p-6"
                style={{ ...GLASS, border: '1px solid rgba(255,180,171,0.3)' }}
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className="material-symbols-outlined text-error" style={{ fontSize: '20px' }}>
                    error
                  </span>
                  <span className="text-on-surface font-semibold" style={{ fontFamily: 'Geist', fontSize: '18px' }}>
                    Verification failed
                  </span>
                </div>
                <p className="text-on-surface-variant" style={{ fontFamily: 'Inter', fontSize: '14px' }}>
                  {error}
                </p>
              </div>
            )}

            {status === 'success' && result && (
              <div className="flex flex-col gap-6">
                {/* Verdict */}
                <div
                  className="rounded-xl p-6 flex items-center gap-4"
                  style={{ background: `${verdictColor(result.verdict)}12`, border: `1px solid ${verdictColor(result.verdict)}40` }}
                >
                  <span className="material-symbols-outlined" style={{ fontSize: '40px', color: verdictColor(result.verdict) }}>
                    {verdictIcon(result.verdict)}
                  </span>
                  <div>
                    <p className="text-outline" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px', letterSpacing: '0.1em' }}>
                      MODEL VERDICT
                    </p>
                    <p className="font-bold" style={{ fontFamily: 'Geist', fontSize: '32px', color: verdictColor(result.verdict) }}>
                      {result.verdict}
                    </p>
                  </div>
                </div>

                {/* Metric grid — only real backend values */}
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  <div className="rounded-lg p-4" style={{ background: 'rgba(29,32,35,0.6)', border: '1px solid rgba(255,255,255,0.08)' }}>
                    <p className="text-outline mb-1" style={{ fontFamily: 'JetBrains Mono', fontSize: '9px', letterSpacing: '0.1em' }}>
                      PREDICTED-CLASS PROBABILITY
                    </p>
                    <p className="text-on-surface font-bold" style={{ fontFamily: 'Geist', fontSize: '24px' }}>
                      {(result.score * 100).toFixed(1)}%
                    </p>
                    <p className="text-outline" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px' }}>
                      score {result.score.toFixed(4)}
                    </p>
                  </div>
                  <div className="rounded-lg p-4" style={{ background: 'rgba(29,32,35,0.6)', border: '1px solid rgba(255,255,255,0.08)' }}>
                    <p className="text-outline mb-1" style={{ fontFamily: 'JetBrains Mono', fontSize: '9px', letterSpacing: '0.1em' }}>
                      IMAGE
                    </p>
                    <p className="text-on-surface font-bold" style={{ fontFamily: 'Geist', fontSize: '24px' }}>
                      {result.processing.width} × {result.processing.height}
                    </p>
                    <p className="text-outline" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px' }}>
                      {formatBytes(result.processing.bytes)}
                    </p>
                  </div>
                  <div className="rounded-lg p-4" style={{ background: 'rgba(29,32,35,0.6)', border: '1px solid rgba(255,255,255,0.08)' }}>
                    <p className="text-outline mb-1" style={{ fontFamily: 'JetBrains Mono', fontSize: '9px', letterSpacing: '0.1em' }}>
                      PROCESSING TIME
                    </p>
                    <p className="text-on-surface font-bold" style={{ fontFamily: 'Geist', fontSize: '24px' }}>
                      {result.processing.elapsedMs} ms
                    </p>
                  </div>
                </div>

                {/* Provenance */}
                <div className="rounded-lg p-4" style={{ background: 'rgba(29,32,35,0.6)', border: '1px solid rgba(255,255,255,0.08)' }}>
                  <p className="text-outline mb-2" style={{ fontFamily: 'JetBrains Mono', fontSize: '9px', letterSpacing: '0.1em' }}>
                    MODEL
                  </p>
                  <div className="flex flex-wrap items-center gap-x-6 gap-y-1">
                    <span className="text-on-surface" style={{ fontFamily: 'Inter', fontSize: '14px' }}>
                      {result.model.name}
                    </span>
                    <span className="text-on-surface-variant" style={{ fontFamily: 'JetBrains Mono', fontSize: '11px' }}>
                      revision {result.model.version}
                    </span>
                  </div>
                  <p className="text-outline mt-3" style={{ fontFamily: 'Inter', fontSize: '11px', lineHeight: 1.5 }}>
                    The verdict and score come from this model. They describe this model's classification,
                    not an objective proof that the image is real or fake.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
