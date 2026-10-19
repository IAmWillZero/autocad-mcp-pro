"""Fase 1-2 del reporte UCV: nuevo DWG con zonificacion semitransparente.

Crea un documento dedicado ``Vivienda_UCV_Magisterial_230.dwg`` (carpeta ``out/``,
ignorada por git), aplica unidades/estandar metrico, crea las capas ``Z-`` de
zonificacion y dibuja, para ambas plantas, las zonas funcionales como rellenos
(SOLID semitransparente ~50 %, achurado ANSI31 para area libre) con rotulo.

NO dibuja muros definitivos: es la fase de zonificacion; los poligonos son
reservas graficas segun el reporte (a ajustar cuando se fijen coordenadas).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from autocad_mcp.service import AutoCADService  # noqa: E402

import ucv_data as U  # noqa: E402  (scripts/house en sys.path)
from house_blocks import define_blocks  # noqa: E402
from house_main import _draw_floor  # noqa: E402
from draw_house import _frame_viewport, _draw_area_table  # noqa: E402
import ucv_areas as AR  # noqa: E402

OUT_DIR = str(ROOT / "out")
TARGET = "Vivienda_UCV_Magisterial_230.dwg"
TARGET_PATH = os.path.join(OUT_DIR, TARGET)

OX = 10.0  # separacion en X entre planta baja y planta alta

# capa -> (color ACI, patron, transparencia, escala)
ZONE_STYLE = {
    "Z-SOCIAL": ("magenta", "SOLID", "50", 1.0),
    "Z-SERVICIOS": ("blue", "SOLID", "50", 1.0),
    "Z-PRIVADA": ("green", "SOLID", "50", 1.0),
    "Z-AREA-LIBRE": ("green", "ANSI31", "60", 0.35),
}


def _rect(x0: float, y0: float, x1: float, y1: float) -> list[list[float]]:
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


# (capa, puntos, etiqueta, punto_etiqueta)
# ORIENTACION: frente=SUR (y=0), fondo=NORTE (y=23), X+ = ESTE.
PB: list[tuple[str, list[list[float]], str, list[float]]] = [
    ("Z-AREA-LIBRE", _rect(0.15, 0.15, 7.85, 4.00), "JARDIN FRONTAL (SUR)", [4.0, 2.0]),
    ("Z-SERVICIOS", _rect(1.00, 4.05, 4.00, 9.50), "GARAJE (SO)", [2.5, 6.7]),
    ("Z-SERVICIOS", _rect(4.00, 4.05, 7.00, 6.67), "OFICINA (SE)", [5.5, 5.3]),
    ("Z-SERVICIOS", _rect(4.00, 6.67, 7.00, 9.50), "LAVANDERIA / SS.HH. 1", [5.5, 8.1]),
    ("Z-SERVICIOS", _rect(4.00, 9.50, 7.00, 13.00), "COCINA (ESTE)", [5.5, 11.2]),
    ("Z-SOCIAL", [[1.00, 9.50], [4.00, 9.50], [4.00, 13.00], [7.00, 13.00],
                  [7.00, 16.00], [1.00, 16.00]],
     "SALA-COMEDOR (OESTE/CENTRO)", [3.0, 12.5]),
    ("Z-AREA-LIBRE", _rect(1.00, 16.00, 7.00, 20.00), "TERRAZA POSTERIOR (NORTE)", [4.0, 18.0]),
    ("Z-AREA-LIBRE", _rect(0.15, 21.00, 7.85, 22.85), "JARDIN POSTERIOR (NORTE)",
     [4.0, 21.9]),
]

PA: list[tuple[str, list[list[float]], str, list[float]]] = [
    ("Z-AREA-LIBRE", _rect(OX + 1.00, 2.00, OX + 7.00, 4.00), "BALCON FRONTAL (SUR)",
     [OX + 4.0, 3.0]),
    ("Z-PRIVADA", _rect(OX + 1.00, 4.00, OX + 7.00, 16.00),
     "ZONA PRIVADA (DORMITORIOS / ESTAR)", [OX + 3.0, 11.0]),
    ("Z-SERVICIOS", _rect(OX + 4.00, 8.33, OX + 7.00, 10.83), "SS.HH. (existente + nuevo)",
     [OX + 5.5, 9.6]),
    ("Z-AREA-LIBRE", _rect(OX + 1.00, 16.00, OX + 7.00, 18.00), "BALCON POSTERIOR (NORTE)",
     [OX + 4.0, 17.0]),
]


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


def _ensure_target(s: AutoCADService) -> str:
    """Usa un DWG dedicado y limpio; no toca otros documentos abiertos."""
    app = s.conn.app
    docs = app.Documents
    names = [str(_retry(lambda i=i: docs.Item(i).Name)) for i in range(int(docs.Count))]
    if TARGET in names:
        s.conn.doc = _retry(lambda: docs.Item(TARGET))
        _retry(lambda: s.conn.doc.Activate())
        return TARGET
    doc = _retry(docs.Add)
    os.makedirs(OUT_DIR, exist_ok=True)
    _retry(lambda: doc.SaveAs(TARGET_PATH))
    s.conn.doc = doc
    return str(doc.Name)


def _poly(s: AutoCADService, pts2d: list[list[float]], closed: bool = True) -> list[str]:
    r = s.geometry.create_polyline(pts2d, closed=closed, color="bylayer")
    if not r.get("success"):
        return []
    return list(r.get("handles", []))


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
    h = min(0.22, available / (len(label) * 0.95))
    h = max(0.10, h)
    w = len(label) * 0.95 * h
    s.layer_tools.set_current_layer("A-TEXTOS")
    s.geometry.create_text([round(anchor[0] - w / 2.0, 3), round(anchor[1], 3)], label,
                           round(h, 3), "bylayer")


def _terreno(s: AutoCADService, ox: float = 0.0) -> None:
    s.layer_tools.set_current_layer("A-TERRENO")
    _poly(s, _rect(ox, 0.0, ox + 8.0, 23.0))


def _legend(s: AutoCADService, x0: float, y_top: float) -> None:
    rows = [
        ("Z-SOCIAL", "ZONA SOCIAL"),
        ("Z-SERVICIOS", "ZONA SERVICIOS"),
        ("Z-PRIVADA", "ZONA PRIVADA"),
        ("Z-AREA-LIBRE", "AREA LIBRE (ANSI31)"),
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


def _outline(s: AutoCADService, pts: list[list[float]], ox: float,
             layer: str = "A-PROYECC") -> None:
    """Traza un contorno (terrazas/balcones) desplazado en X por ``ox``."""
    s.layer_tools.set_current_layer(layer)
    shifted = [[round(p[0] + ox, 3), round(p[1], 3)] for p in pts]
    _poly(s, shifted, closed=True)


def _draw_plans(s: AutoCADService) -> None:
    """Fase 3: plantas desarrolladas (muros, vanos, mobiliario, cotas, rotulos)."""
    define_blocks(s)
    _draw_floor(
        s, U.ROOMS1, U.X1, U.Y1, U.OPEN1, U.AXES_V1, U.AXES_H1, U.FIX1, U.TITLE1,
        bottom_levels=[(1.4, [1.0, 4.0, 7.0]), (2.8, [1.0, 7.0])],
        left_levels=[(1.4, [4.0, 6.67, 8.33, 9.5, 13.0, 16.0]),
                     (2.8, [4.0, 6.67, 9.5, 13.0, 16.0])],
        ox=U.PB_OX,
    )
    _terreno(s, U.PB_OX)
    for pts in (U.JARDIN_FRONTAL, U.TERRAZA_POST, U.JARDIN_POST):
        _outline(s, pts, U.PB_OX)
    _draw_floor(
        s, U.ROOMS2, U.X2, U.Y2, U.OPEN2, U.AXES_V2, U.AXES_H2, U.FIX2, U.TITLE2,
        bottom_levels=[(1.4, [1.0, 4.0, 7.0]), (2.8, [1.0, 7.0])],
        left_levels=[(1.4, [4.0, 8.0, 8.33, 9.5, 10.83, 11.33, 16.0]),
                     (2.8, [4.0, 8.0, 11.33, 16.0])],
        ox=U.PA_OX,
    )
    _terreno(s, U.PA_OX)
    for pts in (U.BALCON_FRONTAL, U.BALCON_POST):
        _outline(s, pts, U.PA_OX)


def main() -> int:
    s = AutoCADService()
    if not s.connect():
        _log("ABORT: sin conexion a AutoCAD")
        return 1
    name = _ensure_target(s)
    _log("Documento:", name)

    for _lm in ("ZONIFICACION", "PLANTA BAJA", "PLANTA ALTA"):
        try:
            s.conn.doc.Layouts.Item(_lm).Delete()
        except Exception:  # noqa: BLE001 - no existia
            pass
    s.deleter.delete_all_entities(confirm=True)
    std = s.standards.apply_standard()
    _log(std["message"])

    for lay, color in (
        ("Z-SOCIAL", "magenta"),
        ("Z-SERVICIOS", "blue"),
        ("Z-PRIVADA", "green"),
        ("Z-AREA-LIBRE", "green"),
        ("A-TERRENO", "white"),
        ("A-ROTULO", "white"),
    ):
        s.layer_tools.create_or_get_layer(lay, color, "Zonificacion / terreno")

    _terreno(s, 0.0)
    _terreno(s, OX)
    for layer, pts, label, anchor in PB:
        _zone(s, layer, pts, label, anchor)
    for layer, pts, label, anchor in PA:
        _zone(s, layer, pts, label, anchor)

    s.layer_tools.set_current_layer("A-TEXTOS")
    s.geometry.create_text([0.0, 24.2], "PLANTA BAJA - ZONIFICACION", 0.30, "bylayer")
    s.geometry.create_text([OX, 24.2], "PLANTA ALTA - ZONIFICACION", 0.30, "bylayer")
    s.geometry.create_text(
        [0.0, -1.6],
        "Psje. Magisterial N.230 - Independencia, Huaraz - Vivienda unifamiliar 8.00 x 23.00 m "
        "(zonificacion preliminar + plantas referenciales)",
        0.22,
        "bylayer",
    )
    _legend(s, 19.5, 24.4)
    _north(s, 26.5, 24.0)
    s.layer_tools.set_current_layer("A-TEXTOS")
    s.geometry.create_text(
        [0.0, 25.4],
        "ORIENTACION CARDINAL: frente = SUR (Psje. Magisterial), fondo = NORTE; X+ = ESTE. "
        "Hipotesis de lote, PENDIENTE de confirmar.",
        0.22,
        "bylayer",
    )

    # --- Fase 3: plantas desarrolladas (region aparte) ---
    _draw_plans(s)
    s.layer_tools.set_current_layer("A-TEXTOS")
    s.geometry.create_text([U.PB_OX, -1.6], U.TITLE1, 0.22, "bylayer")

    # --- Cuadro de areas + cuadro de vanos (verificacion del programa) ---
    _retry(lambda: _draw_area_table(
        s, AR.table_rows(), x0=29.5, y_top=24.5, w1=4.6, w2=1.7, rh=0.44, th=0.17))
    _retry(lambda: _draw_area_table(
        s, AR.vanos_rows(), x0=29.5, y_top=13.4, w1=4.6, w2=1.0, rh=0.40, th=0.13))
    d = AR.schedule()
    _log(f"areas: PB {d['total_pb']:.2f} / PA {d['total_pa']:.2f} / "
         f"total {d['total']:.2f} / libre {d['area_libre']:.2f} ({d['libre_pct']:.1f}%)")

    s.ops.zoom_extents()
    _retry(
        lambda: s.layouts.create_layout(
            "ZONIFICACION", media="ISO_A3_(297.00_x_420.00_MM)", plot_style_table="acad.ctb"
        )
    )
    _retry(
        lambda: s.layouts.create_viewport(
            "ZONIFICACION", center=[148.5, 210.0], width=280.0, height=390.0,
            scale=0.01, view_center=[13.0, 11.8],
        )
    )
    for name, vcx, vcy in (
        ("PLANTA BAJA", 43.0, 9.5),
        ("PLANTA ALTA", 57.0, 9.0),
    ):
        _retry(
            lambda name=name: s.layouts.create_layout(
                name, media="ISO_A3_(297.00_x_420.00_MM)", plot_style_table="acad.ctb"
            )
        )
        _retry(
            lambda name=name, vcx=vcx, vcy=vcy: s.layouts.create_viewport(
                name, center=[148.5, 210.0], width=170.0, height=372.0,
                scale=0.01, view_center=[vcx, vcy],
            )
        )
    # Deja solo el viewport propio en cada lamina (borra los de plantilla).
    for name, vcx, vcy, vp_w in (
        ("ZONIFICACION", 13.0, 11.8, 280.0),
        ("PLANTA BAJA", 43.0, 9.5, 170.0),
        ("PLANTA ALTA", 57.0, 9.0, 170.0),
    ):
        _retry(lambda name=name, vcx=vcx, vcy=vcy, vp_w=vp_w:
               _frame_viewport(s, name, vcx, vcy, scale=0.01, vp_width=vp_w))
    s.layouts.set_active_layout("Model")

    _retry(lambda: s.conn.doc.Save())
    rep = s.analysis.analyze_drawing()
    if "summary" in rep:
        _log("entidades:", rep["summary"]["total_entities"])
        _log("por capa:", rep["summary"]["counts_by_layer"])
    else:
        _log("analisis no disponible:", rep.get("error"))
    _log("listo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
