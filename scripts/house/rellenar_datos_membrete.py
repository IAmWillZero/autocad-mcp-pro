"""Rellena los valores del membrete en los layouts existentes.

NO toca los MVIEW (viewports). Solo agrega los valores de texto al lado
de cada etiqueta MTEXT: ALUMNO, TEMA, PROFESOR, FECHA, ESCALA, CICLO, LAMINA.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import pythoncom
import win32com.client

from autocad_mcp.com import variant_point  # noqa: E402
from autocad_mcp.service import AutoCADService  # noqa: E402

RED = 1
BLACK = 7
PAPER = 0
DWG_PATH = Path("D:/UCV_MAGISTERIAL_230_ENTREGA/Vivienda_UCV_Magisterial_230_ENTREGA.dwg")

# Datos por lámina
LAMINA_DATA = {
    "A4_PB": {
        "sheet": "A-01",
        "escala": "1:100",
        "subtitulo": "PLANTA BAJA | A4 VERTICAL",
    },
    "A4_PA": {
        "sheet": "A-02",
        "escala": "1:100",
        "subtitulo": "PLANTA ALTA | A4 VERTICAL",
    },
    "A3_D": {
        "sheet": "A-03",
        "escala": "1:125",
        "subtitulo": "PLANTAS + ZONIFICACION | A3",
    },
}

COMMON = {
    "alumno": "WILLIAMS RONALDO SIGUEÑAS ORTIZ",
    "tema": "VIVIENDA UCV MAGISTERIAL 230",
    "profesor": "M.S. MARIBEL MARCELA NORIEGA FALCON",
    "fecha": "27/10/2026",
    "ciclo": "II",
    "pland": "PLANTA ARQUITECTONICA",
}


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


def _text(block, value: str, x: float, y: float, height: float = 0.0025,
          color: int = BLACK):
    e = block.AddText(value, variant_point(x, y), height)
    e.Layer = "A-ROTULO"
    e.Color = color
    return e


def _find_label(block, label_text: str):
    """Busca un MTEXT cuya cadena comience con label_text y devuelve su posición."""
    for i in range(int(block.Count)):
        try:
            e = block.Item(i)
            if e.ObjectName != "AcDbMText":
                continue
            t = str(e.TextString or "")
            t_clean = t.replace("\\H2x;", "").replace("\\H3x;", "").replace("{", "").replace("}", "").strip()
            if t_clean.startswith(label_text):
                try:
                    mn, mx = e.GetBoundingBox()
                    return (float(mn[0]), float(mn[1]), float(mx[0]), float(mx[1]))
                except Exception:
                    return None
        except Exception:
            continue
    return None


def _fill_label_values(doc, block, data: dict) -> None:
    """Agrega los valores al lado de cada etiqueta del membrete."""
    ciclo = COMMON["ciclo"]
    pland = COMMON["pland"]
    fecha = COMMON["fecha"]
    sheet = data["sheet"]
    escala = data["escala"]

    valores = {
        "ALUMNO": COMMON["alumno"],
        "TEMA": data["subtitulo"],
        "PROFESOR": COMMON["profesor"],
        "FECHA": fecha,
        "ESCALA": escala,
        "CICLO": ciclo,
        "PLAND": pland,
        "LAMINA": sheet,
    }

    for label, valor in valores.items():
        bb = _find_label(block, label)
        if bb is None:
            print(f"  aviso: no se encontro etiqueta '{label}'")
            continue
        x0, y0, x1, y1 = bb
        # Escribir el valor a la derecha de la etiqueta, con un pequeño desplazamiento
        vx = x1 + 0.015
        vy = (y0 + y1) / 2 - 0.001
        _text(block, valor, vx, vy, height=0.0025)
        print(f"  relleno '{label}' = {valor!r} en ({vx:.3f}, {vy:.3f})")


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

    for name in ("A4_PB", "A4_PA", "A3_D"):
        if name not in LAMINA_DATA:
            continue
        _activate(copy_doc, name)
        block = copy_doc.PaperSpace
        print("\nLAYOUT", name)
        _fill_label_values(copy_doc, block, LAMINA_DATA[name])

    copy_doc.ActiveLayout = copy_doc.Layouts.Item("Model")
    copy_doc.SetVariable("CTAB", "Model")
    copy_doc.Save()
    print("\nDatos del membrete rellenados en", DWG_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
