# Feature Specification: Delete Projects and Surveys

**Feature Branch**: `005-delete-projects-surveys`

**Created**: 2026-07-20

**Status**: Draft

**Input**: User description: "Permitir borrar proyectos y/o levantamientos (surveys) existentes. Actualmente no hay ninguna forma de eliminarlos: ni endpoint, ni UI, ni soft-delete; el spec de 001-survey-ingest lo marcó explícitamente fuera de alcance (\"project editing/deletion are out of scope\", \"Deleting surveys is out of scope for this feature; coexistence and immutability are the guarantees provided\"). El usuario quiere poder borrar un proyecto o un survey, ya sea porque no se procesó correctamente (falló) o simplemente porque ya no lo necesita. Hay que definir: qué se puede borrar (¿solo proyectos?, ¿solo surveys dentro de un proyecto?, ¿ambos?), si el borrado es lógico (soft-delete) o físico (incluyendo los archivos derivados en el almacenamiento de objetos S3/MinIO y los registros en Postgres), qué pasa con los artefactos ya publicados (DerivedArtifact) y con los runs en curso, quién tiene permiso para borrar (¿cualquier miembro?, ¿solo el owner del proyecto?), y si se requiere una confirmación explícita dado que hoy la inmutabilidad es una garantía de diseño central de la plataforma."

## Context

Today there is no way to remove a project or a survey once created — not from the interface, not as an API operation. This was a deliberate choice in the initial ingest feature ("project editing/deletion are out of scope"; "deleting surveys is out of scope... coexistence and immutability are the guarantees provided"). In practice, users have no way to clear clutter: surveys that failed and will never be retried, test uploads, or entire projects that turned out unnecessary. This feature introduces a deliberate, explicit way to remove a project or an individual survey within a project. It does not change the platform's existing guarantee that a survey's *published results* are never silently mutated by any background process — removal is always a distinct, confirmed, user-initiated action, never a side effect of anything else.

## Clarifications

### Session 2026-07-20

- Q: Is deletion permanent and immediate the moment it's confirmed, or does the platform keep deleted projects/surveys recoverable for a period before permanently purging their data and files? → A: Soft delete with a recovery window — hidden immediately, restorable for a period, then a background process permanently purges the database rows and derived files in object storage.
- Q: Who is authorized to delete — any project member, or only the project's owner(s)? Does the answer differ between deleting a single survey and deleting the whole project? → A: Owner-only for both — deleting a survey and deleting a project both require the project owner role; a member without that role cannot delete either.
- Q: How does a user find and restore something they deleted — a browsable list, an inline "undo" right after deleting, or no self-service restore at all? → A: A dedicated "Recently Deleted" view per project, where the owner can browse and restore items within the recovery window (like a trash/papelera).
- Q: When a deleted project is restored, do the surveys that were cascade-deleted along with it come back automatically, or must each be restored separately afterward? → A: Restoring a project automatically brings back, as a single unit, every survey that was cascade-deleted with it.
- Q: Should deleting an entire project also be blocked while it has an upload actively in progress (not yet turned into a survey)? → A: Yes — block project deletion while any upload is actively in progress, in addition to blocking on queued/running processing runs; this does not affect deleting an individual survey, which remains unaffected by unrelated uploads elsewhere in the same project (FR-001).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Remove a survey that is no longer needed (Priority: P1)

A project owner uploaded a survey that failed to process, was a test, or is simply no longer needed. From the project's survey list, they delete that one survey; the survey and everything it produced (uploads, processing runs, derived products) disappear from the project, while the rest of the project and its other surveys remain exactly as they were.

**Why this priority**: This is the most common, lowest-risk cleanup action (a single survey vs. an entire project) and directly matches the reported need ("no se procesaron... o simplemente ya no los quiero").

**Independent Test**: Create a project with two surveys, delete one of them, and verify only the deleted survey disappears from listings while the other survey and the project remain fully intact and usable.

**Acceptance Scenarios**:

1. **Given** a project with a failed survey, **When** the project owner deletes that survey, **Then** it no longer appears in the project's survey list and its previously processed products are no longer reachable.
2. **Given** a project with a survey that is actively being processed (a run is queued or running), **When** the owner attempts to delete it, **Then** the deletion is rejected with a clear explanation, and they can retry once processing reaches a final state.
3. **Given** a survey was just deleted, **When** the same user tries to delete it again, **Then** the system responds clearly that it no longer exists (no crash, no silent success).
4. **Given** a project member who is not the owner, **When** they attempt to delete a survey, **Then** the action is rejected and the survey is unaffected.

---

### User Story 2 - Remove an entire project (Priority: P2)

A project owner decides an entire project is no longer needed. They delete the project; all of its surveys and everything produced from them are removed together, and the project disappears from their project list.

**Why this priority**: Less frequent than single-survey cleanup, and higher blast radius (an entire project's history disappears at once), so it is built once single-survey deletion is proven safe.

**Independent Test**: Create a project with two surveys (one completed, one failed), delete the project, and verify the project and both surveys are gone while other, unrelated projects are unaffected.

**Acceptance Scenarios**:

1. **Given** a project with several surveys in different states, **When** the owner deletes the project, **Then** the project and every survey inside it stop appearing anywhere in the platform.
2. **Given** a project with a survey currently processing, **When** the owner attempts to delete the project, **Then** the deletion is rejected until that processing reaches a final state, with a clear explanation of why.
3. **Given** a project member who is not the owner, **When** they attempt to delete the project, **Then** the action is rejected and the project is unaffected.

---

### User Story 3 - Undo an accidental deletion (Priority: P3)

A project owner opens the project's "Recently Deleted" view — days or moments after deleting a survey or project — and restores it exactly as it was, with no data loss.

**Why this priority**: Valuable safety net now that deletion is soft (Clarifications), but the core need ("let me clean things up") is fully met without it — it is the smallest, most cuttable slice if time is short.

**Independent Test**: Delete a survey, find it in the "Recently Deleted" view and restore it within the recovery period, and verify it reappears with all its data and history intact; after the recovery period elapses, verify it no longer offers a restore action and is no longer restorable.

**Acceptance Scenarios**:

1. **Given** a survey deleted moments ago, **When** the owner opens "Recently Deleted" and restores it within the recovery period, **Then** it reappears in the project exactly as it was, including its processing history and products, and disappears from "Recently Deleted".
2. **Given** a survey deleted longer ago than the recovery period, **When** the owner looks in "Recently Deleted", **Then** it either no longer appears there or is clearly shown as no longer restorable.

### Edge Cases

- Deleting a project cascades to every survey, upload session, processing run, and derived product inside it; nothing is left orphaned or later resurfaces.
- A survey or project cannot be deleted while it has processing actively queued or running — the request is rejected with a clear, translated message instead of silently queuing behind it or corrupting in-flight work.
- A project cannot be deleted while it has an upload actively in progress (not yet turned into a survey) — rejected the same way (FR-003); an individual survey deletion is unaffected by unrelated uploads happening elsewhere in the same project.
- Deleting a survey that another user currently has open in the 2D or 3D viewer: the viewer simply fails to load further data for it, the same way it already handles an expired or unavailable result.
- A survey processed before this feature existed deletes exactly the same way as one processed after it.
- Deleting the last remaining survey in a project leaves an empty, otherwise intact project — deleting the project itself is a separate, explicit action.
- Restoring a survey whose parent project was itself deleted and already permanently purged is not possible; the system explains this clearly rather than restoring an orphaned survey.
- A survey deleted on its own, before its project was later deleted, is not brought back by restoring the project — only surveys that were still active at the moment the project was deleted are cascade-restored with it (FR-011).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The project owner MUST be able to delete an individual survey from within its project, removing that survey and everything derived from it (uploads, processing runs, generated products) without affecting the rest of the project.
- **FR-002**: The project owner MUST be able to delete an entire project, which removes every survey inside it and everything derived from them.
- **FR-003**: The system MUST reject deletion of a survey or project while any of its processing runs is queued or running, with a clear, understandable explanation, rather than silently deferring the request or corrupting the in-flight run. Deleting an entire project MUST additionally be rejected the same way while the project has any upload actively in progress that has not yet produced a survey; deleting an individual survey is unaffected by unrelated uploads elsewhere in the same project.
- **FR-004**: The system MUST require an explicit confirmation step before deleting a project or survey, distinct from the click that initiates the request, so deletion is never a side effect of a casual click.
- **FR-005**: Deleted projects and surveys MUST stop appearing in all normal listings and views immediately after deletion is confirmed.
- **FR-006**: Deletion MUST be recoverable for a defined period after confirmation (soft delete): the deleted project or survey stays out of normal listings but its data and files remain intact and restorable until the period elapses, after which a background process permanently and irreversibly removes its records and derived files from storage.
- **FR-007**: Only the project's owner MAY delete a project or a survey within it; a project member who is not an owner MUST NOT be able to delete either, and MUST receive a clear rejection if they attempt it.
- **FR-008**: The system MUST record who deleted a project or survey and when, so the action is traceable after the fact.
- **FR-009**: Attempting to delete a project or survey that has already been deleted (or never existed) MUST fail with a clear, understandable message rather than a confusing error.
- **FR-010**: The project owner MUST be able to browse a "Recently Deleted" view listing every project or survey they deleted that is still within its recovery period, and restore any of them from that view, returning it exactly as it was (including its processing history and products); attempting to restore past the recovery period, or a survey whose parent project was already permanently purged, MUST fail with a clear explanation, and the "Recently Deleted" view MUST reflect items falling out of the recovery period without further user action.
- **FR-011**: Restoring a deleted project MUST automatically restore, as a single unit, every survey that was cascade-deleted along with it — the owner MUST NOT need to restore each survey separately. A survey deleted independently, before its project was deleted, follows its own recovery period and is unaffected by the project's deletion or restoration.

### Key Entities

- **Project** *(existing)*: gains a deleted state and a recovery-period expiry; while deleted, it and everything inside it are excluded from normal listings and views but remain intact until permanently purged.
- **Survey** *(existing)*: gains a deleted state and a recovery-period expiry; while deleted, it and everything derived from it (uploads, runs, products) are excluded from normal listings and views. Deleting a project deletes every survey inside it the same way, sharing the project's recovery period.
- **Deletion Record**: who deleted a project or survey and when (FR-008); backs both traceability and the recovery-period countdown (FR-006/FR-010).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A project owner can remove a survey they no longer need in under 30 seconds from the project view, without contacting anyone else.
- **SC-002**: 100% of a deleted project's surveys, uploads, and generated products stop appearing anywhere in the platform immediately after the project's deletion is confirmed.
- **SC-003**: 0% of deletion requests succeed while the target has processing actively queued or running.
- **SC-004**: 100% of deletions are traceable to the user and time that performed them.
- **SC-005**: Every deletion requires an explicit confirmation step; 0% of surveys or projects are removed by a single, unconfirmed click.
- **SC-006**: 100% of projects/surveys restored within the recovery period come back with their processing history and products fully intact.
- **SC-007**: A project owner can find and restore a recently deleted survey or project from "Recently Deleted" in under 1 minute, without contacting anyone else.

## Assumptions

- Deletion applies to projects and surveys; deleting a project always cascades to every survey (and everything derived from it) inside it — there is no way to delete "part of" a survey's results independently of the whole survey.
- A survey or project with processing actively queued or running cannot be deleted; the owner must wait for it to reach a terminal state (completed or failed) first, consistent with how the platform already blocks other actions (e.g. requesting additional processing) while a run is in flight.
- Deletion always requires an explicit confirmation step (e.g. a confirmation dialog), consistent with how the platform already confirms other destructive actions (removing a project member).
- The recovery period's exact length is an implementation detail to settle during planning (e.g. matching the platform's existing 7-day pending-upload expiry window, or another value); this spec only requires that users are told clearly how long they have.
- This feature does not change who can be a project member or what a role grants beyond deletion itself — it only extends the existing owner role with the ability to delete.
- Permanent purge of storage files and database rows after the recovery period is expected to run as a background process, consistent with the platform's existing expired-upload purge job — not a synchronous part of the delete request.
- Restoring from "Recently Deleted" is available to any current owner of the project, not only the specific owner who performed the deletion — ownership is a project-wide role (existing membership model), not a per-action grant tied to one individual.
- How the background purge job handles a partial failure (e.g. database rows removed but an object-storage file fails to delete, or vice versa) is an implementation-level reliability concern to settle during planning, not a scope decision for this spec.
