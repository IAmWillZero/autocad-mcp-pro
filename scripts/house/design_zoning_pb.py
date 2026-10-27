"""Dibuja SOLO la primera zonificacion (planta baja) para revision.

No inserta bloques, no crea tablas, no plotea y no toca la planta alta.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "house"))

from autocad_mcp.service import AutoCADService  # noqa: E402
import ucv_data as U  # noqa: E402
import vivienda_ucv as V  # noqa: E402

OUT = ROOT / "out" / "Vivienda_UCV_Magisterial_230_ZONIFICACION_PB.dwg"


def _clean(s: AutoCADService):
    docs = s.conn.app.Documents
    for i in range(int(docs.Count)):
        d = docs.Item(i)
        try:
            if str(d.FullName).lower() == str(OUT).lower():
                s.conn.doc = d
                d.Activate()
                return d
        except Exception:  # noqa: BLE001
            pass
    os.makedirs(OUT.parent, exist_ok=True)
    if OUT.exists():
        d = docs.Open(str(OUT))
    else:
        d = docs.Add()
        d.SaveAs(str(OUT))
    s.conn.doc = d
    d.Activate()
    return d


def main() -> int:
    s = AutoCADService()
    if not s.connect():
        print("ABORT: sin conexion", flush=True)
        return 1
    doc = _clean(s)
    print("Documento:", doc.Name, flush=True)
    s.deleter.delete_all_entities(confirm=True)
    # Capas y estilos base (sin bloques ni tablas).
    s.standards.apply_standard()
    for lay, color in (
        ("Z-SOCIAL", "magenta"),
        ("Z-SERVICIOS", "blue"),
        ("Z-PRIVADA", "green"),
        ("Z-CIRCULACION", "yellow"),
        ("Z-AREA-LIBRE", "green"),
        ("A-MUROS-TABIQ", "white"),
        ("A-TERRENO", "white"),
        ("A-TEXTOS", "white"),
        ("A-ROTULO", "white"),
    ):
        s.layer_tools.create_or_get_layer(lay, color, "Zonificacion")

    # Primera lamina de zonificacion: solo planta baja, en el origen.
    V._terreno(s, 0.0)
    V._room_zones(s, U.ROOMS1, U.X1, U.Y1, 0.0)
    V._stair_plan(s, U.STAIR, 0.0, 0.0, "SUBE")
    for pts in (U.JARDIN_FRONTAL, U.TERRAZA_POST, U.JARDIN_POST):
        if pts:
            V._zone(s, "Z-AREA-LIBRE", pts, V._lib_label(pts), V._mid(pts))
    V._legend(s, 19.5, 22.6)
    V._north(s, 26.8, 20.6)
    s.layer_tools.set_current_layer("A-TEXTOS")
    s.geometry.create_text([0.0, 23.45],
                           "PLANTA BAJA - ZONIFICACION (REVISION 6)", 0.26, "bylayer")
    s.geometry.create_text([0.0, 22.95],
                           "TODO EL ANCHO (8.00 m) / CORREDOR RECTO DESDE EL HALL / "
                           "ESCALERA EN L, 1ER TRAMO JUNTO AL MURO ESTE / SERVICIOS AMPLIADOS",
                           0.15, "bylayer")
    s.ops.zoom_extents()
    doc.Save()
    print("Guardado:", OUT, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
