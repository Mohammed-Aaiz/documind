import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { VoiceSpeakerButton, stopActiveTtsPlayback } from './VoiceSpeakerButton';
import {
  FakeAudio,
  installFetchMock,
  objectUrls,
  restoreTtsGlobals,
  stubTtsGlobals,
} from '../../test/ttsTestDoubles';

/**
 * Regression tests for the Voice TTS playback lifecycle (audit findings
 * F-01, F-02, F-03, F-05, F-06).
 *
 * These drive the real component and the real API helper against a stubbed
 * `fetch` and a stubbed `Audio`, so cancellation, ownership and cleanup are
 * observed directly. They do NOT prove real-browser audio behaviour: no audio
 * device, media stack or network is involved.
 */

interface SpeakerPairProps {
  disabled?: boolean;
  onA?: (playing: boolean) => void;
  onB?: (playing: boolean) => void;
}

const SpeakerPair: React.FC<SpeakerPairProps> = ({
  disabled = false,
  onA,
  onB,
}) => (
  <div>
    <VoiceSpeakerButton
      text="First answer"
      disabled={disabled}
      onPlaybackChange={onA}
    />
    <VoiceSpeakerButton
      text="Second answer"
      disabled={disabled}
      onPlaybackChange={onB}
    />
  </div>
);

const speakerButtons = (): HTMLButtonElement[] =>
  screen.getAllByRole('button') as HTMLButtonElement[];

const statusRegions = (): HTMLElement[] =>
  Array.from(document.querySelectorAll('[role="status"]')) as HTMLElement[];

beforeEach(() => {
  stubTtsGlobals();
});

afterEach(() => {
  cleanup();
  restoreTtsGlobals();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe('VoiceSpeakerButton playback ownership', () => {
  it('1. two messages synthesizing concurrently: only the current attempt plays', async () => {
    const entries = installFetchMock();
    render(<SpeakerPair />);
    const [first, second] = speakerButtons();

    await act(async () => {
      fireEvent.click(first);
    });
    expect(first.getAttribute('aria-busy')).toBe('true');
    expect(entries).toHaveLength(1);
    expect(entries[0].signal).toBeInstanceOf(AbortSignal);

    await act(async () => {
      fireEvent.click(second);
    });

    expect(entries).toHaveLength(2);
    expect(entries[0].aborted).toBe(true);
    expect(entries[1].aborted).toBe(false);

    await act(async () => {
      entries[1].resolveOk();
    });

    expect(FakeAudio.instances).toHaveLength(1);
    expect(second.getAttribute('aria-pressed')).toBe('true');
    expect(first.getAttribute('aria-pressed')).toBe('false');
    expect(first.getAttribute('aria-label')).toBe('Read answer aloud');
  });

  it('2. an older response that resolves after a newer one cannot take over playback', async () => {
    const entries = installFetchMock();
    render(<SpeakerPair />);
    const [first, second] = speakerButtons();

    await act(async () => {
      fireEvent.click(first);
    });
    // Simulate a response that had already completed when the abort arrived.
    entries[0].ignoreAbort = true;

    await act(async () => {
      fireEvent.click(second);
    });
    expect(entries[0].aborted).toBe(true);

    await act(async () => {
      entries[1].resolveOk();
    });
    await act(async () => {
      entries[0].resolveOk();
    });

    expect(FakeAudio.instances).toHaveLength(1);
    expect(FakeAudio.instances[0].src).toBe(objectUrls.created[0]);
    expect(second.getAttribute('aria-pressed')).toBe('true');
    expect(first.getAttribute('aria-pressed')).toBe('false');
  });

  it('3. a response that resolves after unmount never plays and leaks nothing', async () => {
    const entries = installFetchMock();
    const { unmount } = render(<SpeakerPair />);

    await act(async () => {
      fireEvent.click(speakerButtons()[0]);
    });
    expect(objectUrls.created).toHaveLength(0);
    entries[0].ignoreAbort = true;

    await act(async () => {
      unmount();
    });
    expect(entries[0].aborted).toBe(true);

    await act(async () => {
      entries[0].resolveOk();
    });

    expect(FakeAudio.instances).toHaveLength(0);
    expect(objectUrls.created).toHaveLength(0);
    expect(objectUrls.revoked).toHaveLength(0);
  });

  it('F-01a. cancellation while play() is pending cannot resurrect playback', async () => {
    const entries = installFetchMock();
    render(<SpeakerPair />);
    const [first] = speakerButtons();

    FakeAudio.deferPlay = true;
    await act(async () => {
      fireEvent.click(first);
    });
    await act(async () => {
      entries[0].resolveOk();
    });

    const audio = FakeAudio.instances[0];
    expect(audio.playCalls).toBe(1);
    // play() has not resolved, so nothing has been announced as playing yet.
    expect(first.getAttribute('aria-pressed')).toBe('false');

    await act(async () => {
      stopActiveTtsPlayback();
    });
    expect(audio.pauseCalls).toBe(1);
    expect(objectUrls.revoked).toEqual(objectUrls.created);

    await act(async () => {
      audio.resolvePlay();
    });

    expect(first.getAttribute('aria-pressed')).toBe('false');
    expect(first.getAttribute('aria-label')).toBe('Read answer aloud');
    expect(statusRegions()[0].textContent).toBe('');
  });

  it('F-01b. an element that ends before play() resolves cannot leave playback stuck on', async () => {
    const entries = installFetchMock();
    render(<SpeakerPair />);
    const [first] = speakerButtons();

    FakeAudio.deferPlay = true;
    await act(async () => {
      fireEvent.click(first);
    });
    await act(async () => {
      entries[0].resolveOk();
    });

    const audio = FakeAudio.instances[0];
    // The element reports the clip finished before play() ever resolved.
    await act(async () => {
      audio.onended?.();
    });
    expect(first.getAttribute('aria-pressed')).toBe('false');

    await act(async () => {
      audio.resolvePlay();
    });

    expect(first.getAttribute('aria-pressed')).toBe('false');
    expect(first.getAttribute('aria-label')).toBe('Read answer aloud');
    expect(objectUrls.revoked).toEqual(objectUrls.created);
  });

  it('F-01c. an element error is reported once, releases resources and clears ownership', async () => {
    const entries = installFetchMock();
    render(<SpeakerPair />);
    const [first] = speakerButtons();

    FakeAudio.deferPlay = true;
    await act(async () => {
      fireEvent.click(first);
    });
    await act(async () => {
      entries[0].resolveOk();
    });

    const audio = FakeAudio.instances[0];
    // The element reports a media failure while play() is still pending.
    await act(async () => {
      audio.onerror?.();
    });

    expect(first.getAttribute('aria-label')).toBe('Speech unavailable');
    expect(statusRegions()[0].textContent).toBe('Speech unavailable');
    expect(audio.pauseCalls).toBe(1);
    expect(objectUrls.revoked).toEqual(objectUrls.created);

    // The error cleared ownership, so a later stop is a no-op…
    await act(async () => {
      stopActiveTtsPlayback();
    });
    expect(objectUrls.revoked).toEqual(objectUrls.created);

    // …and the play() still in flight cannot revive playback or re-report.
    await act(async () => {
      audio.resolvePlay();
    });
    expect(first.getAttribute('aria-pressed')).toBe('false');
    expect(first.getAttribute('aria-label')).toBe('Speech unavailable');
  });

  it('F-01d. superseding an attempt while play() is pending cannot revive or block playback', async () => {
    const entries = installFetchMock();
    render(<SpeakerPair />);
    const [first, second] = speakerButtons();

    FakeAudio.deferPlay = true;
    await act(async () => {
      fireEvent.click(first);
    });
    await act(async () => {
      entries[0].resolveOk();
    });

    const audioA = FakeAudio.instances[0];
    expect(audioA.playCalls).toBe(1);
    expect(first.getAttribute('aria-pressed')).toBe('false');

    // A legitimate application interaction: the user asks for the second
    // answer while the first attempt's play() is still in flight.
    await act(async () => {
      fireEvent.click(second);
    });

    expect(audioA.pauseCalls).toBe(1);
    expect(objectUrls.revoked).toEqual(objectUrls.created);
    expect(first.getAttribute('aria-label')).toBe('Read answer aloud');

    // The superseded play() resolving now must change nothing…
    await act(async () => {
      audioA.resolvePlay();
    });
    expect(first.getAttribute('aria-pressed')).toBe('false');
    expect(first.getAttribute('aria-label')).toBe('Read answer aloud');
    expect(screen.queryByText(/Speech unavailable/)).toBeNull();
    // …and an attempt that never became audible must not announce a stop.
    expect(statusRegions()[0].textContent).toBe('');

    // The newer attempt plays normally and owns the only live audio.
    FakeAudio.deferPlay = false;
    await act(async () => {
      entries[1].resolveOk();
    });
    expect(second.getAttribute('aria-pressed')).toBe('true');
    expect(FakeAudio.instances).toHaveLength(2);
    expect(objectUrls.created).toHaveLength(2);
    expect(objectUrls.revoked).toEqual([objectUrls.created[0]]);
  });
});

describe('VoiceSpeakerButton and speech-to-text coordination', () => {
  it('4. STT becoming active aborts the pending request and blocks late playback', async () => {
    const entries = installFetchMock();
    const { rerender } = render(<SpeakerPair />);

    await act(async () => {
      fireEvent.click(speakerButtons()[0]);
    });
    entries[0].ignoreAbort = true;

    rerender(<SpeakerPair disabled />);

    expect(entries[0].aborted).toBe(true);
    expect(speakerButtons()[0].getAttribute('aria-busy')).toBe('false');

    await act(async () => {
      entries[0].resolveOk();
    });

    expect(FakeAudio.instances).toHaveLength(0);
    expect(objectUrls.created).toHaveLength(0);
    expect(screen.queryByText(/Speech unavailable/)).toBeNull();
    expect(statusRegions()[0].textContent).toBe('');
  });

  it('F-02. re-enabling the control does not revive a cancelled attempt', async () => {
    const entries = installFetchMock();
    const { rerender } = render(<SpeakerPair />);

    await act(async () => {
      fireEvent.click(speakerButtons()[0]);
    });
    entries[0].ignoreAbort = true;

    rerender(<SpeakerPair disabled />);
    expect(entries[0].aborted).toBe(true);

    rerender(<SpeakerPair />);
    expect(speakerButtons()[0].getAttribute('aria-label')).toBe(
      'Read answer aloud',
    );

    // The cancelled attempt's response finally arrives, with the control
    // enabled again: it must still not play.
    await act(async () => {
      entries[0].resolveOk();
    });
    expect(FakeAudio.instances).toHaveLength(0);
    expect(objectUrls.created).toHaveLength(0);

    // A fresh click starts a genuinely new attempt.
    await act(async () => {
      fireEvent.click(speakerButtons()[0]);
    });
    expect(entries).toHaveLength(2);
    await act(async () => {
      entries[1].resolveOk();
    });
    expect(FakeAudio.instances).toHaveLength(1);
    expect(speakerButtons()[0].getAttribute('aria-pressed')).toBe('true');
  });

  it('5. STT becoming active during playback stops the audio and releases resources', async () => {
    const entries = installFetchMock();
    const onPlayback = vi.fn();
    const { rerender } = render(<SpeakerPair onA={onPlayback} />);

    await act(async () => {
      fireEvent.click(speakerButtons()[0]);
    });
    await act(async () => {
      entries[0].resolveOk();
    });

    const audio = FakeAudio.instances[0];
    expect(audio.pauseCalls).toBe(0);
    expect(onPlayback).toHaveBeenCalledWith(true);

    rerender(<SpeakerPair disabled onA={onPlayback} />);

    expect(audio.pauseCalls).toBe(1);
    // Every URL created for this attempt is revoked exactly once.
    expect(objectUrls.revoked).toEqual(objectUrls.created);
    expect(speakerButtons()[0].getAttribute('aria-pressed')).toBe('false');
    expect(onPlayback).toHaveBeenLastCalledWith(false);
    // STT interrupted audible playback, and the user did not touch this
    // control, so the stop is announced through the live region.
    expect(statusRegions()[0].textContent).toBe('Reading stopped');
  });

  it('6. an intentional cancellation never surfaces as an error', async () => {
    const entries = installFetchMock();
    render(<SpeakerPair />);

    await act(async () => {
      fireEvent.click(speakerButtons()[0]);
    });
    await act(async () => {
      fireEvent.click(speakerButtons()[1]);
    });

    expect(entries[0].aborted).toBe(true);
    expect(screen.queryByText(/Speech unavailable/)).toBeNull();
    expect(screen.queryByText(/session has expired/i)).toBeNull();
    expect(statusRegions()[0].textContent).toBe('');
    expect(speakerButtons()[0].getAttribute('aria-label')).toBe(
      'Read answer aloud',
    );
  });

  it('F-04. a newly mounted idle control cannot clear a playing control’s state', async () => {
    const entries = installFetchMock();
    const onPlayback = vi.fn();
    const { rerender } = render(
      <div>
        <VoiceSpeakerButton text="First answer" onPlaybackChange={onPlayback} />
      </div>,
    );

    await act(async () => {
      fireEvent.click(speakerButtons()[0]);
    });
    await act(async () => {
      entries[0].resolveOk();
    });
    expect(speakerButtons()[0].getAttribute('aria-pressed')).toBe('true');
    expect(onPlayback).toHaveBeenLastCalledWith(true);

    // A second answer arrives while the first is still being read aloud: the
    // new (idle) control must publish nothing, or the microphone would be
    // re-enabled mid-speech.
    rerender(
      <div>
        <VoiceSpeakerButton text="First answer" onPlaybackChange={onPlayback} />
        <VoiceSpeakerButton text="Second answer" onPlaybackChange={onPlayback} />
      </div>,
    );

    expect(onPlayback).toHaveBeenLastCalledWith(true);
    expect(speakerButtons()[0].getAttribute('aria-pressed')).toBe('true');
  });
});

describe('VoiceSpeakerButton error handling', () => {
  it('7. an earlier attempt’s error timer cannot overwrite a retry', async () => {
    vi.useFakeTimers();
    const entries = installFetchMock();
    render(<SpeakerPair />);
    const [first] = speakerButtons();

    await act(async () => {
      fireEvent.click(first);
    });
    await act(async () => {
      entries[0].resolveError(500, { detail: 'synthesis failed' });
    });
    expect(first.getAttribute('aria-label')).toBe('Speech unavailable');

    // Retry before the 3s auto-reset fires.
    await act(async () => {
      fireEvent.click(first);
    });
    await act(async () => {
      entries[1].resolveOk();
    });
    expect(first.getAttribute('aria-pressed')).toBe('true');

    await act(async () => {
      vi.advanceTimersByTime(5000);
    });

    expect(first.getAttribute('aria-pressed')).toBe('true');
    expect(first.getAttribute('aria-label')).toBe('Stop reading answer');
  });

  it('8. repeated cleanup is safe and revokes each object URL exactly once', async () => {
    const entries = installFetchMock();
    const { unmount } = render(<SpeakerPair />);

    await act(async () => {
      fireEvent.click(speakerButtons()[0]);
    });
    await act(async () => {
      entries[0].resolveOk();
    });

    const audio = FakeAudio.instances[0];
    expect(objectUrls.created).toHaveLength(1);
    expect(objectUrls.revoked).toHaveLength(0);

    await act(async () => {
      stopActiveTtsPlayback();
      stopActiveTtsPlayback();
    });

    expect(objectUrls.revoked).toEqual(objectUrls.created);
    expect(audio.pauseCalls).toBe(1);
    expect(speakerButtons()[0].getAttribute('aria-label')).toBe(
      'Read answer aloud',
    );

    await act(async () => {
      unmount();
    });

    // A second cleanup pass must not revoke anything again.
    expect(objectUrls.revoked).toEqual(objectUrls.created);
  });

  it('9. starting playback on another message stops the previous playback and state', async () => {
    const entries = installFetchMock();
    const onA = vi.fn();
    const onB = vi.fn();
    render(<SpeakerPair onA={onA} onB={onB} />);

    await act(async () => {
      fireEvent.click(speakerButtons()[0]);
    });
    await act(async () => {
      entries[0].resolveOk();
    });

    const audioA = FakeAudio.instances[0];
    expect(speakerButtons()[0].getAttribute('aria-pressed')).toBe('true');
    expect(onA).toHaveBeenCalledWith(true);

    await act(async () => {
      fireEvent.click(speakerButtons()[1]);
    });

    expect(speakerButtons()[0].getAttribute('aria-pressed')).toBe('false');
    expect(speakerButtons()[0].getAttribute('aria-label')).toBe(
      'Read answer aloud',
    );
    expect(audioA.pauseCalls).toBe(1);
    expect(objectUrls.revoked).toEqual(objectUrls.created);
    expect(onA).toHaveBeenLastCalledWith(false);
    // Another answer took over audible playback: announce the interruption.
    expect(statusRegions()[0].textContent).toBe('Reading stopped');

    await act(async () => {
      entries[1].resolveOk();
    });

    expect(speakerButtons()[1].getAttribute('aria-pressed')).toBe('true');
    expect(onB).toHaveBeenCalledWith(true);
    expect(FakeAudio.instances).toHaveLength(2);
  });

  it('F-06. errors are actionable without leaking internal detail', async () => {
    const entries = installFetchMock();
    render(<SpeakerPair />);
    const [first] = speakerButtons();

    await act(async () => {
      fireEvent.click(first);
    });
    await act(async () => {
      entries[0].resolveError(401, { detail: 'INTERNAL-401-DETAIL' });
    });

    // The actionable message is announced once, through the live region; the
    // accessible name stays short so it is not announced twice.
    expect(statusRegions()[0].textContent).toBe(
      'Your session has expired. Please sign in again.',
    );
    expect(first.getAttribute('aria-label')).toBe('Speech unavailable');

    await act(async () => {
      fireEvent.click(first);
    });
    await act(async () => {
      entries[1].resolveError(503, { detail: 'INTERNAL-503-UPSTREAM-URL' });
    });

    expect(statusRegions()[0].textContent).toBe('Speech unavailable');
    expect(first.getAttribute('aria-label')).toBe('Speech unavailable');
    expect(document.body.textContent).not.toContain('INTERNAL-401-DETAIL');
    expect(document.body.textContent).not.toContain('INTERNAL-503-UPSTREAM-URL');
  });
});

describe('VoiceSpeakerButton accessibility state', () => {
  it('11. busy, pressed and the live status region are exposed outside the button', async () => {
    const entries = installFetchMock();
    render(<SpeakerPair />);
    const [first] = speakerButtons();

    expect(first.getAttribute('aria-busy')).toBe('false');
    expect(first.getAttribute('aria-pressed')).toBe('false');
    expect(statusRegions()[0].textContent).toBe('');
    expect(statusRegions()[0].closest('button')).toBeNull();

    await act(async () => {
      fireEvent.click(first);
    });
    expect(first.getAttribute('aria-busy')).toBe('true');
    expect(first.getAttribute('aria-label')).toBe('Synthesizing speech...');
    expect(statusRegions()[0].textContent).toBe('Synthesizing speech');

    await act(async () => {
      entries[0].resolveOk();
    });
    expect(first.getAttribute('aria-busy')).toBe('false');
    expect(first.getAttribute('aria-pressed')).toBe('true');
    expect(statusRegions()[0].textContent).toBe('Reading answer aloud');

    // The user stopped it from this focused control: its name and pressed
    // state already announce that, so the live region must not repeat it.
    await act(async () => {
      fireEvent.click(first);
    });
    expect(first.getAttribute('aria-pressed')).toBe('false');
    expect(first.getAttribute('aria-label')).toBe('Read answer aloud');
    expect(statusRegions()[0].textContent).toBe('');
  });
});
