"""Rellena los datos del membrete en los layouts existentes.

NO toca los viewports (MVIEW) que ya creaste. Solo agrega:
- Marco rojo del tamanio exacto de la hoja
- Texto UCV, titulo, escala, fecha, lamina
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import pythoncom
import win32com.client

from autocad_mcp.com import variant_array, variant_point  # noqa: E402
from autocad_mcp.service import AutoCADService  # noqa: E402

RED = 1
BLUE = 5
BLACK = 7
PAPER = 0
DWG_PATH = Path("D:/UCV_MAGISTERIAL_230_ENTREGA/Vivienda_UCV_Magisterial_230_ENTREGA.dwg")


def _wait(seconds: float = 0.6) -> None:
    time.sleep(seconds)


def _activate(doc: AutoCADService, name: str) -> None:  # noqa: ANN401
    for _ in range(20):
        try:
            doc.ActiveLayout = doc.Layouts.Item(name)
            doc.ActiveSpace = PAPER
            _wait()
            doc.SetVariable("CTAB", name)
            _wait()
            return
        except Exception:  # noqa: BLE001
            _wait()
    raise RuntimeError(f"No se pudo activar {name}")


def _layer(doc: AutoCADService, name: str, color: int) -> None:  # noqa: ANN401
    try:
        layer = doc.Layers.Item(name)
    except Exception:  # noqa: BLE001
        layer = doc.Layers.Add(name)
    layer.Color = color
    try:
        layer.LayerOn = True
    except Exception:  # noqa: BLE001
        pass
    try:
        layer.Freeze = False
    except Exception:  # noqa: BLE001
        pass


def _line(block, x0: float, y0: float, x1: float, y1: float,
          color: int = RED):
    e = block.AddLine(variant_point(x0, y0), variant_point(x1, y1))
    e.Layer = "A-ROTULO"
    e.Color = color
    try:
        e.Lineweight = -3
    except Exception:  # noqa: BLE001
        pass
    return e


def _text(block, value: str, x: float, y: float, height: float,
          color: int = BLACK):
    e = block.AddText(value, variant_point(x, y), height)
    e.Layer = "A-ROTULO"
    e.Color = color
    return e


def _poly(block, pts: list[tuple[float, float]], color: int = RED):
    coords: list[float] = []
    for x, y in pts:
        coords.extend((x, y))
    e = block.AddLightWeightPolyline(variant_array(coords))
    e.Closed = False
    e.Layer = "A-ROTULO"
    e.Color = color
    try:
        e.Lineweight = -3
    except Exception:  # noqa: BLE001
        pass
    return e


def _draw_membrete_a4(block, sheet: str, escala: str, subtitulo: str) -> None:
    """Marco A4 vertical (210 x 297 mm) con membrete en la parte superior."""
    w, h = 0.210, 0.297
    # Borde exterior y marco interior
    for a in (
        (0.005, 0.005, w - 0.005, 0.005),
        (w - 0.005, 0.005, w - 0.005, h - 0.005),
        (w - 0.005, h - 0.005, 0.005, h - 0.005),
        (0.005, h - 0.005, 0.005, 0.005),
        (0.010, 0.010, w - 0.010, 0.010),
        (w - 0.010, 0.010, w - 0.010, h - 0.010),
        (w - 0.010, h - 0.010, 0.010, h - 0.010),
        (0.010, h - 0.010, 0.010, 0.010),
    ):
        _line(block, *a)
    # Linea separadora del cajete (zona superior)
    _line(block, 0.010, h - 0.036, w - 0.010, h - 0.036)
    _line(block, w - 0.105, 0.010, w - 0.105, h - 0.036)

    # Logo lineal UCV (escudo simple)
    s = 0.00030
    tx = 0.015 - s * 229.2223460759
    ty = h - 0.013 - s * (-93.3174331498)
    _poly(block, [
        (tx - 0.5 * s, ty + 0.0 * s),
        (tx - 0.45 * s, ty + 1.30 * s),
        (tx - 0.30 * s, ty + 1.75 * s),
        (tx - 0.10 * s, ty + 1.95 * s),
        (tx + 0.00 * s, ty + 2.05 * s),
        (tx + 0.10 * s, ty + 1.95 * s),
        (tx + 0.30 * s, ty + 1.75 * s),
        (tx + 0.45 * s, ty + 1.30 * s),
        (tx + 0.50 * s, ty + 0.0 * s),
        (tx - 0.50 * s, ty + 0.0 * s),
    ])
    _arc(block, tx, ty + 0.85 * s, 0.42 * s, 180.0, 0.0)
    _arc(block, tx, ty + 0.95 * s, 0.30 * s, 180.0, 0.0)
    _arc(block, tx, ty + 1.05 * s, 0.18 * s, 180.0, 0.0)
    _line(block, tx - 0.18 * s, ty + 0.45 * s, tx - 0.18 * s, ty + 0.85 * s)
    _arc(block, tx - 0.13 * s, ty + 0.85 * s, 0.05 * s, 180.0, 360.0)
    _line(block, tx - 0.08 * s, ty + 0.85 * s, tx - 0.08 * s, ty + 0.45 * s)
    _line(block, tx + 0.08 * s, ty + 0.45 * s, tx + 0.13 * s, ty + 0.80 * s)
    _line(block, tx + 0.13 * s, ty + 0.80 * s, tx + 0.18 * s, ty + 0.45 * s)
    _arc(block, tx + 0.00 * s, ty + 0.62 * s, 0.04 * s, 0.0, 360.0)

    _text(block, "UNIVERSIDAD CESAR VALLEJO", 0.034, h - 0.0135, 0.0018, RED)
    _text(block, "VIVIENDA UCV MAGISTERIAL 230", 0.057, h - 0.028, 0.0030, BLUE)
    _text(block, subtitulo, 0.057, h - 0.022, 0.0023)
    _text(block, "INGENIERIA CIVIL - EXPRESION GRAFICA - GRUPO A1",
          0.057, h - 0.016, 0.0018)
    _text(block, "UNIDADES: METROS | DWGUNITS: METROS", 0.057, h - 0.012,
          0.0017)
    ix = w - 0.100
    _text(block, f"LAMINA: {sheet}", ix + 0.005, h - 0.028, 0.0025, BLUE)
    _text(block, f"ESCALA: {escala}", ix + 0.005, h - 0.022, 0.0020)
    _text(block, "FECHA: 27/10/2026", ix + 0.005, h - 0.017, 0.0018)
    _text(block, "A-010 / A-020", ix + 0.005, h - 0.012, 0.0018)


def _arc(block, cx: float, cy: float, r: float, a0: float, a1: float,
         color: int = RED):
    e = block.AddArc(variant_point(cx, cy, 0.0), r, a0, a1)
    e.Layer = "A-ROTULO"
    e.Color = color
    try:
        e.Lineweight = -3
    except Exception:  # noqa: BLE001
        pass
    return e


def _draw_membrete_a3(block, sheet: str, escala: str, subtitulo: str) -> None:
    """Marco A3 horizontal (420 x 297 mm) con membrete en la parte superior."""
    w, h = 0.420, 0.297
    for a in (
        (0.005, 0.005, w - 0.005, 0.005),
        (w - 0.005, 0.005, w - 0.005, h - 0.005),
        (w - 0.005, h - 0.005, 0.005, h - 0.005),
        (0.005, h - 0.005, 0.005, 0.005),
        (0.010, 0.010, w - 0.010, 0.010),
        (w - 0.010, 0.010, w - 0.010, h - 0.010),
        (w - 0.010, h - 0.010, 0.010, h - 0.010),
        (0.010, h - 0.010, 0.010, 0.010),
    ):
        _line(block, *a)
    _line(block, 0.010, h - 0.036, w - 0.010, h - 0.036)
    _line(block, w - 0.105, 0.010, w - 0.105, h - 0.036)

    s = 0.00030
    tx = 0.015 - s * 229.2223460759
    ty = h - 0.013 - s * (-93.3174331498)
    _poly(block, [
        (tx - 0.5 * s, ty + 0.0 * s),
        (tx - 0.45 * s, ty + 1.30 * s),
        (tx - 0.30 * s, ty + 1.75 * s),
        (tx - 0.10 * s, ty + 1.95 * s),
        (tx + 0.00 * s, ty + 2.05 * s),
        (tx + 0.10 * s, ty + 1.95 * s),
        (tx + 0.30 * s, ty + 1.75 * s),
        (tx + 0.45 * s, ty + 1.30 * s),
        (tx + 0.50 * s, ty + 0.0 * s),
        (tx - 0.50 * s, ty + 0.0 * s),
    ])
    _arc(block, tx, ty + 0.85 * s, 0.42 * s, 180.0, 0.0)
    _arc(block, tx, ty + 0.95 * s, 0.30 * s, 180.0, 0.0)
    _arc(block, tx, ty + 1.05 * s, 0.18 * s, 180.0, 0.0)
    _line(block, tx - 0.18 * s, ty + 0.45 * s, tx - 0.18 * s, ty + 0.85 * s)
    _arc(block, tx - 0.13 * s, ty + 0.85 * s, 0.05 * s, 180.0, 360.0)
    _line(block, tx - 0.08 * s, ty + 0.85 * s, tx - 0.08 * s, ty + 0.45 * s)
    _line(block, tx + 0.08 * s, ty + 0.45 * s, tx + 0.13 * s, ty + 0.80 * s)
    _line(block, tx + 0.13 * s, ty + 0.80 * s, tx + 0.18 * s, ty + 0.45 * s)
    _arc(block, tx + 0.00 * s, ty + 0.62 * s, 0.04 * s, 0.0, 360.0)

    _text(block, "UNIVERSIDAD CESAR VALLEJO", 0.034, h - 0.0135, 0.0018, RED)
    _text(block, "VIVIENDA UCV MAGISTERIAL 230", 0.057, h - 0.028, 0.0030, BLUE)
    _text(block, subtitulo, 0.057, h - 0.022, 0.0023)
    _text(block, "INGENIERIA CIVIL - EXPRESION GRAFICA - GRUPO A1",
          0.057, h - 0.016, 0.0018)
    _text(block, "UNIDADES: METROS | DWGUNITS: METROS", 0.057, h - 0.012,
          0.0017)
    ix = w - 0.100
    _text(block, f"LAMINA: {sheet}", ix + 0.005, h - 0.028, 0.0025, BLUE)
    _text(block, f"ESCALA: {escala}", ix + 0.005, h - 0.022, 0.0020)
    _text(block, "FECHA: 27/10/2026", ix + 0.005, h - 0.017, 0.0018)
    _text(block, "A-010 / A-020", ix + 0.005, h - 0.012, 0.0018)


def main() -> int:
    if not DWG_PATH.exists():
        raise FileNotFoundError(f"No existe: {DWG_PATH}")

    pythoncom.CoInitialize()
    app = win32com.client.GetActiveObject("AutoCAD.Application.25.1")
    docs = app.Documents
    copy_doc = None
    for _ in range(15):
        try:
            for i in range(int(docs.Count)):
                d = docs.Item(i)
                if str(d.Name) == "Vivienda_UCV_Magisterial_230_ENTREGA.dwg":
                    copy_doc = d
                    break
            if copy_doc is not None:
                break
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.5)
    if copy_doc is None:
        copy_doc = docs.Open(str(DWG_PATH), False)
    copy_doc.Activate()

    _layer(copy_doc, "A-ROTULO", RED)

    layouts = {
        "A4_PB": ("A-01", "PB 1:100", "PLANTA BAJA | A4 VERTICAL"),
        "A4_PA": ("A-02", "PA 1:100", "PLANTA ALTA | A4 VERTICAL"),
        "A3_D": ("A-03", "PB + PA 1:125", "PLANTAS + ZONIFICACION | A3"),
    }
    for name, (sheet, escala, subtitulo) in layouts.items():
        _activate(copy_doc, name)
        block = copy_doc.PaperSpace
        if name == "A3_D":
            _draw_membrete_a3(block, sheet, escala, subtitulo)
        else:
            _draw_membrete_a4(block, sheet, escala, subtitulo)
        print("membrete rellenado en", name)

    copy_doc.ActiveLayout = copy_doc.Layouts.Item("Model")
    copy_doc.SetVariable("CTAB", "Model")
    copy_doc.Save()
    print("Membrete rellenado en", DWG_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
