import React, { useState } from 'react';
import { Page } from './types';
import { useAuth } from './context/AuthContext';
import { CosmicBackground } from './components/3d/CosmicBackground';
import { TopNavBar } from './components/common/TopNavBar';
import { SideNavBar } from './components/common/SideNavBar';
import { LoginPage } from './pages/LoginPage';
import { WorkspacePage } from './pages/WorkspacePage';
import { VerificationPage } from './pages/VerificationPage';
import { ReliabilityPage } from './pages/ReliabilityPage';
import { SettingsPage } from './pages/SettingsPage';

const App: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const [currentPage, setCurrentPage] = useState<Page>('login');

  const handleNavigate = (page: Page) => {
    setCurrentPage(page);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleLoginSuccess = () => {
    setCurrentPage('workspace');
  };

  // Login page — full screen, no shell
  if (!isAuthenticated || currentPage === 'login') {
    return (
      <div className="relative min-h-screen w-screen bg-void-black text-on-surface overflow-hidden">
        <CosmicBackground />
        <LoginPage onLoginSuccess={handleLoginSuccess} />
      </div>
    );
  }

  // App shell — sidebar + topnav + page content
  return (
    <div className="relative min-h-screen w-screen bg-void-black text-on-surface font-body-base overflow-x-hidden">
      <CosmicBackground />
      <SideNavBar currentPage={currentPage} onNavigate={handleNavigate} />
      <TopNavBar currentPage={currentPage} onNavigate={handleNavigate} />

      {/* Main content shifted right of sidebar */}
      <main className="ml-64 min-h-screen">
        {currentPage === 'workspace' && <WorkspacePage onNavigate={handleNavigate} />}
        {currentPage === 'verification' && <VerificationPage onNavigate={handleNavigate} />}
        {currentPage === 'reliability' && <ReliabilityPage onNavigate={handleNavigate} />}
        {currentPage === 'settings' && <SettingsPage onNavigate={handleNavigate} />}
      </main>
    </div>
  );
};

export default App;
