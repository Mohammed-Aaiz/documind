import React, { createContext, useContext, useState, useCallback } from 'react';
import { AppSettings } from '../types';

interface SettingsContextType {
  settings: AppSettings;
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

const SettingsContext = createContext<SettingsContextType | undefined>(undefined);

export const SettingsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [settings, setSettings] = useState<AppSettings>(defaults);
  const [saved, setSaved] = useState<AppSettings>(defaults);
  const [saveToast, setSaveToast] = useState(false);

  const updateProfile = useCallback((updates: Partial<AppSettings['profile']>) => {
    setSettings((prev) => ({ ...prev, profile: { ...prev.profile, ...updates } }));
  }, []);

  const updateSecurity = useCallback((updates: Partial<AppSettings['security']>) => {
    setSettings((prev) => ({ ...prev, security: { ...prev.security, ...updates } }));
  }, []);

  const updateAIProcessing = useCallback((updates: Partial<AppSettings['aiProcessing']>) => {
    setSettings((prev) => ({ ...prev, aiProcessing: { ...prev.aiProcessing, ...updates } }));
  }, []);

  const updateEnvironment = useCallback((updates: Partial<AppSettings['environment']>) => {
    setSettings((prev) => ({ ...prev, environment: { ...prev.environment, ...updates } }));
  }, []);

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
