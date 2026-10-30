import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import type { ChatMessage } from '../../types';
import { AnswerThread } from './AnswerThread';

afterEach(cleanup);
beforeEach(() => {
  HTMLElement.prototype.scrollIntoView = vi.fn();
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
