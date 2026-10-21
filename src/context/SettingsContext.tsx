import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { apiGetSettings, apiPatchSettings, ApiSettings } from '../lib/api';
import { useAuth } from './AuthContext';

/**
 * Settings context.
 *
 * Holds exactly the settings the backend actually persists — the five fields
 * of GET/PATCH `/api/settings`. Nothing else is represented as state: a value
 * this context does not carry cannot be rendered as though a server had saved
 * it.
 *
 * Two consequences are deliberate:
 *
 * 1. The user's identity is NOT part of settings. The Settings page reads the
 *    authenticated user from `useAuth()` (populated from `GET /api/auth/me`),
 *    so it can never show a placeholder identity.
 * 2. Security features the product does not implement (two-factor auth,
 *    end-to-end encryption) are absent here rather than defaulted to `true`.
 *    The page renders those surfaces as unavailable instead.
 *
 * Edits are local until applied. `applyConfiguration()` performs the real
 * PATCH and reports what the server actually did; a failed save is surfaced
 * as a failure, never as a success.
 */

/** The server-persisted settings, grouped as the Settings page presents them. */
export interface PersistedSettings {
  aiProcessing: {
    /** 1–5, persisted as `processing_depth`. */
    depth: number;
    contextWindow: 'session' | '24h' | 'persistent';
  };
  environment: {
    theme: 'dark-cyber' | 'light';
    /** 0–100, persisted as `glass_intensity`. */
    glassIntensity: number;
    density: 'standard' | 'high';
  };
}

export type SettingsLoadState = 'loading' | 'ready' | 'unavailable';
export type SettingsSaveState = 'idle' | 'saving' | 'saved' | 'error';

interface SettingsContextType {
  settings: PersistedSettings;
  loadState: SettingsLoadState;
  loadError: string | null;
  saveState: SettingsSaveState;
  saveError: string | null;
  updateAIProcessing: (updates: Partial<PersistedSettings['aiProcessing']>) => void;
  updateEnvironment: (updates: Partial<PersistedSettings['environment']>) => void;
  applyConfiguration: () => Promise<void>;
  discardChanges: () => void;
}

/**
 * Mirrors the column defaults of `user_settings` (`backend/user/models.py`):
 * depth 3, context window `persistent`, theme `dark-cyber`, density `high`,
 * glass intensity 70. These are what the server itself reports for a user who
 * has never saved anything, so showing them before the first load is honest —
 * and the page states when the load has not succeeded.
 */
const defaults: PersistedSettings = {
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

/** Map the API settings shape to the app settings shape. */
function apiToSettings(api: ApiSettings): PersistedSettings {
  return {
    aiProcessing: {
      depth: api.processingDepth,
      contextWindow: api.contextWindow,
    },
    environment: {
      theme: api.theme,
      density: api.density,
      glassIntensity: api.glassIntensity,
    },
  };
}

/** Map the app settings shape back to the PATCH body the API accepts. */
function settingsToApiPatch(settings: PersistedSettings): Partial<ApiSettings> {
  return {
    processingDepth: settings.aiProcessing.depth,
    contextWindow: settings.aiProcessing.contextWindow,
    theme: settings.environment.theme,
    density: settings.environment.density,
    glassIntensity: settings.environment.glassIntensity,
  };
}

/**
 * Fixed, non-technical messages. Backend `detail` strings, status codes and
 * exception text are deliberately not surfaced here.
 */
function describeFailure(err: unknown, action: 'load' | 'save'): string {
  const status =
    typeof (err as { status?: unknown } | null)?.status === 'number'
      ? (err as { status: number }).status
      : null;
  const expired = status === 401;

  if (action === 'load') {
    return expired
      ? 'Your session has expired. Sign in again to load your saved settings.'
      : 'Could not load your saved settings from the server.';
  }
  return expired
    ? 'Your session has expired. Sign in again to save your settings.'
    : 'Could not save your settings. Your changes are not persisted on the server.';
}

const SettingsContext = createContext<SettingsContextType | undefined>(undefined);

export const SettingsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuth();

  const [settings, setSettings] = useState<PersistedSettings>(defaults);
  /** Last values the server confirmed; `discardChanges` returns to these. */
  const [saved, setSaved] = useState<PersistedSettings>(defaults);
  const [loadState, setLoadState] = useState<SettingsLoadState>('loading');
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<SettingsSaveState>('idle');
  const [saveError, setSaveError] = useState<string | null>(null);

  // -------------------------------------------------------------------------
  // Load the user's persisted settings once the session is authenticated.
  // -------------------------------------------------------------------------
  useEffect(() => {
    let cancelled = false;

    if (!isAuthenticated) {
      setLoadState('unavailable');
      setLoadError('Not signed in.');
      return;
    }

    async function loadSettings() {
      try {
        const apiSettings = await apiGetSettings();
        if (cancelled) return;
        const loaded = apiToSettings(apiSettings);
        setSettings(loaded);
        setSaved(loaded);
        setLoadState('ready');
        setLoadError(null);
      } catch (err) {
        if (cancelled) return;
        setLoadState('unavailable');
        setLoadError(describeFailure(err, 'load'));
      }
    }

    loadSettings();
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated]);

  /** Any edit invalidates a previous "saved" claim. */
  const markEdited = useCallback(() => {
    setSaveState('idle');
    setSaveError(null);
  }, []);

  const updateAIProcessing = useCallback(
    (updates: Partial<PersistedSettings['aiProcessing']>) => {
      setSettings((prev) => ({ ...prev, aiProcessing: { ...prev.aiProcessing, ...updates } }));
      markEdited();
    },
    [markEdited],
  );

  const updateEnvironment = useCallback(
    (updates: Partial<PersistedSettings['environment']>) => {
      setSettings((prev) => ({ ...prev, environment: { ...prev.environment, ...updates } }));
      markEdited();
    },
    [markEdited],
  );

  /**
   * Persist the current values with a real PATCH and report the outcome. The
   * server's response — not the local draft — becomes the saved state.
   */
  const applyConfiguration = useCallback(async () => {
    setSaveState('saving');
    setSaveError(null);
    try {
      const persisted = await apiPatchSettings(settingsToApiPatch(settings));
      const confirmed = apiToSettings(persisted);
      setSettings(confirmed);
      setSaved(confirmed);
      setSaveState('saved');
    } catch (err) {
      setSaveState('error');
      setSaveError(describeFailure(err, 'save'));
    }
  }, [settings]);

  const discardChanges = useCallback(() => {
    setSettings(saved);
    setSaveState('idle');
    setSaveError(null);
  }, [saved]);

  return (
    <SettingsContext.Provider
      value={{
        settings,
        loadState,
        loadError,
        saveState,
        saveError,
        updateAIProcessing,
        updateEnvironment,
        applyConfiguration,
        discardChanges,
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
