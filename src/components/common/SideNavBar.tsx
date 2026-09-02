import React from 'react';
import { Page } from '../../types';

interface SideNavBarProps {
  currentPage: Page;
  onNavigate: (page: Page) => void;
}

interface NavItem {
  icon: string;
  label: string;
  page: Page;
}

const NAV_ITEMS: NavItem[] = [
  { icon: 'psychology', label: 'Core', page: 'workspace' },
  { icon: 'qr_code_2', label: 'Threads', page: 'workspace' },
  { icon: 'qr_code_scanner', label: 'Verification', page: 'verification' },
  { icon: 'insert_chart', label: 'Analytics', page: 'reliability' },
  { icon: 'settings', label: 'System', page: 'settings' },
];

export const SideNavBar: React.FC<SideNavBarProps> = ({ currentPage, onNavigate }) => {
  const isActive = (item: NavItem) => {
    if (item.page === 'workspace' && currentPage === 'workspace') return true;
    return item.page === currentPage;
  };

  return (
    <aside
      className="h-screen w-64 fixed left-0 top-0 z-50 hidden md:flex flex-col"
      style={{
        background: 'rgba(5,7,10,0.70)',
        backdropFilter: 'blur(24px)',
        WebkitBackdropFilter: 'blur(24px)',
        borderRight: '1px solid rgba(255,255,255,0.1)',
        boxShadow: '0 0 40px rgba(139,92,246,0.15), inset 1px 1px 0px rgba(255,255,255,0.1)',
      }}
    >
      {/* Branding */}
      <div className="p-6 pb-6 border-b border-white/5">
        <div className="flex items-center gap-4 mb-2">
          <div
            className="w-10 h-10 rounded-full flex items-center justify-center"
            style={{
              background: 'linear-gradient(135deg, #8B5CF6, #06B6D4)',
              boxShadow: '0 0 15px rgba(139,92,246,0.4)',
            }}
          >
            <span className="material-symbols-outlined text-white text-[20px]">psychology</span>
          </div>
          <div>
            <h1
              className="font-bold bg-clip-text text-transparent"
              style={{
                backgroundImage: 'linear-gradient(135deg, #8B5CF6, #06B6D4)',
                fontSize: '20px',
                fontFamily: 'Geist',
              }}
            >
              The Oracle
            </h1>
            <p className="text-outline" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px', letterSpacing: '0.1em', fontWeight: 700 }}>
              V.2.0.4 AI Core
            </p>
          </div>
        </div>
      </div>

      {/* Nav links */}
      <nav className="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const active = isActive(item);
          return (
            <button
              key={item.label}
              onClick={() => onNavigate(item.page)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-left transition-all duration-200 ${
                active
                  ? 'text-cyber-cyan border-l-4 border-cyber-cyan bg-surface-container-highest/30'
                  : 'text-outline hover:text-on-surface hover:bg-surface-bright/20 hover:shadow-[0_0_15px_rgba(6,182,212,0.2)]'
              }`}
              style={{
                fontFamily: 'JetBrains Mono',
                fontSize: '10px',
                letterSpacing: '0.1em',
                fontWeight: 700,
                transform: active ? 'scale(0.98)' : undefined,
              }}
            >
              <span
                className="material-symbols-outlined"
                style={active ? { fontVariationSettings: "'FILL' 1" } : undefined}
              >
                {item.icon}
              </span>
              {item.label}
            </button>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-white/5 space-y-3">
        <button
          className="w-full py-3 rounded-lg text-black font-bold transition-all duration-300 flex items-center justify-center gap-2"
          style={{
            fontFamily: 'JetBrains Mono',
            fontSize: '10px',
            letterSpacing: '0.1em',
            background: 'linear-gradient(135deg, #8B5CF6, #06B6D4)',
            boxShadow: '0 0 15px rgba(139,92,246,0.3)',
          }}
        >
          <span className="material-symbols-outlined text-[16px]">bolt</span>
          Initiate Pulse
        </button>
        <div className="flex justify-around pt-2">
          <button className="text-outline hover:text-cyber-cyan transition-colors" title="Help">
            <span className="material-symbols-outlined text-sm">help</span>
          </button>
          <button className="text-outline hover:text-cyber-cyan transition-colors" title="Privacy">
            <span className="material-symbols-outlined text-sm">security</span>
          </button>
        </div>
      </div>
    </aside>
  );
};
