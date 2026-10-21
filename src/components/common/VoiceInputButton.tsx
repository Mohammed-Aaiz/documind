import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, apiTranscribeAudio } from '../../lib/api';

/**
 * Microphone control for the chat composer.
 *
 * Records via the browser `MediaRecorder` and sends the clip to the real
 * backend STT endpoint (`POST /api/voice/transcribe`) through the shared
 * authenticated API client. The returned text is handed to `onTranscript`;
 * this component never sends the chat message itself and never invents a
 * transcript.
 *
 * States: idle → requesting permission → recording → processing → idle/error.
 */

type VoiceState = 'idle' | 'requesting' | 'recording' | 'processing' | 'error';

interface VoiceInputButtonProps {
  /** Called with the real transcript so the caller can insert it into the input. */
  onTranscript: (text: string) => void;
  /** Notifies the composer when recording/transcribing so conflicting controls can disable. */
  onBusyChange?: (busy: boolean) => void;
  /** Externally disable the control (e.g. while the composer is locked). */
  disabled?: boolean;
}

// Ordered by preference. WebM/Matroska and OGG are accepted by the backend
// audio sniffer; MP4 is a fallback for Safari.
const PREFERRED_MIME_TYPES = [
  'audio/webm;codecs=opus',
  'audio/webm',
  'audio/ogg;codecs=opus',
  'audio/mp4',
];

function pickMimeType(): string | undefined {
  if (
    typeof MediaRecorder === 'undefined' ||
    typeof MediaRecorder.isTypeSupported !== 'function'
  ) {
    return undefined;
  }
  return PREFERRED_MIME_TYPES.find((type) => MediaRecorder.isTypeSupported(type));
}

/** Map a getUserMedia failure to an honest, non-technical message. */
function describeMicrophoneError(err: unknown): string {
  if (typeof DOMException !== 'undefined' && err instanceof DOMException) {
    switch (err.name) {
      case 'NotAllowedError':
      case 'SecurityError':
        return 'Microphone permission was denied. Enable it in your browser to use voice input.';
      case 'NotFoundError':
        return 'No microphone was found on this device.';
      case 'NotReadableError':
        return 'The microphone is already in use by another application.';
      default:
        break;
    }
  }
  return 'Could not start recording. Please try again.';
}

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export const VoiceInputButton: React.FC<VoiceInputButtonProps> = ({
  onTranscript,
  onBusyChange,
  disabled = false,
}) => {
  const [state, setState] = useState<VoiceState>('idle');
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const cancelledRef = useRef(false);
  const timerRef = useRef<number | null>(null);

  const isBusy = state === 'requesting' || state === 'recording' || state === 'processing';

  useEffect(() => {
    onBusyChange?.(isBusy);
  }, [isBusy, onBusyChange]);

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const releaseStream = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
  }, []);

  // Clean up microphone + timer if the component unmounts mid-session.
  useEffect(() => {
    return () => {
      clearTimer();
      const recorder = recorderRef.current;
      if (recorder && recorder.state !== 'inactive') {
        cancelledRef.current = true;
        recorder.stop();
      }
      releaseStream();
    };
  }, [clearTimer, releaseStream]);

  const finalize = useCallback(async () => {
    clearTimer();
    releaseStream();
    recorderRef.current = null;

    const chunks = chunksRef.current;
    chunksRef.current = [];

    // Cancelled by the user — discard the audio, do not transcribe.
    if (cancelledRef.current) {
      cancelledRef.current = false;
      setState('idle');
      return;
    }

    const blob = new Blob(chunks, { type: chunks[0]?.type || 'audio/webm' });
    if (blob.size === 0) {
      setState('error');
      setError('No audio was captured. Please try again.');
      return;
    }

    setState('processing');
    try {
      const result = await apiTranscribeAudio(blob, 'voice-recording');
      const text = (result.text ?? '').trim();
      if (!text) {
        setState('error');
        setError('No speech was detected in the recording.');
        return;
      }
      onTranscript(text);
      setState('idle');
    } catch (err) {
      setState('error');
      // Never surface raw backend/internal detail to the user.
      setError(
        err instanceof ApiError && err.status === 401
          ? 'Your session has expired. Please sign in again.'
          : 'Transcription failed. Please try again.',
      );
    }
  }, [clearTimer, releaseStream, onTranscript]);

  const handleStart = useCallback(async () => {
    setError(null);

    if (
      typeof navigator === 'undefined' ||
      !navigator.mediaDevices?.getUserMedia ||
      typeof MediaRecorder === 'undefined'
    ) {
      setState('error');
      setError('Audio recording is not supported in this browser.');
      return;
    }

    setState('requesting');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const mimeType = pickMimeType();
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);

      chunksRef.current = [];
      cancelledRef.current = false;
      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };
      recorder.onstop = () => {
        void finalize();
      };
      recorderRef.current = recorder;

      recorder.start();
      setElapsed(0);
      setState('recording');
      timerRef.current = window.setInterval(
        () => setElapsed((prev) => prev + 1),
        1000,
      );
    } catch (err) {
      releaseStream();
      setState('error');
      setError(describeMicrophoneError(err));
    }
  }, [finalize, releaseStream]);

  const handleStop = useCallback(() => {
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop();
    } else {
      setState('idle');
    }
  }, []);

  const handleCancel = useCallback(() => {
    cancelledRef.current = true;
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop();
    } else {
      cancelledRef.current = false;
      setState('idle');
    }
  }, []);

  const handleDismissError = useCallback(() => {
    setError(null);
    setState('idle');
  }, []);

  // -------------------------------------------------------------------------
  // Rendering
  // -------------------------------------------------------------------------
  if (state === 'recording') {
    return (
      <div
        className="flex items-center gap-1.5 flex-shrink-0"
        role="status"
        aria-live="polite"
      >
        <span className="flex items-center gap-1.5 px-2 h-9 rounded-lg"
          style={{ background: 'rgba(248,113,113,0.12)', border: '1px solid rgba(248,113,113,0.3)' }}>
          <span className="w-2 h-2 rounded-full bg-red-400 animate-pulse" aria-hidden="true" />
          <span className="text-red-300 tabular-nums" style={{ fontFamily: 'JetBrains Mono', fontSize: '11px' }}>
            {formatElapsed(elapsed)}
          </span>
        </span>
        <button
          type="button"
          onClick={handleStop}
          className="w-9 h-9 rounded-lg flex items-center justify-center text-cyber-cyan hover:bg-surface-bright/40 transition-colors"
          title="Stop recording and transcribe"
          aria-label="Stop recording and transcribe"
        >
          <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>stop_circle</span>
        </button>
        <button
          type="button"
          onClick={handleCancel}
          className="w-9 h-9 rounded-lg flex items-center justify-center text-outline hover:text-error hover:bg-surface-bright/40 transition-colors"
          title="Cancel recording"
          aria-label="Cancel recording"
        >
          <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>close</span>
        </button>
      </div>
    );
  }

  if (state === 'processing') {
    return (
      <div
        className="flex items-center gap-2 px-2 h-9 rounded-lg flex-shrink-0 text-cyber-cyan"
        style={{ background: 'rgba(6,182,212,0.10)', border: '1px solid rgba(6,182,212,0.25)' }}
        role="status"
        aria-live="polite"
      >
        <span className="material-symbols-outlined animate-spin" style={{ fontSize: '16px' }} aria-hidden="true">
          progress_activity
        </span>
        <span style={{ fontFamily: 'JetBrains Mono', fontSize: '11px' }}>Transcribing…</span>
      </div>
    );
  }

  if (state === 'requesting') {
    return (
      <button
        type="button"
        disabled
        className="w-9 h-9 rounded-lg flex items-center justify-center text-cyber-cyan flex-shrink-0 cursor-wait"
        title="Requesting microphone permission…"
        aria-label="Requesting microphone permission"
      >
        <span className="material-symbols-outlined animate-spin" style={{ fontSize: '18px' }}>progress_activity</span>
      </button>
    );
  }

  return (
    <div className="flex items-center gap-1.5 flex-shrink-0 min-w-0">
      {state === 'error' && error && (
        <span
          className="flex items-center gap-1 px-2 h-9 rounded-lg text-red-300 max-w-[180px] min-w-0"
          style={{ background: 'rgba(248,113,113,0.10)', border: '1px solid rgba(248,113,113,0.25)' }}
          role="alert"
          aria-live="assertive"
          title={error}
        >
          <span className="material-symbols-outlined flex-shrink-0" style={{ fontSize: '15px' }} aria-hidden="true">
            error
          </span>
          <span className="truncate" style={{ fontFamily: 'JetBrains Mono', fontSize: '10px' }}>{error}</span>
          <button
            type="button"
            onClick={handleDismissError}
            className="flex-shrink-0 text-outline hover:text-on-surface transition-colors"
            title="Dismiss"
            aria-label="Dismiss voice input message"
          >
            <span className="material-symbols-outlined" style={{ fontSize: '14px' }}>close</span>
          </button>
        </span>
      )}
      <button
        type="button"
        onClick={handleStart}
        disabled={disabled}
        className="w-9 h-9 rounded-lg flex items-center justify-center text-cyber-cyan hover:bg-surface-bright/40 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        title="Record voice input"
        aria-label="Record voice input"
        aria-pressed={false}
      >
        <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>mic</span>
      </button>
    </div>
  );
};
