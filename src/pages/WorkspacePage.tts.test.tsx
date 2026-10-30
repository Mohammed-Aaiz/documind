import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import {
  installFetchMock,
  restoreTtsGlobals,
  stubTtsGlobals,
} from '../test/ttsTestDoubles';

/**
 * Workspace-level regression test for the STT/TTS coordination (audit finding
 * F-04): while a message is being read aloud, the microphone control must be
 * disabled, so a recording cannot capture the application's own answer.
 *
 * The conversation composer now hosts the streaming `VoiceStreamButton` rather
 * than a one-shot dictation button; its stable accessible name is
 * "Voice conversation", and the same guard applies (the page disables it while
 * the per-message speaker is playing).
 *
 * The workspace context is replaced by a fixed store; the real
 * `VoiceSpeakerButton` and `VoiceStreamButton` are rendered, and
 * `fetch`/`Audio`/`WebSocket` are stubbed — no network, no audio device, no
 * microphone.
 */

const mocks = vi.hoisted(() => ({
  workspace: {} as Record<string, unknown>,
}));

vi.mock('../context/WorkspaceContext', () => ({
  useWorkspace: () => mocks.workspace,
}));

import { WorkspacePage } from './WorkspacePage';

beforeEach(() => {
  stubTtsGlobals();
  // jsdom has no layout engine.
  Element.prototype.scrollIntoView = vi.fn() as unknown as typeof Element.prototype.scrollIntoView;

  mocks.workspace = {
    files: [],
    uploadError: null,
    addFiles: vi.fn(),
    removeFile: vi.fn(),
    messages: [
      {
        id: 'm1',
        sender: 'oracle',
        text: 'The Oracle answer that can be read aloud.',
        timestamp: '2026-01-01T00:00:00Z',
      },
    ],
    chatInput: '',
    setChatInput: vi.fn(),
    sendMessage: vi.fn(),
    isConversationMode: true,
    sessions: [],
    sessionsLoading: false,
    startNewConversation: vi.fn(),
    openConversation: vi.fn(),
    backToHomepage: vi.fn(),
    drawerOpen: false,
    toggleDrawer: vi.fn(),
    closeDrawer: vi.fn(),
    activeSessionId: 'session-1',
  };
});

afterEach(() => {
  cleanup();
  restoreTtsGlobals();
  vi.unstubAllGlobals();
});

describe('Workspace STT/TTS coordination', () => {
  it('10. the microphone cannot capture the Oracle reading an answer aloud', async () => {
    const entries = installFetchMock();
    render(<WorkspacePage onNavigate={() => {}} />);

    const speaker = screen.getByRole('button', { name: 'Read answer aloud' });
    const mic = screen.getByRole('button', {
      name: 'Voice conversation',
    }) as HTMLButtonElement;

    // Idle: dictation is available.
    expect(mic.disabled).toBe(false);

    await act(async () => {
      fireEvent.click(speaker);
    });
    await act(async () => {
      entries[0].resolveOk();
    });

    expect(speaker.getAttribute('aria-pressed')).toBe('true');
    expect(mic.disabled).toBe(true);

    // Stopping playback releases the microphone again.
    await act(async () => {
      fireEvent.click(speaker);
    });

    expect(speaker.getAttribute('aria-pressed')).toBe('false');
    expect(mic.disabled).toBe(false);
  });

  it('10b. a new Oracle answer arriving mid-playback keeps the microphone disabled', async () => {
    const entries = installFetchMock();
    const { rerender } = render(<WorkspacePage onNavigate={() => {}} />);

    const speaker = screen.getByRole('button', { name: 'Read answer aloud' });
    await act(async () => {
      fireEvent.click(speaker);
    });
    await act(async () => {
      entries[0].resolveOk();
    });

    expect(
      (screen.getByRole('button', {
        name: 'Voice conversation',
      }) as HTMLButtonElement).disabled,
    ).toBe(true);

    // The Oracle answers again while the first answer is still being read
    // aloud. The newly mounted (idle) control must not re-enable the mic.
    (mocks.workspace.messages as unknown[]).push({
      id: 'm2',
      sender: 'oracle',
      text: 'A second answer.',
      timestamp: '2026-01-01T00:00:01Z',
    });
    rerender(<WorkspacePage onNavigate={() => {}} />);

    // A is still the owner: its control is the only one playing, and the
    // control newly mounted for B is idle.
    const playingA = screen.getByRole('button', {
      name: 'Stop reading answer',
    });
    expect(playingA.getAttribute('aria-pressed')).toBe('true');
    expect(
      screen.getAllByRole('button', { name: 'Read answer aloud' }),
    ).toHaveLength(1);
    expect(
      (screen.getByRole('button', {
        name: 'Voice conversation',
      }) as HTMLButtonElement).disabled,
    ).toBe(true);

    // Stopping A releases the microphone again.
    await act(async () => {
      fireEvent.click(playingA);
    });
    expect(
      (screen.getByRole('button', {
        name: 'Voice conversation',
      }) as HTMLButtonElement).disabled,
    ).toBe(false);
    expect(
      screen.getAllByRole('button', { name: 'Read answer aloud' }),
    ).toHaveLength(2);
  });
});
