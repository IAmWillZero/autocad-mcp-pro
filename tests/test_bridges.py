"""Tests del generador de puentes (sin AutoCAD).

Verifican el preset real, la validacion de la geometria y la forma de la catenaria.
"""

from __future__ import annotations

from typing import Any

import pytest

from autocad_mcp.features.bridges import (
    KINDS,
    PRESETS,
    BridgeResult,
    BridgeSpec,
    BridgeTools,
    cable_points,
    material_breakdown,
)


class _FakeConn:
    doc = None

    def ensure(self) -> bool:
        return True

    def model_space(self) -> Any:
        raise AssertionError("no deberia tocar el ModelSpace")

    def regen(self) -> None:
        pass


def _tools() -> BridgeTools:
    return BridgeTools(_FakeConn())  # type: ignore[arg-type]


def test_golden_gate_preset_has_real_dimensions() -> None:
    preset = PRESETS["golden_gate"]
    assert preset["kind"] == "suspension"
    assert preset["total_length"] == pytest.approx(2737.0)
    assert preset["main_span"] == pytest.approx(1280.0)
    assert preset["side_span"] == pytest.approx(343.0)
    assert preset["deck_width"] == pytest.approx(27.4)
    assert preset["tower_height"] == pytest.approx(227.0)
    assert preset["cable_sag"] == pytest.approx(143.0)
    assert preset["cable_diameter"] == pytest.approx(0.92)


def test_preset_fills_spec_and_overrides_apply() -> None:
    tools = _tools()
    spec = tools._build_spec(preset="golden_gate")
    assert spec.kind == "suspension"
    assert spec.total_length == pytest.approx(2737.0)
    assert spec.deck_top == pytest.approx(74.6)

    custom = tools._build_spec(preset="golden_gate", deck_width=30.0, name="OTRO")
    assert custom.deck_width == pytest.approx(30.0)
    assert custom.name == "OTRO"
    assert custom.total_length == pytest.approx(2737.0)


def test_unknown_kwargs_are_ignored() -> None:
    spec = _tools()._build_spec(total_length=100.0, not_a_field=5)
    assert spec.total_length == pytest.approx(100.0)


def test_validate_accepts_golden_gate() -> None:
    spec = BridgeSpec(**PRESETS["golden_gate"])
    assert spec.validate() is None


def test_validate_rejects_unknown_kind() -> None:
    spec = BridgeSpec(kind="teleferico")
    assert "kind invalido" in str(spec.validate())


def test_validate_rejects_spans_exceeding_length() -> None:
    spec = BridgeSpec(
        kind="suspension",
        total_length=1000.0,
        main_span=900.0,
        side_span=200.0,
        tower_height=150.0,
        cable_sag=30.0,
    )
    assert "excede" in str(spec.validate())


def test_validate_rejects_sag_above_deck() -> None:
    spec = BridgeSpec(
        kind="suspension",
        total_length=500.0,
        main_span=300.0,
        side_span=50.0,
        clearance=50.0,
        deck_depth=2.0,
        tower_height=60.0,
        cable_sag=20.0,
    )
    assert "cable_sag" in str(spec.validate())


def test_validate_rejects_tower_below_deck() -> None:
    spec = BridgeSpec(
        kind="suspension",
        total_length=500.0,
        main_span=300.0,
        side_span=50.0,
        clearance=50.0,
        deck_depth=2.0,
        tower_height=40.0,
        cable_sag=5.0,
    )
    assert "tower_height" in str(spec.validate())


def test_all_kinds_build_without_com() -> None:
    tools = _tools()
    for kind in KINDS:
        spec = tools._build_spec(kind=kind)
        assert spec.validate() is None
        assert spec.kind == kind


def test_create_bridge_rejects_bad_preset() -> None:
    result = _tools().create_bridge(preset="golden_gate_2")
    assert result["success"] is False
    assert "preset" in result["error"]


def test_create_bridge_rejects_invalid_geometry() -> None:
    result = _tools().create_bridge(kind="girder", total_length=-5)
    assert result["success"] is False
    assert "total_length" in result["error"]


def test_main_cable_is_symmetric_with_correct_sag() -> None:
    tools = _tools()
    spec = BridgeSpec(**PRESETS["golden_gate"])
    half = spec.main_span / 2
    samples = tools._main_cable(spec, half, spec.tower_height)

    assert samples[0][0] == pytest.approx(-half)
    assert samples[-1][0] == pytest.approx(half)
    assert samples[0][1] == pytest.approx(spec.tower_height)
    assert samples[-1][1] == pytest.approx(spec.tower_height)
    assert samples[len(samples) // 2][1] == pytest.approx(spec.tower_height - spec.cable_sag)

    # Simetria respecto al centro del vano.
    for left, right in zip(samples, reversed(samples), strict=True):
        assert left[1] == pytest.approx(right[1])


def test_pylon_positions_symmetric() -> None:
    tools = _tools()
    spec = BridgeSpec(kind="cable_stayed", pylons=2, main_span=400.0, total_length=600.0)
    positions = tools._pylon_positions(spec)
    assert positions == pytest.approx([-200.0, 200.0])

    single = tools._pylon_positions(BridgeSpec(kind="cable_stayed", pylons=1))
    assert single == pytest.approx([0.0])


def test_bridge_result_ignores_failures() -> None:
    result = BridgeResult()
    result.add({"success": False, "error": "x"})
    assert result.handles == []
    assert result.volume == 0.0

    result.add({"success": True, "handles": ["A1"], "volume": 2.5})
    result.add({"success": True, "handles": ["A2"], "volume": None})
    assert result.handles == ["A1", "A2"]
    assert result.volume == pytest.approx(2.5)


class _Recorder:
    """Sustituto de SolidTools que solo registra la geometria pedida."""

    def __init__(self) -> None:
        self.boxes: list[dict[str, Any]] = []
        self.beams: list[dict[str, Any]] = []
        self.cylinders: list[dict[str, Any]] = []

    def create_box_solid(self, center, length, width, height, layer, color="bylayer", rotation=0.0):  # type: ignore[no-untyped-def]  # noqa: ANN001, ANN201, ARG002
        self.boxes.append(
            {"center": center, "length": length, "width": width, "height": height, "layer": layer}
        )
        return {"success": True, "handles": ["B"], "volume": 1.0}

    def create_box_between(self, start, end, width, depth, layer, color="bylayer"):  # type: ignore[no-untyped-def]  # noqa: ANN001, ANN201, ARG002
        self.beams.append(
            {"start": start, "end": end, "width": width, "depth": depth, "layer": layer}
        )
        return {"success": True, "handles": ["D"], "volume": 0.5}

    def create_cylinder_between(self, start, end, radius, layer, color="bylayer"):  # type: ignore[no-untyped-def]  # noqa: ANN001, ANN201, ARG002
        self.cylinders.append({"start": start, "end": end, "radius": radius, "layer": layer})
        return {"success": True, "handles": ["C"], "volume": 0.2}


def _recording_tools() -> tuple[BridgeTools, _Recorder]:
    recorder = _Recorder()
    return BridgeTools(_FakeConn(), solids=recorder), recorder  # type: ignore[arg-type]


def test_truss_adds_posts_and_diagonals_on_both_faces() -> None:
    tools, recorder = _recording_tools()
    spec = BridgeSpec(**PRESETS["golden_gate"])
    tools._truss(spec)

    panels = int(spec.total_length / spec.suspender_spacing)
    assert len(recorder.boxes) == 2 * panels
    assert len(recorder.beams) == 2 * panels
    # Los montantes van del fondo del tablero a la cara superior.
    assert recorder.boxes[0]["height"] == pytest.approx(spec.deck_depth)
    # La primera diagonal arranca abajo y termina arriba.
    first = recorder.beams[0]
    assert first["start"][2] == pytest.approx(spec.clearance)
    assert first["end"][2] == pytest.approx(spec.deck_top)


def test_tower_has_legs_braces_and_x_bracing() -> None:
    tools, recorder = _recording_tools()
    spec = BridgeSpec(**PRESETS["golden_gate"])
    tools._tower(0.0, spec)

    legs_and_struts = 6 * 2 + 7
    assert len(recorder.boxes) == legs_and_struts
    assert len(recorder.beams) == 6 * 2
    # La torre llega a la altura real.
    assert max(box["center"][2] + box["height"] / 2 for box in recorder.boxes) == pytest.approx(
        spec.tower_height
    )


def test_beam_between_applies_bridge_origin() -> None:
    tools, recorder = _recording_tools()
    tools._off = (100.0, 200.0, 300.0)
    tools._beam_between([0, 0, 0], [10, 0, 0], 0.3, 0.3, "S-VIGAS")

    beam = recorder.beams[0]
    assert beam["start"] == pytest.approx([100.0, 200.0, 300.0])
    assert beam["end"] == pytest.approx([110.0, 200.0, 300.0])


def test_material_breakdown_converts_volume_to_tonnes() -> None:
    report = material_breakdown(
        {
            "S-TABLERO": {"count": 2, "volume": 100.0},
            "S-VIGAS": {"count": 1, "volume": 10.0},
            "S-PAVIMENTO": {"count": 1, "volume": 5.0},
        }
    )
    assert set(report) == {"hormigon", "acero", "asfalto"}
    assert report["hormigon"]["volume_m3"] == pytest.approx(100.0)
    assert report["hormigon"]["mass_t"] == pytest.approx(240.0)
    assert report["acero"]["mass_t"] == pytest.approx(78.5)
    assert report["asfalto"]["mass_t"] == pytest.approx(12.0)
    assert report["hormigon"]["layers"] == ["S-TABLERO"]


def test_cable_points_are_symmetric_with_parabolic_sag() -> None:
    points = cable_points([0, 0, 20], [100, 0, 20], sag=10, samples=10)
    assert len(points) == 11
    assert points[0] == pytest.approx([0, 0, 20])
    assert points[-1] == pytest.approx([100, 0, 20])
    assert points[5][2] == pytest.approx(10.0)
    assert points[2][2] == pytest.approx(points[8][2])


def test_cable_points_reject_invalid_input() -> None:
    with pytest.raises(ValueError, match="samples"):
        cable_points([0, 0, 0], [1, 0, 0], samples=0)
    with pytest.raises(ValueError, match="sag"):
        cable_points([0, 0, 0], [1, 0, 0], sag=-1)
    with pytest.raises(ValueError, match="coinciden"):
        cable_points([0, 0, 0], [0, 0, 0])


def test_create_cable_validates_without_com() -> None:
    tools = _tools()
    assert tools.create_cable([0, 0, 0], [1, 0, 0], diameter=0)["success"] is False
    invalid = tools.create_cable([0, 0, 0], [0, 0, 0])
    assert invalid["success"] is False
    assert "coinciden" in invalid["error"]


def test_list_bridge_presets_exposes_real_dimensions() -> None:
    presets = _tools().list_bridge_presets()
    assert presets["success"] is True
    assert presets["kinds"] == list(KINDS)
    golden = next(p for p in presets["presets"] if p["preset"] == "golden_gate")
    assert golden["name"] == "GOLDEN GATE"
    assert golden["total_length"] == pytest.approx(2737.0)
    assert golden["description"]


def test_suspender_has_double_rope_and_clamp() -> None:
    tools, recorder = _recording_tools()
    tools._suspender(10.0, 100.0, 74.6, 12.9)
    assert len(recorder.cylinders) == 2
    assert {round(c["start"][1], 2) for c in recorder.cylinders} == {12.55, 13.25}
    assert len(recorder.boxes) == 1
    assert recorder.boxes[0]["layer"] == "S-CABLES"


def test_deck_has_asphalt_median_and_sidewalks() -> None:
    tools, recorder = _recording_tools()
    spec = BridgeSpec(**PRESETS["golden_gate"])
    tools._deck(spec)
    layers = [box["layer"] for box in recorder.boxes]
    assert layers.count("S-PAVIMENTO") >= 4
    assert layers.count("S-TABLERO") >= 4
    pave = [box for box in recorder.boxes if box["layer"] == "S-PAVIMENTO"]
    assert all(box["center"][2] == pytest.approx(spec.deck_top + 0.04) for box in pave[:2])


def test_cross_frames_and_bracing_add_transverse_members() -> None:
    tools, recorder = _recording_tools()
    spec = BridgeSpec(**PRESETS["golden_gate"])
    tools._cross_frames(spec)
    frames = len(recorder.beams)
    assert frames > 0
    tools._bottom_bracing(spec)
    assert len(recorder.beams) > frames


def test_railings_and_streetlights_use_equipment_layer() -> None:
    tools, recorder = _recording_tools()
    spec = BridgeSpec(**PRESETS["golden_gate"])
    tools._railings(spec)
    railings = len(recorder.boxes)
    tools._streetlights(spec)
    assert railings > 100
    assert len(recorder.boxes) > railings
    assert len(recorder.cylinders) > 0
    assert {box["layer"] for box in recorder.boxes} == {"S-EQUIPAMIENTO"}


def test_tower_caps_and_fenders() -> None:
    tools, recorder = _recording_tools()
    spec = BridgeSpec(**PRESETS["golden_gate"])
    tools._tower_caps(0.0, spec)
    assert len(recorder.boxes) == 5
    assert max(box["center"][2] + box["height"] / 2 for box in recorder.boxes) > spec.tower_height

    recorder.boxes.clear()
    tools._fenders(spec)
    assert len(recorder.boxes) == 8


def test_fort_point_arch_is_asymmetric_and_has_spandrels() -> None:
    tools, recorder = _recording_tools()
    spec = BridgeSpec(**PRESETS["golden_gate"])
    tools._fort_point_arch(spec)
    assert len(recorder.beams) > 30
    assert all(beam["start"][0] > spec.main_span / 2 for beam in recorder.beams)
    assert recorder.boxes


def test_expansion_joints_do_not_extend_bridge_length() -> None:
    tools, recorder = _recording_tools()
    spec = BridgeSpec(**PRESETS["golden_gate"])
    tools._expansion_joints(spec)
    half = spec.total_length / 2
    for box in recorder.boxes:
        x0 = box["center"][0] - box["length"] / 2
        x1 = box["center"][0] + box["length"] / 2
        assert x0 >= -half - 1e-6
        assert x1 <= half + 1e-6
    assert len(recorder.boxes) == 6


def test_detail_defaults_to_none_and_validates() -> None:
    spec = BridgeSpec()
    assert spec.detail == "none"
    assert spec.max_fasteners == 1200
    assert BridgeSpec(detail="members").validate() is None
    assert BridgeSpec(detail="bolted", max_fasteners=0).validate() is None
    assert "detail invalido" in str(BridgeSpec(detail="extremo").validate())
    assert "max_fasteners" in str(BridgeSpec(max_fasteners=-1).validate())


def test_detail_none_adds_no_steel_detail() -> None:
    tools, recorder = _recording_tools()
    tools._steel_details(BridgeSpec(**PRESETS["golden_gate"]))
    assert recorder.boxes == []
    assert recorder.beams == []
    assert recorder.cylinders == []


def test_members_detail_builds_i_beams_plates_and_stiffeners() -> None:
    tools, recorder = _recording_tools()
    spec = BridgeSpec(**PRESETS["golden_gate"], detail="members")
    tools._fastener_cap = spec.max_fasteners
    tools._steel_details(spec)

    layers = [box["layer"] for box in recorder.boxes]
    assert layers.count("S-PLACAS") > 200
    assert layers.count("S-RIGIDIZADORES") > 20
    assert "S-PERNOS" not in layers
    assert recorder.cylinders == []
    # Vigas I = 3 cajas por viga; hay varias alas y almas bajo la losa.
    stringers = [box for box in recorder.boxes if box["layer"] == "S-PLACAS"]
    assert len(stringers) >= 24


def test_bolted_detail_respects_fastener_cap() -> None:
    tools, recorder = _recording_tools()
    spec = BridgeSpec(**PRESETS["golden_gate"], detail="bolted", max_fasteners=25)
    tools._fastener_cap = spec.max_fasteners
    tools._fasteners = 0
    tools._steel_details(spec)

    assert tools._fasteners == 25
    assert len(recorder.cylinders) == 25
    assert all(item["layer"] == "S-PERNOS" for item in recorder.cylinders)


def test_bolted_detail_generates_fasteners_by_default() -> None:
    tools, recorder = _recording_tools()
    spec = BridgeSpec(**PRESETS["golden_gate"], detail="bolted")
    tools._fastener_cap = spec.max_fasteners
    tools._fasteners = 0
    tools._steel_details(spec)

    assert 200 < tools._fasteners <= spec.max_fasteners
    assert len(recorder.cylinders) == tools._fasteners


def test_suspension_suspenders_use_both_cable_sides_without_duplicates() -> None:
    tools, recorder = _recording_tools()
    spec = BridgeSpec(**PRESETS["golden_gate"], detail="bolted", max_fasteners=5000)
    tools._fastener_cap = spec.max_fasteners
    tools._build_suspension(spec)

    bolts = [item for item in recorder.cylinders if item["layer"] == "S-PERNOS"]
    left = [item for item in bolts if (item["start"][1] + item["end"][1]) / 2 < 0]
    right = [item for item in bolts if (item["start"][1] + item["end"][1]) / 2 > 0]
    assert len(left) == len(right) > 100
    keys = {
        (
            tuple(round(value, 4) for value in item["start"]),
            tuple(round(value, 4) for value in item["end"]),
        )
        for item in bolts
    }
    assert len(keys) == len(bolts)


def test_suspender_detail_adds_band_sockets_and_bolts() -> None:
    tools, recorder = _recording_tools()
    members = BridgeSpec(**PRESETS["golden_gate"], detail="members")
    tools._suspender(10.0, 100.0, 74.6, 12.9, spec=members)

    plates = [box for box in recorder.boxes if box["layer"] == "S-PLACAS"]
    assert len(plates) == 6
    # Dos cables gemelos + dos pasadores de los sockets.
    assert len(recorder.cylinders) == 4

    recorder.boxes.clear()
    recorder.cylinders.clear()
    bolted = BridgeSpec(**PRESETS["golden_gate"], detail="bolted", max_fasteners=10)
    tools._fastener_cap = bolted.max_fasteners
    tools._fasteners = 0
    tools._suspender(10.0, 100.0, 74.6, 12.9, spec=bolted)
    assert tools._fasteners == 2
    assert [item["layer"] for item in recorder.cylinders].count("S-PERNOS") == 2
