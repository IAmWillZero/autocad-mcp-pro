"""Sondeo de metodos disponibles (tabla e insercion de bloques)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import pythoncom  # noqa: E402
import win32com.client  # noqa: E402
from win32com.client import gencache  # noqa: E402

from autocad_mcp.com import variant_point  # noqa: E402


def main() -> int:
    pythoncom.CoInitialize()
    app = win32com.client.GetActiveObject("AutoCAD.Application.25.1")
    doc = app.ActiveDocument
    name = "ZZ_TEST"
    try:
        doc.Layouts.Item(name).Delete()
    except Exception:  # noqa: BLE001
        pass
    doc.Layouts.Add(name)
    doc.ActiveLayout = doc.Layouts.Item(name)
    doc.ActiveSpace = 0
    time.sleep(0.8)
    doc.SetVariable("CTAB", name)
    time.sleep(0.8)
    block = doc.PaperSpace

    for m in ("InsertBlock", "AddBlockReference", "AddTable", "AddJoggedDimension"):
        print(m, hasattr(block, m))

    for args in (
        (variant_point(0.05, 0.05), "OBJ-SOFA-MOD-260", 0.008, 0.008, 0.008, 0.0),
    ):
        try:
            ref = block.InsertBlock(*args)
            print("InsertBlock OK", ref.ObjectName)
            mn, mx = ref.GetBoundingBox()
            print("  bbox", round(float(mn[0]), 4), round(float(mn[1]), 4),
                  round(float(mx[0]), 4), round(float(mx[1]), 4))
            ref.Delete()
        except Exception as exc:  # noqa: BLE001
            print("InsertBlock FALLO", exc)

    t = block.AddTable(variant_point(0.02, 0.25), 3, 3, 0.006, 0.03)
    print("table ok")
    try:
        t.SetCellTextHeight(0, 0, 0.0016)
        print("SetCellTextHeight OK")
    except Exception as exc:  # noqa: BLE001
        print("SetCellTextHeight FALLO", exc)
    try:
        t.SetTextHeight(-1, 0.0016)
        print("SetTextHeight(rowTypes, h) OK")
    except Exception as exc:  # noqa: BLE001
        print("SetTextHeight 2 args FALLO", exc)
    try:
        t.SetCellAlignment(0, 0, 5)
        print("SetCellAlignment OK")
    except Exception as exc:  # noqa: BLE001
        print("SetCellAlignment FALLO", exc)
    try:
        t.SetRowHeight(0, 0.006)
        print("SetRowHeight OK")
    except Exception as exc:  # noqa: BLE001
        print("SetRowHeight FALLO", exc)

    # tipos de letra / estilo de tabla
    try:
        t.StyleName = "Standard"
        print("StyleName OK")
    except Exception as exc:  # noqa: BLE001
        print("StyleName FALLO", exc)

    # metodos de la tabla (lista completa via early binding)
    try:
        early = gencache.EnsureDispatch(t)
        metodos = [m for m in dir(early) if m.startswith(("Set", "Insert", "Get"))]
        print("METODOS:", ", ".join(sorted(metodos)))
    except Exception as exc:  # noqa: BLE001
        print("dir tabla fallo", exc)
    try:
        earlyb = gencache.EnsureDispatch(block)
        print("BLOCK:", ", ".join(sorted(m for m in dir(earlyb) if m.startswith("Add"))))
    except Exception as exc:  # noqa: BLE001
        print("dir block fallo", exc)

    t.Delete()
    doc.Layouts.Item(name).Delete()
    doc.ActiveLayout = doc.Layouts.Item("Model")
    doc.SetVariable("CTAB", "Model")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
