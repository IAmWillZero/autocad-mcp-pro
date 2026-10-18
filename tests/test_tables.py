"""Tests de la herramienta de tablas (sin AutoCAD)."""

from __future__ import annotations

from typing import Any

from autocad_mcp.features.tables import TableTools


class _FakeTable:
    def __init__(self) -> None:
        self.cells: dict[tuple[int, int], str] = {}
        self.col_widths: dict[int, float] = {}
        self.layer = ""

    def SetText(self, row: int, col: int, value: str) -> None:
        self.cells[(row, col)] = value

    def SetTextHeight(self, row: int, col: int, height: float) -> None:  # noqa: ARG002
        pass

    def SetCellAlignment(self, row: int, col: int, align: int) -> None:  # noqa: ARG002
        pass

    def SetColumnWidth(self, col: int, width: float) -> None:
        self.col_widths[col] = width

    @property
    def Handle(self) -> str:
        return "T1"


class _FakeModelSpace:
    def __init__(self) -> None:
        self.table = _FakeTable()
        self.args: tuple[Any, ...] = ()

    def AddTable(self, point: Any, rows: int, cols: int, rh: float, cw: float) -> _FakeTable:
        self.args = (rows, cols, rh, cw)
        return self.table


class _FakeConn:
    def __init__(self) -> None:
        self.ms = _FakeModelSpace()

    def ensure(self) -> bool:
        return True

    def model_space(self) -> _FakeModelSpace:
        return self.ms

    def regen(self) -> None:
        pass


def test_create_table_fills_cells_and_reports_size() -> None:
    conn = _FakeConn()
    tools = TableTools(conn)  # type: ignore[arg-type]
    result = tools.create_table([[1, "B"], ["c", "d"]])
    assert result["success"] is True
    assert result["rows"] == 2
    assert result["cols"] == 2
    assert conn.ms.table.cells[(0, 0)] == "1"
    assert conn.ms.table.cells[(1, 1)] == "d"


def test_create_table_with_title_adds_extra_row() -> None:
    conn = _FakeConn()
    tools = TableTools(conn)  # type: ignore[arg-type]
    result = tools.create_table([["A", "B"]], title="CUADRO DE AREAS")
    assert result["rows"] == 2
    assert conn.ms.table.cells[(0, 0)] == "CUADRO DE AREAS"


def test_create_table_pads_ragged_rows() -> None:
    conn = _FakeConn()
    tools = TableTools(conn)  # type: ignore[arg-type]
    result = tools.create_table([["a"], ["b", "c", "d"]])
    assert result["cols"] == 3
    assert conn.ms.table.cells[(0, 2)] == ""


def test_create_table_rejects_empty_data() -> None:
    tools = TableTools(_FakeConn())  # type: ignore[arg-type]
    result = tools.create_table([])
    assert result["success"] is False
    assert "vacia" in result["error"]


def test_create_table_applies_per_column_widths() -> None:
    conn = _FakeConn()
    tools = TableTools(conn)  # type: ignore[arg-type]
    tools.create_table([["a", "b"]], col_width=2.0, col_widths=[3.5, 1.7])
    assert conn.ms.table.col_widths == {0: 3.5, 1: 1.7}
