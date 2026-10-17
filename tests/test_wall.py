"""Tests del offset de eje de muro (geometria pura, sin AutoCAD)."""

from __future__ import annotations

from autocad_mcp.features.geometry import GeometryTools


def _round(points: list[list[float]]) -> list[tuple[float, float]]:
    return [(round(x, 6), round(y, 6)) for x, y in points]


def test_offset_open_line() -> None:
    out = GeometryTools._offset_polyline([(0.0, 0.0), (2.0, 0.0)], 0.5, closed=False)
    assert _round(out) == [(0.0, 0.5), (2.0, 0.5)]


def test_offset_open_right_angle_miters_corner() -> None:
    out = GeometryTools._offset_polyline([(0.0, 0.0), (2.0, 0.0), (2.0, 2.0)], 0.5, closed=False)
    assert _round(out) == [(0.0, 0.5), (1.5, 0.5), (1.5, 2.0)]


def test_offset_closed_rectangle() -> None:
    pts = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]
    out = GeometryTools._offset_polyline(pts, 0.5, closed=True)
    assert _round(out) == [(0.5, 0.5), (1.5, 0.5), (1.5, 1.5), (0.5, 1.5)]


def test_offset_degenerate_returns_input() -> None:
    out = GeometryTools._offset_polyline([(1.0, 1.0), (1.0, 1.0)], 0.5, closed=False)
    assert _round(out) == [(1.0, 1.0), (1.0, 1.0)]
