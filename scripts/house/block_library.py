"""Biblioteca de objetos de alto diseno para la vivienda UCV.

- Define bloques en el DWG de plantas, pero NO inserta ninguno en el modelo.
- Crea una hoja aparte ("BIBLIOTECA") para revisarlos sin ensuciar el plano.
- Los bloques quedan disponibles con INSERT para aplicarlos cuando se aprueben.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "house"))

from autocad_mcp.com import as_dynamic, variant_point  # noqa: E402
from autocad_mcp.service import AutoCADService  # noqa: E402

OUT = ROOT / "out" / "Vivienda_UCV_Magisterial_230_PLANTAS.dwg"
BASE = (100.0, 0.0)
MOB = "A-MOBILIARIO"
SAN = "A-SANITARIO"
ELE = "A-ELECTRO"
VEG = "A-VEGETACION"
PV = "A-PUER-VENT"


def _h(res: dict) -> str:
    if not res.get("success"):
        raise RuntimeError(f"Entidad no creada: {res}")
    return res.get("handle") or res["handles"][0]


def _pt(x: float, y: float) -> list[float]:
    return [round(BASE[0] + x, 3), round(BASE[1] + y, 3)]


def _line(s, x0, y0, x1, y1, layer):
    s.layer_tools.set_current_layer(layer)
    return _h(s.geometry.create_line(_pt(x0, y0), _pt(x1, y1), "bylayer"))


def _rect(s, x0, y0, x1, y1, layer):
    s.layer_tools.set_current_layer(layer)
    return _h(s.geometry.create_rectangle(_pt(x0, y0), _pt(x1, y1), "bylayer"))


def _circle(s, x, y, r, layer):
    s.layer_tools.set_current_layer(layer)
    return _h(s.geometry.create_circle(_pt(x, y), r, "bylayer"))


def _arc(s, x, y, r, a0, a1, layer):
    s.layer_tools.set_current_layer(layer)
    res = s.geometry.create_arc(_pt(x, y), r, a0, a1, "bylayer")
    return _h(res)


def _poly(s, pts, layer, closed=True):
    s.layer_tools.set_current_layer(layer)
    res = s.geometry.create_polyline([_pt(x, y) for x, y in pts], closed=closed, color="bylayer")
    return _h(res)


def _block(svc, name: str, draw) -> None:
    # Los dibujos usan un servicio global para no repetir el parametro en
    # cada primitiva; se declaran como fabricas para crear entidades nuevas.
    global s
    s = svc
    # Acepta tanto una fabrica de dibujo (_sofa) como un dibujo ya resuelto
    # (_door(0.80)); en ambos casos se crean entidades nuevas por corrida.
    built = draw()
    handles = built() if callable(built) else built
    res = svc.blocks.create_block(
        name, handles, base_point=[BASE[0], BASE[1], 0.0], delete_source=True
    )
    if not res.get("success"):
        for h in handles:
            try:
                svc.deleter.delete_entity(h)
            except Exception:  # noqa: BLE001
                pass
        raise RuntimeError(f"No se pudo crear {name}: {res}")


# --- objetos civiles / mobiliario -------------------------------------------
def _sofa():
    def d():
        hs = [
            # bastidor y respaldo
            _rect(s, 0.00, 0.00, 2.60, 1.00, MOB),
            _rect(s, 0.00, 0.78, 2.60, 1.00, MOB),
            _line(s, 0.00, 0.78, 2.60, 0.78, MOB),
            # brazos
            _rect(s, 0.00, 0.10, 0.22, 0.78, MOB),
            _rect(s, 2.38, 0.10, 2.60, 0.78, MOB),
            # tres cojines de asiento con pliegue
            _rect(s, 0.24, 0.10, 1.00, 0.74, MOB),
            _rect(s, 1.02, 0.10, 1.58, 0.74, MOB),
            _rect(s, 1.60, 0.10, 2.36, 0.74, MOB),
            _line(s, 0.30, 0.14, 0.30, 0.70, MOB),
            _line(s, 0.94, 0.14, 0.94, 0.70, MOB),
            _line(s, 1.08, 0.14, 1.08, 0.70, MOB),
            _line(s, 1.52, 0.14, 1.52, 0.70, MOB),
            _line(s, 1.66, 0.14, 1.66, 0.70, MOB),
            _line(s, 2.30, 0.14, 2.30, 0.70, MOB),
            # almohadones decorativos
            _poly(s, [(0.30, 0.80), (0.55, 0.66), (0.80, 0.80), (0.55, 0.94)], MOB),
            _poly(s, [(1.80, 0.80), (2.05, 0.66), (2.30, 0.80), (2.05, 0.94)], MOB),
            # patas
            _circle(s, 0.12, 0.05, 0.03, MOB),
            _circle(s, 1.30, 0.05, 0.03, MOB),
            _circle(s, 2.48, 0.05, 0.03, MOB),
        ]
        return hs

    return d


def _armchair():
    def d():
        return [
            _rect(s, 0.00, 0.00, 0.90, 0.90, MOB),
            _rect(s, 0.00, 0.68, 0.90, 0.90, MOB),
            _rect(s, 0.00, 0.10, 0.16, 0.68, MOB),
            _rect(s, 0.74, 0.10, 0.90, 0.68, MOB),
            _rect(s, 0.16, 0.10, 0.74, 0.66, MOB),
            _line(s, 0.16, 0.64, 0.74, 0.64, MOB),
            _line(s, 0.21, 0.14, 0.21, 0.62, MOB),
            _line(s, 0.69, 0.14, 0.69, 0.62, MOB),
            _poly(s, [(0.26, 0.70), (0.45, 0.60), (0.64, 0.70), (0.45, 0.80)], MOB),
            _circle(s, 0.10, 0.05, 0.03, MOB),
            _circle(s, 0.80, 0.05, 0.03, MOB),
        ]

    return d


def _coffee():
    def d():
        outer = [
            (0.06, 0),
            (1.14, 0),
            (1.20, 0.06),
            (1.20, 0.54),
            (1.14, 0.60),
            (0.06, 0.60),
            (0, 0.54),
            (0, 0.06),
        ]
        return [
            _poly(s, outer, MOB),
            _rect(s, 0.08, 0.08, 1.12, 0.52, MOB),
            # bandeja y revistas
            _rect(s, 0.16, 0.20, 0.55, 0.40, MOB),
            _line(s, 0.66, 0.22, 1.02, 0.22, MOB),
            _line(s, 0.66, 0.30, 0.96, 0.30, MOB),
            _line(s, 0.66, 0.38, 1.02, 0.38, MOB),
            _circle(s, 0.35, 0.30, 0.04, MOB),
        ]

    return d


def _rug():
    def d():
        hs = [
            _rect(s, 0, 0, 2.40, 1.60, MOB),
            _rect(s, 0.10, 0.10, 2.30, 1.50, MOB),
            _poly(s, [(1.20, 0.10), (2.30, 0.80), (1.20, 1.50), (0.10, 0.80)], MOB),
            _poly(s, [(1.20, 0.30), (1.90, 0.80), (1.20, 1.30), (0.50, 0.80)], MOB),
        ]
        # flecos en los extremos cortos
        for y in (0.05, 0.25, 0.45, 0.65, 0.85, 1.05, 1.25, 1.45):
            hs.append(_line(s, -0.06, y, 0.00, y, MOB))
            hs.append(_line(s, 2.40, y, 2.46, y, MOB))
        return hs

    return d


def _tv():
    def d():
        return [
            _rect(s, 0, 0, 1.80, 0.42, MOB),
            _line(s, 0, 0.34, 1.80, 0.34, MOB),
            _rect(s, 0.20, 0.42, 1.60, 0.56, ELE),
            _rect(s, 0.24, 0.45, 1.56, 0.53, ELE),
            _line(s, 0.34, 0.17, 1.46, 0.17, MOB),
            _rect(s, 0.08, 0.06, 0.28, 0.28, ELE),
            _circle(s, 0.18, 0.17, 0.05, ELE),
            _rect(s, 1.52, 0.06, 1.72, 0.28, ELE),
            _circle(s, 1.62, 0.17, 0.05, ELE),
            _line(s, 0.72, 0.42, 0.72, 0.56, ELE),
            _line(s, 1.08, 0.42, 1.08, 0.56, ELE),
        ]

    return d


def _dining():
    def d():
        hs = [
            # tablero y mantel
            _rect(s, 0.40, 0.50, 2.00, 1.30, MOB),
            _rect(s, 0.46, 0.56, 1.94, 1.24, MOB),
            _line(s, 1.20, 0.56, 1.20, 1.24, MOB),
            _circle(s, 1.20, 0.90, 0.12, MOB),
            _circle(s, 1.20, 0.90, 0.06, MOB),
        ]
        # seis sillas: respaldo + asiento + patas
        for x0, y0, back in (
            (0.55, 1.30, "n"),
            (1.30, 1.30, "n"),
            (0.55, 0.05, "s"),
            (1.30, 0.05, "s"),
            (0.00, 0.68, "w"),
            (1.95, 0.68, "e"),
        ):
            hs.append(_rect(s, x0, y0, x0 + 0.45, y0 + 0.45, MOB))
            if back == "n":
                hs.append(_line(s, x0, y0 + 0.45, x0 + 0.45, y0 + 0.45, MOB))
            elif back == "s":
                hs.append(_line(s, x0, y0, x0 + 0.45, y0, MOB))
            elif back == "w":
                hs.append(_line(s, x0, y0, x0, y0 + 0.45, MOB))
            else:
                hs.append(_line(s, x0 + 0.45, y0, x0 + 0.45, y0 + 0.45, MOB))
            # puesto de mesa
            hs.append(_circle(s, x0 + 0.225, y0 + 0.225, 0.07, MOB))
        return hs

    return d


def _island():
    def d():
        hs = [
            # tablero y zócalo
            _rect(s, 0, 0, 2.40, 0.90, ELE),
            _rect(s, 0.05, 0.05, 2.35, 0.85, ELE),
            # lavabo con grifería
            _rect(s, 0.18, 0.44, 0.86, 0.80, SAN),
            _circle(s, 0.52, 0.62, 0.13, SAN),
            _circle(s, 0.52, 0.62, 0.025, SAN),
            _line(s, 0.52, 0.75, 0.52, 0.82, SAN),
            _arc(s, 0.52, 0.82, 0.07, 0, 180, SAN),
            # anafe de cuatro hornillas
            _rect(s, 1.34, 0.16, 2.16, 0.76, MOB),
            _circle(s, 1.52, 0.32, 0.09, MOB),
            _circle(s, 1.52, 0.60, 0.09, MOB),
            _circle(s, 1.94, 0.32, 0.09, MOB),
            _circle(s, 1.94, 0.60, 0.09, MOB),
            _line(s, 1.34, 0.46, 2.16, 0.46, MOB),
            # alacena inferior
            _line(s, 1.02, 0.05, 1.02, 0.85, ELE),
            _line(s, 1.10, 0.05, 1.10, 0.85, ELE),
            _circle(s, 1.06, 0.45, 0.015, ELE),
        ]
        return hs

    return d


def _island_180():
    def d():
        return [
            # tablero y zocalo
            _rect(s, 0, 0, 1.80, 0.90, ELE),
            _rect(s, 0.05, 0.05, 1.75, 0.85, ELE),
            # lavabo con griferia
            _rect(s, 0.14, 0.44, 0.72, 0.80, SAN),
            _circle(s, 0.43, 0.62, 0.12, SAN),
            _circle(s, 0.43, 0.62, 0.025, SAN),
            _line(s, 0.43, 0.75, 0.43, 0.82, SAN),
            _arc(s, 0.43, 0.82, 0.07, 0, 180, SAN),
            # anafe de cuatro hornillas
            _rect(s, 0.98, 0.16, 1.66, 0.76, MOB),
            _circle(s, 1.13, 0.32, 0.08, MOB),
            _circle(s, 1.13, 0.60, 0.08, MOB),
            _circle(s, 1.51, 0.32, 0.08, MOB),
            _circle(s, 1.51, 0.60, 0.08, MOB),
            _line(s, 0.98, 0.46, 1.66, 0.46, MOB),
            # alacena inferior
            _line(s, 0.80, 0.05, 0.80, 0.85, ELE),
            _line(s, 0.88, 0.05, 0.88, 0.85, ELE),
            _circle(s, 0.84, 0.45, 0.015, ELE),
        ]

    return d


def _queen():
    def d():
        hs = [
            # cabecero y base
            _rect(s, 0.00, 1.96, 1.80, 2.14, MOB),
            _rect(s, 0.06, 0.00, 1.74, 1.96, MOB),
            _rect(s, 0.14, 0.06, 1.66, 1.90, MOB),
            # almohadas
            _rect(s, 0.22, 1.58, 0.84, 1.88, MOB),
            _rect(s, 0.96, 1.58, 1.58, 1.88, MOB),
            _line(s, 0.53, 1.58, 0.53, 1.88, MOB),
            _line(s, 1.27, 1.58, 1.27, 1.88, MOB),
            # cobertor y pliegue
            _line(s, 0.14, 0.95, 1.66, 0.95, MOB),
            _line(s, 0.14, 0.62, 1.66, 0.62, MOB),
            _line(s, 0.90, 0.06, 0.90, 0.62, MOB),
            # mesa de noche
            _rect(s, 1.82, 1.50, 2.26, 1.94, MOB),
            _circle(s, 2.04, 1.72, 0.05, ELE),
            _rect(s, 2.34, 1.50, 2.78, 1.94, MOB),
            _circle(s, 2.56, 1.72, 0.05, ELE),
        ]
        return hs

    return d


def _single():
    def d():
        return [
            _rect(s, 0.00, 1.92, 1.05, 2.08, MOB),
            _rect(s, 0.05, 0.00, 1.00, 1.92, MOB),
            _rect(s, 0.11, 0.05, 0.94, 1.87, MOB),
            _rect(s, 0.16, 1.55, 0.89, 1.84, MOB),
            _line(s, 0.52, 1.55, 0.52, 1.84, MOB),
            _line(s, 0.11, 0.88, 0.94, 0.88, MOB),
            _line(s, 0.11, 0.58, 0.94, 0.58, MOB),
            _line(s, 0.52, 0.05, 0.52, 0.58, MOB),
        ]

    return d


def _wardrobe():
    def d():
        hs = [
            _rect(s, 0, 0, 2.40, 0.60, MOB),
            _line(s, 0, 0.12, 2.40, 0.12, MOB),
            # tres puertas correderas
            _line(s, 0.80, 0.00, 0.80, 0.60, MOB),
            _line(s, 1.60, 0.00, 1.60, 0.60, MOB),
            _line(s, 0.78, 0.00, 0.78, 0.60, MOB),
            _line(s, 1.62, 0.00, 1.62, 0.60, MOB),
            _line(s, 0.06, 0.52, 2.34, 0.52, MOB),
        ]
        hs.extend(_circle(s, x, 0.32, 0.02, MOB) for x in (0.77, 1.59))
        # cajones y tiradores
        hs.extend(
            [
                _rect(s, 0.10, 0.02, 0.30, 0.10, MOB),
                _rect(s, 2.10, 0.02, 2.30, 0.10, MOB),
            ]
        )
        return hs

    return d


def _desk():
    def d():
        return [
            _rect(s, 0.00, 0.42, 1.40, 1.12, MOB),
            _rect(s, 0.06, 0.48, 1.34, 1.06, MOB),
            # cajonera
            _rect(s, 1.02, 0.48, 1.34, 1.06, MOB),
            _line(s, 1.02, 0.70, 1.34, 0.70, MOB),
            _line(s, 1.02, 0.88, 1.34, 0.88, MOB),
            _circle(s, 1.18, 0.59, 0.015, MOB),
            _circle(s, 1.18, 0.79, 0.015, MOB),
            _circle(s, 1.18, 0.97, 0.015, MOB),
            # silla
            _circle(s, 0.42, 0.20, 0.21, MOB),
            _circle(s, 0.42, 0.20, 0.16, MOB),
            _rect(s, 0.16, 0.00, 0.68, 0.06, MOB),
            _line(s, 0.20, 0.20, 0.64, 0.20, MOB),
            # monitor y lámpara
            _rect(s, 0.20, 0.86, 0.72, 1.02, ELE),
            _line(s, 0.46, 0.86, 0.46, 0.78, ELE),
            _line(s, 0.36, 0.78, 0.56, 0.78, ELE),
            _circle(s, 0.86, 0.96, 0.06, ELE),
            _line(s, 0.86, 0.96, 0.86, 1.08, ELE),
        ]

    return d


def _side_table():
    def d():
        return [
            _circle(s, 0.30, 0.30, 0.30, MOB),
            _circle(s, 0.30, 0.30, 0.25, MOB),
            _circle(s, 0.30, 0.30, 0.04, MOB),
            _line(s, 0.12, 0.30, 0.48, 0.30, MOB),
            _line(s, 0.30, 0.12, 0.30, 0.48, MOB),
        ]

    return d


# --- sanitarios --------------------------------------------------------------
def _toilet():
    def d():
        return [
            # tanque y descarga
            _rect(s, 0.02, 0.50, 0.38, 0.70, SAN),
            _rect(s, 0.06, 0.54, 0.34, 0.66, SAN),
            _circle(s, 0.20, 0.60, 0.025, SAN),
            # taza
            _circle(s, 0.20, 0.28, 0.20, SAN),
            _circle(s, 0.20, 0.28, 0.15, SAN),
            _line(s, 0.20, 0.48, 0.20, 0.44, SAN),
            _line(s, 0.06, 0.28, 0.34, 0.28, SAN),
            # bisagra
            _circle(s, 0.12, 0.47, 0.012, SAN),
            _circle(s, 0.28, 0.47, 0.012, SAN),
        ]

    return d


def _vanity():
    def d():
        return [
            _rect(s, 0, 0, 1.00, 0.50, SAN),
            _rect(s, 0.05, 0.05, 0.95, 0.45, SAN),
            # lavabo
            _circle(s, 0.50, 0.25, 0.17, SAN),
            _circle(s, 0.50, 0.25, 0.035, SAN),
            _line(s, 0.50, 0.42, 0.50, 0.48, SAN),
            _arc(s, 0.50, 0.48, 0.06, 0, 180, SAN),
            # jabonera y toalla
            _rect(s, 0.10, 0.10, 0.22, 0.20, SAN),
            _line(s, 0.78, 0.08, 0.94, 0.08, SAN),
            _line(s, 0.78, 0.13, 0.94, 0.13, SAN),
        ]

    return d


def _shower():
    def d():
        return [
            # plato de ducha
            _rect(s, 0, 0, 1.20, 0.90, SAN),
            _rect(s, 0.05, 0.05, 1.15, 0.85, SAN),
            # mampara y puerta
            _line(s, 0.00, 0.90, 0.90, 0.90, SAN),
            _line(s, 0.90, 0.90, 0.90, 0.00, SAN),
            _line(s, 1.14, 0.00, 1.14, 0.90, SAN),
            _arc(s, 0.90, 0.00, 0.22, 0, 90, SAN),
            # ducha y desague
            _circle(s, 0.18, 0.16, 0.06, SAN),
            _line(s, 0.18, 0.16, 0.36, 0.34, SAN),
            _circle(s, 0.36, 0.34, 0.045, SAN),
            _rect(s, 0.96, 0.78, 1.06, 0.86, SAN),
            _line(s, 0.98, 0.82, 1.04, 0.82, SAN),
            _line(s, 0.98, 0.79, 1.04, 0.79, SAN),
        ]

    return d


def _tub():
    def d():
        return [
            _rect(s, 0, 0, 1.70, 0.80, SAN),
            _poly(s, [(0.08, 0.08), (1.62, 0.08), (1.62, 0.72), (0.08, 0.72)], SAN),
            _line(s, 0.08, 0.16, 1.62, 0.16, SAN),
            _circle(s, 1.42, 0.44, 0.045, SAN),
            _line(s, 1.42, 0.48, 1.42, 0.56, SAN),
            _arc(s, 1.42, 0.56, 0.06, 0, 180, SAN),
            _line(s, 0.20, 0.74, 0.20, 0.62, SAN),
            _line(s, 0.20, 0.62, 0.40, 0.62, SAN),
            _line(s, 0.30, 0.08, 0.30, 0.16, SAN),
        ]

    return d


def _utility():
    def d():
        return [
            _rect(s, 0, 0, 0.60, 0.55, SAN),
            _rect(s, 0.05, 0.05, 0.55, 0.50, SAN),
            _rect(s, 0.12, 0.12, 0.40, 0.42, SAN),
            _circle(s, 0.26, 0.27, 0.10, SAN),
            _circle(s, 0.26, 0.27, 0.02, SAN),
            _line(s, 0.26, 0.42, 0.26, 0.48, SAN),
            _arc(s, 0.26, 0.48, 0.05, 0, 180, SAN),
            # escurridor
            _line(s, 0.44, 0.10, 0.44, 0.45, SAN),
            _line(s, 0.48, 0.10, 0.48, 0.45, SAN),
            _line(s, 0.52, 0.10, 0.52, 0.45, SAN),
        ]

    return d


def _plant():
    def d():
        return [
            # maceta
            _circle(s, 0.35, 0.35, 0.16, VEG),
            _circle(s, 0.35, 0.35, 0.12, VEG),
            # hojas
            _arc(s, 0.35, 0.35, 0.32, 20, 160, VEG),
            _arc(s, 0.35, 0.35, 0.27, 200, 340, VEG),
            _arc(s, 0.35, 0.35, 0.23, 80, 220, VEG),
            _arc(s, 0.35, 0.35, 0.18, 260, 400, VEG),
            _line(s, 0.35, 0.20, 0.35, 0.52, VEG),
            _line(s, 0.22, 0.30, 0.35, 0.38, VEG),
            _line(s, 0.48, 0.30, 0.35, 0.38, VEG),
        ]

    return d


def _bookshelf():
    """Librero de 2.00 x 0.35 con cuatro módulos y libros vistos en planta."""

    def d():
        hs = [
            _rect(s, 0.00, 0.00, 2.00, 0.35, MOB),
            _line(s, 0.00, 0.055, 2.00, 0.055, MOB),
            _line(s, 0.00, 0.300, 2.00, 0.300, MOB),
        ]
        hs.extend(_line(s, x, 0.055, x, 0.300, MOB) for x in (0.50, 1.00, 1.50))
        # Grupos de libros con espacios libres para que se lea a 1:100.
        for bx in (0.08, 0.58, 1.08, 1.58):
            hs.append(_rect(s, bx, 0.095, bx + 0.20, 0.265, MOB))
            hs.append(_line(s, bx + 0.10, 0.095, bx + 0.10, 0.265, MOB))
            hs.append(_rect(s, bx + 0.24, 0.095, bx + 0.34, 0.235, MOB))
        return hs

    return d


def _refrigerator():
    def d():
        return [
            _rect(s, 0, 0, 0.70, 0.90, ELE),
            _rect(s, 0.05, 0.05, 0.65, 0.85, ELE),
            _line(s, 0.05, 0.45, 0.65, 0.45, ELE),
            _circle(s, 0.35, 0.22, 0.03, ELE),
            _circle(s, 0.35, 0.68, 0.03, ELE),
        ]

    return d


def _sink():
    def d():
        return [
            _rect(s, 0, 0, 0.60, 0.60, SAN),
            _circle(s, 0.30, 0.32, 0.22, SAN),
            _rect(s, 0.22, 0.24, 0.38, 0.30, SAN),
            _line(s, 0.30, 0.54, 0.30, 0.60, SAN),
        ]

    return d


def _microwave():
    def d():
        return [
            _rect(s, 0, 0, 0.55, 0.40, ELE),
            _rect(s, 0.05, 0.05, 0.50, 0.35, ELE),
            _circle(s, 0.43, 0.20, 0.08, ELE),
            _line(s, 0.05, 0.20, 0.35, 0.20, ELE),
        ]

    return d


def _washer():
    def d():
        return [
            _rect(s, 0, 0, 0.60, 0.60, SAN),
            _circle(s, 0.30, 0.32, 0.22, SAN),
            _circle(s, 0.30, 0.32, 0.04, SAN),
            _rect(s, 0.12, 0.52, 0.48, 0.56, SAN),
        ]

    return d


def _garden_plant():
    def d():
        return [
            _circle(s, 0.40, 0.40, 0.35, VEG),
            _circle(s, 0.40, 0.40, 0.18, VEG),
            _rect(s, 0.36, 0.00, 0.44, 0.20, VEG),
            _line(s, 0.40, 0.20, 0.40, 0.40, VEG),
        ]

    return d


def _car():
    """Automovil compacto en planta (4.50 x 1.80 m).

    Origen en la esquina posterior izquierda. Incluye carroceria, techo,
    lunas, puertas, ruedas, espejos, faros y pilotos.
    """

    def d():
        return [
            # Carroceria: maletero, techo, capo y paragolpes.
            _poly(
                s,
                [
                    (0.00, 0.40),
                    (0.00, 1.40),
                    (0.28, 1.60),
                    (3.52, 1.60),
                    (4.04, 1.46),
                    (4.50, 1.14),
                    (4.50, 0.66),
                    (4.04, 0.34),
                    (3.52, 0.20),
                    (0.28, 0.20),
                ],
                MOB,
            ),
            # Techo y lunas delanteras/traseras.
            _poly(s, [(1.35, 0.36), (2.88, 0.36), (2.88, 1.44), (1.35, 1.44)], MOB),
            _line(s, 2.88, 0.36, 3.34, 0.24, MOB),
            _line(s, 2.88, 1.44, 3.34, 1.56, MOB),
            _line(s, 3.34, 0.24, 3.34, 1.56, MOB),
            _line(s, 1.35, 0.36, 1.00, 0.26, MOB),
            _line(s, 1.35, 1.44, 1.00, 1.54, MOB),
            _line(s, 1.00, 0.26, 1.00, 1.54, MOB),
            # Puertas y manijas.
            _line(s, 2.10, 0.20, 2.10, 0.36, MOB),
            _line(s, 2.10, 1.44, 2.10, 1.60, MOB),
            _rect(s, 1.90, 0.26, 2.04, 0.32, MOB),
            _rect(s, 1.90, 1.48, 2.04, 1.54, MOB),
            # Ruedas con banda de rodadura.
            _rect(s, 0.68, 0.00, 1.10, 0.26, MOB),
            _rect(s, 3.40, 0.00, 3.82, 0.26, MOB),
            _rect(s, 0.68, 1.54, 1.10, 1.80, MOB),
            _rect(s, 3.40, 1.54, 3.82, 1.80, MOB),
            _line(s, 0.70, 0.08, 1.08, 0.08, MOB),
            _line(s, 3.42, 0.08, 3.80, 0.08, MOB),
            _line(s, 0.70, 1.72, 1.08, 1.72, MOB),
            _line(s, 3.42, 1.72, 3.80, 1.72, MOB),
            # Espejos laterales.
            _poly(s, [(2.95, 0.20), (3.12, 0.20), (3.06, 0.04)], MOB),
            _poly(s, [(2.95, 1.60), (3.12, 1.60), (3.06, 1.76)], MOB),
            # Faros delanteros y pilotos traseros.
            _rect(s, 4.36, 0.42, 4.48, 0.62, ELE),
            _rect(s, 4.36, 1.18, 4.48, 1.38, ELE),
            _rect(s, 0.00, 0.42, 0.10, 0.62, ELE),
            _rect(s, 0.00, 1.18, 0.10, 1.38, ELE),
            # Parrilla y paragolpes.
            _line(s, 4.46, 0.70, 4.46, 1.10, MOB),
            _line(s, 4.50, 0.66, 4.50, 1.14, MOB),
            _line(s, 0.00, 0.66, 0.00, 1.14, MOB),
        ]

    return d


def _north_symbol():
    """Simbolo de norte profesional: circulo, rosa de agujas y letra N."""
    cx, cy = BASE

    def d():
        hs = [
            _circle(s, 0.0, 0.0, 0.62, "A-EJES"),
            _circle(s, 0.0, 0.0, 0.55, "A-EJES"),
            # Ejes cardinales y marcas.
            _line(s, 0.0, -0.78, 0.0, 0.78, "A-EJES"),
            _line(s, -0.78, 0.0, 0.78, 0.0, "A-EJES"),
            _line(s, -0.08, 0.78, 0.08, 0.78, "A-EJES"),
            # Aguja principal.
            _poly(s, [(0.0, 0.50), (-0.13, 0.02), (0.0, -0.08), (0.13, 0.02)], "A-EJES"),
            _line(s, 0.0, -0.08, 0.0, -0.48, "A-EJES"),
            _line(s, -0.07, -0.38, 0.0, -0.48, "A-EJES"),
            _line(s, 0.07, -0.38, 0.0, -0.48, "A-EJES"),
            _circle(s, 0.0, 0.0, 0.035, "A-EJES"),
        ]
        # Letra N sobre el circulo.
        s.layer_tools.set_current_layer("A-TEXTOS")
        res = s.geometry.create_text([round(cx - 0.075, 3), round(cy + 0.64, 3)], "N", 0.20)
        if res.get("success"):
            hs.append(res.get("handle") or res["handles"][0])
        return hs

    return d


def _door(width: float, exterior: bool = False):
    """Puerta de una hoja: bisagra en el origen, hoja abierta a 90 grados (+Y).

    La hoja cerrada queda sobre +X (el vano); el arco barre 90 grados. Asi el
    mismo bloque sirve para cualquier muro girandolo con la referencia.
    """

    def d():
        w = width
        hs = [
            # marcos del vano (espesor de muro 0.15)
            _rect(s, 0.00, -0.075, 0.045, 0.075, PV),
            _rect(s, w - 0.045, -0.075, w, 0.075, PV),
            _line(s, 0.045, 0.075, 0.045, -0.075, PV),
            _line(s, w - 0.045, 0.075, w - 0.045, -0.075, PV),
            # hoja abierta (grosor 0.04)
            _rect(s, 0.02, 0.02, 0.06, w - 0.02, PV),
            _line(s, 0.045, 0.10, 0.045, w - 0.10, PV),
            # barrido de la hoja
            _arc(s, 0.00, 0.00, w - 0.02, 0, 90, PV),
            _circle(s, 0.00, 0.00, 0.025, PV),
            # manija
            _circle(s, 0.085, w - 0.14, 0.018, PV),
        ]
        if exterior:
            # umbral y refuerzo de hoja
            _line(s, 0.00, 0.00, w, 0.00, PV)
            _line(s, 0.02, w * 0.55, 0.06, w * 0.55, PV)
            _line(s, 0.02, w * 0.80, 0.06, w * 0.80, PV)
        return hs

    return d


def _sliding_door(width: float = 2.00):
    """Corredera de dos hojas superpuestas, con riel y tiradores."""

    def d():
        w = width
        leaf = w * 0.52
        return [
            # rieles
            _line(s, 0.00, -0.05, w, -0.05, PV),
            _line(s, 0.00, 0.05, w, 0.05, PV),
            # hoja exterior
            _rect(s, 0.01, -0.035, leaf, -0.005, PV),
            _line(s, 0.07, -0.020, leaf - 0.06, -0.020, PV),
            # hoja interior
            _rect(s, w - leaf, 0.005, w - 0.01, 0.035, PV),
            _line(s, w - leaf + 0.06, 0.020, w - 0.07, 0.020, PV),
            # topes y tiradores
            _circle(s, 0.10, 0.00, 0.018, PV),
            _circle(s, w - 0.10, 0.00, 0.018, PV),
            _rect(s, leaf - 0.10, -0.035, leaf - 0.05, -0.005, PV),
            _rect(s, w - leaf + 0.05, 0.005, w - leaf + 0.10, 0.035, PV),
        ]

    return d


LIBRARY = [
    ("OBJ-SOFA-MOD-260", "SOFA 3 CUERPOS 2.60 x 1.00", _sofa),
    ("OBJ-SILLA-LOUNGE", "SILLA LOUNGE 0.90 x 0.90", _armchair),
    ("OBJ-MESA-CENTRO-120", "MESA DE CENTRO 1.20 x 0.60", _coffee),
    ("OBJ-ALFOMBRA-240", "ALFOMBRA 2.40 x 1.60", _rug),
    ("OBJ-TV-180", "MUEBLE TV 1.80 x 0.56", _tv),
    ("OBJ-COMEDOR-6P", "COMEDOR 6 PERSONAS 2.40 x 1.80", _dining),
    ("OBJ-MESA-LATERAL-060", "MESA LATERAL 0.60", _side_table),
    ("OBJ-ISLA-COCINA-240", "ISLA DE COCINA 2.40 x 0.90", _island),
    ("OBJ-ISLA-COCINA-180", "ISLA DE COCINA 1.80 x 0.90", _island_180),
    ("OBJ-CAMA-QUEEN", "CAMA QUEEN 1.80 x 2.14", _queen),
    ("OBJ-CAMA-SINGLE", "CAMA SINGLE 1.15 x 2.08", _single),
    ("OBJ-ROPERO-240", "ROPERO 2.40 x 0.60", _wardrobe),
    ("OBJ-ESCRITORIO-140", "ESCRITORIO 1.40 x 1.12", _desk),
    ("OBJ-INODORO-SUSP", "INODORO 0.40 x 0.70", _toilet),
    ("OBJ-LAVAMANOS-100", "LAVAMANOS 1.00 x 0.50", _vanity),
    ("OBJ-DUCHA-WALKIN", "DUCHA WALK-IN 1.20 x 0.90", _shower),
    ("OBJ-TINA-FREESTANDING", "TINA 1.70 x 0.80", _tub),
    ("OBJ-LAVADERO-UTIL", "LAVADERO 0.60 x 0.55", _utility),
    ("OBJ-PLANTA-INTERIOR", "PLANTA INTERIOR 0.70", _plant),
    ("OBJ-LIBRERO-200", "LIBRERO 2.00 x 0.35", _bookshelf),
    ("OBJ-REFRI-090", "REFRIGERADOR 0.90 x 0.70", _refrigerator),
    ("OBJ-LAVAPLATOS-060", "FREGADERO 0.60 x 0.60", _sink),
    ("OBJ-MICROONDAS-060", "MICROONDAS 0.55 x 0.40", _microwave),
    ("OBJ-LAVADORA-060", "LAVADORA 0.60 x 0.60", _washer),
    ("OBJ-PLANTA-JARDIN", "PLANTA DE JARDIN 0.80", _garden_plant),
    ("OBJ-AUTO-450", "AUTOMOVIL 4.50 x 1.80", _car),
    ("A-NORTE", "SIMBOLO DE NORTE 1.20", _north_symbol),
    # puertas: mismas definiciones que inserta la planta
    ("A-PUERTA-070", "PUERTA 1 HOJA 0.70", _door(0.70)),
    ("A-PUERTA-080", "PUERTA 1 HOJA 0.80", _door(0.80)),
    ("A-PUERTA-090", "PUERTA 1 HOJA 0.90", _door(0.90)),
    ("A-PUERTA-100", "PUERTA 1 HOJA 1.00", _door(1.00, exterior=True)),
    ("A-PUERTA-110", "PUERTA 1 HOJA 1.10", _door(1.10, exterior=True)),
    ("A-PUERTA-120", "PUERTA 1 HOJA 1.20", _door(1.20, exterior=True)),
    ("A-PUERTA-CORREDERA-200", "CORREDERA 2 HOJAS 2.00", _sliding_door(2.00)),
]


def _setup_layers(s) -> None:
    for lay, color in (
        (MOB, "8"),
        (SAN, "4"),
        (ELE, "30"),
        (VEG, "3"),
        (PV, "4"),
        ("A-TEXTOS", "white"),
        ("A-ROTULO", "white"),
    ):
        s.layer_tools.create_or_get_layer(lay, color, "Arquitectura")


def _define(s, only_missing: bool = False) -> None:
    existing: set[str] = set()
    if only_missing:
        blocks = s.conn.doc.Blocks
        for i in range(int(blocks.Count)):
            try:
                existing.add(str(blocks.Item(i).Name).upper())
            except Exception:  # noqa: BLE001
                pass
    for name, _label, draw in LIBRARY:
        if only_missing and name.upper() in existing:
            continue
        _block(s, name, draw)


def _paper_text(ps, text: str, x: float, y: float, height: float, layer="A-TEXTOS"):
    t = ps.AddText(str(text), variant_point(x, y), float(height))
    try:
        t.Layer = layer
    except Exception:  # noqa: BLE001
        pass
    return t


def _paper_line(ps, x0, y0, x1, y1, layer="A-ROTULO"):
    ln = ps.AddLine(variant_point(x0, y0), variant_point(x1, y1))
    try:
        ln.Layer = layer
    except Exception:  # noqa: BLE001
        pass
    return ln


def _catalog(s) -> None:
    doc = s.conn.doc
    try:
        doc.Layouts.Item("BIBLIOTECA").Delete()
    except Exception:  # noqa: BLE001
        pass
    res = s.layouts.create_layout(
        "BIBLIOTECA", media="ISO_A3_(420.00_x_297.00_MM)", plot_style_table="acad.ctb"
    )
    if not res.get("success"):
        raise RuntimeError(f"No se pudo crear BIBLIOTECA: {res}")
    s.layouts.set_active_layout("BIBLIOTECA")

    # El dispositivo por defecto puede ser PublishToWeb (pixeles). Para que
    # "420 x 297" sea milimetros reales hay que fijar primero DWG To PDF.
    pc3 = (
        Path(os.environ.get("APPDATA", ""))
        / "Autodesk"
        / "AutoCAD 2026"
        / "R25.1"
        / "enu"
        / "plotters"
        / "DWG To PDF.pc3"
    )
    if pc3.exists():
        try:
            lay = doc.Layouts.Item("BIBLIOTECA")
            lay.ConfigName = str(pc3)
            lay.CanonicalMediaName = "ISO_A3_(420.00_x_297.00_MM)"
            lay.PlotType = 5
        except Exception as exc:  # noqa: BLE001
            print("Aviso: no se pudo fijar A3:", exc, flush=True)
    ps = as_dynamic(doc.PaperSpace)

    # limpia la hoja (incluye el viewport por defecto)
    for i in range(int(ps.Count) - 1, -1, -1):
        try:
            ps.Item(i).Delete()
        except Exception:  # noqa: BLE001
            pass

    _paper_line(ps, 8, 8, 412, 8)
    _paper_line(ps, 412, 8, 412, 289)
    _paper_line(ps, 412, 289, 8, 289)
    _paper_line(ps, 8, 289, 8, 8)

    _paper_text(ps, "BIBLIOTECA DE OBJETOS - ALTO DISENO", 18, 276, 5.0, "A-ROTULO")
    _paper_text(
        ps,
        "MOBILIARIO: definiciones e inserciones en ambas plantas.",
        18,
        267,
        2.4,
    )
    _paper_text(
        ps,
        "PUERTAS: bloques por ancho (0.70 a 1.20) y corredera 2.00.",
        18,
        261,
        2.2,
    )

    cols, cell_w, cell_h = 6, 63.0, 45.0
    x0, y_top = 18.0, 252.0
    for i, (name, label, _draw) in enumerate(LIBRARY):
        col, row = i % cols, i // cols
        cx = x0 + col * cell_w
        y1 = y_top - row * cell_h
        y0 = y1 - 42.0
        _paper_line(ps, cx, y0, cx + 58, y0)
        _paper_line(ps, cx + 58, y0, cx + 58, y1)
        _paper_line(ps, cx + 58, y1, cx, y1)
        _paper_line(ps, cx, y1, cx, y0)
        try:
            ref = ps.InsertBlock(variant_point(cx + 3, y0 + 5.5), name, 13.0, 13.0, 13.0, 0.0)
            try:
                ref.Layer = MOB
            except Exception:  # noqa: BLE001
                pass
        except Exception as exc:  # noqa: BLE001
            _paper_text(ps, f"ERROR: {exc}", cx + 4, y0 + 25, 1.8)
        _paper_text(ps, label, cx + 4, y0 + 3.6, 1.9)
        _paper_text(ps, name, cx + 4, y0 + 1.0, 1.5)

    _paper_text(
        ps,
        f"{len(LIBRARY)} bloques / mobiliario, sanitarios, electro, vegetacion, simbolos y puertas",
        18,
        13,
        2.0,
    )
    try:
        doc.Regen(0)
    except Exception:  # noqa: BLE001
        pass


def main() -> int:
    s = AutoCADService()
    if not s.connect():
        print("ABORT: sin conexion", flush=True)
        return 1
    docs = s.conn.app.Documents
    doc = None
    for i in range(int(docs.Count)):
        d = docs.Item(i)
        try:
            if str(d.FullName).lower() == str(OUT).lower():
                doc = d
                break
        except Exception:  # noqa: BLE001
            pass
    if doc is None:
        doc = docs.Open(str(OUT))
    s.conn.doc = doc
    doc.Activate()
    print("Documento:", doc.Name, flush=True)

    # La hoja de catalogo referencia los bloques: hay que borrarla antes de
    # redefinirlos, o AutoCAD no permite eliminar las definiciones.
    try:
        doc.Layouts.Item("BIBLIOTECA").Delete()
    except Exception:  # noqa: BLE001
        pass

    _setup_layers(s)
    catalog_only = "--catalog-only" in sys.argv[1:]
    missing_only = "--missing-only" in sys.argv[1:]
    if not catalog_only:
        _define(s, only_missing=missing_only)
    _catalog(s)
    s.layouts.set_active_layout("Model")
    doc.Save()

    # verificacion: el catalogo no debe meter muebles en el modelo; solo las
    # puertas que inserta el plano.
    ms = s.conn.model_space()
    refs = 0
    for i in range(int(ms.Count)):
        try:
            if str(ms.Item(i).ObjectName) == "AcDbBlockReference":
                refs += 1
        except Exception:  # noqa: BLE001
            pass
    print(f"Bloques definidos: {len(LIBRARY)}; puertas en modelo: {refs}", flush=True)
    print("Guardado:", OUT, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
