"""Verifica que los rotulos de ambiente queden ENCUADRADOS dentro de su area.

Usa el bounding box real de AutoCAD (no la estimacion 0.62) para comprobar que el
nombre y la superficie de cada local caen dentro del rectangulo del ambiente.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "house"))

import win32com.client as w  # noqa: E402

import house_data as D  # noqa: E402
from autocad_mcp.com import as_dynamic  # noqa: E402

EPS = 0.02


def main() -> int:
    app = w.GetActiveObject("AutoCAD.Application")
    d = app.Documents.Item("CASA.dwg")
    ms = d.ModelSpace

    texts = []
    for i in range(ms.Count):
        e = as_dynamic(ms.Item(i))
        try:
            if str(e.ObjectName) != "AcDbText":
                continue
            s = str(e.TextString)
            lo, hi = e.GetBoundingBox()
        except Exception:  # noqa: BLE001
            continue
        texts.append((s, float(lo[0]), float(lo[1]), float(hi[0]), float(hi[1])))

    problems = []
    checked = 0
    floors = [
        (D.ROOMS1, D.X1, D.Y1, 0.0, 0.0),
        (D.ROOMS2, D.X2, D.Y2, D.OFF2, 0.0),
    ]
    for rooms, X, Y, ox, oy in floors:
        for label, i0, i1, j0, j1 in rooms:
            x0, x1 = X[i0] + ox, X[i1] + ox
            y0, y1 = Y[j0] + oy, Y[j1] + oy
            area = abs(x1 - x0) * abs(y1 - y0)
            wanted = {label, f"{area:.2f} m2"}
            found = 0
            for s, tx0, ty0, tx1, ty1 in texts:
                if s not in wanted:
                    continue
                cx, cy = (tx0 + tx1) / 2, (ty0 + ty1) / 2
                if not (x0 <= cx <= x1 and y0 <= cy <= y1):
                    continue
                found += 1
                checked += 1
                if tx0 < x0 - EPS or tx1 > x1 + EPS or ty0 < y0 - EPS or ty1 > y1 + EPS:
                    problems.append(
                        (label, s, round(tx0, 2), round(ty0, 2), round(tx1, 2), round(ty1, 2))
                    )
            if found == 0:
                problems.append((label, "SIN ROTULO EN EL AMBIENTE", 0, 0, 0, 0))

    print("textos revisados:", checked)
    print("rotulos fuera de su area:", len(problems))
    for p in problems[:40]:
        print("  ", p)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
