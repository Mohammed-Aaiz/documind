import React, { useRef, useState } from 'react';
import { Page } from '../types';

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

export const VerificationPage: React.FC<VerificationPageProps> = () => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [hasMedia, setHasMedia] = useState(false);
  const [params, setParams] = useState({ deepfake: true, generative: true, pixel: false });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) setHasMedia(true);
  };

  return (
    <div className="pt-28 px-8 pb-8 h-screen overflow-y-auto relative z-10 flex flex-col gap-6">
      {/* Header */}
      <header className="flex justify-between items-end">
        <div>
          <h1 className="font-bold text-on-surface mb-2" style={{ fontFamily: 'Geist', fontSize: '56px', lineHeight: 1.1, letterSpacing: '-0.04em' }}>
            Media Verification
          </h1>
          <p className="font-body-base text-on-surface-variant flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-cyber-cyan animate-pulse" />
            Upload media to analyze authenticity
          </p>
        </div>
        <div className="flex gap-3">
          <button className="px-6 py-2 rounded-lg font-label-code text-label-code text-on-surface hover:bg-surface-bright/30 transition-all"
            style={{ ...GLASS, border: '1px solid rgba(73,68,84,0.6)' }}>
            Export Report
          </button>
          {hasMedia && (
            <button className="px-6 py-2 rounded-lg font-label-code text-label-code text-white transition-all"
              style={{ background: '#8B5CF6', boxShadow: '0 0 20px rgba(139,92,246,0.4)' }}>
              Halt Analysis
            </button>
          )}
        </div>
      </header>

      {/* 12-col grid */}
      <div className="grid grid-cols-12 gap-6 flex-1 min-h-[560px]">

        {/* Left — Parameters */}
        <div className="col-span-3 flex flex-col">
          <div className="rounded-xl p-5 flex-1 flex flex-col" style={GLASS}>
            <h3 className="font-semibold text-on-surface mb-6 flex items-center gap-2" style={{ fontFamily: 'Geist', fontSize: '24px' }}>
              <span className="material-symbols-outlined">tune</span> Parameters
            </h3>
            <div className="space-y-6 flex-1">
              {/* Deepfake Heuristics */}
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <label className="font-label-code text-label-code text-on-surface">Deepfake Heuristics</label>
                  <button onClick={() => setParams((p) => ({ ...p, deepfake: !p.deepfake }))}
                    className="w-10 h-5 rounded-full relative cursor-pointer flex-shrink-0 transition-colors"
                    style={{ background: params.deepfake ? 'rgba(5,7,10,0.8)' : 'rgba(50,53,57,1)', boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.6)' }}>
                    <div className={`absolute top-0.5 w-4 h-4 rounded-full transition-all ${params.deepfake ? 'right-1 bg-cyber-cyan shadow-[0_0_10px_rgba(6,182,212,0.8)]' : 'left-1 bg-outline'}`} />
                  </button>
                </div>
                <div className="h-1 w-full rounded-full overflow-hidden" style={{ background: 'rgba(29,32,35,1)' }}>
                  <div className="h-full rounded-full" style={{ width: params.deepfake ? '75%' : '0%', background: 'linear-gradient(90deg, rgba(29,32,35,1), #06B6D4)', transition: 'width 0.3s' }} />
                </div>
              </div>

              {/* AI Generative Artifacts */}
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <label className="font-label-code text-label-code text-on-surface">AI Generative Artifacts</label>
                  <button onClick={() => setParams((p) => ({ ...p, generative: !p.generative }))}
                    className="w-10 h-5 rounded-full relative cursor-pointer flex-shrink-0 transition-colors"
                    style={{ background: params.generative ? 'rgba(5,7,10,0.8)' : 'rgba(50,53,57,1)', boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.6)' }}>
                    <div className={`absolute top-0.5 w-4 h-4 rounded-full transition-all ${params.generative ? 'right-1 bg-electric-violet shadow-[0_0_10px_rgba(139,92,246,0.8)]' : 'left-1 bg-outline'}`} />
                  </button>
                </div>
                <div className="h-1 w-full rounded-full overflow-hidden" style={{ background: 'rgba(29,32,35,1)' }}>
                  <div className="h-full rounded-full" style={{ width: params.generative ? '90%' : '0%', background: 'linear-gradient(90deg, rgba(29,32,35,1), #8B5CF6)', transition: 'width 0.3s' }} />
                </div>
              </div>

              {/* Pixel Manipulation */}
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <label className="font-label-code text-label-code text-on-surface-variant">Pixel Manipulation</label>
                  <button onClick={() => setParams((p) => ({ ...p, pixel: !p.pixel }))}
                    className="w-10 h-5 rounded-full relative cursor-pointer flex-shrink-0 transition-colors"
                    style={{ background: 'rgba(12,14,18,1)', border: '1px solid rgba(73,68,84,0.7)' }}>
                    <div className={`absolute top-0.5 w-4 h-4 rounded-full transition-all ${params.pixel ? 'right-1 bg-cyber-cyan shadow-[0_0_10px_rgba(6,182,212,0.8)]' : 'left-1 bg-outline'}`} />
                  </button>
                </div>
                <div className="h-1 w-full rounded-full overflow-hidden" style={{ background: 'rgba(29,32,35,1)' }}>
                  <div className="h-full" style={{ width: params.pixel ? '45%' : '0%', background: '#06B6D4', transition: 'width 0.3s' }} />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Center — Media Preview */}
        <div className="col-span-6 flex flex-col">
          <div
            className="rounded-xl flex-1 relative overflow-hidden group cursor-pointer"
            style={{ ...GLASS, border: '1px solid rgba(6,182,212,0.3)', boxShadow: '0 0 40px rgba(139,92,246,0.15)' }}
            onClick={() => !hasMedia && fileInputRef.current?.click()}
          >
            {!hasMedia ? (
              /* Upload placeholder */
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-4">
                <span className="material-symbols-outlined text-outline animate-pulse" style={{ fontSize: '64px' }}>perm_media</span>
                <p className="font-body-base text-outline">Drop image or video here, or click to upload</p>
                <button
                  className="px-6 py-3 rounded-lg font-label-code text-label-code text-white"
                  style={{ background: 'linear-gradient(90deg, #8B5CF6, #06B6D4)' }}
                >
                  Select Media
                </button>
              </div>
            ) : (
              /* Analysis view */
              <>
                {/* Dark overlay */}
                <div className="absolute inset-0 z-10" style={{ background: 'rgba(12,14,18,0.80)' }} />
                {/* Facial tracking overlay */}
                <div className="absolute inset-0 z-20 p-6 flex flex-col justify-between pointer-events-none">
                  <div className="flex justify-between items-start">
                    <div className="px-3 py-1 rounded font-label-code text-label-code text-cyber-cyan flex items-center gap-2"
                      style={{ background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(8px)', border: '1px solid rgba(6,182,212,0.5)' }}>
                      <span className="material-symbols-outlined text-[16px]">visibility</span>
                      FACIAL NODES: ACQUIRED
                    </div>
                    <div className="font-label-caps text-label-caps text-outline px-2 py-1 rounded" style={{ background: 'rgba(0,0,0,0.4)' }}>
                      FRAME: 02441.9
                    </div>
                  </div>

                  {/* Tracking ring */}
                  <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-64 h-64 rounded-full relative"
                    style={{ border: '1px solid rgba(6,182,212,0.3)' }}>
                    <div className="absolute top-1/4 left-1/4 w-2 h-2 rounded-full bg-electric-violet" style={{ boxShadow: '0 0 10px #8B5CF6' }} />
                    <div className="absolute top-1/4 right-1/4 w-2 h-2 rounded-full bg-electric-violet" style={{ boxShadow: '0 0 10px #8B5CF6' }} />
                    <div className="absolute bottom-1/4 left-1/2 w-3 h-3 rounded-full -translate-x-1/2 bg-error" style={{ boxShadow: '0 0 15px #ffb4ab' }} />
                    <svg className="absolute inset-0 w-full h-full opacity-50" viewBox="0 0 100 100">
                      <line x1="25" y1="25" x2="75" y2="25" stroke="#06B6D4" strokeWidth="0.5" strokeDasharray="2,2" />
                      <line x1="25" y1="25" x2="50" y2="75" stroke="#06B6D4" strokeWidth="0.5" strokeDasharray="2,2" />
                      <line x1="75" y1="25" x2="50" y2="75" stroke="#06B6D4" strokeWidth="0.5" strokeDasharray="2,2" />
                    </svg>
                  </div>

                  {/* Scan line */}
                  <div className="absolute inset-0 w-full h-1 pointer-events-none" style={{
                    background: 'linear-gradient(to bottom, transparent, rgba(6,182,212,0.4), transparent)',
                    animation: 'scanLine 3s linear infinite',
                  }} />

                  {/* Score */}
                  <div className="self-end mt-auto text-right">
                    <div className="font-bold" style={{
                      fontSize: '80px', lineHeight: 1, letterSpacing: '-0.05em',
                      background: 'linear-gradient(90deg, #8B5CF6, #06B6D4, #8B5CF6)',
                      backgroundSize: '200% auto',
                      color: 'transparent',
                      WebkitBackgroundClip: 'text',
                      backgroundClip: 'text',
                      animation: 'shimmerText 3s linear infinite',
                      fontFamily: 'Geist',
                    }}>87.4%</div>
                    <div className="font-label-caps text-label-caps text-on-surface-variant">ANOMALY DETECTED</div>
                  </div>
                </div>
              </>
            )}
          </div>
          <input ref={fileInputRef} type="file" accept="image/*,video/*" className="hidden" onChange={handleFileChange} />
        </div>

        {/* Right — Confidence */}
        <div className="col-span-3 flex flex-col">
          <div className="rounded-xl p-5 flex-1 flex flex-col justify-between" style={GLASS}>
            <h3 className="font-semibold text-on-surface mb-4 flex items-center gap-2" style={{ fontFamily: 'Geist', fontSize: '24px' }}>
              <span className="material-symbols-outlined">donut_large</span> Confidence
            </h3>

            {/* SVG gauge */}
            <div className="relative w-40 h-40 mx-auto flex items-center justify-center">
              <svg className="w-full h-full" style={{ transform: 'rotate(-90deg)' }} viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="45" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="8" />
                <circle cx="50" cy="50" r="45" fill="none" strokeLinecap="round" strokeWidth="8"
                  stroke="url(#gaugeGrad)" strokeDasharray="282.7" strokeDashoffset="35.3" />
                <defs>
                  <linearGradient id="gaugeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#8B5CF6" />
                    <stop offset="100%" stopColor="#06B6D4" />
                  </linearGradient>
                </defs>
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-white font-bold" style={{ fontFamily: 'Geist', fontSize: '32px', letterSpacing: '-0.02em' }}>
                  {hasMedia ? '87%' : '--'}
                </span>
                {hasMedia && <span className="font-label-caps text-label-caps text-error">SYNTHETIC</span>}
              </div>
            </div>

            {hasMedia && (
              <div className="space-y-4 mt-4">
                <div>
                  <div className="flex justify-between font-label-code text-label-code mb-1">
                    <span className="text-on-surface-variant">Lip Sync Drift</span>
                    <span className="text-cyber-cyan">High</span>
                  </div>
                  <div className="h-1.5 w-full rounded-full overflow-hidden" style={{ background: 'rgba(29,32,35,1)' }}>
                    <div className="h-full rounded-full" style={{ width: '85%', background: '#06B6D4' }} />
                  </div>
                </div>
                <div>
                  <div className="flex justify-between font-label-code text-label-code mb-1">
                    <span className="text-on-surface-variant">Blink Rate</span>
                    <span className="text-electric-violet">Abnormal</span>
                  </div>
                  <div className="h-1.5 w-full rounded-full overflow-hidden" style={{ background: 'rgba(29,32,35,1)' }}>
                    <div className="h-full rounded-full" style={{ width: '92%', background: '#8B5CF6' }} />
                  </div>
                </div>
              </div>
            )}

            {!hasMedia && (
              <p className="font-body-sm text-outline text-center mt-4">Upload media to see confidence metrics</p>
            )}
          </div>
        </div>
      </div>

      <style>{`
        @keyframes scanLine { 0% { transform: translateY(-100%); } 100% { transform: translateY(100vh); } }
        @keyframes shimmerText { to { background-position: 200% center; } }
      `}</style>
    </div>
  );
};
