import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

/**
 * The insights panel's page-extraction section: it must show *which* pages were
 * read by OCR and how, and it must not present missing provenance as zero
 * pages.  The API client is mocked, so these tests assert rendering only —
 * the backend contract is covered by the Python insights tests.
 */

const insightsMock = vi.hoisted(() => ({ fn: vi.fn() }));

vi.mock('../../lib/api', () => {
  class ApiError extends Error {
    status: number;
    constructor(message: string, status: number) {
      super(message);
      this.name = 'ApiError';
      this.status = status;
    }
  }
  return {
    apiGetDocumentInsights: insightsMock.fn,
    ApiError,
  };
});

import { DocumentInsightsPanel } from './DocumentInsightsPanel';

const BASE_INSIGHTS = {
  documentId: 'doc-1',
  name: 'maintenance-scan.pdf',
  fileType: 'pdf',
  fileSize: 12345,
  status: 'ready',
  embeddingStatus: 'ready',
  createdAt: '2026-10-24T00:00:00Z',
  chunkCount: 1,
  structure: {
    totalChunks: 1,
    pagesRepresented: 2,
    pageCount: 2,
    sectionsRepresented: 0,
    headingPathsRepresented: 0,
    elementTypeCounts: {},
    avgChunkLength: 100,
    avgTokenCount: 20,
    totalTokenCount: 20,
  },
  embedding: { embeddedChunkCount: 1, coverage: 1 },
  graph: { nodeCount: 1, edgeCount: 0, relationCounts: {}, coverage: 1 },
  provenance: { parserVersion: null, chunkerVersion: null, embeddingModel: null },
};

function renderWith(pages: unknown) {
  insightsMock.fn.mockResolvedValue({ ...BASE_INSIGHTS, pages });
  render(<DocumentInsightsPanel documentId="doc-1" onClose={() => {}} />);
}

afterEach(() => {
  cleanup();
  insightsMock.fn.mockReset();
});

describe('DocumentInsightsPanel — page extraction', () => {
  it('lists each OCR-read page with its engine, rotation and confidence', async () => {
    renderWith({
      recorded: true,
      pagesTotal: 3,
      nativePageCount: 1,
      ocrPageCount: 1,
      unaccountedPageCount: 1,
      ocrPages: [
        {
          pageNumber: 2,
          textChars: 95,
          ocrEngine: 'rapidocr',
          ocrEngineVersion: '3.10.0',
          ocrConfidence: 0.98765,
          ocrRotation: 180,
          ocrSeconds: 2.5,
        },
      ],
      unaccountedPages: [{ pageNumber: 3, failureReason: 'ocr_failed' }],
    });

    expect(await screen.findByText('PAGE EXTRACTION')).toBeTruthy();
    expect(await screen.findByText('PAGE 2 · OCR')).toBeTruthy();
    // Recorded facts only: engine, rotation, latency, characters.
    expect(
      screen.getByText('rapidocr 3.10.0 · read rotated 180° · 2.5s · 95 chars'),
    ).toBeTruthy();
    expect(screen.getByText('0.988')).toBeTruthy();
    // The unreadable page states its reason in words, not its enum value.
    expect(screen.getByText('PAGE 3')).toBeTruthy();
    expect(screen.getByText('OCR found no text')).toBeTruthy();
  });

  it('says a document was not recorded rather than claiming zero pages', async () => {
    renderWith({
      recorded: false,
      pagesTotal: 0,
      nativePageCount: 0,
      ocrPageCount: 0,
      unaccountedPageCount: 0,
      ocrPages: [],
      unaccountedPages: [],
    });

    expect(
      await screen.findByText(/Not recorded for this document/),
    ).toBeTruthy();
    expect(screen.queryByText('PAGES')).toBeNull();
  });

  it('states plainly when every page had a usable text layer', async () => {
    renderWith({
      recorded: true,
      pagesTotal: 2,
      nativePageCount: 2,
      ocrPageCount: 0,
      unaccountedPageCount: 0,
      ocrPages: [],
      unaccountedPages: [],
    });

    expect(
      await screen.findByText('Every page had a usable text layer.'),
    ).toBeTruthy();
  });

  it('omits the section on a server that predates page provenance', async () => {
    renderWith(undefined);

    expect(await screen.findByText('STRUCTURE')).toBeTruthy();
    expect(screen.queryByText('PAGE EXTRACTION')).toBeNull();
  });
});
