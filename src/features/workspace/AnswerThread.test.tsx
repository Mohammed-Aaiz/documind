import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ChatMessage } from '../../types';
import { AnswerThread } from './AnswerThread';
import { answerForReading, conversationMarkdown } from './answerPresentation';

afterEach(cleanup);
beforeEach(() => {
  HTMLElement.prototype.scrollIntoView = vi.fn();
});

describe('professional source presentation', () => {
  const cited = '### 1 [2] [3] [4] [7] [8].\n\nCurrent carries charge [1].\n\n### 2 [1] [5] [6] [7].';
  const sources = Array.from({ length: 8 }, (_, index) => ({
    ...baseMessage.sources![0], chunkId: `chunk-${index}`, documentId: index < 4 ? 'a' : 'b',
  }));

  it('removes valid citation clusters from headings and prose without changing stored text', () => {
    const message = { ...baseMessage, text: cited, sources };
    const { container } = render(<AnswerThread messages={[message]} />);
    const reading = container.querySelector('.dm-message-text')!.textContent!;
    expect(reading).not.toMatch(/\[\d+\]/);
    expect(screen.getByRole('heading', { name: '1.' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: '2.' })).toBeTruthy();
    expect(screen.getByText(/Sources · 2 documents/)).toBeTruthy();
    expect(screen.getByText('Passage 8')).toBeTruthy();
    expect(message.text).toBe(cited);
  });

  it('preserves indexing, code, links, escaped brackets and non-source numbers', () => {
    const literal = 'A[1] and `[2]` and [1](https://example.com) and [2026] and \\[1].\n\n```\n[1]\n```';
    expect(answerForReading(literal, 8)).toBe(literal);
    expect(answerForReading('A fact [1][2].', 2)).toBe('A fact.');
    expect(answerForReading('Unknown [9].', 2)).toBe('Unknown [9].');
    expect(answerForReading('No source [1].', 0)).toBe('No source [1].');
  });

  it('does not hide bracketed content in the user question', () => {
    render(<AnswerThread messages={[{ ...baseMessage, sender: 'user', text: 'Explain A[1] and [1].', sources: [] }]} />);
    expect(screen.getByText('Explain A[1] and [1].')).toBeTruthy();
  });

  it('keeps answer notes available without expanding them by default', () => {
    const { container } = render(<AnswerThread messages={[{ ...baseMessage, warnings: ['Some evidence was shortened.'] }]} />);
    const notes = container.querySelector('.dm-answer-notes') as HTMLDetailsElement;
    expect(notes.open).toBe(false);
    expect(notes.textContent).toContain('Some evidence was shortened.');
    expect(screen.getByText('Answer notes')).toBeTruthy();
  });

  it('copies the clean reading answer', async () => {
    const original = Object.getOwnPropertyDescriptor(navigator, 'clipboard');
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } });
    try {
      render(<AnswerThread messages={[{ ...baseMessage, text: 'Current carries charge [1].' }]} />);
      fireEvent.click(screen.getByRole('button', { name: /Copy/ }));
      await waitFor(() => expect(writeText).toHaveBeenCalledWith('Current carries charge.'));
    } finally {
      if (original) Object.defineProperty(navigator, 'clipboard', original);
      else Reflect.deleteProperty(navigator, 'clipboard');
    }
  });

  it('exports clean answers and a compact source list without repeating full passages', () => {
    const text = conversationMarkdown([
      { ...baseMessage, sender: 'user', text: 'Explain A[1].', sources: [] },
      { ...baseMessage, text: 'Current carries charge [1].', sources: [baseMessage.sources![0], baseMessage.sources![0]] },
      { ...baseMessage, id: 'draft', text: 'Unfinished draft', streaming: true },
    ], 'Student');
    expect(text).toContain('Explain A[1].');
    expect(text).toContain('Current carries charge.');
    expect(text).toContain('### Sources\n\n- biology.pdf · Page 4');
    expect(text.match(/biology\.pdf/g)).toHaveLength(1);
    expect(text).not.toContain('Mitochondria generate ATP');
    expect(text).not.toContain('Unfinished draft');
  });
});

const baseMessage: ChatMessage = {
  id: 'answer-1',
  sender: 'oracle',
  text: 'Evidence-based answer.',
  timestamp: '2026-10-27T00:00:00Z',
  sources: [{
    chunkId: 'chunk-1',
    content: 'Mitochondria generate ATP through oxidative phosphorylation.',
    score: 0.7,
    documentId: 'doc-1',
    documentName: 'biology.pdf',
    page: 4,
    retrievalPath: 'hybrid',
    knowledgeGraphPath: 'Mitochondria → performs → oxidative phosphorylation',
    knowledgeGraphHops: 2,
    knowledgeGraphPredicate: 'performs',
    knowledgeGraphQuote: 'Mitochondria generate ATP through oxidative phosphorylation.',
  }],
};

describe('AnswerThread graph evidence', () => {
  it('shows graph path, hop count, predicate, and the exact evidence quote', () => {
    render(<AnswerThread messages={[baseMessage]} />);

    expect(screen.getByRole('region', { name: 'Entity relation evidence' })).toBeTruthy();
    expect(screen.getByText('Graph path · 2 hops')).toBeTruthy();
    expect(screen.getByText('Mitochondria → performs → oxidative phosphorylation')).toBeTruthy();
    expect(screen.getByText('Relation: performs')).toBeTruthy();
    expect(screen.getAllByText('Mitochondria generate ATP through oxidative phosphorylation.')).toHaveLength(2);
  });

  it('does not imply a knowledge graph path for ordinary evidence', () => {
    const message: ChatMessage = {
      ...baseMessage,
      sources: [{ ...baseMessage.sources![0], knowledgeGraphPath: null, knowledgeGraphQuote: null }],
    };
    render(<AnswerThread messages={[message]} />);

    expect(screen.queryByRole('region', { name: 'Entity relation evidence' })).toBeNull();
  });
});
