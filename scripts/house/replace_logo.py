"""Reemplaza el logo vectorial aproximado por el logo real de UCV en los layouts del USB.

Dibuja el escudo UCV con lineas vectoriales basadas en la imagen proporcionada:
escudo con borde exterior, lineas curvas concéntricas y letra entrelazada central.
No modifica el ploteo; solo reemplaza el grafico del logo en el membrete.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import pythoncom
import win32com.client

from autocad_mcp.com import variant_point, variant_array  # noqa: E402
from autocad_mcp.service import AutoCADService  # noqa: E402

RED = 1
BLACK = 7
PAPER = 0
DWG_PATH = Path("D:/UCV_MAGISTERIAL_230_ENTREGA/Vivienda_UCV_Magisterial_230_ENTREGA.dwg")


def _wait(seconds: float = 0.6) -> None:
    time.sleep(seconds)


def _activate(doc: Any, name: str) -> None:  # noqa: ANN401
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


def _layer(doc: Any, name: str, color: int) -> None:  # noqa: ANN401
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


def _line(block, x0: float, y0: float, x1: float, y1: float, color: int = RED):
    e = block.AddLine(variant_point(x0, y0), variant_point(x1, y1))
    e.Layer = "A-ROTULO"
    e.Color = color
    try:
        e.Lineweight = -3
    except Exception:  # noqa: BLE001
        pass
    return e


def _poly(block, pts: list[tuple[float, float]], color: int = RED, closed: bool = False):
    coords: list[float] = []
    for x, y in pts:
        coords.extend((x, y))
    e = block.AddLightWeightPolyline(variant_array(coords))
    e.Closed = closed
    e.Layer = "A-ROTULO"
    e.Color = color
    try:
        e.Lineweight = -3
    except Exception:  # noqa: BLE001
        pass
    return e


def _arc(block, cx: float, cy: float, r: float, a0: float, a1: float, color: int = RED):
    e = block.AddArc(variant_point(cx, cy, 0.0), r, a0, a1)
    e.Layer = "A-ROTULO"
    e.Color = color
    try:
        e.Lineweight = -3
    except Exception:  # noqa: BLE001
        pass
    return e


def _text(block, value: str, x: float, y: float, height: float, color: int = BLACK):
    e = block.AddText(value, variant_point(x, y), height)
    e.Layer = "A-ROTULO"
    e.Color = color
    return e


def _remove_old_logo(block) -> None:
    """Elimina el logo vectorial aproximado anterior y el texto UCV del logo."""
    for i in range(int(block.Count) - 1, -1, -1):
        try:
            e = block.Item(i)
            mn, mx = e.GetBoundingBox()
            x0, y0, x1, y1 = (float(mn[0]), float(mn[1]), float(mx[0]), float(mx[1]))
            # Zona del logo: esquina superior izquierda del membrete (metros)
            if x1 < 0.045 and y0 > 0.008 and y1 < 0.030:
                if str(e.TextString).strip() == "UNIVERSIDAD CESAR VALLEJO":
                    e.Delete()
                    continue
                if e.ObjectName in ("AcDbLine", "AcDbPolyline", "AcDbArc"):
                    e.Delete()
        except Exception:  # noqa: BLE001
            continue


def _draw_ucv_logo(block, cx: float = 0.020, cy: float = 0.018, size: float = 0.012) -> None:
    """Dibuja el escudo UCV basado en la imagen proporcionada.

    Escudo con borde exterior, lineas curvas concéntricas y forma central
    que sugiere las letras U y V entrelazadas. Coordenadas en metros.
    """
    s = size / 0.012  # escala relativa al tamaño base

    # Borde exterior del escudo (forma aproximadamente triangular con base curva)
    _poly(
        block,
        [
            (cx - 0.5 * s, cy + 0.0 * s),  # punta inferior izquierda
            (cx - 0.45 * s, cy + 1.30 * s),  # sube por la izquierda
            (cx - 0.30 * s, cy + 1.75 * s),  # hombro izquierdo
            (cx - 0.10 * s, cy + 1.95 * s),  # cerca de la cima izquierda
            (cx + 0.00 * s, cy + 2.05 * s),  # punta superior central
            (cx + 0.10 * s, cy + 1.95 * s),  # cerca de la cima derecha
            (cx + 0.30 * s, cy + 1.75 * s),  # hombro derecho
            (cx + 0.45 * s, cy + 1.30 * s),  # baja por la derecha
            (cx + 0.50 * s, cy + 0.0 * s),  # punta inferior derecha
            (cx - 0.50 * s, cy + 0.0 * s),  # cierra base inferior
        ],
        closed=True,
    )

    # Linea interior superior (arco del escudo)
    _arc(block, cx, cy + 0.85 * s, 0.42 * s, 180.0, 0.0)
    _arc(block, cx, cy + 0.95 * s, 0.30 * s, 180.0, 0.0)
    _arc(block, cx, cy + 1.05 * s, 0.18 * s, 180.0, 0.0)

    # Lineas curvas horizontales (rayas del escudo)
    _arc(block, cx - 0.35 * s, cy + 0.40 * s, 0.70 * s, 200.0, 340.0)
    _arc(block, cx - 0.25 * s, cy + 0.62 * s, 0.50 * s, 190.0, 350.0)
    _arc(block, cx - 0.15 * s, cy + 0.82 * s, 0.30 * s, 180.0, 360.0)

    # Letra U estilizada (lado izquierdo central)
    _line(block, cx - 0.18 * s, cy + 0.45 * s, cx - 0.18 * s, cy + 0.85 * s)
    _arc(block, cx - 0.13 * s, cy + 0.85 * s, 0.05 * s, 180.0, 360.0)
    _line(block, cx - 0.08 * s, cy + 0.85 * s, cx - 0.08 * s, cy + 0.45 * s)

    # Letra V estilizada (lado derecho central)
    _line(block, cx + 0.08 * s, cy + 0.45 * s, cx + 0.13 * s, cy + 0.80 * s)
    _line(block, cx + 0.13 * s, cy + 0.80 * s, cx + 0.18 * s, cy + 0.45 * s)

    # Detalle central (punto de union U-V)
    _arc(block, cx + 0.00 * s, cy + 0.62 * s, 0.04 * s, 0.0, 360.0)


def _replace_logo_in_layout(doc, name: str) -> None:
    _activate(doc, name)
    block = doc.PaperSpace
    _remove_old_logo(block)
    _draw_ucv_logo(block)
    _text(block, "UNIVERSIDAD CESAR VALLEJO", 0.034, 0.0135, 0.0018, RED)
    print("logo reemplazado en", name)


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
    for name in ("A4_PB", "A4_PA", "A3_COLOR", "A3_FULL"):
        _replace_logo_in_layout(copy_doc, name)

    copy_doc.ActiveLayout = copy_doc.Layouts.Item("Model")
    copy_doc.SetVariable("CTAB", "Model")
    copy_doc.Save()
    print("Logo UCV reemplazado en", DWG_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
