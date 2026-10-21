import { vi } from 'vitest';

/**
 * Deterministic browser-API doubles for the TTS lifecycle tests.
 *
 * jsdom implements neither audio playback nor object URLs, and the tests must
 * never touch a real network or audio device — so the tests own that boundary
 * explicitly instead of asserting on browser behaviour they cannot observe.
 */

/** Stand-in for `HTMLAudioElement`, recording every play/pause. */
export class FakeAudio {
  static instances: FakeAudio[] = [];
  /**
   * When true, `play()` stays pending until the test calls `resolvePlay()`, so
   * the window while `play()` is still in flight can be exercised.
   */
  static deferPlay = false;

  src: string;
  onended: (() => void) | null = null;
  onerror: (() => void) | null = null;
  playCalls = 0;
  pauseCalls = 0;
  private playResolvers: Array<() => void> = [];

  constructor(src: string) {
    this.src = src;
    FakeAudio.instances.push(this);
  }

  async play(): Promise<void> {
    this.playCalls += 1;
    if (FakeAudio.deferPlay) {
      await new Promise<void>((resolve) => {
        this.playResolvers.push(resolve);
      });
    }
  }

  /** Release a `play()` deferred by `FakeAudio.deferPlay`. */
  resolvePlay(): void {
    const resolvers = this.playResolvers;
    this.playResolvers = [];
    resolvers.forEach((resolve) => resolve());
  }

  pause(): void {
    this.pauseCalls += 1;
  }
}

/** Object URLs handed out / revoked during one test. */
export const objectUrls = {
  created: [] as string[],
  revoked: [] as string[],
};

/** One captured `fetch` call that the test can settle by hand. */
export interface FetchEntry {
  url: string;
  signal: AbortSignal | null;
  /** True once the component aborted this request. */
  aborted: boolean;
  /**
   * Set before the abort to *not* reject on abort, simulating a response that
   * had already completed when the abort arrived — the stale-response case.
   */
  ignoreAbort: boolean;
  resolveOk: () => void;
  resolveError: (status: number, body: unknown) => void;
}

const okResponse = () => ({
  ok: true,
  status: 200,
  json: async () => ({}),
  blob: async () => new Blob([new Uint8Array([1, 2, 3])], { type: 'audio/mpeg' }),
});

const errorResponse = (status: number, body: unknown) => ({
  ok: false,
  status,
  json: async () => body,
  blob: async () => new Blob([]),
});

/** The rejection a real `fetch` produces for an aborted signal. */
export function abortError(): Error {
  const err = new Error('The operation was aborted.');
  err.name = 'AbortError';
  return err;
}

interface ObjectUrlApi {
  createObjectURL?: (blob: Blob) => string;
  revokeObjectURL?: (value: string) => void;
}

/**
 * The `URL` methods are assigned directly (the whole `URL` global must keep
 * working), so `vi.unstubAllGlobals()` cannot restore them: remember what the
 * environment had and let `restoreTtsGlobals()` put it back.
 */
let savedObjectUrlApi: ObjectUrlApi | null = null;

/** Install the `Audio`/object-URL doubles and reset their records. */
export function stubTtsGlobals(): void {
  FakeAudio.instances = [];
  FakeAudio.deferPlay = false;
  objectUrls.created = [];
  objectUrls.revoked = [];
  let counter = 0;

  vi.stubGlobal('Audio', FakeAudio);

  const urlApi = URL as unknown as ObjectUrlApi;
  savedObjectUrlApi = {
    createObjectURL: urlApi.createObjectURL,
    revokeObjectURL: urlApi.revokeObjectURL,
  };
  urlApi.createObjectURL = () => {
    counter += 1;
    const value = `blob:mock-${counter}`;
    objectUrls.created.push(value);
    return value;
  };
  urlApi.revokeObjectURL = (value: string) => {
    objectUrls.revoked.push(value);
  };
}

/** Undo `stubTtsGlobals()`'s object-URL stubs (jsdom has neither method). */
export function restoreTtsGlobals(): void {
  if (!savedObjectUrlApi) return;
  const urlApi = URL as unknown as Record<string, unknown>;
  for (const key of ['createObjectURL', 'revokeObjectURL'] as const) {
    const original = savedObjectUrlApi[key];
    if (original) {
      urlApi[key] = original;
    } else {
      delete urlApi[key];
    }
  }
  savedObjectUrlApi = null;
}

/** Install a `fetch` double whose responses settle only when the test says so. */
export function installFetchMock(): FetchEntry[] {
  const entries: FetchEntry[] = [];

  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      return new Promise<Response>((resolve, reject) => {
        const signal = init?.signal ?? null;
        const entry: FetchEntry = {
          url: String(input),
          signal,
          aborted: false,
          ignoreAbort: false,
          resolveOk: () => resolve(okResponse() as unknown as Response),
          resolveError: (status, body) =>
            resolve(errorResponse(status, body) as unknown as Response),
        };
        entries.push(entry);
        signal?.addEventListener('abort', () => {
          entry.aborted = true;
          if (!entry.ignoreAbort) reject(abortError());
        });
      });
    }),
  );

  return entries;
}
