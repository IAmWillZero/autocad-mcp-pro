"""Vivienda UCV Magisterial 230: DWG unico con zonificacion + plantas + presentacion.

Reune las fases del informe de mejora:
- Fase 2: dos banos (SS.HH. 1 PB / SS.HH. 2 PA) apilados al norte de la escalera.
- Fase 3: zonificacion por ambiente (social/servicios/privada/circulacion/libre),
  semitransparente, sin ocultar lineas.
- Fase 4: biblioteca de bloques normalizados (se define e inserta).
- Fase 5: cotas, ejes coordinados, niveles, norte, escala grafica, cuadros y simbologia.
- Fase 6: jerarquia de grosores por capa.
- Fase 8: layouts A3 con membrete UCV.
- Fase 9: guarda una copia en un archivo NUEVO.

Regenera el documento desde cero (idempotente). Unidades metros, 1:1 en Modelo.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from autocad_mcp.com import as_dynamic, variant_point  # noqa: E402
from autocad_mcp.service import AutoCADService  # noqa: E402

import ucv_areas as AR  # noqa: E402
import ucv_data as U  # noqa: E402
from draw_house import _draw_area_table, _frame_viewport  # noqa: E402
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
    doc = _retry(docs.Add)
    os.makedirs(OUT_DIR, exist_ok=True)
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


def _zoning(s: AutoCADService) -> None:
    _terreno(s, 0.0)
    _terreno(s, OX)
    _room_zones(s, U.ROOMS1, U.X1, U.Y1, 0.0)
    _room_zones(s, U.ROOMS2, U.X2, U.Y2, OX)
    for pts in (U.JARDIN_FRONTAL, U.TERRAZA_POST, U.JARDIN_POST):
        _zone(s, "Z-AREA-LIBRE", pts, _lib_label(pts), _mid(pts))
    for pts in (U.BALCON_FRONTAL, U.BALCON_POST):
        _zone(s, "Z-AREA-LIBRE", [[p[0] + OX, p[1]] for p in pts], _lib_label(pts), _mid(pts, OX))
    s.layer_tools.set_current_layer("A-TEXTOS")
    s.geometry.create_text([0.0, 24.2], "PLANTA BAJA - ZONIFICACION", 0.30, "bylayer")
    s.geometry.create_text([OX, 24.2], "PLANTA ALTA - ZONIFICACION", 0.30, "bylayer")


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
        return "BALCON FRONTAL (SUR)"
    if yc < 20.0 and min(ys) >= 15.5:
        return "TERRAZA / BALCON"
    return "JARDIN POSTERIOR (NORTE)"


def _draw_plans(s: AutoCADService) -> None:
    """Fase 5: plantas desarrolladas con muros, vanos, cotas, ejes y simbologia."""
    define_blocks(s)
    for rooms, X, Y, opens, av, ah, fix, title, ox in (
        (U.ROOMS1, U.X1, U.Y1, U.OPEN1, U.AXES_V1, U.AXES_H1, U.FIX1, U.TITLE1, U.PB_OX),
        (U.ROOMS2, U.X2, U.Y2, U.OPEN2, U.AXES_V2, U.AXES_H2, U.FIX2, U.TITLE2, U.PA_OX),
    ):
        _draw_floor(
            s, rooms, X, Y, opens, av, ah, fix, title,
            bottom_levels=[(1.4, [X[0], X[1], X[2]]), (2.8, [X[0], X[2]])],
            left_levels=[(1.4, list(Y)), (2.8, [Y[0], Y[1], Y[6], Y[7], Y[8]])],
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
    _scale_bar(s, U.PB_OX, -1.6)


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
        _retry(lambda: setattr(al, "CanonicalMediaName", "ISO_A3_(297.00_x_420.00_MM)"))
        _retry(lambda: setattr(al, "PlotType", 5))  # 5 = Layout
    except Exception as exc:  # noqa: BLE001
        _log("aviso dispositivo PDF", layout, exc)


def _cajetin(s: AutoCADService, layout: str, content: str, codigo: str, escala: str) -> None:
    """Fase 8: membrete UCV en el espacio papel del layout."""
    _retry(lambda: s.layouts.set_active_layout(layout))
    ps = _retry(lambda: as_dynamic(s.conn.doc.PaperSpace))
    x0, y0, x1, y1 = 8.5, 14.0, 288.5, 52.0
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

    line(x0, y0, x1, y0)
    line(x1, y0, x1, y1)
    line(x1, y1, x0, y1)
    line(x0, y1, x0, y0)
    line(x0, y0 + 12, x1, y0 + 12)
    for xv in (70.0, 150.0, 210.0):
        line(xv, y0, xv, y0 + 12)
    txt("UNIVERSIDAD CESAR VALLEJO - FACULTAD DE ARQUITECTURA", x0 + 3, y1 - 7, 4.0)
    txt(f"PROYECTO: {content}", x0 + 3, y0 + 6.5, 3.0)
    txt("UBICACION: Psje. Magisterial N.230 - Independencia, Huaraz", x0 + 3, y0 + 2.5, 2.6)
    txt("RESPONSABLE: ____", 73.0, y0 + 6.5, 2.6)
    txt("FECHA: 2026", 73.0, y0 + 2.5, 2.6)
    txt(f"ESCALA: {escala}", 153.0, y0 + 6.5, 2.6)
    txt("NORTE: como plano", 153.0, y0 + 2.5, 2.6)
    txt(f"LAMINA: {codigo}", 213.0, y0 + 6.5, 3.0)


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
    s.layer_tools.set_current_layer("A-TEXTOS")
    s.geometry.create_text(
        [0.0, -1.6],
        "Psje. Magisterial N.230 - Independencia, Huaraz - Vivienda unifamiliar - lote 8.00 x 23.00 m "
        "(construido 6.00 m; zonificacion + plantas referenciales)",
        0.22, "bylayer",
    )
    _legend(s, 19.5, 24.4)
    _north(s, 26.5, 24.0)
    s.geometry.create_text(
        [0.0, 25.4],
        "ORIENTACION: frente = SUR (Psje. Magisterial), fondo = NORTE; X+ = ESTE. "
        "SS.HH. 1 (PB) y SS.HH. 2 (PA) apilados, al norte de la escalera.",
        0.22, "bylayer",
    )

    # Fase 5: plantas desarrolladas.
    _draw_plans(s)

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

    # Fase 8: layouts A3 + viewport.
    sheets = (("ZONIFICACION", 13.0, 11.8, 280.0), ("PLANTA BAJA", 43.0, 9.5, 175.0),
              ("PLANTA ALTA", 57.0, 9.5, 175.0))
    for nm, vcx, vcy, w in sheets:
        _retry(lambda nm=nm: s.layouts.create_layout(
            nm, media="ISO_A3_(297.00_x_420.00_MM)", plot_style_table="acad.ctb"))
        _set_pdf_device(s, nm)
        _retry(lambda nm=nm, vcx=vcx, vcy=vcy, w=w: s.layouts.create_viewport(
            nm, center=[148.5, 235.0], width=w, height=350.0,
            scale=0.01, view_center=[vcx, vcy]))
    for nm, vcx, vcy, w in sheets:
        _retry(lambda nm=nm, vcx=vcx, vcy=vcy, w=w:
               _frame_viewport(s, nm, vcx, vcy, scale=0.01, vp_width=w))

    # Fase 8: membrete UCV por lamina.
    _cajetin(s, "ZONIFICACION", "Vivienda unifamiliar - Zonificacion", "A-01", "1:100 (por confirmar)")
    _cajetin(s, "PLANTA BAJA", "Vivienda unifamiliar - Planta baja", "A-02", "1:100 (por confirmar)")
    _cajetin(s, "PLANTA ALTA", "Vivienda unifamiliar - Planta alta", "A-03", "1:100 (por confirmar)")
    s.layouts.set_active_layout("Model")

    # Fase 9: guarda el archivo de trabajo y una copia en un archivo NUEVO.
    _retry(lambda: s.conn.doc.Save())
    _retry(lambda: s.conn.doc.SaveAs(NEW_PATH))
    _retry(lambda: s.conn.doc.SaveAs(TARGET_PATH))
    rep = s.analysis.analyze_drawing()
    if "summary" in rep:
        _log("entidades:", rep["summary"]["total_entities"])
        _log("por capa:", rep["summary"]["counts_by_layer"])
    _log("copia nueva:", NEW_PATH)
    _log("listo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
