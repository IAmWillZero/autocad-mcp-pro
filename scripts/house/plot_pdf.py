"""Fase 9: vista previa PDF de las laminas (best-effort).

Traza cada layout a PDF usando la configuracion de pagina existente. Si el
AutoCAD no tiene un dispositivo de trazado configurado, informa y termina.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from autocad_mcp.com import as_dynamic  # noqa: E402
from autocad_mcp.service import AutoCADService  # noqa: E402

TARGET = "Vivienda_UCV_Magisterial_230.dwg"
PDF_DIR = ROOT / "out" / "pdf"


def _retry(fn, tries: int = 6, delay: float = 1.0):
    import time

    last = None
    for _ in range(tries):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(delay)
    raise last  # type: ignore[misc]


def main() -> int:
    s = AutoCADService()
    if not s.connect():
        print("ABORT: sin conexion")
        return 1
    docs = s.conn.app.Documents
    names = [_retry(lambda i=i: str(docs.Item(i).Name)) for i in range(int(docs.Count))]
    if TARGET not in names:
        print("ABORT: no esta abierto", TARGET)
        return 1
    doc = _retry(lambda: docs.Item(TARGET))
    _retry(doc.Activate)
    s.conn.doc = doc
    PDF_DIR.mkdir(parents=True, exist_ok=True)

    try:
        _retry(lambda: doc.SetVariable("BACKGROUNDPLOT", 0))
    except Exception as exc:  # noqa: BLE001
        print("aviso BACKGROUNDPLOT:", exc)

    pdf_pc3 = (str(Path(os.environ["APPDATA"]) / "Autodesk" / "AutoCAD 2026" / "R25.1"
                   / "enu" / "plotters" / "DWG To PDF.pc3"))
    for nm in ("ZONIFICACION", "PLANTA BAJA", "PLANTA ALTA"):
        out = str(PDF_DIR / f"UCV_Magisterial_230_{nm.replace(' ', '_')}.pdf")
        try:
            _retry(lambda nm=nm: doc.SetVariable("CTAB", nm))
            if os.path.exists(pdf_pc3):
                _retry(lambda: setattr(as_dynamic(doc.ActiveLayout), "ConfigName", pdf_pc3))
            al = as_dynamic(doc.ActiveLayout)
            try:
                medias = [str(m) for m in al.GetCanonicalMediaNames()]
                pick = next((m for m in medias if "A3" in m.upper()), None)
                if pick:
                    al.CanonicalMediaName = pick
            except Exception as exc:  # noqa: BLE001
                print("  aviso media:", exc)
            _retry(lambda: setattr(al, "PlotType", 5))  # 5 = Layout
            _retry(lambda: doc.Plot.PlotToFile(out))
            print("OK", out, os.path.getsize(out), "bytes")
        except Exception as exc:  # noqa: BLE001
            print("FALLO", nm, "->", exc)
    _retry(lambda: doc.SetVariable("CTAB", "Model"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
