import React, { useCallback, useEffect, useRef, useState } from 'react';
import type { WorkspaceMode, WorkspaceTask } from '../../types';
import { stopActiveTtsPlayback } from './VoiceSpeakerButton';
import {
  VoicePhase,
  VoiceAudioProcessingStatus,
  VoiceReadyInfo,
  VoiceServerAnswer,
  VoiceStreamClient,
} from '../../lib/voiceStream';

interface VoiceStreamButtonProps {
  /** Conversation the server keeps the history for. */
  sessionId: string | null;
  answerFormat: '5' | '10' | '15';
  workspace?: WorkspaceMode;
  task?: WorkspaceTask;
  /** Called with the server's answer, including the updated history. */
  onAnswer?: (answer: VoiceServerAnswer) => void;
  /** Called when the call is negotiated, with the engines it reports. */
  onReady?: (info: VoiceReadyInfo) => void;
  onActiveChange?: (active: boolean) => void;
  disabled?: boolean;
}

const PHASE_LABEL: Record<VoicePhase, string> = {
  idle: 'Tap to speak',
  connecting: 'Connecting…',
  listening: 'Listening — pause to send',
  transcribing: 'Transcribing…',
  thinking: 'Thinking…',
  speaking: 'Speaking — speak or tap to interrupt',
  error: 'Voice unavailable',
};

const BARS = 5;

/**
 * Continuous duplex voice control over WebRTC.
 *
 * A single control covers the whole turn: start listening → the server's VAD
 * ends the turn on a pause → the answer arrives as text *and* the Piper audio
 * track → tap again while it is generating or speaking to interrupt.
 * Barge-in also works hands-free: because the microphone stays attached during
 * playback, talking over the answer cancels it on the server.  The bars are
 * driven by real microphone/playback levels, not by a timer.
 */
export const VoiceStreamButton: React.FC<VoiceStreamButtonProps> = ({
  sessionId,
  answerFormat,
  workspace = 'student',
  task = 'answer',
  onAnswer,
  onReady,
  onActiveChange,
  disabled = false,
}) => {
  const clientRef = useRef<VoiceStreamClient | null>(null);
  const [phase, setPhase] = useState<VoicePhase>('idle');
  const [level, setLevel] = useState(0);
  const [notice, setNotice] = useState<string | null>(null);
  const [memory, setMemory] = useState<{ backend: string; error?: string | null } | null>(
    null,
  );
  const [vad, setVad] = useState<{ available?: boolean; error?: string | null } | null>(
    null,
  );
  const [transcript, setTranscript] = useState('');
  const [transcriptFinal, setTranscriptFinal] = useState(false);
  const [answerDraft, setAnswerDraft] = useState('');
  const [audioProcessing, setAudioProcessing] =
    useState<VoiceAudioProcessingStatus | null>(null);

  // Keep the latest callbacks without re-creating the call on every render.
  const onAnswerRef = useRef(onAnswer);
  const onReadyRef = useRef(onReady);
  onAnswerRef.current = onAnswer;
  onReadyRef.current = onReady;

  useEffect(() => {
    onActiveChange?.(['connecting', 'listening', 'transcribing', 'thinking', 'speaking'].includes(phase));
    return () => onActiveChange?.(false);
  }, [phase, onActiveChange]);

  useEffect(() => {
    if (!sessionId) {
      clientRef.current?.close();
      clientRef.current = null;
      setPhase('idle');
      setLevel(0);
      setTranscript('');
      setTranscriptFinal(false);
      setAnswerDraft('');
      setAudioProcessing(null);
      return undefined;
    }

    const client = new VoiceStreamClient(sessionId, answerFormat, {
      onPhase: (nextPhase) => {
        setPhase(nextPhase);
        if (nextPhase === 'thinking') setAnswerDraft('');
      },
      onLevel: setLevel,
      onTranscriptPartial: (text) => {
        setTranscript(text);
        setTranscriptFinal(false);
      },
      onTranscript: (text) => {
        setTranscript(text);
        setTranscriptFinal(true);
        if (text) setNotice(null);
      },
      onAnswerDelta: (text) => {
        if (text) setAnswerDraft((previous) => previous + text);
      },
      onAudioProcessing: setAudioProcessing,
      onReady: (info) => {
        setVad({ available: info.vad?.available, error: info.vad?.error ?? null });
        onReadyRef.current?.(info);
      },
      onAnswer: (answer) => {
        setNotice(null);
        setAnswerDraft('');
        setTranscript(answer.question);
        setTranscriptFinal(true);
        // The answer carries where the server actually kept the conversation.
        setMemory({ backend: answer.memoryBackend, error: null });
        onAnswerRef.current?.(answer);
      },
      onInterrupted: () => {
        setAnswerDraft('');
        setNotice('Interrupted. Listening for your next question.');
      },
      onError: (message) => setNotice(message),
    }, workspace, task);

    clientRef.current = client;

    return () => {
      client.close();
      clientRef.current = null;
    };
    // `sessionId` identity is the conversation; a format change applies to the
    // next turn and must not tear down an open call.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, workspace, task]);

  // The mark selector applies to the next turn without reconnecting.
  useEffect(() => {
    clientRef.current?.setAnswerFormat(answerFormat);
  }, [answerFormat]);

  const toggle = useCallback(async () => {
    const client = clientRef.current;
    if (!client) {
      setNotice('Start a conversation first.');
      return;
    }
    setNotice(null);

    try {
      if (client.phase === 'listening') {
        client.stopListening();
        return;
      }
      if (client.phase === 'speaking' || client.phase === 'thinking') {
        client.bargeIn();
        return;
      }
      setTranscript('');
      setTranscriptFinal(false);
      setAnswerDraft('');
      stopActiveTtsPlayback({ announceStop: false });
      await client.connect();
      await client.startListening();
    } catch (error) {
      setNotice(
        error instanceof Error
          ? error.message
          : 'The microphone could not be started.',
      );
    }
  }, []);

  const active = phase === 'listening' || phase === 'speaking';
  const bars = Array.from({ length: BARS }, (_, index) => {
    if (!active) return 0.15;
    // A travelling envelope so the bars read as one waveform, not five copies.
    const wave = 0.35 + 0.65 * Math.abs(Math.sin((index + 1) * 1.1 + level * 6));
    return Math.max(0.15, Math.min(1, level * 1.8 * wave));
  });

  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex items-center gap-2">
        {/* Level meter — real analyser data, zero when no audio is flowing. */}
        <div className="flex items-end gap-0.5 h-6" aria-hidden="true">
          {bars.map((height, index) => (
            <span
              key={index}
              className="w-1 rounded-full transition-[height] duration-75"
              style={{
                height: `${Math.round(height * 100)}%`,
                background:
                  phase === 'speaking'
                    ? 'linear-gradient(180deg, #8B5CF6, #06B6D4)'
                    : 'rgba(6,182,212,0.85)',
                opacity: active ? 1 : 0.35,
              }}
            />
          ))}
        </div>

        <button
          type="button"
          onClick={toggle}
          disabled={disabled || !sessionId}
          aria-pressed={active}
          // A stable accessible name: the phase is announced separately (see the
          // live region below), so assistive technology does not see the control
          // renamed on every state change.
          aria-label="Voice conversation"
          title={PHASE_LABEL[phase]}
          className="w-9 h-9 rounded-lg flex items-center justify-center transition-all disabled:opacity-40 disabled:cursor-not-allowed flex-shrink-0"
          style={{
            background: active
              ? 'linear-gradient(135deg, #8B5CF6, #06B6D4)'
              : 'rgba(29,32,35,1)',
            color: active ? '#0b0e12' : '#06B6D4',
            border: '1px solid rgba(255,255,255,0.08)',
            boxShadow: active ? '0 0 15px rgba(6,182,212,0.45)' : 'none',
          }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>
            {phase === 'speaking' || phase === 'thinking'
              ? 'stop'
              : phase === 'listening'
                ? 'send'
                : 'mic'}
          </span>
        </button>
      </div>

      <span
        aria-live="polite"
        className="text-outline"
        style={{ fontFamily: 'JetBrains Mono', fontSize: '8px', letterSpacing: '0.06em' }}
      >
        {PHASE_LABEL[phase]}
        {memory?.backend === 'memory' ? ' · memory: in-process' : ''}
      </span>

      {(transcript || answerDraft) && (
        <div
          aria-label="Voice captions"
          aria-live="off"
          role="group"
          className="max-w-[320px] text-right text-outline"
          data-testid="voice-captions"
          style={{ fontSize: '10px', lineHeight: 1.45 }}
        >
          {transcript && (
            <p className="m-0" data-testid="voice-transcript-caption">
              <span className="text-slate-400">You: </span>{transcript}
            </p>
          )}
          {answerDraft && (
            <p className="m-0" data-testid="voice-answer-caption">
              <span className="text-cyan-300">DocuMind: </span>{answerDraft}
            </p>
          )}
        </div>
      )}

      {transcriptFinal && transcript && (
        <span className="sr-only" aria-live="polite" aria-atomic="true">
          You said: {transcript}
        </span>
      )}

      {audioProcessing?.noiseSuppression !== undefined && (
        <span
          aria-label={`Browser noise suppression ${audioProcessing.noiseSuppression ? 'enabled' : 'not enabled'}`}
          className="text-outline"
          data-testid="voice-noise-suppression-status"
          style={{ fontSize: '8px' }}
        >
          {audioProcessing.noiseSuppression
            ? 'Browser noise suppression on'
            : 'Browser noise suppression off'}
        </span>
      )}

      {notice && (
        <span
          role="status"
          className="text-yellow-400 max-w-[220px] text-right"
          style={{ fontSize: '9px' }}
        >
          {notice}
        </span>
      )}

      {vad?.available === false && (
        <span
          role="status"
          className="text-yellow-400 max-w-[220px] text-right"
          style={{ fontSize: '9px' }}
          title={vad.error ?? 'The server could not load its voice detector.'}
        >
          Server voice detection unavailable
        </span>
      )}
    </div>
  );
};

export default VoiceStreamButton;
