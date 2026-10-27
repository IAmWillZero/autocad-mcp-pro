"""Plotea layouts a PDF y los convierte a PNG para revision visual."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import fitz  # noqa: E402
import pythoncom  # noqa: E402
import win32com.client  # noqa: E402


def activate(doc, name: str) -> None:
    for _ in range(20):
        try:
            doc.ActiveLayout = doc.Layouts.Item(name)
            doc.ActiveSpace = 0
            time.sleep(0.5)
            doc.SetVariable("CTAB", name)
            time.sleep(0.5)
            return
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    raise RuntimeError(name)


def main(argv: list[str]) -> int:
    prefix = argv[0] if argv else "before"
    names = argv[1:] or ["A4_PB", "A4_PA", "A3_D", "BIBLIOTECA"]
    outdir = ROOT / "out" / "pdf"
    outdir.mkdir(parents=True, exist_ok=True)

    pythoncom.CoInitialize()
    app = win32com.client.GetActiveObject("AutoCAD.Application.25.1")
    doc = app.ActiveDocument
    doc.SetVariable("BACKGROUNDPLOT", 0)

    for name in names:
        pdf = outdir / f"{prefix}_{name}.pdf"
        activate(doc, name)
        if pdf.exists():
            pdf.unlink()
        doc.Plot.PlotToFile(str(pdf))
        # AutoCAD escribe el PDF en segundo plano: esperar a que deje de crecer.
        last, stable = -1, 0
        for _ in range(120):
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
        if not pdf.exists() or pdf.stat().st_size == 0:
            print(name, "FALLO plot")
            continue
        d = fitz.open(pdf)
        page = d[0]
        zoom = 150 / 72
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        png = outdir / f"{prefix}_{name}.png"
        pix.save(png)
        print(name, pdf.stat().st_size, "->", png.relative_to(ROOT))
        d.close()

    doc.ActiveLayout = doc.Layouts.Item("Model")
    doc.SetVariable("CTAB", "Model")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
