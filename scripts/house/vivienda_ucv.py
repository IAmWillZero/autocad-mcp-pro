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
PB: list[tuple[str, list[list[float]], str, list[float]]] = [
    ("Z-AREA-LIBRE", _rect(0.15, 0.15, 7.85, 4.00), "JARDIN FRONTAL (AREA LIBRE)", [4.0, 2.0]),
    ("Z-SERVICIOS", _rect(5.00, 4.05, 7.85, 8.35), "GARAJE / OFICINA", [6.4, 6.2]),
    ("Z-SOCIAL", _rect(0.15, 4.05, 4.90, 16.90), "ZONA SOCIAL (SALA-COMEDOR)", [2.5, 10.5]),
    ("Z-SERVICIOS", _rect(5.00, 8.50, 7.85, 16.90), "COCINA / LAVANDERIA / SS.HH.",
     [6.4, 12.5]),
    ("Z-AREA-LIBRE", _rect(0.15, 17.00, 7.85, 20.90), "TERRAZA POSTERIOR", [4.0, 18.9]),
    ("Z-AREA-LIBRE", _rect(0.15, 21.00, 7.85, 22.85), "JARDIN POSTERIOR", [4.0, 21.9]),
]

PA: list[tuple[str, list[list[float]], str, list[float]]] = [
    ("Z-AREA-LIBRE", _rect(OX + 0.15, 4.05, OX + 7.85, 6.00), "BALCON FRONTAL",
     [OX + 4.0, 5.0]),
    # zona privada en L (deja el hueco del nuevo SS.HH. apilado)
    ("Z-PRIVADA", [[OX + 0.15, 6.10], [OX + 7.85, 6.10], [OX + 7.85, 13.00],
                   [OX + 5.00, 13.00], [OX + 5.00, 15.50], [OX + 7.85, 15.50],
                   [OX + 7.85, 19.00], [OX + 0.15, 19.00]],
     "ZONA PRIVADA (DORMITORIOS / ESTAR)", [OX + 2.6, 10.0]),
    ("Z-SERVICIOS", _rect(OX + 5.00, 13.00, OX + 7.85, 15.50), "SS.HH.", [OX + 6.4, 14.2]),
    ("Z-AREA-LIBRE", _rect(OX + 0.15, 19.10, OX + 7.85, 21.00), "BALCON POSTERIOR",
     [OX + 4.0, 20.0]),
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


def main() -> int:
    s = AutoCADService()
    if not s.connect():
        _log("ABORT: sin conexion a AutoCAD")
        return 1
    name = _ensure_target(s)
    _log("Documento:", name)

    for _lm in ("ZONIFICACION",):
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
    s.geometry.create_text([0.0, 24.2], "PLANTA BAJA - ZONIFICACION (PRELIMINAR)", 0.30,
                           "bylayer")
    s.geometry.create_text([OX, 24.2], "PLANTA ALTA - ZONIFICACION (PRELIMINAR)", 0.30,
                           "bylayer")
    s.geometry.create_text(
        [0.0, -1.6],
        "Psje. Magisterial N.230 - Independencia, Huaraz - Vivienda unifamiliar 8.00 x 23.00 m",
        0.22,
        "bylayer",
    )
    _legend(s, 19.5, 24.4)
    _north(s, 26.5, 24.0)

    s.ops.zoom_extents()
    _retry(
        lambda: s.layouts.create_layout(
            "ZONIFICACION", media="ISO_A3_(297.00_x_420.00_MM)", plot_style_table="acad.ctb"
        )
    )
    _retry(
        lambda: s.layouts.create_viewport(
            "ZONIFICACION", center=[148.5, 210.0], width=280.0, height=390.0,
            scale=10.0, view_center=[13.0, 11.8],
        )
    )
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
