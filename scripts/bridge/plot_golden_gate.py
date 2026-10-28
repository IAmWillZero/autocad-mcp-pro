"""Abre el DWG del Golden Gate y lo traza a PDF (util para re-trazar sin reconstruir)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pythoncom
from build_golden_gate import OUT_DIR, _plot_pdf
from win32com.client import VARIANT

from autocad_mcp.service import AutoCADService


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT_DIR, help="carpeta de salida")
    args = parser.parse_args()
    out_dir = Path(args.out)
    dwg = out_dir / "Puente-Golden-Gate.dwg"

    service = AutoCADService()
    if not service.connect():
        print("ERROR: sin conexion")
        return 1

    doc = None
    for item in service.conn.app.Documents:
        if str(item.FullName).lower() == str(dwg).lower():
            doc = item
            break
    if doc is None:
        if not dwg.exists():
            print(f"ERROR: no existe {dwg}")
            return 2
        doc = service.conn.app.Documents.Open(str(dwg))
    service.conn.doc = doc
    service.conn._doc_name = str(doc.Name)  # noqa: SLF001
    doc.Activate()
    print("documento:", doc.Name, flush=True)

    doc.SetVariable("FILEDIA", 0)
    doc.SetVariable("CMDDIA", 0)
    viewport = doc.ActiveViewport
    viewport.Direction = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [1.0, -1.0, 0.8])
    doc.ActiveViewport = viewport
    doc.Regen(1)
    service.conn.app.ZoomExtents()
    doc.Save()

    pdf = out_dir / "Puente-Golden-Gate.pdf"
    written = _plot_pdf(doc, pdf)
    print(f"PDF: {written} ({written.stat().st_size} bytes)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
