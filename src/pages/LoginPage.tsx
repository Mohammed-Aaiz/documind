import React, { useState, useRef } from 'react';
import { useAuth } from '../context/AuthContext';

interface LoginPageProps {
  onLoginSuccess: () => void;
}

export const LoginPage: React.FC<LoginPageProps> = ({ onLoginSuccess }) => {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const panelRef = useRef<HTMLDivElement>(null);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!panelRef.current) return;
    const rect = panelRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    panelRef.current.style.background = `radial-gradient(circle at ${x}px ${y}px, rgba(139,92,246,0.07), rgba(5,7,10,0.70) 45%)`;
  };

  const handleMouseLeave = () => {
    if (!panelRef.current) return;
    panelRef.current.style.background = 'rgba(5,7,10,0.70)';
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');
    try {
      await login(email, password);
      onLoginSuccess();
    } catch (err) {
      if (err instanceof Error && err.message) {
        setError(err.message);
      } else {
        setError('Connection failed. Please check your credentials.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center relative">
      {/* Decorative orbit rings behind the panel */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none" aria-hidden="true">
        <div
          className="absolute rounded-full border border-white/10 opacity-20"
          style={{ width: 560, height: 560, top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }}
        />
        <div
          className="absolute rounded-full border border-cyber-cyan/25 opacity-35"
          style={{
            width: 420,
            height: 420,
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%) rotateX(65deg) rotateZ(15deg)',
          }}
        />
        <div
          className="absolute rounded-full border border-electric-violet/15 opacity-25"
          style={{
            width: 300,
            height: 300,
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%) rotateX(55deg) rotateY(-20deg)',
          }}
        />
        {/* Pulsing center glow */}
        <div
          className="absolute rounded-full opacity-30 animate-pulse"
          style={{
            width: 160,
            height: 160,
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            background: 'radial-gradient(circle, rgba(139,92,246,0.4), transparent 70%)',
          }}
        />
      </div>

      {/* Login container */}
      <main className="relative z-10 w-full max-w-[500px] px-8">
        {/* Header */}
        <header className="text-center mb-12">
          <h1 className="font-headline-lg text-on-surface mb-4 font-bold" style={{ fontSize: '36px', letterSpacing: '-0.02em' }}>
            DOCUMIND:{' '}
            <span
              className="bg-clip-text text-transparent"
              style={{ backgroundImage: 'linear-gradient(90deg, #8B5CF6, #06B6D4)' }}
            >
              NEURAL AUTH CORE
            </span>
          </h1>
          <p className="font-body-sm text-on-surface-variant tracking-wider uppercase text-sm">
            Establish connection to the intelligence cluster
          </p>
        </header>

        {/* Glass panel */}
        <div
          ref={panelRef}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          className="rounded-xl p-12 relative overflow-hidden transition-all duration-300"
          style={{
            background: 'rgba(5,7,10,0.70)',
            backdropFilter: 'blur(24px)',
            WebkitBackdropFilter: 'blur(24px)',
            borderTop: '1px solid rgba(255,255,255,0.1)',
            borderLeft: '1px solid rgba(255,255,255,0.1)',
            borderRight: '1px solid rgba(255,255,255,0.03)',
            borderBottom: '1px solid rgba(255,255,255,0.03)',
            boxShadow: '0 0 60px rgba(139,92,246,0.15)',
          }}
        >
          {/* Top edge light */}
          <div
            className="absolute top-0 left-0 w-full h-px pointer-events-none"
            style={{ background: 'linear-gradient(90deg, transparent, rgba(139,92,246,0.5), transparent)' }}
          />

          {error && (
            <div className="mb-6 p-3 rounded bg-error/10 border border-error/30 text-error text-xs font-mono">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="flex flex-col gap-8">
            {/* Identity Matrix */}
            <div className="relative group">
              <label
                htmlFor="identity"
                className="font-label-code text-label-code text-electric-violet mb-2 block uppercase tracking-widest"
              >
                Identity Matrix
              </label>
              <div className="relative flex items-center">
                <span className="material-symbols-outlined absolute left-0 text-outline group-focus-within:text-electric-violet transition-colors">
                  fingerprint
                </span>
                <input
                  id="identity"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Enter credentials..."
                  className="w-full bg-transparent border-0 border-b border-outline-variant pl-8 py-3 text-on-surface font-body-base focus:ring-0 focus:border-electric-violet focus:outline-none transition-all duration-300 placeholder:text-outline/50"
                  style={{ WebkitBoxShadow: 'none' }}
                />
              </div>
            </div>

            {/* Access Cipher */}
            <div className="relative group">
              <label
                htmlFor="cipher"
                className="font-label-code text-label-code text-electric-violet mb-2 flex items-center justify-between uppercase tracking-widest"
              >
                <span>Access Cipher</span>
                <button
                  type="button"
                  className="text-cyber-cyan hover:text-secondary transition-colors font-mono text-[11px] normal-case tracking-normal"
                >
                  Override?
                </button>
              </label>
              <div className="relative flex items-center">
                <span className="material-symbols-outlined absolute left-0 text-outline group-focus-within:text-electric-violet transition-colors">
                  key
                </span>
                <input
                  id="cipher"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full bg-transparent border-0 border-b border-outline-variant pl-8 py-3 text-on-surface font-body-base focus:ring-0 focus:border-electric-violet focus:outline-none transition-all duration-300 placeholder:text-outline/50"
                />
              </div>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={isLoading}
              className="mt-2 w-full py-4 rounded-lg text-white font-label-caps text-label-caps font-bold tracking-[0.2em] uppercase relative overflow-hidden shimmer-btn group disabled:opacity-50 transition-all duration-300"
              style={{
                background: 'linear-gradient(90deg, #8B5CF6, #a078ff)',
              }}
            >
              <span className="relative z-10 flex items-center justify-center gap-2">
                {isLoading ? (
                  <>
                    <span className="material-symbols-outlined text-[18px] animate-spin">progress_activity</span>
                    Authenticating...
                  </>
                ) : (
                  <>
                    Initialize Connection
                    <span className="material-symbols-outlined text-[16px] group-hover:translate-x-1 transition-transform">
                      arrow_forward
                    </span>
                  </>
                )}
              </span>
            </button>
          </form>
        </div>

        {/* Footer links */}
        <div className="mt-8 text-center flex justify-center gap-6">
          <a href="#" className="font-label-code text-label-code text-outline hover:text-cyber-cyan transition-colors flex items-center gap-1">
            <span className="material-symbols-outlined text-[14px]">policy</span>
            Protocols
          </a>
          <a href="#" className="font-label-code text-label-code text-outline hover:text-cyber-cyan transition-colors flex items-center gap-1">
            <span className="material-symbols-outlined text-[14px]">support_agent</span>
            Support
          </a>
        </div>
      </main>

      <style>{`
        .shimmer-btn::after {
          content: '';
          position: absolute;
          top: 0; left: 0;
          width: 100%; height: 100%;
          background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
          transform: translateX(-100%);
        }
        .shimmer-btn:hover::after {
          animation: shimmerSlide 1.5s infinite;
        }
        @keyframes shimmerSlide {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
      `}</style>
    </div>
  );
};
