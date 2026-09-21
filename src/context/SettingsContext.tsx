import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { AppSettings } from '../types';
import { apiGetSettings, apiPatchSettings, ApiSettings } from '../lib/api';

interface SettingsContextType {
  settings: AppSettings;
  loading: boolean;
  updateProfile: (updates: Partial<AppSettings['profile']>) => void;
  updateSecurity: (updates: Partial<AppSettings['security']>) => void;
  updateAIProcessing: (updates: Partial<AppSettings['aiProcessing']>) => void;
  updateEnvironment: (updates: Partial<AppSettings['environment']>) => void;
  resetSettings: () => void;
  triggerSaveToast: () => void;
  saveToast: boolean;
}

const defaults: AppSettings = {
  profile: {
    name: 'User',
    email: 'user@documind.io',
    avatarUrl: '',
    clearance: 'Level 3 — Analyst',
  },
  security: {
    twoFactor: true,
    e2eEncryption: true,
  },
  aiProcessing: {
    depth: 3,
    contextWindow: 'persistent',
  },
  environment: {
    theme: 'dark-cyber',
    density: 'high',
    glassIntensity: 70,
  },
};

/** Map API settings shape to AppSettings shape. */
function apiToAppSettings(api: ApiSettings, profile: AppSettings['profile']): AppSettings {
  return {
    ...defaults,
    profile,
    aiProcessing: {
      depth: api.processingDepth,
      contextWindow: api.contextWindow,
    },
    environment: {
      ...defaults.environment,
      theme: api.theme,
      density: api.density,
      glassIntensity: api.glassIntensity,
    },
  };
}

/** Map AppSettings shape to API patch shape. */
function appToApiPatch(settings: AppSettings): Partial<ApiSettings> {
  return {
    processingDepth: settings.aiProcessing.depth,
    contextWindow: settings.aiProcessing.contextWindow,
    theme: settings.environment.theme,
    density: settings.environment.density,
    glassIntensity: settings.environment.glassIntensity,
  };
}

const SettingsContext = createContext<SettingsContextType | undefined>(undefined);

export const SettingsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [settings, setSettings] = useState<AppSettings>(defaults);
  const [saved, setSaved] = useState<AppSettings>(defaults);
  const [saveToast, setSaveToast] = useState(false);
  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState<AppSettings['profile']>(defaults.profile);

  // -----------------------------------------------------------------------
  // Load settings from backend on mount
  // -----------------------------------------------------------------------
  useEffect(() => {
    let cancelled = false;

    async function loadSettings() {
      try {
        const apiSettings = await apiGetSettings();
        if (!cancelled) {
          const loaded = apiToAppSettings(apiSettings, profile);
          setSettings(loaded);
          setSaved(loaded);
        }
      } catch {
        // Use defaults if API unavailable (user not authenticated, etc.)
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadSettings();
    return () => { cancelled = true; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // -----------------------------------------------------------------------
  // Persist to backend whenever server-persisted fields change
  // -----------------------------------------------------------------------
  const persistToServer = useCallback(async (newSettings: AppSettings) => {
    try {
      await apiPatchSettings(appToApiPatch(newSettings));
    } catch {
      // Server persistence failed — local state already updated,
      // next load will re-sync from server.
    }
  }, []);

  // -----------------------------------------------------------------------
  // Update handlers — local state + server persistence
  // -----------------------------------------------------------------------
  const updateProfile = useCallback((updates: Partial<AppSettings['profile']>) => {
    setProfile((prev) => ({ ...prev, ...updates }));
    setSettings((prev) => ({ ...prev, profile: { ...prev.profile, ...updates } }));
    // Profile updates are not server-persisted (auth table handles profile)
  }, []);

  const updateSecurity = useCallback((updates: Partial<AppSettings['security']>) => {
    setSettings((prev) => ({ ...prev, security: { ...prev.security, ...updates } }));
    // Security toggles are local UI only in this phase
  }, []);

  const updateAIProcessing = useCallback((updates: Partial<AppSettings['aiProcessing']>) => {
    setSettings((prev) => {
      const next = { ...prev, aiProcessing: { ...prev.aiProcessing, ...updates } };
      persistToServer(next);
      return next;
    });
  }, [persistToServer]);

  const updateEnvironment = useCallback((updates: Partial<AppSettings['environment']>) => {
    setSettings((prev) => {
      const next = { ...prev, environment: { ...prev.environment, ...updates } };
      persistToServer(next);
      return next;
    });
  }, [persistToServer]);

  const resetSettings = useCallback(() => {
    setSettings(saved);
  }, [saved]);

  const triggerSaveToast = useCallback(() => {
    setSaved(settings);
    setSaveToast(true);
    setTimeout(() => setSaveToast(false), 3000);
  }, [settings]);

  return (
    <SettingsContext.Provider
      value={{
        settings,
        loading,
        updateProfile,
        updateSecurity,
        updateAIProcessing,
        updateEnvironment,
        resetSettings,
        triggerSaveToast,
        saveToast,
      }}
    >
      {children}
    </SettingsContext.Provider>
  );
};

export const useSettings = () => {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error('useSettings must be used within SettingsProvider');
  return ctx;
};
