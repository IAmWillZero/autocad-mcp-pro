"""Acotado completo de las dos plantas (PB y PA).

Recorta de forma determinista todas las cotas de la capa A-COTAS:
- cadenas inferiores y de habitaciones (igual que las existentes)
- cadenas superiores y laterales derechas (nuevo)
- cotas totales 8.00 x 17.00 por planta (nuevo)

Es idempotente: borra las cotas anteriores de A-COTAS y las vuelve a crear.
Usa el estilo MCP-ARQ ya presente en el DWG.
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import pythoncom  # noqa: E402
import win32com.client  # noqa: E402

from autocad_mcp.com import variant_point  # noqa: E402

ROT_H = 0.0
ROT_V = math.pi / 2

# cadenas horizontales por planta: (x de referencia (muro), segmentos, y cota)
PLANTAS = {
    "PB": {
        "x_ejes": [-1.0, 2.0, 3.4, 5.2, 7.0],
        "y_ejes": [4.0, 9.5, 12.5, 14.25, 16.0, 18.0, 21.0],
        "salas_x": [(-1.0, 3.4), (3.4, 7.0)],
        "salas_y": [(4.0, 12.5), (12.5, 21.0)],
        "ref_inf": 4.0,
        "ref_sup": 21.0,
        "ref_izq": -1.0,
        "ref_der": 7.0,
        "y_inf1": 3.02,
        "y_inf2": 1.82,
        "y_total": 0.9,
        "y_sup": 22.2,
        "x_izq1": -3.79,
        "x_izq2": -5.0,
        "x_total": -6.2,
        "x_der": 8.2,
    },
    "PA": {
        "x_ejes": [15.0, 18.0, 19.4, 21.2, 23.0],
        "y_ejes": [4.0, 9.5, 11.6, 12.5, 14.25, 17.25, 21.0],
        "salas_x": [(15.0, 19.4), (19.4, 23.0)],
        "salas_y": [(4.0, 9.5), (9.5, 14.25), (14.25, 21.0)],
        "ref_inf": 4.0,
        "ref_sup": 21.0,
        "ref_izq": 15.0,
        "ref_der": 23.0,
        "y_inf1": 3.02,
        "y_inf2": 1.82,
        "y_total": 0.9,
        "y_sup": 22.2,
        "x_izq1": 12.2,
        "x_izq2": 11.0,
        "x_total": 10.0,
        "x_der": 24.4,
    },
}


def dim(
    ms: Any,
    p1: tuple[float, float],
    p2: tuple[float, float],
    linea: tuple[float, float],
    rot: float,
) -> Any:
    d = ms.AddDimRotated(variant_point(*p1), variant_point(*p2), variant_point(*linea), rot)
    try:
        d.Layer = "A-COTAS"
        d.StyleName = "MCP-ARQ"
    except Exception:  # noqa: BLE001
        pass
    return d


def cadena_h(ms: Any, xs: list[float], y_ref: float, y_dim: float) -> int:
    n = 0
    for a, b in zip(xs, xs[1:], strict=False):
        dim(ms, (a, y_ref), (b, y_ref), ((a + b) / 2, y_dim), ROT_H)
        n += 1
    return n


def cadena_v(ms: Any, ys: list[float], x_ref: float, x_dim: float) -> int:
    n = 0
    for a, b in zip(ys, ys[1:], strict=False):
        dim(ms, (x_ref, a), (x_ref, b), (x_dim, (a + b) / 2), ROT_V)
        n += 1
    return n


def main() -> int:
    pythoncom.CoInitialize()
    app = win32com.client.GetActiveObject("AutoCAD.Application.25.1")
    doc = app.ActiveDocument
    doc.Activate()
    for _ in range(20):
        try:
            doc.ActiveLayout = doc.Layouts.Item("Model")
            doc.ActiveSpace = 0
            doc.SetVariable("CTAB", "Model")
            time.sleep(0.6)
            break
        except Exception:  # noqa: BLE001
            time.sleep(0.6)
    ms = doc.ModelSpace

    # 1. borrar cotas existentes (se recrean identicas + las nuevas)
    borradas = 0
    for i in range(int(ms.Count) - 1, -1, -1):
        e = ms.Item(i)
        try:
            if str(e.Layer) == "A-COTAS" and "Dimension" in str(e.ObjectName):
                e.Delete()
                borradas += 1
        except Exception:  # noqa: BLE001
            pass
    print("cotas anteriores borradas:", borradas)

    creadas = 0
    for nombre, p in PLANTAS.items():
        xe, ye = p["x_ejes"], p["y_ejes"]
        # inferiores: cadena de ejes + cadena de salas + total
        creadas += cadena_h(ms, xe, p["ref_inf"], p["y_inf1"])
        for a, b in p["salas_x"]:
            dim(ms, (a, p["ref_inf"]), (b, p["ref_inf"]), ((a + b) / 2, p["y_inf2"]), ROT_H)
            creadas += 1
        dim(
            ms,
            (xe[0], p["ref_inf"]),
            (xe[-1], p["ref_inf"]),
            ((xe[0] + xe[-1]) / 2, p["y_total"]),
            ROT_H,
        )
        creadas += 1
        # superiores: cadena de ejes
        creadas += cadena_h(ms, xe, p["ref_sup"], p["y_sup"])
        # izquierdas: cadena de ejes + salas + total
        creadas += cadena_v(ms, ye, p["ref_izq"], p["x_izq1"])
        for a, b in p["salas_y"]:
            dim(ms, (p["ref_izq"], a), (p["ref_izq"], b), (p["x_izq2"], (a + b) / 2), ROT_V)
            creadas += 1
        dim(
            ms,
            (p["ref_izq"], ye[0]),
            (p["ref_izq"], ye[-1]),
            (p["x_total"], (ye[0] + ye[-1]) / 2),
            ROT_V,
        )
        creadas += 1
        # derechas: cadena de ejes
        creadas += cadena_v(ms, ye, p["ref_der"], p["x_der"])
        print(f"{nombre}: cotas listas")

    for _ in range(10):
        try:
            doc.Regen(1)
            doc.Save()
            break
        except Exception:  # noqa: BLE001
            time.sleep(1.0)
    print("cotas creadas:", creadas)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
