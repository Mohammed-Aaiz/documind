import React from 'react';
import { Page } from '../../types';
import { useAuth } from '../../context/AuthContext';

interface TopNavBarProps {
  currentPage: Page;
  onNavigate: (page: Page) => void;
}

const PAGE_LABELS: Record<Page, string> = {
  login: 'Login',
  workspace: 'Oracle Interface',
  verification: 'DocuMind Core',
  reliability: 'Reliability Center',
  settings: 'System Settings',
};

export const TopNavBar: React.FC<TopNavBarProps> = ({ currentPage, onNavigate }) => {
  const { user } = useAuth();
  const initial = user.name ? user.name[0].toUpperCase() : 'U';

  return (
    <nav
      className="fixed top-4 right-4 md:right-8 left-4 md:left-72 h-16 rounded-xl z-40 flex items-center justify-between px-4 md:px-8"
      style={{
        background: 'rgba(25,28,31,0.60)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        border: '1px solid rgba(255,255,255,0.1)',
        boxShadow: 'inset 1px 1px 0px rgba(255,255,255,0.05), 0 0 30px rgba(0,0,0,0.5)',
      }}
    >
      {/* Left: title + search */}
      <div className="flex items-center gap-6">
        <span className="text-on-surface font-semibold" style={{ fontFamily: 'Geist', fontSize: '20px' }}>
          {PAGE_LABELS[currentPage]}
        </span>
        {currentPage === 'workspace' && (
          <div className="relative hidden lg:block">
            <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-[18px]">
              search
            </span>
            <input
              type="text"
              placeholder="Search knowledge base..."
              className="bg-transparent border-b border-white/10 focus:border-electric-violet focus:outline-none text-sm pl-9 pr-4 py-2 w-56 transition-all text-on-surface placeholder-outline/60"
              style={{ fontFamily: 'Inter', fontSize: '14px' }}
            />
          </div>
        )}
      </div>

      {/* Right: page links + actions + avatar */}
      <div className="flex items-center gap-4">
        {/* Quick page nav pills */}
        <ul className="hidden md:flex gap-1" style={{ fontFamily: 'JetBrains Mono', fontSize: '12px' }}>
          {[
            { label: 'Workspace', page: 'workspace' as Page },
            { label: 'Verification', page: 'verification' as Page },
            { label: 'Reliability', page: 'reliability' as Page },
          ].map(({ label, page }) => (
            <li key={page}>
              <button
                onClick={() => onNavigate(page)}
                className={`px-3 py-1.5 rounded transition-all ${
                  currentPage === page
                    ? 'text-primary border-b-2 border-primary font-bold'
                    : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high/40'
                }`}
              >
                {label}
              </button>
            </li>
          ))}
        </ul>

        <div className="flex items-center gap-3 ml-2">
          <button className="text-outline hover:text-cyber-cyan transition-colors" title="Notifications">
            <span className="material-symbols-outlined">notifications_active</span>
          </button>
          <button
            onClick={() => onNavigate('settings')}
            className="w-8 h-8 rounded-full border border-white/10 flex items-center justify-center text-[12px] font-bold text-white transition-all hover:border-electric-violet/50"
            style={{ background: 'linear-gradient(135deg, #8B5CF6, #06B6D4)' }}
            title="Settings"
          >
            {initial}
          </button>
        </div>
      </div>
    </nav>
  );
};
