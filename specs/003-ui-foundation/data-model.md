# Data Model — Visual Foundation of the Application (003)

This feature persists no data and adds no entities, migrations, or API
shapes. Its "model" is the design-token vocabulary and the UI component
inventory that every screen consumes. The only stored value is the language
preference (`localStorage["rampa.lang"]`, `"es" | "en"`).

## Design tokens (defined once in `frontend/src/index.css` via `@theme`)

### Color

| Token | Value | Use |
|---|---|---|
| `--color-surface-0` | `#18181b` | Page background |
| `--color-surface-1` | `#27272a` | Cards, table headers, header bar |
| `--color-surface-2` | `#3f3f46` | Hover surfaces, borders |
| `--color-text` | `#d4d4d8` | Body text |
| `--color-text-strong` | `#fafafa` | Headings, emphasized values |
| `--color-text-muted` | `#a1a1aa` | Secondary text, captions |
| `--color-accent` | `#f59e0b` | Brand accent, primary buttons, focus ring, links |
| `--color-accent-hover` | `#fbbf24` | Accent hover state |
| `--color-on-accent` | `#1c1917` | Text on amber fills |
| `--color-status-queued` | `#a1a1aa` | Badge: queued |
| `--color-status-processing` | `#60a5fa` | Badge: processing |
| `--color-status-completed` | `#4ade80` | Badge: completed |
| `--color-status-failed` | `#f87171` | Badge: failed, danger buttons, error alerts |
| `--color-status-warning` | `#facc15` | Reserved: warnings / future semaphore yellow |

Rules: amber is never used for statuses; green/yellow/red are never used for
brand or interaction accents; badges always pair color with a text label
(never color alone).

### Typography & spacing

- Font: system UI stack; sizes restricted to Tailwind's `text-xs`…`text-2xl`
  steps; page titles `text-2xl/semibold`, section titles `text-lg/semibold`.
- Spacing: Tailwind default 4px scale; content max width `max-w-5xl`
  (detail) / `max-w-3xl` (lists, forms); page padding `p-6`.
- Radius: `rounded-md` for controls, `rounded-lg` for cards/dialogs.
- Focus: 2px amber ring (`outline-color: --color-accent`) on every
  interactive element (FR-004).

## UI component inventory (`frontend/src/ui/`)

| Component | States | Consumed by |
|---|---|---|
| `Button` (`primary` \| `secondary` \| `danger`) | default / hover / focus / disabled | all pages, dialogs |
| `Field` (label + input/select slot + error text) | default / focus / invalid | Login, ProjectsPage form, UploadWidget, ProjectMembers add |
| `Table` (+`Th`/`Td` helpers) | default / row hover / empty | ProjectDetailPage surveys, ProjectMembers |
| `ConfirmDialog` | closed / open (focus-trapped) | ProjectMembers removal (replaces `window.confirm`) |
| `Badge` (`queued` \| `processing` \| `completed` \| `failed`) | static | SurveyStatus |
| `ProgressBar` (0–100) | determinate | UploadWidget |
| `EmptyState` (message + optional CTA) | static | ProjectsPage, surveys table, PendingUploads |
| `Alert` (`error` \| `info`) | static, `role="alert"` kept | all forms, viewer errors |
| `LanguageSwitcher` (es/en) | current-language highlighted | App header |
| `ViewerOverlay` (children + controls slot + close) | open / closing via button or `Esc` | Map2D, Cloud3D from ProjectDetailPage |

## State transitions

- `ViewerOverlay`: `closed → open` (user opens viewer) → `closed` (close
  button, `Esc`); underlying `ProjectDetailPage` never unmounts (spec US3
  scenario 3).
- `ConfirmDialog`: `closed → open` (destructive action requested) →
  `confirmed` (runs action) | `cancelled`; both return focus to the
  triggering element.
- Language: `es ⇄ en`, persisted to `localStorage`, applied at bootstrap.
