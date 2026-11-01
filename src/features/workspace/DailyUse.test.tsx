import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ me: vi.fn(), list: vi.fn(), upload: vi.fn(), reprocess: vi.fn(), sessions: vi.fn(), create: vi.fn() }));
vi.mock('../../lib/api', async (original) => ({
  ...await original<typeof import('../../lib/api')>(), apiGetMe: mocks.me,
  apiListDocuments: mocks.list, apiUploadDocument: mocks.upload, apiReprocessDocument: mocks.reprocess,
  apiListSessions: mocks.sessions, apiCreateSession: mocks.create,
}));

import { AuthProvider, useAuth } from '../../context/AuthContext';
import { ApiError, SESSION_EXPIRED_EVENT, TOKEN_KEY, getToken, setToken, clearToken } from '../../lib/api';
import { useDocuments } from './useDocuments';
import { useWorkspaceChats } from './useWorkspaceChats';

const profile = { name: 'Alex', email: 'alex@example.test', avatarUrl: null };
const document = { id: 'doc-1', name: 'notes.txt', fileType: 'txt', fileSize: 12, chunkCount: 1, status: 'ready', createdAt: '' };
const AuthStatus = () => { const auth = useAuth(); return <p>{auth.isAuthenticated ? auth.user.name : 'Signed out'}</p>; };

beforeEach(() => { vi.clearAllMocks(); localStorage.clear(); mocks.list.mockResolvedValue([]); mocks.sessions.mockResolvedValue([]); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('Account recovery', () => {
  it('expires only the token used by the failed request, not a newer account session', async () => {
    const actual = await vi.importActual<typeof import('../../lib/api')>('../../lib/api');
    let resolve!: (response: Response) => void;
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>((done) => { resolve = done; })));
    const expired = vi.fn(); window.addEventListener(SESSION_EXPIRED_EVENT, expired);
    setToken('old-session');
    const request = actual.apiGetMe();
    setToken('new-session');
    resolve(new Response(JSON.stringify({ detail: 'Expired' }), { status: 401 }));
    await expect(request).rejects.toBeInstanceOf(ApiError);
    expect(getToken()).toBe('new-session');
    expect(expired).not.toHaveBeenCalled();
    window.removeEventListener(SESSION_EXPIRED_EVENT, expired);
  });

  it('clears the current rejected token and announces session expiry', async () => {
    const actual = await vi.importActual<typeof import('../../lib/api')>('../../lib/api');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 401 })));
    const expired = vi.fn(); window.addEventListener(SESSION_EXPIRED_EVENT, expired);
    setToken('expired-session');
    await expect(actual.apiGetMe()).rejects.toBeInstanceOf(ApiError);
    expect(getToken()).toBeNull();
    expect(expired).toHaveBeenCalledTimes(1);
    window.removeEventListener(SESSION_EXPIRED_EVENT, expired);
  });

  it('keeps a saved sign-in during a network outage and lets the user retry', async () => {
    setToken('saved-session');
    mocks.me.mockRejectedValueOnce(new TypeError('Failed to fetch')).mockResolvedValueOnce(profile);
    render(<AuthProvider><AuthStatus /></AuthProvider>);
    await screen.findByRole('button', { name: 'Try again' });
    expect(getToken()).toBe('saved-session');
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByText('Alex')).toBeTruthy();
    expect(mocks.me).toHaveBeenCalledTimes(2);
  });

  it('shows progress while validating, and removes a rejected token', async () => {
    setToken('expired-session');
    let reject!: (error: Error) => void;
    mocks.me.mockReturnValueOnce(new Promise((_, fail) => { reject = fail; }));
    render(<AuthProvider><AuthStatus /></AuthProvider>);
    expect(screen.getByRole('status').textContent).toContain('Opening');
    await act(async () => reject(new ApiError('Expired', 401)));
    expect(await screen.findByText('Signed out')).toBeTruthy();
    expect(getToken()).toBeNull();
  });

  it('returns an expired signed-in session to account access', async () => {
    setToken('saved-session'); mocks.me.mockResolvedValueOnce(profile);
    render(<AuthProvider><AuthStatus /></AuthProvider>);
    await screen.findByText('Alex');
    act(() => { clearToken(); window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT)); });
    expect(screen.getByText('Signed out')).toBeTruthy();
  });

  it('revalidates account changes from another browser tab instead of retaining the previous identity', async () => {
    setToken('alex-session'); mocks.me.mockResolvedValueOnce(profile).mockResolvedValueOnce({ ...profile, name: 'Sam', email: 'sam@example.test' });
    render(<AuthProvider><AuthStatus /></AuthProvider>);
    await screen.findByText('Alex');
    act(() => { setToken('sam-session'); window.dispatchEvent(new StorageEvent('storage', { key: TOKEN_KEY, newValue: 'sam-session' })); });
    expect(await screen.findByText('Sam')).toBeTruthy();
    expect(screen.queryByText('Alex')).toBeNull();
  });
});

describe('Source recovery', () => {
  it('does not let a late background refresh remove a newly uploaded source', async () => {
    let resolve!: (documents: unknown[]) => void;
    mocks.list.mockReturnValueOnce(new Promise((done) => { resolve = done; }));
    mocks.upload.mockResolvedValueOnce(document);
    const { result } = renderHook(() => useDocuments(profile.email));
    await act(async () => result.current.addFiles([new File(['notes'], 'notes.txt')]));
    expect(result.current.files).toHaveLength(1);
    await act(async () => resolve([]));
    expect(result.current.files).toHaveLength(1);
  });

  it('does not erase an upload failure when background source refresh succeeds', async () => {
    mocks.upload.mockRejectedValueOnce(new Error('Upload interrupted'));
    const { result } = renderHook(() => useDocuments(profile.email));
    await waitFor(() => expect(result.current.filesLoading).toBe(false));
    await act(async () => result.current.addFiles([new File(['notes'], 'notes.txt')]));
    await act(async () => result.current.refreshFiles());
    expect(result.current.uploadError).toBe('Upload interrupted');
    expect(result.current.listError).toBeNull();
  });

  it('distinguishes a failed list from an empty library and recovers it', async () => {
    mocks.list.mockRejectedValueOnce(new Error('Offline')).mockResolvedValueOnce([document]);
    const { result } = renderHook(() => useDocuments(profile.email));
    await waitFor(() => expect(result.current.listError).toBe('Offline'));
    await act(async () => result.current.refreshFiles());
    expect(result.current.files[0].name).toBe('notes.txt');
    expect(result.current.listError).toBeNull();
  });

  it('retries document processing without hiding a failure or losing the existing source', async () => {
    mocks.list.mockResolvedValueOnce([{ ...document, status: 'partial' }]);
    mocks.reprocess.mockRejectedValueOnce(new Error('Please retry later')).mockResolvedValueOnce(document);
    const { result } = renderHook(() => useDocuments(profile.email));
    await waitFor(() => expect(result.current.files).toHaveLength(1));
    await act(async () => result.current.reprocessFile(document.id));
    expect(result.current.files[0].status).toBe('partial');
    expect(result.current.uploadError).toBe('Please retry later');
    await act(async () => result.current.reprocessFile(document.id));
    expect(result.current.files[0].status).toBe('ready');
    expect(result.current.uploadError).toBeNull();
  });
});

describe('Conversation loading', () => {
  it('retains an explicit chat-list error and provides a successful retry', async () => {
    mocks.sessions.mockRejectedValueOnce(new Error('Chat list offline')).mockResolvedValueOnce([]);
    const { result } = renderHook(() => useWorkspaceChats('student', profile.email));
    await waitFor(() => expect(result.current.sessionsError).toBe('Chat list offline'));
    expect(result.current.chatError).toBeNull();
    await act(async () => result.current.refreshSessions());
    expect(result.current.sessionsError).toBeNull();
  });

  it('cannot send with Enter while the selected history is still loading', async () => {
    mocks.sessions.mockReturnValueOnce(new Promise(() => undefined));
    const { result } = renderHook(() => useWorkspaceChats('student', profile.email));
    await waitFor(() => expect(result.current.sessionsLoading).toBe(true));
    act(() => result.current.setChatInput('What are these notes about?'));
    await act(async () => result.current.sendMessage());
    expect(mocks.create).not.toHaveBeenCalled();
    expect(result.current.chatInput).toBe('What are these notes about?');
  });
});
