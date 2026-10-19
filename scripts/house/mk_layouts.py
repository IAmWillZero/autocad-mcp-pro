"""Crea (si faltan) los layouts PLANTA BAJA / PLANTA ALTA con reintentos."""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from autocad_mcp.service import AutoCADService


def retry(fn, tries: int = 10, delay: float = 1.5):
    last = None
    for _ in range(tries):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(delay)
    raise last


def main() -> int:
    s = AutoCADService()
    if not s.connect():
        print("no conecta")
        return 1
    s.documents.set_active_document("CASA.dwg")
    print("doc", s.conn.doc.Name)

    for name in ("PLANTA BAJA", "PLANTA ALTA"):
        try:
            s.conn.doc.Layouts.Item(name).Delete()
        except Exception:  # noqa: BLE001
            pass

    for name, vcx, vcy in (("PLANTA BAJA", 2.3, 10.9), ("PLANTA ALTA", 21.0, 10.9)):
        lay = retry(
            lambda name=name: s.layouts.create_layout(
                name, media="ISO_A3_(297.00_x_420.00_MM)", plot_style_table="acad.ctb"
            )
        )
        print("layout:", lay.get("message", lay))
        vp = retry(
            lambda name=name, vcx=vcx, vcy=vcy: s.layouts.create_viewport(
                name,
                center=[148.5, 210.0],
                width=170.0,
                height=372.0,
                scale=0.01,
                view_center=[vcx, vcy],
            )
        )
        print("viewport:", vp.get("message", vp))
    retry(lambda: s.layouts.set_active_layout("Model"))
    print("listo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
