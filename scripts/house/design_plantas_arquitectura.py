"""Dibuja las dos plantas arquitectonicas desarrolladas.

Criterios de esta entrega:
- Muros de 0.15 m.
- Sin columnas.
- Puertas: bloque con hoja, barrido y marco (A-PUERTA-*).
- Ventanas: posicionadas con sus lineas de carpinteria.
- Ejes y cotas en ambas plantas.
- Zonificacion de ambas plantas, con leyenda y cuadro de datos.
- Mobiliario de biblioteca insertado en ambas plantas (sin ploteo).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "house"))

import ucv_areas as AR  # noqa: E402
import ucv_data as U  # noqa: E402
import vivienda_ucv as V  # noqa: E402
from house_draw import (  # noqa: E402
    draw_axes,
    draw_bottom_dims,
    draw_labels,
    draw_left_dims,
    draw_walls_and_openings,
    shift_openings,
)

import autocad_mcp.connection as _cad_conn  # noqa: E402
from autocad_mcp.com import variant_point  # noqa: E402
from autocad_mcp.service import AutoCADService  # noqa: E402

OUT = ROOT / "out" / "Vivienda_UCV_Magisterial_230_PLANTAS.dwg"
PB_OX = 0.0
PA_OX = 15.0
ZONE_OX = 30.0
ZONE_PA_OX = 45.0
INFO_X = 55.5
OVERS = {"bottom": 1.6, "top": 1.2, "left": 1.6, "right": 1.2}


def _clean(s: AutoCADService):
    docs = s.conn.app.Documents
    for i in range(int(docs.Count)):
        d = docs.Item(i)
        try:
            if str(d.FullName).lower() == str(OUT).lower():
                s.conn.doc = d
                d.Activate()
                return d
        except Exception:  # noqa: BLE001
            pass
    os.makedirs(OUT.parent, exist_ok=True)
    if OUT.exists():
        d = docs.Open(str(OUT))
    else:
        d = docs.Add()
        d.SaveAs(str(OUT))
    s.conn.doc = d
    d.Activate()
    return d


def _draw_plan(
    s: AutoCADService,
    rooms: list,
    X: list,
    Y: list,
    openings: list,
    axes_v: list,
    axes_h: list,
    title: str,
    ox: float,
    bottom_levels: list,
    left_levels: list,
) -> None:
    Xa = [x + ox for x in X]
    Ya = list(Y)
    ops = shift_openings(openings, ox, 0.0)

    draw_walls_and_openings(s, rooms, Xa, Ya, ops)
    draw_labels(s, rooms, Xa, Ya)
    draw_axes(s, axes_v, axes_h, ox, 0.0, OVERS, bubble=0.35, text=0.24)

    for off, breaks in bottom_levels:
        draw_bottom_dims(s, breaks, Ya[0], off, ox)
    for off, breaks in left_levels:
        draw_left_dims(s, breaks, Xa[0], off, 0.0)

    s.layer_tools.set_current_layer("A-TEXTOS")
    s.geometry.create_text([Xa[0], max(Ya) + 2.4], title, 0.24, "bylayer")


def _draw_zoning(
    s: AutoCADService,
    rooms: list,
    X: list,
    Y: list,
    ox: float,
    title: str,
    stair_label: str,
    gardens: bool = False,
    terraces: bool = False,
) -> None:
    """Zonificacion de una planta, en el mismo modelo, con su titulo."""
    V._terreno(s, ox)
    V._stair_plan(s, U.STAIR, ox, 0.0, stair_label)
    V._room_zones(s, rooms, X, Y, ox)
    if gardens:
        for pts in (U.JARDIN_FRONTAL, U.TERRAZA_POST, U.JARDIN_POST, U.JARDIN_NOTCH_PB):
            if not pts:
                continue
            shifted = [[p[0] + ox, p[1]] for p in pts]
            V._zone(s, "Z-AREA-LIBRE", shifted, V._lib_label(shifted), V._mid(shifted))

    if terraces:
        for pts in (U.TERRAZA_NOTCH,):
            if not pts:
                continue
            shifted = [[p[0] + ox, p[1]] for p in pts]
            V._zone(s, "Z-AREA-LIBRE", shifted, V._lib_label(shifted), V._mid(shifted))

    s.layer_tools.set_current_layer("A-TEXTOS")
    s.geometry.create_text([ox, 24.15], title, 0.26, "bylayer")
    s.geometry.create_text(
        [ox, 23.65],
        "ZONA SOCIAL / SERVICIOS / PRIVADA / CIRCULACION / AREA LIBRE",
        0.14,
        "bylayer",
    )


def _draw_data_table(s: AutoCADService) -> None:
    """Cuadro de datos de ambientes: ancho, largo y area en metros (2 decimales)."""
    rows: list[list[str]] = [
        ["NIVEL", "AMBIENTE", "ANCHO (m)", "LARGO (m)", "AREA (m2)"],
    ]
    for level, rooms, X, Y in (
        ("1.er PISO", U.ROOMS1, U.X1, U.Y1),
        ("2.do PISO", U.ROOMS2, U.X2, U.Y2),
    ):
        total = 0.0
        for label, i0, i1, j0, j1 in rooms:
            w = abs(X[i1] - X[i0])
            ln = abs(Y[j1] - Y[j0])
            area = w * ln
            total += area
            rows.append([level, label, f"{w:.2f}", f"{ln:.2f}", f"{area:.2f}"])
        rows.append(["", f"SUBTOTAL {level}", "", "", f"{total:.2f}"])

    d = AR.schedule()
    rows.append(["", "AREA TECHADA TOTAL", "", "", f"{d['total']:.2f}"])
    rows.append(["", "TERRENO (8.00 x 23.00)", "8.00", "23.00", f"{d['terreno']:.2f}"])
    rows.append(["", "AREA LIBRE", "", "", f"{d['area_libre']:.2f}"])

    # Tabla dibujada con lineas y textos: predecible a 1:100 y facil de copiar.
    x0, top, rh = INFO_X, 17.0, 0.30
    widths = [2.2, 5.6, 2.2, 2.2, 2.4]
    xs = [x0]
    for w in widths:
        xs.append(xs[-1] + w)
    bottom = top - len(rows) * rh

    s.layer_tools.set_current_layer("A-ROTULO")
    s.geometry.create_rectangle([x0, bottom], [xs[-1], top], "bylayer")
    for r in range(1, len(rows)):
        y = top - r * rh
        s.geometry.create_line([x0, y], [xs[-1], y], "bylayer")
    for x in xs[1:-1]:
        s.geometry.create_line([x, bottom], [x, top], "bylayer")

    s.layer_tools.set_current_layer("A-TEXTOS")
    for r, row in enumerate(rows):
        h = 0.145 if r == 0 else 0.13
        y = top - (r + 0.5) * rh - h * 0.45
        for c, value in enumerate(row):
            if not value:
                continue
            tw = 0.95 * h * len(value)
            if c <= 1:
                x = xs[c] + 0.07
            else:
                x = xs[c] + (widths[c] - tw) / 2.0
            s.geometry.create_text([round(x, 3), round(y, 3)], value, h, "bylayer")

    s.geometry.create_text([INFO_X, 17.35], "CUADRO DE DATOS - AMBIENTES", 0.24, "bylayer")
    s.geometry.create_text(
        [INFO_X, bottom - 0.30],
        "Dimensiones y areas en metros, con dos decimales. Areas de recinto sin muros.",
        0.14,
        "bylayer",
    )


def _draw_furniture(s: AutoCADService) -> None:
    """Inserta mobiliario, sanitarios y vegetacion en las plantas (no en zonificacion)."""
    # (bloque, x local, y local, giro en grados)
    pb = [
        # OFICINA
        ("OBJ-ESCRITORIO-140", 6.00, 8.30, 0.0),
        ("OBJ-LIBRERO-200", 4.75, 7.00, 90.0),
        ("OBJ-LIBRERO-200", 7.65, 8.00, -90.0),
        ("OBJ-PLANTA-INTERIOR", 7.30, 4.40, 0.0),
        ("OBJ-AUTO-450", 1.95, 4.35, 90.0),
        # SALA DE ESTAR
        ("OBJ-SOFA-MOD-260", 1.00, 13.60, 90.0),
        ("OBJ-MESA-CENTRO-120", 1.80, 14.20, 90.0),
        ("OBJ-ALFOMBRA-240", 2.40, 13.70, 90.0),
        ("OBJ-TV-180", 2.44, 16.20, -90.0),
        ("OBJ-SILLA-LOUNGE", 0.30, 16.40, 0.0),
        ("OBJ-PLANTA-INTERIOR", 2.20, 17.20, 0.0),
        # RINCON DE LECTURA: ocupa el area libre sin bloquear el acceso.
        ("OBJ-SILLA-LOUNGE", 0.30, 10.20, 0.0),
        ("OBJ-MESA-LATERAL-060", 1.35, 10.25, 0.0),
        # SS.HH. 1
        ("OBJ-INODORO-SUSP", 5.90, 13.55, 0.0),
        ("OBJ-LAVAMANOS-100", 5.50, 12.55, 0.0),
        ("OBJ-DUCHA-WALKIN", 6.80, 13.35, 0.0),
        # LAVANDERIA
        ("OBJ-LAVADERO-UTIL", 7.30, 14.60, 0.0),
        ("OBJ-LAVADORA-060", 6.55, 15.30, 0.0),
        # COCINA
        ("OBJ-ISLA-COCINA-180", 5.20, 17.30, 0.0),
        ("OBJ-REFRI-090", 8.00, 16.10, 90.0),
        ("OBJ-LAVAPLATOS-060", 5.20, 16.05, 0.0),
        ("OBJ-MICROONDAS-060", 7.40, 18.30, 0.0),
        # JARDIN
        ("OBJ-PLANTA-JARDIN", 1.00, 1.00, 0.0),
        ("OBJ-PLANTA-JARDIN", 6.50, 1.50, 0.0),
        ("OBJ-PLANTA-JARDIN", 2.00, 22.00, 0.0),
        ("OBJ-PLANTA-JARDIN", 6.00, 22.20, 0.0),
        ("OBJ-PLANTA-JARDIN", 4.80, 20.30, 0.0),
        ("OBJ-PLANTA-JARDIN", 7.15, 20.45, 0.0),
        # COMEDOR
        ("OBJ-COMEDOR-6P", 1.00, 18.55, 0.0),
        ("OBJ-PLANTA-INTERIOR", 0.30, 18.30, 0.0),
    ]
    pa = [
        # DORMITORIO 2
        ("OBJ-CAMA-SINGLE", 0.30, 6.90, 0.0),
        ("OBJ-ROPERO-240", 4.40, 6.00, 90.0),
        ("OBJ-ESCRITORIO-140", 0.60, 4.60, 0.0),
        ("OBJ-PLANTA-INTERIOR", 3.50, 4.45, 0.0),
        # DORMITORIO 3
        ("OBJ-CAMA-SINGLE", 6.60, 6.90, 0.0),
        ("OBJ-ROPERO-240", 5.00, 5.00, 90.0),
        ("OBJ-ESCRITORIO-140", 5.60, 4.40, 0.0),
        # SALA DE ESTAR
        ("OBJ-SOFA-MOD-260", 1.00, 9.90, 90.0),
        ("OBJ-MESA-CENTRO-120", 1.80, 10.50, 90.0),
        ("OBJ-ALFOMBRA-240", 2.60, 10.00, 90.0),
        ("OBJ-SILLA-LOUNGE", 0.30, 12.70, 0.0),
        ("OBJ-PLANTA-INTERIOR", 2.20, 13.40, 0.0),
        # RINCON DE LECTURA: mobiliario complementario separado del recorrido.
        ("OBJ-SILLA-LOUNGE", 0.30, 14.55, 0.0),
        ("OBJ-MESA-LATERAL-060", 1.35, 14.70, 0.0),
        # BALCON
        ("OBJ-PLANTA-INTERIOR", 4.50, 9.60, 0.0),
        ("OBJ-PLANTA-JARDIN", 5.40, 9.70, 0.0),
        ("OBJ-MESA-LATERAL-060", 5.00, 10.70, 0.0),
        # TERRAZA POSTERIOR (area libre)
        ("OBJ-PLANTA-JARDIN", 4.80, 20.30, 0.0),
        ("OBJ-PLANTA-JARDIN", 7.15, 20.45, 0.0),
        # SS.HH. 3
        ("OBJ-INODORO-SUSP", 5.90, 13.55, 0.0),
        ("OBJ-LAVAMANOS-100", 5.50, 12.55, 0.0),
        ("OBJ-DUCHA-WALKIN", 6.80, 13.35, 0.0),
        # DORMITORIO PRINCIPAL
        ("OBJ-CAMA-QUEEN", 0.90, 18.80, 0.0),
        # Separacion de 0.10 m respecto al vano para no invadir el barrido.
        ("OBJ-ROPERO-240", 4.30, 15.60, 90.0),
        ("OBJ-PLANTA-INTERIOR", 0.30, 16.90, 0.0),
        # SS.HH. 2
        ("OBJ-TINA-FREESTANDING", 8.00, 14.50, 90.0),
        ("OBJ-INODORO-SUSP", 4.60, 16.50, 0.0),
        ("OBJ-DUCHA-WALKIN", 5.50, 16.30, 0.0),
        ("OBJ-LAVAMANOS-100", 5.30, 14.40, 0.0),
        # VESTIDOR 2: un solo ropero en el muro norte; deja paso libre a la puerta.
        ("OBJ-ROPERO-240", 5.60, 18.40, 0.0),
    ]

    for floor_ox, items in ((PB_OX, pb), (PA_OX, pa)):
        s.layer_tools.set_current_layer("A-MOBILIARIO")
        for name, x, y, rot in items:
            res = s.blocks.insert_block(name, [round(x + floor_ox, 3), round(y, 3), 0.0], 1.0, rot)
            if not res.get("success"):
                print(f"Aviso: no se inserto {name}: {res}", flush=True)


def _north(s: AutoCADService, x: float, y: float) -> None:
    """Inserta el bloque profesional de norte (A-NORTE) sin regen intermedio."""
    s.layer_tools.set_current_layer("A-EJES")
    try:
        s.conn.ensure()
        ref = s.conn.doc.ModelSpace.InsertBlock(
            variant_point(round(x, 3), round(y, 3), 0.0),
            "A-NORTE",
            1.0,
            1.0,
            1.0,
            0.0,
        )
        ref.Layer = "A-EJES"
    except Exception as exc:  # noqa: BLE001
        print(f"Aviso: no se inserto A-NORTE: {exc}", flush=True)


def _setup(s: AutoCADService) -> None:
    s.standards.apply_standard()
    for lay, color in (
        ("A-MUROS-CARGA", "white"),
        ("A-MUROS-TABIQ", "white"),
        ("A-PUER-VENT", "cyan"),
        ("A-EJES", "red"),
        ("A-COTAS", "yellow"),
        ("A-TEXTOS", "white"),
        ("A-TERRENO", "white"),
        ("A-ROTULO", "white"),
        ("A-MOBILIARIO", "white"),
        ("A-SANITARIO", "cyan"),
        ("A-ELECTRO", "yellow"),
        ("A-VEGETACION", "green"),
        ("Z-SOCIAL", "magenta"),
        ("Z-SERVICIOS", "blue"),
        ("Z-PRIVADA", "green"),
        ("Z-CIRCULACION", "yellow"),
        ("Z-AREA-LIBRE", "green"),
    ):
        s.layer_tools.create_or_get_layer(lay, color, "Arquitectura")


def main() -> int:
    s = AutoCADService()
    if not s.connect():
        print("ABORT: sin conexion", flush=True)
        return 1
    # Un regen por entidad vuelve el dibujo inviable (696 entidades). Se
    # desactiva durante la construccion y se regenera una sola vez al final.
    regen_final = s.conn.regen

    def _sin_regen() -> None:
        return None

    def _sin_espera(_segundos: float) -> None:
        return None

    s.conn.regen = _sin_regen  # type: ignore[method-assign]
    _cad_conn.time.sleep = _sin_espera
    doc = _clean(s)
    print("Documento:", doc.Name, flush=True)
    s.deleter.delete_all_entities(confirm=True)
    _setup(s)

    # Cotas en metros con dos decimales exactos (DIMDEC=2, DIMZIN=0).
    # Se fija en el estilo activo MCP-ARQ antes de crear las cotas; evitar
    # DIMOVERRIDE por SendCommand, que puede quedar esperando en AutoCAD.
    try:
        doc.SetVariable("DIMDEC", 2)
        doc.SetVariable("DIMZIN", 0)
    except Exception as exc:  # noqa: BLE001
        print(f"Aviso: no se ajusto la precision de cotas: {exc}", flush=True)

    # El mobiliario va antes de rotulos/ejes para que los textos queden encima.
    _draw_furniture(s)
    # La escalera tambien va antes de los rotulos de ambiente.
    V._stair_plan(s, U.STAIR, PB_OX, 0.0, "SUBE", outline=False)
    V._stair_plan(s, U.STAIR, PA_OX, 0.0, "BAJA", outline=False)

    bottom = [(0.8, [0.0, 3.0, 4.4, 6.2, 8.0]), (2.0, [0.0, 4.4, 8.0])]
    left_pb = [
        (2.4, [4.0, 9.5, 12.5, 14.25, 16.0, 18.0, 21.0]),
        (3.6, [4.0, 12.5, 21.0]),
    ]
    left_pa = [
        (2.4, [4.0, 9.5, 11.6, 12.5, 14.25, 17.25, 21.0]),
        (3.6, [4.0, 9.5, 14.25, 21.0]),
    ]

    _draw_plan(
        s,
        U.ROOMS1,
        U.X1,
        U.Y1,
        U.OPEN1,
        U.AXES_V1,
        U.AXES_H1,
        "PLANTA BAJA - DISTRIBUCION ARQUITECTONICA",
        PB_OX,
        bottom,
        left_pb,
    )
    _draw_plan(
        s,
        U.ROOMS2,
        U.X2,
        U.Y2,
        U.OPEN2,
        U.AXES_V2,
        U.AXES_H2,
        "PLANTA ALTA - DISTRIBUCION ARQUITECTONICA",
        PA_OX,
        bottom,
        left_pa,
    )
    V._terreno(s, PB_OX)
    V._terreno(s, PA_OX)

    _draw_zoning(
        s,
        U.ROOMS1,
        U.X1,
        U.Y1,
        ZONE_OX,
        "PLANTA BAJA - ZONIFICACION",
        "SUBE",
        gardens=True,
    )
    _draw_zoning(
        s,
        U.ROOMS2,
        U.X2,
        U.Y2,
        ZONE_PA_OX,
        "PLANTA ALTA - ZONIFICACION",
        "BAJA",
        terraces=True,
    )
    V._legend(s, INFO_X, 22.6)
    _north(s, INFO_X + 0.2, 24.3)
    _draw_data_table(s)

    s.layer_tools.set_current_layer("A-TEXTOS")
    for pos, txt, height in (
        ((PB_OX, 25.55), "VIVIENDA UCV MAGISTERIAL 230 - PLANTAS ARQUITECTONICAS", 0.30),
        (
            (PB_OX, 24.95),
            "Muros de 0.15 m / Sin columnas / Puertas: bloque con hoja y barrido / "
            "Ventanas posicionadas / Cotas en metros",
            0.15,
        ),
    ):
        V._retry(
            lambda pos=pos, txt=txt, height=height: s.geometry.create_text(
                [pos[0], pos[1]], txt, height, "bylayer"
            )
        )
    # Norte en ambas plantas arquitectonicas (bloque A-NORTE).
    _north(s, PB_OX + 10.5, 21.5)
    _north(s, PA_OX + 10.5, 21.5)

    V._retry(lambda: s.ops.zoom_extents())
    try:
        regen_final()
    except Exception:  # noqa: BLE001
        pass
    V._retry(lambda: doc.Save())
    print("Guardado:", OUT, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
