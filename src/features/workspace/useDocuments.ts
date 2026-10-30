import { useCallback, useEffect, useRef, useState } from 'react';
import { apiDeleteDocument, apiListDocuments, apiUploadDocument, ApiDocument } from '../../lib/api';
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
  const identityRef = useRef(identity); identityRef.current = identity;
  const refreshFiles = useCallback(async () => {
    if (!identity) return;
    try { const documents = await apiListDocuments(); if (identityRef.current === identity) { setFiles(documents.map(documentFile)); setUploadError(null); } }
    catch (error) { if (identityRef.current === identity) setUploadError(error instanceof Error ? error.message : 'Could not load your documents.'); }
  }, [identity]);
  useEffect(() => { setFiles([]); setUploading(false); setUploadError(null); if (identity) void refreshFiles(); }, [identity, refreshFiles]);
  useEffect(() => {
    if (!files.some((file) => file.status === 'processing')) return;
    const timer = window.setInterval(() => void refreshFiles(), 4000);
    return () => window.clearInterval(timer);
  }, [files, refreshFiles]);
  const addFiles = useCallback(async (raw: File[]) => {
    if (!identity) return;
    setUploading(true); setUploadError(null);
    for (const file of raw) {
      if (identityRef.current !== identity) return;
      if (!/\.(pdf|docx|txt)$/i.test(file.name)) { setUploadError('Choose a PDF, DOCX, or TXT file.'); continue; }
      try { const uploaded = documentFile(await apiUploadDocument(file)); if (identityRef.current === identity) setFiles((items) => [uploaded, ...items.filter((item) => item.id !== uploaded.id)]); }
      catch (error) { if (identityRef.current === identity) setUploadError(error instanceof Error ? error.message : 'Upload failed.'); }
    }
    if (identityRef.current === identity) setUploading(false);
  }, [identity]);
  const removeFile = useCallback(async (id: string) => {
    try { await apiDeleteDocument(id); if (identityRef.current === identity) setFiles((items) => items.filter((item) => item.id !== id)); }
    catch (error) { if (identityRef.current === identity) setUploadError(error instanceof Error ? error.message : 'Could not delete this document.'); }
  }, [identity]);
  return { files, uploading, uploadError, refreshFiles, addFiles, removeFile };
}
