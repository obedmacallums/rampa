# Quickstart Validation: Delete Projects and Surveys

**Plan**: [plan.md](./plan.md) | **Contracts**: [contracts/rest-api.md](./contracts/rest-api.md) | **Data model**: [data-model.md](./data-model.md)

## Prerequisites

```bash
cd infra && docker compose up -d --build
docker compose exec backend python manage.py migrate --check
```

Two logged-in sessions help for the permission scenarios: an owner (`cookies_owner.txt`)
and a plain member (`cookies_member.txt`) of the same project — add a member
via `POST /projects/{id}/members` (002) if you don't have one yet.

## Scenario 1 — Delete a survey independently (US1)

```bash
curl -s -b cookies_owner.txt -X DELETE http://localhost:8000/api/v1/surveys/$SURVEY_A
# expected: 204
curl -s -b cookies_owner.txt http://localhost:8000/api/v1/projects/$PROJECT/surveys | jq '[.[] | .id]'
# expected: $SURVEY_A absent; other surveys in the project still present and unaffected
```

## Scenario 2 — Blocked while processing, blocked for non-owners (US1)

```bash
# Non-owner attempt
curl -s -b cookies_member.txt -o /dev/null -w "%{http_code}\n" -X DELETE http://localhost:8000/api/v1/surveys/$SURVEY_B
# expected: 403 not_owner

# Owner attempt while a run is queued/running
curl -s -b cookies_owner.txt http://localhost:8000/api/v1/surveys/$SURVEY_PROCESSING/retry -o /dev/null # or wait for an in-flight upload to land
curl -s -b cookies_owner.txt -X DELETE http://localhost:8000/api/v1/surveys/$SURVEY_PROCESSING
# expected: 409 not_deletable
```

## Scenario 3 — Delete an entire project cascades (US2)

```bash
curl -s -b cookies_owner.txt -X DELETE http://localhost:8000/api/v1/projects/$PROJECT
# expected: 204
curl -s -b cookies_owner.txt http://localhost:8000/api/v1/projects | jq '[.[] | .id]'
# expected: $PROJECT absent
curl -s -b cookies_owner.txt -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/v1/projects/$PROJECT/surveys
# expected: 404 (project no longer resolvable)
```

## Scenario 4 — Recently Deleted listing + restore a survey (US3)

```bash
curl -s -b cookies_owner.txt http://localhost:8000/api/v1/deleted | jq .
# expected: "projects" includes $PROJECT with a purge_at ~7 days out;
#           "surveys" includes any independently-deleted survey (e.g. $SURVEY_A
#           from Scenario 1) — NOT the surveys cascade-deleted with $PROJECT

curl -s -b cookies_owner.txt -X POST http://localhost:8000/api/v1/surveys/$SURVEY_A/restore
# expected: 200, survey reappears
curl -s -b cookies_owner.txt http://localhost:8000/api/v1/projects/$PROJECT_OF_A/surveys | jq '[.[] | .id]'
# expected: $SURVEY_A present again
```

## Scenario 5 — Restore a whole project cascade-restores its surveys (US2/US3)

```bash
curl -s -b cookies_owner.txt -X POST http://localhost:8000/api/v1/projects/$PROJECT/restore
# expected: 200
curl -s -b cookies_owner.txt http://localhost:8000/api/v1/projects/$PROJECT/surveys | jq '[.[] | .id]'
# expected: every survey that was active in $PROJECT at the moment it was
#           deleted (Scenario 3) is back; a survey that had already been
#           independently deleted BEFORE that (if any) is still absent
```

## Scenario 6 — Past the recovery window: not_restorable

```bash
# Simulate an expired deletion (test-only): backdate deleted_at past
# DELETE_RECOVERY_DAYS via the Django shell, then:
curl -s -b cookies_owner.txt -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/api/v1/surveys/$OLD_DELETED_SURVEY/restore
# expected: 404 not_restorable
```

## Scenario 7 — Purge job physically removes expired deletions

```bash
docker compose exec backend python manage.py shell -c "
from apps.surveys.tasks_maintenance import purge_expired_deletions
purge_expired_deletions()
"
# expected: the backdated project/survey from Scenario 6 is gone from the
# database, and its object-storage prefix no longer exists in MinIO
docker compose exec backend python manage.py shell -c "
from apps.surveys.models import Survey
print(Survey.objects.filter(id='$OLD_DELETED_SURVEY').exists())
"
# expected: False
```

## Full suites

```bash
docker compose exec backend pytest -q      # backend incl. cascade/permission/purge tests
cd frontend && npm test                     # delete/restore UI flows, Recently Deleted page
```

**Done when**: all scenarios pass against the compose stack, matching the
project's established dev-flow validation approach (see 004's
`validation-notes.md` for the pattern).
