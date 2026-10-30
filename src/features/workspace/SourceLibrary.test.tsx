import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

const mocks = vi.hoisted(() => ({
  workspace: { value: null as null | Record<string, unknown> },
  rebuildGraph: vi.fn(),
}));

vi.mock('../../context/WorkspaceContext', () => ({
  useWorkspace: () => mocks.workspace.value,
}));
vi.mock('../../components/common/DocumentInsightsPanel', () => ({
  DocumentInsightsPanel: () => null,
}));
vi.mock('../../lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../lib/api')>();
  return { ...actual, apiRebuildDocumentKnowledgeGraph: mocks.rebuildGraph };
});

import { SourceLibrary } from './SourceLibrary';

const file = {
  id: 'doc-1',
  name: 'biology.pdf',
  size: '2 MB',
  type: 'pdf' as const,
  status: 'ready' as const,
  chunkCount: 3,
};

beforeEach(() => {
  mocks.workspace.value = {
    files: [file], uploading: false, uploadError: null,
    addFiles: vi.fn(), removeFile: vi.fn(), refreshFiles: vi.fn(),
  };
  mocks.rebuildGraph.mockReset();
});
afterEach(cleanup);

describe('SourceLibrary knowledge graph action', () => {
  it('does not claim an existing document graph is ready before an explicit build', () => {
    render(<SourceLibrary />);

    expect(screen.getByRole('button', { name: 'Build entity graph' })).toBeTruthy();
    expect(screen.queryByText(/relations?/)).toBeNull();
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('shows pending, then the exact ready status and count returned by the API', async () => {
    let resolveRequest!: (value: { documentId: string; status: 'ready'; relationCount: number }) => void;
    mocks.rebuildGraph.mockReturnValue(new Promise((resolve) => { resolveRequest = resolve; }));
    render(<SourceLibrary />);

    fireEvent.click(screen.getByRole('button', { name: 'Build entity graph' }));
    expect(screen.getByText('Building entity graph…')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Building…' }).hasAttribute('disabled')).toBe(true);

    resolveRequest({ documentId: 'doc-1', status: 'ready', relationCount: 7 });
    expect((await screen.findByRole('status')).textContent).toContain('Ready · 7 relations');
    expect(mocks.rebuildGraph).toHaveBeenCalledWith('doc-1');
  });

  it.each([
    ['partial', 2, 'Partial · 2 relations'],
    ['unavailable', 0, 'Unavailable · 0 relations'],
  ] as const)('renders the API-reported %s status and relation count', async (status, relationCount, label) => {
    mocks.rebuildGraph.mockResolvedValue({ documentId: 'doc-1', status, relationCount });
    render(<SourceLibrary />);

    fireEvent.click(screen.getByRole('button', { name: 'Build entity graph' }));
    expect((await screen.findByRole('status')).textContent).toContain(label);
  });

  it('shows request failures as errors without inventing a graph status or count', async () => {
    mocks.rebuildGraph.mockRejectedValue(new Error('Document has no persisted chunks'));
    render(<SourceLibrary />);

    fireEvent.click(screen.getByRole('button', { name: 'Build entity graph' }));
    expect((await screen.findByRole('alert')).textContent).toContain('Document has no persisted chunks');
    expect(screen.queryByText(/relations?/)).toBeNull();
  });
});
