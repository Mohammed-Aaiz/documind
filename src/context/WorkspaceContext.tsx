import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { DocumentFile, ChatMessage, ChatSession } from '../types';
import {
  apiUploadDocument,
  apiListDocuments,
  apiDeleteDocument,
  apiAskQuestion,
  apiListSessions,
  apiCreateSession,
  apiGetSessionMessages,
  apiAddSessionMessage,
  ApiDocument,
} from '../lib/api';

interface WorkspaceContextType {
  // Documents
  files: DocumentFile[];
  uploading: boolean;
  uploadError: string | null;
  addFiles: (rawFiles: File[]) => Promise<void>;
  removeFile: (id: string) => Promise<void>;
  refreshFiles: () => Promise<void>;

  // Conversation state
  activeSessionId: string | null;
  sessions: ChatSession[];
  messages: ChatMessage[];
  chatInput: string;
  setChatInput: (v: string) => void;
  sendMessage: () => Promise<void>;
  startNewConversation: () => Promise<void>;
  openConversation: (sessionId: string) => Promise<void>;
  backToHomepage: () => void;
  isConversationMode: boolean;

  // Drawer
  drawerOpen: boolean;
  toggleDrawer: () => void;
  closeDrawer: () => void;

  // Loading states
  sessionsLoading: boolean;
}

const WorkspaceContext = createContext<WorkspaceContextType | undefined>(undefined);

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function apiDocToFile(doc: ApiDocument): DocumentFile {
  return {
    id: doc.id,
    name: doc.name,
    size: formatSize(doc.fileSize),
    type: doc.fileType as DocumentFile['type'],
    status: doc.status as DocumentFile['status'],
    chunkCount: doc.chunkCount,
  };
}

export const WorkspaceProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // Documents
  const [files, setFiles] = useState<DocumentFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Conversation
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [sessionsLoading, setSessionsLoading] = useState(false);

  // Drawer
  const [drawerOpen, setDrawerOpen] = useState(false);

  const isConversationMode = activeSessionId !== null;

  // -----------------------------------------------------------------------
  // Load documents on mount
  // -----------------------------------------------------------------------
  const refreshFiles = useCallback(async () => {
    try {
      const docs = await apiListDocuments();
      setFiles(docs.map(apiDocToFile));
    } catch {
      // Silently fail — user may not be authenticated
    }
  }, []);

  useEffect(() => {
    refreshFiles();
  }, [refreshFiles]);

  // -----------------------------------------------------------------------
  // Load sessions on mount
  // -----------------------------------------------------------------------
  const refreshSessions = useCallback(async () => {
    setSessionsLoading(true);
    try {
      const apiSessions = await apiListSessions();
      setSessions(
        apiSessions.map((s) => ({
          id: s.id,
          createdAt: s.createdAt,
          preview: s.preview,
        })),
      );
    } catch {
      // Silently fail
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshSessions();
  }, [refreshSessions]);

  // -----------------------------------------------------------------------
  // Upload files to backend
  // -----------------------------------------------------------------------
  const addFiles = useCallback(async (rawFiles: File[]) => {
    setUploading(true);
    setUploadError(null);
    try {
      for (const file of rawFiles) {
        const ext = file.name.split('.').pop()?.toLowerCase();
        if (!['pdf', 'docx', 'txt'].includes(ext ?? '')) {
          setUploadError(`Unsupported file type: .${ext}`);
          continue;
        }
        // Add optimistic entry
        const tempId = `temp-${Date.now()}-${Math.random()}`;
        const optimistic: DocumentFile = {
          id: tempId,
          name: file.name,
          size: formatSize(file.size),
          type: ext as DocumentFile['type'],
          status: 'uploading',
          chunkCount: 0,
        };
        setFiles((prev) => [optimistic, ...prev]);

        try {
          const doc = await apiUploadDocument(file);
          setFiles((prev) => prev.map((f) => (f.id === tempId ? apiDocToFile(doc) : f)));
        } catch (err) {
          setFiles((prev) => prev.map((f) => (f.id === tempId ? { ...f, status: 'error' as const } : f)));
          setUploadError(err instanceof Error ? err.message : 'Upload failed');
        }
      }
    } finally {
      setUploading(false);
    }
  }, []);

  // -----------------------------------------------------------------------
  // Delete document
  // -----------------------------------------------------------------------
  const removeFile = useCallback(async (id: string) => {
    try {
      await apiDeleteDocument(id);
      setFiles((prev) => prev.filter((f) => f.id !== id));
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Delete failed');
    }
  }, []);

  // -----------------------------------------------------------------------
  // Start a new conversation
  // -----------------------------------------------------------------------
  const startNewConversation = useCallback(async () => {
    try {
      const session = await apiCreateSession();
      setActiveSessionId(session.id);
      setMessages([]);
      setDrawerOpen(false);
      // Refresh session list
      refreshSessions();
    } catch {
      // Could not create session
    }
  }, [refreshSessions]);

  // -----------------------------------------------------------------------
  // Open an existing conversation
  // -----------------------------------------------------------------------
  const openConversation = useCallback(async (sessionId: string) => {
    setActiveSessionId(sessionId);
    setDrawerOpen(false);
    try {
      const apiMessages = await apiGetSessionMessages(sessionId);
      setMessages(
        apiMessages.map((m) => ({
          id: m.id,
          sender: m.sender as 'user' | 'oracle',
          text: m.content,
          timestamp: m.createdAt,
        })),
      );
    } catch {
      setMessages([]);
    }
  }, []);

  // -----------------------------------------------------------------------
  // Go back to homepage
  // -----------------------------------------------------------------------
  const backToHomepage = useCallback(() => {
    setActiveSessionId(null);
    setMessages([]);
    setChatInput('');
    refreshSessions();
  }, [refreshSessions]);

  // -----------------------------------------------------------------------
  // Send a message (with persistence)
  // -----------------------------------------------------------------------
  const sendMessage = useCallback(async () => {
    const text = chatInput.trim();
    if (!text) return;

    let sessionId = activeSessionId;

    // If no active session, create one first
    if (!sessionId) {
      try {
        const session = await apiCreateSession();
        sessionId = session.id;
        setActiveSessionId(sessionId);
        refreshSessions();
      } catch {
        return; // Cannot create session
      }
    }

    const finalSessionId = sessionId;
    setChatInput('');

    // Optimistic user message
    const userMsg: ChatMessage = {
      id: `temp-user-${Date.now()}`,
      sender: 'user',
      text,
      timestamp: new Date().toLocaleTimeString(),
    };
    setMessages((prev) => [...prev, userMsg]);

    // Persist user message
    apiAddSessionMessage(finalSessionId, 'user', text).catch(() => {});

    try {
      const res = await apiAskQuestion(text);
      let answerText = res.answer;
      if (res.insufficientContext || !answerText) {
        answerText = 'I could not find relevant information in your documents to answer this question.';
      }

      const oracleMsg: ChatMessage = {
        id: `temp-oracle-${Date.now() + 1}`,
        sender: 'oracle',
        text: answerText,
        timestamp: new Date().toLocaleTimeString(),
        sources: res.sources,
        insufficientContext: res.insufficientContext,
      };
      setMessages((prev) => [...prev, oracleMsg]);

      // Persist oracle message
      apiAddSessionMessage(finalSessionId, 'oracle', answerText).catch(() => {});
    } catch {
      const errorMsg: ChatMessage = {
        id: `temp-oracle-${Date.now() + 1}`,
        sender: 'oracle',
        text: 'Failed to process your question. Please try again.',
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
      apiAddSessionMessage(finalSessionId, 'oracle', 'Failed to process your question. Please try again.').catch(() => {});
    }
  }, [chatInput, activeSessionId, refreshSessions]);

  // -----------------------------------------------------------------------
  // Drawer controls
  // -----------------------------------------------------------------------
  const toggleDrawer = useCallback(() => setDrawerOpen((prev) => !prev), []);
  const closeDrawer = useCallback(() => setDrawerOpen(false), []);

  return (
    <WorkspaceContext.Provider
      value={{
        files,
        uploading,
        uploadError,
        addFiles,
        removeFile,
        refreshFiles,
        activeSessionId,
        sessions,
        messages,
        chatInput,
        setChatInput,
        sendMessage,
        startNewConversation,
        openConversation,
        backToHomepage,
        isConversationMode,
        drawerOpen,
        toggleDrawer,
        closeDrawer,
        sessionsLoading,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
};

export const useWorkspace = () => {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error('useWorkspace must be used within WorkspaceProvider');
  return ctx;
};
