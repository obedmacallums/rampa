# Implementation Plan: Visual Foundation of the Application

**Branch**: `003-ui-foundation` | **Date**: 2026-07-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-ui-foundation/spec.md`

## Summary

Give the frontend a coherent visual foundation without changing any behavior:
a small design system (dark theme, "mining amber" palette, typography and
spacing tokens) built with Tailwind CSS v4, a set of reusable UI primitives
(buttons, fields, table, confirm dialog, badges, progress bar, empty states,
alerts), a persistent application shell (header with wordmark, user menu,
language switcher), and a full-viewport overlay frame for the 2D/3D viewers
with their controls integrated over the map. All existing screens are
restyled; no API, route, store, or backend change.

## Technical Context

**Language/Version**: TypeScript 5.7 / React 18.3 (existing frontend)

**Primary Dependencies**: Vite 6, Tailwind CSS v4 (`tailwindcss` +
`@tailwindcss/vite`, new), react-i18next 15, react-router-dom 7, Zustand 5,
MapLibre GL 5, Potree (vendored). No component library — UI primitives are
hand-rolled on Tailwind utilities; the confirm dialog uses the native
`<dialog>` element.

**Storage**: N/A (no data changes; language preference in `localStorage`)

**Testing**: vitest 2 + jsdom (existing `tests/i18n.test.ts` must keep
passing; new tests for ConfirmDialog behavior and i18n key parity of new
keys). Backend pytest suite untouched but re-run as regression evidence.

**Target Platform**: Desktop browsers (Chrome/Firefox/Safari), viewports from
1280×720 upward; served by the existing nginx frontend image on :8080.

**Project Type**: Web application — this feature touches `frontend/` only.

**Performance Goals**: No regression in viewer interactivity (Principle II);
CSS bundle stays small (Tailwind emits only used utilities); no external
network requests introduced (fonts/icons self-contained, demo-first).

**Constraints**: Zero behavioral change (FR-010); all texts through i18n
es/en (Principle IX); WCAG AA contrast on dark theme; semantic
green/yellow/red reserved for statuses, amber reserved for brand accent;
docker image rebuild required to see changes (images do not mount code).

**Scale/Scope**: 3 pages, 4 feature components, 2 viewers, 1 app shell,
~10 new UI primitives, ~15 new i18n keys per language.

## Constitution Check

*GATE: evaluated against constitution v1.3.0 before Phase 0; re-checked after
Phase 1 design — PASS (no violations).*

| Principle | Verdict | Notes |
|---|---|---|
| I. Analysis on rasters | N/A | No analysis code touched. |
| II. Thin backend, interactive frontend | PASS | Frontend-only; no new backend calls; viewer interactivity (basemap/layer switching client-side) preserved unchanged. |
| III. Async ingestion | N/A | Pipeline untouched. |
| IV. Station-based model | N/A | No analysis entities. |
| V. Assisted detection | N/A | — |
| VI. Evaluation profiles as data | PASS | No thresholds introduced; semantic colors are presentation tokens, not compliance rules. |
| VII. Reproducible reports | N/A | — |
| VIII. Test-first analysis core | N/A | No analysis library code; frontend tests still required to pass (FR-010). |
| IX. Bilingual by design | PASS | Every new visible text (dialog buttons, empty-state CTAs, viewer close, language switcher labels) added to es/en catalogs; no hard-coded strings. |
| X. Mining focus, neutral core | PASS | "Mining amber" identity is presentation-only; no domain rules in code. |
| XI. AI as isolated service | N/A | — |
| Tech constraints | PASS | Stack additions limited to Tailwind (build-time dev dependency); multi-arch docker build unaffected (`npm run build` inside image); demo-first preserved (no external assets). |

**Gate note**: Tailwind CSS is an addition to the constitution's named
frontend stack (React + TypeScript + Zustand + MapLibre + Potree). It is a
build-time styling tool, not a runtime framework substitution, so it does not
contradict any principle; recorded here for transparency.

## Project Structure

### Documentation (this feature)

```text
specs/003-ui-foundation/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (design tokens + component inventory)
├── quickstart.md        # Phase 1 output (validation guide)
├── contracts/
│   └── ui-components.md # Phase 1 output (UI component + i18n contracts)
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
frontend/
├── index.html                    # (touch) fonts/meta if needed; title unchanged
├── package.json                  # (modify) + tailwindcss, @tailwindcss/vite
├── vite.config.ts                # (modify) register Tailwind plugin
├── src/
│   ├── index.css                 # (new) Tailwind entry + @theme design tokens
│   ├── main.tsx                  # (modify) import "./index.css"
│   ├── App.tsx                   # (modify) app shell: header, nav, user menu
│   ├── ui/                       # (new) reusable primitives
│   │   ├── Button.tsx
│   │   ├── Field.tsx             # label + input/select + error slot
│   │   ├── Table.tsx
│   │   ├── ConfirmDialog.tsx     # native <dialog>, replaces window.confirm
│   │   ├── Badge.tsx             # semantic status badge
│   │   ├── ProgressBar.tsx
│   │   ├── EmptyState.tsx
│   │   ├── Alert.tsx
│   │   ├── LanguageSwitcher.tsx
│   │   └── ViewerOverlay.tsx     # full-viewport overlay frame + close
│   ├── pages/
│   │   ├── LoginPage.tsx         # (modify) restyle
│   │   ├── ProjectsPage.tsx      # (modify) restyle + empty state + card list
│   │   └── ProjectDetailPage.tsx # (modify) restyle + viewers via ViewerOverlay
│   ├── components/
│   │   ├── PendingUploads.tsx    # (modify) restyle
│   │   ├── ProjectMembers.tsx    # (modify) restyle + ConfirmDialog
│   │   ├── SurveyStatus.tsx      # (modify) Badge-based
│   │   └── UploadWidget.tsx      # (modify) restyle + ProgressBar
│   ├── viewers/
│   │   ├── Map2D.tsx             # (modify) overlay controls on map
│   │   └── Cloud3D.tsx           # (modify) styled loading/error states
│   └── i18n/
│       ├── es/common.json        # (modify) new keys
│       └── en/common.json        # (modify) new keys
└── tests/
    ├── i18n.test.ts              # (existing) must keep passing
    └── confirm-dialog.test.tsx   # (new) dialog behavior
```

**Structure Decision**: Web application layout already in place; this feature
adds a `frontend/src/ui/` primitives directory and a single global stylesheet
`frontend/src/index.css`, and modifies existing pages/components in place. No
backend paths are touched.

## Complexity Tracking

No constitution violations — table not required.
