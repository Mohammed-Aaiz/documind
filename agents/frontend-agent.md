# FRONTEND_AGENT

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
