"""Redibuja completa la vivienda (2 plantas) en el documento ACTIVO."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import house_data as D
from autocad_mcp.service import AutoCADService
from house_blocks import define_blocks
from house_draw import draw_bottom_dims, draw_left_dims, draw_stair_u
from house_main import _draw_floor, _retry

OX = D.OFF2
OUT_DIR = str(ROOT / "out")
TARGET = "CASA.dwg"
TARGET_PATH = os.path.join(OUT_DIR, TARGET)


def _ensure_target(s: AutoCADService) -> str:
    """Usa un DWG dedicado y limpio (CASA.dwg); no toca otros documentos abiertos."""
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


def _frame_viewport(
    s: AutoCADService, name: str, cx: float, cy: float, scale: float = 10.0, vp_width: float = 170.0
) -> None:
    """Deja el viewport propio visible (apaga/borra los de plantilla) y lo centra en (cx, cy)."""
    import time as _t

    from autocad_mcp.com import as_dynamic

    doc = s.conn.doc

    def _collect() -> list:
        ps = doc.PaperSpace
        out = []
        for i in range(ps.Count):
            e = as_dynamic(ps.Item(i))
            try:
                if str(e.ObjectName) == "AcDbViewport":
                    out.append(e)
            except Exception:  # noqa: BLE001
                pass
        return out

    try:
        doc.SetVariable("CTAB", name)
        doc.ActiveSpace = 1
        _t.sleep(0.8)
        viewports = _collect()
        ours = next((v for v in viewports if abs(float(v.Width) - vp_width) < 2.0), None)
        if ours is None:
            s.layouts.create_viewport(
                name, center=[148.5, 210.0], width=vp_width, height=372.0,
                scale=scale, view_center=[cx, cy],
            )
            _t.sleep(0.6)
            viewports = _collect()
            ours = next((v for v in viewports if abs(float(v.Width) - vp_width) < 2.0), None)
        if ours is None:
            return
        for v in viewports:
            if v is ours:
                continue
            for _ in range(8):
                try:
                    v.Delete()
                    break
                except Exception:  # noqa: BLE001
                    _t.sleep(0.3)
            else:
                try:
                    v.ViewportOn = False
                except Exception:  # noqa: BLE001
                    pass
        ours.DisplayLocked = False
        try:
            ours.ViewportOn = True
        except Exception:  # noqa: BLE001
            pass
        try:
            doc.ActivePViewport = ours
        except Exception:  # noqa: BLE001
            pass
        doc.MSpace = True
        _t.sleep(0.2)
        doc.SendCommand(f"_.ZOOM\n_C\n{cx},{cy}\n{372.0 / scale}\n")
        _t.sleep(0.3)
        doc.MSpace = False
        try:
            ours.ViewportOn = True
        except Exception:  # noqa: BLE001
            pass
        ours.DisplayLocked = True
        doc.Regen(0)
    except Exception:  # noqa: BLE001
        pass


def _repair_fixtures(s: AutoCADService) -> int:
    """Reinserta cualquier mobiliario que se haya perdido (op COM rechazada)."""
    from autocad_mcp.com import as_dynamic

    doc = s.conn.doc
    ms = doc.ModelSpace
    existing = set()
    for i in range(ms.Count):
        e = as_dynamic(ms.Item(i))
        try:
            if str(e.ObjectName) == "AcDbBlockReference":
                ip = e.InsertionPoint
                existing.add((str(e.Name), round(float(ip[0]), 3), round(float(ip[1]), 3)))
        except Exception:  # noqa: BLE001
            pass
    expected = [(b, p[0], p[1], r) for (b, p, r) in D.FIX1]
    expected += [(b, p[0] + OX, p[1], r) for (b, p, r) in D.FIX2]
    fixed = 0
    for block, x, y, rot in expected:
        if (block, round(x, 3), round(y, 3)) not in existing:
            log("REPARANDO mobiliario:", block, x, y)
            s.blocks.insert_block(block, [x, y], rotation=rot, layer="A-MOBILIARIO")
            fixed += 1
    return fixed


def _redraw_dimensions(s: AutoCADService) -> None:
    """Borra todas las cotas y las redibuja (garantiza el juego completo de 3 niveles)."""
    from autocad_mcp.com import as_dynamic

    doc = s.conn.doc
    ms = doc.ModelSpace
    doomed = []
    for i in range(ms.Count):
        e = as_dynamic(ms.Item(i))
        try:
            if str(e.ObjectName) == "AcDbRotatedDimension":
                doomed.append(e)
        except Exception:  # noqa: BLE001
            pass
    for e in doomed:
        try:
            e.Delete()
        except Exception:  # noqa: BLE001
            pass

    s.layer_tools.set_current_layer("A-COTAS")
    # planta baja (ox=0)
    for off, breaks in [(1.4, [0, 3, 5.5, 8]), (2.8, [0, 3, 8]), (4.2, [0, 8])]:
        draw_bottom_dims(s, breaks, 4.0, off, 0.0)
    for off, breaks in [
        (1.4, [4, 7, 10.5, 13.5, 16, 17.5, 21]),
        (2.8, [4, 10.5, 17.5, 21]),
        (4.2, [4, 21]),
    ]:
        draw_left_dims(s, breaks, 0.0, off, 0.0)
    # planta alta (desplazada +16 en X)
    for off, breaks in [(3.0, [0, 3, 4, 6, 8]), (4.4, [0, 3, 8]), (5.8, [0, 8])]:
        draw_bottom_dims(s, breaks, 4.0, off, OX)
    for off, breaks in [(1.4, [4, 7, 9, 12, 14.5, 17.5]), (2.8, [4, 11, 17.5]), (4.2, [4, 17.5])]:
        draw_left_dims(s, breaks, OX, off, 0.0)

    # Precision: maximo 3 decimales, sin ceros finales (DIMOVERRIDE fiable).
    s.dimensions.set_dimension_precision(3, True)


def _poche_walls(s: AutoCADService) -> int:
    """Rellena (SOLID) los contornos cerrados de los muros: muros cortados solidos."""
    from autocad_mcp.com import as_dynamic

    doc = s.conn.doc
    ms = doc.ModelSpace
    targets = []
    for i in range(ms.Count):
        e = as_dynamic(ms.Item(i))
        try:
            if str(e.ObjectName) != "AcDbPolyline":
                continue
            lay = str(e.Layer)
            if lay not in ("A-MUROS-CARGA", "A-MUROS-TABIQ"):
                continue
            if not bool(e.Closed):
                continue
            targets.append((str(e.Handle), lay))
        except Exception:  # noqa: BLE001
            pass
    n = 0
    for handle, lay in targets:
        r = s.geometry.create_hatch([handle], "SOLID", layer=lay, color="bylayer")
        if r.get("success"):
            n += 1
    return n


def _draw_area_table(s: AutoCADService, rows: list[tuple[str, str, float]], x0: float = 9.6,
                     y_top: float = 20.5, w1: float = 2.9, w2: float = 1.7,
                     rh: float = 0.55, th: float = 0.28) -> int:
    """Dibuja un cuadro de superficies (ambiente | area) en la zona libre."""
    w = w1 + w2
    s.layer_tools.set_current_layer("A-TEXTOS")

    def hline(y: float) -> None:
        s.geometry.create_line([x0, y], [x0 + w, y], "bylayer")

    def vline(x: float, y_a: float, y_b: float) -> None:
        s.geometry.create_line([x, y_a], [x, y_b], "bylayer")

    n = len(rows)
    y_bot = y_top - (n + 1) * rh
    for i in range(n + 2):
        hline(y_top - i * rh)
    vline(x0, y_bot, y_top)
    vline(x0 + w1, y_bot, y_top)
    vline(x0 + w, y_bot, y_top)

    # cabecera
    s.geometry.create_text([x0 + 0.08, y_top - rh + 0.12], "CUADRO DE AREAS", th, "bylayer")
    for i, (amb, kind, area) in enumerate(rows):
        y = y_top - (i + 2) * rh + 0.12
        if kind == "h":
            s.geometry.create_text([x0 + 0.08, y], amb, th * 0.95, "bylayer")
        else:
            s.geometry.create_text([x0 + 0.08, y], amb, th, "bylayer")
        right = f"{area:.2f} m2" if area else ""
        s.geometry.create_text([x0 + w1 + 0.08, y], right, th, "bylayer")
    return n


def _draw_north(s: AutoCADService, cx: float, cy: float, r: float = 0.55) -> None:
    """Simbolo de norte: circulo, aguja y rotulo N."""
    s.layer_tools.set_current_layer("A-TEXTOS")
    s.geometry.create_circle([cx, cy], r, "bylayer")
    s.geometry.create_line([cx, cy - r], [cx, cy + r], "bylayer")
    head = 0.18
    s.geometry.create_line([cx, cy + r], [cx - head, cy + r - head], "bylayer")
    s.geometry.create_line([cx, cy + r], [cx + head, cy + r - head], "bylayer")
    s.geometry.create_text([cx - 0.09, cy + r + 0.12], "N", 0.32, "bylayer")


def _pin(s: AutoCADService) -> None:
    """Reafirma que se dibuja en TARGET (por si AutoCAD cambio de documento)."""
    try:
        cur = s.conn.doc.Name if s.conn.doc else ""
    except Exception:  # noqa: BLE001
        cur = ""
    if cur != TARGET:
        s.documents.set_active_document(TARGET)


def _speed_up() -> None:
    """Reemplaza la pausa fija de 1 s por COM por reintentos ante 'busy' (solo test)."""
    import time

    def fast(op, delay: float = 0.0):
        last = None
        for _ in range(60):
            try:
                result = op()
                time.sleep(0.15)  # deja que AutoCAD se asiente (evita RPC busy)
                return result
            except Exception as exc:  # noqa: BLE001
                last = exc
                time.sleep(0.5)
        print("OP-FAILED:", repr(last), flush=True)
        return None

    for mod in list(sys.modules.values()):
        if hasattr(mod, "safe_operation"):
            mod.safe_operation = fast


def log(*a):
    print(*a, flush=True)


def main() -> int:
    _speed_up()
    s = AutoCADService()
    if not s.connect():
        log("ERROR: no conecta")
        return 1
    log("Documento:", _ensure_target(s))
    log("Fijado:", s.conn.doc.Name)
    for _name in ("PLANTA BAJA", "PLANTA ALTA"):
        try:
            s.conn.doc.Layouts.Item(_name).Delete()
        except Exception:  # noqa: BLE001 - no existia
            pass
    s.deleter.delete_all_entities(confirm=True)
    std = s.standards.apply_standard()
    log(std["message"])
    if len(std.get("created_layers", [])) + len(std.get("existing_layers", [])) < 6:
        log("ABORT: el estandar no aplico capas; no se dibuja nada")
        return 2
    define_blocks(s)
    log("bloques ok")

    n1 = _draw_floor(
        s, D.ROOMS1, D.X1, D.Y1, D.OPEN1, D.AXES_V1, D.AXES_H1, D.FIX1, D.TITLE1,
        bottom_levels=[(1.4, [0, 3, 5.5, 8]), (2.8, [0, 3, 8]), (4.2, [0, 8])],
        left_levels=[(1.4, [4, 7, 10.5, 13.5, 16, 17.5, 21]), (2.8, [4, 10.5, 17.5, 21]),
                      (4.2, [4, 21])],
    )
    log("PISO1 muros:", n1)
    s.layer_tools.set_current_layer("A-SITIO")
    s.geometry.create_polyline(
        [[0.0, 0.0], [8.0, 0.0], [8.0, 23.0], [0.0, 23.0]], closed=True, color="bylayer"
    )
    s.layer_tools.set_current_layer("A-TEXTOS")
    s.geometry.create_text([4.0, 2.0], "JARDIN FRONTAL", 0.22, "bylayer")
    s.geometry.create_text([4.0, 22.0], "JARDIN POSTERIOR", 0.22, "bylayer")
    log("piso1 ok")

    _pin(s)
    n2 = _draw_floor(
        s, D.ROOMS2, D.X2, D.Y2, D.OPEN2, D.AXES_V2, D.AXES_H2, D.FIX2, D.TITLE2,
        bottom_levels=[(3.0, [0, 3, 4, 6, 8]), (4.4, [0, 3, 8]), (5.8, [0, 8])],
        left_levels=[(1.4, [4, 7, 9, 12, 14.5, 17.5]), (2.8, [4, 11, 17.5]),
                     (4.2, [4, 17.5])],
        ox=OX,
    )
    log("PISO2 muros:", n2)
    draw_stair_u(s, D.STAIR2, OX, 0.0)
    s.layer_tools.set_current_layer("A-MUROS-TABIQ")
    s.geometry.create_wall(
        [[p[0] + OX, p[1]] for p in D.BALCON_FRONTAL], thickness=0.10, color="bylayer"
    )
    s.layer_tools.set_current_layer("A-TEXTOS")
    s.geometry.create_text([4.0 + OX, 2.6], "BALCON FRONTAL", 0.2, "bylayer")
    s.geometry.create_text(
        [OX, 18.6], "ESCALERA: 16 ALZADAS x 0.175 m - ANCHO UTIL 0.90 m", 0.22, "bylayer"
    )
    log("piso2 ok")

    _retry(lambda: _poche_walls(s), tries=4, delay=1.5)
    log("poche ok")

    rows = [("PLANTA BAJA", "h", 0.0)]
    a1 = 0.0
    for (label, i0, i1, j0, j1) in D.ROOMS1:
        a = abs(D.X1[i1] - D.X1[i0]) * abs(D.Y1[j1] - D.Y1[j0])
        a1 += a
        rows.append((label, "r", a))
    rows.append(("SUBTOTAL PLANTA BAJA", "h", a1))
    rows.append(("PLANTA ALTA", "h", 0.0))
    a2 = 0.0
    for (label, i0, i1, j0, j1) in D.ROOMS2:
        a = abs(D.X2[i1] - D.X2[i0]) * abs(D.Y2[j1] - D.Y2[j0])
        a2 += a
        rows.append((label, "r", a))
    rows.append(("SUBTOTAL PLANTA ALTA", "h", a2))
    rows.append(("TOTAL", "h", a1 + a2))
    _retry(
        lambda: _draw_area_table(s, rows, x0=26.5, y_top=20.5, w1=3.5, w2=1.7, rh=0.52, th=0.26),
        tries=4,
        delay=1.5,
    )
    _retry(lambda: _draw_north(s, 27.2, 3.5), tries=4, delay=1.5)
    log("cuadro + norte ok")

    _pin(s)
    nfix = _repair_fixtures(s)
    log("mobiliario reparado:", nfix)
    _retry(lambda: _redraw_dimensions(s), tries=8, delay=1.5)
    log("cotas redibujadas")
    for _ in range(3):
        for _try in range(20):
            try:
                s.conn.doc.PurgeAll()
                break
            except Exception:  # noqa: BLE001
                import time

                time.sleep(0.4)
    s.ops.zoom_extents()
    log("zoom ok")

    _pin(s)
    for name, vcx, vcy in (("PLANTA BAJA", 2.3, 10.9), ("PLANTA ALTA", 21.0, 10.9)):
        lay = _retry(
            lambda name=name: s.layouts.create_layout(
                name, media="ISO_A3_(297.00_x_420.00_MM)", plot_style_table="acad.ctb"
            ),
            tries=6,
            delay=1.5,
        )
        log("layout:", lay.get("message", lay))
        vp = _retry(
            lambda name=name, vcx=vcx, vcy=vcy: s.layouts.create_viewport(
                name, center=[148.5, 210.0], width=170.0, height=372.0,
                scale=10.0, view_center=[vcx, vcy],
            ),
            tries=6,
            delay=1.5,
        )
        log("viewport:", vp.get("message", vp))
        _frame_viewport(s, name, vcx, vcy, scale=10.0)
    s.layouts.set_active_layout("Model")

    rep = s.analysis.analyze_drawing()
    log("=== ANALISIS ===", rep["summary"]["total_entities"])
    log("por tipo:", rep["summary"]["counts_by_type"])
    log("por capa:", rep["summary"]["counts_by_layer"])
    log("cotas:", len(rep["dimensions"]))
    log("listo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
