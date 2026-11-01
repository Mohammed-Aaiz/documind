import { useState } from 'react';
import type { Page } from '../../types';
import { useWorkspace } from '../../context/WorkspaceContext';
import { useAuth } from '../../context/AuthContext';
import { WORKSPACES } from './config';

export const Icon = ({ name, className = '' }: { name: string; className?: string }) => <span aria-hidden="true" className={`material-symbols-outlined ${className}`}>{name}</span>;

export function WorkspaceSidebar({ page, onNavigate, open, onClose }: { page: Page; onNavigate: (page: Page) => void; open: boolean; onClose: () => void }) {
  const { workspace, setWorkspace, sessions, activeSessionId, openConversation, startNewConversation, sessionsLoading, sessionsError, refreshSessions, deleteConversation } = useWorkspace();
  const { user, logout } = useAuth();
  const [search, setSearch] = useState('');
  const [deleteId, setDeleteId] = useState<string | null>(null);
  return <>
    {open && <button className="dm-sidebar-scrim" aria-label="Close navigation" onClick={onClose} />}
    <aside className={`dm-sidebar ${open ? 'is-open' : ''}`}>
      <button className="dm-brand" onClick={() => { onNavigate('workspace'); onClose(); }}><span className="dm-brand-symbol"><Icon name="auto_stories" /></span>DocuMind<span className="dm-brand-dot">.</span></button>
      <p className="dm-sidebar-label">YOUR SPACE</p>
      <div className="dm-mode-switch" aria-label="Workspace">
        {(['student', 'research'] as const).map((mode) => <button key={mode} aria-pressed={workspace === mode} onClick={() => { setWorkspace(mode); onNavigate('workspace'); onClose(); setSearch(''); }}><Icon name={WORKSPACES[mode].icon} />{WORKSPACES[mode].label}</button>)}
      </div>
      <button className="dm-new-chat" onClick={() => { void startNewConversation(); onNavigate('workspace'); onClose(); }}><Icon name="add" />New {workspace === 'student' ? 'study' : 'research'} chat<kbd>↗</kbd></button>
      <nav className="dm-primary-nav" aria-label="Main navigation">
        {([{ page: 'workspace', label: 'Workspace', icon: 'space_dashboard' }, { page: 'reliability', label: 'Evidence & reliability', icon: 'verified_user' }, { page: 'verification', label: 'Media analysis', icon: 'image_search' }] as const).map((item) => <button key={item.page} aria-current={page === item.page ? 'page' : undefined} onClick={() => { onNavigate(item.page); onClose(); }}><Icon name={item.icon} />{item.label}</button>)}
      </nav>
      <div className="dm-history-heading"><span className="dm-sidebar-label">{workspace.toUpperCase()} CHATS</span><span>{sessions.length}</span></div>
      <label className="dm-chat-search"><Icon name="search" /><input aria-label="Search this workspace's chats" placeholder="Find a conversation" value={search} onChange={(event) => setSearch(event.target.value)} /></label>
      <div className="dm-history">
        {sessionsLoading && <p className="dm-sidebar-hint" role="status">Loading chats…</p>}
        {sessionsError && <div className="dm-sidebar-hint" role="alert"><p>{sessionsError}</p><button className="dm-text-button" onClick={() => void refreshSessions()}>Retry loading chats</button></div>}
        {!sessionsLoading && !sessionsError && sessions.length === 0 && <p className="dm-sidebar-hint">Your conversations will live here, separate from your {workspace === 'student' ? 'research' : 'study'} chats.</p>}
        {!sessionsLoading && !sessionsError && search && sessions.length > 0 && !sessions.some((session) => (session.preview ?? '').toLowerCase().includes(search.toLowerCase())) && <p className="dm-sidebar-hint">No conversations match this search.</p>}
        {sessions.filter((session) => (session.preview ?? '').toLowerCase().includes(search.toLowerCase())).map((session) => <div className={`dm-history-row ${session.id === activeSessionId ? 'is-active' : ''}`} key={session.id}>
          <button onClick={() => { void openConversation(session.id); onNavigate('workspace'); onClose(); }}><Icon name="chat_bubble" /><span>{session.preview || 'Untitled conversation'}</span></button>
          <button className="dm-delete-chat" aria-label={`Delete ${session.preview || 'untitled chat'}`} onClick={() => setDeleteId(session.id)}><Icon name="close" /></button>
        </div>)}
      </div>
      <div className="dm-sidebar-footer">
        <div className="dm-space-note"><Icon name="folder_copy" /><span>One source library.<br /><strong>Two ways to think.</strong></span></div>
        <button className="dm-account" onClick={() => { onNavigate('settings'); onClose(); }}><span className="dm-avatar">{user.name.charAt(0).toUpperCase()}</span><span><strong>{user.name}</strong><small>Account & preferences</small></span><Icon name="settings" /></button>
        <button className="dm-signout" onClick={logout}>Sign out <Icon name="logout" /></button>
      </div>
    </aside>
    {deleteId && <div className="dm-modal-backdrop"><div className="dm-modal" role="alertdialog" aria-modal="true" aria-labelledby="delete-chat-heading"><h2 id="delete-chat-heading">Delete this conversation?</h2><p>The chat and its messages will be removed. Your documents will remain in the library.</p><div><button className="dm-button" onClick={() => setDeleteId(null)}>Keep chat</button><button className="dm-button dm-danger" onClick={() => { void deleteConversation(deleteId); setDeleteId(null); }}>Delete chat</button></div></div></div>}
  </>;
}
