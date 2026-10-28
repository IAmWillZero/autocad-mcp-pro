"""Definicion de bloques (puertas, sanitarios, mobiliario) con las tools MCP."""

from __future__ import annotations


def _h(res: dict) -> str:
    return res.get("handle") or res["handles"][0]


def _mk(s, name: str, handles: list) -> None:
    res = s.blocks.create_block(name, handles, delete_source=True)
    if not res.get("success"):
        raise RuntimeError(f"No se pudo crear bloque {name}: {res}")


def define_blocks(s) -> None:
    # --- puerta 0.90 m (hoja + arco), capa A-PUER-VENT ---
    s.layer_tools.set_current_layer("A-PUER-VENT")
    leaf = s.geometry.create_line([0.0, 0.0], [0.0, 0.9], "bylayer")
    arc = s.geometry.create_arc([0.0, 0.0], 0.9, 0.0, 90.0, "bylayer")
    _mk(s, "A-PUERTA-090", [_h(leaf), _h(arc)])

    # --- sanitarios y mobiliario, capa A-MOBILIARIO ---
    s.layer_tools.set_current_layer("A-MOBILIARIO")

    tank = s.geometry.create_rectangle([0.0, 0.0], [0.38, 0.18], "bylayer")
    bowl = s.geometry.create_circle([0.19, 0.38], 0.19, "bylayer")
    _mk(s, "A-INODORO", [_h(tank), _h(bowl)])

    lav = s.geometry.create_rectangle([0.0, 0.0], [0.55, 0.42], "bylayer")
    lav2 = s.geometry.create_circle([0.275, 0.21], 0.12, "bylayer")
    _mk(s, "A-LAVATORIO", [_h(lav), _h(lav2)])

    duch = s.geometry.create_rectangle([0.0, 0.0], [0.9, 0.9], "bylayer")
    dia = s.geometry.create_line([0.0, 0.0], [0.9, 0.9], "bylayer")
    dra = s.geometry.create_circle([0.45, 0.45], 0.05, "bylayer")
    _mk(s, "A-DUCHA", [_h(duch), _h(dia), _h(dra)])

    cama = s.geometry.create_rectangle([0.0, 0.0], [1.4, 2.0], "bylayer")
    cama2 = s.geometry.create_line([0.0, 1.75], [1.4, 1.75], "bylayer")
    _mk(s, "A-CAMA-140x200", [_h(cama), _h(cama2)])

    sofa = s.geometry.create_rectangle([0.0, 0.0], [1.8, 0.8], "bylayer")
    sofa2 = s.geometry.create_rectangle([0.0, 0.8], [1.8, 1.0], "bylayer")
    _mk(s, "A-SOFA", [_h(sofa), _h(sofa2)])

    mesa = s.geometry.create_rectangle([0.0, 0.0], [1.0, 0.7], "bylayer")
    _mk(s, "A-MESA", [_h(mesa)])

    auto = s.geometry.create_rectangle([0.0, 0.0], [1.8, 4.2], "bylayer")
    w1 = s.geometry.create_circle([0.2, 1.0], 0.18, "bylayer")
    w2 = s.geometry.create_circle([1.6, 1.0], 0.18, "bylayer")
    w3 = s.geometry.create_circle([0.2, 3.2], 0.18, "bylayer")
    w4 = s.geometry.create_circle([1.6, 3.2], 0.18, "bylayer")
    _mk(s, "A-AUTO", [_h(auto), _h(w1), _h(w2), _h(w3), _h(w4)])

    coc = s.geometry.create_rectangle([0.0, 0.0], [0.6, 2.4], "bylayer")
    coc2 = s.geometry.create_circle([0.3, 0.5], 0.18, "bylayer")
    coc3 = s.geometry.create_circle([0.3, 1.2], 0.12, "bylayer")
    _mk(s, "A-COCINA", [_h(coc), _h(coc2), _h(coc3)])

    lavd = s.geometry.create_rectangle([0.0, 0.0], [0.60, 0.55], "bylayer")
    lavd2 = s.geometry.create_circle([0.30, 0.27], 0.16, "bylayer")
    _mk(s, "A-LAVADERO", [_h(lavd), _h(lavd2)])

    # vegetacion: arbol (copa + tronco) en capa A-TERRENO
    s.layer_tools.set_current_layer("A-TERRENO")
    copa = s.geometry.create_circle([0.0, 0.0], 0.70, "bylayer")
    tronco = s.geometry.create_circle([0.0, 0.0], 0.10, "bylayer")
    _mk(s, "A-ARBOL", [_h(copa), _h(tronco)])
