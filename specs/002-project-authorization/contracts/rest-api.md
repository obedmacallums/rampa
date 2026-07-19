# REST API Contract: Project Authorization

Base path `/api/v1`. Session auth; error envelope `{error: {code,
message_key, detail?}}` as in 001. All endpoints below require an
authenticated session (401 otherwise).

## Scoping change to existing endpoints (FR-001/FR-002)

Every already-existing project-scoped endpoint changes behavior, not shape:

| Endpoint | New behavior for non-members |
|---|---|
| `GET /projects` | Returns only the caller's projects (may be empty list) |
| `GET /projects/{id}/surveys`, `GET /projects/{id}/uploads`, `POST /projects/{id}/uploads` | `404 not_found` |
| `GET /surveys/{id}`, `GET /surveys/{id}/artifacts`, `POST /surveys/{id}/retry` | `404 not_found` |
| `POST /projects` | Unchanged shape; side effect: creator gets an `owner` membership (FR-003) |

`404 not_found` is byte-identical to the response for a truly nonexistent id
(FR-002). `POST /api/v1/hooks/tusd` is exempt (shared-secret, FR-012).

## New: membership endpoints

All of them 404 for non-members of `{id}` (same indistinguishability rule).
Mutations additionally require the caller to be an **owner**; a plain member
receives `403 not_owner` (the member already sees the project, so no
existence leak).

### `GET /projects/{id}/members`

Visible to any member (FR-007).

```json
200 [
  {
    "username": "obed",
    "role": "owner",
    "granted_by": null,
    "granted_at": "2026-07-19T12:00:00Z"
  },
  {
    "username": "maria",
    "role": "member",
    "granted_by": "obed",
    "granted_at": "2026-07-19T12:05:00Z"
  }
]
```

`granted_by: null` renders as "system" (backfilled) in the UI.

### `POST /projects/{id}/members`

Owner only. Body: `{"username": "maria", "role": "member" | "owner"}`.

- `201` → membership row as in the list above.
- `404 user_not_found` — username does not exist (FR-005).
- `409 already_member` — membership exists (edge case).
- `400 invalid_role` — role outside the enum.

### `PATCH /projects/{id}/members/{username}`

Owner only. Body: `{"role": "member" | "owner"}` (grant/revoke ownership,
US3 scenario 6).

- `200` → updated row.
- `409 last_owner` — downgrade would leave zero owners (FR-006).
- `404 not_found` — no such membership.

### `DELETE /projects/{id}/members/{username}`

Owner only.

- `204` — removed; all the target's access ends for new requests (FR-008).
- `409 last_owner` — removing the only owner (FR-006), including an owner
  removing themselves while sole owner.
- `404 not_found` — no such membership.

## Message keys (FR-011)

New keys, present in `es` (primary) and `en` catalogs:
`members.title`, `members.role_owner`, `members.role_member`,
`members.granted_by_system`, `members.add_label`, `members.remove_confirm`,
`errors.user_not_found`, `errors.already_member`, `errors.last_owner`,
`errors.not_owner`.

## Admin channel (out-of-band, R5)

`manage.py members list|add|remove <project-name-or-id> [username]
[--role owner|member]` — bypasses ownership checks (operator tool); the only
path that can rescue a project whose sole owner was deleted.
