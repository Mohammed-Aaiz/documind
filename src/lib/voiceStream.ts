/**
 * Full-duplex voice conversation client (`POST /api/voice/webrtc/offer`).
 *
 * Transport: one `RTCPeerConnection` per conversation session.
 *  - **up** — the microphone is attached to the audio transceiver's sender and
 *    stays live while the control is on, so the *server* can hear a spoken
 *    interruption.  There is no client-side voice-activity detection and no
 *    audio ever leaves the machine.
 *  - **down** — the server's Piper track arrives as a remote `MediaStream` and
 *    is played by an `<audio>` element; its level drives the visualiser.
 *  - **control** — a data channel created by the server carries the JSON turn
 *    protocol (`status`, `transcript`, `answer`, `interrupted`, `error`) and
 *    the client's `barge_in` / `answer_format` messages.
 *
 * The server owns the conversation: it transcribes the audio, runs the
 * LangGraph retrieval/answer pipeline, decides with Silero VAD when a spoken
 * turn ended and when the user talked over the answer, and returns the updated
 * multi-turn `history`.  This client therefore never invents message state —
 * it renders what the channel reports.
 *
 * No STUN/TURN server is configured: the call is host-candidate only, which is
 * what keeps the whole path offline (local evaluation, no external egress).
 *
 * Honest failure: every failure path reports a message through `onError`.
 * There is no silent fallback and no synthetic transcript or answer.
 */

import { ApiConversationTurn, ApiSource, apiVoiceWebRtcOffer } from './api';
import type { WorkspaceMode, WorkspaceTask } from '../types';

export type VoicePhase =
  | 'idle'
  | 'connecting'
  | 'listening'
  | 'transcribing'
  | 'thinking'
  | 'speaking'
  | 'error';

export interface VoiceServerAnswer {
  question: string;
  answer: string;
  engine: string;
  model: string;
  marks: number;
  verification: {
    claimCount: number;
    supportedClaims: number;
    unsupportedClaims: string[];
    uncitedClaims: number;
    citationAccuracy: number;
    verified: boolean;
    status?: string;
    wrongEntityClaims?: string[];
  };
  warnings: string[];
  sources: ApiSource[];
  history: ApiConversationTurn[];
  retrievalQuery?: string;
  followupResolved?: boolean;
  insufficientContext: boolean;
  abstained: boolean;
  memoryBackend: string;
  pipelineVersion: string;
}

export interface VoiceVadStatus {
  engine?: string;
  available?: boolean;
  error?: string | null;
  [key: string]: unknown;
}

export interface VoiceReadyInfo {
  sessionId: string;
  stt: string;
  tts: string;
  /** Server-side Silero VAD.  `available:false` means no barge-in detection. */
  vad?: VoiceVadStatus;
}

/** Browser-reported capture processing; absent values mean the browser did not report support. */
export interface VoiceAudioProcessingStatus {
  echoCancellation?: boolean;
  noiseSuppression?: boolean;
  autoGainControl?: boolean;
}

export interface VoiceStreamCallbacks {
  onPhase?: (phase: VoicePhase) => void;
  onReady?: (info: VoiceReadyInfo) => void;
  /** Cumulative partial recognized text while the local STT decoder is working. */
  onTranscriptPartial?: (text: string, language: string) => void;
  onTranscript?: (text: string, language: string) => void;
  /** Text deltas from the same streamed assistant response that will be spoken. */
  onAnswerDelta?: (text: string) => void;
  onAudioProcessing?: (status: VoiceAudioProcessingStatus) => void;
  onAnswer?: (answer: VoiceServerAnswer) => void;
  onError?: (message: string, code?: string) => void;
  onInterrupted?: () => void;
  onLevel?: (level: number) => void;
}

type ServerMessage = {
  type?: string;
  state?: string;
  text?: string;
  code?: string;
  message?: string;
  [key: string]: unknown;
};

/** A source exactly as the voice payload carries it. */
type VoiceSourcePayload = Partial<ApiSource> & { id?: string };

/**
 * Rename the voice payload's source `id` to `chunkId`.
 *
 * The voice frame is the one place in the API that keys the chunk id `id`
 * (``_json_safe_sources`` in ``backend/voice_webrtc.py``); every REST payload
 * and every renderer uses `chunkId`.  The transcript index renders
 * `chunkId.slice(0, 8)`, so forwarding the server's spelling unchanged threw
 * inside `WorkspacePage` and unmounted the workspace on the first spoken
 * answer.  The rename happens here, at the boundary that receives the frame,
 * rather than in each consumer.
 */
export function normalizeVoiceSources(sources: unknown): ApiSource[] {
  if (!Array.isArray(sources)) return [];
  return sources.map((raw) => {
    const source = (raw ?? {}) as VoiceSourcePayload;
    return {
      chunkId: String(source.chunkId ?? source.id ?? ''),
      content: String(source.content ?? ''),
      score: Number(source.score ?? 0) || 0,
      documentId: String(source.documentId ?? ''),
      documentName: String(source.documentName ?? ''),
      page: typeof source.page === 'number' ? source.page : null,
      retrievalPath: source.retrievalPath ?? null,
      fusionScore: source.fusionScore ?? null,
      structuralHops: source.structuralHops ?? null,
      knowledgeGraphPath: source.knowledgeGraphPath ?? null,
      knowledgeGraphHops: source.knowledgeGraphHops ?? null,
      knowledgeGraphPredicate: source.knowledgeGraphPredicate ?? null,
      knowledgeGraphQuote: source.knowledgeGraphQuote ?? null,
      headingPath: source.headingPath ?? null,
      section: source.section ?? null,
    };
  });
}

/** How long to wait for host ICE candidates before sending the offer. */
const ICE_GATHERING_TIMEOUT_MS = 2_000;

/** The data channel the offer must carry; the server attaches to this label. */
const CONTROL_CHANNEL_LABEL = 'control';

type PeerConnectionCtor = new (config: RTCConfiguration) => RTCPeerConnection;

function webRtcAvailable(): boolean {
  return typeof window !== 'undefined' && typeof window.RTCPeerConnection !== 'undefined';
}

export class VoiceStreamClient {
  private pc: RTCPeerConnection | null = null;
  private transceiver: RTCRtpTransceiver | null = null;
  private channel: RTCDataChannel | null = null;

  private micStream: MediaStream | null = null;
  private audio: HTMLAudioElement | null = null;

  private audioContext: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private sourceNode: AudioNode | null = null;
  /** Silent sink so the analyser graph is pulled without doubling playback. */
  private silentSink: GainNode | null = null;
  private meterFrame: number | null = null;

  private phaseValue: VoicePhase = 'idle';
  private closedByUser = false;
  /** Muted while a turn is being cancelled; the next answer un-mutes it. */
  private playbackMuted = false;

  constructor(
    private readonly sessionId: string,
    private answerFormat: '5' | '10' | '15',
    private readonly callbacks: VoiceStreamCallbacks = {},
    private readonly workspace: WorkspaceMode = 'student',
    private readonly task: WorkspaceTask = 'answer',
  ) {}

  get phase(): VoicePhase {
    return this.phaseValue;
  }

  /** True while the microphone is attached to the peer connection. */
  get microphoneLive(): boolean {
    return this.micStream !== null;
  }

  private setPhase(phase: VoicePhase): void {
    this.phaseValue = phase;
    this.callbacks.onPhase?.(phase);
  }

  private fail(message: string, code?: string): Error {
    this.setPhase('error');
    this.callbacks.onError?.(message, code);
    return new Error(message);
  }

  // -------------------------------------------------------------------------
  // Connection (SDP offer / answer)
  // -------------------------------------------------------------------------

  async connect(): Promise<void> {
    if (this.closedByUser) return;
    if (this.pc) return;

    const Ctor = webRtcAvailable()
      ? (window.RTCPeerConnection as unknown as PeerConnectionCtor)
      : undefined;
    if (!Ctor) {
      throw this.fail('This browser cannot negotiate a WebRTC audio call.');
    }

    this.setPhase('connecting');

    // No ICE servers: host candidates only, so the call never leaves the
    // machine.  This is a requirement, not an oversight.
    const pc = new Ctor({ iceServers: [] });
    this.pc = pc;

    pc.addEventListener('connectionstatechange', this.handleConnectionState);
    pc.addEventListener('iceconnectionstatechange', this.handleConnectionState);
    pc.ontrack = (event) => {
      const stream = event.streams[0] ?? new MediaStream([event.track]);
      this.attachRemoteStream(stream);
    };

    // One sendrecv audio m-line, negotiated once.  The microphone is later
    // swapped in with `replaceTrack`, so starting a turn needs no re-offer.
    this.transceiver = pc.addTransceiver('audio', { direction: 'sendrecv' });

    // The offer must carry the data channel: an SDP answer cannot add an SCTP
    // media section, and the server refuses an offer without it.
    this.attachChannel(pc.createDataChannel(CONTROL_CHANNEL_LABEL));

    try {
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      await this.waitForIceGathering(pc);

      const sdp = pc.localDescription?.sdp ?? offer.sdp ?? '';
      if (!sdp) throw new Error('The browser produced an empty SDP offer.');

      const answer = await apiVoiceWebRtcOffer(this.sessionId, this.answerFormat, sdp, this.workspace, this.task);
      if (this.closedByUser || this.pc !== pc) return;
      await pc.setRemoteDescription({ type: 'answer', sdp: answer.sdp });
    } catch (error) {
      await this.teardownPeer();
      if (this.closedByUser) return;
      const message =
        error instanceof Error && error.message
          ? error.message
          : 'The voice connection could not be established.';
      throw this.fail(message);
    }

    this.setPhase('idle');
  }

  private waitForIceGathering(pc: RTCPeerConnection): Promise<void> {
    if (pc.iceGatheringState === 'complete') return Promise.resolve();
    return new Promise<void>((resolve) => {
      let settled = false;
      const finish = () => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        pc.removeEventListener('icegatheringstatechange', check);
        resolve();
      };
      const check = () => {
        if (pc.iceGatheringState === 'complete') finish();
      };
      // Host-only gathering is immediate; the timeout is a safety net for a
      // browser that never reports completion, not a fallback transport.
      const timer = setTimeout(finish, ICE_GATHERING_TIMEOUT_MS);
      pc.addEventListener('icegatheringstatechange', check);
    });
  }

  private readonly handleConnectionState = (): void => {
    if (!this.pc || this.closedByUser) return;
    const state = this.pc.connectionState;
    if (state === 'failed') {
      this.callbacks.onError?.('The voice connection was lost.');
      this.setPhase('error');
    }
  };

  private attachChannel(channel: RTCDataChannel): void {
    this.channel = channel;
    channel.onmessage = (event: MessageEvent) => this.handleMessage(event);
    channel.onclose = () => {
      if (!this.closedByUser) this.callbacks.onError?.('The voice control channel closed.');
    };
  }

  private send(payload: Record<string, unknown>): boolean {
    const channel = this.channel;
    if (!channel || channel.readyState !== 'open') return false;
    channel.send(JSON.stringify(payload));
    return true;
  }

  private handleMessage(event: MessageEvent): void {
    if (this.closedByUser) return;
    if (typeof event.data !== 'string') return;

    let payload: ServerMessage;
    try {
      payload = JSON.parse(event.data) as ServerMessage;
    } catch {
      this.callbacks.onError?.('The server sent a message this client cannot read.');
      return;
    }

    switch (payload.type) {
      case 'ready':
        this.callbacks.onReady?.({
          sessionId: String(payload.sessionId ?? this.sessionId),
          stt: String(payload.stt ?? 'unknown'),
          tts: String(payload.tts ?? 'unknown'),
          vad: (payload.vad as VoiceVadStatus | undefined) ?? undefined,
        });
        break;

      case 'status': {
        const state = (payload.state as VoicePhase) ?? 'idle';
        // "listening" from the server means "ready for the next turn".  It is
        // only a listening *state* when the microphone is actually live;
        // otherwise the control must not offer to stop a capture that is not
        // running.
        if (state === 'listening' && !this.microphoneLive) {
          this.setPhase('idle');
          break;
        }
        if (state === 'speaking') this.unmutePlayback();
        this.setPhase(state);
        break;
      }

      case 'transcript':
        this.callbacks.onTranscript?.(
          String(payload.text ?? ''),
          String(payload.language ?? ''),
        );
        break;

      case 'transcript_partial':
        this.callbacks.onTranscriptPartial?.(
          String(payload.text ?? ''),
          String(payload.language ?? ''),
        );
        break;

      case 'answer_delta':
        this.callbacks.onAnswerDelta?.(String(payload.text ?? ''));
        break;

      case 'answer': {
        const answer = payload as unknown as VoiceServerAnswer;
        this.callbacks.onAnswer?.({
          ...answer,
          sources: normalizeVoiceSources(payload.sources),
        });
        break;
      }

      case 'interrupted':
        this.mutePlayback();
        this.callbacks.onInterrupted?.();
        this.setPhase(this.microphoneLive ? 'listening' : 'idle');
        break;

      case 'error':
        this.setPhase('error');
        this.callbacks.onError?.(
          String(payload.message ?? 'The voice turn failed.'),
          payload.code ? String(payload.code) : undefined,
        );
        break;

      default:
        break;
    }
  }

  // -------------------------------------------------------------------------
  // Microphone
  // -------------------------------------------------------------------------

  async startListening(): Promise<void> {
    if (this.closedByUser) return;
    if (!this.pc) await this.connect();

    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
      throw this.fail('This browser cannot capture audio.');
    }

    // Autoplay is only allowed after a gesture; this call is that gesture.
    void this.audio?.play().catch(() => undefined);

    if (this.micStream) {
      this.setPhase('listening');
      return;
    }

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
    } catch (error) {
      const message =
        error instanceof DOMException && error.name === 'NotAllowedError'
          ? 'Microphone permission was denied.'
          : 'The microphone could not be started.';
      throw this.fail(message);
    }

    if (this.closedByUser || !this.pc) {
      stream.getTracks().forEach((track) => track.stop());
      return;
    }
    this.micStream = stream;
    const track = stream.getAudioTracks?.()[0] ?? null;
    try {
      const settings = track?.getSettings?.();
      this.callbacks.onAudioProcessing?.({
        echoCancellation: settings?.echoCancellation,
        noiseSuppression: settings?.noiseSuppression,
        autoGainControl: settings?.autoGainControl,
      });
    } catch {
      // Capture itself remains valid if a browser cannot expose its settings.
      this.callbacks.onAudioProcessing?.({});
    }
    try {
      await this.transceiver?.sender.replaceTrack(track);
    } catch (error) {
      stream.getTracks().forEach((item) => item.stop());
      this.micStream = null;
      throw this.fail(
        error instanceof Error
          ? `The microphone could not be attached: ${error.message}`
          : 'The microphone could not be attached.',
      );
    }

    this.startMetering(stream);
    this.setPhase('listening');
  }

  /** Stop talking: end any in-flight turn and detach the microphone. */
  stopListening(): void {
    this.send({ type: 'barge_in' });
    this.releaseMicrophone();
    void this.transceiver?.sender.replaceTrack(null).catch(() => undefined);
    this.setPhase('idle');
  }

  private releaseMicrophone(): void {
    this.stopMetering();
    this.micStream?.getTracks().forEach((track) => track.stop());
    this.micStream = null;
  }

  /**
   * Update the requested answer format for the following turns.
   *
   * The format travels over the control channel, so the server's next turn uses
   * the same value the UI is showing.
   */
  setAnswerFormat(format: '5' | '10' | '15'): void {
    if (format === this.answerFormat) return;
    this.answerFormat = format;
    this.send({ type: 'answer_format', answerFormat: format });
  }

  // -------------------------------------------------------------------------
  // Barge-in / playback
  // -------------------------------------------------------------------------

  /** Interrupt the answer; the server cancels the turn and drops queued audio. */
  bargeIn(): void {
    this.send({ type: 'barge_in' });
    this.mutePlayback();
    this.setPhase(this.microphoneLive ? 'listening' : 'idle');
  }

  private mutePlayback(): void {
    this.playbackMuted = true;
    if (this.audio) this.audio.muted = true;
  }

  private unmutePlayback(): void {
    if (!this.playbackMuted) return;
    this.playbackMuted = false;
    if (this.audio) this.audio.muted = false;
  }

  private attachRemoteStream(stream: MediaStream): void {
    const audio = this.audio ?? new Audio();
    audio.srcObject = stream;
    audio.autoplay = true;
    audio.muted = this.playbackMuted;
    this.audio = audio;

    void audio.play().catch(() => {
      // Autoplay can be blocked until the user interacts; the text answer is
      // already displayed, and `startListening` retries on the next gesture.
      this.callbacks.onError?.('Playback was blocked by the browser.');
    });

    this.attachAnalyser(stream);
  }

  private revokeRemoteStream(): void {
    if (this.audio) {
      this.audio.pause();
      this.audio.srcObject = null;
      this.audio = null;
    }
  }

  // -------------------------------------------------------------------------
  // Level metering (drives the visualiser)
  // -------------------------------------------------------------------------

  private ensureContext(): AudioContext | null {
    if (typeof window === 'undefined') return null;
    const Ctor =
      window.AudioContext ??
      (window as unknown as { webkitAudioContext?: typeof AudioContext })
        .webkitAudioContext;
    if (!Ctor) return null;
    if (!this.audioContext) {
      this.audioContext = new Ctor();
      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = 512;
      // A muted sink keeps the analyser graph alive in browsers that only pull
      // nodes connected to a destination, without duplicating the audio.
      this.silentSink = this.audioContext.createGain();
      this.silentSink.gain.value = 0;
      this.analyser.connect(this.silentSink);
      this.silentSink.connect(this.audioContext.destination);
    }
    return this.audioContext;
  }

  private startMetering(stream: MediaStream): void {
    const context = this.ensureContext();
    if (!context || !this.analyser) return;

    this.detachSource();
    this.sourceNode = context.createMediaStreamSource(stream);
    this.sourceNode.connect(this.analyser);
    this.runMeter();
  }

  private attachAnalyser(stream: MediaStream): void {
    const context = this.ensureContext();
    if (!context || !this.analyser) return;
    this.detachSource();
    this.sourceNode = context.createMediaStreamSource(stream);
    this.sourceNode.connect(this.analyser);
    this.runMeter();
  }

  private detachSource(): void {
    this.stopMetering();
    try {
      this.sourceNode?.disconnect();
    } catch {
      // already detached
    }
    this.sourceNode = null;
  }

  private runMeter(): void {
    if (!this.analyser) return;
    const data = new Uint8Array(this.analyser.fftSize);
    let frame = 0;

    const tick = () => {
      if (!this.analyser) return;
      this.analyser.getByteTimeDomainData(data);
      let sum = 0;
      for (let i = 0; i < data.length; i += 1) {
        const deviation = (data[i] - 128) / 128;
        sum += deviation * deviation;
      }
      const rms = Math.sqrt(sum / data.length);

      // Throttle to ~20 fps: enough for a smooth meter, cheap on the main thread.
      if (frame % 3 === 0) this.callbacks.onLevel?.(Math.min(1, rms * 3));
      frame += 1;
      this.meterFrame = requestAnimationFrame(tick);
    };

    this.meterFrame = requestAnimationFrame(tick);
  }

  private stopMetering(): void {
    if (this.meterFrame !== null) {
      cancelAnimationFrame(this.meterFrame);
      this.meterFrame = null;
    }
    this.callbacks.onLevel?.(0);
  }

  // -------------------------------------------------------------------------
  // Teardown
  // -------------------------------------------------------------------------

  private async teardownPeer(): Promise<void> {
    this.channel = null;
    this.transceiver = null;
    const pc = this.pc;
    this.pc = null;
    if (pc) {
      try {
        pc.close();
      } catch {
        // already closed
      }
    }
  }

  close(): void {
    this.closedByUser = true;
    this.releaseMicrophone();
    void this.transceiver?.sender.replaceTrack(null).catch(() => undefined);
    this.revokeRemoteStream();

    const pc = this.pc;
    this.pc = null;
    this.channel = null;
    this.transceiver = null;
    if (pc) {
      try {
        pc.close();
      } catch {
        // already closed
      }
    }

    this.detachSource();
    try {
      this.analyser?.disconnect();
    } catch {
      // already detached
    }
    try {
      this.silentSink?.disconnect();
    } catch {
      // already detached
    }
    this.analyser = null;
    this.silentSink = null;
    if (this.audioContext) {
      void this.audioContext.close().catch(() => undefined);
      this.audioContext = null;
    }
    this.setPhase('idle');
  }
}
