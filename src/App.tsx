import React, { useState } from 'react';
import type { Page } from './types';
import { useAuth } from './context/AuthContext';
import { useWorkspace } from './context/WorkspaceContext';
import { WorkspaceSidebar, Icon } from './features/workspace/WorkspaceSidebar';
import { LoginPage } from './pages/LoginPage';
import { WorkspacePage } from './pages/WorkspacePage';
import { VerificationPage } from './pages/VerificationPage';
import { ReliabilityPage } from './pages/ReliabilityPage';
import { SettingsPage } from './pages/SettingsPage';

const App: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const { workspace } = useWorkspace();
  const [page, setPage] = useState<Page>('workspace');
  const [navigationOpen, setNavigationOpen] = useState(false);
  const navigate = (next: Page) => { setPage(next === 'login' ? 'workspace' : next); };
  if (!isAuthenticated) return <LoginPage onLoginSuccess={() => setPage('workspace')} />;
  return <div className="dm-app" data-workspace={workspace}>
    <a className="dm-skip-link" href="#main-content">Skip to content</a>
    <WorkspaceSidebar page={page} onNavigate={navigate} open={navigationOpen} onClose={() => setNavigationOpen(false)} />
    <main className="dm-main" id="main-content">
      <header className="dm-topbar"><div><button className="dm-icon-button dm-menu-toggle" aria-label="Open navigation" onClick={() => setNavigationOpen(true)}><Icon name="menu" /></button><span>My workspace</span><Icon name="chevron_right" /><strong>{page === 'workspace' ? (workspace === 'student' ? 'Study & learn' : 'Research & discover') : page === 'reliability' ? 'Evidence & reliability' : page === 'verification' ? 'Media analysis' : 'Settings'}</strong></div><span className="dm-topbar-note"><span />Evidence comes first</span></header>
      {page === 'workspace' ? <WorkspacePage onNavigate={navigate} /> : <div className="dm-utility-page">
        {page === 'verification' && <VerificationPage onNavigate={navigate} />}
        {page === 'reliability' && <ReliabilityPage onNavigate={navigate} />}
        {page === 'settings' && <SettingsPage onNavigate={navigate} />}
      </div>}
    </main>
  </div>;
};
export default App;
