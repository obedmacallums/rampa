"""T002: registry validation, selection closure, topo order (data-model.md, R8)."""

import pytest

from pipeline import options as options_mod


def _opt(id_, *, input_types=frozenset({"t"}), prerequisites=(), required=False, active=True):
    return options_mod.OptionSpec(
        id=id_,
        label_key=f"options.{id_}.label",
        description_key=f"options.{id_}.description",
        input_types=input_types,
        target_view="map2d",
        required=required,
        default_selected=False,
        active=active,
        prerequisites=prerequisites,
    )


@pytest.fixture
def fresh_registry(monkeypatch):
    monkeypatch.setattr(options_mod, "_options", {})
    monkeypatch.setattr(options_mod, "_input_types", {})
    options_mod.register_input_type(options_mod.InputTypeSpec(id="t", label_key="input_types.t"))
    return options_mod


def test_duplicate_option_id_rejected(fresh_registry):
    fresh_registry.register_option(_opt("a"))
    with pytest.raises(fresh_registry.RegistryError):
        fresh_registry.register_option(_opt("a"))


def test_duplicate_input_type_id_rejected(fresh_registry):
    with pytest.raises(fresh_registry.RegistryError):
        fresh_registry.register_input_type(options_mod.InputTypeSpec(id="t", label_key="x"))


def test_prerequisite_cycle_rejected(fresh_registry):
    fresh_registry.register_option(_opt("a", prerequisites=("b",)))
    fresh_registry.register_option(_opt("b", prerequisites=("a",)))
    with pytest.raises(fresh_registry.RegistryError, match="cycle"):
        fresh_registry.validate_registry()


def test_unknown_prerequisite_rejected(fresh_registry):
    fresh_registry.register_option(_opt("a", prerequisites=("ghost",)))
    with pytest.raises(fresh_registry.RegistryError):
        fresh_registry.validate_registry()


def test_input_type_mismatch_rejected(fresh_registry):
    fresh_registry.register_input_type(options_mod.InputTypeSpec(id="other", label_key="x"))
    fresh_registry.register_option(_opt("base", input_types=frozenset({"other"})))
    fresh_registry.register_option(
        _opt("dependent", prerequisites=("base",), input_types=frozenset({"t"}))
    )
    with pytest.raises(fresh_registry.RegistryError):
        fresh_registry.validate_registry()


def test_effective_selection_adds_required_and_closure(fresh_registry):
    fresh_registry.register_option(_opt("req", required=True))
    fresh_registry.register_option(_opt("base"))
    fresh_registry.register_option(_opt("dep", prerequisites=("base",)))
    fresh_registry.validate_registry()

    result = fresh_registry.effective_selection("t", ["dep"])

    assert set(result) == {"req", "base", "dep"}
    assert result.index("base") < result.index("dep")


def test_effective_selection_rejects_unknown_id(fresh_registry):
    fresh_registry.register_option(_opt("req", required=True))
    with pytest.raises(fresh_registry.InvalidSelectionError) as exc_info:
        fresh_registry.effective_selection("t", ["nope"])
    assert exc_info.value.invalid_ids == ["nope"]


def test_effective_selection_rejects_inactive_id(fresh_registry):
    fresh_registry.register_option(_opt("inactive_opt", active=False))
    with pytest.raises(fresh_registry.InvalidSelectionError):
        fresh_registry.effective_selection("t", ["inactive_opt"])


def test_effective_selection_rejects_inapplicable_id(fresh_registry):
    fresh_registry.register_input_type(options_mod.InputTypeSpec(id="other", label_key="x"))
    fresh_registry.register_option(_opt("other_opt", input_types=frozenset({"other"})))
    with pytest.raises(fresh_registry.InvalidSelectionError):
        fresh_registry.effective_selection("t", ["other_opt"])


def test_effective_selection_unknown_input_type(fresh_registry):
    with pytest.raises(fresh_registry.UnknownInputTypeError):
        fresh_registry.effective_selection("ghost", [])


def test_topo_order_prerequisites_first(fresh_registry):
    fresh_registry.register_option(_opt("base"))
    fresh_registry.register_option(_opt("mid", prerequisites=("base",)))
    fresh_registry.register_option(_opt("top", prerequisites=("mid",)))
    fresh_registry.validate_registry()

    order = fresh_registry.topo_order(["top", "mid", "base"])

    assert order.index("base") < order.index("mid") < order.index("top")


def test_initial_catalog_matches_r8():
    point_cloud_options = {opt.id: opt for opt in options_mod.options_for("point_cloud")}

    assert set(point_cloud_options) == {"elevation", "hillshade", "point_cloud_3d"}

    elevation = point_cloud_options["elevation"]
    assert elevation.required is True
    assert elevation.target_view == "map2d"
    assert elevation.prerequisites == ()

    hillshade = point_cloud_options["hillshade"]
    assert hillshade.required is False
    assert hillshade.prerequisites == ("elevation",)
    assert hillshade.target_view == "map2d"

    point_cloud_3d = point_cloud_options["point_cloud_3d"]
    assert point_cloud_3d.required is False
    assert point_cloud_3d.target_view == "view3d"
    assert point_cloud_3d.prerequisites == ()

    for opt in point_cloud_options.values():
        assert opt.default_selected is True
        assert opt.active is True
