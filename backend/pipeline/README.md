# `pipeline` — processing option & input-type registry

`pipeline/options.py` is the single source of truth for what a run can
produce (data-model.md). Adding a new **option** or **input type** is meant
to be pure registration: a declaration + a producer function + i18n keys —
no changes to `apps/surveys/tasks.py` (orchestration), `serializers.py`, or
any `views_*.py`. `tests/integration/test_dummy_option_e2e.py` proves this in
CI and is the template for both procedures below.

## Adding an option

1. **Write the producer** in `pipeline/stages/<your_module>.py` (or reuse an
   existing one): a plain function `producer(ctx: RunContext) -> dict[str, SurfaceArtifact]`.
   - `ctx.input_laz`, `ctx.workdir`, `ctx.resolution_m` are always available.
   - `ctx.artifacts` maps each of the option's *prerequisites* to a local
     path already downloaded by the orchestrator — read from there if your
     option consumes a prior option's output (see `hillshade_producer`
     consuming `elevation`'s DEM in `pipeline/stages/surfaces.py`).
   - Return `{option_id: SurfaceArtifact}` for the option(s) this call
     fulfills. **One producer may fulfill several options in a single
     execution** (FR-015) — e.g. a future NodeODM route emitting DEM +
     orthophoto + point cloud together. Key the returned dict by every
     option id it produces; the per-option task wrapper (`run_option` in
     `apps/surveys/tasks.py`) publishes each one independently and skips any
     that aren't pending in the current run — you never need to touch that
     wrapper.
   - Never upload from the producer. Return artifact descriptors only;
     `run_option` uploads, checksums, and creates `DerivedArtifact` rows.
2. **Register the `OptionSpec`** at the bottom of `pipeline/options.py`:
   ```python
   register_option(
       OptionSpec(
           id="my_option",                       # stable forever — never rename
           label_key="options.my_option.label",
           description_key="options.my_option.description",
           input_types=frozenset({"point_cloud"}),
           target_view="map2d",                  # or "view3d"
           required=False,
           default_selected=False,
           active=True,
           prerequisites=(),                     # or ("elevation",) etc.
           producer=my_option_producer,
       )
   )
   ```
   Import-time validation (`validate_registry()`, called at the bottom of
   the module) rejects a duplicate id, an unknown/inapplicable prerequisite,
   or a prerequisite cycle immediately on import.
3. **Add i18n keys** in `frontend/src/i18n/es/common.json` and
   `.../en/common.json` under `options.my_option.label` /
   `options.my_option.description`. No user-visible string may live outside
   these catalogs (Principle IX) — the catalog endpoint only ever serves
   keys, never display text.
4. **Tests** (mirroring `test_dummy_option_e2e.py`):
   - A unit test for the producer itself, if it has real logic worth
     covering (see `tests/unit/test_stage_surfaces.py`).
   - An integration test that the option appears in `GET
     /processing-options`, is selectable at upload initiation, executes end
     to end, and resolves in `GET /surveys/{id}/artifacts` — without editing
     any orchestration/serializer/view file.

Deactivating an option later is a one-line flip (`active=False`): it
disappears from the catalog and is rejected on new selections, but
historical runs/artifacts and retries of runs that already selected it keep
working unchanged (FR-008) — see `tests/integration/test_option_deactivation.py`.

## Adding an input type

1. **Register the `InputTypeSpec`**:
   ```python
   register_input_type(InputTypeSpec(id="my_input", label_key="input_types.my_input.label"))
   ```
2. **Declare its options** with `input_types={"my_input", ...}` as above.
   `GET /processing-options?input_type=my_input` then serves only that
   input type's active options; `effective_selection("my_input", ids)`
   validates against that same subset.
3. Mandatory prep steps (the async chain that must run before any option,
   e.g. validation/reprojection for `point_cloud`) are wired per input type
   in `apps/surveys/tasks.py::enqueue_run` — that's the one place where a
   genuinely new *ingest route* (as opposed to a new *option*) needs an
   explicit branch, since prep steps are real Celery tasks and this package
   stays framework-light (importable without Django).

## What never changes

`apps/surveys/tasks.py`, `serializers.py`, and every `views_*.py` are
input-type- and option-agnostic: they read the registry generically
(`options_for`, `effective_selection`, `topo_order`, `get_option`) and never
hardcode an option or input-type id. If you find yourself editing one of
those files to add an option, something is wrong — check
`test_dummy_option_e2e.py` for the intended shape.
