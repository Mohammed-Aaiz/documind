import React, { useState } from 'react';
import { useSettings, PersistedSettings } from '../context/SettingsContext';
import { useAuth } from '../context/AuthContext';
import { Page } from '../types';

interface SettingsPageProps {
  onNavigate: (page: Page) => void;
}

export const SettingsPage: React.FC<SettingsPageProps> = ({ onNavigate }) => {
  const {
    settings,
    loadState,
    loadError,
    saveState,
    saveError,
    updateAIProcessing,
    updateEnvironment,
    applyConfiguration,
    discardChanges,
  } = useSettings();
  // Identity comes from the authenticated session (`GET /api/auth/me`), never
  // from a placeholder.
  const { user, logout } = useAuth();

  const [copiedId, setCopiedId] = useState(false);

  const handleCopyEmail = () => {
    navigator.clipboard.writeText(user.email);
    setCopiedId(true);
    setTimeout(() => setCopiedId(false), 2000);
  };

  const depthLabels = ['Fast', 'Balanced', 'Analytical', 'Deep', 'Comprehensive'];
  const displayName = user.name || user.email || 'Signed-in user';

  return (
    <div className="pt-28 px-4 md:px-16 pb-16 min-h-screen relative z-10 overflow-y-auto">
      <div className="max-w-[1600px] mx-auto">
        {/* Page Header */}
        <header className="mb-8 flex flex-col md:flex-row justify-between items-start md:items-end gap-4">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h2 className="font-bold text-on-surface tracking-tight" style={{ fontFamily: 'Geist', fontSize: 'clamp(28px, 4vw, 56px)', lineHeight: 1.1, letterSpacing: '-0.04em' }}>
                System Settings
              </h2>
              <span className="px-2.5 py-0.5 rounded-full bg-cyber-cyan/20 border border-cyber-cyan/40 text-cyber-cyan font-mono text-[10px] font-bold">
                NODE CONFIG
              </span>
            </div>
            <p className="text-on-surface-variant max-w-2xl" style={{ fontFamily: 'Inter', fontSize: '16px', lineHeight: 1.6 }}>
              Configure your neural link preferences, security protocols, and visual environment for DocuMind.
            </p>
          </div>

          <div className="hidden lg:flex items-center gap-4">
            <span className="flex items-center gap-2 text-cyber-cyan bg-cyber-cyan/10 px-4 py-2 rounded-full border border-cyber-cyan/20 shadow-[0_0_15px_rgba(6,182,212,0.15)]" style={{ fontFamily: 'JetBrains Mono', fontSize: '12px' }}>
              <span className="w-2 h-2 rounded-full bg-cyber-cyan animate-pulse" />
              Secure Connection Active
            </span>
          </div>
        </header>

        {/* Server state. These banners are the ONLY place this page claims that
            anything was stored: success requires a confirmed server response. */}
        {loadState === 'loading' && (
          <div role="status" className="mb-6 p-4 rounded-xl bg-surface-container-low/60 border border-white/10 text-on-surface-variant text-xs" style={{ fontFamily: 'JetBrains Mono' }}>
            Loading your saved settings from the server...
          </div>
        )}
        {loadState === 'unavailable' && (
          <div role="alert" className="mb-6 p-4 rounded-xl bg-error/10 border border-error/40 text-on-surface text-xs" style={{ fontFamily: 'JetBrains Mono' }}>
            {loadError} The controls below show the server's own column defaults and the server persisted nothing for this session.
          </div>
        )}
        {saveState === 'saved' && (
          <div role="status" className="mb-6 p-4 rounded-xl bg-gradient-to-r from-electric-violet/20 to-cyber-cyan/20 border border-cyber-cyan text-white text-xs flex items-center justify-between shadow-[0_0_25px_rgba(6,182,212,0.3)]" style={{ fontFamily: 'JetBrains Mono' }}>
            <span className="flex items-center gap-2">
              <span className="material-symbols-outlined text-cyber-cyan">check_circle</span>
              Settings saved to the server.
            </span>
            <span className="text-secondary font-bold">SAVED</span>
          </div>
        )}
        {saveState === 'error' && (
          <div role="alert" className="mb-6 p-4 rounded-xl bg-error/10 border border-error/40 text-on-surface text-xs" style={{ fontFamily: 'JetBrains Mono' }}>
            {saveError}
          </div>
        )}

        {/* Profile Section */}
        <section className="rounded-2xl p-8 mb-8 transition-shadow duration-500 relative overflow-hidden border border-white/10" style={{ background: 'rgba(5,7,10,0.70)', backdropFilter: 'blur(24px)', WebkitBackdropFilter: 'blur(24px)', borderTop: '1px solid rgba(255,255,255,0.1)', borderLeft: '1px solid rgba(255,255,255,0.1)' }}>
          <div className="absolute top-0 right-0 w-64 h-64 bg-electric-violet/10 rounded-full blur-[80px] -translate-y-1/2 translate-x-1/4 pointer-events-none" />

          <div className="flex flex-col md:flex-row items-center md:items-start gap-8 relative z-10">
            {/* Avatar */}
            <div className="relative group cursor-pointer">
              <div className="w-28 h-28 md:w-32 md:h-32 rounded-full p-1 bg-gradient-to-tr from-electric-violet via-surface-container to-cyber-cyan shadow-[0_0_30px_rgba(139,92,246,0.3)]">
                <div className="w-full h-full rounded-full border-4 border-surface-deep flex items-center justify-center text-white font-bold text-3xl" style={{ fontFamily: 'Geist', background: 'linear-gradient(135deg, #8B5CF6, #06B6D4)' }}>
                  {displayName ? displayName[0].toUpperCase() : 'U'}
                </div>
              </div>
              <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity rounded-full pointer-events-none">
                <span className="material-symbols-outlined text-white text-3xl drop-shadow-lg">photo_camera</span>
              </div>
              <div className="absolute bottom-2 right-2 w-5 h-5 bg-cyber-cyan rounded-full border-2 border-surface-deep shadow-[0_0_10px_rgba(6,182,212,0.8)]" />
            </div>

            {/* User Info */}
            <div className="flex-1 text-center md:text-left">
              <h3 className="text-2xl font-bold text-white mb-1" style={{ fontFamily: 'Geist' }}>{displayName}</h3>
              <p className="text-electric-violet mb-4" style={{ fontFamily: 'JetBrains Mono', fontSize: '12px' }}>Authenticated session</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 mt-6">
                <div className="space-y-1">
                  <label className="text-outline block" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px', letterSpacing: '0.1em', fontWeight: 700 }}>EMAIL</label>
                  <div className="flex items-center gap-2 bg-surface-container-low/60 px-3 py-2 rounded-lg border border-white/5" style={{ fontFamily: 'JetBrains Mono', fontSize: '12px' }}>
                    <span className="text-on-surface-variant font-semibold">{user.email}</span>
                    <button
                      onClick={handleCopyEmail}
                      className="ml-auto text-outline hover:text-cyber-cyan transition-colors"
                      title="Copy email"
                    >
                      <span className="material-symbols-outlined text-[16px]">
                        {copiedId ? 'check' : 'content_copy'}
                      </span>
                    </button>
                  </div>
                </div>
                <div className="space-y-1">
                  <label className="text-outline block" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px', letterSpacing: '0.1em', fontWeight: 700 }}>AVATAR</label>
                  <p className="bg-surface-container-low/60 border border-white/5 rounded-lg px-3 py-2 text-on-surface-variant" style={{ fontFamily: 'JetBrains Mono', fontSize: '12px' }}>
                    {user.avatarUrl || 'No avatar set for this account'}
                  </p>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="flex flex-row md:flex-col gap-3 w-full md:w-auto">
              <p className="text-outline text-xs md:max-w-[16rem]" style={{ fontFamily: 'JetBrains Mono' }}>
                Profile editing is unavailable: the API exposes no profile-update endpoint.
              </p>
              <button
                onClick={() => {
                  logout();
                  onNavigate('login');
                }}
                className="flex-1 md:flex-none px-6 py-2.5 rounded-lg border border-outline-variant hover:border-error/50 hover:bg-error/10 text-on-surface-variant hover:text-error transition-all"
                style={{ fontFamily: 'JetBrains Mono', fontSize: '12px' }}
              >
                Sign Out
              </button>
            </div>
          </div>
        </section>

        {/* Bento Grid for Settings Categories */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mb-8">
          {/* Security Protocols (Span 8) */}
          <section className="rounded-2xl lg:col-span-8 p-6 transition-shadow duration-500 flex flex-col border border-white/10" style={{ background: 'rgba(5,7,10,0.70)', backdropFilter: 'blur(24px)', WebkitBackdropFilter: 'blur(24px)', borderTop: '1px solid rgba(255,255,255,0.1)', borderLeft: '1px solid rgba(255,255,255,0.1)' }}>
            <div className="flex items-center gap-3 mb-6 border-b border-white/5 pb-4">
              <div className="w-8 h-8 rounded bg-cyber-cyan/10 flex items-center justify-center border border-cyber-cyan/20">
                <span className="material-symbols-outlined text-cyber-cyan text-[20px]">security</span>
              </div>
              <h4 className="text-xl text-white font-bold" style={{ fontFamily: 'Geist' }}>Security Protocols</h4>
            </div>

            <div className="flex-1 space-y-5">
              {/* Two-Factor Authentication */}
              <div className="rounded-xl p-5 flex items-center justify-between group hover:border-electric-violet/30 transition-colors" style={{ background: 'rgba(5,7,10,0.60)', backdropFilter: 'blur(20px)', borderTop: '1px solid rgba(255,255,255,0.1)', borderLeft: '1px solid rgba(255,255,255,0.1)' }}>
                <div>
                  <h5 className="text-base font-semibold text-white mb-1 flex items-center gap-2">
                    Two-Factor Authentication
                    <span className="bg-surface-container-high text-outline font-mono text-[9px] font-bold px-2 py-0.5 rounded">
                      NOT IMPLEMENTED
                    </span>
                  </h5>
                  <p className="text-xs text-on-surface-variant">
                    No two-factor authentication exists in this build. The control is shown as unavailable rather than as a saved preference.
                  </p>
                </div>
                <button
                  type="button"
                  disabled
                  aria-disabled="true"
                  title="Two-factor authentication is not implemented"
                  className="w-12 h-6 rounded-full relative bg-surface-container-high opacity-60 cursor-not-allowed"
                >
                  <div className="absolute top-1 left-1 w-4 h-4 rounded-full bg-white shadow-md" />
                </button>
              </div>

              {/* End-to-End Encryption */}
              <div className="rounded-xl p-5 flex items-center justify-between group hover:border-electric-violet/30 transition-colors" style={{ background: 'rgba(5,7,10,0.60)', backdropFilter: 'blur(20px)', borderTop: '1px solid rgba(255,255,255,0.1)', borderLeft: '1px solid rgba(255,255,255,0.1)' }}>
                <div>
                  <h5 className="text-base font-semibold text-white mb-1 flex items-center gap-2">
                    End-to-End Encryption
                    <span className="bg-surface-container-high text-outline font-mono text-[9px] font-bold px-2 py-0.5 rounded">
                      NOT IMPLEMENTED
                    </span>
                  </h5>
                  <p className="text-xs text-on-surface-variant">
                    No end-to-end encryption layer is implemented. Document data is stored by the DocuMind backend.
                  </p>
                </div>
                <button
                  type="button"
                  disabled
                  aria-disabled="true"
                  title="End-to-end encryption is not implemented"
                  className="w-12 h-6 rounded-full relative bg-surface-container-high opacity-60 cursor-not-allowed"
                >
                  <div className="absolute top-1 left-1 w-4 h-4 rounded-full bg-white shadow-md" />
                </button>
              </div>

              {/* Privacy info */}
              <div className="pt-2">
                <p className="text-on-surface-variant text-xs" style={{ fontFamily: 'JetBrains Mono' }}>
                  Documents you upload are stored by the DocuMind backend and processed by its local retrieval and QA models. Spoken answers use an external text-to-speech service.
                </p>
              </div>
            </div>
          </section>

          {/* AI Processing (Span 4) */}
          <section className="rounded-2xl lg:col-span-4 p-6 transition-shadow duration-500 relative overflow-hidden flex flex-col border border-white/10" style={{ background: 'rgba(5,7,10,0.70)', backdropFilter: 'blur(24px)', WebkitBackdropFilter: 'blur(24px)', borderTop: '1px solid rgba(255,255,255,0.1)', borderLeft: '1px solid rgba(255,255,255,0.1)' }}>
            <div className="absolute bottom-0 right-0 w-32 h-32 bg-cyber-cyan/10 rounded-full blur-[50px] pointer-events-none" />

            <div className="flex items-center gap-3 mb-6 border-b border-white/5 pb-4 relative z-10">
              <div className="w-8 h-8 rounded bg-electric-violet/10 flex items-center justify-center border border-electric-violet/20">
                <span className="material-symbols-outlined text-electric-violet text-[20px]">psychology</span>
              </div>
              <h4 className="text-xl text-white font-bold" style={{ fontFamily: 'Geist' }}>AI Processing</h4>
            </div>

            <div className="flex-1 space-y-6 relative z-10">
              {/* Slider for Depth */}
              <div className="space-y-3">
                <div className="flex justify-between items-end">
                  <label className="text-outline" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px', letterSpacing: '0.1em', fontWeight: 700 }}>ANALYSIS DEPTH</label>
                  <span className="text-cyber-cyan font-bold" style={{ fontFamily: 'JetBrains Mono', fontSize: '12px' }}>{depthLabels[settings.aiProcessing.depth - 1]}</span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="5"
                  value={settings.aiProcessing.depth}
                  onChange={(e) => updateAIProcessing({ depth: Number(e.target.value) })}
                  className="w-full h-1.5 bg-surface-container rounded-lg appearance-none cursor-pointer accent-electric-violet"
                />
                <div className="flex justify-between text-outline" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px' }}>
                  <span>Fast</span>
                  <span>Analytical</span>
                  <span>Creative</span>
                </div>
              </div>

              {/* Context retention */}
              <div className="space-y-2 pt-2">
                <label className="text-outline block" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px', letterSpacing: '0.1em', fontWeight: 700 }}>CONTEXT MEMORY WINDOW</label>
                <select
                  value={settings.aiProcessing.contextWindow}
                  onChange={(e) => updateAIProcessing({ contextWindow: e.target.value as PersistedSettings['aiProcessing']['contextWindow'] })}
                  className="w-full bg-surface-container-low/70 border border-white/10 rounded-lg px-3 py-2.5 text-on-surface focus:border-electric-violet/60 focus:ring-0 appearance-none cursor-pointer outline-none transition-colors"
                  style={{ fontFamily: 'JetBrains Mono', fontSize: '12px' }}
                >
                  <option value="session" className="bg-surface-deep text-white">Current Session Only</option>
                  <option value="24h" className="bg-surface-deep text-white">Rolling 24 Hours</option>
                  <option value="persistent" className="bg-surface-deep text-white">Persistent Knowledge Graph</option>
                </select>
              </div>
            </div>
          </section>

          {/* Appearance & Environment (Span 12) */}
          <section className="rounded-2xl lg:col-span-12 p-6 transition-shadow duration-500 border border-white/10" style={{ background: 'rgba(5,7,10,0.70)', backdropFilter: 'blur(24px)', WebkitBackdropFilter: 'blur(24px)', borderTop: '1px solid rgba(255,255,255,0.1)', borderLeft: '1px solid rgba(255,255,255,0.1)' }}>
            <div className="flex items-center gap-3 mb-6 border-b border-white/5 pb-4">
              <div className="w-8 h-8 rounded bg-surface-container-high flex items-center justify-center border border-white/10">
                <span className="material-symbols-outlined text-outline text-[20px]">palette</span>
              </div>
              <h4 className="text-xl text-white font-bold" style={{ fontFamily: 'Geist' }}>Environment Display</h4>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Theme Selection */}
              <div className="space-y-4">
                <label className="text-outline block" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px', letterSpacing: '0.1em', fontWeight: 700 }}>VISUAL THEME</label>
                <div className="flex gap-4">
                  <div
                    onClick={() => updateEnvironment({ theme: 'dark-cyber' })}
                    className="flex-1 h-24 rounded-xl border-2 border-electric-violet relative cursor-pointer overflow-hidden p-3 bg-void-black shadow-[0_0_20px_rgba(139,92,246,0.3)] flex flex-col justify-between"
                  >
                    <div className="space-y-1">
                      <div className="h-2 w-1/3 bg-electric-violet rounded" />
                      <div className="h-4 bg-surface-deep rounded border border-white/10" />
                    </div>
                    <div className="flex justify-between items-center text-electric-violet font-bold" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px' }}>
                      <span>Dark Cyber</span>
                      <span className="material-symbols-outlined text-[16px]">check_circle</span>
                    </div>
                  </div>

                  <div className="flex-1 h-24 rounded-xl border border-white/10 opacity-40 relative cursor-not-allowed overflow-hidden grayscale p-3 bg-neutral-900 flex flex-col justify-between">
                    <div className="space-y-1">
                      <div className="h-2 w-1/3 bg-neutral-600 rounded" />
                      <div className="h-4 bg-neutral-800 rounded" />
                    </div>
                    <span className="text-outline" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px' }}>Light (Disabled)</span>
                  </div>
                </div>
              </div>

              {/* Density */}
              <div className="space-y-4">
                <label className="text-outline block" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px', letterSpacing: '0.1em', fontWeight: 700 }}>DATA DENSITY</label>
                <div className="space-y-2" style={{ fontFamily: 'JetBrains Mono', fontSize: '12px' }}>
                  <label
                    onClick={() => updateEnvironment({ density: 'standard' })}
                    className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                      settings.environment.density === 'standard'
                        ? 'border-electric-violet/50 bg-electric-violet/10 text-white'
                        : 'border-white/5 bg-surface-container-low/40 text-on-surface-variant'
                    }`}
                  >
                    <input
                      type="radio"
                      checked={settings.environment.density === 'standard'}
                      readOnly
                      className="text-electric-violet"
                    />
                    <span>Standard (Comfortable)</span>
                  </label>

                  <label
                    onClick={() => updateEnvironment({ density: 'high' })}
                    className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                      settings.environment.density === 'high'
                        ? 'border-cyber-cyan/50 bg-cyber-cyan/10 text-cyber-cyan font-bold'
                        : 'border-white/5 bg-surface-container-low/40 text-on-surface-variant'
                    }`}
                  >
                    <input
                      type="radio"
                      checked={settings.environment.density === 'high'}
                      readOnly
                      className="text-cyber-cyan"
                    />
                    <span>High (Data Heavy)</span>
                  </label>
                </div>
              </div>

              {/* Glassmorphism preview */}
              <div className="space-y-4">
                <label className="text-outline block" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px', letterSpacing: '0.1em', fontWeight: 700 }}>GLASSMORPHISM INTENSITY</label>
                <div className="p-4 rounded-xl flex items-center justify-center h-24 border-dashed border-white/20 relative overflow-hidden" style={{ background: 'rgba(5,7,10,0.60)', backdropFilter: 'blur(20px)' }}>
                  <div className="absolute inset-0 bg-gradient-to-r from-electric-violet/25 to-cyber-cyan/25 blur-xl pointer-events-none" />
                  <span className="text-white z-10 font-bold drop-shadow-md" style={{ fontFamily: 'JetBrains Mono', fontSize: '12px' }}>
                    {settings.environment.glassIntensity}% Blur Active
                  </span>
                </div>
              </div>
            </div>
          </section>
        </div>

        {/* Footer Actions */}
        <div className="flex justify-end gap-4 pb-8">
          <button
            onClick={discardChanges}
            className="px-6 py-3 rounded-lg text-outline hover:text-white transition-colors cursor-pointer"
            style={{ fontFamily: 'JetBrains Mono', fontSize: '12px' }}
          >
            Discard Changes
          </button>
          <button
            onClick={() => { void applyConfiguration(); }}
            disabled={saveState === 'saving'}
            className="px-8 py-3 rounded-lg text-void-black font-bold bg-cyber-cyan hover:bg-secondary transition-colors shadow-[0_0_20px_rgba(6,182,212,0.3)] hover:shadow-[0_0_30px_rgba(6,182,212,0.6)] cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
            style={{ fontFamily: 'JetBrains Mono', fontSize: '12px' }}
          >
            {saveState === 'saving' ? 'Applying...' : 'Apply Configuration'}
          </button>
        </div>
      </div>
    </div>
  );
};
