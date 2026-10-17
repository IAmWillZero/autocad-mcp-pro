"""Tests de analisis (sin AutoCAD): logica pura y guarda de conexion."""

from __future__ import annotations

from autocad_mcp.features.analysis import AnalysisTools


class _NotConnected:
    """Conexion falsa que nunca esta lista."""

    def ensure(self) -> bool:
        return False


def test_analyze_requires_connection() -> None:
    tools = AnalysisTools(_NotConnected(), None)  # type: ignore[arg-type]
    assert tools.analyze_drawing().get("error")


def test_passes_filter() -> None:
    desc = {"type": "AcDbLine", "layer": "WALLS"}
    assert AnalysisTools._passes_filter(desc, None, None)
    assert AnalysisTools._passes_filter(desc, "Line", None)
    assert not AnalysisTools._passes_filter(desc, "Circle", None)
    assert AnalysisTools._passes_filter(desc, None, "walls")
    assert not AnalysisTools._passes_filter(desc, None, "DOORS")


def test_extents_from_bounds() -> None:
    ext = AnalysisTools._extents([0.0, 0.0, 0.0], [10.0, 5.0, 0.0])
    assert ext["width"] == 10.0
    assert ext["height"] == 5.0


def test_extents_empty() -> None:
    ext = AnalysisTools._extents([float("inf")] * 3, [float("-inf")] * 3)
    assert ext["width"] == 0.0
    assert ext["height"] == 0.0


def test_expand_extents() -> None:
    mn = [float("inf")] * 3
    mx = [float("-inf")] * 3
    AnalysisTools._expand_extents(mn, mx, {"min": [1.0, 2.0, 0.0], "max": [3.0, 4.0, 0.0]})
    AnalysisTools._expand_extents(mn, mx, {"min": [-1.0, 0.0, 0.0], "max": [2.0, 5.0, 0.0]})
    assert mn == [-1.0, 0.0, 0.0]
    assert mx == [3.0, 5.0, 0.0]


def test_dimension_geometry_reads_measurement() -> None:
    class _Dim:
        Measurement = 12.34567
        TextOverride = ""
        TextPosition = (1.0, 2.0, 0.0)
        Rotation = 0.0

    geom = AnalysisTools._dimension_geometry(_Dim())
    assert geom["measurement"] == 12.3457
    assert geom["textposition"] == [1.0, 2.0, 0.0]
