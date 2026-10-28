"""Tests del modelado 3D (sin AutoCAD).

Cubren la matematica de alineacion de primitivas y la validacion previa a COM.
Las convenciones verificadas contra AutoCAD 2026 estan documentadas en
``autocad_mcp.features.solids``.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from autocad_mcp.features.solids import (
    AC_INTERSECTION,
    AC_SUBTRACTION,
    AC_UNION,
    BOOLEAN_OPERATIONS,
    SolidTools,
    box_angles,
    cylinder_angles,
)


class _FakeDoc:
    def HandleToObject(self, handle: str) -> Any:  # noqa: ARG002
        raise RuntimeError("handle inexistente")


class _FakeConn:
    def __init__(self) -> None:
        self.doc = _FakeDoc()

    def ensure(self) -> bool:
        return True

    def model_space(self) -> Any:
        raise AssertionError("no deberia tocar el ModelSpace")

    def regen(self) -> None:
        pass


def _tools() -> SolidTools:
    return SolidTools(_FakeConn())  # type: ignore[arg-type]


def test_boolean_enum_matches_autocad_late_binding() -> None:
    # Verificado en AutoCAD 2026: 0=union, 1=interseccion, 2=resta.
    assert (AC_UNION, AC_INTERSECTION, AC_SUBTRACTION) == (0, 1, 2)
    assert BOOLEAN_OPERATIONS["union"] == 0
    assert BOOLEAN_OPERATIONS["intersection"] == 1
    assert BOOLEAN_OPERATIONS["subtraction"] == 2


def test_cylinder_angles_vertical_points_up() -> None:
    length, az, theta = cylinder_angles([0, 0, 0], [0, 0, 10])
    assert length == pytest.approx(10.0)
    assert az == pytest.approx(0.0)
    assert theta == pytest.approx(0.0)


def test_cylinder_angles_along_x_needs_90_degrees() -> None:
    length, az, theta = cylinder_angles([0, 0, 0], [10, 0, 0])
    assert length == pytest.approx(10.0)
    assert az == pytest.approx(0.0)
    assert theta == pytest.approx(math.pi / 2)


def test_cylinder_angles_along_y_has_azimuth() -> None:
    _, az, theta = cylinder_angles([0, 0, 0], [0, 10, 0])
    assert az == pytest.approx(math.pi / 2)
    assert theta == pytest.approx(math.pi / 2)


def test_box_angles_diagonal_has_elevation() -> None:
    length, az, el = box_angles([0, 0, 0], [10, 0, 10])
    assert length == pytest.approx(math.sqrt(200))
    assert az == pytest.approx(0.0)
    assert el == pytest.approx(math.pi / 4)


def test_angles_reject_degenerate_segment() -> None:
    with pytest.raises(ValueError):
        cylinder_angles([1, 1, 1], [1, 1, 1])
    with pytest.raises(ValueError):
        box_angles([0, 0], [0, 0])


def test_box_solid_rejects_non_positive_dimensions() -> None:
    result = _tools().create_box_solid([0, 0, 0], 0.0, 1.0, 1.0)
    assert result["success"] is False
    assert "length" in result["error"]

    result = _tools().create_box_solid([0, 0, 0], 1.0, -1.0, 1.0)
    assert result["success"] is False
    assert "width" in result["error"]


def test_cylinder_between_rejects_identical_points() -> None:
    result = _tools().create_cylinder_between([0, 0, 0], [0, 0, 0], 0.5)
    assert result["success"] is False
    assert "coinciden" in result["error"]


def test_cylinder_between_rejects_zero_radius() -> None:
    result = _tools().create_cylinder_between([0, 0, 0], [1, 0, 0], 0.0)
    assert result["success"] is False
    assert "radius" in result["error"]


def test_extrude_polygon_requires_three_points() -> None:
    result = _tools().extrude_polygon([[0, 0], [1, 0]], 2.0)
    assert result["success"] is False
    assert "3 puntos" in result["error"]


def test_boolean_rejects_unknown_operation() -> None:
    result = _tools().boolean_solids("A1", "A2", "merge")
    assert result["success"] is False
    assert "merge" in result["error"]


def test_move_solid_reports_missing_handle() -> None:
    result = _tools().move_solid("ZZ", [0, 0, 0], [1, 0, 0])
    assert result["success"] is False
    assert "handle" in result["error"]


def test_copy_solid_rejects_invalid_count_and_missing_handle() -> None:
    result = _tools().copy_solid("ZZ", [1, 0, 0], count=0)
    assert result["success"] is False
    assert "count" in result["error"]

    result = _tools().copy_solid("ZZ", [1, 0, 0])
    assert result["success"] is False
    assert "handle" in result["error"]


def test_array_solids_rejects_invalid_count() -> None:
    result = _tools().array_solids("ZZ", 0, [1, 0, 0])
    assert result["success"] is False
    assert "count" in result["error"]


def test_scale_solid_rejects_non_positive_factor() -> None:
    result = _tools().scale_solid("ZZ", [0, 0, 0], 0.0)
    assert result["success"] is False
    assert "factor" in result["error"]

    result = _tools().scale_solid("ZZ", [0, 0, 0], -2.0)
    assert result["success"] is False
    assert "factor" in result["error"]


def test_batch_defers_regen() -> None:
    tools = _tools()
    calls = {"regen": 0}

    def regen() -> None:
        calls["regen"] += 1

    tools.conn.regen = regen  # type: ignore[method-assign]
    with tools.batch():
        assert tools._defer is True
    assert calls["regen"] == 1
    assert tools._defer is False
