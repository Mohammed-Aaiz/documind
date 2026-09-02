import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { UserProfile } from '../types';
import {
  apiLogin,
  apiLogout,
  apiGetMe,
  getToken,
  setToken,
  clearToken,
} from '../lib/api';

interface AuthContextType {
  isAuthenticated: boolean;
  user: UserProfile;
  login: (email: string, password: string) => Promise<void>;
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

  // -----------------------------------------------------------------------
  // On mount: validate any persisted token against the backend /me endpoint.
  // -----------------------------------------------------------------------
  useEffect(() => {
    const token = getToken();
    if (!token) {
      setInitialising(false);
      return;
    }

    apiGetMe()
      .then((profile) => {
        setUser({ name: profile.name, email: profile.email, avatarUrl: profile.avatarUrl ?? undefined });
        setIsAuthenticated(true);
      })
      .catch(() => {
        // Token is invalid or expired — clear everything.
        clearToken();
        setUser(defaultUser);
        setIsAuthenticated(false);
      })
      .finally(() => {
        setInitialising(false);
      });
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

  // Show nothing while we validate the stored token on first render.
  if (initialising) {
    return null;
  }

  return (
    <AuthContext.Provider value={{ isAuthenticated, user, login, logout, updateUser }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
};
