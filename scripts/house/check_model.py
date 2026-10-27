"""Plotea la zona de las plantas del Model a PDF/PNG para control visual."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import fitz  # noqa: E402
import pythoncom  # noqa: E402
import win32com.client  # noqa: E402

from autocad_mcp.com import variant_point  # noqa: E402


def main(argv: list[str]) -> int:
    prefix = argv[0] if argv else "modelo"
    outdir = ROOT / "out" / "pdf"
    outdir.mkdir(parents=True, exist_ok=True)
    pdf = outdir / f"{prefix}.pdf"

    pythoncom.CoInitialize()
    app = win32com.client.GetActiveObject("AutoCAD.Application.25.1")
    doc = app.ActiveDocument
    for _ in range(20):
        try:
            doc.ActiveLayout = doc.Layouts.Item("Model")
            doc.ActiveSpace = 0
            doc.SetVariable("CTAB", "Model")
            time.sleep(0.6)
            break
        except Exception:  # noqa: BLE001
            time.sleep(0.6)

    layout = doc.ActiveLayout
    pc3 = (
        Path.home()
        / "AppData"
        / "Roaming"
        / "Autodesk"
        / "AutoCAD 2026"
        / "R25.1"
        / "enu"
        / "plotters"
        / "DWG To PDF.pc3"
    )
    layout.ConfigName = str(pc3)
    layout.RefreshPlotDeviceInfo()
    layout.CanonicalMediaName = "ISO_full_bleed_A3_(420.00_x_297.00_MM)"
    layout.PlotType = 4  # acWindow
    layout.SetWindowToPlot(
        win32com.client.VARIANT(
            pythoncom.VT_ARRAY | pythoncom.VT_R8, [-7.0, -0.5, 26.0, 25.0])
    )
    layout.UseStandardScale = False
    layout.SetCustomScale(1.0, 1.0)  # ventana ajustada? no: escala real
    layout.StandardScale = 0
    layout.CenterPlot = True
    layout.PlotRotation = 0
    layout.PaperUnits = 1
    try:
        layout.PlotViewportBorders = False
    except Exception:  # noqa: BLE001
        pass

    doc.SetVariable("BACKGROUNDPLOT", 0)
    if pdf.exists():
        pdf.unlink()
    doc.Plot.PlotToFile(str(pdf))
    last, stable = -1, 0
    for _ in range(160):
        if pdf.exists():
            size = pdf.stat().st_size
            if size > 0 and size == last:
                stable += 1
                if stable >= 4:
                    break
            else:
                stable = 0
            last = size
        time.sleep(0.5)
    if not pdf.exists():
        print("fallo el plot")
        return 1
    d = fitz.open(pdf)
    pix = d[0].get_pixmap(matrix=fitz.Matrix(2.2, 2.2))
    png = pdf.with_suffix(".png")
    pix.save(png)
    print("ok:", png)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
