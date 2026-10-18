"""Detecta solapes entre textos (AcDbText) en el ModelSpace de CASA.dwg."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import win32com.client as w

from autocad_mcp.com import as_dynamic

app = w.GetActiveObject("AutoCAD.Application")
d = app.Documents.Item("CASA.dwg")
ms = d.ModelSpace

texts = []
for i in range(ms.Count):
    e = as_dynamic(ms.Item(i))
    try:
        if str(e.ObjectName) != "AcDbText":
            continue
    except Exception:  # noqa: BLE001
        continue
    try:
        txt = str(e.TextString)
        h = float(e.Height)
        ip = e.InsertionPoint
        x, y = float(ip[0]), float(ip[1])
    except Exception:  # noqa: BLE001
        continue
    wd = len(txt) * 0.62 * h
    texts.append((txt, x, y, wd, h, (x, y, x + wd, y + h)))

print("textos:", len(texts))


def ov(a, b, pad=0.0):
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return not (ax1 + pad <= bx0 or bx1 + pad <= ax0 or ay1 + pad <= by0 or by1 + pad <= ay0)


hits = []
for i in range(len(texts)):
    for j in range(i + 1, len(texts)):
        if ov(texts[i][5], texts[j][5], pad=0.02):
            hits.append((texts[i][0], texts[j][0], texts[i][1:3], texts[j][1:3]))

print("solapes:", len(hits))
for t in hits[:40]:
    print("  ", t)
