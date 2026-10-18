"""Verificacion del dibujo de la vivienda (documento activo)."""

from __future__ import annotations

import win32com.client

PROGID = "AutoCAD.Application"


def main() -> int:
    app = win32com.client.GetActiveObject(PROGID)
    names = [str(app.Documents.Item(i).Name) for i in range(app.Documents.Count)]
    doc = app.Documents.Item("CASA.dwg") if "CASA.dwg" in names else app.ActiveDocument
    print("Documento:", doc.Name)
    ms = doc.ModelSpace
    layers: dict = {}
    bad_layer = []
    non_bylayer = 0
    blocks = 0
    minx = miny = 1e18
    maxx = maxy = -1e18
    for i in range(ms.Count):
        e = ms.Item(i)
        lay = str(e.Layer)
        layers[lay] = layers.get(lay, 0) + 1
        if lay in ("0", "Defpoints"):
            bad_layer.append(str(getattr(e, "ObjectName", "")))
        try:
            if int(e.color) != 256:
                non_bylayer += 1
        except Exception:
            pass
        if "BlockReference" in str(e.ObjectName):
            blocks += 1
        try:
            lo, hi = e.GetBoundingBox()
            xs = [lo[0], hi[0]]
            ys = [lo[1], hi[1]]
            minx, maxx = min(minx, *xs), max(maxx, *xs)
            miny, maxy = min(miny, *ys), max(maxy, *ys)
        except Exception:
            pass
    print("Entidades:", ms.Count)
    print("Por capa:", layers)
    print("En capa 0/Defpoints:", len(bad_layer), bad_layer[:5])
    print("No-ByLayer:", non_bylayer)
    print("BlockRefs:", blocks)
    print("BBox: min", round(minx, 3), round(miny, 3), " max", round(maxx, 3), round(maxy, 3))
    print("Layouts:", [str(doc.Layouts.Item(i).Name) for i in range(doc.Layouts.Count)])
    print("Bloques:", [str(doc.Blocks.Item(i).Name) for i in range(doc.Blocks.Count)
                       if not str(doc.Blocks.Item(i).Name).startswith("*")])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
