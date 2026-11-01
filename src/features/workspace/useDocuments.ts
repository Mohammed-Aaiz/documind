import { useCallback, useEffect, useRef, useState } from 'react';
import { apiDeleteDocument, apiListDocuments, apiUploadDocument, apiReprocessDocument, ApiDocument } from '../../lib/api';
import type { DocumentFile, DocumentStatus } from '../../types';

const statuses: DocumentStatus[] = ['uploading', 'processing', 'ready', 'partial', 'error'];
function documentFile(doc: ApiDocument): DocumentFile {
  return { id: doc.id, name: doc.name, type: doc.fileType as DocumentFile['type'], chunkCount: doc.chunkCount,
    size: doc.fileSize < 1048576 ? `${Math.ceil(doc.fileSize / 1024)} KB` : `${(doc.fileSize / 1048576).toFixed(1)} MB`,
    status: statuses.includes(doc.status as DocumentStatus) ? doc.status as DocumentStatus : 'unknown' };
}

export function useDocuments(identity: string) {
  const [files, setFiles] = useState<DocumentFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [filesLoading, setFilesLoading] = useState(false);
  const [reprocessing, setReprocessing] = useState<string | null>(null);
  const identityRef = useRef(identity); identityRef.current = identity;
  const mutation = useRef(0);
  const refreshRequest = useRef(0);
  const refreshFiles = useCallback(async () => {
    if (!identity) return;
    const version = mutation.current;
    const request = ++refreshRequest.current;
    setFilesLoading(true);
    try { const documents = await apiListDocuments(); if (identityRef.current === identity && version === mutation.current && request === refreshRequest.current) { setFiles(documents.map(documentFile)); setListError(null); } }
    catch (error) { if (identityRef.current === identity && request === refreshRequest.current) setListError(error instanceof Error ? error.message : 'Could not load your documents.'); }
    finally { if (identityRef.current === identity && request === refreshRequest.current) setFilesLoading(false); }
  }, [identity]);
  useEffect(() => { mutation.current++; setFiles([]); setUploading(false); setFilesLoading(false); setUploadError(null); setListError(null); setReprocessing(null); if (identity) void refreshFiles(); }, [identity, refreshFiles]);
  useEffect(() => {
    if (!files.some((file) => file.status === 'processing')) return;
    const timer = window.setInterval(() => void refreshFiles(), 4000);
    return () => window.clearInterval(timer);
  }, [files, refreshFiles]);
  const addFiles = useCallback(async (raw: File[]) => {
    if (!identity) return;
    mutation.current++; setUploading(true); setUploadError(null);
    for (const file of raw) {
      if (identityRef.current !== identity) return;
      if (!/\.(pdf|docx|txt)$/i.test(file.name)) { setUploadError('Choose a PDF, DOCX, or TXT file.'); continue; }
      try { const uploaded = documentFile(await apiUploadDocument(file)); if (identityRef.current === identity) { mutation.current++; setFiles((items) => [uploaded, ...items.filter((item) => item.id !== uploaded.id)]); } }
      catch (error) { if (identityRef.current === identity) setUploadError(error instanceof Error ? error.message : 'Upload failed.'); }
    }
    if (identityRef.current === identity) setUploading(false);
  }, [identity]);
  const removeFile = useCallback(async (id: string) => {
    try { await apiDeleteDocument(id); if (identityRef.current === identity) { mutation.current++; setFiles((items) => items.filter((item) => item.id !== id)); } }
    catch (error) { if (identityRef.current === identity) setUploadError(error instanceof Error ? error.message : 'Could not delete this document.'); }
  }, [identity]);
  const reprocessFile = useCallback(async (id: string) => {
    if (reprocessing) return;
    mutation.current++; setReprocessing(id); setUploadError(null);
    try {
      const document = documentFile(await apiReprocessDocument(id));
      if (identityRef.current === identity) { mutation.current++; setFiles((items) => items.map((item) => item.id === id ? document : item)); }
    } catch (error) { if (identityRef.current === identity) setUploadError(error instanceof Error ? error.message : 'Could not retry processing.'); }
    finally { if (identityRef.current === identity) setReprocessing(null); }
  }, [identity, reprocessing]);
  return { files, uploading, uploadError, listError, filesLoading, reprocessing, refreshFiles, addFiles, removeFile, reprocessFile };
}
