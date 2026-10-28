"""Tests del analisis estructural 2D y del exportador .ftl (sin AutoCAD).

Cubren el solver contra soluciones exactas de resistencia de materiales, el
modelo real del Golden Gate, el equilibrio global y la ida y vuelta al formato
de FTOOL 4.01.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from autocad_mcp.config import AutoCADMCPConfig
from autocad_mcp.features.ftool import (
    FrameMember,
    FrameModel,
    FrameNode,
    FToolTools,
    Material,
    Section,
    StructuralError,
    _ftl_float,
    _ftl_name,
    _model_info,
    _nan_filter,
    _set_point_load,
    analyze_point_load,
    build_suspension_model,
    equilibrium_check,
    model_to_ftl,
    parse_ftl,
    solve_frame,
    summarize,
    verify_ftl,
)

STEEL = Material("Steel", 2.0e8, 0.3, 78.5, 1.2e-5)
BEAM_SECTION = Section("Beam", 0.01, 1e-3)
EI = STEEL.E * BEAM_SECTION.inertia


def _beam(
    length: float = 10.0,
    *,
    supports: tuple[tuple[bool, bool, bool], ...] = ((True, True, False), (False, True, False)),
    points: tuple[float, ...] = (),
) -> FrameModel:
    """Viga recta con nudos en ``0, length`` y los puntos intermedios dados.

    ``supports`` son los dos extremos; los nudos intermedios quedan libres.
    """
    xs = sorted({0.0, length, *points})
    nodes = []
    for index, x in enumerate(xs):
        if index == 0:
            support = supports[0]
        elif index == len(xs) - 1:
            support = supports[-1]
        else:
            support = (False, False, False)
        nodes.append(FrameNode(x, 0.0, "beam", support))
    members = [FrameMember(index, index + 1, 1, "beam") for index in range(len(nodes) - 1)]
    return FrameModel(
        name="beam",
        nodes=nodes,
        members=members,
        materials=[STEEL],
        sections=[BEAM_SECTION],
    )


def _reaction_items(container: dict[str, Any]) -> list[dict[str, Any]]:
    """Reacciones del solver (lista) o de un resumen (dict por apoyo)."""
    values = container["reactions"]
    return list(values.values()) if isinstance(values, dict) else list(values)


def _reaction_sum(container: dict[str, Any], key: str) -> float:
    return sum(float(item[key]) for item in _reaction_items(container))


# ---------------------------------------------------------------------------
# Solver contra soluciones exactas
# ---------------------------------------------------------------------------
def test_simply_supported_beam_point_load() -> None:
    model = _beam(points=(5.0,))
    model.nodes[1].load = (0.0, -10.0, 0.0)  # 10 kN hacia abajo
    result = solve_frame(model, geometric=False)

    deflection = result["node_displacements"][1 * 3 + 1]
    assert deflection == pytest.approx(-10.0 * 10.0**3 / (48.0 * EI), rel=1e-6)
    assert _reaction_sum(result, "fy") == pytest.approx(10.0, rel=1e-9)
    assert result["reactions"][0]["fy"] == pytest.approx(5.0, rel=1e-9)
    assert result["reactions"][-1]["fy"] == pytest.approx(5.0, rel=1e-9)


def test_cantilever_tip_load_and_rotation() -> None:
    model = _beam(supports=((True, True, True), (False, False, False)))
    model.nodes[-1].load = (0.0, -10.0, 0.0)
    result = solve_frame(model, geometric=False)

    deflection = result["node_displacements"][1 * 3 + 1]
    rotation = result["node_displacements"][1 * 3 + 2]
    assert deflection == pytest.approx(-10.0 * 10.0**3 / (3.0 * EI), rel=1e-6)
    assert rotation == pytest.approx(-10.0 * 10.0**2 / (2.0 * EI), rel=1e-6)
    assert result["reactions"][0]["mz"] == pytest.approx(10.0 * 10.0, rel=1e-6)


def test_fixed_fixed_beam_uniform_load() -> None:
    model = _beam(supports=((True, True, True), (True, True, True)), points=(5.0,))
    for member in model.members:
        member.uniform_load = 10.0  # 10 kN/m hacia abajo

    result = solve_frame(model, geometric=False)
    deflection = result["node_displacements"][1 * 3 + 1]

    assert deflection == pytest.approx(-10.0 * 10.0**4 / (384.0 * EI), rel=1e-6)
    assert _reaction_sum(result, "fy") == pytest.approx(100.0, rel=1e-9)
    assert abs(result["reactions"][0]["mz"]) == pytest.approx(10.0 * 10.0**2 / 12.0, rel=1e-6)
    assert abs(result["reactions"][-1]["mz"]) == pytest.approx(10.0 * 10.0**2 / 12.0, rel=1e-6)

    check = equilibrium_check(model, result)
    assert check["relative_error_fy"] < 1e-9
    assert check["relative_error_mz"] < 1e-9


def test_tension_only_deactivates_compressed_truss() -> None:
    """Un montante articulado que se comprime queda fuera del modelo."""
    model = FrameModel(
        name="prop",
        nodes=[
            FrameNode(0.0, 0.0, "support", (True, True, True)),
            FrameNode(10.0, 0.0, "support", (True, True, True)),
            FrameNode(5.0, 0.0, "deck"),
            FrameNode(5.0, -5.0, "support", (True, True, False)),
        ],
        members=[
            FrameMember(0, 2, 1, "beam", "frame"),
            FrameMember(2, 1, 1, "beam", "frame"),
            FrameMember(2, 3, 1, "prop", "truss"),
        ],
        materials=[STEEL],
        sections=[BEAM_SECTION],
    )
    model.nodes[2].load = (0.0, -10.0, 0.0)

    result = solve_frame(model, geometric=False, tension_only=True)
    assert result["active"] == [True, True, False]
    assert _reaction_sum(result, "fy") == pytest.approx(10.0, rel=1e-6)

    with_prop = solve_frame(model, geometric=False, tension_only=False)
    assert _reaction_sum(with_prop, "fy") == pytest.approx(10.0, rel=1e-6)
    assert max(item["fy"] for item in with_prop["reactions"]) > 0.0


# ---------------------------------------------------------------------------
# Modelo Golden Gate
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def golden_gate() -> FrameModel:
    return build_suspension_model("golden_gate")


def test_golden_gate_topology(golden_gate: FrameModel) -> None:
    info = _model_info(golden_gate)
    assert info["nodes"] == 276
    assert info["members"] == 401
    assert info["members_by_group"] == {"cable": 130, "deck": 142, "hanger": 127, "tower": 2}
    xmin, xmax, ymin, ymax = info["extents"]
    assert (xmin, xmax) == pytest.approx((-1368.5, 1368.5))
    assert (ymin, ymax) == pytest.approx((0.0, 227.0))
    assert info["meta"]["main_span"] == pytest.approx(1280.0)
    assert info["meta"]["sag"] == pytest.approx(143.0)
    assert 0.0 < info["meta"]["side_sag"] < 20.0


def test_golden_gate_member_kinds(golden_gate: FrameModel) -> None:
    for member in golden_gate.members:
        if member.group == "tower":
            assert member.kind == "frame"
        elif member.group in {"cable", "hanger"}:
            assert member.kind == "truss"
    assert all(node.y >= -1e-9 for node in golden_gate.nodes)


def test_golden_gate_anchorages_are_clear_of_pier_supports(golden_gate: FrameModel) -> None:
    """Los anclajes estan al nivel del tablero y 50 mm fuera del apoyo de pila.

    El desfase es obligatorio: FTOOL fusiona nodos a menos de 1 mm y se perderia
    el apoyo de rodillo del tablero en el estribo.
    """
    meta = golden_gate.meta
    assert meta["anchor_offset"] == pytest.approx(0.05)
    anchors = [node for node in golden_gate.nodes if node.support_tag == "anchorage"]
    assert len(anchors) == 2
    for node in anchors:
        assert node.y == pytest.approx(meta["deck_y"])
        assert abs(node.x) == pytest.approx(meta["pier_x"] + meta["anchor_offset"])

    pier_supports = [
        node for node in golden_gate.nodes if node.support_tag == "pier" and abs(node.x) > 900.0
    ]
    for support in pier_supports:
        assert min(abs(support.x - node.x) for node in anchors) > 1e-3
    nearest = min(abs(support.x - node.x) for support in pier_supports for node in anchors)
    assert nearest == pytest.approx(meta["anchor_offset"])


def test_golden_gate_dead_load_state(golden_gate: FrameModel) -> None:
    result = solve_frame(golden_gate, tension_only=False, reference=True)
    summary = summarize(golden_gate, result)

    assert summary["max_deck_deflection"] < 0.5
    assert 4.0e5 < summary["cable_tension_max"] < 5.2e5
    assert summary["hanger_tension_max"] > 0.0
    assert summary["reactions"]["tower_base"]["fy"] > 1.0e6
    assert summary["equilibrium"]["relative_error_fy"] < 1e-6
    assert summary["equilibrium"]["relative_error_mz"] < 1e-5


def test_golden_gate_dead_load_has_no_compressed_hangers(golden_gate: FrameModel) -> None:
    """Con el anclaje a nivel del tablero no aparecen compresiones falsas."""
    result = solve_frame(golden_gate, tension_only=False, reference=True)
    summary = summarize(golden_gate, result)

    assert summary["slack_hangers"] == 0
    compressed = [
        index
        for index, member in enumerate(golden_gate.members)
        if member.group == "hanger" and float(result["forces"][index]["axial"]) <= 0.0
    ]
    assert compressed == []
    assert all(result["active"])


def test_golden_gate_point_load_increment(golden_gate: FrameModel) -> None:
    analysis = analyze_point_load(golden_gate, x=0.0, magnitude=1000.0)
    live = analysis["point_load"]

    assert 0.05 < live["max_deck_deflection"] < 0.30
    assert live["load"]["deflection_at_load"] == pytest.approx(
        -live["max_deck_deflection"], rel=1e-3
    )
    assert 1.0e3 < live["cable_tension_max"] < 3.0e3
    assert 0.0 < live["hanger_tension_max"] < 300.0
    assert _reaction_sum(analysis["dead_load"], "fy") > 0.0
    assert sum(item["fy"] for item in live["reactions"].values()) == pytest.approx(1000.0, abs=1.0)
    assert live["equilibrium"]["relative_error_fy"] < 1e-6

    combined = analysis["combined"]
    assert combined["cable_tension_max"] > live["cable_tension_max"]
    assert combined["reactions"]["tower_base"]["fy"] > live["reactions"]["tower_base"]["fy"]


def test_point_load_off_center_deflects_less(golden_gate: FrameModel) -> None:
    center = analyze_point_load(golden_gate, x=0.0, magnitude=500.0)
    tower = analyze_point_load(golden_gate, x=640.0, magnitude=500.0)
    assert tower["point_load"]["max_deck_deflection"] < center["point_load"]["max_deck_deflection"]
    assert tower["point_load"]["load"]["x"] == pytest.approx(640.0, abs=1.0)


def test_negative_point_load_is_rejected(golden_gate: FrameModel) -> None:
    with pytest.raises(StructuralError):
        analyze_point_load(golden_gate, magnitude=-10.0)


# ---------------------------------------------------------------------------
# Formato .ftl
# ---------------------------------------------------------------------------
def test_ftl_floats_use_ftool_format() -> None:
    assert _ftl_float(4.0) == "+4.00000e+000"
    assert _ftl_float(-0.0) == "+0.00000e+000"
    with pytest.raises(StructuralError):
        _ftl_float(float("nan"))


def test_nan_filter_normalizes_negative_zero() -> None:
    assert _nan_filter(-0.0) == 0.0
    assert str(_nan_filter(-0.0)) == "0.0"
    assert _nan_filter(-1e-9) == 0.0
    assert _nan_filter(float("nan")) == 0.0
    assert _nan_filter(12.34567, 2) == 12.35


def test_ftl_names_are_ascii_and_single_line() -> None:
    assert _ftl_name("Acero A36 n") == "Acero A36 n"
    assert _ftl_name("  Seccion   dnica  ") == "Seccion dnica"
    assert _ftl_name("Año 'A36'") == "Ano A36"
    assert _ftl_name("") == "unnamed"


def test_model_to_ftl_header_and_single_load_case() -> None:
    text = model_to_ftl(_beam())
    lines = text.splitlines()
    assert lines[0] == "401 0"
    assert lines[2] == "1"
    assert lines[16] == "1"  # un unico caso de carga
    assert lines[17].startswith("'")
    assert text.endswith(" 0\n")
    assert text.isascii()


def test_ftl_round_trip_small_model() -> None:
    model = _beam(points=(4.0, 6.0))
    model.nodes[1].load = (0.0, -25.0, 0.0)
    model.nodes[2].support = (False, True, False)
    for member in model.members:
        member.uniform_load = 3.5

    report = verify_ftl(model)
    assert report["ok"] is True
    assert report["differences"] == []
    assert report["nodes"] == 4
    assert report["members"] == 3
    assert report["merged_nodes"] == 0
    assert report["origin_offset"] == [0.0, 0.0]


def test_ftl_round_trip_merges_coincident_nodes() -> None:
    model = _beam(supports=((True, True, True), (True, True, True)))
    model.nodes[1].load = (0.0, -10.0, 0.0)
    model.nodes.insert(2, FrameNode(10.0, 0.0, "extra", (False, True, False)))
    model.members.append(FrameMember(1, 2, 1, "beam"))

    report = verify_ftl(model)
    assert report["ok"] is True
    assert report["merged_nodes"] == 1
    assert report["nodes"] == 2


def test_ftl_carries_point_load_with_ftool_sign() -> None:
    model = build_suspension_model("golden_gate")
    index, applied_x = _set_point_load(model, 0.0, 1000.0)
    assert applied_x == pytest.approx(0.0)

    text = model_to_ftl(model)
    assert "'Nodal' 0 1000 0" in text
    report = verify_ftl(model)
    assert report["ok"] is True

    parsed = parse_ftl(text)
    offset_x, offset_y = report["origin_offset"]
    target_x = model.nodes[index].x - offset_x
    target_y = model.nodes[index].y - offset_y
    loaded = [
        node
        for node in parsed.nodes
        if abs(node.x - target_x) < 1e-3 and abs(node.y - target_y) < 1e-3
    ]
    assert len(loaded) == 1
    assert loaded[0].load[1] == pytest.approx(-1000.0, abs=0.05)
    assert index < len(model.nodes)


def test_ftl_round_trip_golden_gate(golden_gate: FrameModel) -> None:
    report = verify_ftl(golden_gate)
    assert report["ok"] is True
    assert report["nodes"] == 276
    assert report["members"] == 401
    assert report["lines"] > 5000
    assert report["origin_offset"] == pytest.approx([-1368.5, 67.0])


def test_ftl_rejects_non_ftool_text() -> None:
    with pytest.raises(StructuralError):
        parse_ftl("no es un ftl\n" * 50)


def test_ftl_requires_materials_and_sections() -> None:
    model = _beam()
    model.materials = []
    model.sections = []
    with pytest.raises(StructuralError):
        model_to_ftl(model)


# ---------------------------------------------------------------------------
# Herramientas MCP
# ---------------------------------------------------------------------------
def _ftool_tools(tmp_path: Path, exe: str = "") -> FToolTools:
    config = AutoCADMCPConfig(ftool_exe=exe, ftool_output_dir=str(tmp_path))
    return FToolTools(config)


def test_ftool_status_reports_format_and_output_dir(tmp_path: Path) -> None:
    status = _ftool_tools(tmp_path).status()
    assert status["success"] is True
    assert status["format"] == "FTL 4.01"
    assert status["output_dir"] == str(tmp_path)
    assert isinstance(status["installed"], bool)
    assert status["limitations"]


def test_ftool_status_accepts_missing_configured_exe(tmp_path: Path) -> None:
    status = _ftool_tools(tmp_path, exe=str(tmp_path / "no-existe.exe")).status()
    assert status["installed"] is False
    assert status["configured_exe"].endswith("no-existe.exe")


def test_export_ftool_model_writes_verified_file(tmp_path: Path) -> None:
    tools = _ftool_tools(tmp_path)
    report = tools.export_model(load_x=0.0, load_kN=500.0)

    path = Path(report["path"])
    assert path.is_file()
    assert path.parent == tmp_path
    assert path.name == "Golden-Gate-modelo-2D.ftl"
    assert report["verified"]["ok"] is True
    assert report["model"]["nodes"] == 276
    assert report["load"] == {"x": 0.0, "kN": 500.0}
    assert path.read_text(encoding="utf-8").endswith(" 0\n")


def test_export_ftool_model_respects_explicit_path(tmp_path: Path) -> None:
    tools = _ftool_tools(tmp_path)
    target = tmp_path / "custom" / "bridge.ftl"
    report = tools.export_model(path=str(target))
    assert Path(report["path"]) == target.resolve()
    assert target.is_file()


def test_analyze_bridge_load_returns_reactions_and_notes(tmp_path: Path) -> None:
    report = _ftool_tools(tmp_path).analyze_load(x=0.0, magnitude=1000.0)
    assert report["success"] is True
    assert report["point_load"]["max_deck_deflection"] > 0.0
    assert report["ftool"]["installed"] in (True, False)
    assert "solver interno" in report["ftool"]["note"]
    json.dumps(report)  # el handler debe devolver JSON serializable
