import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

/**
 * Frontend test configuration.
 *
 * Deliberately separate from `vite.config.ts`: the dev-server proxy / CORS
 * behaviour and the production build stay untouched by test setup.
 *
 * `jsdom` supplies the DOM the components need; everything the components
 * touch that jsdom does not implement (`Audio`, `URL.createObjectURL`) is
 * stubbed per test file, so no network or real audio device is involved.
 */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
    restoreMocks: true,
  },
});
