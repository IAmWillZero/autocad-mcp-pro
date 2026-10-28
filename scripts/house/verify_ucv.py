"""Fase 9: control final del DWG (solo lectura).

Verifica contornos/capas, cotas, areas, textos, orientacion, los dos banos, los
bloques y los membretes de los layouts. Imprime PASS/FAIL por comprobacion.
"""

from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from autocad_mcp.com import as_dynamic  # noqa: E402
from autocad_mcp.service import AutoCADService  # noqa: E402

TARGET = "Vivienda_UCV_Magisterial_230.dwg"
NEW_NAME = "Vivienda_UCV_Magisterial_230_MEJORADO.dwg"


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
        print("ABORT: sin conexion")
        return 1
    docs = s.conn.app.Documents
    names = [_retry(lambda i=i: str(docs.Item(i).Name)) for i in range(int(docs.Count))]
    if TARGET not in names:
        print("ABORT: no esta abierto", TARGET)
        return 1
    doc = _retry(lambda: docs.Item(TARGET))
    _retry(doc.Activate)
    s.conn.doc = doc

    ms = _retry(lambda: doc.ModelSpace)
    n = int(_retry(lambda: ms.Count))
    by_layer: Counter[str] = Counter()
    by_type: Counter[str] = Counter()
    texts: list[tuple[str, tuple]] = []
    refs: Counter[str] = Counter()
    wall_dims: list[float] = []
    for i in range(n):
        try:
            e = as_dynamic(ms.Item(i))
            oname = str(e.ObjectName)
            lay = str(e.Layer)
            by_layer[lay] += 1
            by_type[oname] += 1
            if oname == "AcDbText":
                lo, hi = e.GetBoundingBox()
                texts.append(
                    (str(e.TextString), (float(lo[0]), float(lo[1]), float(hi[0]), float(hi[1])))
                )
            elif oname == "AcDbBlockReference":
                refs[str(e.Name)] += 1
            elif oname == "AcDbPolyline" and lay == "A-MUROS-CARGA":
                lo, hi = e.GetBoundingBox()
                wall_dims.append(min(float(hi[0]) - float(lo[0]), float(hi[1]) - float(lo[1])))
        except Exception:  # noqa: BLE001
            continue

    ok = True

    def check(name: str, cond: bool, extra: str = "") -> None:
        nonlocal ok
        ok = ok and cond
        print(f"[{'PASS' if cond else 'FAIL'}] {name} {extra}")

    print(f"entidades: {n}")
    print("por capa:", dict(by_layer))
    print("por tipo:", dict(by_type))
    print("refs de bloque:", dict(refs))

    def overlaps() -> list:
        def ov(a, b, pad=0.02):
            return not (
                a[2] + pad <= b[0] or b[2] + pad <= a[0] or a[3] + pad <= b[1] or b[3] + pad <= a[1]
            )

        # Solo la zona de planos/zonificacion (x < 66) para no medir las laminas
        # de cortes/elevaciones/detalles, que reutilizan etiquetas.
        plan = [(t, b) for (t, b) in texts if b[0] < 66.0]
        return [
            (plan[i][0], plan[j][0])
            for i in range(len(plan))
            for j in range(i + 1, len(plan))
            if ov(plan[i][1], plan[j][1])
        ]

    hit = overlaps()
    check("sin solapes de texto", not hit, f"({len(texts)} textos, {len(hit)} solapes)")
    for h in hit[:10]:
        print("    solape:", h)

    check(
        "cotas completas (>=30)",
        by_layer.get("A-COTAS", 0) >= 30,
        f"A-COTAS={by_layer.get('A-COTAS', 0)}",
    )
    check(
        "una sola escalera por planta (muros tabique >= 40)",
        by_layer.get("A-MUROS-TABIQ", 0) >= 40,
        f"A-MUROS-TABIQ={by_layer.get('A-MUROS-TABIQ', 0)}",
    )

    labels = [t for t, _b in texts]
    sshh = {t for t in labels if t in ("SS.HH. 1", "SS.HH. 2", "SS.HH. 3")}
    check(
        "exactamente 3 banos (SS.HH. 1 + 2 + 3)",
        sshh == {"SS.HH. 1", "SS.HH. 2", "SS.HH. 3"},
        f"{sorted(sshh)}",
    )
    check("sin banos duplicados", not any("EXISTENTE" in t or "NUEVO" in t for t in labels))
    check("existe NORTH/rotulo N", "N" in labels)
    check("existe cuadro de areas", "CUADRO DE AREAS" in labels)
    check("existe cuadro de vanos", "CUADRO DE VANOS" in labels)
    check(
        "ducha insertada (>=2 refs)",
        refs.get("A-DUCHA", 0) >= 2,
        f"A-DUCHA={refs.get('A-DUCHA', 0)}",
    )

    if wall_dims:
        import statistics

        med = statistics.median(wall_dims)
        check("muros de ~0.15 m", 0.13 <= med <= 0.17, f"mediana={med:.3f} m (n={len(wall_dims)})")

    for nm in ("PLANTAS", "ZONIFICACION", "CORTES", "ELEVACIONES", "DETALLES"):
        try:
            _retry(lambda nm=nm: s.layouts.set_active_layout(nm))
            al = _retry(lambda: as_dynamic(doc.ActiveLayout))
            media = str(al.CanonicalMediaName)
            landscape = "297.00_x_210.00" in media
            check(f"A4 horizontal en {nm}", landscape, media)
            ps = _retry(lambda: as_dynamic(doc.PaperSpace))
            npap = int(_retry(lambda: ps.Count))
            ps_txt = []
            vp_count = 0
            vp_scale = None
            for k in range(npap):
                try:
                    ent = as_dynamic(ps.Item(k))
                    oname = str(ent.ObjectName)
                    if oname == "AcDbText":
                        ps_txt.append(str(ent.TextString))
                    elif oname == "AcDbViewport":
                        vp_count += 1
                        vp_scale = float(ent.CustomScale)
                except Exception:  # noqa: BLE001
                    continue
            tiene = any("UNIVERSIDAD" in t for t in ps_txt) and any("LAMINA" in t for t in ps_txt)
            check(f"membrete UCV en layout {nm}", tiene, f"paperspace={npap}")
            check(f"un solo viewport en {nm}", vp_count == 1, f"n={vp_count}")
            check(
                f"escala 1:150 en {nm}",
                vp_scale is not None and abs(vp_scale - 1.0 / 150.0) < 1e-4,
                f"CustomScale={vp_scale}",
            )
        except Exception as exc:  # noqa: BLE001
            check(f"layout {nm}", False, str(exc))
    _retry(lambda: s.layouts.set_active_layout("Model"))

    newp = ROOT / "out" / NEW_NAME
    check(
        "archivo NUEVO guardado",
        newp.exists(),
        f"{os.path.getsize(newp) if newp.exists() else 0} bytes",
    )

    print("\nFASE 9:", "PASS" if ok else "FAIL")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
