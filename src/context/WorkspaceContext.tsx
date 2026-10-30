import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { useAuth } from './AuthContext';
import { useDocuments } from '../features/workspace/useDocuments';
import { useWorkspaceChats } from '../features/workspace/useWorkspaceChats';
import type { WorkspaceMode } from '../types';

type WorkspaceContextType = ReturnType<typeof useDocuments> & ReturnType<typeof useWorkspaceChats> & {
  workspace: WorkspaceMode; setWorkspace: (mode: WorkspaceMode) => void;
  drawerOpen: boolean; toggleDrawer: () => void; closeDrawer: () => void;
};
const WorkspaceContext = createContext<WorkspaceContextType | undefined>(undefined);
export const WorkspaceProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, user } = useAuth();
  const [workspace, setMode] = useState<WorkspaceMode>('student');
  const [drawerOpen, setDrawerOpen] = useState(false);
  const documents = useDocuments(isAuthenticated ? user.email : '');
  const chats = useWorkspaceChats(workspace, isAuthenticated ? user.email : '');
  const cancelRef = useRef(chats.cancelMessage); cancelRef.current = chats.cancelMessage;
  const setWorkspace = useCallback((mode: WorkspaceMode) => { cancelRef.current(); setMode(mode); setDrawerOpen(false); }, []);
  useEffect(() => { if (!isAuthenticated) setMode('student'); }, [isAuthenticated]);
  return <WorkspaceContext.Provider value={{ ...documents, ...chats, workspace, setWorkspace, drawerOpen,
    toggleDrawer: () => setDrawerOpen((open) => !open), closeDrawer: () => setDrawerOpen(false) }}>{children}</WorkspaceContext.Provider>;
};
export const useWorkspace = () => {
  const value = useContext(WorkspaceContext);
  if (!value) throw new Error('useWorkspace must be used within WorkspaceProvider');
  return value;
};
