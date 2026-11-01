import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { UserProfile } from '../types';
import {
  apiLogin,
  apiRegister,
  apiLogout,
  apiGetMe,
  getToken,
  setToken,
  clearToken,
  ApiError,
  SESSION_EXPIRED_EVENT,
  TOKEN_KEY,
} from '../lib/api';

interface AuthContextType {
  isAuthenticated: boolean;
  user: UserProfile;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  updateUser: (updates: Partial<UserProfile>) => void;
}

const defaultUser: UserProfile = {
  name: 'User',
  email: '',
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // Start unauthenticated; we validate any stored token on mount.
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [user, setUser] = useState<UserProfile>(defaultUser);
  const [initialising, setInitialising] = useState<boolean>(true);
  const [restoreError, setRestoreError] = useState(false);
  const [restoreAttempt, setRestoreAttempt] = useState(0);

  // -----------------------------------------------------------------------
  // On mount: validate any persisted token against the backend /me endpoint.
  // -----------------------------------------------------------------------
  useEffect(() => {
    const token = getToken();
    if (!token) {
      setInitialising(false);
      return;
    }

    let active = true;
    const abort = new AbortController();
    const timeout = window.setTimeout(() => abort.abort(), 10000);
    apiGetMe(abort.signal)
      .then((profile) => {
        if (!active || getToken() !== token) return;
        setUser({ name: profile.name, email: profile.email, avatarUrl: profile.avatarUrl ?? undefined });
        setIsAuthenticated(true);
      })
      .catch((error) => {
        if (!active || (getToken() !== token && getToken() !== null)) return;
        if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
          clearToken();
          setUser(defaultUser);
          setIsAuthenticated(false);
        } else {
          // A temporary outage is not evidence that the user's token expired.
          setRestoreError(true);
        }
      })
      .finally(() => {
        window.clearTimeout(timeout);
        if (active) setInitialising(false);
      });
    return () => { active = false; window.clearTimeout(timeout); abort.abort(); };
  }, [restoreAttempt]);

  useEffect(() => {
    const expired = () => {
      setUser(defaultUser); setIsAuthenticated(false); setInitialising(false); setRestoreError(false);
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, expired);
    const changed = (event: StorageEvent) => {
      if (event.key !== null && event.key !== TOKEN_KEY) return;
      setUser(defaultUser); setIsAuthenticated(false); setRestoreError(false); setInitialising(true);
      setRestoreAttempt((attempt) => attempt + 1);
    };
    window.addEventListener('storage', changed);
    return () => { window.removeEventListener(SESSION_EXPIRED_EVENT, expired); window.removeEventListener('storage', changed); };
  }, []);

  // -----------------------------------------------------------------------
  // login — call POST /api/auth/login
  // -----------------------------------------------------------------------
  const login = useCallback(async (email: string, password: string): Promise<void> => {
    const res = await apiLogin(email, password);
    setToken(res.access_token);
    setUser({
      name: res.user.name,
      email: res.user.email,
      avatarUrl: res.user.avatarUrl ?? undefined,
    });
    setIsAuthenticated(true);
  }, []);

  const register = useCallback(async (name: string, email: string, password: string): Promise<void> => {
    const res = await apiRegister(name, email, password);
    setToken(res.access_token);
    setUser({ name: res.user.name, email: res.user.email, avatarUrl: res.user.avatarUrl ?? undefined });
    setIsAuthenticated(true);
  }, []);

  // -----------------------------------------------------------------------
  // logout — call POST /api/auth/logout then clear local state
  // -----------------------------------------------------------------------
  const logout = useCallback(() => {
    // Fire-and-forget: best-effort server-side acknowledgement.
    apiLogout().catch(() => {
      /* Network error — still clear client state. */
    });
    clearToken();
    setUser(defaultUser);
    setIsAuthenticated(false);
  }, []);

  // -----------------------------------------------------------------------
  // updateUser — local-only profile tweaks (e.g. settings page edits)
  // -----------------------------------------------------------------------
  const updateUser = useCallback((updates: Partial<UserProfile>) => {
    setUser((prev) => ({ ...prev, ...updates }));
  }, []);

  if (initialising || restoreError) {
    return <main className="dm-auth-restore"><section aria-live="polite">
      <h1>DocuMind</h1>
      {restoreError ? <><p role="alert">We couldn't reconnect to your workspace. Your sign-in is saved.</p>
        <button className="dm-button dm-primary" onClick={() => { setRestoreError(false); setInitialising(true); setRestoreAttempt((attempt) => attempt + 1); }}>Try again</button>
        <button className="dm-button" onClick={() => { clearToken(); setRestoreError(false); setUser(defaultUser); setIsAuthenticated(false); }}>Use another account</button>
      </> : <p role="status">Opening your workspace…</p>}
    </section></main>;
  }

  return (
    <AuthContext.Provider value={{ isAuthenticated, user, login, register, logout, updateUser }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
};
