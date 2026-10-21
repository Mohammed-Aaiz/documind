import React, { useCallback, useEffect, useId, useRef, useState } from 'react';
import { ApiError, apiSynthesizeSpeech } from '../../lib/api';

/**
 * Text-to-speech playback button for Oracle chat responses.
 *
 * Calls ``POST /api/voice/synthesize`` via the authenticated API client,
 * creates an in-memory audio object from the returned MP3 Blob, and manages
 * the playback lifecycle.
 *
 * Enforces:
 * - At most one playback attempt per browser tab (the guarantee is per tab,
 *   not across tabs): starting an attempt cancels any attempt already running,
 *   including one that is still synthesizing.
 * - A per-attempt generation token plus an ``AbortController``, so a late,
 *   superseded or cancelled response can never create, adopt or play audio.
 * - No playback after unmount, and no work started after unmount.
 * - Intentional cancellation is a normal lifecycle event, never an error.
 * - Full object URL revocation on stop, finish, error, cancellation and
 *   unmount; every cleanup path is idempotent.
 * - Text truncation guard keeping the request <= 2000 characters.
 * - Accessible labels, busy/pressed state, and one polite live region that
 *   also announces a stop the user did not make from this control.
 */

export type SpeakerState = 'idle' | 'loading' | 'playing' | 'error';

interface VoiceSpeakerButtonProps {
  /** The assistant answer text to read aloud. */
  text: string;
  /** Whether the control is disabled (e.g. while microphone/STT is active). */
  disabled?: boolean;
  /**
   * Notifies the composer while this control is speaking aloud, so conflicting
   * controls (the microphone) can disable themselves. Only the control that is
   * actually playing publishes, and it publishes the stop as well, so an
   * unrelated control mounting cannot clear another control's state.
   */
  onPlaybackChange?: (playing: boolean) => void;
}

// ---------------------------------------------------------------------------
// One active attempt per browser tab
// ---------------------------------------------------------------------------

interface ActiveAttempt {
  /** Owner instance, so a control can cancel only its own attempt. */
  id: string;
  /** Aborts the request, stops any audio, and resets the owner's state. */
  cancel: (announceStop: boolean) => void;
}

let activeAttempt: ActiveAttempt | null = null;

/**
 * Cancel whatever attempt is active in this tab. Idempotent and safe to call
 * when nothing is active; it never produces a user-visible error.
 *
 * `announceStop` (default true) decides whether stopping *audible* playback is
 * announced through the live region. A stop the user triggered from the
 * focused control passes false: its accessible name and `aria-pressed` change
 * already carry that, and announcing it twice would be noise.
 */
export function stopActiveTtsPlayback(options?: {
  announceStop?: boolean;
}): void {
  const attempt = activeAttempt;
  activeAttempt = null;
  attempt?.cancel(options?.announceStop !== false);
}

/** True for the rejection produced by an aborted fetch. */
function isAbortError(err: unknown): boolean {
  return (
    (typeof DOMException !== 'undefined' &&
      err instanceof DOMException &&
      err.name === 'AbortError') ||
    (err instanceof Error && err.name === 'AbortError')
  );
}

// ---------------------------------------------------------------------------
// Text normalization helper
// ---------------------------------------------------------------------------

function prepareTextForTts(rawText: string): string {
  const clean = rawText.trim();
  if (!clean) return '';
  if (clean.length <= 2000) return clean;

  // Truncate at natural sentence or word boundary before 1990 chars
  const slice = clean.slice(0, 1990);
  const lastSentence = Math.max(
    slice.lastIndexOf('. '),
    slice.lastIndexOf('! '),
    slice.lastIndexOf('? '),
  );
  if (lastSentence > 800) {
    return slice.slice(0, lastSentence + 1).trim();
  }
  const lastSpace = slice.lastIndexOf(' ');
  if (lastSpace > 800) {
    return `${slice.slice(0, lastSpace).trim()}...`;
  }
  return `${slice}...`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const VoiceSpeakerButton: React.FC<VoiceSpeakerButtonProps> = ({
  text,
  disabled = false,
  onPlaybackChange,
}) => {
  const instanceId = useId();
  const [state, setState] = useState<SpeakerState>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  /**
   * True when audible playback was stopped by something other than the user's
   * own click on this control (another answer starting, STT taking over), so
   * the stop is still announced. Cleared when an attempt starts or an error is
   * reported, so the message can never repeat.
   */
  const [stoppedNotice, setStoppedNotice] = useState(false);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null);
  const errorTimeoutRef = useRef<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  /** Monotonic per-instance attempt counter; bumped to make in-flight work stale. */
  const attemptRef = useRef(0);
  const mountedRef = useRef(true);

  // Publish playback to the composer so the microphone can be disabled while
  // the Oracle speaks. Only the playing control publishes — and it publishes
  // the stop too — so an idle control mounting cannot clear a playing
  // control's state.
  const playing = state === 'playing';
  useEffect(() => {
    if (!playing) return;
    onPlaybackChange?.(true);
    return () => onPlaybackChange?.(false);
  }, [playing, onPlaybackChange]);

  const clearErrorTimer = useCallback(() => {
    if (errorTimeoutRef.current !== null) {
      window.clearTimeout(errorTimeoutRef.current);
      errorTimeoutRef.current = null;
    }
  }, []);

  // Idempotent: safe from every terminal path, any number of times.
  const releaseAudio = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.onended = null;
      audioRef.current.onerror = null;
      audioRef.current.src = '';
      audioRef.current = null;
    }
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = null;
    }
  }, []);

  // Only ever called for the attempt that is still current, so a stale timer
  // cannot reset a newer attempt's state.
  const showError = useCallback(
    (message: string) => {
      clearErrorTimer();
      setStoppedNotice(false);
      setState('error');
      setErrorMessage(message);
      errorTimeoutRef.current = window.setTimeout(() => {
        errorTimeoutRef.current = null;
        setState('idle');
        setErrorMessage(null);
      }, 3000);
    },
    [clearErrorTimer],
  );

  // Unmount: never let this control play after it is gone, and never leave an
  // in-flight request, a timer or an object URL behind.
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      attemptRef.current += 1;
      abortRef.current?.abort();
      abortRef.current = null;
      if (activeAttempt?.id === instanceId) activeAttempt = null;
      clearErrorTimer();
      releaseAudio();
    };
  }, [clearErrorTimer, instanceId, releaseAudio]);

  // STT (or any other external lock) took over: abort this control's pending
  // synthesis and stop its playback, without surfacing an error.
  useEffect(() => {
    if (!disabled) return;
    if (activeAttempt?.id === instanceId) stopActiveTtsPlayback();
  }, [disabled, instanceId]);

  const handlePlay = async () => {
    if (disabled || state === 'loading') return;

    if (state === 'playing') {
      // The user stopped it from this focused control: its name and pressed
      // state already announce that, so the live region stays silent.
      stopActiveTtsPlayback({ announceStop: false });
      return;
    }

    const ttsText = prepareTextForTts(text);
    if (!ttsText) return;

    // Supersede any attempt still running in this tab — including one that is
    // still synthesizing. Ownership is registered before the first await, so a
    // newer attempt can always cancel an older one.
    stopActiveTtsPlayback();

    const attempt = attemptRef.current + 1;
    attemptRef.current = attempt;
    clearErrorTimer();
    setErrorMessage(null);
    setStoppedNotice(false);
    setState('loading');

    const controller = new AbortController();
    abortRef.current = controller;

    /** True while this attempt is still the owner and the control is mounted. */
    const isCurrent = () =>
      attemptRef.current === attempt && mountedRef.current;

    /**
     * Set the moment this attempt reaches a terminal state (ended, element
     * error, or cancellation), so no later continuation can revive it.
     */
    let settled = false;

    /** True once this attempt actually became audible. */
    let spoken = false;

    const cancel = (announceStop: boolean) => {
      settled = true;
      controller.abort();
      if (abortRef.current === controller) abortRef.current = null;
      // Invalidate any continuation already past an await.
      if (attemptRef.current === attempt) attemptRef.current += 1;
      releaseAudio();
      if (mountedRef.current) {
        clearErrorTimer();
        setState('idle');
        setErrorMessage(null);
        // Only an audible, externally interrupted stop needs announcing.
        setStoppedNotice(spoken && announceStop);
      }
    };

    const attemptHandle: ActiveAttempt = { id: instanceId, cancel };
    activeAttempt = attemptHandle;

    try {
      const blob = await apiSynthesizeSpeech(
        ttsText,
        'en',
        false,
        controller.signal,
      );

      // Cancelled, superseded, or unmounted while synthesizing: no audio is
      // created, so nothing is left to release.
      if (!isCurrent()) return;

      const audioUrl = URL.createObjectURL(blob);
      const audio = new Audio(audioUrl);

      // Adopt the resources only once this attempt is known to still be
      // current; a superseded attempt revokes its own URL and leaves.
      audioUrlRef.current = audioUrl;
      audioRef.current = audio;

      audio.onended = () => {
        settled = true;
        if (activeAttempt === attemptHandle) activeAttempt = null;
        releaseAudio();
        if (mountedRef.current && isCurrent()) setState('idle');
      };

      audio.onerror = () => {
        if (settled || !mountedRef.current || !isCurrent()) return;
        settled = true;
        if (activeAttempt === attemptHandle) activeAttempt = null;
        releaseAudio();
        showError('Speech unavailable');
      };

      await audio.play();

      // Cancelled while play() was pending: cancel() already released the
      // audio element and revoked its URL. `settled` additionally covers an
      // element that reported `ended`/`error` before play() resolved, which
      // would otherwise leave the control showing "playing" with no audio.
      if (settled || !isCurrent()) return;
      spoken = true;
      setState('playing');
    } catch (err) {
      // An intentional abort is a lifecycle event, not a failure, and an
      // attempt that already settled must not report a second error.
      if (isAbortError(err) || settled) return;
      if (!isCurrent()) return;
      if (activeAttempt === attemptHandle) activeAttempt = null;
      releaseAudio();
      // 401 matches how the rest of the app reports an expired session; no
      // raw backend detail, URL or stack trace is ever surfaced.
      showError(
        err instanceof ApiError && err.status === 401
          ? 'Your session has expired. Please sign in again.'
          : 'Speech unavailable',
      );
    }
  };

  const getAriaLabel = () => {
    switch (state) {
      case 'loading':
        return 'Synthesizing speech...';
      case 'playing':
        return 'Stop reading answer';
      case 'error':
        // The specific message is announced once, through the live region
        // below; repeating it in the accessible name would announce it twice.
        return 'Speech unavailable';
      default:
        return 'Read answer aloud';
    }
  };

  const getIcon = () => {
    switch (state) {
      case 'loading':
        return 'progress_activity';
      case 'playing':
        return 'stop';
      case 'error':
        return 'error_outline';
      default:
        return 'volume_up';
    }
  };

  // One concise status region, outside the button: the loading/playing label
  // sits on a disabled control. A stop the user did not make from this control
  // (another answer starting, STT taking over) is announced here; a stop they
  // made from this focused button is carried by its name and pressed state.
  const statusText =
    state === 'loading'
      ? 'Synthesizing speech'
      : state === 'playing'
        ? 'Reading answer aloud'
        : state === 'error'
          ? errorMessage || 'Speech unavailable'
          : stoppedNotice
            ? 'Reading stopped'
            : '';

  const isButtonDisabled = disabled || state === 'loading' || !text.trim();

  return (
    <span className="inline-flex items-center">
      <button
        type="button"
        onClick={handlePlay}
        disabled={isButtonDisabled}
        aria-busy={state === 'loading'}
        aria-pressed={state === 'playing'}
        aria-label={getAriaLabel()}
        title={getAriaLabel()}
        className={`inline-flex items-center justify-center rounded-md p-1 transition-all focus:outline-none focus:ring-1 focus:ring-cyber-cyan ${
          state === 'playing'
            ? 'text-cyber-cyan bg-cyber-cyan/10 shadow-[0_0_10px_rgba(6,182,212,0.3)]'
            : state === 'error'
              ? 'text-amber-400/80 hover:text-amber-300'
              : 'text-outline hover:text-cyber-cyan hover:bg-white/5'
        } disabled:opacity-40 disabled:cursor-not-allowed`}
        style={{
          border:
            state === 'playing'
              ? '1px solid rgba(6,182,212,0.4)'
              : '1px solid transparent',
        }}
      >
        <span
          className={`material-symbols-outlined text-[16px] leading-none ${
            state === 'loading' ? 'animate-spin text-cyber-cyan' : ''
          }`}
        >
          {getIcon()}
        </span>
      </button>
      <span className="sr-only" role="status" aria-live="polite">
        {statusText}
      </span>
    </span>
  );
};
