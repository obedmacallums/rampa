# Data Model: Selectable & Extensible Processing Options

**Date**: 2026-07-19 | **Plan**: [plan.md](./plan.md) | Extends [001 data-model](../001-survey-ingest/data-model.md)

## Registry (code, not database)

Single source of truth in `backend/pipeline/options.py`. Not persisted;
validated at import time (unique ids, acyclic prerequisites, prerequisites
share at least the option's input types).

### OptionSpec

| Field | Type | Notes |
|---|---|---|
| `id` | str (slug) | Stable forever; stored on DB rows as plain string |
| `label_key` / `description_key` | str | i18n keys (es primary, en secondary) — never display text (Principle IX) |
| `input_types` | set[str] | Input types the option applies to (FR-001/FR-014) |
| `target_view` | enum `map2d` \| `view3d` | Where products surface (FR-005) |
| `required` | bool (per spec: per input type) | Always generated, non-deselectable (FR-002) |
| `default_selected` | bool | Preselected in UI |
| `active` | bool | Inactive: hidden from new selections, history intact (FR-008) |
| `prerequisites` | list[option id] | Visible auto-selection + server closure (FR-006) |
| `producer` | callable ref | Production route; one producer MAY fulfill several options (FR-015) |

### InputTypeSpec

| Field | Type | Notes |
|---|---|---|
| `id` | str (slug) | `point_cloud` (only entry in scope, FR-013) |
| `label_key` | str | i18n key |
| `prep_steps` | list[task ref] | Mandatory preparation chain (relocate, validate, reproject) |

**Initial catalog** (R8): `elevation` (required, map2d, no prereqs),
`hillshade` (optional, map2d, prereq `elevation`), `point_cloud_3d`
(optional, view3d, no prereqs) — all `input_types={point_cloud}`,
`default_selected=True`, `active=True`.

## Database changes

### Survey *(modified)*

| Field | Change | Notes |
|---|---|---|
| `input_type` | NEW `CharField(32)`, default `point_cloud` | FR-013; validated against registry |

### UploadSession *(modified)*

| Field | Change | Notes |
|---|---|---|
| `selected_options` | NEW `JSONField` (list[str]), schema default `list` (empty) | Effective selection (server-completed closure incl. required), always computed from the registry and written by the initiation view — never defaulted in the schema, so the migration carries no catalog knowledge. Recorded at upload start (FR-002, clarification Q4) |

### ProcessingRun *(modified)*

| Field | Change | Notes |
|---|---|---|
| `input_type` | NEW `CharField(32)`, default `point_cloud` | Copied from survey at enqueue (FR-013) |
| `stage` | unchanged values + semantics note | `validation`/`reprojection` describe prep; once options start, per-option states are the primary progress signal. Historical `surface_generation` rows remain valid |

State machine (run): `queued → running → completed | failed` (unchanged).
`completed` requires all RunOptions `completed`/`reused`; any `failed`
RunOption ⇒ run `failed` (FR-009), even though other options published.

### RunOption *(new)*

One row per option in a run's effective selection. Unit of selection
persistence (FR-004), progress (FR-010), publication and failure attribution
(FR-009).

| Field | Type | Notes |
|---|---|---|
| `id` | UUID pk | |
| `run` | FK ProcessingRun (`related_name="options"`) | CASCADE |
| `option_id` | `CharField(64)` | Registry id (string, no FK — R1) |
| `state` | enum | `pending → running → completed \| failed \| skipped`; `reused` set at creation on retry when a prior run already completed the option (R5) |
| `reused_from` | FK ProcessingRun, null | Producing run when `state=reused` (transitive resolution target) |
| `failure_code` / `failure_message_key` | CharField, null | Same error vocabulary as run (FR-009, SC-006) |
| `started_at` / `finished_at` | DateTime, null | |

Constraints: `UniqueConstraint(run, option_id)`.

State transitions: `pending → running → completed | failed`;
`pending → skipped` (a prerequisite failed, FR-009/R3); `reused` is terminal
and set only at creation.

### DerivedArtifact *(modified)*

| Field | Change | Notes |
|---|---|---|
| `option_id` | NEW `CharField(64)`, null=True only during backfill; promoted to NOT NULL by a follow-up migration once T007 attributes every legacy row (tasks T033) | Attribution (FR-005); backfilled from `kind` (R6) |
| `kind` | unchanged | Artifact format kind (dem/hillshade/copc; later ortho, …) — distinct axis from option (R8) |
| constraint | `artifact_kind_per_run_unique` unchanged | Per-option publication writes each option's artifacts once per run |

## Resolution rule (FR-016)

For a survey and each option ever selected: displayed product = artifacts of
the **latest run** whose `RunOption(option_id)` is `completed`; `reused` rows
delegate to `reused_from`. Implemented as a query helper used by the artifacts
endpoint; no denormalized pointers (R5).

## Backfill migration (FR-012, R6)

1. `Survey.input_type = ProcessingRun.input_type = 'point_cloud'` (default).
2. `DerivedArtifact.option_id` from `kind`: `dem→elevation`,
   `hillshade→hillshade`, `copc→point_cloud_3d`.
3. For every existing run, create `RunOption` rows for the then-standard
   selection (`elevation`, `hillshade`, `point_cloud_3d`): `completed` where
   the run has the matching artifact; otherwise `failed` (run failed) with the
   run's failure code, or `skipped` for the rest of a failed run.
4. `UploadSession.selected_options` = standard set for historical rows.

## Validation rules

- Selection writes (upload initiation, retry/additional-options enqueue):
  every id exists in registry ∧ active ∧ applies to input type; server adds
  required + prerequisite closure; else `invalid_options` (R2).
- `RunOption` writes validate `option_id` against registry (including
  inactive ids for historical operations like retry — deactivation only
  blocks *new selections*, FR-008 / edge case).
- Producers publish through the existing `assert_key_within_survey` guard;
  an option's artifacts are created only after all its files are uploaded and
  checksummed (option-level atomicity, FR-009).
