# Research: Project Authorization

No NEEDS CLARIFICATION markers remained in the spec; research consolidates
the design decisions and their alternatives.

## R1 — Enforcement point: scoped querysets, not permission classes

**Decision**: All project-scoped access goes through one helper module
(`apps/projects/access.py`): `projects_for(user)` returns the membership-
scoped queryset, and `get_project_or_404(user, id)` /
`get_survey_or_404(user, id)` resolve objects through that scope. Views never
query `Project.objects` / `Survey.objects` directly for user requests.

**Rationale**: FR-002 requires denial to be indistinguishable from
nonexistence. Object-level DRF permission classes run *after* object
retrieval and return 403, which leaks existence. Scoped querysets make 404
the natural outcome, concentrate the rule in one reviewable place, and make
"unscoped query in a view" a grep-detectable smell.

**Alternatives considered**: per-view DRF `permission_classes` (403 leaks +
scattered logic); row-level security in the database (overkill for one table
and hard to test with the current tooling); middleware-based URL guards
(breaks for nested resources like surveys reached by their own id).

## R2 — Role model: one membership table with a role field

**Decision**: `ProjectMembership(project, user, role ∈ {owner, member},
granted_by, granted_at)` with `unique(project, user)`. The "at least one
owner" invariant (FR-006) is enforced transactionally in the membership
mutation endpoints (count owners with `select_for_update` before remove /
downgrade).

**Rationale**: US3 requires shared and transferable ownership, which a
single `owner` FK on Project cannot express. A two-value role enum covers the
spec exactly; the table is the natural place for the FR-009 audit fields.

**Alternatives considered**: `Project.owner` FK + membership table
(cannot have co-owners); Django groups/permissions framework (global, not
per-object, would need django-guardian — a new dependency for two roles);
separate owners/members tables (two tables, same shape, more joins).

## R3 — Backfill: data migration from `created_by`

**Decision**: A data migration inserts an owner membership
`(project, project.created_by, role=owner, granted_by=NULL)` for every
existing project. `created_by` is non-nullable (`PROTECT`), so every project
has a creator to promote; `granted_by=NULL` denotes "by the system".

**Rationale**: FR-010 requires zero manual steps. Reusing `created_by` — 
already stored since 001 — makes the backfill total and idempotent
(`get_or_create`).

**Alternatives considered**: management command run by operators (violates
"zero manual intervention"); leaving old projects visible to all
(grandfathering would contradict US4 scenario 2).

## R4 — Server-to-server paths bypass membership

**Decision**: The tusd completion hook (shared-secret authenticated, no user
session) and Celery pipeline tasks keep using unscoped managers; only
user-session request paths route through `access.py`.

**Rationale**: FR-012 — the pipeline acts on behalf of the platform. The
hook already authenticates via shared secret; adding user scoping there
would break ingestion for every upload finishing after a membership change.

**Alternatives considered**: a synthetic "pipeline user" holding membership
in every project (pure bookkeeping, drifts on every membership change).

## R5 — Admin channel: management command

**Decision**: `manage.py members <add|remove|list> <project> [username]
[--role]`, mirroring the existing `createuser` command, usable for support
cases (e.g. sole owner deleted — edge case in spec).

**Rationale**: the spec assumes administrators keep an out-of-band channel
with full reach and no new admin UI; a management command matches how
accounts are already provisioned in this deployment model.

**Alternatives considered**: Django admin site (not currently enabled;
enabling it just for this widens surface area); no tooling (leaves the
orphaned-project edge case unresolvable).

## R6 — Revocation vs. already-issued artifact URLs

**Decision**: No change to presigned URL issuing. Existing expiry is 3600 s
(= the 60 min bound in FR-008/SC-005). Revocation denies all *new* requests
immediately because every issuing endpoint is membership-scoped.

**Rationale**: The spec explicitly accepts natural expiry of outstanding
links. Shortening expiry would hurt long 3D sessions (Potree streams nodes
continuously from one URL).

**Alternatives considered**: proxying artifact bytes through the backend to
check membership per byte-range (kills Principle II's client-side streaming
and titiler integration); per-request short-lived URLs (breaks Potree's
long-running range requests mid-session).

## R7 — Frontend surface

**Decision**: A `ProjectMembers` panel on the project detail page (list +
owner-only add/remove/role controls), a small Zustand store, and es/en
catalog additions. The projects store needs no change — the list endpoint
simply returns fewer rows.

**Rationale**: SC-006 (add a teammate without leaving the project page) and
FR-007 (all members see the list, owners see controls) point to a single
embedded panel rather than a separate settings page.

**Alternatives considered**: separate members/settings route (more
navigation for a single panel); modal-only management (harder to show the
FR-009 audit columns).
