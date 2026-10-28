"""Diagnóstico de solo lectura del DWG de plantas UCV.

Imprime: documentos abiertos en AutoCAD, layouts, conteos por capa/tipo,
bloques definidos (OBJ-*), refs en modelo y los segmentos de muro
(A-MUROS-CARGA / A-MUROS-TABIQ) de la planta baja (x < 14).

No escribe, no guarda, no modifica nada.

Uso: python scripts/house/diag_plantas.py
"""

from __future__ import annotations

import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from autocad_mcp.com import as_dynamic  # noqa: E402
from autocad_mcp.service import AutoCADService  # noqa: E402

TARGET = ROOT / "out" / "Vivienda_UCV_Magisterial_230_PLANTAS.dwg"


def rt(fn, tries: int = 10, delay: float = 0.8):
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
        print("ABORT: sin conexion", flush=True)
        return 1
    docs = s.conn.app.Documents
    n_docs = int(rt(lambda: docs.Count))
    print(f"DOCUMENTOS ABIERTOS: {n_docs}", flush=True)
    for i in range(n_docs):
        try:
            d = docs.Item(i)
            nm = str(rt(lambda d=d: d.Name))
            try:
                full = str(rt(lambda d=d: d.FullName))
            except Exception:  # noqa: BLE001
                full = "(sin guardar)"
            print(f"  [{i}] {nm} | {full}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  [{i}] ERR {exc}", flush=True)

    doc = None
    for i in range(n_docs):
        try:
            d = docs.Item(i)
            if str(rt(lambda d=d: d.FullName)).lower() == str(TARGET).lower():
                doc = d
                break
        except Exception:  # noqa: BLE001
            continue
    if doc is None:
        print("ABORT: el PLANTAS.dwg no esta abierto", flush=True)
        return 2
    rt(doc.Activate)
    s.conn.doc = doc
    print(f"OBJETIVO: {rt(lambda: doc.Name)}", flush=True)

    lays = rt(lambda: doc.Layouts)
    n_lays = int(rt(lambda: lays.Count))
    print(f"\nLAYOUTS ({n_lays}):", flush=True)
    for i in range(n_lays):
        try:
            lay = lays.Item(i)
            print(f"  {str(lay.Name)} | media={str(lay.CanonicalMediaName)}", flush=True)
        except Exception:  # noqa: BLE001
            print("  <layout err>", flush=True)

    ms = rt(lambda: as_dynamic(doc.ModelSpace))
    n = int(rt(lambda: ms.Count))
    by_layer: Counter[str] = Counter()
    by_type: Counter[str] = Counter()
    walls_pb: list = []
    walls_pa: list = []
    refs_model: Counter[str] = Counter()
    for i in range(n):
        try:
            e = as_dynamic(ms.Item(i))
            t = str(e.ObjectName)
            lay = str(e.Layer)
            by_layer[lay] += 1
            by_type[t] += 1
            if t == "AcDbBlockReference":
                refs_model[str(e.Name)] += 1
            if lay in ("A-MUROS-CARGA", "A-MUROS-TABIQ"):
                if t == "AcDbLine":
                    a = e.StartPoint
                    b = e.EndPoint
                    seg = (
                        round(float(a[0]), 3),
                        round(float(a[1]), 3),
                        round(float(b[0]), 3),
                        round(float(b[1]), 3),
                    )
                elif t == "AcDbPolyline":
                    seg = tuple(round(float(v), 3) for v in e.Coordinates)
                else:
                    seg = ()
                xmin = min(seg[0::2]) if seg else 0.0
                (walls_pb if xmin < 14.0 else walls_pa).append((str(e.Handle), lay, t, seg))
        except Exception:  # noqa: BLE001
            continue

    print(f"\nMODELO: {n} entidades", flush=True)
    print("por capa:", dict(sorted(by_layer.items())), flush=True)
    print("por tipo:", dict(sorted(by_type.items())), flush=True)
    print("refs de bloque en modelo:", dict(refs_model) or "{}", flush=True)

    blocks = rt(lambda: doc.Blocks)
    n_b = int(rt(lambda: blocks.Count))
    names = []
    for i in range(n_b):
        try:
            names.append(str(rt(lambda i=i: blocks.Item(i).Name)))
        except Exception:  # noqa: BLE001
            continue
    objs = sorted(x for x in names if x.startswith("OBJ-"))
    print(f"\nBLOQUES: {n_b}; OBJ-*: {len(objs)}", flush=True)
    for x in objs:
        print("  ", x, flush=True)

    print(f"\nMUROS (PB, x<14): {len(walls_pb)} segmentos", flush=True)
    for h, lay, t, seg in sorted(
        walls_pb,
        key=lambda r: (r[3][0] if r[3] else 0.0, r[3][1] if len(r[3]) > 1 else 0.0),
    ):
        print(f"  {h} {lay} {t} {seg}", flush=True)
    print(f"MUROS (PA, x>=14): {len(walls_pa)} segmentos (no se listan)", flush=True)

    try:
        rt(lambda: s.layouts.set_active_layout("BIBLIOTECA"))
        ps = rt(lambda: as_dynamic(doc.PaperSpace))
        nps = int(rt(lambda: ps.Count))
        ps_refs: Counter[str] = Counter()
        for k in range(nps):
            try:
                pe = as_dynamic(ps.Item(k))
                if str(pe.ObjectName) == "AcDbBlockReference":
                    ps_refs[str(pe.Name)] += 1
            except Exception:  # noqa: BLE001
                continue
        print(
            f"\nBIBLIOTECA paperspace: {nps} entidades; refs={dict(ps_refs) or '{}'}",
            flush=True,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"\nBIBLIOTECA: no se pudo inspeccionar: {exc}", flush=True)
    try:
        rt(lambda: s.layouts.set_active_layout("Model"))
    except Exception:  # noqa: BLE001
        pass

    print("\nFIN DIAG", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
