"""Processing option & input-type registry — single source of truth (data-model.md).

Declarative catalog of what a run can produce: each `OptionSpec` is a code
release (declaration + producer), never a database row. DB rows store plain
option-id strings, validated against this registry at write time (R1). The
catalog API (`GET /processing-options`) serves this registry directly.

Adding a new option is meant to be pure registration: declare an `OptionSpec`,
call `register_option`, ship its producer and i18n keys — no changes to
orchestration, serializers, or views (FR-007, US2).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from pipeline.stages.surfaces import (
    elevation_producer,
    hillshade_producer,
    point_cloud_3d_producer,
)

TARGET_VIEWS = {"map2d", "view3d"}


class RegistryError(Exception):
    """Raised for malformed registrations or catalog graph problems."""


class UnknownInputTypeError(RegistryError):
    def __init__(self, input_type: str):
        self.input_type = input_type
        super().__init__(f"unknown input type: {input_type}")


class InvalidSelectionError(RegistryError):
    """Requested option ids that are unknown, inactive, or inapplicable to the
    input type (R2). Callers map this to the `invalid_options` API error."""

    def __init__(self, invalid_ids: list[str]):
        self.invalid_ids = invalid_ids
        super().__init__(f"invalid option ids: {invalid_ids}")


@dataclass(frozen=True)
class OptionSpec:
    id: str
    label_key: str
    description_key: str
    input_types: frozenset[str]
    target_view: str
    required: bool = False
    default_selected: bool = False
    active: bool = True
    prerequisites: tuple[str, ...] = ()
    producer: Callable | None = None


@dataclass(frozen=True)
class InputTypeSpec:
    id: str
    label_key: str
    prep_steps: tuple[Callable, ...] = field(default_factory=tuple)


_options: dict[str, OptionSpec] = {}
_input_types: dict[str, InputTypeSpec] = {}


def register_input_type(spec: InputTypeSpec) -> InputTypeSpec:
    if spec.id in _input_types:
        raise RegistryError(f"duplicate input type id: {spec.id!r}")
    _input_types[spec.id] = spec
    return spec


def register_option(spec: OptionSpec) -> OptionSpec:
    if spec.id in _options:
        raise RegistryError(f"duplicate option id: {spec.id!r}")
    if spec.target_view not in TARGET_VIEWS:
        raise RegistryError(f"{spec.id}: invalid target_view {spec.target_view!r}")
    _options[spec.id] = spec
    return spec


def validate_registry() -> None:
    """Cross-checks over the full graph: run once after every registration is
    in place (import-time validation for the built-in catalog; explicitly by
    tests exercising a broken catalog)."""
    for option in _options.values():
        if not option.input_types <= set(_input_types):
            unknown = sorted(option.input_types - set(_input_types))
            raise RegistryError(f"{option.id}: unknown input type(s) {unknown}")
        for prereq_id in option.prerequisites:
            prereq = _options.get(prereq_id)
            if prereq is None:
                raise RegistryError(f"{option.id}: unknown prerequisite {prereq_id!r}")
            if not option.input_types <= prereq.input_types:
                raise RegistryError(
                    f"{option.id}: prerequisite {prereq_id!r} does not cover "
                    f"all of its input types"
                )
    for option_id in _options:
        _check_acyclic(option_id)


def _check_acyclic(start_id: str) -> None:
    path: set[str] = set()

    def visit(option_id: str) -> None:
        if option_id in path:
            raise RegistryError(f"prerequisite cycle detected at {option_id!r}")
        path.add(option_id)
        for prereq_id in _options[option_id].prerequisites:
            visit(prereq_id)
        path.discard(option_id)

    visit(start_id)


def get_option(option_id: str) -> OptionSpec | None:
    return _options.get(option_id)


def get_input_type(input_type_id: str) -> InputTypeSpec | None:
    return _input_types.get(input_type_id)


def options_for(input_type: str) -> list[OptionSpec]:
    if input_type not in _input_types:
        raise UnknownInputTypeError(input_type)
    return sorted(
        (opt for opt in _options.values() if opt.active and input_type in opt.input_types),
        key=lambda opt: opt.id,
    )


def topo_order(option_ids) -> list[str]:
    """Deterministic order with prerequisites first."""
    ids = set(option_ids)
    ordered: list[str] = []
    visited: set[str] = set()

    def visit(option_id: str) -> None:
        if option_id in visited:
            return
        visited.add(option_id)
        for prereq_id in sorted(_options[option_id].prerequisites):
            if prereq_id in ids:
                visit(prereq_id)
        ordered.append(option_id)

    for option_id in sorted(ids):
        visit(option_id)
    return ordered


def effective_selection(input_type: str, requested_ids: list[str] | None) -> list[str]:
    """Complete + validate a requested selection server-side: unknown,
    inactive, or inapplicable ids raise `InvalidSelectionError` (R2); required
    options and the full prerequisite closure are always added, regardless of
    what the client sent (FR-002/FR-006)."""
    applicable = options_for(input_type)  # raises UnknownInputTypeError
    applicable_ids = {opt.id for opt in applicable}

    requested = set(requested_ids or [])
    invalid = sorted(rid for rid in requested if rid not in applicable_ids)
    if invalid:
        raise InvalidSelectionError(invalid)

    required_ids = {opt.id for opt in applicable if opt.required}
    selection = requested | required_ids

    frontier = set(selection)
    while frontier:
        next_frontier: set[str] = set()
        for option_id in frontier:
            for prereq_id in _options[option_id].prerequisites:
                if prereq_id not in selection:
                    selection.add(prereq_id)
                    next_frontier.add(prereq_id)
        frontier = next_frontier

    return topo_order(selection)


# --- Initial catalog (R8): point_cloud input type, 3 options --------------

register_input_type(InputTypeSpec(id="point_cloud", label_key="input_types.point_cloud.label"))

register_option(
    OptionSpec(
        id="elevation",
        label_key="options.elevation.label",
        description_key="options.elevation.description",
        input_types=frozenset({"point_cloud"}),
        target_view="map2d",
        required=True,
        default_selected=True,
        active=True,
        prerequisites=(),
        producer=elevation_producer,
    )
)

register_option(
    OptionSpec(
        id="hillshade",
        label_key="options.hillshade.label",
        description_key="options.hillshade.description",
        input_types=frozenset({"point_cloud"}),
        target_view="map2d",
        required=False,
        default_selected=True,
        active=True,
        prerequisites=("elevation",),
        producer=hillshade_producer,
    )
)

register_option(
    OptionSpec(
        id="point_cloud_3d",
        label_key="options.point_cloud_3d.label",
        description_key="options.point_cloud_3d.description",
        input_types=frozenset({"point_cloud"}),
        target_view="view3d",
        required=False,
        default_selected=True,
        active=True,
        prerequisites=(),
        producer=point_cloud_3d_producer,
    )
)

validate_registry()
