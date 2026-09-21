import React from 'react';
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

/**
 * Media Verification page — honest unavailable state.
 *
 * The backend media analysis pipeline is not yet implemented
 * (POST /api/verification/analyze raises NotImplementedError).
 * This page therefore does NOT display fabricated analysis results.
 *
 * All fake metrics, scores, verdicts, and analysis overlays have been
 * removed.  The page clearly communicates that the feature is under
 * development and does not pretend that analysis has occurred.
 */
export const VerificationPage: React.FC<VerificationPageProps> = () => {
  return (
    <div className="pt-28 px-8 pb-8 h-screen overflow-y-auto relative z-10 flex flex-col gap-6">
      {/* Header */}
      <header className="flex justify-between items-end">
        <div>
          <h1 className="font-bold text-on-surface mb-2" style={{ fontFamily: 'Geist', fontSize: '56px', lineHeight: 1.1, letterSpacing: '-0.04em' }}>
            Media Verification
          </h1>
          <p className="font-body-base text-on-surface-variant flex items-center gap-2">
            <span className="material-symbols-outlined text-yellow-400" style={{ fontSize: '18px' }}>construction</span>
            Analysis pipeline under development
          </p>
        </div>
      </header>

      {/* 12-col grid */}
      <div className="grid grid-cols-12 gap-6 flex-1 min-h-[560px]">

        {/* Left — Capabilities (honest status) */}
        <div className="col-span-3 flex flex-col">
          <div className="rounded-xl p-5 flex-1 flex flex-col" style={GLASS}>
            <h3 className="font-semibold text-on-surface mb-6 flex items-center gap-2" style={{ fontFamily: 'Geist', fontSize: '24px' }}>
              <span className="material-symbols-outlined">tune</span> Capabilities
            </h3>
            <div className="space-y-5 flex-1">
              {[
                { label: 'Deepfake Detection', status: 'Not available', icon: 'block', color: 'text-outline' },
                { label: 'AI Generative Analysis', status: 'Not available', icon: 'block', color: 'text-outline' },
                { label: 'Pixel Manipulation', status: 'Not available', icon: 'block', color: 'text-outline' },
                { label: 'Lip-Sync Analysis', status: 'Not available', icon: 'block', color: 'text-outline' },
                { label: 'Blink Rate Analysis', status: 'Not available', icon: 'block', color: 'text-outline' },
              ].map((cap) => (
                <div key={cap.label} className="space-y-2">
                  <div className="flex justify-between items-center">
                    <label className="font-label-code text-label-code text-on-surface-variant">{cap.label}</label>
                    <span className={`font-label-code text-label-code ${cap.color} flex items-center gap-1`}>
                      <span className="material-symbols-outlined" style={{ fontSize: '14px' }}>{cap.icon}</span>
                      {cap.status}
                    </span>
                  </div>
                  <div className="h-1 w-full rounded-full overflow-hidden" style={{ background: 'rgba(29,32,35,1)' }}>
                    <div className="h-full rounded-full" style={{ width: '0%', background: 'rgba(73,68,84,0.5)', transition: 'width 0.3s' }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Center — Unavailable state */}
        <div className="col-span-6 flex flex-col">
          <div
            className="rounded-xl flex-1 relative overflow-hidden flex flex-col items-center justify-center"
            style={{ ...GLASS, border: '1px solid rgba(73,68,84,0.3)' }}
          >
            {/* Decorative icon */}
            <span className="material-symbols-outlined text-outline mb-6" style={{ fontSize: '80px', opacity: 0.4 }}>
              shield
            </span>

            <h2 className="text-on-surface mb-3" style={{ fontFamily: 'Geist', fontSize: '28px', fontWeight: 600 }}>
              Analysis Pipeline Not Yet Available
            </h2>

            <p className="text-on-surface-variant max-w-md text-center mb-6" style={{ fontFamily: 'Inter', fontSize: '14px', lineHeight: 1.6 }}>
              The media verification pipeline is currently under development.
              Once implemented, this page will analyze uploaded images and videos
              for manipulation, synthetic content, and AI-generated artifacts.
            </p>

            <div className="flex items-center gap-2 px-4 py-2 rounded-lg" style={{ background: 'rgba(29,32,35,0.6)', border: '1px solid rgba(255,255,255,0.08)' }}>
              <span className="material-symbols-outlined text-yellow-400" style={{ fontSize: '16px' }}>info</span>
              <span className="font-label-code text-label-code text-outline" style={{ fontSize: '11px' }}>
                No analysis will be performed — no fabricated results will be shown
              </span>
            </div>
          </div>
        </div>

        {/* Right — Status */}
        <div className="col-span-3 flex flex-col">
          <div className="rounded-xl p-5 flex-1 flex flex-col justify-between" style={GLASS}>
            <h3 className="font-semibold text-on-surface mb-4 flex items-center gap-2" style={{ fontFamily: 'Geist', fontSize: '24px' }}>
              <span className="material-symbols-outlined">donut_large</span> Status
            </h3>

            {/* Status indicator */}
            <div className="flex flex-col items-center justify-center flex-1">
              <div className="w-20 h-20 rounded-full flex items-center justify-center mb-4" style={{ background: 'rgba(29,32,35,0.8)', border: '2px solid rgba(73,68,84,0.4)' }}>
                <span className="material-symbols-outlined text-outline" style={{ fontSize: '36px' }}>hourglass_empty</span>
              </div>
              <span className="text-on-surface-variant font-label-caps text-label-caps mb-1">PIPELINE STATUS</span>
              <span className="text-outline" style={{ fontFamily: 'JetBrains Mono', fontSize: '12px' }}>Under Development</span>
            </div>

            {/* What will be available */}
            <div className="mt-6 space-y-3">
              <p className="text-outline font-label-code text-label-code" style={{ fontSize: '10px', letterSpacing: '0.1em' }}>
                PLANNED CAPABILITIES
              </p>
              {['Deepfake detection', 'AI-generated content analysis', 'Pixel manipulation detection', 'Lip-sync verification'].map((item) => (
                <div key={item} className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-outline" style={{ fontSize: '14px' }}>radio_button_unchecked</span>
                  <span className="text-on-surface-variant" style={{ fontFamily: 'Inter', fontSize: '12px' }}>{item}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
