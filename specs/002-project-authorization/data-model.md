# Data Model: Project Authorization

References: [spec.md](./spec.md) · [research.md](./research.md)

## Entities

### ProjectMembership (new)

| Field | Type | Rules |
|---|---|---|
| id | UUID (pk) | generated |
| project | FK → Project, CASCADE | membership dies with the project |
| user | FK → User, CASCADE | membership dies with the user (edge case: sole owner handled via admin channel) |
| role | enum `owner` \| `member` | FR-004 |
| granted_by | FK → User, SET_NULL, nullable | NULL = granted by the system (backfill) — FR-009 |
| granted_at | datetime, auto | FR-009 |

**Constraints**

- `unique(project, user)` — at most one membership per user per project.
- Application-level invariant (FR-006): a project always has ≥ 1 membership
  with `role=owner`; enforced transactionally in every mutation that removes
  or downgrades an owner (`select_for_update` on the project's memberships).

**Indexes**: `(user, project)` covered by the unique constraint (user listed
first in a secondary index to serve `projects_for(user)` lookups).

### Project (existing — behavioral change only)

- No schema change. `created_by` remains the audit field for "who created
  it"; authorization derives from ProjectMembership, never from `created_by`
  after the backfill migration.
- Visibility rule: a project exists for a user iff a membership row links
  them (FR-001/FR-002).

### User (existing — unchanged)

- Participates in zero or more memberships.

## State transitions

Membership has no state machine — rows are created, updated (role), and
deleted. The meaningful transitions and their guards:

| Transition | Guard |
|---|---|
| create (member or owner) | actor is owner of project; target user exists; no existing membership (FR-005) |
| role member → owner | actor is owner |
| role owner → member | actor is owner; project keeps ≥ 1 other owner (FR-006) |
| delete | actor is owner; if target is owner, project keeps ≥ 1 other owner; actor may not delete own membership if sole owner |
| backfill create | migration only: `(project, created_by, owner, granted_by=NULL)` (FR-010) |

## Migration plan

1. Schema migration: create `ProjectMembership` table + indexes.
2. Data migration: for every `Project`, `get_or_create` the owner membership
   for `created_by` (idempotent, zero manual steps — FR-010).
3. No reverse data migration (dropping the table restores the pre-feature
   world where visibility is global).
