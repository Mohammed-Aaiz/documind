import { useRef, useState } from 'react';
import { useWorkspace } from '../../context/WorkspaceContext';
import { DocumentInsightsPanel } from '../../components/common/DocumentInsightsPanel';
import { apiRebuildDocumentKnowledgeGraph, type ApiKnowledgeGraphStatus } from '../../lib/api';
import { Icon } from './WorkspaceSidebar';

type KnowledgeGraphState =
  | { status: 'pending' }
  | { status: 'ready' | 'partial' | 'unavailable'; relationCount: number }
  | { status: 'error'; message: string };

export function SourceLibrary() {
  const { files, uploading, uploadError, listError, filesLoading, reprocessing, addFiles, removeFile, refreshFiles, reprocessFile } = useWorkspace();
  const input = useRef<HTMLInputElement>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [removeId, setRemoveId] = useState<string | null>(null);
  const [knowledgeGraphs, setKnowledgeGraphs] = useState<Record<string, KnowledgeGraphState>>({});

  const rebuildKnowledgeGraph = async (documentId: string) => {
    setKnowledgeGraphs((previous) => ({ ...previous, [documentId]: { status: 'pending' } }));
    try {
      const result = await apiRebuildDocumentKnowledgeGraph(documentId);
      const status: ApiKnowledgeGraphStatus = result.status;
      if (!['ready', 'partial', 'unavailable', 'pending'].includes(status)) {
        throw new Error('The server returned an unknown graph status.');
      }
      setKnowledgeGraphs((previous) => ({
        ...previous,
        [documentId]: status === 'pending'
          ? { status: 'pending' }
          : { status, relationCount: result.relationCount },
      }));
    } catch (error) {
      setKnowledgeGraphs((previous) => ({
        ...previous,
        [documentId]: {
          status: 'error',
          message: error instanceof Error ? error.message : 'Could not build the entity graph.',
        },
      }));
    }
  };

  const graphStatusText = (state: KnowledgeGraphState) => {
    if (state.status === 'pending') return 'Building entity graph…';
    if (state.status === 'error') return state.message;
    const label = state.status === 'ready' ? 'Ready' : state.status === 'partial' ? 'Partial' : 'Unavailable';
    return `${label} · ${state.relationCount} ${state.relationCount === 1 ? 'relation' : 'relations'}`;
  };
  return <aside className="dm-library">
    <div className="dm-panel-heading"><div><span className="dm-eyebrow">YOUR KNOWLEDGE</span><h2>Source library <span>{files.length}</span></h2></div><button className="dm-icon-button" disabled={filesLoading} aria-label="Refresh sources" onClick={() => void refreshFiles()}><Icon name="refresh" /></button></div>
    <p className="dm-muted dm-small">Shared across your workspaces. Answers draw from your searchable documents.</p>
    <button className="dm-upload" disabled={uploading} onClick={() => input.current?.click()} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); if (!uploading) void addFiles(Array.from(event.dataTransfer.files)); }}><span className="dm-upload-icon"><Icon name={uploading ? 'hourglass_top' : 'upload_file'} /></span><strong>{uploading ? 'Processing documents…' : 'Add your sources'}</strong><span>Drop files here or browse</span><small>PDF, DOCX, TXT</small></button>
    <input ref={input} hidden type="file" multiple accept=".pdf,.docx,.txt" aria-label="Upload documents" onChange={(event) => { if (event.target.files) void addFiles(Array.from(event.target.files)); event.target.value = ''; }} />
    {uploadError && <p className="dm-alert" role="alert">{uploadError}</p>}
    {listError && <div className="dm-alert" role="alert"><span>{listError}</span><button className="dm-text-button" onClick={() => void refreshFiles()}>Try again</button></div>}
    {filesLoading && files.length === 0 && <p role="status" className="dm-muted">Loading your sources…</p>}
    <div className="dm-document-list">{files.map((file) => {
      const graph = knowledgeGraphs[file.id];
      const graphPending = graph?.status === 'pending';
      const canBuildGraph = file.chunkCount > 0 && (file.status === 'ready' || file.status === 'partial');
      return <article className="dm-document" key={file.id}>
        <span className={`dm-file-icon ${file.type}`}><Icon name={file.type === 'pdf' ? 'picture_as_pdf' : 'description'} /></span>
        <div className="dm-document-main">
          <button className="dm-document-title" onClick={() => setSelected(file.id)}><strong>{file.name}</strong><span>{file.size} · <span className={`dm-file-status ${file.status}`}>{file.status === 'partial' ? 'Partially searchable' : file.status}</span></span></button>
          <button
            className="dm-graph-build-button"
            type="button"
            disabled={!canBuildGraph || graphPending}
            aria-busy={graphPending}
            onClick={() => void rebuildKnowledgeGraph(file.id)}
          >
            <Icon name={graphPending ? 'hourglass_top' : 'hub'} />
            {graphPending ? 'Building…' : graph ? 'Rebuild entity graph' : 'Build entity graph'}
          </button>
          {graph && <span className={`dm-graph-status is-${graph.status}`} role={graph.status === 'error' ? 'alert' : 'status'} aria-live="polite">{graphStatusText(graph)}</span>}
          {(file.status === 'error' || file.status === 'partial') && <button className="dm-graph-build-button" disabled={!!reprocessing} aria-busy={reprocessing === file.id} onClick={() => void reprocessFile(file.id)}><Icon name="refresh" />{reprocessing === file.id ? 'Retrying processing…' : 'Retry document processing'}</button>}
        </div>
        <button className="dm-icon-button" aria-label={`Delete ${file.name}`} onClick={() => setRemoveId(file.id)}><Icon name="more_horiz" /></button>
      </article>;
    })}</div>
    {files.length === 0 && !filesLoading && !listError && <div className="dm-library-empty"><Icon name="library_books" /><p>A good answer starts<br />with a good source.</p><small>Add lecture notes, papers,<br />or a chapter to get started.</small></div>}
    <div className="dm-library-tip"><Icon name="info" /><p>Citations point back to the passages used. Always review the source for important claims.</p></div>
    {selected && <DocumentInsightsPanel documentId={selected} onClose={() => setSelected(null)} />}
    {removeId && <div className="dm-modal-backdrop"><div className="dm-modal" role="alertdialog" aria-modal="true" aria-labelledby="delete-source-heading"><h2 id="delete-source-heading">Remove this source?</h2><p>This removes it from the shared library in both workspaces.</p><div><button className="dm-button" onClick={() => setRemoveId(null)}>Keep source</button><button className="dm-button dm-danger" onClick={() => { void removeFile(removeId); setRemoveId(null); }}>Remove</button></div></div></div>}
  </aside>;
}
