import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const voiceClientMock = vi.hoisted(() => ({
  callbacks: null as Record<string, (...args: unknown[]) => void> | null,
  instance: null as {
    phase: string;
    connect: ReturnType<typeof vi.fn>;
    startListening: ReturnType<typeof vi.fn>;
    stopListening: ReturnType<typeof vi.fn>;
    bargeIn: ReturnType<typeof vi.fn>;
    setAnswerFormat: ReturnType<typeof vi.fn>;
    close: ReturnType<typeof vi.fn>;
  } | null,
}));

vi.mock('../../lib/voiceStream', () => ({
  VoiceStreamClient: class {
    phase = 'idle';
    connect = vi.fn(async () => undefined);
    startListening = vi.fn(async () => undefined);
    stopListening = vi.fn();
    bargeIn = vi.fn();
    setAnswerFormat = vi.fn();
    close = vi.fn();

    constructor(
      _sessionId: string,
      _answerFormat: string,
      callbacks: Record<string, (...args: unknown[]) => void>,
    ) {
      voiceClientMock.callbacks = callbacks;
      voiceClientMock.instance = this;
    }
  },
}));

vi.mock('./VoiceSpeakerButton', () => ({
  stopActiveTtsPlayback: vi.fn(),
}));

import { VoiceStreamButton } from './VoiceStreamButton';

describe('VoiceStreamButton captions', () => {
  beforeEach(() => {
    voiceClientMock.callbacks = null;
    voiceClientMock.instance = null;
  });

  afterEach(cleanup);

  it('shows partial speech, replaces it with the final transcript, and renders answer deltas', async () => {
    render(<VoiceStreamButton sessionId="session-1" answerFormat="10" />);
    const callbacks = voiceClientMock.callbacks;
    expect(callbacks).not.toBeNull();

    await act(async () => {
      callbacks?.onTranscriptPartial?.('What is');
      callbacks?.onTranscriptPartial?.('What is the answer?');
    });
    expect(screen.getByTestId('voice-transcript-caption').textContent).toContain(
      'What is the answer?',
    );

    await act(async () => {
      callbacks?.onTranscript?.('Final transcript.');
      callbacks?.onAnswerDelta?.('The answer ');
      callbacks?.onAnswerDelta?.('is 42.');
    });
    expect(screen.getByTestId('voice-transcript-caption').textContent).toContain(
      'Final transcript.',
    );
    expect(screen.getByTestId('voice-transcript-caption').textContent).not.toContain(
      'What is the answer?',
    );
    expect(screen.getByTestId('voice-answer-caption').textContent).toContain(
      'The answer is 42.',
    );
    expect(screen.getByText('You said: Final transcript.')).toBeTruthy();
  });

  it('shows browser-reported noise suppression without claiming it when unavailable', async () => {
    render(<VoiceStreamButton sessionId="session-1" answerFormat="10" />);
    const callbacks = voiceClientMock.callbacks;
    expect(callbacks).not.toBeNull();

    await act(async () => callbacks?.onAudioProcessing?.({ noiseSuppression: true }));
    expect(screen.getByTestId('voice-noise-suppression-status').textContent).toBe(
      'Browser noise suppression on',
    );

    await act(async () => callbacks?.onAudioProcessing?.({ noiseSuppression: false }));
    expect(screen.getByTestId('voice-noise-suppression-status').textContent).toBe(
      'Browser noise suppression off',
    );
  });

  it('keeps voice conversation controls actionable', async () => {
    render(<VoiceStreamButton sessionId="session-1" answerFormat="10" />);
    fireEvent.click(screen.getByRole('button', { name: 'Voice conversation' }));
    await act(async () => undefined);
    expect(voiceClientMock.instance?.connect).toHaveBeenCalledTimes(1);
    expect(voiceClientMock.instance?.startListening).toHaveBeenCalledTimes(1);
  });
});
