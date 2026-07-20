# Specification Quality Checklist: Selectable & Extensible Processing Options

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-19
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- The typo in the user description ("unos en la vista 2d y otros en la vista
  2d") was resolved as 2D and 3D and recorded in Assumptions; confirm with
  the author during `/speckit-clarify` if needed.
- **Resolved (T034)**: the run-level atomicity assumption above was
  superseded by the 2026-07-19 clarification and FR-009: publication moved to
  per-option atomicity (each option publishes all of its products or none; a
  run may end with a mix of completed and failed options). Implemented in
  `apps.surveys.tasks.run_option`/`_fail_option`/`_skip_dependents` and
  covered by `tests/integration/test_per_option_publication.py`.
- Input type was added as an explicit dimension (FR-013/FR-014, Input Type
  entity) to lay foundations for future photogrammetric (drone photos) and
  georeferenced-mesh inputs, per the author's 2026-07-19 follow-up; those
  input types remain out of implementation scope.
- FR-015 decouples options (deliverables) from production routes per input
  type, since a photogrammetric engine emits several deliverables in one
  execution while point-cloud routes derive them step by step; handling of
  co-produced but unselected deliverables is deferred to each input type's
  feature.
- Items marked incomplete require spec updates before `/speckit-clarify` or `/speckit-plan`

### Success Criteria verification (T034, post-implementation)

- **SC-001** (selection adds < 1 min to upload flow): design-level — the
  catalog loads once from the in-memory registry on `UploadWidget` mount and
  arrives pre-checked with today's default set, so the zero-click path is
  unchanged; not independently timed against real users.
- **SC-002** (100% of products attributable to option + run, in declared
  view): verified — `DerivedArtifact.option_id` is DB-enforced NOT NULL
  (T033); `tests/integration/test_api_artifacts_products.py` and
  `test_per_option_publication.py` assert per-option attribution and that
  the frontend gates 2D/3D layers on product presence (T024).
- **SC-003** (new option needs no upload/view/orchestration changes):
  verified — `tests/integration/test_dummy_option_e2e.py` registers a
  throwaway option end to end without touching `tasks.py`/`serializers.py`/
  any `views_*.py`.
- **SC-004** (≥90% of users find each product in the expected view on first
  attempt): usability metric, out of reach for automated tests — addressed
  by design (per-option target-view badge in `OptionPicker`, product-gated
  2D/3D tabs) but requires a real usability check to confirm the number.
- **SC-005** (additional products need zero re-uploads): verified —
  `tests/integration/test_additional_options.py` asserts
  `UploadSession.objects.count() == 0` after `POST /surveys/{id}/process`.
- **SC-006** (100% of failed runs name the failing option in the user's
  language): verified — `RunOption.failure_message_key` always resolves
  through the es/en `errors.json` catalogs;
  `frontend/tests/survey-status.test.tsx` asserts the translated message
  renders for the failing option.
