import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { SettingsProvider } from '../context/SettingsContext';
import { SettingsPage } from './SettingsPage';

/**
 * Settings-page honesty regression tests.
 *
 * The page talks to the REAL settings context, which talks to the REAL API
 * client, against a stubbed `fetch`. Two classes of defect are pinned:
 *
 * 1. Fabricated state — the page must never present a placeholder identity, an
 *    "ACTIVE" security feature that does not exist, or a saved value the server
 *    never confirmed.
 * 2. Dishonest outcomes — a failed PATCH must never be reported as success.
 *
 * jsdom only: no network, no backend. These assertions are DOM-level.
 */

const mocks = vi.hoisted(() => ({
  user: { name: 'Ada Lovelace', email: 'ada@example.com' } as {
    name: string;
    email: string;
    avatarUrl?: string;
  },
  logout: vi.fn(),
}));

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    user: mocks.user,
    login: vi.fn(),
    logout: mocks.logout,
    updateUser: vi.fn(),
  }),
}));

/** The exact shape GET/PATCH /api/settings use. */
interface ServerSettings {
  processingDepth: number;
  contextWindow: string;
  theme: string;
  density: string;
  glassIntensity: number;
}

/** The backend's own column defaults for a user who has never saved. */
const serverDefaults = (): ServerSettings => ({
  processingDepth: 3,
  contextWindow: 'persistent',
  theme: 'dark-cyber',
  density: 'high',
  glassIntensity: 70,
});

interface FetchEntry {
  method: string;
  url: string;
  body: Record<string, unknown> | null;
  resolveOk: (settings: ServerSettings) => void;
  resolveError: (status: number) => void;
}

const jsonResponse = (status: number, body: unknown): Response =>
  ({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  }) as unknown as Response;

/** A `fetch` double whose responses settle only when the test says so. */
function installFetchMock(): FetchEntry[] {
  const entries: FetchEntry[] = [];

  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      return new Promise<Response>((resolve) => {
        entries.push({
          method: init?.method ?? 'GET',
          url: String(input),
          body: init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : null,
          resolveOk: (settings) => resolve(jsonResponse(200, settings)),
          // A real backend error body, which must never reach the user.
          resolveError: (status) => resolve(jsonResponse(status, { detail: 'INTERNAL-DETAIL' })),
        });
      });
    }),
  );

  return entries;
}

const renderPage = () =>
  render(
    <SettingsProvider>
      <SettingsPage onNavigate={() => {}} />
    </SettingsProvider>,
  );

const combobox = (): HTMLSelectElement =>
  screen.getByRole('combobox') as HTMLSelectElement;

const radios = (): HTMLInputElement[] =>
  screen.getAllByRole('radio') as HTMLInputElement[];

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('SettingsPage honesty', () => {
  it('shows the authenticated identity and never a placeholder', async () => {
    const entries = installFetchMock();
    renderPage();

    await act(async () => {
      entries[0].resolveOk(serverDefaults());
    });

    expect(screen.getByText('Ada Lovelace')).toBeDefined();
    expect(screen.getByText('ada@example.com')).toBeDefined();
    expect(screen.queryByText('user@documind.io')).toBeNull();
    expect(screen.queryByText(/Level 3/)).toBeNull();
    expect(screen.queryByText(/Analyst/)).toBeNull();
  });

  it('renders the settings the server actually returned', async () => {
    const entries = installFetchMock();
    renderPage();

    await act(async () => {
      entries[0].resolveOk({
        processingDepth: 5,
        contextWindow: 'session',
        theme: 'dark-cyber',
        density: 'standard',
        glassIntensity: 42,
      });
    });

    expect(screen.getByText('Comprehensive')).toBeDefined();
    expect(screen.getByText('42% Blur Active')).toBeDefined();
    expect(combobox().value).toBe('session');
    expect(radios()[0].checked).toBe(true);
  });

  it('never presents an unimplemented security feature as active', async () => {
    const entries = installFetchMock();
    renderPage();

    await act(async () => {
      entries[0].resolveOk(serverDefaults());
    });

    expect(screen.queryByText('ACTIVE')).toBeNull();
    expect(screen.queryByText('STANDBY')).toBeNull();
    expect(screen.queryByText('AES-256-GCM')).toBeNull();
    expect(screen.getAllByText('NOT IMPLEMENTED')).toHaveLength(2);

    const twoFactor = screen.getByTitle('Two-factor authentication is not implemented');
    const e2e = screen.getByTitle('End-to-end encryption is not implemented');
    expect((twoFactor as HTMLButtonElement).disabled).toBe(true);
    expect((e2e as HTMLButtonElement).disabled).toBe(true);
  });

  it('does not claim success until the server confirms the save', async () => {
    const entries = installFetchMock();
    renderPage();

    await act(async () => {
      entries[0].resolveOk(serverDefaults());
    });

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /apply configuration/i }));
    });

    expect(entries).toHaveLength(2);
    expect(entries[1].method).toBe('PATCH');
    expect(entries[1].url).toContain('/api/settings');
    expect(entries[1].body).toMatchObject({
      processingDepth: 3,
      contextWindow: 'persistent',
      theme: 'dark-cyber',
      density: 'high',
      glassIntensity: 70,
    });
    // Still pending: the page must not have claimed anything was stored.
    expect(screen.queryByText(/saved to the server/i)).toBeNull();

    await act(async () => {
      entries[1].resolveOk({ ...serverDefaults(), glassIntensity: 55 });
    });

    expect(screen.getByText(/saved to the server/i)).toBeDefined();
    expect(screen.getByText('55% Blur Active')).toBeDefined();
  });

  it('reports a failed save honestly instead of claiming success', async () => {
    const entries = installFetchMock();
    renderPage();

    await act(async () => {
      entries[0].resolveOk(serverDefaults());
    });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /apply configuration/i }));
    });
    await act(async () => {
      entries[1].resolveError(500);
    });

    expect(screen.queryByText(/saved to the server/i)).toBeNull();
    const alert = screen.getByRole('alert');
    expect(alert.textContent).toContain('not persisted');
    expect(alert.textContent).not.toContain('INTERNAL-DETAIL');
  });

  it('reports an unavailable load instead of showing invented state', async () => {
    const entries = installFetchMock();
    renderPage();

    await act(async () => {
      entries[0].resolveError(500);
    });

    const alert = screen.getByRole('alert');
    expect(alert.textContent).toContain('Could not load your saved settings');
    expect(alert.textContent).not.toContain('INTERNAL-DETAIL');
    expect(screen.queryByText('ACTIVE')).toBeNull();
    expect(screen.getAllByText('NOT IMPLEMENTED')).toHaveLength(2);
  });

  it('discards unapplied edits and never sends them to the server', async () => {
    const entries = installFetchMock();
    renderPage();

    await act(async () => {
      // The server reports a non-default context window.
      entries[0].resolveOk({ ...serverDefaults(), contextWindow: '24h' });
    });
    expect(combobox().value).toBe('24h');

    await act(async () => {
      fireEvent.change(combobox(), { target: { value: 'session' } });
    });
    expect(combobox().value).toBe('session');

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /discard changes/i }));
    });

    expect(combobox().value).toBe('24h');
    // Only the initial GET ever reached the server.
    expect(entries).toHaveLength(1);
    expect(screen.queryByText(/saved to the server/i)).toBeNull();
  });
});
