# Research — Visual Foundation of the Application (003)

All Technical Context unknowns resolved. Decisions below.

## R1. Tailwind CSS version and integration

- **Decision**: Tailwind CSS v4 with the first-party Vite plugin
  (`@tailwindcss/vite`). Design tokens defined in CSS via the v4 `@theme`
  block in `frontend/src/index.css`; no `tailwind.config.js` needed.
- **Rationale**: v4 is the current major; the Vite plugin needs zero PostCSS
  config and the CSS-first `@theme` syntax makes the tokens live in one file
  next to the styles that use them. Build output only includes used
  utilities, keeping the bundle small. Works unchanged inside the docker
  frontend image (`npm run build` during image build).
- **Alternatives considered**: Tailwind v3 + PostCSS (older config style, no
  benefit); plain CSS custom properties + hand-written classes (slower to
  apply consistently across ~10 screens/components, easy to drift); CSS
  Modules (same drift risk, more files).

## R2. Component strategy

- **Decision**: Hand-rolled primitives in `frontend/src/ui/` styled with
  Tailwind utilities. The confirmation dialog uses the native `<dialog>`
  element (`showModal()`), which provides focus trapping, `Esc` dismissal,
  and a backdrop pseudo-element for free.
- **Rationale**: The inventory is small (~10 primitives) and the user chose
  a utility-first approach over a component library; native `<dialog>`
  avoids a headless-UI dependency while meeting the keyboard/focus edge
  cases in the spec. jsdom supports `HTMLDialogElement` well enough for
  vitest behavior tests.
- **Alternatives considered**: Radix UI / Headless UI (extra dependency for
  one dialog and a menu — not justified at this scale); Mantine (rejected by
  the user in favor of Tailwind).

## R3. Typography and iconography

- **Decision**: System UI font stack (no webfonts); no icon library —
  the few needed glyphs (close ×, chevrons, status dots) are inline SVG or
  text glyphs inside the primitives.
- **Rationale**: Demo-first constitution constraint — the app must work with
  no external network dependencies, and the nginx image should not grow with
  font assets for a provisional identity. System stacks render well on the
  target desktop platforms.
- **Alternatives considered**: Self-hosted Inter (deferred until definitive
  branding); lucide-react icons (nice-to-have, can be added later without
  rework because icons live inside primitives).

## R4. "Mining amber" palette (dark theme)

- **Decision**: Neutral dark grays (zinc-scale: page `#18181b`, surfaces
  `#27272a`, borders `#3f3f46`, body text `#d4d4d8`, headings `#fafafa`)
  with amber accent (`#f59e0b` base, `#fbbf24` hover, dark text `#1c1917`
  on amber fills). Semantic status colors reserved and distinct from the
  accent: queued = neutral gray, processing = blue `#60a5fa`, completed =
  green `#4ade80`, failed = red `#f87171`; warning yellow (future semaphore)
  stays a paler yellow `#facc15` used only in status contexts.
- **Rationale**: Matches the clarified "mining amber" identity; amber-on-dark
  and dark-on-amber both clear WCAG AA for the sizes used; blue for
  "processing" keeps green/yellow/red free for the future compliance
  semaphore and avoids amber/yellow confusion by pairing color with label
  text in every badge (never color alone).
- **Alternatives considered**: Amber also for "processing" (rejected —
  collides with accent); pure black background (rejected — harsher contrast,
  worse layering against map tiles).

## R5. Viewer overlay pattern

- **Decision**: `ViewerOverlay` renders a `position: fixed; inset: 0`
  container above the app shell (below any dialog), with a floating close
  button and a slot for map-overlay controls. Viewers keep mounting only
  while open (current conditional-render behavior in `ProjectDetailPage`),
  so MapLibre/Potree size themselves correctly on mount; `Esc` also closes.
  Project-detail state survives because the page stays mounted underneath.
- **Rationale**: Meets the clarified full-viewport decision with no route
  changes and no viewer lifecycle changes; establishes the surface the
  future axis-drawing tools will extend.
- **Alternatives considered**: Native `<dialog>` for the overlay (rejected:
  its top-layer stacking complicates MapLibre popups/controls and the
  future drawing toolbars); dedicated route (rejected in clarification).

## R6. Language switcher

- **Decision**: Visible es/en switcher in the header calling
  `i18n.changeLanguage`, persisting the choice to `localStorage`
  (`rampa.lang`) and restoring it at i18n bootstrap; default stays `es`.
- **Rationale**: The spec requires a visible switcher; today `lng: "es"` is
  hard-fixed. Persistence is presentation-level state, allowed by FR-010.
- **Alternatives considered**: Browser-language auto-detection
  (i18next-browser-languagedetector) — deferred; explicit user choice is
  more predictable for shared field laptops.

## R7. Verification approach

- **Decision**: Evidence chain per FR-010 / SC-003: `tsc --noEmit`,
  `npm test` (i18n parity + new ConfirmDialog test), eslint via
  `ESLINT_USE_FLAT_CONFIG=false npx eslint src` (repo's flat-config issue is
  pre-existing), backend `pytest tests/` unchanged, then docker rebuild
  (`docker compose -f infra/docker-compose.yml build frontend && up -d`) and
  a manual walkthrough of every flow at 1280×720 with the demo credentials.
- **Rationale**: Matches the project's verification-before-completion rule
  and the docker images-don't-mount-code constraint.
- **Alternatives considered**: Playwright visual regression (overkill for a
  first design pass; can be introduced when the UI stabilizes).
