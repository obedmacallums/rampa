# Quickstart Validation — Visual Foundation of the Application (003)

Prerequisites: node ≥ 20 in `frontend/`, docker compose stack from
`infra/docker-compose.yml`, demo users (`demo/demo1234`, `ana/ana12345`).

## 1. Static checks (fast loop, no docker)

```sh
cd frontend
npx tsc --noEmit                                  # expect exit 0
npm test                                          # expect all tests pass (i18n + confirm-dialog)
ESLINT_USE_FLAT_CONFIG=false npx eslint src       # expect exit 0 (flat-config issue is pre-existing)
```

Backend regression evidence (nothing should change):

```sh
cd backend && python -m pytest tests/             # expect same pass count as before the feature
```

## 2. Deployed visual validation

Images do not mount code — rebuild first:

```sh
docker compose -f infra/docker-compose.yml build frontend
docker compose -f infra/docker-compose.yml up -d
```

Open `http://localhost:8080` and walk the scenarios below. Do one pass at a
normal window and one with the window sized to 1280×720 (SC-005, FR-012).

### US1 — Shell (P1)

1. Login page: dark theme, wordmark, styled form; wrong password shows a
   styled alert in the current language.
2. After login: persistent header on every page with wordmark, username,
   sign-out, and ES/EN switcher; switching language updates all visible
   texts immediately and survives a reload (localStorage).
3. Tab through a page: every interactive element shows the amber focus ring.

### US2 — Working screens (P2)

1. Account with no projects → styled empty state with create CTA.
2. Create a project via the styled form; list shows styled entries.
3. Upload a survey: styled progress bar with percent; interrupt and re-select
   the file → resumable notice styled.
4. Survey table: status badges colored queued/processing/completed/failed
   with visible stage while processing; retry button on failures.
5. Members: add ana; removing her opens the styled ConfirmDialog (no native
   popup); cancel keeps her, confirm removes her.

### US3 — Viewers (P3)

1. Open the 2D map of a completed survey → full-viewport overlay; basemap and
   survey-layer selectors float over the map and keep all options working;
   close button and `Esc` return to the detail page with its state intact.
2. Open the 3D view → full-viewport overlay, styled loading indicator, close
   works. Force an error (e.g., expired artifacts) → styled alert.

## 3. Acceptance gates

- SC-001: zero screens/dialogs with browser-default styling (including
  `window.confirm` — must be gone from `src/`: `grep -r "window.confirm" src` empty).
- SC-002/SC-003: all flows behave identically; full frontend + backend suites
  green (outputs shown, not asserted from memory).
- SC-004: spot-check contrast of body text on `#18181b`/`#27272a` and amber
  buttons with a contrast checker → AA.
- SC-006: language switch leaves no untranslated string on any redesigned
  screen (walk both languages).
