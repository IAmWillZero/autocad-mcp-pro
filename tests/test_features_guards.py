"""Guards de las herramientas nuevas sin AutoCAD (validacion temprana)."""

from __future__ import annotations

from typing import Any

from autocad_mcp.features.blocks import BlockTools
from autocad_mcp.features.dimensions import DimensionTools
from autocad_mcp.features.grid import GridTools
from autocad_mcp.features.standards import StandardsTools


class _NotConnected:
    def ensure(self) -> bool:
        return False


class _EmptySpace:
    Count = 0


class _ConnectedEmpty:
    """Conexion simulada 'lista' con ModelSpace vacio."""

    doc: Any = None

    def ensure(self) -> bool:
        return True

    def model_space(self) -> Any:
        return _EmptySpace()

    def regen(self) -> None:
        return None


def test_each_tool_requires_connection() -> None:
    conn = _NotConnected()
    assert "error" in StandardsTools(conn).apply_standard()  # type: ignore[arg-type]
    assert "error" in GridTools(conn).create_construction_grid([0.0, 1.0])  # type: ignore[arg-type]
    assert "error" in BlockTools(conn).list_blocks()  # type: ignore[arg-type]
    assert (
        "error" in DimensionTools(conn).create_dimension("rotated", [[0.0, 0.0], [1.0, 0.0]])  # type: ignore[arg-type]
    )


def test_grid_requires_positions() -> None:
    result = GridTools(_ConnectedEmpty()).create_construction_grid([], [])  # type: ignore[arg-type]
    assert result["success"] is False
    assert "vertical_positions" in result["error"]


def test_dimension_validates_type_and_points() -> None:
    tools = DimensionTools(_ConnectedEmpty())  # type: ignore[arg-type]
    assert tools.create_dimension("bogus", [[0.0, 0.0], [1.0, 0.0]])["success"] is False
    assert tools.create_dimension("rotated", [[0.0, 0.0]])["success"] is False
    missing = tools.create_dimension("rotated", [[0.0, 0.0], [1.0, 0.0]])
    assert missing["success"] is False
    assert "dim_line_point" in missing["error"]


def test_explode_empty_modelspace() -> None:
    result = BlockTools(_ConnectedEmpty()).explode_entities(["ABC123"])  # type: ignore[arg-type]
    assert result["success"] is True
    assert result["exploded_count"] == 0
