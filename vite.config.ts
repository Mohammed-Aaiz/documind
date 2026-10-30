import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// A loopback backend URL.  When the dev client is pointed at one of these it
// reaches the SAME local FastAPI the Vite proxy already targets, but it does so
// cross-origin — which forces a CORS preflight on every call.
const LOOPBACK_API = /^https?:\/\/(?:localhost|127\.0\.0\.1|\[::1\])(?::\d+)?$/;

// https://vitejs.dev/config/
export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const configuredApiBase = (env.VITE_API_BASE_URL ?? '').trim();

  // Local dev must talk to the Vite dev server and let `/api` be proxied to
  // FastAPI (same origin).  The backend's CORS allowlist is an exact-match
  // origin list and must stay closed, so a direct cross-origin call breaks the
  // moment the browser's origin is not byte-identical to an allowlisted entry
  // (classically a dev server that drifted off port 3000, or localhost vs
  // 127.0.0.1).  Starlette's CORSMiddleware then answers the preflight with
  // "400 Disallowed CORS origin" and the browser never sends the real request.
  //
  // Routing through the proxy removes CORS from the local path entirely, so no
  // preflight is issued and the allowlist never has to be widened.  A
  // non-loopback value (a deliberately remote API) is respected untouched, and
  // production/Docker builds are unaffected (this only applies to `vite` serve
  // in development mode).
  const forceSameOrigin =
    command === 'serve' &&
    mode === 'development' &&
    (configuredApiBase === '' || LOOPBACK_API.test(configuredApiBase));

  return {
    plugins: [react()],
    define: forceSameOrigin
      ? { 'import.meta.env.VITE_API_BASE_URL': JSON.stringify('') }
      : {},
    server: {
      port: 3000,
      // Fail loudly instead of silently auto-incrementing to 3001, 3002, ...
      // The backend's CORS allowlist is an exact-match origin list (config.py
      // _LOCAL_DEV_ORIGINS: 3000 / 5173 / 4173), so a drifting dev server lands
      // on an unlisted origin and every API preflight fails with
      // "400 Disallowed CORS origin".  The CORS allowlist is security-relevant
      // and must not be widened to paper over a port mismatch.
      strictPort: true,
      open: true,
      watch: {
        ignored: ['**/backend/**'], // <-- Added this to prevent the scandir crash
      },
      proxy: {
        '/api': {
          // Pinned to IPv4: the backend runs on 0.0.0.0:8000 (IPv4), while the
          // dev server may bind only IPv6 loopback.  A bare `localhost` target
          // can resolve to ::1 and be refused (the intermittent WinError 10054
          // / ECONNREFUSED class of failure).
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
      },
    },
  };
});