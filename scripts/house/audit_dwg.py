"""Fase 1: auditoria SOLO LECTURA del DWG residencial + copia de seguridad.

No modifica ni elimina nada. Inspecciona unidades, capas, entidades, bloques,
extents, cotas, textos y layouts, y deja una copia de seguridad en out/backup/.
"""

from __future__ import annotations

import os
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from autocad_mcp.com import as_dynamic  # noqa: E402
from autocad_mcp.service import AutoCADService  # noqa: E402

OUT_DIR = ROOT / "out"
TARGET = "Vivienda_UCV_Magisterial_230.dwg"
BACKUP_DIR = OUT_DIR / "backup"


def _retry(fn, tries: int = 8, delay: float = 1.0):
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
        print("ABORT: sin conexion a AutoCAD")
        return 1
    app = s.conn.app
    docs = app.Documents
    names = [_retry(lambda i=i: str(docs.Item(i).Name)) for i in range(int(docs.Count))]
    if TARGET not in names:
        print("ABORT: no esta abierto", TARGET, "->", names)
        return 1
    doc = _retry(lambda: docs.Item(TARGET))
    _retry(doc.Activate)
    s.conn.doc = doc

    print("=" * 70)
    print("FASE 1 - AUDITORIA:", TARGET)
    print("=" * 70)

    full = str(_retry(lambda: doc.FullName))
    print("ruta          :", full)
    print("tamano        :", os.path.getsize(full), "bytes")

    # --- copia de seguridad ---
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    bak = BACKUP_DIR / (Path(TARGET).stem + "_bak_auditoria.dwg")
    try:
        _retry(lambda: doc.SaveAs(str(bak)))
        _retry(lambda: doc.SaveAs(full))
        print("backup        :", bak)
    except Exception as exc:  # noqa: BLE001
        print("backup FALLO  :", exc)
        try:
            shutil.copy2(full, bak)
            print("backup (copy) :", bak)
        except Exception as exc2:  # noqa: BLE001
            print("backup copy FALLO:", exc2)

    # --- unidades / variables ---
    def var(name: str):
        try:
            return _retry(lambda: doc.GetVariable(name))
        except Exception:  # noqa: BLE001
            return None

    for v in (
        "INSUNITS",
        "LUNITS",
        "LUPREC",
        "DIMSCALE",
        "LTSCALE",
        "MEASUREMENT",
        "EXTMIN",
        "EXTMAX",
    ):
        print(f"{v:14}:", var(v))

    # --- entidades ---
    ms = _retry(lambda: doc.ModelSpace)
    n = int(_retry(lambda: ms.Count))
    by_layer: Counter[str] = Counter()
    by_type: Counter[str] = Counter()
    texts: list[tuple[str, tuple]] = []
    for i in range(n):
        try:
            e = as_dynamic(ms.Item(i))
            lay = str(e.Layer)
            oname = str(e.ObjectName)
            by_layer[lay] += 1
            by_type[oname] += 1
            if oname == "AcDbText":
                lo, hi = e.GetBoundingBox()
                texts.append(
                    (str(e.TextString), (float(lo[0]), float(lo[1]), float(hi[0]), float(hi[1])))
                )
        except Exception:  # noqa: BLE001
            continue

    print("\nentidades ModelSpace:", n)
    print("por capa:")
    for k, v in sorted(by_layer.items()):
        print(f"   {k:18} {v}")
    print("por tipo:")
    for k, v in sorted(by_type.items()):
        print(f"   {k:22} {v}")

    # --- bloques ---
    blocks = _retry(lambda: doc.Blocks)
    bn = int(_retry(lambda: blocks.Count))
    print("\nbloques definidos:", bn)
    for i in range(bn):
        try:
            b = as_dynamic(blocks.Item(i))
            nm = str(b.Name)
            if nm.startswith("*"):
                continue
            bp = b.GetBasePoint() if hasattr(b, "GetBasePoint") else None
            cnt = int(b.Count) if hasattr(b, "Count") else -1
            print(f"   {nm:26} base={bp} refs={cnt}")
        except Exception:  # noqa: BLE001
            continue

    # --- layouts ---
    layouts = _retry(lambda: doc.Layouts)
    ln = int(_retry(lambda: layouts.Count))
    print("\nlayouts:", ln)
    for i in range(ln):
        try:
            print("   ", str(layouts.Item(i).Name))
        except Exception:  # noqa: BLE001
            continue

    # --- textos (rotulos / ambientes) ---
    print("\ntextos:", len(texts))
    labels = [t for t, _b in texts]
    for t in labels:
        print("   ", t)

    print("\nFASE 1 completada (sin cambios en la geometria).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
