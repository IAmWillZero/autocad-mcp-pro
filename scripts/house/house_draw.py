"""Dibujo generico de una planta (muros, vanos, rotulos, ejes y cotas)."""

from __future__ import annotations

from house_geom import collect_walls, draw_openings, draw_wall_run


def shift_openings(openings: list, ox: float, oy: float) -> list:
    out = []
    for op in openings:
        q = dict(op)
        if op["axis"] == "h":
            q["at"] = op["at"] + oy
            q["a"] = op["a"] + ox
            q["b"] = op["b"] + ox
        else:
            q["at"] = op["at"] + ox
            q["a"] = op["a"] + oy
            q["b"] = op["b"] + oy
        out.append(q)
    return out


def draw_walls_and_openings(s, rooms: list, X: list, Y: list, openings: list) -> int:
    edges = collect_walls(rooms, X, Y)
    for edge in edges.values():
        draw_wall_run(s, edge, openings)
    stats = draw_openings(s, openings)
    return len(edges)


def _text_width(label: str, height: float, factor: float = 0.62) -> float:
    """Ancho aproximado del texto (fuente tipo simplex: ~0.62 de la altura por caracter)."""
    return len(label) * factor * height


def draw_labels(s, rooms: list, X: list, Y: list, height: float = 0.22) -> None:
    """Rotula cada ambiente (nombre + superficie); ajusta al local y separa solapes."""
    s.layer_tools.set_current_layer("A-TEXTOS")
    items: list[list] = []
    for (label, i0, i1, j0, j1) in rooms:
        cx = (X[i0] + X[i1]) / 2.0
        cy = (Y[j0] + Y[j1]) / 2.0
        inner_w = max((X[i1] - X[i0]) - 0.30, 0.4)
        inner_h = max((Y[j1] - Y[j0]) - 0.30, 0.4)
        area = abs(X[i1] - X[i0]) * abs(Y[j1] - Y[j0])
        area_txt = f"{area:.2f} m2"
        h = height
        if label:
            h = min(h, inner_w / _text_width(label, 1.0))
        h = min(h, inner_h * 0.55)
        h = max(h, 0.09)
        if label:
            items.append([label, cx, cy + h * 0.45, h])
        ha = max(min(h * 0.72, inner_w / _text_width(area_txt, 1.0)), 0.07)
        items.append([area_txt, cx, cy - h * 0.60, ha])

    # separa etiquetas que se pisen (desplaza en Y, que es lo mas holgado)
    for _ in range(60):
        moved = False
        for a in range(len(items)):
            for b in range(a + 1, len(items)):
                la, xa, ya, ha = items[a]
                lb, xb, yb, hb = items[b]
                wa, wb = _text_width(la, ha), _text_width(lb, hb)
                if abs(xa - xb) < (wa + wb) / 2 + 0.05 and abs(ya - yb) < (ha + hb) / 2 + 0.05:
                    push = ((ha + hb) / 2 + 0.07 - abs(ya - yb)) / 2.0
                    if ya <= yb:
                        items[a][2] -= push
                        items[b][2] += push
                    else:
                        items[a][2] += push
                        items[b][2] -= push
                    moved = True
        if not moved:
            break

    for label, cx, cy, h in items:
        if label:
            s.geometry.create_text([cx, cy], label, round(h, 3), "bylayer")


def draw_fixtures(s, fixtures: list, ox: float, oy: float) -> None:
    for (block, pos, rot) in fixtures:
        s.blocks.insert_block(
            block, [pos[0] + ox, pos[1] + oy], rotation=rot, layer="A-MOBILIARIO"
        )


def draw_bottom_dims(s, breaks: list, front: float, off: float, ox: float) -> None:
    for i in range(len(breaks) - 1):
        b0, b1 = breaks[i], breaks[i + 1]
        mid = (b0 + b1) / 2.0
        s.dimensions.create_dimension(
            "rotated", [[b0 + ox, front], [b1 + ox, front]], [mid + ox, front - off],
            rotation=0.0, layer="A-COTAS", style="MCP-ARQ",
        )


def draw_left_dims(s, breaks: list, left: float, off: float, oy: float) -> None:
    for i in range(len(breaks) - 1):
        b0, b1 = breaks[i], breaks[i + 1]
        mid = (b0 + b1) / 2.0
        s.dimensions.create_dimension(
            "rotated", [[left, b0 + oy], [left, b1 + oy]], [left - off, mid + oy],
            rotation=90.0, layer="A-COTAS", style="MCP-ARQ",
        )


def draw_axes(s, vert: list, horiz: list, ox: float, oy: float,
              overs: dict, bubble: float = 0.45, text: float = 0.3) -> None:
    s.grid.create_construction_grid(
        vertical_positions=[v + ox for v in vert],
        horizontal_positions=[h + oy for h in horiz],
        bubble_radius=bubble, overshoot=1.0, text_height=text, layer="A-EJES",
        overshoot_bottom=overs.get("bottom", 1.0), overshoot_top=overs.get("top", 1.0),
        overshoot_left=overs.get("left", 1.0), overshoot_right=overs.get("right", 1.0),
    )


def draw_stair_u(s, stair: dict, ox: float, oy: float) -> None:
    """Escalera en U: dos tramos de 0.90 m, descanso y linea de rotura."""
    s.layer_tools.set_current_layer("A-MUROS-TABIQ")
    x0, x1 = stair["x0"] + ox, stair["x1"] + ox
    y0, y1 = stair["y0"] + oy, stair["y1"] + oy
    n = 8
    landing = 1.0
    run = (y1 - y0) - landing
    step = run / n
    fl = x0 + 0.9
    fr = x1 - 0.9
    # barandas
    s.geometry.create_line([fl, y0], [fl, y1], "bylayer")
    s.geometry.create_line([fr, y0], [fr, y1], "bylayer")
    # peldaños (dos tramos)
    for i in range(1, n + 1):
        yy = y0 + i * step
        s.geometry.create_line([x0, yy], [fl, yy], "bylayer")
        s.geometry.create_line([fr, yy], [x1, yy], "bylayer")
    s.geometry.create_line([x0, y0 + run], [x1, y0 + run], "bylayer")
    # flecha de subida sobre el tramo izquierdo
    xc = (x0 + fl) / 2.0
    y_base = y0 + 0.15
    y_tip = y0 + run - 0.15
    s.geometry.create_line([xc, y_base], [xc, y_tip], "bylayer")
    head = 0.12
    s.geometry.create_line([xc, y_tip], [xc - head, y_tip - head], "bylayer")
    s.geometry.create_line([xc, y_tip], [xc + head, y_tip - head], "bylayer")
