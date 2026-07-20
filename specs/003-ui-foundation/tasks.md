# Tasks: Visual Foundation of the Application

**Input**: Design documents from `/specs/003-ui-foundation/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ui-components.md, quickstart.md

**Tests**: Included where the plan demands them (ConfirmDialog behavior test; existing `tests/i18n.test.ts` is a hard regression gate per FR-010). No backend tests are added — the backend is untouched.

**Organization**: Tasks are grouped by user story so each story is an independently verifiable increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

## Path Conventions

Web app — this feature only touches `frontend/`. All paths are repo-relative.

---

## Phase 1: Setup (Tailwind toolchain)

**Purpose**: Install and wire the styling toolchain so utilities and tokens are available everywhere.

- [X] T001 Install `tailwindcss` and `@tailwindcss/vite` as devDependencies in frontend/package.json (npm install -D)
- [X] T002 Register the Tailwind plugin in frontend/vite.config.ts
- [X] T003 Create frontend/src/index.css with the `@import "tailwindcss"` entry plus the `@theme` design tokens from data-model.md (mining-amber palette, status colors, focus ring), set the dark page/body base styles, and import "./index.css" in frontend/src/main.tsx

**Checkpoint**: `npx tsc --noEmit` and `npm run build` succeed; app renders unchanged except base dark background.

---

## Phase 2: Foundational (shared primitives)

**Purpose**: Primitives and i18n keys consumed by more than one story. Blocks all user stories.

- [X] T004 [P] Create Button primitive (`primary`/`secondary`/`danger`, focus ring, disabled state) in frontend/src/ui/Button.tsx per contracts/ui-components.md
- [X] T005 [P] Create Field primitive (label + control slot + error text) in frontend/src/ui/Field.tsx
- [X] T006 [P] Create Alert primitive (`error`/`info`, keeps `role="alert"`) in frontend/src/ui/Alert.tsx
- [X] T007 Add shared i18n keys (`common.cancel`, `common.close`, `common.language`, `nav.projects`) to frontend/src/i18n/es/common.json and frontend/src/i18n/en/common.json

**Checkpoint**: primitives compile and are importable; `npm test` still green (i18n parity).

---

## Phase 3: User Story 1 - Consistent application shell and visual identity (Priority: P1) 🎯 MVP

**Goal**: Dark theme, persistent header (wordmark, user, sign-out, ES/EN switcher), consistent layout on every page, styled login.

**Independent Test**: Sign in and browse every page: header persists with all elements, language switch works and survives reload, all pages share theme/width/spacing, focus ring visible on tab. (quickstart.md §US1)

### Implementation for User Story 1

- [X] T008 [P] [US1] Create LanguageSwitcher (ES/EN, calls `i18n.changeLanguage`, persists to `localStorage["rampa.lang"]`, active language highlighted) in frontend/src/ui/LanguageSwitcher.tsx
- [X] T009 [P] [US1] Restore persisted language at bootstrap (read `localStorage["rampa.lang"]`, fallback "es") in frontend/src/i18n/index.ts
- [X] T010 [US1] Rebuild the app shell in frontend/src/App.tsx: dark layout container, persistent header with wordmark (app.title), projects nav link, username display, sign-out Button, and LanguageSwitcher; consistent content max-width/padding wrapper for routed pages (depends on T008)
- [X] T011 [US1] Restyle frontend/src/pages/LoginPage.tsx with product identity (wordmark), Field/Button primitives and Alert for errors — behavior unchanged

**Checkpoint**: US1 fully verifiable per quickstart §US1; existing flows intact.

---

## Phase 4: User Story 2 - Styled working screens: projects, surveys, upload, members (Priority: P2)

**Goal**: Styled tables, forms, badges, progress, empty states, and a real confirmation dialog across the projects/detail screens.

**Independent Test**: With a fresh account: projects empty state → create project → surveys empty state → upload with styled progress → badges through pipeline states → member add/remove with styled ConfirmDialog. (quickstart.md §US2)

### Tests for User Story 2

> Write first; it must fail until T017 exists.

- [X] T012 [P] [US2] Behavior test for ConfirmDialog (opens via `showModal`, Esc cancels, confirm/cancel callbacks fire, no `window.confirm` involved) in frontend/tests/confirm-dialog.test.tsx

### Implementation for User Story 2

- [X] T013 [P] [US2] Create Badge primitive (status → token color + translated label, never color alone) in frontend/src/ui/Badge.tsx
- [X] T014 [P] [US2] Create ProgressBar primitive (determinate 0–100) in frontend/src/ui/ProgressBar.tsx
- [X] T015 [P] [US2] Create EmptyState primitive (message + optional CTA slot) in frontend/src/ui/EmptyState.tsx
- [X] T016 [P] [US2] Create Table/Th/Td primitives (dark header surface, row borders/hover) in frontend/src/ui/Table.tsx
- [X] T017 [US2] Create ConfirmDialog on native `<dialog>` (focus trap, Esc cancels, danger confirm Button, backdrop) in frontend/src/ui/ConfirmDialog.tsx — makes T012 pass
- [X] T018 [US2] Restyle frontend/src/pages/ProjectsPage.tsx: styled create form (Field/Button), styled project list entries, EmptyState with create CTA, Alert for errors
- [X] T019 [US2] Restyle frontend/src/components/SurveyStatus.tsx to render pipeline states with Badge (stage text kept visible while processing) — polling logic untouched
- [X] T020 [US2] Restyle frontend/src/components/UploadWidget.tsx with Field/Button and ProgressBar; interrupted/done notices via Alert — tus wiring untouched
- [X] T021 [US2] Restyle frontend/src/components/PendingUploads.tsx (styled pending list / notice, EmptyState-consistent)
- [X] T022 [US2] Restyle frontend/src/components/ProjectMembers.tsx and replace `window.confirm` with ConfirmDialog (uses `members.remove_confirm`, `common.cancel`) — API calls untouched
- [X] T023 [US2] Restyle frontend/src/pages/ProjectDetailPage.tsx: section layout, surveys Table with EmptyState, styled action Buttons — viewer opening logic untouched (US3 restyles the viewers themselves)

**Checkpoint**: US1 + US2 verifiable; `npm test` green including confirm-dialog test; `grep -r "window.confirm" frontend/src` empty.

---

## Phase 5: User Story 3 - Viewers as protagonists (Priority: P3)

**Goal**: 2D/3D viewers open as full-viewport overlays with close (button + Esc), Map2D controls float over the map, styled loading/error states.

**Independent Test**: Open 2D and 3D viewers of a completed survey: overlay fills the window, controls float on the map and keep working, close/Esc returns to the intact detail page. (quickstart.md §US3)

### Implementation for User Story 3

- [X] T024 [P] [US3] Add viewer i18n keys (`viewer.close`) to frontend/src/i18n/es/common.json and frontend/src/i18n/en/common.json
- [X] T025 [US3] Create ViewerOverlay (fixed inset-0 above shell, title, close button, Esc handler, floating `controls` slot) in frontend/src/ui/ViewerOverlay.tsx per contracts/ui-components.md
- [X] T026 [US3] Integrate viewers through ViewerOverlay in frontend/src/pages/ProjectDetailPage.tsx (conditional render preserved so the page and its state stay mounted underneath; close resets `viewer` state)
- [X] T027 [US3] Restyle frontend/src/viewers/Map2D.tsx: render basemap and survey-layer selectors as floating overlay controls on the map (styled selects/segmented controls); map fills the overlay; props, layer logic, and fetch behavior unchanged
- [X] T028 [US3] Restyle frontend/src/viewers/Cloud3D.tsx: styled loading indicator and Alert-based error state; canvas fills the overlay — Potree wiring untouched
- [X] T032 [US3] Single viewer page (user request during implementation): icon-based 2D/3D mode switch in the overlay header in frontend/src/ui/ViewerModeSwitch.tsx, `actions` slot in frontend/src/ui/ViewerOverlay.tsx, one shared overlay in frontend/src/pages/ProjectDetailPage.tsx

**Checkpoint**: all three stories verifiable independently.

---

## Phase 6: Polish & Verification

**Purpose**: Regression evidence per FR-010 / SC-001..SC-006 and the project's verification-before-completion rule.

- [X] T029 [P] Static verification with shown outputs: `npx tsc --noEmit`, `npm test`, `ESLINT_USE_FLAT_CONFIG=false npx eslint src` (all exit 0) and `grep -r "window.confirm" frontend/src` returns nothing
- [X] T030 [P] Backend regression evidence: `python -m pytest tests/` in backend/ with same pass count as before the feature (no backend files modified: `git status backend/` clean)
- [X] T031 Rebuild and validate deployed stack per specs/003-ui-foundation/quickstart.md: `docker compose -f infra/docker-compose.yml build frontend && docker compose -f infra/docker-compose.yml up -d`, then full walkthrough of §US1–US3 at normal size and 1280×720, in both languages, with contrast spot-check (SC-004/SC-005/SC-006)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001 → T002 → T003 (sequential: toolchain before tokens)
- **Foundational (Phase 2)**: needs Phase 1 (utilities available); blocks all stories
- **US1 (Phase 3)**: needs Phase 2 (Button/Field/Alert, keys)
- **US2 (Phase 4)**: needs Phase 2; independent of US1 (touches different screens; App.tsx not modified here)
- **US3 (Phase 5)**: needs Phase 2; T026 and T023 both edit ProjectDetailPage.tsx → run US3 after US2 (or coordinate edits)
- **Polish (Phase 6)**: after all desired stories

### Parallel Opportunities

- Phase 2: T004, T005, T006 in parallel (T007 separate files, also parallel-safe)
- US1: T008 ∥ T009, then T010 → T011
- US2: T012, T013, T014, T015, T016 all in parallel; then T017; then screen restyles T018–T023 (parallel across different files: T018 ∥ T019 ∥ T020 ∥ T021 ∥ T022, T023 last as it consumes Table/EmptyState)
- US3: T024 ∥ T025, then T026 → T027 ∥ T028
- Polish: T029 ∥ T030, then T031

---

## Implementation Strategy

**MVP first (US1)**: Phases 1–3 give a themed, branded app with shell and login — already demoable. Then US2 (daily-work screens), then US3 (viewer overlays). Each checkpoint runs the static checks fresh; the docker walkthrough (T031) closes the feature. Commit per phase or logical group.
