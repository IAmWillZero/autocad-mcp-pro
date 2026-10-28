"""Generacion de muros con espesor real y vanos a partir de una grilla de salas."""

from __future__ import annotations


def seg_key(axis: str, coord: float, a: float, b: float) -> tuple:
    lo, hi = sorted((round(a, 3), round(b, 3)))
    return (axis, round(coord, 3), lo, hi)


def _kind_for(axis: str, coord: float, X: list, Y: list) -> str:
    if axis == "v":
        return "ext" if round(coord, 3) in (round(X[0], 3), round(X[-1], 3)) else "int"
    return "ext" if round(coord, 3) in (round(Y[0], 3), round(Y[-1], 3)) else "int"


def _merge_intervals(intervals: list) -> list:
    if not intervals:
        return []
    ordered = sorted((min(a, b), max(a, b)) for a, b in intervals)
    merged = [list(ordered[0])]
    for lo, hi in ordered[1:]:
        if lo <= merged[-1][1] + 1e-6:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    return [(lo, hi) for lo, hi in merged]


def collect_walls(rooms: list, X: list, Y: list) -> dict:
    """Muros unicos: agrupa por eje, une tramos colineales y clasifica ext/int.

    {key: (axis, coord, lo, hi, kind, layer)}
    """
    groups: dict = {}
    for _label, i0, i1, j0, j1 in rooms:
        x0, x1 = X[i0], X[i1]
        y0, y1 = Y[j0], Y[j1]
        for axis, coord, a, b in (
            ("h", y0, x0, x1),
            ("h", y1, x0, x1),
            ("v", x0, y0, y1),
            ("v", x1, y0, y1),
        ):
            groups.setdefault((axis, round(coord, 3)), []).append((a, b))

    edges: dict = {}
    for (axis, coord), intervals in groups.items():
        kind = _kind_for(axis, coord, X, Y)
        layer = "A-MUROS-CARGA" if kind == "ext" else "A-MUROS-TABIQ"
        for lo, hi in _merge_intervals(intervals):
            edges[seg_key(axis, coord, lo, hi)] = (axis, coord, lo, hi, kind, layer)
    return edges


def cuts_for(edge: tuple, openings: list) -> list:
    axis, coord, a, b = edge[0], edge[1], edge[2], edge[3]
    lo, hi = min(a, b), max(a, b)
    cuts = []
    for op in openings:
        if op["axis"] != axis or abs(op["at"] - coord) > 1e-6:
            continue
        c1, c2 = max(op["a"], lo), min(op["b"], hi)
        if c2 - c1 > 1e-6:
            cuts.append((min(c1, c2), max(c1, c2)))
    return cuts


def subtract(a: float, b: float, cuts: list) -> list:
    intervals = [(a, b)]
    for c1, c2 in sorted(cuts):
        out = []
        for s, e in intervals:
            if c2 <= s + 1e-9 or c1 >= e - 1e-9:
                out.append((s, e))
                continue
            if c1 > s + 1e-9:
                out.append((s, c1))
            if c2 < e - 1e-9:
                out.append((c2, e))
        intervals = out
    return [(s, e) for (s, e) in intervals if e - s > 1e-6]


def thickness(kind: str) -> float:
    # Espesor de muro uniforme ~0.15 m (pedido de revision).
    return 0.15


# Bloques de puerta a escala real por ancho nominal (definidos en block_library.py).
DOOR_BLOCKS = {
    0.70: "A-PUERTA-070",
    0.80: "A-PUERTA-080",
    0.90: "A-PUERTA-090",
    1.00: "A-PUERTA-100",
    1.10: "A-PUERTA-110",
    1.20: "A-PUERTA-120",
}
SLIDER_BLOCK_200 = "A-PUERTA-CORREDERA-200"


def draw_wall_run(s, edge: tuple, openings: list) -> list:
    """Dibuja el muro (con sus tramos) tras restar los vanos del borde."""
    axis, coord, a, b = edge[0], edge[1], edge[2], edge[3]
    kind, layer = edge[4], edge[5]
    lo, hi = min(a, b), max(a, b)
    t = thickness(kind)
    s.layer_tools.set_current_layer(layer)
    runs = subtract(lo, hi, cuts_for(edge, openings))
    handles = []
    for idx, (s0, s1) in enumerate(runs):
        ea = idx == 0
        eb = idx == len(runs) - 1
        a0 = s0 - (t / 2.0 if ea else 0.0)
        b0 = s1 + (t / 2.0 if eb else 0.0)
        if axis == "h":
            p0, p1 = [a0, coord], [b0, coord]
        else:
            p0, p1 = [coord, a0], [coord, b0]
        res = s.geometry.create_wall([p0, p1], thickness=t, color="bylayer")
        handles.extend(res.get("handles", []))
    return handles


def draw_openings(s, openings: list) -> dict:
    """Coloca puertas (bloque), ventanas (lineas) y portones en los vanos."""
    s.layer_tools.set_current_layer("A-PUER-VENT")
    doors = windows = panels = 0
    for op in openings:
        axis, coord, a, b = op["axis"], op["at"], op["a"], op["b"]
        w = abs(b - a)
        kind = op.get("kind", "door")
        if kind == "door":
            into = str(op.get("into", "+y")).lower()
            if axis == "h":
                if into in ("+y", "n", "arriba"):
                    pos, rot = [min(a, b), coord], 0.0
                else:
                    pos, rot = [max(a, b), coord], 180.0
            elif into in ("-x", "w", "izq"):
                pos, rot = [coord, min(a, b)], 90.0
            else:
                pos, rot = [coord, max(a, b)], 270.0
            # Bloque de puerta a escala real por ancho nominal; respaldo 0.90 escalado.
            block = DOOR_BLOCKS.get(round(w, 2))
            scale = 1.0 if block else w / 0.9
            s.blocks.insert_block(
                block or "A-PUERTA-090", pos, scale=scale, rotation=rot, layer="A-PUER-VENT"
            )
            doors += 1
        elif kind == "sliding":
            if abs(round(w, 2) - 2.0) < 1e-9:
                # Bloque de corredera 2.00 m (dos hojas superpuestas).
                if axis == "h":
                    pos, rot = [min(a, b), coord], 0.0
                else:
                    pos, rot = [coord, min(a, b)], 90.0
                s.blocks.insert_block(
                    SLIDER_BLOCK_200, pos, scale=1.0, rotation=rot, layer="A-PUER-VENT"
                )
            else:
                offs = (-0.04, 0.04)
                for o in offs:
                    if axis == "h":
                        s.geometry.create_line([a, coord + o], [b, coord + o], "bylayer")
                    else:
                        s.geometry.create_line([coord + o, a], [coord + o, b], "bylayer")
                if axis == "h":
                    m = (a + b) / 2.0
                    s.geometry.create_line([m, coord - 0.04], [m, coord + 0.04], "bylayer")
                else:
                    m = (a + b) / 2.0
                    s.geometry.create_line([coord - 0.04, m], [coord + 0.04, m], "bylayer")
            windows += 1
        elif kind == "window":
            offs = (-0.05, 0.0, 0.05)
            for o in offs:
                if axis == "h":
                    s.geometry.create_line([a, coord + o], [b, coord + o], "bylayer")
                else:
                    s.geometry.create_line([coord + o, a], [coord + o, b], "bylayer")
            windows += 1
        elif kind == "garage":
            for o in (-0.06, 0.06):
                if axis == "h":
                    s.geometry.create_line([a, coord + o], [b, coord + o], "bylayer")
                else:
                    s.geometry.create_line([coord + o, a], [coord + o, b], "bylayer")
            n = 6
            for i in range(1, n):
                p = a + (b - a) * i / n
                if axis == "h":
                    s.geometry.create_line([p, coord - 0.06], [p, coord + 0.06], "bylayer")
                else:
                    s.geometry.create_line([coord - 0.06, p], [coord + 0.06, p], "bylayer")
            panels += 1
        # "open" = paso libre: no se dibuja nada
    return {"doors": doors, "windows": windows, "panels": panels}
