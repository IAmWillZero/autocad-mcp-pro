"""Tests de la biblioteca de detalles metalicos (sin AutoCAD)."""

from __future__ import annotations

import math

from autocad_mcp.features.detail_sheet import (
    CELL_HEIGHT,
    CELL_WIDTH,
    DEFAULT_ORIGIN,
    DETAIL_LIBRARY,
    _item_points,
    hatch_lines,
    paper_size,
    sheet_cells,
    sheet_size,
)
from autocad_mcp.layers import DETAIL_LAYERS


def test_library_has_twelve_unique_details() -> None:
    assert len(DETAIL_LIBRARY) == 12
    names = [spec.name for spec in DETAIL_LIBRARY]
    codes = [spec.code for spec in DETAIL_LIBRARY]
    assert len(set(names)) == 12
    assert len(set(codes)) == 12
    assert all(name.startswith("DET-") for name in names)


def test_blocks_are_ascii_and_documented() -> None:
    for spec in DETAIL_LIBRARY:
        assert spec.name == spec.name.upper()
        assert spec.name.isascii()
        assert spec.title
        assert spec.scale
        assert spec.note


def test_details_fit_the_cell() -> None:
    for spec in DETAIL_LIBRARY:
        assert 0 < spec.width <= CELL_WIDTH - 20
        assert 0 < spec.height <= CELL_HEIGHT - 30


def test_details_are_centered() -> None:
    for spec in DETAIL_LIBRARY:
        xs: list[float] = []
        ys: list[float] = []
        for item in (*spec.items, *spec.dims):
            for x, y in _item_points(item):
                xs.append(x)
                ys.append(y)
        assert math.isclose((min(xs) + max(xs)) / 2.0, 0.0, abs_tol=1e-6)
        assert math.isclose((min(ys) + max(ys)) / 2.0, 0.0, abs_tol=1e-6)


def test_all_items_use_detail_layers() -> None:
    for spec in DETAIL_LIBRARY:
        for item in spec.items:
            assert item.layer in DETAIL_LAYERS
        for dim in spec.dims:
            assert dim.layer in DETAIL_LAYERS


def test_every_detail_has_geometry_and_dimensions() -> None:
    for spec in DETAIL_LIBRARY:
        assert len(spec.items) >= 3
        assert len(spec.dims) >= 2
        assert all(dim.text for dim in spec.dims)


def test_cells_form_a_non_overlapping_grid() -> None:
    cells = sheet_cells(len(DETAIL_LIBRARY), DEFAULT_ORIGIN)
    assert len(cells) == 12
    assert {cell.column for cell in cells} == {0, 1, 2, 3}
    assert {cell.row for cell in cells} == {0, 1, 2}
    assert cells[0].x0 == DEFAULT_ORIGIN[0]
    assert cells[0].y0 == DEFAULT_ORIGIN[1] + 2 * CELL_HEIGHT
    assert cells[-1].x0 == DEFAULT_ORIGIN[0] + 3 * CELL_WIDTH
    assert cells[-1].y0 == DEFAULT_ORIGIN[1]

    seen: set[tuple[float, float]] = set()
    for cell in cells:
        key = (round(cell.x0, 6), round(cell.y0, 6))
        assert key not in seen
        seen.add(key)
        assert cell.cx == cell.x0 + CELL_WIDTH / 2.0
        assert cell.cy == cell.y0 + CELL_HEIGHT / 2.0


def test_grid_fits_an_a1_viewport() -> None:
    width, height = sheet_size(len(DETAIL_LIBRARY))
    assert width == 4 * CELL_WIDTH
    assert height == 3 * CELL_HEIGHT
    # Campo de dibujo del A1: 15 mm de margen y 65 mm de rotulo inferior.
    assert width <= 841.0 - 30.0
    assert height <= 594.0 - 15.0 - 65.0


def test_paper_size_by_media_name() -> None:
    assert paper_size("ISO_A1_(841.00_x_594.00_MM)") == (841.0, 594.0)
    assert paper_size("ANSI_D_(34.00_x_22.00_IN)") == (863.6, 558.8)
    assert paper_size("desconocido") == (841.0, 594.0)


def test_hatch_lines_stay_inside_polygon() -> None:
    square = ((0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0))
    lines = hatch_lines(square, spacing=1.0)
    assert lines
    for line in lines:
        for x, y in (line.p1, line.p2):
            assert -1e-6 <= x <= 10.0 + 1e-6
            assert -1e-6 <= y <= 5.0 + 1e-6


def test_hatch_lines_reject_degenerate_input() -> None:
    assert hatch_lines(((0.0, 0.0), (1.0, 1.0)), spacing=1.0) == ()
    assert hatch_lines(((0.0, 0.0), (1.0, 0.0), (1.0, 1.0)), spacing=0.0) == ()
