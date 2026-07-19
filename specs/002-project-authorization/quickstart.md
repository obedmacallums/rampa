# Quickstart & Validation Guide: Project Authorization

Runnable scenarios proving the feature end-to-end. References:
[spec.md](./spec.md) · [data-model.md](./data-model.md) ·
[contracts/rest-api.md](./contracts/rest-api.md)

## Prerequisites

- The 001 stack running: `docker compose -f infra/docker-compose.yml up -d`
- Two users:

```bash
docker compose -f infra/docker-compose.yml exec backend \
  python manage.py createuser ana --password ana12345
docker compose -f infra/docker-compose.yml exec backend \
  python manage.py createuser beto --password beto12345
```

## Scenario 1 — Isolation between users (US1, US2, SC-001)

1. Log in as `ana`; create project "Rajo Ana". Log in as `beto` (other
   browser/incognito); create project "Rajo Beto".
2. Each list shows exactly one project (their own).
3. As `beto`, paste the direct URL of "Rajo Ana"
   (`/projects/{id}` captured from ana's session) → the page behaves as if
   the project did not exist; `GET /api/v1/projects/{ana-id}/surveys`
   returns the same `404 not_found` envelope as a random UUID.
4. As `ana`, upload a survey to "Rajo Ana" and wait for `completed`. As
   `beto`, request `GET /api/v1/surveys/{id}` and
   `GET /api/v1/surveys/{id}/artifacts` for ana's survey → `404`, no
   presigned URLs are issued.

## Scenario 2 — Invite, work, revoke (US3, SC-002, SC-006)

1. As `ana`, open "Rajo Ana" → member panel shows `ana (owner, system)`.
2. Add `beto` as member (< 1 min, without leaving the page — SC-006). As
   `beto`, refresh the project list → "Rajo Ana" appears; open its 2D/3D
   viewers.
3. As `beto`, open the member panel → sees both rows, no management
   controls. `POST /members` as beto → `403 not_owner`.
4. As `ana`, remove `beto` → beto's next request (≤ 5 s later — SC-002)
   shows no "Rajo Ana"; direct URLs are `404` again.
5. As `ana`, try to remove herself / downgrade to member → `409 last_owner`
   with a comprehensible Spanish message.
6. Add `beto` as `owner`; as `beto`, downgrade `ana` to member → allowed
   (two owners existed); as `beto`, try to downgrade himself → `409`.

## Scenario 3 — Expiry bound on issued links (SC-005)

1. As `ana` (owner) with `beto` as member, `beto` opens the 3D view and
   captures the presigned COPC URL from the network panel.
2. `ana` removes `beto`. The captured URL keeps serving range requests until
   its `X-Amz-Expires` window closes (≤ 60 min), then returns 403; no new
   URL can be obtained by `beto` (all issuing endpoints now 404).

## Scenario 4 — Migration backfill (US4, SC-003)

1. On a database created before this feature (e.g. the existing demo stack):
   run migrations.
2. `demo`'s pre-existing projects appear only in `demo`'s list; `ana`/`beto`
   do not see them. Member panel of each old project shows its creator as
   `owner` granted by `system`.

## Automated checks

```bash
# Access-boundary matrix, membership API, migration backfill
docker compose -f infra/docker-compose.yml exec backend pytest \
  tests/integration/test_access_boundaries.py \
  tests/integration/test_membership_api.py \
  tests/integration/test_membership_migration.py

# Full suite (001 regressions must stay green)
docker compose -f infra/docker-compose.yml exec backend pytest

# Frontend i18n completeness (new member-panel keys in es and en)
cd frontend && npm test
```

Expected: all green; 001's quickstart Scenario 1 (upload → 2D/3D) still
passes when exercised by a project member.

## Validation results (2026-07-19, implement phase)

- **Automated checks**: backend suite green in-container against PostgreSQL
  (`pytest tests/` → 49 passed, 1 skipped — the pre-existing `real_laz`
  sample-gated test) and locally; frontend `npm test` → 19 passed (i18n
  parity incl. the four new membership error codes).
- **Scenario 1 (US1/US2, SC-001)**: exercised via HTTP against the compose
  stack — `ana`/`beto` each see exactly their own project; `beto` requesting
  `GET /projects/{ana-id}/surveys` receives a 404 envelope byte-identical to
  a nonexistent UUID. PASS.
- **Scenario 2 (US3, SC-002, SC-006)**: member panel API round-trip — add by
  username (201), member sees list but `403 not_owner` on mutation,
  `404 user_not_found` / `409 already_member` / `409 last_owner` all as
  contracted; revocation reflected in the target's next request; ownership
  handover with two owners works, sole-owner self-downgrade refused. PASS.
- **Scenario 3 (SC-005)**: verified by design — `PRESIGN_EXPIRY_SECONDS`
  defaults to 3600 s (= the 60 min bound) and all issuing endpoints are
  membership-scoped; the wall-clock expiry wait was not exercised.
- **Scenario 4 (US4, SC-003)**: migrations applied on the pre-feature demo
  database; the pre-existing "Demo Smoke" project ended with its creator
  `demo` as `owner` granted by `system`, with zero manual steps. PASS.
