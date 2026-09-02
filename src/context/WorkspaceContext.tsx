import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { DocumentFile, ChatMessage } from '../types';
import {
  apiUploadDocument,
  apiListDocuments,
  apiDeleteDocument,
  apiAskQuestion,
  ApiDocument,
} from '../lib/api';

interface WorkspaceContextType {
  files: DocumentFile[];
  uploading: boolean;
  uploadError: string | null;
  addFiles: (rawFiles: File[]) => Promise<void>;
  removeFile: (id: string) => Promise<void>;
  refreshFiles: () => Promise<void>;
  messages: ChatMessage[];
  chatInput: string;
  setChatInput: (v: string) => void;
  sendMessage: () => void;
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
  const [files, setFiles] = useState<DocumentFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState('');

  // Load documents on mount
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

  // Upload files to backend
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
          // Replace optimistic entry with real one
          setFiles((prev) => prev.map((f) => (f.id === tempId ? apiDocToFile(doc) : f)));
        } catch (err) {
          // Mark as error
          setFiles((prev) => prev.map((f) => (f.id === tempId ? { ...f, status: 'error' as const } : f)));
          setUploadError(err instanceof Error ? err.message : 'Upload failed');
        }
      }
    } finally {
      setUploading(false);
    }
  }, []);

  // Delete document from backend
  const removeFile = useCallback(async (id: string) => {
    try {
      await apiDeleteDocument(id);
      setFiles((prev) => prev.filter((f) => f.id !== id));
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Delete failed');
    }
  }, []);

  const sendMessage = useCallback(async () => {
    const text = chatInput.trim();
    if (!text) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      sender: 'user',
      text,
      timestamp: new Date().toLocaleTimeString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setChatInput('');

    try {
      const res = await apiAskQuestion(text);
      let answerText = res.answer;
      if (res.insufficientContext || !answerText) {
        answerText = 'I could not find relevant information in your documents to answer this question.';
      }
      const oracleMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'oracle',
        text: answerText,
        timestamp: new Date().toLocaleTimeString(),
        sources: res.sources,
        insufficientContext: res.insufficientContext,
      };
      setMessages((prev) => [...prev, oracleMsg]);
    } catch {
      const errorMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'oracle',
        text: 'Failed to process your question. Please try again.',
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    }
  }, [chatInput]);

  return (
    <WorkspaceContext.Provider value={{ files, uploading, uploadError, addFiles, removeFile, refreshFiles, messages, chatInput, setChatInput, sendMessage }}>
      {children}
    </WorkspaceContext.Provider>
  );
};

export const useWorkspace = () => {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error('useWorkspace must be used within WorkspaceProvider');
  return ctx;
};
