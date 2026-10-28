"""Biblioteca de detalles metalicos: bloques reutilizables y lamina A1.

Dibuja un conjunto de detalles de estructura metalica en milimetros y a escala
de detalle (pernos, tuercas, arandelas, perfiles IPE/HEB, placas base, cartelas,
apoyos elastomericos, abrazaderas de cable, anclajes, empalmes y rigidizadores).
Cada detalle se define como bloque reutilizable y se compone una lamina A1 con
marco, rotulo y un viewport 1:1 sobre la retícula de detalles.

Las coordenadas de los bloques estan en milimetros de papel (escala de detalle),
no en metros: la lamina se imprime a 1:1 con el viewport.
"""

from __future__ import annotations

import math
import os
import re
import shutil
import time
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any

from autocad_mcp.colors import color_index
from autocad_mcp.com import as_dynamic, variant_array, variant_objects, variant_point
from autocad_mcp.connection import AutoCADConnection
from autocad_mcp.features.base import FeatureBase
from autocad_mcp.layers import DETAIL_LAYERS

Point = tuple[float, float]

# Rejilla de la lamina (mm de papel). 4 x 3 celdas caben en un A1 apaisado.
CELL_WIDTH = 198.0
CELL_HEIGHT = 170.0
DEFAULT_COLUMNS = 4
DEFAULT_ORIGIN: Point = (20000.0, 0.0)

# Trazador PDF de AutoCAD: define los nombres canonicos de papel.
PLOT_DEVICE = "DWG To PDF.pc3"

# Tamano canonico de papel por prefijo de nombre de medio de AutoCAD.
_SHEET_SIZES: dict[str, tuple[float, float]] = {
    "ISO_A0": (1189.0, 841.0),
    "ISO_A1": (841.0, 594.0),
    "ISO_A2": (594.0, 420.0),
    "ISO_A3": (420.0, 297.0),
    "ANSI_D": (863.6, 558.8),
    "ANSI_C": (558.8, 431.8),
}

# "ISO_A1_(841.00_x_594.00_MM)" / "ANSI_D_(34.00_x_22.00_In)"
_MEDIA_PATTERN = re.compile(r"_\(\s*([\d.]+)\s*_x_?\s*([\d.]+)\s*_(mm|in)\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Primitivas de dibujo (independientes de COM para poder testearlas)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LineItem:
    p1: Point
    p2: Point
    layer: str = "view"


@dataclass(frozen=True)
class CircleItem:
    center: Point
    radius: float
    layer: str = "view"


@dataclass(frozen=True)
class ArcItem:
    center: Point
    radius: float
    start_angle: float
    end_angle: float
    layer: str = "view"


@dataclass(frozen=True)
class PolyItem:
    points: tuple[Point, ...]
    closed: bool = True
    layer: str = "view"


@dataclass(frozen=True)
class TextItem:
    point: Point
    text: str
    height: float = 2.5
    layer: str = "text"
    align: str = "left"


@dataclass(frozen=True)
class DimItem:
    kind: str
    p1: Point
    p2: Point
    at: Point
    text: str | None = None
    rotation: float = 0.0
    layer: str = "dim"


Item = LineItem | CircleItem | ArcItem | PolyItem | TextItem


@dataclass(frozen=True)
class DetailSpec:
    """Un detalle de la biblioteca: bloque + cotas + rotulo."""

    code: str
    name: str
    title: str
    scale: str
    items: tuple[Item, ...]
    dims: tuple[DimItem, ...]
    note: str = ""
    width: float = 0.0
    height: float = 0.0


def _line(x1: float, y1: float, x2: float, y2: float, layer: str = "view") -> LineItem:
    return LineItem((x1, y1), (x2, y2), layer)


def _circle(cx: float, cy: float, r: float, layer: str = "view") -> CircleItem:
    return CircleItem((cx, cy), r, layer)


def _arc(cx: float, cy: float, r: float, start: float, end: float, layer: str = "view") -> ArcItem:
    return ArcItem((cx, cy), r, start, end, layer)


def _poly(points: tuple[Point, ...], closed: bool = True, layer: str = "view") -> PolyItem:
    return PolyItem(points, closed, layer)


def _rect(x0: float, y0: float, x1: float, y1: float, layer: str = "view") -> PolyItem:
    return PolyItem(((x0, y0), (x1, y0), (x1, y1), (x0, y1)), True, layer)


def _hexagon(cx: float, cy: float, across_flats: float, layer: str = "view") -> PolyItem:
    """Hexagono con caras planas horizontales (across flats)."""
    radius = across_flats / math.sqrt(3.0)
    points = tuple(
        (
            cx + radius * math.cos(math.radians(60.0 * i)),
            cy + radius * math.sin(math.radians(60.0 * i)),
        )
        for i in range(6)
    )
    return PolyItem(points, True, layer)


def _cross(cx: float, cy: float, half: float) -> tuple[LineItem, LineItem]:
    return (
        _line(cx - half, cy, cx + half, cy, "axis"),
        _line(cx, cy - half, cx, cy + half, "axis"),
    )


def _i_section(h: float, b: float, tw: float, tf: float, scale: float) -> PolyItem:
    """Contorno de perfil I/H (sin radios de acuerdo) a la escala indicada."""
    hh = h * scale / 2.0
    bf = b * scale / 2.0
    xw = tw * scale / 2.0
    ft = tf * scale
    points = (
        (-bf, -hh),
        (bf, -hh),
        (bf, -hh + ft),
        (xw, -hh + ft),
        (xw, hh - ft),
        (bf, hh - ft),
        (bf, hh),
        (-bf, hh),
        (-bf, hh - ft),
        (-xw, hh - ft),
        (-xw, -hh + ft),
        (-bf, -hh + ft),
    )
    return PolyItem(points, True, "cut")


def _dim_h(x1: float, x2: float, y: float, at_y: float, text: str | None = None) -> DimItem:
    """Cota horizontal entre dos puntos de igual y."""
    return DimItem("linear", (x1, y), (x2, y), ((x1 + x2) / 2.0, at_y), text, 0.0)


def _dim_v(x: float, y1: float, y2: float, at_x: float, text: str | None = None) -> DimItem:
    """Cota vertical entre dos puntos de igual x."""
    return DimItem("linear", (x, y1), (x, y2), (at_x, (y1 + y2) / 2.0), text, 90.0)


def _dim_dia(cx: float, cy: float, r: float, text: str | None = None) -> DimItem:
    """Cota diametral con el cabo a 45 grados."""
    chord = (cx + r * math.cos(math.radians(45.0)), cy + r * math.sin(math.radians(45.0)))
    return DimItem("diametric", (cx, cy), chord, chord, text)


def hatch_lines(
    points: tuple[Point, ...] | list[Point],
    spacing: float = 2.0,
    angle: float = 45.0,
    layer: str = "fill",
) -> tuple[LineItem, ...]:
    """Achurado de lineas paralelas recortado a un poligono convexo."""
    pts = [(float(x), float(y)) for x, y in points]
    if len(pts) < 3 or spacing <= 0:
        return ()

    radians = math.radians(angle)
    dx, dy = math.cos(radians), math.sin(radians)
    nx, ny = -dy, dx
    projection = [x * nx + y * ny for x, y in pts]
    tmin, tmax = min(projection), max(projection)

    segments: list[LineItem] = []
    t = tmin + spacing
    while t < tmax - 1e-9:
        hits: list[float] = []
        for index, (x1, y1) in enumerate(pts):
            x2, y2 = pts[(index + 1) % len(pts)]
            ex, ey = x2 - x1, y2 - y1
            denom = dx * ey - dy * ex
            if abs(denom) < 1e-12:
                continue
            qx, qy = x1 - nx * t, y1 - ny * t
            s = (qx * ey - qy * ex) / denom
            u = (qx * dy - qy * dx) / denom
            if -1e-9 <= u <= 1.0 + 1e-9:
                hits.append(s)
        if len(hits) >= 2:
            s0, s1 = min(hits), max(hits)
            if s1 - s0 > 1e-6:
                segments.append(
                    LineItem(
                        (nx * t + dx * s0, ny * t + dy * s0),
                        (nx * t + dx * s1, ny * t + dy * s1),
                        layer,
                    )
                )
        t += spacing
    return tuple(segments)


def _item_points(item: Item | DimItem) -> tuple[Point, ...]:
    if isinstance(item, LineItem):
        return (item.p1, item.p2)
    if isinstance(item, CircleItem):
        return (
            (item.center[0] - item.radius, item.center[1] - item.radius),
            (item.center[0] + item.radius, item.center[1] + item.radius),
        )
    if isinstance(item, ArcItem):
        return (
            (item.center[0] - item.radius, item.center[1] - item.radius),
            (item.center[0] + item.radius, item.center[1] + item.radius),
        )
    if isinstance(item, PolyItem):
        return item.points
    if isinstance(item, TextItem):
        return (item.point,)
    return (item.p1, item.p2, item.at)


def _shift(item: Any, dx: float, dy: float) -> Any:
    """Traslada cualquier primitiva (o cota) sin mutar el original."""
    if isinstance(item, LineItem):
        return LineItem(
            (item.p1[0] + dx, item.p1[1] + dy), (item.p2[0] + dx, item.p2[1] + dy), item.layer
        )
    if isinstance(item, CircleItem):
        return replace(item, center=(item.center[0] + dx, item.center[1] + dy))
    if isinstance(item, ArcItem):
        return replace(item, center=(item.center[0] + dx, item.center[1] + dy))
    if isinstance(item, PolyItem):
        return replace(item, points=tuple((x + dx, y + dy) for x, y in item.points))
    if isinstance(item, TextItem):
        return replace(item, point=(item.point[0] + dx, item.point[1] + dy))
    if isinstance(item, DimItem):
        return replace(
            item,
            p1=(item.p1[0] + dx, item.p1[1] + dy),
            p2=(item.p2[0] + dx, item.p2[1] + dy),
            at=(item.at[0] + dx, item.at[1] + dy),
        )
    return item


def _spec(
    code: str,
    name: str,
    title: str,
    scale: str,
    items: tuple[Item, ...],
    dims: tuple[DimItem, ...] = (),
    note: str = "",
) -> DetailSpec:
    """Centra el detalle en el origen y calcula su envolvente."""
    all_items: tuple[Item | DimItem, ...] = (*items, *dims)
    xs: list[float] = []
    ys: list[float] = []
    for item in all_items:
        for x, y in _item_points(item):
            xs.append(x)
            ys.append(y)
    cx = (min(xs) + max(xs)) / 2.0
    cy = (min(ys) + max(ys)) / 2.0
    return DetailSpec(
        code=code,
        name=name,
        title=title,
        scale=scale,
        items=tuple(_shift(item, -cx, -cy) for item in items),
        dims=tuple(_shift(item, -cx, -cy) for item in dims),
        note=note,
        width=max(xs) - min(xs),
        height=max(ys) - min(ys),
    )


# ---------------------------------------------------------------------------
# Detalles de la biblioteca
# ---------------------------------------------------------------------------


def _det_bolt() -> tuple[tuple[Item, ...], tuple[DimItem, ...]]:
    items: tuple[Item, ...] = (
        _rect(-12.5, -15, 0, 15),
        _rect(0, -10, 70, 10),
        _line(40, -8.66, 70, -8.66, "hidden"),
        _line(40, 8.66, 70, 8.66, "hidden"),
        _line(40, -10, 40, 10),
        _line(66, -10, 70, -6.6),
        _line(66, 10, 70, 6.6),
        _line(-20, 0, 78, 0, "axis"),
        _hexagon(120, 0, 30),
        _circle(120, 0, 10),
        _circle(120, 0, 8.66, "hidden"),
        *_cross(120, 0, 25),
    )
    dims = (
        _dim_h(0, 70, -10, -26, "70"),
        _dim_v(70, -10, 10, 84, "%%c20"),
        _dim_h(-12.5, 0, 15, 24, "12.5"),
        _dim_dia(120, 0, 10, "%%c20"),
    )
    return items, dims


def _det_nut() -> tuple[tuple[Item, ...], tuple[DimItem, ...]]:
    items: tuple[Item, ...] = (
        _hexagon(0, 0, 30, "cut"),
        _circle(0, 0, 10),
        _circle(0, 0, 8.66, "hidden"),
        *_cross(0, 0, 24),
        _rect(50, -15, 66, 15, "cut"),
        _line(50, -10, 66, -10, "hidden"),
        _line(50, 10, 66, 10, "hidden"),
        _line(50, 0, 66, 0, "axis"),
    )
    dims = (
        _dim_v(50, -15, 15, 76, "16"),
        _dim_h(-15, 15, -15, -25, "30"),
        _dim_dia(0, 0, 10, "%%c20"),
    )
    return items, dims


def _det_washer() -> tuple[tuple[Item, ...], tuple[DimItem, ...]]:
    items: tuple[Item, ...] = (
        _circle(0, 0, 18.5, "cut"),
        _circle(0, 0, 10.5, "cut"),
        *_cross(0, 0, 23),
        _rect(40, -18.5, 43, 18.5),
        _line(40, -10.5, 43, -10.5),
        _line(40, 10.5, 43, 10.5),
        *hatch_lines(((40, -18.5), (43, -18.5), (43, -10.5), (40, -10.5)), 0.8),
        *hatch_lines(((40, 10.5), (43, 10.5), (43, 18.5), (40, 18.5)), 0.8),
    )
    dims = (
        _dim_dia(0, 0, 18.5, "%%c37"),
        _dim_h(40, 43, 18.5, 26, "3"),
    )
    return items, dims


def _det_ipe() -> tuple[tuple[Item, ...], tuple[DimItem, ...]]:
    items: tuple[Item, ...] = (
        _i_section(300, 150, 7.1, 10.7, 0.2),
        _line(0, -36, 0, 36, "axis"),
        _line(-21, 0, 21, 0, "axis"),
    )
    dims = (
        _dim_v(15, -30, 30, 38, "300"),
        _dim_h(-15, 15, -30, -38, "150"),
    )
    return items, dims


def _det_heb() -> tuple[tuple[Item, ...], tuple[DimItem, ...]]:
    items: tuple[Item, ...] = (
        _i_section(300, 300, 11, 19, 0.2),
        _line(0, -36, 0, 36, "axis"),
        _line(-36, 0, 36, 0, "axis"),
    )
    dims = (
        _dim_v(30, -30, 30, 44, "300"),
        _dim_h(-30, 30, -30, -38, "300"),
    )
    return items, dims


def _det_base_plate() -> tuple[tuple[Item, ...], tuple[DimItem, ...]]:
    holes = tuple(_circle(x, y, 1.2, "cut") for x in (-20.0, 20.0) for y in (-20.0, 20.0))
    items: tuple[Item, ...] = (
        _rect(-25, -25, 25, 25, "cut"),
        *holes,
        *_cross(0, 0, 31),
    )
    dims = (
        _dim_h(-25, 25, -25, -34, "500"),
        _dim_h(-20, 20, 25, 34, "400"),
        _dim_dia(-20, -20, 1.2, "%%c26"),
    )
    return items, dims


def _det_gusset() -> tuple[tuple[Item, ...], tuple[DimItem, ...]]:
    items: tuple[Item, ...] = (
        _poly(((-15, -15), (15, -15), (15, 15)), True, "cut"),
        _line(-12, -12, 12, 12, "hidden"),
        _circle(-2, -10, 1.2, "cut"),
        _circle(6, -10, 1.2, "cut"),
        _circle(-2, -3, 1.2, "cut"),
        _circle(6, -3, 1.2, "cut"),
    )
    dims = (
        _dim_h(-15, 15, -15, -24, "300"),
        _dim_v(15, -15, 15, 24, "300"),
        _dim_dia(-2, -10, 1.2, "%%c26"),
    )
    return items, dims


def _det_bearing() -> tuple[tuple[Item, ...], tuple[DimItem, ...]]:
    items: tuple[Item, ...] = (
        _rect(-20, 4, 20, 34, "cut"),
        _circle(-15, 19, 1, "cut"),
        _circle(15, 19, 1, "cut"),
        *_cross(0, 19, 24),
        _rect(-20, -28, 20, -20, "cut"),
        _line(-20, -25.5, 20, -25.5),
        _line(-20, -25.25, 20, -25.25),
        _line(-20, -22.75, 20, -22.75),
        _line(-20, -22.5, 20, -22.5),
    )
    dims = (
        _dim_h(-20, 20, 34, 42, "400"),
        _dim_v(20, 4, 34, 27, "300"),
        _dim_v(20, -28, -20, 27, "80"),
    )
    return items, dims


def _det_cable_clamp() -> tuple[tuple[Item, ...], tuple[DimItem, ...]]:
    items: tuple[Item, ...] = (
        _circle(0, 0, 27, "cut"),
        _circle(0, 0, 23, "cut"),
        _line(-27, 0, -23, 0),
        _line(23, 0, 27, 0),
        _circle(-25, 4, 1.2, "cut"),
        _circle(-25, -4, 1.2, "cut"),
        _circle(25, 4, 1.2, "cut"),
        _circle(25, -4, 1.2, "cut"),
        *_cross(0, 0, 33),
    )
    dims = (
        _dim_dia(0, 0, 23, "%%c920"),
        _dim_dia(0, 0, 27, "%%c1080"),
    )
    return items, dims


def _det_anchor() -> tuple[tuple[Item, ...], tuple[DimItem, ...]]:
    items: tuple[Item, ...] = (
        _rect(-10, 20, 10, 23, "cut"),
        *hatch_lines(((-10, 20), (10, 20), (10, 23), (-10, 23)), 0.7),
        _rect(-2.8, 18.2, 2.8, 18.8, "cut"),
        _rect(-1.8, 16.5, 1.8, 18.2, "cut"),
        _rect(-1.2, -22, 1.2, 16.5),
        _line(-1.04, 8, -1.04, 16.5, "hidden"),
        _line(1.04, 8, 1.04, 16.5, "hidden"),
        _line(0, -31, 0, 26, "axis"),
        _line(-1.2, -22, -1.2, -25),
        _arc(-6.2, -25, 5, 180, 360),
        _line(-11.2, -25, -11.2, -21),
    )
    dims = (
        _dim_v(14, -25, 23, 20, "500"),
        _dim_h(-10, 10, 23, 30, "200"),
    )
    return items, dims


def _det_splice() -> tuple[tuple[Item, ...], tuple[DimItem, ...]]:
    bolts = tuple(_circle(x, y, 1.2, "cut") for x in (-8.0, 8.0) for y in (-5.0, 0.0, 5.0))
    items: tuple[Item, ...] = (
        _rect(-30, -8, -1, 8),
        _rect(1, -8, 30, 8),
        _rect(-12, 8, 12, 10.5, "cut"),
        _rect(-12, -10.5, 12, -8, "cut"),
        *bolts,
        _line(-12, 0, 12, 0, "axis"),
    )
    dims = (
        _dim_h(-12, 12, 10.5, 18, "240"),
        _dim_v(12, -10.5, 10.5, 19, "90"),
    )
    return items, dims


def _det_stiffener() -> tuple[tuple[Item, ...], tuple[DimItem, ...]]:
    welds = (
        _poly(((-8, -10), (-8, -6), (-4, -10)), True, "symbol"),
        _poly(((8, -10), (8, -6), (4, -10)), True, "symbol"),
        _poly(((-8, 10), (-8, 6), (-4, 10)), True, "symbol"),
        _poly(((8, 10), (8, 6), (4, 10)), True, "symbol"),
    )
    items: tuple[Item, ...] = (
        _rect(-25, 10, 25, 14, "cut"),
        _rect(-25, -14, 25, -10, "cut"),
        _rect(-1.5, -10, 1.5, 10, "cut"),
        _rect(-8, -10, -1.5, 10),
        _rect(1.5, -10, 8, 10),
        *welds,
    )
    dims = (
        _dim_v(25, -14, 14, 33, "300"),
        _dim_h(-25, 25, 14, 22, "300"),
    )
    return items, dims


def _build_library() -> tuple[DetailSpec, ...]:
    bolt_items, bolt_dims = _det_bolt()
    nut_items, nut_dims = _det_nut()
    washer_items, washer_dims = _det_washer()
    ipe_items, ipe_dims = _det_ipe()
    heb_items, heb_dims = _det_heb()
    plate_items, plate_dims = _det_base_plate()
    gusset_items, gusset_dims = _det_gusset()
    bearing_items, bearing_dims = _det_bearing()
    clamp_items, clamp_dims = _det_cable_clamp()
    anchor_items, anchor_dims = _det_anchor()
    splice_items, splice_dims = _det_splice()
    stiffener_items, stiffener_dims = _det_stiffener()
    return (
        _spec(
            "01",
            "DET-PERNO-M20",
            "PERNO HEXAGONAL M20 x 70",
            "1:1",
            bolt_items,
            bolt_dims,
            "Cabeza 30 A/F - rosca M20 x 40 - acero 8.8",
        ),
        _spec(
            "02",
            "DET-TUERCA-M20",
            "TUERCA HEXAGONAL M20",
            "1:1",
            nut_items,
            nut_dims,
            "30 A/F - altura 16 mm - acero clase 8",
        ),
        _spec(
            "03",
            "DET-ARANDELA-M20",
            "ARANDELA PLANA M20",
            "1:1",
            washer_items,
            washer_dims,
            "Ø37 x Ø21 x 3 mm - DIN 125 - acero galvanizado",
        ),
        _spec(
            "04",
            "DET-VIGA-IPE300",
            "VIGA IPE 300",
            "1:5",
            ipe_items,
            ipe_dims,
            "h 300 - b 150 - tw 7.1 - tf 10.7 - r 15 - S355JR",
        ),
        _spec(
            "05",
            "DET-VIGA-HEB300",
            "VIGA HEB 300",
            "1:5",
            heb_items,
            heb_dims,
            "h 300 - b 300 - tw 11 - tf 19 - r 27 - S355JR",
        ),
        _spec(
            "06",
            "DET-PLACA-BASE",
            "PLACA BASE 500 x 500 x 30",
            "1:10",
            plate_items,
            plate_dims,
            "4 agujeros Ø26 para pernos M24 - placa S355 de 30 mm",
        ),
        _spec(
            "07",
            "DET-CARTELA",
            "CARTELA DE NUDO 300 x 300 x 12",
            "1:10",
            gusset_items,
            gusset_dims,
            "4 agujeros Ø26 - cartela de 12 mm con rigidizador",
        ),
        _spec(
            "08",
            "DET-APOYO-ELASTOMERICO",
            "APOYO ELASTOMERICO 400 x 300 x 80",
            "1:10",
            bearing_items,
            bearing_dims,
            "3 capas de elastomero de 25 mm + 2 chapas de 2.5 mm",
        ),
        _spec(
            "09",
            "DET-ABRAZADERA-CABLE",
            "ABRAZADERA DE CABLE Ø920",
            "1:20",
            clamp_items,
            clamp_dims,
            "2 x M24 por lado - cable principal de Ø0.92 m",
        ),
        _spec(
            "10",
            "DET-ANCLAJE-M24",
            "ANCLAJE M24 x 500",
            "1:10",
            anchor_items,
            anchor_dims,
            "Tuerca + arandela + gancho 180 - acero 8.8 galvanizado",
        ),
        _spec(
            "11",
            "DET-EMPALME",
            "EMPALME ATORNILLADO DE ALMA",
            "1:10",
            splice_items,
            splice_dims,
            "2 chapas 240 x 90 x 10 - 6 x M24 - S355",
        ),
        _spec(
            "12",
            "DET-RIGIDIZADOR",
            "RIGIDIZADOR DE ALMA",
            "1:10",
            stiffener_items,
            stiffener_dims,
            "Chapa de 12 mm - soldadura en angulo de 6 mm",
        ),
    )


DETAIL_LIBRARY: tuple[DetailSpec, ...] = _build_library()


# ---------------------------------------------------------------------------
# Composicion de la lamina (datos puros)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Cell:
    index: int
    column: int
    row: int
    x0: float
    y0: float
    cx: float
    cy: float


def sheet_cells(
    count: int,
    origin: Point = DEFAULT_ORIGIN,
    columns: int = DEFAULT_COLUMNS,
) -> tuple[Cell, ...]:
    """Celdas de la retícula, de arriba-izquierda a abajo-derecha."""
    columns = max(1, int(columns))
    rows = max(1, math.ceil(count / columns))
    cells: list[Cell] = []
    for index in range(count):
        column = index % columns
        row = index // columns
        x0 = origin[0] + column * CELL_WIDTH
        y0 = origin[1] + (rows - 1 - row) * CELL_HEIGHT
        cells.append(
            Cell(
                index=index,
                column=column,
                row=row,
                x0=x0,
                y0=y0,
                cx=x0 + CELL_WIDTH / 2.0,
                cy=y0 + CELL_HEIGHT / 2.0,
            )
        )
    return tuple(cells)


def sheet_size(count: int, columns: int = DEFAULT_COLUMNS) -> tuple[float, float]:
    columns = max(1, int(columns))
    rows = max(1, math.ceil(count / columns))
    return columns * CELL_WIDTH, rows * CELL_HEIGHT


def paper_size(media: str) -> tuple[float, float]:
    """Tamano de papel (mm, apaisado) segun el nombre canonico de AutoCAD."""
    parsed = _media_dimensions(media)
    if parsed is not None:
        long_side, short_side = max(parsed), min(parsed)
        return (round(long_side, 1), round(short_side, 1))
    upper = media.upper()
    for prefix, size in _SHEET_SIZES.items():
        if upper.startswith(prefix):
            return size
    return (841.0, 594.0)


def _media_dimensions(media: str) -> tuple[float, float] | None:
    """Extrae (ancho, alto) en mm del nombre canonico de AutoCAD."""
    match = _MEDIA_PATTERN.search(str(media))
    if match is None:
        return None
    try:
        width, height = float(match.group(1)), float(match.group(2))
    except ValueError:
        return None
    if match.group(3).lower() == "in":
        width, height = width * 25.4, height * 25.4
    return (width, height)


def _is_landscape_media(media: str) -> bool:
    dims = _media_dimensions(media)
    return bool(dims and dims[0] > dims[1])


# ---------------------------------------------------------------------------
# Herramienta COM
# ---------------------------------------------------------------------------


def _is_plot_busy(exc: BaseException) -> bool:
    """True si AutoCAD rechazo la llamada por estar ocupado (plot/save en curso).

    Ademas de ``RPC_E_CALL_REJECTED`` y ``RPC_E_DISCONNECTED``, AutoCAD devuelve
    errores de propiedad (``Property 'AddCircle.Layer' can not be set``) cuando el
    proxy COM queda invalidado mientras traza o guarda: tambien son transitorios.
    """
    text = f"{exc} {exc!r}".lower()
    codes = ("-2147418111", "-2147417848", "-2147418113")
    phrases = (
        "rechazada",
        "rejected",
        "desconectado",
        "can not be set",
        "cannot be set",
        "unable to set",
        "call was rejected",
    )
    return any(code in text for code in codes) or any(phrase in text for phrase in phrases)


def _make_entity(factory: Any, configure: Any, attempts: int = 5, delay: float = 0.6) -> Any:
    """Crea una entidad y la configura, recreandola si AutoCAD rechaza el proxy.

    AutoCAD puede devolver un objeto COM valido y rechazar la escritura de sus
    propiedades; en ese caso hay que borrar el objeto y volver a crearlo.
    """
    last: BaseException | None = None
    for _ in range(attempts):
        obj = factory()
        try:
            configure(obj)
            return obj
        except Exception as exc:  # noqa: BLE001 - proxy COM invalidado por AutoCAD
            last = exc
            try:
                obj.Delete()
            except Exception:  # noqa: BLE001
                pass
            if not _is_plot_busy(exc):
                raise
            time.sleep(delay)
    assert last is not None
    raise last


def _com_retry(action: Any, attempts: int = 40, delay: float = 0.75) -> Any:
    """Reintenta una llamada COM mientras AutoCAD este ocupado."""
    last: BaseException | None = None
    for _ in range(attempts):
        try:
            return action()
        except Exception as exc:  # noqa: BLE001 - errores COM variados
            last = exc
            if not _is_plot_busy(exc):
                raise
            time.sleep(delay)
    assert last is not None
    raise last


def _wait_file_stable(path: Path, timeout: float = 60.0, settle: float = 1.2) -> bool:
    """Espera a que el PDF exista y su tamano deje de cambiar."""
    deadline = time.monotonic() + timeout
    previous = -1
    while time.monotonic() < deadline:
        if path.exists():
            size = path.stat().st_size
            if size > 0 and size == previous:
                return True
            previous = size
        time.sleep(settle)
    return path.exists() and path.stat().st_size > 0


def _wait_idle(app: Any, timeout: float = 90.0, poll: float = 0.5) -> bool:
    """Espera a que AutoCAD este inactivo (``AcadState.IsQuiescent``).

    Componer la lamina mientras AutoCAD procesa un comando o un trazado hace que
    rechace las llamadas COM (``RPC_E_CALL_REJECTED``) y a veces devuelve objetos
    a medio crear. Esperar al estado inactivo evita casi todos esos fallos.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if bool(app.GetAcadState().IsQuiescent):
                return True
        except Exception:  # noqa: BLE001 - version sin GetAcadState
            return False
        time.sleep(poll)
    return False


class DetailSheetTools(FeatureBase):
    """Crea bibliotecas de bloques de detalle y su lamina en papel."""

    def __init__(self, conn: AutoCADConnection, cache: Any | None = None) -> None:
        super().__init__(conn, cache)
        self._text_style = "Standard"
        self._dim_style = "Standard"
        self._sheet_viewport: tuple[str, float, float] = ("", 0.0, 0.0)

    def create_detail_sheet(
        self,
        layout_name: str = "DETALLES-ACERO",
        origin: list[float] | None = None,
        include_dimensions: bool = True,
        columns: int = DEFAULT_COLUMNS,
    ) -> dict[str, Any]:
        """Genera los 12 bloques de detalle y la lamina A1 que los compone."""
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}
        if not layout_name:
            return {"success": False, "error": "layout_name es obligatorio"}

        base: Point = DEFAULT_ORIGIN
        if origin:
            try:
                base = (float(origin[0]), float(origin[1]))
            except (IndexError, TypeError, ValueError) as exc:
                return {"success": False, "error": f"origin invalido: {exc}"}
        columns = max(1, min(6, int(columns)))
        if columns != DEFAULT_COLUMNS:
            return {
                "success": False,
                "error": "columns debe ser 4: la lamina A1 esta compuesta para 4 x 3",
            }

        last_error: BaseException | None = None
        attempts = 6
        try:
            _wait_idle(self.conn.app)
        except Exception:  # noqa: BLE001
            pass
        for attempt in range(attempts):
            try:
                # Reengancharse en cada intento: si AutoCAD invalido el proxy del
                # documento, reintentar con el mismo objeto falla siempre.
                if not self.conn.ensure():
                    return {"error": "Not connected to AutoCAD"}
                doc = self.conn.doc
                _com_retry(doc.Activate, attempts=5)
                return self._compose_sheet(doc, base, columns, layout_name, include_dimensions)
            except Exception as exc:  # noqa: BLE001 - COM devuelve errores variados
                last_error = exc
                if not _is_plot_busy(exc) or attempt == attempts - 1:
                    break
                # Backoff progresivo: AutoCAD suele tardar varios segundos en soltar COM.
                time.sleep(1.5 * (attempt + 1))
        return {"success": False, "error": f"No se pudo crear la lamina: {last_error}"}

    def _compose_sheet(
        self,
        doc: Any,
        base: Point,
        columns: int,
        layout_name: str,
        include_dimensions: bool,
    ) -> dict[str, Any]:
        """Dibuja bloques, retícula y lámina. Se reintenta entero si COM está ocupado."""
        created_layers = self._ensure_layers(doc)
        self._text_style = self._ensure_text_style(doc)
        self._dim_style = self._ensure_dim_style(doc)

        removed = self._cleanup(doc, layout_name)
        model_space = self.conn.model_space()
        blocks = self._build_blocks(doc, model_space)

        cells = sheet_cells(len(DETAIL_LIBRARY), base, columns)
        sheet_entities = 0
        references: list[dict[str, Any]] = []
        for spec, cell in zip(DETAIL_LIBRARY, cells, strict=True):
            ref = model_space.InsertBlock(
                variant_point(cell.cx, cell.cy - 4.0, 0.0),
                spec.name,
                1.0,
                1.0,
                1.0,
                0.0,
            )
            ref.Layer = self._layer("view")
            sheet_entities += 1
            references.append(
                {
                    "code": spec.code,
                    "block": spec.name,
                    "title": spec.title,
                    "scale": spec.scale,
                    "handle": self._handle(ref),
                }
            )
            sheet_entities += self._draw_cell(model_space, cell, spec, include_dimensions)

        width, height = sheet_size(len(DETAIL_LIBRARY), columns)
        layout_info = self._build_layout(doc, layout_name, base, width, height)
        self.conn.regen()
        self._invalidate()

        return {
            "success": True,
            "layout": layout_info["layout"],
            "paper_size": layout_info["paper_size"],
            "media": layout_info["media"],
            "device": layout_info["device"],
            "viewports": layout_info["viewports"],
            "removed_paper_entities": layout_info["removed_paper_entities"],
            "origin": [base[0], base[1]],
            "grid": {"columns": columns, "rows": math.ceil(len(DETAIL_LIBRARY) / columns)},
            "cell": [CELL_WIDTH, CELL_HEIGHT],
            "blocks": blocks,
            "block_count": len(blocks),
            "details": references,
            "removed_previous": removed,
            "entities": sheet_entities,
            "layers_created": created_layers,
            "layers": [str(spec["name"]) for spec in DETAIL_LAYERS.values()],
            "viewport": layout_info["viewport"],
            "message": (
                f"Lamina '{layout_name}' creada con {len(blocks)} bloques y "
                f"{len(references)} detalles"
            ),
        }

    def plot_to_pdf(self, path: str, layout_name: str = "DETALLES-ACERO") -> dict[str, Any]:
        """Traza el layout a PDF con ``PlotToFile`` (sin el comando -PLOT).

        ``-PLOT`` por ``SendCommand`` es sincrono: si una respuesta no coincide,
        AutoCAD queda esperando entrada y bloquea COM. ``PlotToFile`` tambien
        corre en segundo plano, asi que hay que esperar a que el archivo deje de
        crecer y reintentar mientras AutoCAD rechaza llamadas por estar ocupado.
        """
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}

        try:
            _wait_idle(self.conn.app)
        except Exception:  # noqa: BLE001
            pass

        doc = self.conn.doc
        try:
            _com_retry(lambda: doc.Layouts.Item(str(layout_name)))
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"Layout '{layout_name}' no existe: {exc}"}

        # El layout tiene que ser el activo: PlotToFile ignora el layout pedido y
        # traza siempre el actual (si no, sale una hoja A4 vacia de Layout1).
        # Ojo: ``ActiveSpace=1`` debe ir ANTES de ``CTAB``; al reves, AutoCAD
        # devuelve el layout "Model" como activo y el trazado sale en blanco.
        def activate() -> str:
            doc.Activate()
            doc.ActiveSpace = 1
            doc.SetVariable("CTAB", str(layout_name))
            current = str(doc.GetVariable("CTAB"))
            if current != str(layout_name):
                doc.ActiveLayout = doc.Layouts.Item(str(layout_name))
                current = str(doc.GetVariable("CTAB"))
            if current != str(layout_name):
                raise RuntimeError(f"no se pudo activar el layout '{layout_name}'")
            return current

        try:
            active_name = _com_retry(activate)
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"no se pudo activar el layout: {exc}"}

        try:
            _com_retry(lambda: self._prune_other_viewports(doc), attempts=5)
        except Exception:  # noqa: BLE001
            pass

        def configure() -> tuple[str, str]:
            layout = doc.ActiveLayout
            if not str(layout.ConfigName).lower().startswith("dwg to pdf"):
                layout.ConfigName = PLOT_DEVICE
            if not _is_landscape_media(str(layout.CanonicalMediaName)):
                layout.CanonicalMediaName = self._pick_media(layout)
            return (str(layout.CanonicalMediaName), str(layout.ConfigName))

        try:
            media, device = _com_retry(configure)
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"no se pudo configurar el papel: {exc}"}

        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Trazar a un archivo de paso evita que un PDF abierto en el visor impida
        # escribir el definitivo (antes quedaban PDF huerfanos con hora).
        staging = target.with_name(f"{target.stem}.plot{target.suffix}")
        for stale in (staging,):
            if stale.exists():
                try:
                    stale.unlink()
                except OSError:
                    pass
        try:
            _com_retry(lambda: setattr(doc.Plot, "QuietErrorMode", True), attempts=5)
        except Exception:  # noqa: BLE001
            pass
        try:
            _com_retry(lambda: doc.Plot.PlotToFile(str(staging)), attempts=20)
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"PlotToFile fallo: {exc}"}

        if not _wait_file_stable(staging):
            return {"success": False, "error": f"el PDF no se genero en {staging}"}

        final = self._publish_pdf(staging, target)
        return {
            "success": True,
            "pdf": str(final),
            "size": final.stat().st_size,
            "media": media,
            "device": device,
            "layout": active_name,
        }

    @staticmethod
    def _publish_pdf(staging: Path, target: Path, attempts: int = 10) -> Path:
        """Mueve el PDF trazado a su nombre final pese al bloqueo de AutoCAD.

        AutoCAD mantiene un handle abierto sobre el archivo recien trazado, asi
        que ``os.replace`` falla con ``WinError 32``; en ese caso se copia.
        """
        for _ in range(attempts):
            try:
                if target.exists():
                    target.unlink()
                os.replace(staging, target)
                return target
            except OSError:
                time.sleep(1.0)
        try:
            shutil.copyfile(staging, target)
        except OSError:
            return staging
        try:
            staging.unlink()
        except OSError:
            pass
        return target

    def prune_extra_viewports(self, layout_name: str = "DETALLES-ACERO") -> dict[str, Any]:
        """Deja un solo viewport en la lamina y devuelve cuantos quito.

        AutoCAD recrea el viewport principal del layout cada vez que se activa,
        asi que conviene llamarlo justo antes de guardar el DWG.
        """
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}

        doc = self.conn.doc

        def activate() -> None:
            doc.Activate()
            doc.ActiveSpace = 1
            doc.SetVariable("CTAB", str(layout_name))

        try:
            _com_retry(activate, attempts=10)
            removed = int(_com_retry(lambda: self._prune_other_viewports(doc), attempts=5))
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"no se pudieron limpiar los viewports: {exc}"}
        return {
            "success": True,
            "layout": str(layout_name),
            "removed": removed,
            "viewports": self._viewport_count(doc.PaperSpace),
        }

    # -- capas y estilos -------------------------------------------------

    def _prune_other_viewports(self, doc: Any) -> int:
        """Deja solo el viewport de la lamina (por handle o por tamano)."""
        handle, width, height = self._sheet_viewport
        paper = doc.PaperSpace
        removed = 0
        for index in range(int(paper.Count) - 1, -1, -1):
            try:
                entity = paper.Item(index)
                if str(entity.ObjectName) != "AcDbViewport":
                    continue
                own_handle = self._handle(entity)
                matches_size = (
                    abs(float(entity.Width) - width) < 1.0
                    and abs(float(entity.Height) - height) < 1.0
                )
            except Exception:  # noqa: BLE001
                continue
            if (handle and own_handle == handle) or (not handle and matches_size):
                continue
            try:
                entity.ViewportOn = False
            except Exception:  # noqa: BLE001
                pass
            try:
                entity.Delete()
                removed += 1
            except Exception:  # noqa: BLE001
                continue
        return removed

    def _ensure_layers(self, doc: Any) -> list[str]:
        layers = doc.Layers
        created: list[str] = []
        for spec in DETAIL_LAYERS.values():
            name = str(spec["name"])
            try:
                layer = layers.Item(name)
            except Exception:  # noqa: BLE001 - no existe
                layer = layers.Add(name)
                created.append(name)
            try:
                layer.color = color_index(str(spec.get("color", "white")))
            except Exception:  # noqa: BLE001
                pass
            try:
                layer.Lineweight = int(spec["lineweight"])
            except Exception:  # noqa: BLE001
                pass
            linetype = str(spec.get("linetype", "Continuous"))
            if linetype != "Continuous":
                try:
                    doc.Linetypes.Item(linetype)
                except Exception:  # noqa: BLE001 - intentar cargarla
                    try:
                        doc.Linetypes.Load(linetype, "acad.lin")
                    except Exception:  # noqa: BLE001
                        pass
                try:
                    layer.Linetype = linetype
                except Exception:  # noqa: BLE001
                    pass
            try:
                layer.Description = str(spec.get("description", ""))
            except Exception:  # noqa: BLE001
                pass
        return created

    def _ensure_text_style(self, doc: Any) -> str:
        name = "DETALLE"
        try:
            style = doc.TextStyles.Item(name)
        except Exception:  # noqa: BLE001 - no existe
            try:
                style = doc.TextStyles.Add(name)
            except Exception:  # noqa: BLE001
                return "Standard"
        try:
            style.FontFile = "romans.shx"
        except Exception:  # noqa: BLE001
            pass
        try:
            style.Height = 0.0
        except Exception:  # noqa: BLE001
            pass
        return name

    def _ensure_dim_style(self, doc: Any) -> str:
        name = "DETALLE"
        try:
            style = doc.DimStyles.Item(name)
        except Exception:  # noqa: BLE001 - no existe
            try:
                style = doc.DimStyles.Add(name)
            except Exception:  # noqa: BLE001
                return "Standard"
        variables: dict[str, Any] = {
            "DimScale": 1.0,
            "DimTxt": 2.5,
            "DimAsz": 1.8,
            "DimExe": 0.8,
            "DimExo": 1.5,
            "DimGap": 0.8,
            "DimTad": 1,
            "DimTih": 0,
            "DimToh": 0,
            "DimDec": 0,
            "DimZin": 8,
            "DimLunit": 2,
            "DimRnd": 0.0,
            "DimClrd": 256,
            "DimClre": 256,
            "DimClrt": 256,
            "DimTxSty": self._text_style,
        }
        for key, value in variables.items():
            try:
                style.SetVariable(key, value)
            except Exception:  # noqa: BLE001 - variable no soportada
                pass
        try:
            doc.SetVariable("DIMASSOC", 2)
        except Exception:  # noqa: BLE001
            pass
        return name

    def _cleanup(self, doc: Any, layout_name: str) -> int:
        """Borra una lamina anterior y sus entidades D- del espacio modelo."""
        removed = 0
        try:
            if str(doc.ActiveLayout.Name) == layout_name:
                doc.ActiveLayout = doc.Layouts.Item("Model")
                doc.ActiveSpace = 0
        except Exception:  # noqa: BLE001
            pass
        try:
            doc.Layouts.Item(layout_name).Delete()
            removed += 1
        except Exception:  # noqa: BLE001 - no existia o es el layout activo
            pass

        model_space = self.conn.model_space()
        try:
            for index in range(int(model_space.Count) - 1, -1, -1):
                try:
                    entity = model_space.Item(index)
                    layer = str(entity.Layer).upper()
                except Exception:  # noqa: BLE001
                    continue
                if layer.startswith("D-"):
                    try:
                        entity.Delete()
                        removed += 1
                    except Exception:  # noqa: BLE001
                        continue
        except Exception:  # noqa: BLE001
            pass

        for spec in DETAIL_LIBRARY:
            try:
                doc.Blocks.Item(spec.name).Delete()
                removed += 1
            except Exception:  # noqa: BLE001 - bloque usado o inexistente
                pass
        return removed

    # -- dibujo ----------------------------------------------------------

    def _layer(self, key: str) -> str:
        spec = DETAIL_LAYERS.get(key) or DETAIL_LAYERS["view"]
        return str(spec["name"])

    def _add_line(self, space: Any, item: LineItem, dx: float, dy: float) -> Any:
        p1 = variant_point(item.p1[0] + dx, item.p1[1] + dy, 0.0)
        p2 = variant_point(item.p2[0] + dx, item.p2[1] + dy, 0.0)
        layer = self._layer(item.layer)
        return _make_entity(
            lambda: space.AddLine(p1, p2),
            lambda obj: setattr(obj, "Layer", layer),
        )

    def _add_circle(self, space: Any, item: CircleItem, dx: float, dy: float) -> Any:
        center = variant_point(item.center[0] + dx, item.center[1] + dy, 0.0)
        radius = float(item.radius)
        layer = self._layer(item.layer)
        return _make_entity(
            lambda: space.AddCircle(center, radius),
            lambda obj: setattr(obj, "Layer", layer),
        )

    def _add_arc(self, space: Any, item: ArcItem, dx: float, dy: float) -> Any:
        center = variant_point(item.center[0] + dx, item.center[1] + dy, 0.0)
        radius = float(item.radius)
        start = math.radians(float(item.start_angle))
        end = math.radians(float(item.end_angle))
        layer = self._layer(item.layer)
        return _make_entity(
            lambda: space.AddArc(center, radius, start, end),
            lambda obj: setattr(obj, "Layer", layer),
        )

    def _add_poly(self, space: Any, item: PolyItem, dx: float, dy: float) -> Any:
        flat = [value for x, y in item.points for value in (float(x) + dx, float(y) + dy)]
        layer = self._layer(item.layer)
        points = variant_array(flat)

        def configure(obj: Any) -> None:
            if item.closed:
                obj.Closed = True
            obj.Layer = layer

        return _make_entity(lambda: space.AddLightWeightPolyline(points), configure)

    def _add_text(
        self,
        space: Any,
        point: Point,
        text: str,
        height: float,
        layer: str,
        align: str = "left",
    ) -> Any:
        content = _safe_text(text)
        location = variant_point(point[0], point[1], 0.0)
        text_height = float(height)
        layer_name = self._layer(layer)
        style = self._text_style

        def configure(obj: Any) -> None:
            obj.Layer = layer_name
            try:
                obj.StyleName = style
            except Exception:  # noqa: BLE001
                pass
            if align in ("center", "right"):
                try:
                    obj.Alignment = 10 if align == "center" else 2
                    obj.TextAlignmentPoint = location
                except Exception:  # noqa: BLE001
                    shift = -0.28 * text_height * len(text)
                    if align == "right":
                        shift *= 2.0
                    try:
                        obj.InsertionPoint = variant_point(point[0] + shift, point[1], 0.0)
                    except Exception:  # noqa: BLE001
                        pass

        return _make_entity(
            lambda: space.AddText(content, location, text_height),
            configure,
        )

    def _draw_items(self, space: Any, items: tuple[Item, ...], dx: float, dy: float) -> list[Any]:
        entities: list[Any] = []
        for item in items:
            if isinstance(item, LineItem):
                entities.append(self._add_line(space, item, dx, dy))
            elif isinstance(item, CircleItem):
                entities.append(self._add_circle(space, item, dx, dy))
            elif isinstance(item, ArcItem):
                entities.append(self._add_arc(space, item, dx, dy))
            elif isinstance(item, PolyItem):
                entities.append(self._add_poly(space, item, dx, dy))
            elif isinstance(item, TextItem):
                entities.append(
                    self._add_text(
                        space,
                        (item.point[0] + dx, item.point[1] + dy),
                        item.text,
                        item.height,
                        item.layer,
                        item.align,
                    )
                )
        return entities

    def _add_dim(self, space: Any, item: DimItem, dx: float, dy: float) -> Any:
        p1 = variant_point(item.p1[0] + dx, item.p1[1] + dy, 0.0)
        p2 = variant_point(item.p2[0] + dx, item.p2[1] + dy, 0.0)
        at = variant_point(item.at[0] + dx, item.at[1] + dy, 0.0)
        rotation = math.radians(float(item.rotation))
        layer = self._layer(item.layer)
        style = self._dim_style
        override = item.text

        def factory() -> Any:
            if item.kind == "diametric":
                return space.AddDimDiametric(p1, p2, 6.0)
            if item.kind == "aligned":
                return space.AddDimAligned(p1, p2, at)
            return space.AddDimRotated(p1, p2, at, rotation)

        def configure(dim: Any) -> None:
            # La capa es obligatoria: si AutoCAD la rechaza, hay que recrear la cota.
            dim.Layer = layer
            try:
                dim.StyleName = style
            except Exception:  # noqa: BLE001
                pass
            if override:
                try:
                    dim.TextOverride = override
                except Exception:  # noqa: BLE001
                    pass

        dim = _make_entity(factory, configure)
        try:
            dim.Update()
        except Exception:  # noqa: BLE001
            pass
        return dim

    def _build_blocks(self, doc: Any, model_space: Any) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        for spec in DETAIL_LIBRARY:
            entities = self._draw_items(model_space, spec.items, 0.0, 0.0)
            try:
                doc.Blocks.Item(spec.name).Delete()
            except Exception:  # noqa: BLE001 - bloque nuevo
                pass
            block = doc.Blocks.Add(variant_point(0.0, 0.0, 0.0), spec.name)
            doc.CopyObjects(variant_objects(entities), block)
            for entity in entities:
                try:
                    entity.Delete()
                except Exception:  # noqa: BLE001
                    pass
            blocks.append(
                {
                    "code": spec.code,
                    "name": spec.name,
                    "title": spec.title,
                    "scale": spec.scale,
                    "entities": len(entities),
                    "size_mm": [round(spec.width, 1), round(spec.height, 1)],
                }
            )
        return blocks

    def _draw_cell(
        self,
        model_space: Any,
        cell: Cell,
        spec: DetailSpec,
        include_dimensions: bool = True,
    ) -> int:
        created = 0
        frame = _rect(
            cell.x0 + 1.5,
            cell.y0 + 1.5,
            cell.x0 + CELL_WIDTH - 1.5,
            cell.y0 + CELL_HEIGHT - 1.5,
            "frame",
        )
        created += len(self._draw_items(model_space, (frame,), 0.0, 0.0))

        number_center = (cell.x0 + 11.0, cell.y0 + CELL_HEIGHT - 11.0)
        created += len(
            self._draw_items(
                model_space,
                (_circle(number_center[0], number_center[1], 4.5, "symbol"),),
                0.0,
                0.0,
            )
        )
        created += len(
            self._draw_items(
                model_space,
                (
                    TextItem(number_center, spec.code, 2.8, "title", "center"),
                    TextItem(
                        (cell.x0 + 104.5, cell.y0 + CELL_HEIGHT - 12.5),
                        spec.title,
                        3.0,
                        "title",
                        "center",
                    ),
                    TextItem(
                        (cell.x0 + CELL_WIDTH - 5.0, cell.y0 + CELL_HEIGHT - 12.5),
                        f"ESC {spec.scale}",
                        2.4,
                        "text",
                        "right",
                    ),
                ),
                0.0,
                0.0,
            )
        )
        if spec.note:
            created += len(
                self._draw_items(
                    model_space,
                    (
                        TextItem(
                            (cell.x0 + 5.0, cell.y0 + 5.5),
                            spec.note,
                            2.1,
                            "text",
                            "left",
                        ),
                    ),
                    0.0,
                    0.0,
                )
            )
        for dim in spec.dims:
            if not include_dimensions:
                break
            self._add_dim(model_space, dim, cell.cx, cell.cy - 4.0)
            created += 1
        return created

    # -- lamina ----------------------------------------------------------

    def _build_layout(
        self, doc: Any, layout_name: str, origin: Point, lib_width: float, lib_height: float
    ) -> dict[str, Any]:
        try:
            layout = doc.Layouts.Add(str(layout_name))
        except Exception:  # noqa: BLE001 - ya existe
            layout = doc.Layouts.Item(str(layout_name))

        # El dispositivo se fija ANTES del tamano de papel: los nombres canonicos
        # (ISO_A1...) dependen del trazador configurado en el layout.
        try:
            layout.ConfigName = PLOT_DEVICE
        except Exception:  # noqa: BLE001
            pass
        media = self._pick_media(layout)
        try:
            layout.CanonicalMediaName = media
        except Exception:  # noqa: BLE001
            pass
        for name, value in (
            ("PaperUnits", 1),  # acMillimeters
            ("PlotRotation", 0),  # 0 grados (el medio ya es apaisado)
            ("PlotType", 5),  # acLayout
            ("StandardScale", 16),  # 1:1
            ("UseStandardScale", True),
            ("CenterPlot", True),
            ("PlotWithPlotStyles", True),
            ("PlotViewportBorders", False),
            ("ScaleLineweights", False),
            ("StyleSheet", "monochrome.ctb"),
        ):
            try:
                setattr(layout, name, value)
            except Exception:  # noqa: BLE001 - propiedad no soportada por la version
                pass

        width, height = paper_size(media)
        try:
            _com_retry(lambda: setattr(doc, "ActiveSpace", 1), attempts=10)
            _com_retry(lambda: doc.SetVariable("CTAB", str(layout_name)), attempts=10)
            _com_retry(
                lambda: setattr(doc, "ActiveLayout", doc.Layouts.Item(str(layout_name))),
                attempts=5,
            )
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.4)

        paper = as_dynamic(doc.PaperSpace)
        # Se borra todo (incluido el viewport que trae el layout): al viewport
        # heredado no se le puede cambiar el tamano por COM. El propio se crea
        # abajo y se registra para conservarlo al trazar.
        removed = self._clear_paper_space(paper)
        self._draw_paper_sheet(paper, width, height)

        # Campo de dibujo: deja libre el rotulo inferior.
        vp_x0, vp_x1 = 15.0, width - 15.0
        vp_y0, vp_y1 = 65.0, height - 15.0
        vp_cx, vp_cy = (vp_x0 + vp_x1) / 2.0, (vp_y0 + vp_y1) / 2.0
        viewport = paper.AddPViewport(
            variant_point(vp_cx, vp_cy, 0.0), vp_x1 - vp_x0, vp_y1 - vp_y0
        )
        try:
            viewport.ViewportOn = True
        except Exception:  # noqa: BLE001
            pass
        # 1:1 exacto: el alto de vista en unidades de modelo iguala el alto en papel.
        try:
            viewport.Target = variant_point(
                origin[0] + lib_width / 2.0, origin[1] + lib_height / 2.0, 0.0
            )
        except Exception:  # noqa: BLE001
            pass
        try:
            viewport.ViewHeight = vp_y1 - vp_y0
        except Exception:  # noqa: BLE001
            pass
        try:
            viewport.CustomScale = 1.0
        except Exception:  # noqa: BLE001
            pass
        try:
            viewport.DisplayLocked = True
        except Exception:  # noqa: BLE001
            pass

        # Un layout nuevo trae su propio viewport: dejar solo el de la lamina.
        pruned = self._prune_viewports(paper, viewport)
        self._sheet_viewport = (
            self._handle(viewport),
            vp_x1 - vp_x0,
            vp_y1 - vp_y0,
        )

        try:
            doc.SetVariable("CTAB", str(layout_name))
        except Exception:  # noqa: BLE001
            pass
        return {
            "layout": str(layout.Name),
            "paper_size": [width, height],
            "media": media,
            "device": str(layout.ConfigName),
            "viewports": self._viewport_count(paper),
            "removed_paper_entities": removed,
            "removed_viewports": pruned,
            "viewport": {
                "center": [vp_cx, vp_cy],
                "size": [vp_x1 - vp_x0, vp_y1 - vp_y0],
                "scale": 1.0,
                "handle": self._handle(viewport),
            },
        }

    @staticmethod
    def _prune_viewports(paper: Any, keep: Any) -> int:
        """Elimina los viewports que no son el de la lamina (o los apaga)."""
        try:
            keep_handle = str(keep.Handle)
        except Exception:  # noqa: BLE001
            keep_handle = ""
        removed = 0
        for index in range(int(paper.Count) - 1, -1, -1):
            try:
                entity = paper.Item(index)
            except Exception:  # noqa: BLE001
                continue
            try:
                if str(entity.ObjectName) != "AcDbViewport":
                    continue
                if keep_handle and str(entity.Handle) == keep_handle:
                    continue
            except Exception:  # noqa: BLE001
                continue
            try:
                entity.ViewportOn = False
            except Exception:  # noqa: BLE001
                pass
            try:
                entity.Delete()
                removed += 1
            except Exception:  # noqa: BLE001
                continue
        return removed

    @staticmethod
    def _clear_paper_space(paper: Any) -> int:
        """Vacia el espacio papel (marco, rotulo y viewport heredados)."""
        removed = 0
        for index in range(int(paper.Count) - 1, -1, -1):
            try:
                entity = paper.Item(index)
            except Exception:  # noqa: BLE001
                continue
            try:
                entity.Delete()
                removed += 1
            except Exception:  # noqa: BLE001
                continue
        return removed

    @staticmethod
    def _viewport_count(paper: Any) -> int:
        count = 0
        for index in range(int(paper.Count)):
            try:
                if str(paper.Item(index).ObjectName) == "AcDbViewport":
                    count += 1
            except Exception:  # noqa: BLE001
                continue
        return count

    @staticmethod
    def _pick_media(layout: Any) -> str:
        """Elige el A1 apaisado disponible en el trazador del layout."""
        try:
            names = [str(name) for name in layout.GetCanonicalMediaNames()]
        except Exception:  # noqa: BLE001
            names = []
        for prefix in ("ISO_A1", "ANSI_D", "ISO_A2", "ANSI_C"):
            candidates = [name for name in names if name.upper().startswith(prefix)]
            landscape = [name for name in candidates if _is_landscape_media(name)]
            if landscape:
                return landscape[0]
            if candidates:
                return candidates[0]
        return names[0] if names else "ISO_A1_(841.00_x_594.00_MM)"

    def _draw_paper_sheet(self, paper: Any, width: float, height: float) -> None:
        margin, inner = 10.0, 15.0
        border = (
            _rect(margin, margin, width - margin, height - margin, "frame"),
            _rect(inner, inner, width - inner, height - inner, "frame"),
        )

        block_w, block_h = 206.0, 45.0
        bx0, by0 = width - inner - block_w, inner
        bx1, by1 = width - inner, inner + block_h
        title_lines = (
            _rect(bx0, by0, bx1, by1, "frame"),
            _line(bx0, by0 + 30.0, bx1, by0 + 30.0, "frame"),
            _line(bx0 + 130.0, by0, bx0 + 130.0, by0 + 30.0, "frame"),
        )
        self._draw_items(paper, (*border, *title_lines), 0.0, 0.0)

        texts = (
            TextItem((bx0 + 4.0, by0 + 37.0), "PUENTE GOLDEN GATE", 4.8, "title"),
            TextItem(
                (bx0 + 4.0, by0 + 31.5),
                "BIBLIOTECA DE DETALLES METALICOS",
                2.9,
                "text",
            ),
            TextItem(
                (bx0 + 4.0, by0 + 8.0),
                "LAMINA D-101 - ESCALA 1:1 / 1:5 / 1:10 / 1:20",
                2.5,
                "text",
            ),
            TextItem((bx0 + 134.0, by0 + 22.0), "UNIDAD: mm", 2.6, "text"),
            TextItem(
                (bx0 + 134.0, by0 + 15.5),
                f"{len(DETAIL_LIBRARY)} BLOQUES REUTILIZABLES",
                2.4,
                "text",
            ),
            TextItem((bx0 + 134.0, by0 + 9.0), f"FECHA: {date.today().isoformat()}", 2.3, "text"),
            TextItem((bx0 + 134.0, by0 + 3.0), "DIBUJO: AUTOCAD MCP PRO", 2.2, "text"),
        )
        self._draw_items(paper, texts, 0.0, 0.0)

    @staticmethod
    def _handle(entity: Any) -> str:
        try:
            return str(entity.Handle)
        except Exception:  # noqa: BLE001
            return ""


def _safe_text(text: str) -> str:
    """Convierte simbolos tipograficos a codigos de control de AutoCAD."""
    return (
        str(text)
        .replace("Ø", "%%c")
        .replace("ø", "%%c")
        .replace("°", "%%d")
        .replace("±", "%%p")
        .replace("×", "x")
        .replace("—", "-")
        .replace("–", "-")
    )
