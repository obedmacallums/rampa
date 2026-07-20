# Feature Specification: Visual Foundation of the Application

**Feature Branch**: `003-ui-foundation`

**Created**: 2026-07-19

**Status**: Draft

**Input**: User description: "Base visual de la aplicación (design system + rediseño de las pantallas existentes). Como usuario de Rampa (auditor o topógrafo de faena minera), quiero que la aplicación tenga una interfaz visualmente profesional, consistente y cómoda de usar, para poder trabajar con los levantamientos y visores sin la fricción de una UI sin diseño, y para que las próximas features interactivas (dibujo de ejes sobre el mapa, paneles de evaluación) se construyan sobre una base visual sólida. Alcance: (1) Sistema de diseño mínimo con Tailwind CSS: tokens de color, tipografía y espaciado definidos en la configuración del tema; tema oscuro como tema principal (apropiado para una aplicación GIS donde los visores 2D/3D son protagonistas); estados de foco/hover/disabled consistentes y accesibles. (2) Layout de aplicación: header persistente con marca de la app, navegación, indicador de usuario autenticado con menú (cerrar sesión) y selector de idioma es/en visible; contenido con anchos y márgenes consistentes; los visores 2D y 3D deben poder ocupar el máximo espacio disponible. (3) Componentes base reutilizables estilizados: botones (primario/secundario/peligro), inputs y formularios con etiquetas y errores, tablas, modales/diálogos de confirmación (reemplazando window.confirm), badges de estado del pipeline (en cola/procesando/completado/fallido) con color semántico, barra de progreso de subida, estados vacíos con llamada a la acción, y mensajes de error/alerta. (4) Aplicar el rediseño a todas las pantallas existentes: login, lista de proyectos, creación de proyecto, detalle de proyecto (levantamientos, subida, miembros), y el marco de los visores 2D/3D (los controles de mapa base y capa del levantamiento integrados visualmente sobre el mapa). (5) Sin cambios de funcionalidad, API ni backend: es una feature exclusivamente de presentación; todos los tests existentes deben seguir pasando y los textos siguen viniendo de i18n es/en. Fuera de alcance: pantallas o flujos nuevos, cambios de navegación/rutas, tema claro conmutables, branding definitivo con logo, responsive móvil completo (basta que no se rompa en pantallas de escritorio pequeñas)."

## Context

The platform is functionally complete for ingestion, authorization, and 2D/3D
visualization, but every screen renders as unstyled browser defaults: bare
tables, native buttons, no layout, no visual identity. This feature gives the
application a coherent visual foundation — a small design system applied to
every existing screen — without changing any behavior. It deliberately
precedes the geometric evaluation feature, whose interactive UI (axis drawing
tools, result panels, station tooltips) needs a solid visual base to build on.

## Clarifications

### Session 2026-07-19

- Q: How should the 2D/3D viewers be presented to "occupy the maximum
  available space"? → A: As a full-viewport overlay covering the whole
  window, with a close action returning to the project detail; no route
  changes.
- Q: Which provisional visual identity direction for the dark theme? → A:
  Mining amber — an amber/yellow accent over neutral dark grays, keeping
  green/yellow/red reserved for semantic states (pipeline statuses and the
  future compliance semaphore).
- Q (during implementation): Should 2D and 3D be separate overlays? → A: No —
  one viewer overlay per survey with an icon-based 2D/3D mode switch in its
  header, so both views live on a single page.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consistent application shell and visual identity (Priority: P1)

As a Rampa user (auditor or surveyor of a mining operation), when I sign in I
see a professional application with a persistent header — product name,
indicator of who I am signed in as with a sign-out action, and a visible
Spanish/English language switcher — and every page laid out with consistent
widths, spacing, and a dark visual theme suited to map-centric work. I no
longer see unstyled browser-default pages.

**Why this priority**: The shell (theme, layout, header) is the foundation
every other visual change depends on; without it, styling individual
components produces no coherent result. It is also the single change with the
most visible impact per screen.

**Independent Test**: Sign in and navigate through every existing page
(login, project list, project detail). Verify the header persists with brand,
user indicator, sign-out, and language switcher; verify all pages share the
dark theme, consistent content width, and spacing — with no functional
change to any flow.

**Acceptance Scenarios**:

1. **Given** an unauthenticated visitor, **When** they open the application,
   **Then** the login screen presents the product identity and a styled form
   consistent with the application theme.
2. **Given** an authenticated user on any page, **When** they look at the top
   of the screen, **Then** a persistent header shows the product name, their
   username, a sign-out action, and a language switcher that changes all
   visible texts between Spanish and English immediately.
3. **Given** an authenticated user, **When** they navigate between the
   project list and a project detail, **Then** both pages share the same
   theme, content width, typography, and spacing rhythm.
4. **Given** any interactive element (button, link, form field), **When** the
   user hovers it, focuses it via keyboard, or it is disabled, **Then** its
   visual state changes in a way that is consistent across the application
   and visible against the dark background.

---

### User Story 2 - Styled working screens: projects, surveys, upload, members (Priority: P2)

As a Rampa user, the screens where I do my daily work — the project list,
project creation, and the project detail with its survey table, upload
widget, processing statuses, and member management — look organized and
readable: styled tables, clear forms with labeled fields and visible errors,
status badges with semantic colors, a styled upload progress bar, and helpful
empty states when there is nothing yet.

**Why this priority**: These screens are where users spend their time between
uploads; they carry the densest information (tables, statuses, progress) and
gain the most usability from visual hierarchy. They depend on the shell (US1)
being in place.

**Independent Test**: With an account that has no projects, walk the full
flow: see the projects empty state, create a project via the styled form,
open it, see the surveys empty state, start an upload and watch the styled
progress bar and status badges evolve through the pipeline stages, and manage
members. Every step must look styled and behave exactly as before.

**Acceptance Scenarios**:

1. **Given** a user with no projects, **When** they open the project list,
   **Then** they see an empty state with a message and a clear call to action
   to create the first project.
2. **Given** a user viewing a project's surveys, **When** surveys are in
   different pipeline states, **Then** each state (queued / processing /
   completed / failed) appears as a badge with a distinct semantic color, and
   the current stage remains visible while processing.
3. **Given** a user uploading a survey file, **When** the transfer is in
   progress, **Then** a styled progress bar shows the percentage, and
   interrupted/resumable uploads are presented as clearly distinguishable
   notices.
4. **Given** a user removing a project member, **When** they trigger the
   removal, **Then** a styled confirmation dialog (not a native browser
   popup) asks for confirmation before the action executes, with distinct
   confirm (danger) and cancel actions.
5. **Given** a form submission that fails (e.g., invalid login or duplicate
   member), **When** the error is returned, **Then** the message appears as a
   styled, clearly visible alert associated with the form, in the user's
   language.

---

### User Story 3 - Viewers as protagonists (Priority: P3)

As a Rampa user, when I open the 2D map or the 3D point cloud of a survey,
the viewer opens as a full-viewport overlay covering the whole window, with a
visible close action that returns me to the project detail, and its controls
(basemap selector, survey layer selector) are visually integrated over the
map as compact overlay controls, instead of plain form elements around it.
Loading and error states of the viewers are presented consistently with the
rest of the application.

**Why this priority**: The viewers are the product's core value and the
stage on which the upcoming axis-drawing tools will live; their frame and
overlay controls define the pattern those tools will follow. It builds on US1
and can ship after US2 without blocking it.

**Independent Test**: Open the 2D viewer of a completed survey: verify it
fills the available viewport space and that the basemap and survey layer
selectors render as overlay controls on the map, fully functional. Repeat
with the 3D viewer, including its loading indicator and its error state.

**Acceptance Scenarios**:

1. **Given** a completed survey, **When** the user opens the 2D map, **Then**
   the map opens as a full-viewport overlay with a visible close action, and
   the basemap and survey layer selectors appear as compact controls overlaid
   on the map, keeping all their current options and behavior.
2. **Given** a completed survey, **When** the user opens the 3D view,
   **Then** the viewer opens as a full-viewport overlay with a visible close
   action and its loading indicator matches the application's visual style.
3. **Given** an open viewer overlay, **When** the user closes it, **Then**
   they return to the project detail exactly as they left it (scroll
   position, data, and state preserved) without any page reload.
4. **Given** a viewer that cannot load its data, **When** the failure occurs,
   **Then** the error message appears with the application's standard alert
   styling, in the user's language.

---

### Edge Cases

- What happens on small desktop screens (e.g., 1280×720 laptop)? Layout and
  viewers must remain usable without horizontal scrolling or overlapping
  controls; full mobile support is out of scope.
- What happens with long content — project names, usernames, filenames of
  uploaded surveys? Text must truncate or wrap gracefully without breaking
  the layout.
- What happens when the language switches while a confirmation dialog or an
  alert is open? Visible texts must render in the newly selected language on
  next render, and nothing may appear hard-coded in a single language.
- What happens while data is loading (project list, survey table refresh)?
  Screens must not flash unstyled or collapse; existing content areas keep
  their dimensions where feasible.
- What happens to keyboard users? All interactive elements must remain
  reachable in a logical order with a visible focus indicator; dialogs must
  be dismissible and must not trap focus permanently.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The application MUST define a single design system — color
  palette, typography scale, and spacing scale — expressed as reusable design
  tokens, and every screen MUST consume those tokens rather than ad-hoc
  values. The palette uses an amber accent over neutral dark grays; the
  accent MUST remain visually distinguishable from the semantic status
  colors (green/yellow/red), which are reserved for states such as pipeline
  statuses and the future compliance semaphore.
- **FR-002**: The application MUST use a dark theme as its primary and only
  theme, with sufficient contrast for text and interactive elements to remain
  readable (WCAG AA contrast as the working target for body text and
  controls).
- **FR-003**: Every authenticated screen MUST display a persistent header
  containing the product name, the authenticated user's identity, a sign-out
  action, and a Spanish/English language switcher; the login screen MUST
  present the product identity without the authenticated elements.
- **FR-004**: All interactive elements MUST present consistent hover, focus,
  and disabled states; keyboard focus MUST always be visibly indicated.
- **FR-005**: The application MUST provide a set of reusable styled
  components — buttons (primary, secondary, danger), form fields with labels
  and error display, tables, modal/confirmation dialogs, status badges,
  progress bar, empty states, and alert messages — and all screens MUST use
  these components instead of unstyled native elements.
- **FR-006**: Pipeline status indicators MUST use semantically colored badges
  (queued, processing, completed, failed each visually distinct), keeping the
  current stage visible during processing.
- **FR-007**: Destructive confirmations (e.g., removing a project member)
  MUST use the application's styled confirmation dialog instead of native
  browser popups, with visually distinct confirm (danger) and cancel actions.
- **FR-008**: All existing screens — login, project list, project creation,
  project detail (surveys, upload, members), and the 2D/3D viewer frames —
  MUST be restyled with the design system; no screen may remain with
  browser-default styling.
- **FR-009**: The 2D and 3D viewers MUST open as full-viewport overlays
  covering the whole window, with a visible close action returning to the
  project detail without losing its state, and the 2D viewer's basemap and
  survey layer selectors MUST render as overlay controls integrated on the
  map, preserving all current options and behavior.
- **FR-010**: The feature MUST NOT change any functionality, navigation
  route, API call, or backend behavior: every user flow that works today MUST
  work identically after the redesign, and all existing automated tests MUST
  keep passing (with adjustments only where a test asserts presentation
  details that legitimately changed, e.g., the native confirmation popup).
- **FR-011**: All user-visible texts, including any new texts introduced by
  the redesign (e.g., dialog buttons, empty-state calls to action), MUST come
  from the existing Spanish/English internationalization layer; no visible
  text may be hard-coded.
- **FR-012**: The layout MUST remain usable on common desktop resolutions
  down to 1280×720 without horizontal scrolling or overlapping controls.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of existing screens (login, project list, project
  creation, project detail, 2D viewer, 3D viewer) render with the design
  system; zero screens or dialogs remain with browser-default styling
  (native confirmation popups included).
- **SC-002**: A user can complete every existing flow — sign in, create a
  project, upload a survey, follow its processing, open both viewers, manage
  members, switch language, sign out — with zero behavioral differences from
  before the redesign.
- **SC-003**: The full automated test suite passes after the redesign.
- **SC-004**: Every interactive element shows a visible keyboard focus state,
  and body text and controls meet the WCAG AA contrast target against their
  background.
- **SC-005**: On a 1280×720 desktop viewport, every screen is usable without
  horizontal scrolling and the viewers occupy at least 70% of the viewport
  area when open.
- **SC-006**: Switching language updates 100% of visible texts on every
  redesigned screen, including texts introduced by the redesign.

## Assumptions

- The user explicitly chose a utility-first styling approach (Tailwind CSS)
  for the implementation; this is recorded here as a decided constraint for
  the planning phase, while this specification stays otherwise
  implementation-agnostic.
- Dark theme is the only theme in scope; a light theme or a theme switcher is
  deliberately excluded and may come later.
- No new screens, routes, or flows are introduced; the current navigation
  structure is kept as-is.
- Definitive branding (logo, brand colors validated with stakeholders) is out
  of scope; a provisional, coherent identity is sufficient: the product name
  as wordmark plus the chosen "mining amber" palette (amber accent over
  neutral dark grays).
- Full mobile/responsive support is out of scope; the target is desktop
  screens from 1280×720 upward.
- Existing frontend automated tests may be adjusted only where they assert
  presentation details that this feature legitimately changes (e.g., the
  native `window.confirm` popup replaced by a styled dialog); no test may be
  weakened or deleted for convenience.
- The visual patterns established here (overlay controls on the map, panels,
  badges) are expected to be reused by the upcoming geometric evaluation
  feature (axis drawing, station tooltips, compliance panels).
