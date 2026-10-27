"""Plotea los layouts existentes del DWG de USB a PDF sin tocar MVIEW."""

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

DWG_PATH = Path("D:/UCV_MAGISTERIAL_230_ENTREGA/Vivienda_UCV_Magisterial_230_ENTREGA.dwg")
OUT_DIR = Path("D:/UCV_MAGISTERIAL_230_ENTREGA")


def _activate(doc, name: str) -> None:
    for _ in range(20):
        try:
            doc.ActiveLayout = doc.Layouts.Item(name)
            doc.ActiveSpace = 0
            time.sleep(0.6)
            doc.SetVariable("CTAB", name)
            time.sleep(0.6)
            return
        except Exception:  # noqa: BLE001
            time.sleep(0.6)
    raise RuntimeError(f"No se pudo activar {name}")


def main() -> int:
    pythoncom.CoInitialize()
    app = win32com.client.GetActiveObject("AutoCAD.Application.25.1")
    docs = app.Documents
    doc = None
    for _ in range(15):
        try:
            for i in range(int(docs.Count)):
                d = docs.Item(i)
                if str(d.Name) == "Vivienda_UCV_Magisterial_230_ENTREGA.dwg":
                    doc = d
                    break
            if doc is not None:
                break
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.5)
    if doc is None:
        doc = docs.Open(str(DWG_PATH), False)
    doc.Activate()
    doc.SetVariable("BACKGROUNDPLOT", 0)

    layouts = {
        "A4_PB": OUT_DIR / "Vivienda_UCV_Magisterial_230_A4_PLANTA_BAJA.pdf",
        "A4_PA": OUT_DIR / "Vivienda_UCV_Magisterial_230_A4_PLANTA_ALTA.pdf",
        "A3_D": OUT_DIR / "Vivienda_UCV_Magisterial_230_A3_COLOR.pdf",
    }
    for name, out in layouts.items():
        _activate(doc, name)
        if out.exists():
            out.unlink()
        doc.Plot.PlotToFile(str(out))
        for _ in range(40):
            if out.exists() and out.stat().st_size > 0:
                break
            time.sleep(0.5)
        print(name, "->", out.stat().st_size if out.exists() else 0, "bytes")

    doc.ActiveLayout = doc.Layouts.Item("Model")
    doc.SetVariable("CTAB", "Model")
    doc.Save()
    print("PDFs listos en", OUT_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
