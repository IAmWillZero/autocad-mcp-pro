"""Genera la version corregida del diseno (solo modelo, sin tramitar layouts).

Uso:
    python scripts/house/design_v2.py

No crea ni modifica membretes. Dibuja plantas, zonificacion, cuadros y
recorridos sobre un DWG nuevo en ``out``.
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "house"))

from autocad_mcp.com import as_dynamic  # noqa: E402
from autocad_mcp.service import AutoCADService  # noqa: E402

import ucv_areas as AR  # noqa: E402
import ucv_data as U  # noqa: E402
import vivienda_ucv as V  # noqa: E402

OUT = ROOT / "out" / "Vivienda_UCV_Magisterial_230_DISENO_V2.dwg"


def _retry(fn, tries: int = 10, delay: float = 1.0):
    import time

    last = None
    for _ in range(tries):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(delay)
    raise last  # type: ignore[misc]


def _clean_document(s: AutoCADService):
    app = s.conn.app
    docs = app.Documents
    target = str(OUT).lower()
    for i in range(int(docs.Count)):
        d = docs.Item(i)
        try:
            if str(d.FullName).lower() == target:
                s.conn.doc = d
                d.Activate()
                return d
        except Exception:  # noqa: BLE001
            pass
    os.makedirs(OUT.parent, exist_ok=True)
    if OUT.exists():
        doc = docs.Open(str(OUT))
    else:
        doc = docs.Add()
        doc.SaveAs(str(OUT))
    s.conn.doc = doc
    doc.Activate()
    return doc


def _setup_layers(s: AutoCADService) -> None:
    s.standards.apply_standard()
    for lay, color in (
        ("Z-SOCIAL", "magenta"),
        ("Z-SERVICIOS", "blue"),
        ("Z-PRIVADA", "green"),
        ("Z-CIRCULACION", "yellow"),
        ("Z-AREA-LIBRE", "green"),
        ("A-TERRENO", "white"),
        ("A-ROTULO", "white"),
        ("A-CIRCULACION", "cyan"),
    ):
        s.layer_tools.create_or_get_layer(lay, color, "Zonificacion / presentacion")
    for lay, lw in V.LINEWEIGHTS.items():
        try:
            _retry(lambda lay=lay, lw=lw: setattr(s.conn.doc.Layers.Item(lay), "Lineweight", lw))
        except Exception:  # noqa: BLE001
            pass


def _head(s: AutoCADService, tip: tuple[float, float], prev: tuple[float, float], size: float = 0.16) -> None:
    dx, dy = tip[0] - prev[0], tip[1] - prev[1]
    ln = math.hypot(dx, dy)
    if ln < 1e-9:
        return
    ux, uy = dx / ln, dy / ln
    px, py = -uy, ux
    a = (tip[0] - ux * size + px * size * 0.6, tip[1] - uy * size + py * size * 0.6)
    b = (tip[0] - ux * size - px * size * 0.6, tip[1] - uy * size - py * size * 0.6)
    s.geometry.create_polyline([tip, a, b], closed=True, color="bylayer")


def _route(s: AutoCADService, pts: list[tuple[float, float]], label: str = "") -> None:
    s.layer_tools.set_current_layer("A-CIRCULACION")
    for p, q in zip(pts, pts[1:]):
        s.geometry.create_line([round(p[0], 3), round(p[1], 3)],
                               [round(q[0], 3), round(q[1], 3)], "bylayer")
    if len(pts) >= 2:
        _head(s, pts[-1], pts[-2])
    if label:
        s.geometry.create_text([round(pts[0][0] + 0.08, 3), round(pts[0][1] + 0.12, 3)],
                               label, 0.13, "bylayer")


def _draw_plans(s: AutoCADService) -> None:
    """Plantas sin mobiliario ni tablas; solo arquitectura y recorridos."""
    bottom = [(1.4, [1.0, 4.0, 5.2, 5.5, 5.8, 7.0]), (2.8, [1.0, 4.0, 7.0])]
    plans = (
        (U.ROOMS1, U.X1, U.Y1, U.OPEN1, U.AXES_V1, U.AXES_H1, U.TITLE1, U.PB_OX,
         [(1.4, [4.0, 8.33, 11.33, 14.5, 16.0, 18.0]),
          (2.8, [4.0, 8.33, 11.33, 14.5, 18.0])]),
        (U.ROOMS2, U.X2, U.Y2, U.OPEN2, U.AXES_V2, U.AXES_H2, U.TITLE2, U.PA_OX,
         [(1.4, [4.0, 8.0, 8.33, 11.33, 13.66, 16.0]),
          (2.8, [4.0, 8.33, 11.33, 16.0])]),
    )
    for rooms, X, Y, opens, av, ah, title, ox, left in plans:
        V._draw_floor(s, rooms, X, Y, opens, av, ah, [], title,
                      bottom_levels=bottom, left_levels=left, ox=ox)
        V._terreno(s, ox)
        V.draw_stair_u(s, U.STAIR, ox, 0.0)
        V._level(s, X[0] + ox - 1.2, Y[0] + 0.3,
                 U.NPT_PB if ox == U.PB_OX else U.NPT_PA)
    for pts in (U.JARDIN_FRONTAL, U.TERRAZA_POST, U.JARDIN_POST):
        if pts:
            V._outline(s, pts, U.PB_OX)
    V._section_mark(s, 4.0 + U.PB_OX, 0.5, 17.2, "A")
    V._section_mark(s, 4.0 + U.PA_OX, 0.5, 15.2, "A")
    V._scale_bar(s, U.PB_OX, 0.4)


def _circulation(s: AutoCADService) -> None:
    # Primer piso: ingreso por hall (no por oficina) -> escalera -> social.
    ox = U.PB_OX
    _route(s, [(ox + 4.65, 4.35), (ox + 4.75, 6.10), (ox + 4.70, 7.95),
               (ox + 4.72, 9.30), (ox + 3.45, 10.25), (ox + 3.45, 13.30),
               (ox + 4.65, 15.25)], "INGRESO")
    # Servicio: cocina -> lavanderia -> SS.HH. 1.
    _route(s, [(ox + 5.15, 17.20), (ox + 5.15, 13.65), (ox + 6.35, 12.25)],
           "SERVICIO")
    # Acceso independiente de la oficina desde el hall.
    _route(s, [(ox + 4.95, 5.65), (ox + 5.65, 5.65)], "OFICINA")

    # Segundo piso: escalera -> hall -> banos y corredor -> dormitorio 3.
    ox = U.PA_OX
    _route(s, [(ox + 5.05, 11.05), (ox + 5.05, 12.45), (ox + 6.15, 13.55)],
           "HALL")
    _route(s, [(ox + 6.35, 12.80), (ox + 6.35, 9.15), (ox + 6.35, 7.90)],
           "DORM. 3")
    # Escalera -> sala de estar -> dormitorios 2 y principal.
    _route(s, [(ox + 4.75, 10.55), (ox + 3.45, 10.20), (ox + 3.45, 9.40),
               (ox + 2.10, 7.80)], "DORM. 2")
    _route(s, [(ox + 3.45, 11.75), (ox + 2.10, 12.55)], "DORM. PRINCIPAL")
    s.layer_tools.set_current_layer("A-TEXTOS")
    s.geometry.create_text([ox + 1.25, 15.55], "SIN BALCON - VENTANAS AMPLIAS", 0.16, "bylayer")


def main() -> int:
    s = AutoCADService()
    if not s.connect():
        print("ABORT: sin conexion a AutoCAD", flush=True)
        return 1
    doc = _clean_document(s)
    print("Documento:", doc.Name, flush=True)
    s.deleter.delete_all_entities(confirm=True)
    _setup_layers(s)

    V._zoning(s)
    V._legend(s, 19.5, 22.6)
    V._north(s, 26.8, 20.6)
    _draw_plans(s)
    _circulation(s)
    s.ops.zoom_extents()
    _retry(lambda: doc.Save())
    d = AR.schedule()
    print(f"PB {d['total_pb']:.2f} m2 / PA {d['total_pa']:.2f} m2 / "
          f"total {d['total']:.2f} m2 / libre {d['area_libre']:.2f} m2", flush=True)
    print("Guardado:", OUT, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
