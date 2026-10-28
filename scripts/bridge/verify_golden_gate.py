"""Verificacion del DWG construido: nombre, entidades y geometria clave."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from build_golden_gate import OUT_DIR
from autocad_mcp.service import AutoCADService


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT_DIR, help="carpeta de salida")
    args = parser.parse_args()
    dwg = Path(args.out) / "Puente-Golden-Gate.dwg"

    service = AutoCADService()
    if not service.connect():
        print("ERROR: sin conexion")
        return 1

    doc = None
    for item in service.conn.app.Documents:
        if Path(str(item.FullName)).name.lower() == dwg.name.lower():
            doc = item
            break
    if doc is None:
        doc = service.conn.app.Documents.Open(str(dwg))
    service.conn.doc = doc
    service.conn._doc_name = str(doc.Name)  # noqa: SLF001
    doc.Activate()
    print("documento:", doc.Name, flush=True)

    info = service.info.get_drawing_info()
    print("entidades:", info.get("entity_count"), "capas:", info.get("total_layers"))

    report = service.solids.get_solid_info(include_entities=True)
    print("solidos:", report["count"], "volumen:", report["total_volume"])
    print("extents:", report.get("extents"))

    rows = report["entities"]
    towers = [r for r in rows if r["layer"] == "S-TORRES"]
    cables = [r for r in rows if r["layer"] == "S-CABLES"]
    deck = [r for r in rows if r["layer"] == "S-TABLERO"]

    print("torres: n=", len(towers), " z_max=", max(r["bbox"][1][2] for r in towers))
    xs = sorted({round(r["bbox"][0][0] + r["bbox"][1][0], 1) / 2 for r in towers})
    print("torres x (medias):", xs)
    print("cables: n=", len(cables), " z_min=", min(r["bbox"][0][2] for r in cables))
    print("tablero: z=", sorted({round(r["bbox"][0][2], 2) for r in deck})[:4])
    suspenders = [
        r
        for r in cables
        if r["bbox"][1][0] - r["bbox"][0][0] < 2.0
        and r["bbox"][1][1] - r["bbox"][0][1] < 2.0
        and r["bbox"][1][2] - r["bbox"][0][2] > 2.0
    ]
    print("suspensores verticales:", len(suspenders))
    return 0


if __name__ == "__main__":
    sys.exit(main())
