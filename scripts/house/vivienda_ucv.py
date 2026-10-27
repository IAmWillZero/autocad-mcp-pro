"""Vivienda UCV Magisterial 230: DWG unico con zonificacion + plantas + presentacion.

Reune las fases del informe de mejora:
- Fase 2: dos banos (SS.HH. 1 PB / SS.HH. 2 PA) apilados al norte de la escalera.
- Fase 3: zonificacion por ambiente (social/servicios/privada/circulacion/libre),
  semitransparente, sin ocultar lineas.
- Fase 4: biblioteca de bloques normalizados (se define e inserta).
- Fase 5: cotas, ejes coordinados, niveles, norte, escala grafica, cuadros y simbologia.
- Fase 6: jerarquia de grosores por capa.
- Fase 8: layouts A4 horizontal con membrete UCV (A-01..A-05).
- Fase 9: guarda una copia en un archivo NUEVO.

Regenera el documento desde cero (idempotente). Unidades metros, 1:1 en Modelo.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from autocad_mcp.com import as_dynamic, variant_point  # noqa: E402
from autocad_mcp.service import AutoCADService  # noqa: E402

import ucv_areas as AR  # noqa: E402
import ucv_data as U  # noqa: E402
from draw_house import _draw_area_table  # noqa: E402
from house_blocks import define_blocks  # noqa: E402
from house_draw import draw_stair_u  # noqa: E402
from house_main import _draw_floor  # noqa: E402

OUT_DIR = str(ROOT / "out")
TARGET = "Vivienda_UCV_Magisterial_230.dwg"
TARGET_PATH = os.path.join(OUT_DIR, TARGET)
NEW_NAME = "Vivienda_UCV_Magisterial_230_MEJORADO.dwg"
NEW_PATH = os.path.join(OUT_DIR, NEW_NAME)

OX = 10.0  # separacion vertical de plantas dentro de la zona de zonificacion

# categoria -> (capa, patron, transparencia, escala)
ZONE_LAYER = {
    "SOC": "Z-SOCIAL",
    "SER": "Z-SERVICIOS",
    "PRI": "Z-PRIVADA",
    "CIR": "Z-CIRCULACION",
    "LIB": "Z-AREA-LIBRE",
}
ZONE_STYLE = {
    "Z-SOCIAL": ("magenta", "SOLID", "55", 1.0),
    "Z-SERVICIOS": ("blue", "SOLID", "55", 1.0),
    "Z-PRIVADA": ("green", "SOLID", "55", 1.0),
    "Z-CIRCULACION": ("yellow", "ANSI31", "65", 0.5),
    "Z-AREA-LIBRE": ("green", "ANSI31", "65", 0.35),
}
ZONE_TITLE = {
    "SOC": "ZONA SOCIAL",
    "SER": "ZONA SERVICIOS",
    "PRI": "ZONA PRIVADA",
    "CIR": "CIRCULACION",
    "LIB": "AREA LIBRE",
}

# Fase 6: grosor de linea por capa (1/100 mm).
LINEWEIGHTS = {
    "A-MUROS-CARGA": 50,
    "A-MUROS-TABIQ": 30,
    "A-PUER-VENT": 30,
    "A-MOBILIARIO": 18,
    "A-PROYECC": 18,
    "A-EJES": 13,
    "A-COTAS": 13,
    "A-TEXTOS": 13,
    "A-TERRENO": 25,
    "Z-SOCIAL": 9,
    "Z-SERVICIOS": 9,
    "Z-PRIVADA": 9,
    "Z-CIRCULACION": 9,
    "Z-AREA-LIBRE": 9,
}


def _retry(fn, tries: int = 8, delay: float = 1.0):
    import time

    last = None
    for _ in range(tries):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - COM ocupado
            last = exc
            time.sleep(delay)
    raise last  # type: ignore[misc]


def _log(*a) -> None:
    print(*a, flush=True)


def _rect(x0: float, y0: float, x1: float, y1: float) -> list[list[float]]:
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def _ensure_target(s: AutoCADService) -> str:
    """Usa un DWG dedicado y limpio; no toca otros documentos abiertos."""
    app = s.conn.app
    docs = app.Documents
    names = [str(_retry(lambda i=i: docs.Item(i).Name)) for i in range(int(docs.Count))]
    if TARGET in names:
        s.conn.doc = _retry(lambda: docs.Item(TARGET))
        _retry(lambda: s.conn.doc.Activate())
        return TARGET
    os.makedirs(OUT_DIR, exist_ok=True)
    if os.path.exists(TARGET_PATH):
        doc = _retry(lambda: docs.Open(TARGET_PATH))
    else:
        doc = _retry(docs.Add)
        _retry(lambda: doc.SaveAs(TARGET_PATH))
    s.conn.doc = doc
    return str(doc.Name)


def _poly(s: AutoCADService, pts2d: list[list[float]], closed: bool = True) -> list[str]:
    r = s.geometry.create_polyline(pts2d, closed=closed, color="bylayer")
    return list(r.get("handles", [])) if r.get("success") else []


def _zone(s: AutoCADService, layer: str, pts: list[list[float]], label: str,
          anchor: list[float]) -> None:
    color_name, pattern, trans, scale = ZONE_STYLE[layer]
    s.layer_tools.set_current_layer(layer)
    handles = _poly(s, pts)
    if handles:
        s.geometry.create_hatch(
            handles, pattern, scale=scale, layer=layer, color="bylayer", transparency=trans
        )
    xs = [p[0] for p in pts]
    available = (max(xs) - min(xs)) - 0.2
    h = max(0.10, min(0.22, available / (len(label) * 0.95)))
    w = len(label) * 0.95 * h
    s.layer_tools.set_current_layer("A-TEXTOS")
    s.geometry.create_text([round(anchor[0] - w / 2.0, 3), round(anchor[1], 3)], label,
                           round(h, 3), "bylayer")


def _terreno(s: AutoCADService, ox: float = 0.0) -> None:
    s.layer_tools.set_current_layer("A-TERRENO")
    _poly(s, _rect(ox, 0.0, ox + 8.0, 23.0))


def _outline(s: AutoCADService, pts: list[list[float]], ox: float,
             layer: str = "A-PROYECC") -> None:
    s.layer_tools.set_current_layer(layer)
    shifted = [[round(p[0] + ox, 3), round(p[1], 3)] for p in pts]
    _poly(s, shifted, closed=True)


def _legend(s: AutoCADService, x0: float, y_top: float) -> None:
    rows = [
        ("Z-SOCIAL", "ZONA SOCIAL"),
        ("Z-SERVICIOS", "ZONA SERVICIOS"),
        ("Z-PRIVADA", "ZONA PRIVADA"),
        ("Z-CIRCULACION", "CIRCULACION (ESCALERA/HALL)"),
        ("Z-AREA-LIBRE", "AREA LIBRE"),
    ]
    sw = 0.5
    s.layer_tools.set_current_layer("A-TEXTOS")
    s.geometry.create_text([x0, y_top + 0.35], "LEYENDA DE ZONIFICACION", 0.26, "bylayer")
    y = y_top
    for layer, txt in rows:
        s.layer_tools.set_current_layer(layer)
        h = _poly(s, _rect(x0, y - 0.4, x0 + sw, y))
        if h:
            _c, pattern, trans, scale = ZONE_STYLE[layer]
            s.geometry.create_hatch(h, pattern, scale=scale, layer=layer, color="bylayer",
                                    transparency=trans)
        s.layer_tools.set_current_layer("A-TEXTOS")
        s.geometry.create_text([x0 + sw + 0.2, y - 0.3], txt, 0.22, "bylayer")
        y -= 0.8


def _north(s: AutoCADService, cx: float, cy: float, r: float = 0.55) -> None:
    s.layer_tools.set_current_layer("A-TEXTOS")
    s.geometry.create_circle([cx, cy], r, "bylayer")
    s.geometry.create_line([cx, cy - r], [cx, cy + r], "bylayer")
    head = 0.18
    s.geometry.create_line([cx, cy + r], [cx - head, cy + r - head], "bylayer")
    s.geometry.create_line([cx, cy + r], [cx + head, cy + r - head], "bylayer")
    s.geometry.create_text([cx - 0.09, cy + r + 0.12], "N", 0.32, "bylayer")


def _scale_bar(s: AutoCADService, x0: float, y0: float, n: int = 5, step: float = 1.0) -> None:
    """Escala grafica de ``n`` metros con divisiones de 1 m y rotulo."""
    s.layer_tools.set_current_layer("A-TEXTOS")
    total = n * step
    for i in range(n):
        if i % 2 == 0:
            s.geometry.create_rectangle([x0 + i * step, y0], [x0 + (i + 1) * step, y0 + 0.2],
                                        "bylayer")
    s.geometry.create_rectangle([x0, y0], [x0 + total, y0 + 0.2], "bylayer")
    for i in range(n + 1):
        s.geometry.create_text([x0 + i * step - 0.06, y0 - 0.32], str(i), 0.18, "bylayer")
    s.geometry.create_text([x0 + total + 0.15, y0 - 0.32], "m", 0.18, "bylayer")


def _level(s: AutoCADService, x: float, y: float, text: str) -> None:
    """Simbolo de nivel (N.P.T.)."""
    s.layer_tools.set_current_layer("A-TEXTOS")
    s.geometry.create_line([x, y], [x + 0.5, y], "bylayer")
    s.geometry.create_line([x, y], [x, y - 0.25], "bylayer")
    s.geometry.create_text([x + 0.55, y - 0.05], text, 0.2, "bylayer")


def _section_mark(s: AutoCADService, x: float, y0: float, y1: float, label: str) -> None:
    """Linea de corte vertical con burbujas en los extremos."""
    s.layer_tools.set_current_layer("A-EJES")
    s.geometry.create_line([x, y0], [x, y1], "bylayer")
    for y, dy in ((y0, -1), (y1, 1)):
        s.geometry.create_circle([x, y + dy * 0.6], 0.35, "bylayer")
        s.geometry.create_line([x, y], [x, y + dy * 0.25], "bylayer")
        s.layer_tools.set_current_layer("A-TEXTOS")
        s.geometry.create_text([x - 0.09, y + dy * 0.6 - 0.13], label, 0.24, "bylayer")
        s.layer_tools.set_current_layer("A-EJES")
    s.layer_tools.set_current_layer("A-TEXTOS")


def _room_zones(s: AutoCADService, rooms: list, X: list, Y: list, ox: float) -> None:
    """Fase 3: poligono independiente por ambiente, con su categoria."""
    for (label, i0, i1, j0, j1) in rooms:
        x0, x1 = X[i0] + ox, X[i1] + ox
        y0, y1 = Y[j0], Y[j1]
        cat = U.ZONE.get(label, "LIB")
        layer = ZONE_LAYER[cat]
        pts = _rect(x0, y0, x1, y1)
        _zone(s, layer, pts, label, [(x0 + x1) / 2.0, (y0 + y1) / 2.0 - 0.05])


def _stair_plan(s: AutoCADService, stair: dict, ox: float = 0.0, oy: float = 0.0,
                label: str = "SUBE", outline: bool = True) -> None:
    """Escalera en L completa: dos tramos, descanso, barrido y flecha de sentido.

    ``outline=False`` se usa en plantas arquitectonicas: evita superponer el
    rectangulo del recinto sobre los muros y los vanos de puerta.
    """
    x0 = stair["x0"] + ox
    x1 = stair["x1"] + ox
    y0 = stair["y0"] + oy
    y1 = stair["y1"] + oy
    w = 0.90
    xw = x1 - w
    yl = y1 - w

    s.layer_tools.set_current_layer("A-MUROS-TABIQ")
    if outline:
        _poly(s, _rect(x0, y0, x1, y1))
    # Borde sur del descanso (tambien es el ultimo peldaño del primer tramo).
    s.geometry.create_line([x0, yl], [x1, yl], "bylayer")
    s.geometry.create_line([xw, y0], [xw, yl], "bylayer")

    # Primer tramo: sube por el muro este.
    n1 = 10
    run1 = yl - y0
    for i in range(1, n1):
        yy = y0 + i * run1 / n1
        s.geometry.create_line([xw, yy], [x1, yy], "bylayer")

    # Descanso en la esquina noroeste del recinto (1.80 x 0.90); el segundo
    # tramo ocupa solo el ancho del ambiente TRAMO 2 (1.80 m).
    x_land = (x0 + x1) / 2.0
    n2 = 6
    run2 = x_land - x0
    for i in range(1, n2 + 1):
        xx = x0 + i * run2 / n2
        s.geometry.create_line([xx, yl], [xx, y1], "bylayer")

    # Pasamanos del tramo largo, separado del borde abierto.
    s.geometry.create_line([xw + 0.06, y0 + 0.12], [xw + 0.06, yl - 0.10], "bylayer")
    s.geometry.create_line([xw + 0.06, yl - 0.10], [xw + 0.15, yl - 0.10], "bylayer")

    # Camino de circulacion con giro en el descanso.
    xc = (xw + x1) / 2.0
    p0 = (xc, y0 + 0.20)
    p1 = (xc, yl + 0.15)
    p2 = (x0 + 0.35, yl + 0.15)
    s.geometry.create_line([p0[0], p0[1]], [p1[0], p1[1]], "bylayer")
    s.geometry.create_line([p1[0], p1[1]], [p2[0], p2[1]], "bylayer")

    if str(label).upper().startswith("BAJ"):
        # Baja: punta en el arranque sur.
        s.geometry.create_line([p0[0], p0[1]], [p0[0] - 0.11, p0[1] + 0.14], "bylayer")
        s.geometry.create_line([p0[0], p0[1]], [p0[0] + 0.11, p0[1] + 0.14], "bylayer")
        s.geometry.create_circle([p2[0], p2[1]], 0.035, "bylayer")
    else:
        # Sube: punta al final del segundo tramo.
        s.geometry.create_line([p2[0], p2[1]], [p2[0] + 0.15, p2[1] + 0.10], "bylayer")
        s.geometry.create_line([p2[0], p2[1]], [p2[0] + 0.15, p2[1] - 0.10], "bylayer")
        s.geometry.create_circle([p0[0], p0[1]], 0.035, "bylayer")

    s.layer_tools.set_current_layer("A-TEXTOS")
    s.geometry.create_text([round(x0 + 0.12, 3), round(y0 + 0.12, 3)], label, 0.13, "bylayer")
    s.geometry.create_text([round(x0 + 0.12, 3), round(y0 + 0.34, 3)], "16 ESC", 0.10, "bylayer")


def _zoning(s: AutoCADService) -> None:
    _terreno(s, 0.0)
    _terreno(s, OX)
    _room_zones(s, U.ROOMS1, U.X1, U.Y1, 0.0)
    _room_zones(s, U.ROOMS2, U.X2, U.Y2, OX)
    for pts in (U.JARDIN_FRONTAL, U.TERRAZA_POST, U.JARDIN_POST, U.JARDIN_NOTCH_PB):
        if pts:
            _zone(s, "Z-AREA-LIBRE", pts, _lib_label(pts), _mid(pts))
    for pts in (U.BALCON_FRONTAL, U.BALCON_POST, U.TERRAZA_NOTCH):
        if pts:
            _zone(s, "Z-AREA-LIBRE", [[p[0] + OX, p[1]] for p in pts], _lib_label(pts), _mid(pts, OX))
    s.layer_tools.set_current_layer("A-TEXTOS")
    s.geometry.create_text([0.0, 23.45], "PLANTA BAJA - ZONIFICACION", 0.26, "bylayer")
    s.geometry.create_text([OX, 23.45], "PLANTA ALTA - ZONIFICACION", 0.26, "bylayer")


def _mid(pts: list[list[float]], ox: float = 0.0) -> list[float]:
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return [(min(xs) + max(xs)) / 2.0 + ox, (min(ys) + max(ys)) / 2.0]


def _lib_label(pts: list[list[float]]) -> str:
    ys = [p[1] for p in pts]
    yc = (min(ys) + max(ys)) / 2.0
    if yc < 4.0:
        return "JARDIN FRONTAL (SUR)"
    if yc < 6.0:
        return "TERRAZA FRONTAL (SUR)"
    if yc < 20.0 and min(ys) >= 15.5:
        return "TERRAZA POSTERIOR"
    return "JARDIN POSTERIOR (NORTE)"


def _draw_plans(s: AutoCADService) -> None:
    """Fase 5: plantas desarrolladas con muros, vanos, cotas, ejes y simbologia."""
    define_blocks(s)
    bottom = [(1.4, [1.0, 4.0, 5.5, 5.8, 7.0]), (2.8, [1.0, 4.0, 7.0])]
    plans = (
        (U.ROOMS1, U.X1, U.Y1, U.OPEN1, U.AXES_V1, U.AXES_H1, U.FIX1, U.TITLE1, U.PB_OX,
         [(1.4, [4.0, 6.67, 8.33, 11.33, 14.5, 16.0, 18.0]),
          (2.8, [4.0, 8.33, 11.33, 14.5, 18.0])]),
        (U.ROOMS2, U.X2, U.Y2, U.OPEN2, U.AXES_V2, U.AXES_H2, U.FIX2, U.TITLE2, U.PA_OX,
         [(1.4, [4.0, 8.0, 8.33, 11.33, 13.66, 16.0]),
          (2.8, [4.0, 8.33, 11.33, 16.0])]),
    )
    for rooms, X, Y, opens, av, ah, fix, title, ox, left in plans:
        _draw_floor(
            s, rooms, X, Y, opens, av, ah, fix, title,
            bottom_levels=bottom, left_levels=left,
            ox=ox,
        )
        _terreno(s, ox)
        draw_stair_u(s, U.STAIR, ox, 0.0)
        _level(s, X[0] + ox - 1.2, Y[0] + 0.3, U.NPT_PB if ox == U.PB_OX else U.NPT_PA)
    for pts in (U.JARDIN_FRONTAL, U.TERRAZA_POST, U.JARDIN_POST):
        _outline(s, pts, U.PB_OX)
    for pts in (U.BALCON_FRONTAL, U.BALCON_POST):
        _outline(s, pts, U.PA_OX)
    # referencia de corte A-A (eje x=4) en ambas plantas
    _section_mark(s, 4.0 + U.PB_OX, 0.5, 15.2, "A")
    _section_mark(s, 4.0 + U.PA_OX, 0.5, 15.2, "A")
    _scale_bar(s, U.PB_OX, 0.4)


def _line(s: AutoCADService, p0, p1, layer: str = "A-MUROS-TABIQ") -> None:
    s.layer_tools.set_current_layer(layer)
    s.geometry.create_line([round(p0[0], 3), round(p0[1], 3)],
                           [round(p1[0], 3), round(p1[1], 3)], "bylayer")


def _band_rect(s: AutoCADService, x0: float, y0: float, x1: float, y1: float,
               layer: str = "A-MUROS-TABIQ", fill: bool = True) -> list:
    """Rectangulo (muro/losa/vanos en corte o alzado) con relleno SOLID opcional."""
    s.layer_tools.set_current_layer(layer)
    r = s.geometry.create_polyline([[x0, y0], [x1, y0], [x1, y1], [x0, y1]],
                                   closed=True, color="bylayer")
    h = list(r.get("handles", [])) if r.get("success") else []
    if fill and h:
        s.geometry.create_hatch(h, "SOLID", layer=layer, color="bylayer")
    return h


def _txt(s: AutoCADService, x: float, y: float, t: str, h: float = 0.2) -> None:
    s.layer_tools.set_current_layer("A-TEXTOS")
    s.geometry.create_text([round(x, 3), round(y, 3)], t, round(h, 3), "bylayer")


def _stair_section(s: AutoCADService, sy, sz, stair: dict) -> None:
    y0, y1 = stair["y0"], stair["y1"]
    n = 12
    step = (y1 - y0) / n
    zs = U.H_ENTREPISO / n
    pts = [[sy(y0), sz(0)]]
    for i in range(n):
        pts.append([sy(y0 + i * step), sz((i + 1) * zs)])
        pts.append([sy(y0 + (i + 1) * step), sz((i + 1) * zs)])
    s.layer_tools.set_current_layer("A-MUROS-TABIQ")
    s.geometry.create_polyline(pts, closed=False, color="bylayer")


def _corte(s: AutoCADService, ox: float, oy: float, cut_x: float, y0: float, y1: float,
           label: str, pb_walls: list, pa_walls: list, stair: dict | None = None) -> None:
    """Corte esquematico: horizontal = Y (profundidad), vertical = Z (altura)."""
    t = 0.15
    sy = lambda y: round(ox + (y - y0), 3)
    sz = lambda z: round(oy + z, 3)
    _line(s, [sy(y0 - 0.6), sz(0)], [sy(y1 + 0.6), sz(0)], "A-TERRENO")
    _band_rect(s, sy(y0), sz(-0.3), sy(y0) + t, sz(U.H_TECHO), "A-MUROS-CARGA")
    _band_rect(s, sy(y1) - t, sz(-0.3), sy(y1), sz(U.H_TECHO), "A-MUROS-CARGA")
    _band_rect(s, sy(y0), sz(-0.15), sy(y1), sz(0), "A-MUROS-CARGA")
    _band_rect(s, sy(y0), sz(U.H_ENTREPISO - 0.15), sy(y1), sz(U.H_ENTREPISO), "A-MUROS-CARGA")
    _band_rect(s, sy(y0), sz(U.H_TECHO - 0.15), sy(y1), sz(U.H_TECHO), "A-MUROS-CARGA")
    for yw in pb_walls:
        _band_rect(s, sy(yw) - t / 2, sz(0), sy(yw) + t / 2, sz(U.H_ENTREPISO - 0.15),
                   "A-MUROS-TABIQ")
    for yw in pa_walls:
        _band_rect(s, sy(yw) - t / 2, sz(U.H_ENTREPISO), sy(yw) + t / 2,
                   sz(U.H_TECHO - 0.15), "A-MUROS-TABIQ")
    if stair:
        _stair_section(s, sy, sz, stair)
    for z, lab in ((0.0, "+0.00"), (U.H_ENTREPISO, "+2.80"), (U.H_TECHO, "+5.60")):
        _line(s, [sy(y0) - 1.7, sz(z)], [sy(y0) - 1.2, sz(z)], "A-EJES")
        _txt(s, sy(y0) - 1.1, sz(z) - 0.08, lab, 0.18)
    _txt(s, sy(y0) - 1.0, sz(U.H_TECHO) + 0.6, f"CORTE {label} (x={cut_x:.2f})", 0.24)


def _corte_t(s: AutoCADService, ox: float, oy: float, cut_y: float, x0: float, x1: float,
             label: str, walls: list) -> None:
    """Corte transversal: horizontal = X (ancho), vertical = Z (altura)."""
    t = 0.15
    sx = lambda x: round(ox + (x - x0), 3)
    sz = lambda z: round(oy + z, 3)
    _line(s, [sx(x0 - 0.6), sz(0)], [sx(x1 + 0.6), sz(0)], "A-TERRENO")
    _band_rect(s, sx(x0), sz(-0.3), sx(x0) + t, sz(U.H_TECHO), "A-MUROS-CARGA")
    _band_rect(s, sx(x1) - t, sz(-0.3), sx(x1), sz(U.H_TECHO), "A-MUROS-CARGA")
    _band_rect(s, sx(x0), sz(-0.15), sx(x1), sz(0), "A-MUROS-CARGA")
    _band_rect(s, sx(x0), sz(U.H_ENTREPISO - 0.15), sx(x1), sz(U.H_ENTREPISO), "A-MUROS-CARGA")
    _band_rect(s, sx(x0), sz(U.H_TECHO - 0.15), sx(x1), sz(U.H_TECHO), "A-MUROS-CARGA")
    for xw in walls:
        _band_rect(s, sx(xw) - t / 2, sz(0), sx(xw) + t / 2, sz(U.H_ENTREPISO - 0.15),
                   "A-MUROS-TABIQ")
        _band_rect(s, sx(xw) - t / 2, sz(U.H_ENTREPISO), sx(xw) + t / 2,
                   sz(U.H_TECHO - 0.15), "A-MUROS-TABIQ")
    for z, lab in ((0.0, "+0.00"), (U.H_ENTREPISO, "+2.80"), (U.H_TECHO, "+5.60")):
        _line(s, [sx(x0) - 1.7, sz(z)], [sx(x0) - 1.2, sz(z)], "A-EJES")
        _txt(s, sx(x0) - 1.1, sz(z) - 0.08, lab, 0.18)
    _txt(s, sx(x0) - 0.6, sz(U.H_TECHO) + 0.6, f"CORTE {label} (y={cut_y:.2f})", 0.24)


def _elevacion(s: AutoCADService, ox: float, oy: float, x0: float, x1: float, label: str,
               vanos: list, balcon: bool = False) -> None:
    """Elevacion esquematica: horizontal = X (ancho), vertical = Z (altura)."""
    sx = lambda x: round(ox + (x - x0), 3)
    sz = lambda z: round(oy + z, 3)
    _line(s, [sx(x0 - 0.6), sz(0)], [sx(x1 + 0.6), sz(0)], "A-TERRENO")
    _band_rect(s, sx(x0), sz(0), sx(x1), sz(U.H_TECHO), "A-PROYECC", fill=False)
    _line(s, [sx(x0 - 0.15), sz(U.H_ENTREPISO)], [sx(x1 + 0.15), sz(U.H_ENTREPISO)], "A-PROYECC")
    _line(s, [sx(x0 - 0.25), sz(U.H_TECHO)], [sx(x1 + 0.25), sz(U.H_TECHO)], "A-PROYECC")
    if balcon:
        _band_rect(s, sx(x0 - 0.2), sz(U.H_ENTREPISO - 0.15), sx(x1 + 0.2), sz(U.H_ENTREPISO),
                   "A-PROYECC")
        for xx in (x0 - 0.2, x1 + 0.2):
            _line(s, [sx(xx), sz(U.H_ENTREPISO)], [sx(xx), sz(U.H_ENTREPISO + 1.0)], "A-PROYECC")
        _line(s, [sx(x0 - 0.2), sz(U.H_ENTREPISO + 1.0)], [sx(x1 + 0.2), sz(U.H_ENTREPISO + 1.0)],
              "A-PROYECC")
    for (a, b, z0, z1) in vanos:
        _band_rect(s, sx(a), sz(z0), sx(b), sz(z1), "A-PUER-VENT", fill=False)
    _txt(s, sx(x0), sz(U.H_TECHO) + 0.6, label, 0.26)


def _cortes(s: AutoCADService) -> None:
    """Lamina de cortes: A-A (longitudinal por la escalera) y B-B (transversal)."""
    _corte(s, 70.0, 2.0, 5.0, 4.0, 16.0, "A-A",
           pb_walls=[6.67, 8.33, 11.33, 14.5], pa_walls=[8.33, 11.33, 13.66], stair=U.STAIR)
    _corte_t(s, 70.0, 12.0, 10.0, 1.0, 7.0, "B-B", walls=[4.0, 5.5])
    _txt(s, 70.0, 1.0, "LOSAS Y MUROS: ANTEPROYECTO (0.15 m); ALT. ENTREPISO 2.80 m PENDIENTE",
         0.18)


def _elevaciones(s: AutoCADService) -> None:
    """Lamina de elevaciones: frontal (SUR) y posterior (NORTE)."""
    _elevacion(s, 92.0, 2.0, 1.0, 7.0, "ELEVACION FRONTAL (SUR)",
               vanos=[(1.4, 3.7, 0.0, 2.40), (4.6, 5.5, 0.0, 2.10),
                      (1.6, 3.4, 3.70, 4.90), (4.6, 6.4, 3.70, 4.90)], balcon=True)
    _elevacion(s, 92.0, 12.0, 1.0, 7.0, "ELEVACION POSTERIOR (NORTE)",
               vanos=[(1.6, 3.6, 0.0, 2.10), (4.6, 6.8, 1.0, 2.10),
                      (1.6, 3.6, 3.70, 4.90), (4.7, 5.2, 4.20, 4.90), (5.8, 6.3, 4.20, 4.90)])
    _txt(s, 92.0, 1.0, "ALTURAS REFERENCIALES: N.P.T. +0.00 / +2.80 / +5.60 (PENDIENTE)", 0.18)


def _detalles(s: AutoCADService) -> None:
    """Detalles ampliados (en hoja a 1:150, dibujados x3 => 1:50)."""
    k = 3.0
    st = U.STAIR
    ex, ey = 110.0, 2.0
    px = lambda x: round(ex + (x - st["x0"]) * k, 3)
    py = lambda y: round(ey + (y - st["y0"]) * k, 3)
    _band_rect(s, px(st["x0"]), py(st["y0"]), px(st["x1"]), py(st["y1"]), "A-MUROS-TABIQ",
               fill=False)
    fl, fr = st["x0"] + 0.9, st["x1"] - 0.9
    _line(s, [px(fl), py(st["y0"])], [px(fl), py(st["y1"])], "A-MUROS-TABIQ")
    _line(s, [px(fr), py(st["y0"])], [px(fr), py(st["y1"])], "A-MUROS-TABIQ")
    n = 8
    run = (st["y1"] - st["y0"]) - 1.0
    step = run / n
    for i in range(1, n + 1):
        yy = st["y0"] + i * step
        _line(s, [px(st["x0"]), py(yy)], [px(fl), py(yy)], "A-MUROS-TABIQ")
        _line(s, [px(fr), py(yy)], [px(st["x1"]), py(yy)], "A-MUROS-TABIQ")
    _line(s, [px(st["x0"]), py(st["y0"] + run)], [px(st["x1"]), py(st["y0"] + run)],
          "A-MUROS-TABIQ")
    _txt(s, px(st["x0"]), py(st["y1"]) + 0.8, "DETALLE ESCALERA (ESC. 1:50)", 0.24)
    _txt(s, px(st["x0"]), py(st["y0"]) - 1.4,
         "16 ALZADAS x 0.175 m / HUELLA 0.25 m / ANCHO UTIL 0.90 m", 0.18)

    bx, by = 122.0, 2.0
    w, d = 1.5 * k, 2.33 * k
    _band_rect(s, bx, by, bx + w, by + d, "A-MUROS-TABIQ", fill=False)
    _band_rect(s, bx + 0.2, by + d - 1.1, bx + 0.2 + 0.9, by + d - 0.2, "A-MOBILIARIO",
               fill=False)
    _band_rect(s, bx + 0.2, by + d - 2.0, bx + 0.2 + 0.55, by + d - 2.0 + 0.42,
               "A-MOBILIARIO", fill=False)
    _band_rect(s, bx + w - 0.6, by + 0.3, bx + w - 0.2, by + 0.7, "A-MOBILIARIO", fill=False)
    _txt(s, bx, by + d + 0.8, "DETALLE SS.HH. (ESC. 1:50)", 0.24)
    _txt(s, bx, by - 1.4, "INODORO + LAVATORIO + DUCHA 1.50 x 2.33 m", 0.18)

    vx, vy = 110.0, 14.0
    _band_rect(s, vx, vy, vx + 0.9 * k, vy + 2.1 * k, "A-PUER-VENT", fill=False)
    _line(s, [vx, vy + 2.1 * k], [vx + 0.9 * k, vy + 2.1 * k], "A-PUER-VENT")
    _txt(s, vx, vy + 2.1 * k + 0.6, "DETALLE DE VANOS (ESC. 1:50)", 0.24)


def _frame_sheet(s: AutoCADService, layout: str, vcx: float, vcy: float,
                 vpw: float = 150.0, vph: float = 244.0, scale: float = 0.01,
                 center: tuple[float, float] = (148.5, 118.0)) -> None:
    """Deja UN viewport centrado en la hoja y a escala real (CustomScale).

    Evita el ``ZOOM`` por SendCommand: fija ``Target`` (centro del modelo) y
    ``CustomScale`` para que la planta quede centrada y fiel a 1:100.
    """
    import time as _t

    doc = s.conn.doc
    _retry(lambda: s.layouts.set_active_layout(layout))
    ps = _retry(lambda: as_dynamic(doc.PaperSpace))
    vps = []
    for i in range(int(_retry(lambda: ps.Count))):
        try:
            e = as_dynamic(ps.Item(i))
            if str(e.ObjectName) == "AcDbViewport":
                vps.append(e)
        except Exception:  # noqa: BLE001
            continue
    for v in vps:
        for _ in range(6):
            try:
                v.Delete()
                break
            except Exception:  # noqa: BLE001
                _t.sleep(0.3)
    _retry(lambda: s.layouts.create_viewport(
        layout, center=[center[0], center[1]], width=vpw, height=vph,
        scale=scale, view_center=[vcx, vcy]))
    _retry(lambda: doc.Regen(0))


def _set_pdf_device(s: AutoCADService, layout: str) -> None:
    """Fase 8/9: deja el layout listo para trazar a PDF en A3 (DWG To PDF.pc3)."""
    pdf_pc3 = str(Path(os.environ.get("APPDATA", "")) / "Autodesk" / "AutoCAD 2026" / "R25.1"
                  / "enu" / "plotters" / "DWG To PDF.pc3")
    if not os.path.exists(pdf_pc3):
        return
    try:
        _retry(lambda: s.layouts.set_active_layout(layout))
        al = _retry(lambda: as_dynamic(s.conn.doc.ActiveLayout))
        _retry(lambda: setattr(al, "ConfigName", pdf_pc3))
        _retry(lambda: setattr(al, "CanonicalMediaName", "ISO_A4_(297.00_x_210.00_MM)"))
        _retry(lambda: setattr(al, "PlotType", 5))  # 5 = Layout
    except Exception as exc:  # noqa: BLE001
        _log("aviso dispositivo PDF", layout, exc)


def _cajetin(s: AutoCADService, layout: str, content: str, codigo: str, escala: str,
             note: str = "") -> None:
    """Fase 8: membrete UCV en el espacio papel del layout (A4 horizontal)."""
    _retry(lambda: s.layouts.set_active_layout(layout))
    ps = _retry(lambda: as_dynamic(s.conn.doc.PaperSpace))
    # Hoja A4 horizontal: 297 x 210 mm. Cajetin en la franja inferior.
    x0, y0, x1, y1 = 7.0, 6.0, 290.0, 30.0
    ly = "A-ROTULO"
    try:
        s.conn.doc.ActiveLayer = _retry(lambda: s.conn.doc.Layers.Item(ly))
    except Exception:  # noqa: BLE001
        pass

    def line(ax, ay, bx, by):
        _retry(lambda: ps.AddLine(variant_point(ax, ay), variant_point(bx, by)))

    def txt(t, ax, ay, h):
        o = _retry(lambda: ps.AddText(t, variant_point(ax, ay), h))
        try:
            o.Layer = ly
        except Exception:  # noqa: BLE001
            pass

    # marco y divisiones (banda de titulo 24-30, datos 14-24, notas 6-14)
    line(x0, y0, x1, y0)
    line(x1, y0, x1, y1)
    line(x1, y1, x0, y1)
    line(x0, y1, x0, y0)
    line(x0, 24.0, x1, 24.0)
    line(x0, 14.0, x1, 14.0)
    for xv in (100.0, 185.0, 240.0):
        line(xv, 14.0, xv, 24.0)

    txt("UNIVERSIDAD CESAR VALLEJO - FACULTAD DE ARQUITECTURA", x0 + 2, 26.4, 3.0)
    txt("PROYECTO: Vivienda unifamiliar", x0 + 2, 20.4, 2.2)
    txt("UBICACION: Psje. Magisterial N.230 - Independencia, Huaraz", x0 + 2, 16.0, 1.8)
    txt("RESPONSABLE: ________________", 102.0, 20.4, 2.0)
    txt("FECHA: 2026", 102.0, 16.0, 2.0)
    txt("ESCALA:", 187.0, 20.6, 2.0)
    txt(escala, 187.0, 15.8, 2.8)
    txt(f"LAMINA: {codigo}", 242.0, 20.2, 2.4)
    txt("A4 HORIZONTAL", 242.0, 15.8, 1.8)
    txt(f"CONTENIDO: {content}", x0 + 2, 10.6, 1.9)
    if note:
        txt(f"NOTA: {note[:88]}", x0 + 2, 7.4, 1.5)


def main() -> int:
    s = AutoCADService()
    if not s.connect():
        _log("ABORT: sin conexion a AutoCAD")
        return 1
    name = _ensure_target(s)
    _log("Documento:", name)

    for _lm in ("PLANTAS", "ZONIFICACION", "PLANTA BAJA", "PLANTA ALTA",
                "CORTES", "ELEVACIONES", "DETALLES", "CUADROS"):
        try:
            s.conn.doc.Layouts.Item(_lm).Delete()
        except Exception:  # noqa: BLE001
            pass
    s.deleter.delete_all_entities(confirm=True)
    std = s.standards.apply_standard()
    _log(std["message"])

    for lay, color in (
        ("Z-SOCIAL", "magenta"),
        ("Z-SERVICIOS", "blue"),
        ("Z-PRIVADA", "green"),
        ("Z-CIRCULACION", "yellow"),
        ("Z-AREA-LIBRE", "green"),
        ("A-TERRENO", "white"),
        ("A-ROTULO", "white"),
    ):
        s.layer_tools.create_or_get_layer(lay, color, "Zonificacion / presentacion")

    # Fase 6: jerarquia de grosores por capa.
    for lay, lw in LINEWEIGHTS.items():
        try:
            _retry(lambda lay=lay, lw=lw: setattr(s.conn.doc.Layers.Item(lay), "Lineweight", lw))
        except Exception as exc:  # noqa: BLE001
            _log("aviso grosor", lay, exc)

    # Fase 3: zonificacion.
    _zoning(s)
    _legend(s, 19.5, 22.6)
    _north(s, 26.8, 20.6)

    # Fase 5: plantas desarrolladas.
    _draw_plans(s)

    # Láminas de cortes, elevaciones y detalles (memoria del proyecto).
    _cortes(s)
    _elevaciones(s)
    _detalles(s)

    # Fase 5: cuadros (areas y vanos).
    _retry(lambda: _draw_area_table(
        s, AR.table_rows(), x0=29.5, y_top=24.5, w1=4.6, w2=1.7, rh=0.44, th=0.17,
        header="CUADRO DE AREAS"))
    _retry(lambda: _draw_area_table(
        s, AR.vanos_rows(), x0=29.5, y_top=13.4, w1=4.6, w2=1.0, rh=0.40, th=0.13,
        header="CUADRO DE VANOS"))
    d = AR.schedule()
    _log(f"areas: PB {d['total_pb']:.2f} / PA {d['total_pa']:.2f} / "
         f"total {d['total']:.2f} / libre {d['area_libre']:.2f} ({d['libre_pct']:.1f}%)")

    s.ops.zoom_extents()

    # Fase 8: layouts A4 HORIZONTAL (297 x 210 mm), un viewport centrado y a escala real.
    # (nombre, centro_modelo_x, centro_modelo_y, ancho_vp_mm, alto_vp_mm, escala, lamina)
    sc = 1.0 / 150.0
    sheets = (
        ("PLANTAS", 49.5, 11.5, 195.0, 168.0, sc, "A-01"),
        ("ZONIFICACION", 18.0, 12.3, 250.0, 170.0, sc, "A-02"),
        ("CORTES", 75.0, 10.0, 150.0, 132.0, sc, "A-03"),
        ("ELEVACIONES", 95.0, 10.0, 135.0, 132.0, sc, "A-04"),
        ("DETALLES", 118.0, 11.0, 150.0, 142.0, sc, "A-05"),
    )
    for nm, _vcx, _vcy, _w, _h, _sc, _cod in sheets:
        _retry(lambda nm=nm: s.layouts.create_layout(
            nm, media="ISO_A4_(297.00_x_210.00_MM)", plot_style_table="acad.ctb"))
        _set_pdf_device(s, nm)
    for nm, vcx, vcy, w, h, sc, _cod in sheets:
        _frame_sheet(s, nm, vcx, vcy, vpw=w, vph=h, scale=sc)

    # Fase 8: membrete UCV por lamina.
    note = ("Anteproyecto referencial. Lote 8.00 x 23.00 m; construido 6.00 m (retiros "
            "1.00 m). Frente SUR, fondo NORTE. SS.HH. 1 (PB), SS.HH. 2 (privado del dorm. "
            "principal) y SS.HH. 3 (compartido) en PA. Muros 0.15 m. Alturas y areas "
            "PENDIENTES de verificacion.")
    _cajetin(s, "PLANTAS", "Plantas arquitectonicas PB + PA (cotas, ejes y vanos)",
             "A-01", "1:150", note)
    _cajetin(s, "ZONIFICACION", "Distribucion y zonificacion + cuadros de areas y vanos",
             "A-02", "1:150", note)
    _cajetin(s, "CORTES", "Cortes A-A (longitudinal) y B-B (transversal)", "A-03", "1:150", note)
    _cajetin(s, "ELEVACIONES", "Elevaciones frontal y posterior", "A-04", "1:150", note)
    _cajetin(s, "DETALLES", "Detalles de escalera, SS.HH. y vanos", "A-05", "1:150", note)
    s.layouts.set_active_layout("Model")

    # Fase 9: guarda el archivo de trabajo y deja una copia en un archivo NUEVO.
    _retry(lambda: s.conn.doc.Save())
    shutil.copy2(TARGET_PATH, NEW_PATH)
    rep = s.analysis.analyze_drawing()
    if "summary" in rep:
        _log("entidades:", rep["summary"]["total_entities"])
        _log("por capa:", rep["summary"]["counts_by_layer"])
    _log("copia nueva:", NEW_PATH)
    _log("listo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
