"""Helpers de dibujo de la vivienda (plantas) sobre las herramientas MCP.

El punto de entrada es ``draw_house.py``; este modulo solo expone los helpers
reutilizables (``_retry`` y ``_draw_floor``).
"""

from __future__ import annotations

import time

from autocad_mcp.service import AutoCADService
from house_draw import (
    draw_axes,
    draw_bottom_dims,
    draw_fixtures,
    draw_labels,
    draw_left_dims,
    draw_walls_and_openings,
    shift_openings,
)

OVERS = {"bottom": 1.6, "top": 1.6, "left": 1.6, "right": 1.6}


def _retry(fn, tries: int = 10, delay: float = 1.5):
    last = None
    for _ in range(tries):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - AutoCAD momentaneamente ocupado
            last = exc
            time.sleep(delay)
    raise last


def _draw_floor(
    s: AutoCADService,
    rooms: list,
    X: list,
    Y: list,
    openings: list,
    axes_v: list,
    axes_h: list,
    fixtures: list,
    title: str,
    bottom_levels: list,
    left_levels: list,
    ox: float = 0.0,
    oy: float = 0.0,
) -> int:
    Xa = [x + ox for x in X]
    Ya = [y + oy for y in Y]
    ops = shift_openings(openings, ox, oy)
    n = draw_walls_and_openings(s, rooms, Xa, Ya, ops)
    draw_fixtures(s, fixtures, ox, oy)
    draw_labels(s, rooms, Xa, Ya)
    draw_axes(s, axes_v, axes_h, ox, oy, OVERS)
    front, left = Ya[0], Xa[0]
    for off, breaks in bottom_levels:
        draw_bottom_dims(s, breaks, front, off, ox)
    for off, breaks in left_levels:
        draw_left_dims(s, breaks, left, off, oy)
    s.layer_tools.set_current_layer("A-TEXTOS")
    s.geometry.create_text([Xa[0], max(Ya) + 2.4], title, 0.32, "bylayer")
    return n
