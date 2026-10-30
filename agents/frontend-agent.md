# FRONTEND_AGENT

> **2026-10-27 rebuild:** Student/Research are modes inside the existing Workspace
> page. Follow the current design decision at the start of `DESIGN.md`, including
> separate active-chat/draft state, request cancellation and microphone cleanup on
> mode changes. Server-side workspace authorization is required in addition to UI
> filtering. Backend persists successful conversation messages; do not double-save.

## Role

React/TypeScript UI and user interaction.

## Owns

-   `src/**`
-   `index.html`
-   `vite.config.ts`
-   `tailwind.config.js`
-   `tsconfig.json`
-   `postcss.config.js`
-   `package.json`

## Must Not Touch

`backend/**`, `.env`, `dist/**`.

## Rules

Use `src/lib/api.ts`. Mirror real backend state. Never hardcode backend
results. Preserve the five-page information architecture. Handle
loading, empty, unavailable, error and success states. Maintain
accessibility.

## Verify

``` bash
npm run build
```
