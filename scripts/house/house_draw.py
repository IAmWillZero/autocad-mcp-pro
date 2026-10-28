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


def draw_labels(s, rooms: list, X: list, Y: list, height: float = 0.22) -> None:
    """Rotula cada ambiente (nombre + superficie) ENCUADRADO dentro de su area.

    El bloque de texto (nombre arriba, superficie abajo) se centra y se ajusta
    para caber por completo dentro de la cara interior del local, sin invadir
    muros ni salirse a la circulacion.
    """
    s.layer_tools.set_current_layer("A-TEXTOS")
    margin = 0.10
    # ancho real del texto ~0.95 de la altura por caracter (fuente del dibujo);
    # se usa 1.0 con holgura para no invadir muros.
    wf = 1.0
    for label, i0, i1, j0, j1 in rooms:
        x0, x1 = X[i0], X[i1]
        y0, y1 = Y[j0], Y[j1]
        area = abs(x1 - x0) * abs(y1 - y0)
        lines = [t for t in (label, f"{area:.2f} m2") if t]
        if not lines:
            continue
        cx = (x0 + x1) / 2.0
        inner_w = max((x1 - x0) - 2 * margin, 0.2)
        inner_h = max((y1 - y0) - 2 * margin, 0.2)
        widest = max(len(t) for t in lines)
        n = len(lines)
        h_w = inner_w / (wf * widest)  # cabe la linea mas larga
        h_h = inner_h / (1.0 + 1.25 * (n - 1))  # cabe el bloque completo
        h = max(min(height, h_w, h_h), 0.09)
        line_gap = 1.25 * h
        total = h + (n - 1) * line_gap
        # bloque centrado verticalmente, luego encajado dentro del local
        top = (y0 + y1) / 2.0 + total / 2.0
        top = min(top, y1 - margin)
        if top - total < y0 + margin:
            top = y0 + margin + total
        for k, t in enumerate(lines):
            wd = wf * len(t) * h
            x = min(max(cx - wd / 2.0, x0 + margin), x1 - margin - wd)
            y = top - h - k * line_gap
            s.geometry.create_text([round(x, 3), round(y, 3)], t, round(h, 3), "bylayer")


def draw_fixtures(s, fixtures: list, ox: float, oy: float) -> None:
    for block, pos, rot in fixtures:
        s.blocks.insert_block(block, [pos[0] + ox, pos[1] + oy], rotation=rot, layer="A-MOBILIARIO")


def draw_bottom_dims(s, breaks: list, front: float, off: float, ox: float) -> None:
    for i in range(len(breaks) - 1):
        b0, b1 = breaks[i], breaks[i + 1]
        mid = (b0 + b1) / 2.0
        s.dimensions.create_dimension(
            "rotated",
            [[b0 + ox, front], [b1 + ox, front]],
            [mid + ox, front - off],
            rotation=0.0,
            layer="A-COTAS",
            style="MCP-ARQ",
        )


def draw_left_dims(s, breaks: list, left: float, off: float, oy: float) -> None:
    for i in range(len(breaks) - 1):
        b0, b1 = breaks[i], breaks[i + 1]
        mid = (b0 + b1) / 2.0
        s.dimensions.create_dimension(
            "rotated",
            [[left, b0 + oy], [left, b1 + oy]],
            [left - off, mid + oy],
            rotation=90.0,
            layer="A-COTAS",
            style="MCP-ARQ",
        )


def draw_axes(
    s,
    vert: list,
    horiz: list,
    ox: float,
    oy: float,
    overs: dict,
    bubble: float = 0.45,
    text: float = 0.3,
) -> None:
    s.grid.create_construction_grid(
        vertical_positions=[v + ox for v in vert],
        horizontal_positions=[h + oy for h in horiz],
        bubble_radius=bubble,
        overshoot=1.0,
        text_height=text,
        layer="A-EJES",
        overshoot_bottom=overs.get("bottom", 1.0),
        overshoot_top=overs.get("top", 1.0),
        overshoot_left=overs.get("left", 1.0),
        overshoot_right=overs.get("right", 1.0),
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
