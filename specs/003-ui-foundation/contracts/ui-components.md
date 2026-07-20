# UI Contracts — Visual Foundation of the Application (003)

**No REST API contract changes.** The frontend keeps calling exactly the
endpoints and payloads defined in `specs/001-survey-ingest/contracts/rest-api.md`
and `specs/002-project-authorization/contracts/` (FR-010). This document
contracts the reusable UI primitives and the i18n key additions instead.

## Component contracts (`frontend/src/ui/`)

### Button

```ts
type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "danger"; // default "primary"
};
```

- `primary`: amber fill, dark text. `secondary`: neutral surface, border.
  `danger`: red fill/border for destructive actions.
- Must render a real `<button>`; disabled state visually distinct; visible
  focus ring (FR-004).

### Field

```ts
type FieldProps = {
  label: string;            // already-translated text
  error?: string | null;    // already-translated; renders under the control
  children: React.ReactNode; // the input/select element
  htmlFor?: string;
};
```

- Associates label and control; error text uses the failed-status color and
  is announced politely (`role="alert"` preserved where it exists today).

### Table / Th / Td

- Thin wrappers adding the dark-theme table styling (header surface, row
  borders, row hover). No sorting/pagination logic — presentation only.

### ConfirmDialog

```ts
type ConfirmDialogProps = {
  open: boolean;
  message: string;          // already-translated
  confirmLabel: string;     // e.g. t("members.remove")
  cancelLabel: string;      // t("common.cancel")
  onConfirm: () => void;
  onCancel: () => void;
};
```

- Implemented on native `<dialog>` + `showModal()`: focus trapped, `Esc`
  cancels, backdrop dims the page. Confirm button uses `danger` variant.
- Replaces every `window.confirm` call (today: member removal in
  `ProjectMembers.tsx`). No native browser popups may remain (SC-001).

### Badge

```ts
type BadgeProps = { status: "queued" | "processing" | "completed" | "failed"; label: string };
```

- Color per status token; always shows the translated label next to the
  color (never color alone).

### ProgressBar

```ts
type ProgressBarProps = { percent: number }; // 0–100, determinate
```

### EmptyState

```ts
type EmptyStateProps = { message: string; action?: React.ReactNode };
```

### Alert

```ts
type AlertProps = { kind?: "error" | "info"; children: React.ReactNode }; // default "error"
```

- Keeps `role="alert"` semantics used by existing screens.

### LanguageSwitcher

- Renders the two options `ES` / `EN`; current language visually active;
  clicking calls `i18n.changeLanguage` and persists to
  `localStorage["rampa.lang"]`. Lives in the app header on every screen.

### ViewerOverlay

```ts
type ViewerOverlayProps = {
  title: string;             // survey name or viewer title
  onClose: () => void;
  controls?: React.ReactNode; // rendered as floating controls over the canvas
  children: React.ReactNode;  // the viewer itself, must fill the container
};
```

- `position: fixed; inset: 0`, above the app shell; visible close button and
  `Esc` both call `onClose`; the page underneath stays mounted (US3
  scenario 3). Hosts Map2D's basemap/layer selectors in `controls`.

## Behavioral invariants (regression contract)

1. Every user flow of specs 001/002 works identically after restyle: login,
   project CRUD-lite, upload (tus resume included), status polling, retry,
   members management, artifact viewing.
2. `SurveyStatus` polling, `UploadWidget` tus wiring, and store logic are
   not modified — only their rendered markup/classes.
3. `Map2D` keeps its props (`tilejsonUrl`, `demTilejsonUrl`,
   `demStatisticsUrl`), its layer/basemap logic, and its fetch behavior; only
   control placement/styling changes.
4. Existing test `frontend/tests/i18n.test.ts` passes unmodified.

## i18n additions (both `es/common.json` and `en/common.json`)

| Key | es | en |
|---|---|---|
| `common.cancel` | "Cancelar" | "Cancel" |
| `common.close` | "Cerrar" | "Close" |
| `common.language` | "Idioma" | "Language" |
| `nav.projects` | "Proyectos" | "Projects" |
| `viewer.close` | "Cerrar visor" | "Close viewer" |

(Exact final list may grow during implementation; the contract is: every new
visible string ships in both catalogs in the same change — Principle IX.)
