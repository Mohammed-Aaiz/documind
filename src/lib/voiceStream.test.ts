import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { VoicePhase, VoiceStreamClient } from './voiceStream';
import type { ApiSource } from './api';

/**
 * WebRTC voice client tests: SDP negotiation, the control-channel protocol,
 * microphone attach/detach, playback of the remote track, barge-in and honest
 * capability failure.
 *
 * `RTCPeerConnection`, the data channel, `getUserMedia` and `Audio` are fakes —
 * jsdom has no WebRTC stack.  No network and no real audio: the one HTTP call
 * (the SDP offer) goes through a stubbed `fetch`, and the assertions are about
 * what the client sends and how it maps the server's messages onto phases.
 */

class FakeDataChannel {
  static instances: FakeDataChannel[] = [];
  readyState: RTCDataChannelState = 'connecting';
  sent: string[] = [];
  onmessage: ((event: { data: string }) => void) | null = null;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;

  constructor() {
    FakeDataChannel.instances.push(this);
  }

  send(data: string): void {
    this.sent.push(data);
  }

  close(): void {
    this.readyState = 'closed';
    this.onclose?.();
  }

  // --- test helpers ---
  open(): void {
    this.readyState = 'open';
    this.onopen?.();
  }

  emit(payload: Record<string, unknown>): void {
    this.onmessage?.({ data: JSON.stringify(payload) });
  }

  frames(): Array<Record<string, unknown>> {
    return this.sent.map((message) => JSON.parse(message) as Record<string, unknown>);
  }
}

class FakeSender {
  replaceTrack = vi.fn(async (_track: MediaStreamTrack | null) => undefined);
}

class FakeTransceiver {
  readonly sender = new FakeSender();
  direction = 'sendrecv';
}

class FakePeerConnection {
  static instances: FakePeerConnection[] = [];

  readonly config: RTCConfiguration;
  readonly senders: FakeSender[] = [];
  localDescription: { type: string; sdp: string } | null = null;
  remoteDescription: { type: string; sdp: string } | null = null;
  connectionState = 'new';
  iceGatheringState = 'complete';
  closed = false;

  readonly channels: FakeDataChannel[] = [];
  ontrack:
    | ((event: { streams: MediaStream[]; track: { kind: string } }) => void)
    | null = null;
  onconnectionstatechange: (() => void) | null = null;

  constructor(config: RTCConfiguration) {
    this.config = config;
    FakePeerConnection.instances.push(this);
  }

  addEventListener(): void {}
  removeEventListener(): void {}

  addTransceiver(kind: string): FakeTransceiver {
    expect(kind).toBe('audio');
    const transceiver = new FakeTransceiver();
    this.senders.push(transceiver.sender);
    return transceiver;
  }

  async createOffer(): Promise<{ type: string; sdp: string }> {
    return { type: 'offer', sdp: 'offer-sdp' };
  }

  async setLocalDescription(description: { type: string; sdp: string }): Promise<void> {
    this.localDescription = description;
  }

  async setRemoteDescription(description: { type: string; sdp: string }): Promise<void> {
    this.remoteDescription = description;
  }

  createDataChannel(label: string): FakeDataChannel {
    expect(label).toBe('control');
    const channel = new FakeDataChannel();
    this.channels.push(channel);
    return channel;
  }

  close(): void {
    this.closed = true;
    this.connectionState = 'closed';
  }

  // --- test helpers ---

  deliverRemoteStream(stream: MediaStream): void {
    this.ontrack?.({ streams: [stream], track: { kind: 'audio' } });
  }
}

class FakeAudio {
  static instances: FakeAudio[] = [];
  srcObject: MediaStream | null = null;
  autoplay = false;
  muted = false;
  paused = false;
  played = false;

  constructor() {
    FakeAudio.instances.push(this);
  }

  async play(): Promise<void> {
    this.played = true;
  }

  pause(): void {
    this.paused = true;
  }
}

class FakeAnalyser {
  fftSize = 512;
  connect(): void {}
  disconnect(): void {}
  getByteTimeDomainData(data: Uint8Array): void {
    data.fill(128);
  }
}

class FakeGain {
  gain = { value: 1 };
  connect(): void {}
  disconnect(): void {}
}

class FakeAudioContext {
  static instances: FakeAudioContext[] = [];
  destination: unknown = {};
  readonly analysers: FakeAnalyser[] = [];

  constructor() {
    FakeAudioContext.instances.push(this);
  }

  createAnalyser(): FakeAnalyser {
    const analyser = new FakeAnalyser();
    this.analysers.push(analyser);
    return analyser;
  }

  createGain(): FakeGain {
    return new FakeGain();
  }

  createMediaStreamSource(): { connect(): void; disconnect(): void } {
    return { connect: () => undefined, disconnect: () => undefined };
  }

  async close(): Promise<void> {}
}

const MIC_TRACK = {
  kind: 'audio',
  stop: vi.fn(),
  getSettings: vi.fn(() => ({
    echoCancellation: true,
    noiseSuppression: true,
    autoGainControl: true,
  })),
};
const FAKE_STREAM = {
  getAudioTracks: () => [MIC_TRACK],
  getTracks: () => [MIC_TRACK],
};

const REMOTE_STREAM = { id: 'remote-stream' } as unknown as MediaStream;

const ANSWER_SDP = 'answer-sdp';

function makeClient() {
  const events: {
    phases: VoicePhase[];
    answers: unknown[];
    transcripts: string[];
    partialTranscripts: string[];
    answerDeltas: string[];
    audioProcessing: unknown[];
    errors: string[];
    ready: unknown[];
    interrupted: number;
  } = {
    phases: [],
    answers: [],
    transcripts: [],
    partialTranscripts: [],
    answerDeltas: [],
    audioProcessing: [],
    errors: [],
    ready: [],
    interrupted: 0,
  };

  const client = new VoiceStreamClient('session-1', '10', {
    onPhase: (phase) => events.phases.push(phase),
    onAnswer: (answer) => events.answers.push(answer),
    onTranscript: (text) => events.transcripts.push(text),
    onTranscriptPartial: (text) => events.partialTranscripts.push(text),
    onAnswerDelta: (text) => events.answerDeltas.push(text),
    onAudioProcessing: (settings) => events.audioProcessing.push(settings),
    onError: (message) => events.errors.push(message),
    onReady: (info) => events.ready.push(info),
    onInterrupted: () => {
      events.interrupted += 1;
    },
  });

  return { client, events };
}

/** Connect a client and hand back its peer connection and control channel. */
async function connected() {
  const { client, events } = makeClient();
  await client.connect();
  const pc = FakePeerConnection.instances[FakePeerConnection.instances.length - 1];
  const channel = pc.channels[0];
  channel.open();
  return { client, events, pc, channel };
}

beforeEach(() => {
  FakePeerConnection.instances = [];
  FakeDataChannel.instances = [];
  FakeAudio.instances = [];
  FakeAudioContext.instances = [];

  vi.stubGlobal(
    'RTCPeerConnection',
    FakePeerConnection as unknown as typeof RTCPeerConnection,
  );
  vi.stubGlobal('Audio', FakeAudio as unknown as typeof Audio);
  vi.stubGlobal('AudioContext', FakeAudioContext as unknown as typeof AudioContext);
  vi.stubGlobal('requestAnimationFrame', () => 1);
  vi.stubGlobal('cancelAnimationFrame', () => undefined);

  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: { getUserMedia: vi.fn(async () => FAKE_STREAM) },
  });

  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        sdp: ANSWER_SDP,
        type: 'answer',
        sessionId: 'session-1',
        vad: { engine: 'silero-onnx', available: true, error: null },
        stt: 'whisper-local',
        tts: 'piper-local',
      }),
    })),
  );
});

afterEach(() => {
  vi.restoreAllMocks();
  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: undefined,
  });
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe('VoiceStreamClient negotiation', () => {
  it('posts the SDP offer with the JWT and applies the answer', async () => {
    localStorage.setItem('documind_token', 'token-123');
    const { client } = makeClient();

    await client.connect();

    const pc = FakePeerConnection.instances[0];
    expect(pc.config.iceServers).toEqual([]);
    // The SDP answer cannot add an SCTP section, so the offer carries it.
    expect(pc.channels).toHaveLength(1);
    expect(pc.channels[0].readyState).toBe('connecting');
    expect(pc.localDescription?.sdp).toBe('offer-sdp');
    expect(pc.remoteDescription).toEqual({ type: 'answer', sdp: ANSWER_SDP });

    const call = (fetch as unknown as { mock: { calls: [string, RequestInit][] } })
      .mock.calls[0];
    expect(call[0]).toContain('/api/voice/webrtc/offer');
    expect(call[1].method).toBe('POST');
    expect((call[1].headers as Record<string, string>).Authorization).toBe(
      'Bearer token-123',
    );
    expect(JSON.parse(String(call[1].body))).toEqual({
      sdp: 'offer-sdp',
      type: 'offer',
      sessionId: 'session-1',
      answerFormat: '10',
      workspace: 'student',
      task: 'answer',
    });

    expect(client.phase).toBe('idle');
  });

  it('says so when the browser has no WebRTC stack', async () => {
    vi.stubGlobal('RTCPeerConnection', undefined);
    const { client, events } = makeClient();

    await expect(client.connect()).rejects.toThrow(/WebRTC/i);

    expect(events.errors[0]).toMatch(/WebRTC/i);
    expect(client.phase).toBe('error');
  });

  it('surfaces a rejected offer instead of pretending the call exists', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Not authenticated' }),
      })),
    );
    const { client, events } = makeClient();

    await expect(client.connect()).rejects.toThrow(/Not authenticated/i);

    expect(events.errors).toEqual(['Not authenticated']);
    expect(FakePeerConnection.instances[0].closed).toBe(true);
    expect(client.phase).toBe('error');
  });

  it('reports the engines and the server VAD status it is given', async () => {
    const { client, events, channel } = await connected();

    channel.emit({
      type: 'ready',
      sessionId: 'session-1',
      stt: 'whisper-local',
      tts: 'piper-local',
      vad: { engine: 'silero-onnx', available: false, error: 'model missing' },
    });

    expect(events.ready).toEqual([
      {
        sessionId: 'session-1',
        stt: 'whisper-local',
        tts: 'piper-local',
        vad: { engine: 'silero-onnx', available: false, error: 'model missing' },
      },
    ]);
    expect(client.phase).toBe('idle');
  });
});

describe('VoiceStreamClient microphone', () => {
  it('attaches the microphone to the negotiated audio sender', async () => {
    const { client, pc } = await connected();

    await client.startListening();

    expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledWith({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    expect(pc.senders[0].replaceTrack).toHaveBeenCalledWith(MIC_TRACK);
    expect(client.microphoneLive).toBe(true);
    expect(client.phase).toBe('listening');
  });

  it('detaches the microphone and stops its tracks', async () => {
    const { client, pc, channel } = await connected();
    await client.startListening();

    client.stopListening();

    expect(pc.senders[0].replaceTrack).toHaveBeenLastCalledWith(null);
    expect(MIC_TRACK.stop).toHaveBeenCalled();
    expect(client.microphoneLive).toBe(false);
    expect(client.phase).toBe('idle');
    // The server ends any turn in flight when the client stops talking.
    expect(channel.frames()).toContainEqual({ type: 'barge_in' });
  });

  it('says so when the browser cannot capture audio', async () => {
    const { client, events } = await connected();
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: undefined,
    });

    await expect(client.startListening()).rejects.toThrow(/cannot capture audio/i);

    expect(events.errors).toContain('This browser cannot capture audio.');
  });

  it('reports a denied microphone permission', async () => {
    const { client, events } = await connected();
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: {
        getUserMedia: vi.fn(async () => {
          throw new DOMException('denied', 'NotAllowedError');
        }),
      },
    });

    await expect(client.startListening()).rejects.toThrow(/permission was denied/i);

    expect(events.errors).toContain('Microphone permission was denied.');
  });
});

describe('VoiceStreamClient protocol', () => {
  it('maps server status frames onto phases', async () => {
    const { client, channel } = await connected();

    channel.emit({ type: 'status', state: 'transcribing' });
    expect(client.phase).toBe('transcribing');

    channel.emit({ type: 'status', state: 'thinking' });
    expect(client.phase).toBe('thinking');

    channel.emit({ type: 'status', state: 'speaking' });
    expect(client.phase).toBe('speaking');
  });

  it('does not claim the microphone is listening when none is attached', async () => {
    const { client, channel } = await connected();

    channel.emit({ type: 'status', state: 'listening' });

    expect(client.phase).toBe('idle');
  });

  it('keeps saying listening after a turn when the microphone is still live', async () => {
    const { client, channel } = await connected();
    await client.startListening();

    channel.emit({ type: 'status', state: 'speaking' });
    channel.emit({ type: 'status', state: 'listening' });

    expect(client.phase).toBe('listening');
  });

  it('forwards transcripts and the answer with its history', async () => {
    const { events, channel } = await connected();

    channel.emit({ type: 'transcript', text: 'What is the interval?', language: 'en' });
    const payload = {
      type: 'answer',
      question: 'What is the interval?',
      answer: 'Six months [1].',
      engine: 'instruct',
      model: 'Qwen/Qwen2.5-0.5B-Instruct',
      marks: 10,
      verification: { verified: true },
      warnings: [],
      sources: [{ id: 'c1' }],
      history: [
        { role: 'user', content: 'What is the interval?', createdAt: 't1' },
        { role: 'assistant', content: 'Six months [1].', createdAt: 't2' },
      ],
      insufficientContext: false,
      abstained: false,
      memoryBackend: 'redis',
      pipelineVersion: 'langgraph-conversation-v1',
    };
    channel.emit(payload);

    expect(events.transcripts).toEqual(['What is the interval?']);
    expect((events.answers[0] as typeof payload).answer).toBe('Six months [1].');
  });

  it('forwards cumulative STT partials, final transcript, and assistant answer deltas', async () => {
    const { events, channel } = await connected();

    channel.emit({ type: 'transcript_partial', text: 'What is', language: 'en' });
    channel.emit({ type: 'transcript_partial', text: 'What is the interval?', language: 'en' });
    channel.emit({ type: 'transcript', text: 'What is the interval?', language: 'en' });
    channel.emit({ type: 'answer_delta', text: 'The interval ' });
    channel.emit({ type: 'answer_delta', text: 'is six months.' });

    expect(events.partialTranscripts).toEqual(['What is', 'What is the interval?']);
    expect(events.transcripts).toEqual(['What is the interval?']);
    expect(events.answerDeltas).toEqual(['The interval ', 'is six months.']);
  });

  it('requests browser echo/noise processing and reports only browser-reported settings', async () => {
    const getUserMedia = vi.fn(async () => FAKE_STREAM);
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia },
    });
    const { client, events } = await connected();

    await client.startListening();

    expect(getUserMedia).toHaveBeenCalledWith({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    expect(events.audioProcessing).toEqual([
      { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    ]);
  });

  it("renames the voice payload's source id to the chunkId renderers expect", async () => {
    const { events, channel } = await connected();

    channel.emit({
      type: 'answer',
      question: 'What is the interval?',
      answer: 'Six months [1].',
      engine: 'instruct',
      model: 'Qwen/Qwen2.5-0.5B-Instruct',
      marks: 10,
      verification: { verified: true },
      warnings: [],
      // `_json_safe_sources` in backend/voice_webrtc.py keys the chunk id `id`.
      sources: [
        {
          id: 'chunk-1',
          content: 'The interval is six months.',
          score: 0.5,
          documentId: 'doc-1',
          documentName: 'report.pdf',
          page: 2,
          section: 'Intervals',
          evidenceKind: 'chunk',
          retrievalPath: 'hybrid',
          knowledgeGraphPath: 'maintenance schedule → sets interval → six months',
          knowledgeGraphHops: 1,
          knowledgeGraphPredicate: 'sets interval',
          knowledgeGraphQuote: 'The maintenance interval is six months.',
        },
      ],
      history: [
        { role: 'user', content: 'What is the interval?', createdAt: 't1' },
        { role: 'assistant', content: 'Six months [1].', createdAt: 't2' },
      ],
      insufficientContext: false,
      abstained: false,
      memoryBackend: 'redis',
      pipelineVersion: 'langgraph-conversation-v1',
    });

    const answer = events.answers[0] as { sources: ApiSource[] };
    expect(answer.sources).toHaveLength(1);
    expect(answer.sources[0].chunkId).toBe('chunk-1');
    expect(answer.sources[0].section).toBe('Intervals');
    expect(answer.sources[0].retrievalPath).toBe('hybrid');
    expect(answer.sources[0].knowledgeGraphPath).toBe('maintenance schedule → sets interval → six months');
    expect(answer.sources[0].knowledgeGraphHops).toBe(1);
    expect(answer.sources[0].knowledgeGraphPredicate).toBe('sets interval');
    expect(answer.sources[0].knowledgeGraphQuote).toBe('The maintenance interval is six months.');
  });

  it('surfaces an error frame instead of pretending the turn succeeded', async () => {
    const { client, events, channel } = await connected();

    channel.emit({ type: 'error', code: 'vad_unavailable', message: 'No VAD model.' });

    expect(events.errors).toEqual(['No VAD model.']);
    expect(client.phase).toBe('error');
  });

  it('announces an answer-format change over the control channel', async () => {
    const { client, channel } = await connected();

    client.setAnswerFormat('15');
    client.setAnswerFormat('15');

    expect(channel.frames()).toEqual([{ type: 'answer_format', answerFormat: '15' }]);
  });
});

describe('VoiceStreamClient playback and barge-in', () => {
  it('plays the remote track through an audio element', async () => {
    const { client, pc } = await connected();

    pc.deliverRemoteStream(REMOTE_STREAM);

    const audio = FakeAudio.instances[0];
    expect(audio.srcObject).toBe(REMOTE_STREAM);
    expect(audio.autoplay).toBe(true);
    await vi.waitFor(() => expect(audio.played).toBe(true));
    expect(client.phase).toBe('idle');
  });

  it('mutes playback on a tap barge-in and tells the server', async () => {
    const { client, pc, channel } = await connected();
    await client.startListening();
    pc.deliverRemoteStream(REMOTE_STREAM);

    client.bargeIn();

    expect(channel.frames()).toContainEqual({ type: 'barge_in' });
    expect(FakeAudio.instances[0].muted).toBe(true);
    expect(client.phase).toBe('listening');
  });

  it('reports a server-side interruption and returns to listening', async () => {
    const { client, events, pc, channel } = await connected();
    await client.startListening();
    pc.deliverRemoteStream(REMOTE_STREAM);

    channel.emit({ type: 'status', state: 'speaking' });
    channel.emit({ type: 'interrupted', reason: 'vad' });

    expect(events.interrupted).toBe(1);
    expect(FakeAudio.instances[0].muted).toBe(true);
    expect(client.phase).toBe('listening');
  });

  it('un-mutes playback when the next answer starts speaking', async () => {
    const { client, pc, channel } = await connected();
    await client.startListening();
    pc.deliverRemoteStream(REMOTE_STREAM);

    channel.emit({ type: 'interrupted', reason: 'vad' });
    channel.emit({ type: 'status', state: 'speaking' });

    expect(FakeAudio.instances[0].muted).toBe(false);
    expect(client.phase).toBe('speaking');
  });
});

describe('VoiceStreamClient teardown', () => {
  it('closes the peer connection and returns to idle', async () => {
    const { client, pc } = await connected();
    await client.startListening();

    client.close();

    expect(pc.closed).toBe(true);
    expect(MIC_TRACK.stop).toHaveBeenCalled();
    expect(client.phase).toBe('idle');
  });
});
