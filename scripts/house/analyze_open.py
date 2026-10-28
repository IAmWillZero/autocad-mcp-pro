"""Analisis READ-ONLY del dibujo abierto en AutoCAD.

Vuelca a out/open_drawing_report.json:
- documentos abiertos, layout activo, limites del modelo
- por layout: entidades del espacio papel (textos con posicion, viewports,
  polilineas, tablas)
- bloques definidos y cuantas veces se insertan
No modifica nada del dibujo.
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import pythoncom  # noqa: E402
import win32com.client  # noqa: E402

OUT = ROOT / "out" / "open_drawing_report.json"


def _f(value, default=None):
    try:
        return float(value)
    except Exception:  # noqa: BLE001
        return default


def entity_info(e) -> dict:
    info: dict = {"type": "?", "layer": "?"}
    try:
        info["type"] = str(e.ObjectName).replace("AcDb", "")
    except Exception:  # noqa: BLE001
        pass
    try:
        info["layer"] = str(e.Layer)
    except Exception:  # noqa: BLE001
        pass
    try:
        info["handle"] = str(e.Handle)
    except Exception:  # noqa: BLE001
        pass
    t = info["type"]
    try:
        if t in ("Text", "MText", "AttributeDefinition"):
            ip = e.InsertionPoint
            info["text"] = str(e.TextString)
            info["at"] = [round(float(ip[0]), 4), round(float(ip[1]), 4)]
            info["h"] = round(_f(e.Height, 0.0), 5)
            try:
                info["rot"] = round(_f(e.Rotation, 0.0), 2)
            except Exception:  # noqa: BLE001
                pass
            try:
                info["align"] = int(e.Alignment)
            except Exception:  # noqa: BLE001
                pass
        elif t == "Viewport":
            c = e.Center
            info["center"] = [round(float(c[0]), 4), round(float(c[1]), 4)]
            info["w"] = round(_f(e.Width, 0.0), 4)
            info["h"] = round(_f(e.Height, 0.0), 4)
            info["scale"] = round(_f(e.CustomScale, 0.0), 5)
            info["id"] = int(_f(e.ID, 0))
            info["locked"] = bool(e.DisplayLocked)
            info["status"] = str(e.Status)
        elif t in ("Line", "Polyline", "LWPolyline", "Arc", "Circle", "Hatch"):
            try:
                mn, mx = e.GetBoundingBox()
                info["bbox"] = [
                    round(float(mn[0]), 4),
                    round(float(mn[1]), 4),
                    round(float(mx[0]), 4),
                    round(float(mx[1]), 4),
                ]
            except Exception:  # noqa: BLE001
                pass
        elif t == "BlockReference":
            info["block"] = str(e.Name)
            ip = e.InsertionPoint
            info["at"] = [round(float(ip[0]), 4), round(float(ip[1]), 4)]
            try:
                mn, mx = e.GetBoundingBox()
                info["bbox"] = [
                    round(float(mn[0]), 4),
                    round(float(mn[1]), 4),
                    round(float(mx[0]), 4),
                    round(float(mx[1]), 4),
                ]
            except Exception:  # noqa: BLE001
                pass
        elif t == "Table":
            info["rows"] = int(e.Rows)
            info["cols"] = int(e.Columns)
            cells = []
            for r in range(1, min(int(e.Rows), 40) + 1):
                row = []
                for c in range(1, min(int(e.Columns), 12) + 1):
                    try:
                        row.append(str(e.GetText(r, c)))
                    except Exception:  # noqa: BLE001
                        row.append("")
                cells.append(row)
            info["cells"] = cells
            ip = e.InsertionPoint
            info["at"] = [round(float(ip[0]), 4), round(float(ip[1]), 4)]
    except Exception:  # noqa: BLE001
        info["error"] = traceback.format_exc(limit=1).strip().splitlines()[-1]
    return info


def space_dump(block) -> list[dict]:
    out = []
    try:
        n = int(block.Count)
    except Exception:  # noqa: BLE001
        return out
    for i in range(n):
        try:
            out.append(entity_info(block.Item(i)))
        except Exception:  # noqa: BLE001
            out.append({"type": "ERROR"})
    return out


def main() -> int:
    pythoncom.CoInitialize()
    app = win32com.client.GetActiveObject("AutoCAD.Application.25.1")
    app.Visible = True

    report: dict = {"version": str(app.Version), "documents": []}
    docs = app.Documents
    for i in range(int(docs.Count)):
        try:
            report["documents"].append(str(docs.Item(i).Name))
        except Exception:  # noqa: BLE001
            report["documents"].append("?")

    doc = app.ActiveDocument
    report["active"] = str(doc.Name)
    report["path"] = str(doc.FullName)
    report["dirty"] = bool(doc.Saved) is False

    for var in ("INSUNITS", "MEASUREMENT", "LUNITS", "EXTMIN", "EXTMAX"):
        try:
            report[var] = doc.GetVariable(var)
        except Exception:  # noqa: BLE001
            report[var] = None

    report["layers"] = []
    for i in range(int(doc.Layers.Count)):
        try:
            lay = doc.Layers.Item(i)
            report["layers"].append(
                {
                    "name": str(lay.Name),
                    "color": int(lay.Color),
                    "on": bool(lay.LayerOn),
                    "plot": bool(lay.Plottable),
                    "frozen": bool(lay.Freeze),
                }
            )
        except Exception:  # noqa: BLE001
            pass

    ms = doc.ModelSpace
    report["model_count"] = int(ms.Count)
    used: dict[str, int] = {}
    try:
        for i in range(int(ms.Count)):
            e = ms.Item(i)
            if str(e.ObjectName) == "AcDbBlockReference":
                used[str(e.Name)] = used.get(str(e.Name), 0) + 1
    except Exception:  # noqa: BLE001
        pass
    report["block_insertions"] = used

    report["block_defs"] = {}
    for i in range(int(doc.Blocks.Count)):
        try:
            b = doc.Blocks.Item(i)
            name = str(b.Name)
            if name.startswith("*"):
                continue
            report["block_defs"][name] = int(b.Count)
        except Exception:  # noqa: BLE001
            pass

    report["layouts"] = {}
    report["active_layout"] = str(doc.ActiveLayout.Name)
    for i in range(int(doc.Layouts.Count)):
        layout = doc.Layouts.Item(i)
        name = str(layout.Name)
        entry: dict = {}
        try:
            entry["tab_order"] = int(layout.TabOrder)
        except Exception:  # noqa: BLE001
            pass
        try:
            entry["paper_w"] = round(_f(layout.PlotPaperSize[0], 0.0), 4) if False else None
            entry["media"] = str(layout.CanonicalMediaName)
            entry["paper_units"] = int(layout.PaperUnits)
            entry["plot_rotation"] = str(layout.PlotRotation)
        except Exception:  # noqa: BLE001
            pass
        if name != "Model":
            try:
                entry["entities"] = space_dump(layout.Block)
            except Exception:  # noqa: BLE001
                entry["entities"] = []
                entry["error"] = "sin acceso al Block"
        else:
            entry["entities"] = []
        report["layouts"][name] = entry

    # resumen de textos del modelo (para ubicar cuadros)
    texts = []
    try:
        for i in range(int(ms.Count)):
            e = ms.Item(i)
            if str(e.ObjectName) in ("AcDbText", "AcDbMText"):
                try:
                    ip = e.InsertionPoint
                    texts.append(
                        {
                            "t": str(e.TextString)[:90],
                            "x": round(float(ip[0]), 2),
                            "y": round(float(ip[1]), 2),
                            "layer": str(e.Layer),
                        }
                    )
                except Exception:  # noqa: BLE001
                    pass
    except Exception:  # noqa: BLE001
        pass
    report["model_texts"] = texts

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")

    print("doc:", report["active"])
    print("layouts:", list(report["layouts"].keys()))
    print("model_count:", report["model_count"], "| texts:", len(texts))
    print("blocks:", len(report["block_defs"]), "| insertados:", len(used))
    print("reporte:", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
