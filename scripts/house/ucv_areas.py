"""Calculo del cuadro de areas de la vivienda UCV y comparacion con el reporte.

Sin COM: solo aritmetica de las grillas de ``ucv_data``. Sirve para confirmar el
programa de areas del anteproyecto frente a las areas de referencia del reporte.
"""

from __future__ import annotations

import ucv_data as U

# Areas de referencia del reporte (m2). Sala-comedor se compara como suma.
REF_PB = {
    "GARAJE": 16.0,
    "OFICINA": 8.0,
    "LAVANDERIA": 5.0,
    "SS.HH. 1": 3.5,
    "COCINA": 10.5,
    "SALA-COMEDOR": 28.0,
}
REF_PA = {
    "DORMITORIO PRINCIPAL": 14.0,
    "SS.HH. EXISTENTE": 4.0,
    "SS.HH. NUEVO": 3.5,
    "SALA DE ESTAR": 10.0,
    "DORMITORIO 2": 12.0,
    "DORMITORIO 3": 12.0,
}

TERRENO = 8.0 * 23.0


def floor_areas(rooms: list, x: list, y: list) -> list[tuple[str, float]]:
    """Area de cada ambiente (m2) a partir de la grilla modular."""
    return [
        (label, abs(x[i1] - x[i0]) * abs(y[j1] - y[j0]))
        for (label, i0, i1, j0, j1) in rooms
    ]


def _sum(areas: list[tuple[str, float]], keys: set[str]) -> float:
    return sum(a for label, a in areas if label in keys)


def schedule() -> dict:
    """Devuelve el cuadro completo (areas por planta, subtotales y libres)."""
    pb = floor_areas(U.ROOMS1, U.X1, U.Y1)
    pa = floor_areas(U.ROOMS2, U.X2, U.Y2)
    huella = abs(U.X1[-1] - U.X1[0]) * (U.Y1[-1] - U.Y1[0])
    total_pb = sum(a for _l, a in pb)
    total_pa = sum(a for _l, a in pa)
    pa_prog = _sum(pa, set(REF_PA))  # PA comparable al programa (sin ropero/adicionales)
    # comparaciones (sala-comedor = comedor + sala)
    pb_ref = dict(pb)
    pb_ref_labels = {lb: a for lb, a in pb}
    sala_comedor = pb_ref_labels.get("COMEDOR", 0.0) + pb_ref_labels.get("SALA", 0.0)
    pb_ref["SALA-COMEDOR"] = sala_comedor
    return {
        "pb": pb,
        "pa": pa,
        "sala_comedor": sala_comedor,
        "total_pb": total_pb,
        "total_pa": total_pa,
        "pa_prog": pa_prog,
        "total": total_pb + total_pa,
        "terreno": TERRENO,
        "huella": huella,
        "area_libre": TERRENO - huella,
        "libre_pct": (TERRENO - huella) / TERRENO * 100.0,
        "ref_pb": REF_PB,
        "ref_pa": REF_PA,
        "pb_ref": pb_ref,
    }


def table_rows() -> list[tuple[str, str, float]]:
    """Filas (etiqueta, tipo, area) para el cuadro dibujado: r=ambiente, h=titulo."""
    d = schedule()
    rows: list[tuple[str, str, float]] = [("PRIMER PISO", "h", 0.0)]
    for label, area in d["pb"]:
        rows.append((label, "r", area))
    rows.append(("SUBTOTAL 1.er PISO", "h", d["total_pb"]))
    rows.append(("SEGUNDO PISO", "h", 0.0))
    for label, area in d["pa"]:
        rows.append((label, "r", area))
    rows.append(("SUBTOTAL 2.do PISO", "h", d["total_pa"]))
    rows.append(("AREA TECHADA TOTAL", "h", d["total"]))
    rows.append(("TERRENO (8.00 x 23.00)", "h", d["terreno"]))
    rows.append(("AREA LIBRE (terreno - huella)", "h", d["area_libre"]))
    return rows


def openings(open_list: list, x: list, y: list) -> list[dict]:
    """Normaliza cada vano: ancho y distancia desde la esquina de referencia."""
    out: list[dict] = []
    for o in open_list:
        a, b = float(o["a"]), float(o["b"])
        if o["axis"] == "h":
            dist = a - x[0]          # distancia desde la esquina OESTE
        else:
            dist = a - y[0]          # distancia desde la esquina SUR
        out.append({
            "id": o.get("id", "?"),
            "room": o.get("room", "?"),
            "orient": o.get("orient", "?"),
            "axis": o["axis"],
            "width": abs(b - a),
            "sill": float(o.get("sill", 0.0)),
            "dist": dist,
            "kind": o["kind"],
        })
    return out


_ROOM_ABBR = {
    "DORMITORIO PRINCIPAL": "DORM. PRINCIPAL",
    "DORMITORIO 2": "DORM. 2",
    "DORMITORIO 3": "DORM. 3",
    "ESCALERA / HALL": "ESCALERA/HALL",
    "LAVANDERIA": "LAVAND.",
    "SS.HH. EXISTENTE": "SS.HH. EXIST.",
    "SS.HH. NUEVO": "SS.HH. NUEVO",
}


def vanos_rows() -> list[tuple[str, str, float]]:
    """Cuadro de vanos (id ambiente orient. | ancho) para el plano."""
    def row(o: dict) -> tuple[str, str, float]:
        room = _ROOM_ABBR.get(o["room"], o["room"])
        return (f'{o["id"]} {room} {o["orient"]}', "r", o["width"])

    rows: list[tuple[str, str, float]] = [("VANOS - 1.er PISO", "h", 0.0)]
    for o in openings(U.OPEN1, U.X1, U.Y1):
        rows.append(row(o))
    rows.append(("VANOS - 2.do PISO", "h", 0.0))
    for o in openings(U.OPEN2, U.X2, U.Y2):
        rows.append(row(o))
    rows.append(("Antepecho ventanas 0.90 m (por confirmar)", "r", 0.0))
    return rows


def main() -> int:
    d = schedule()
    print("CUADRO DE AREAS - VIVIENDA UCV MAGISTERIAL N.230")
    print(f"{'AMBIENTE':32} {'ANTEPROYECTO':>12} {'REFERENCIA':>11} {'DIF':>7}")
    print("-" * 66)
    print("PRIMER PISO")
    for label, area in d["pb"]:
        print(f"{label:32} {area:12.2f}")
    for label, ref in d["ref_pb"].items():
        cur = d["pb_ref"].get(label, 0.0)
        print(f"  [ref] {label:26} {cur:12.2f} {ref:11.2f} {cur - ref:+7.2f}")
    print(f"{'SUBTOTAL 1.er PISO':32} {d['total_pb']:12.2f} "
          f"{sum(d['ref_pb'].values()):11.2f} {d['total_pb'] - sum(d['ref_pb'].values()):+7.2f}")
    print("SEGUNDO PISO")
    for label, area in d["pa"]:
        print(f"{label:32} {area:12.2f}")
    for label, ref in d["ref_pa"].items():
        cur = dict(d["pa"]).get(label, 0.0)
        print(f"  [ref] {label:26} {cur:12.2f} {ref:11.2f} {cur - ref:+7.2f}")
    print(f"{'SUBTOTAL 2.do PISO (prog.)':32} {d['pa_prog']:12.2f} "
          f"{sum(d['ref_pa'].values()):11.2f} {d['pa_prog'] - sum(d['ref_pa'].values()):+7.2f}")
    print("-" * 66)
    print(f"{'AREA TECHADA TOTAL':32} {d['total']:12.2f}")
    print(f"{'TERRENO':32} {d['terreno']:12.2f}")
    print(f"{'AREA LIBRE (terreno - huella)':32} {d['area_libre']:12.2f} "
          f"({d['libre_pct']:.2f} %)")
    print("-" * 66)
    print("CUADRO DE VANOS (id / ambiente / orient. / ancho / antepecho / dist.esquina)")
    for floor, op, x, y in (("1.er PISO", U.OPEN1, U.X1, U.Y1),
                            ("2.do PISO", U.OPEN2, U.X2, U.Y2)):
        for o in openings(op, x, y):
            print(f"  {floor:9} {o['id']:5} {o['room']:22} {o['orient']:8} "
                  f"{o['width']:5.2f} x alt.antepecho {o['sill']:.2f}  "
                  f"a {o['dist']:.2f} m de esquina")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
