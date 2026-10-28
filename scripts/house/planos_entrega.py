"""Limpia los membretes y crea las laminas A4 que faltan.

Trabaja sobre el DWG abierto en AutoCAD. Hace respaldo antes de tocar nada.

1. En A4_PB / A4_PA / A3_D solo cambian LETRAS del membrete: se borran los
   rotulos duplicados de la capa A-ROTULO y se reescriben los datos dentro de
   las celdas del cajete UCV existente, con altura ajustada para que nada se
   salga de la hoja.
2. Crea A4_BLOQUES_1, A4_BLOQUES_2, A4_BIBLIOTECA y A4_DATOS con membrete
   nuevo, prolijo, y el area de dibujo libre para que el usuario coloque los
   MVIEW a mano.
3. Exporta el cuadro de datos a out/cuadro_datos.xlsx (editable en Excel).

Uso:
    python scripts/house/planos_entrega.py            # todo
    python scripts/house/planos_entrega.py --dry-run  # solo informa
"""

from __future__ import annotations

import csv
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import pythoncom  # noqa: E402
import win32com.client  # noqa: E402

from autocad_mcp.com import (  # noqa: E402
    as_dynamic,
    variant_array,
    variant_objects,
    variant_point,
)

PAPER = 0
RED = 1
YELLOW = 2
GREEN = 3
CYAN = 4
BLUE = 5
MAGENTA = 6
WHITE = 7
GREY = 8

ROTULO = "A-ROTULO"
MARCO = "Marco"

ALUMNO = "WILLIAMS RONALDO SIGUEÑAS ORTIZ"
PROFESOR = "M.S. MARIBEL MARCELA NORIEGA FALCON"
PROYECTO = "VIVIENDA UCV MAGISTERIAL 230"
CURSO = "INGENIERIA CIVIL - EXPRESION GRAFICA - GRUPO A1"
FECHA = "27/10/2026"
CICLO = "II"

# Ancho medio de caracter (fraccion de la altura) para autoajustar textos.
CHW = 0.62


# --------------------------------------------------------------------------- #
# utilidades COM
# --------------------------------------------------------------------------- #
def f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:  # noqa: BLE001
        return default


def bbox(entity: Any) -> tuple[float, float, float, float] | None:
    try:
        mn, mx = entity.GetBoundingBox()
        return (f(mn[0]), f(mn[1]), f(mx[0]), f(mx[1]))
    except Exception:  # noqa: BLE001
        return None


def wait(seconds: float = 0.5) -> None:
    time.sleep(seconds)


def reintentar(accion: Any, etiqueta: str, intentos: int = 12) -> bool:
    """AutoCAD rechaza llamadas cuando esta ocupado: reintenta sin romper."""
    for _ in range(intentos):
        try:
            accion()
            return True
        except Exception:  # noqa: BLE001
            time.sleep(1.0)
    print(f"  aviso: no se pudo completar {etiqueta}")
    return False


def activate(doc: Any, name: str) -> None:
    for _ in range(20):
        try:
            doc.ActiveLayout = doc.Layouts.Item(name)
            doc.ActiveSpace = PAPER
            wait()
            doc.SetVariable("CTAB", name)
            wait()
            return
        except Exception:  # noqa: BLE001
            wait()
    raise RuntimeError(f"No se pudo activar el layout {name}")


def layer(doc: Any, name: str, color: int, plottable: bool = True) -> None:
    try:
        lay = doc.Layers.Item(name)
    except Exception:  # noqa: BLE001
        lay = doc.Layers.Add(name)
    lay.Color = color
    try:
        lay.LayerOn = True
        lay.Freeze = False
        lay.Plottable = plottable
    except Exception:  # noqa: BLE001
        pass


def style(ent: Any, lay: str, color: int, weight: int = -3) -> Any:
    try:
        ent.Layer = lay
        ent.Color = color
        ent.Lineweight = weight
    except Exception:  # noqa: BLE001
        pass
    return ent


def line(
    block: Any,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    color: int = WHITE,
    lay: str = ROTULO,
    weight: int = -3,
) -> Any:
    return style(block.AddLine(variant_point(x0, y0), variant_point(x1, y1)), lay, color, weight)


def rect(
    block: Any,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    color: int = WHITE,
    lay: str = ROTULO,
    weight: int = -3,
) -> None:
    line(block, x0, y0, x1, y0, color, lay, weight)
    line(block, x1, y0, x1, y1, color, lay, weight)
    line(block, x1, y1, x0, y1, color, lay, weight)
    line(block, x0, y1, x0, y0, color, lay, weight)


def text(
    block: Any,
    value: str,
    x: float,
    y: float,
    h: float,
    color: int = WHITE,
    lay: str = ROTULO,
    align: int | None = None,
) -> Any:
    ent = block.AddText(value, variant_point(x, y), h)
    style(ent, lay, color)
    if align is not None:
        try:
            ent.Alignment = align
            ent.TextAlignmentPoint = variant_point(x, y)
        except Exception:  # noqa: BLE001
            pass
    return ent


def fit_height(value: str, max_width: float, max_height: float) -> float:
    """Altura de texto que entra en el ancho dado (sin bajar de 1.1 mm)."""
    if not value:
        return max_height
    h = max_width / (len(value) * CHW)
    return max(0.0011, min(max_height, h))


# --------------------------------------------------------------------------- #
# membrete
# --------------------------------------------------------------------------- #
def cajete_cells(block: Any) -> dict[str, Any]:
    """Detecta la geometria del cajete UCV (filas y columna de lamina)."""
    rows: list[tuple[float, float, float, float]] = []
    narrow: list[tuple[float, float, float, float]] = []
    for i in range(int(block.Count)):
        e = block.Item(i)
        try:
            if str(e.ObjectName) != "AcDbPolyline" or str(e.Layer) != MARCO:
                continue
        except Exception:  # noqa: BLE001
            continue
        bb = bbox(e)
        if not bb:
            continue
        w, h = bb[2] - bb[0], bb[3] - bb[1]
        if w > 0.04 and h < 0.015:
            rows.append(bb)
        elif 0.004 < w < 0.02 and 0.004 < h < 0.02:
            narrow.append(bb)
    rows.sort(key=lambda r: -r[3])
    if not rows:
        raise RuntimeError("No se encontro el cajete (capas/filas)")
    lamina = max(narrow, key=lambda b: b[0]) if narrow else None
    return {"rows": rows, "lamina": lamina}


def dividers(block: Any, y0: float, y1: float) -> list[float]:
    xs: list[float] = []
    for i in range(int(block.Count)):
        e = block.Item(i)
        try:
            if str(e.ObjectName) != "AcDbLine" or str(e.Layer) != MARCO:
                continue
        except Exception:  # noqa: BLE001
            continue
        bb = bbox(e)
        if not bb:
            continue
        if bb[2] - bb[0] < 0.0005 and bb[3] >= y0 - 0.001 and bb[1] <= y1 + 0.001:
            xs.append(round((bb[0] + bb[2]) / 2, 4))
    return sorted(set(xs))


def calibrar(block: Any) -> None:
    """Mide el ancho medio de caracter del estilo de texto actual."""
    global CHW
    try:
        probe = block.AddText("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", variant_point(0, 0), 0.001)
        bb = bbox(probe)
        if bb and bb[2] > bb[0]:
            CHW = (bb[2] - bb[0]) / (36 * 0.001)
        probe.Delete()
    except Exception:  # noqa: BLE001
        pass


def limpiar_membrete(doc: Any, name: str, plano: str, lamina: str, escala: str) -> list[str]:
    """Deja el cajete UCV con los datos escritos y sin rotulos duplicados."""
    activate(doc, name)
    block = doc.PaperSpace
    log: list[str] = []
    calibrar(block)

    cel = cajete_cells(block)
    rows = cel["rows"]
    lam_box = cel["lamina"]

    # --- borrar solo LETRAS y duplicados de la capa A-ROTULO ----------------
    etiquetas = {
        "ALUMNO",
        "TEMA",
        "PROFESOR",
        "FECHA",
        "ESCALA",
        "CICLO",
        "LAMINA",
        "PLANO",
        "UNIVERSIDADCESARVALLEJO",
    }
    for i in range(int(block.Count) - 1, -1, -1):
        e = block.Item(i)
        try:
            lay = str(e.Layer)
            typ = str(e.ObjectName)
        except Exception:  # noqa: BLE001
            continue
        bb = bbox(e)
        if lay == ROTULO:
            # marco duplicado (200x287), logo suelto y rotulos: se rehacen
            if typ in ("AcDbText", "AcDbMText", "AcDbLine", "AcDbPolyline", "AcDbArc", "AcDbHatch"):
                e.Delete()
                log.append(f"  {typ} retirado")
        elif lay in (MARCO, "cota") and typ in ("AcDbMText", "AcDbText"):
            valor = str(getattr(e, "TextString", ""))
            limpio = re.sub(r"\{\\[^;]*;", "", valor)
            limpio = re.sub(r"[^A-Za-z]", "", limpio).upper()
            dentro_lamina = (
                lam_box is not None
                and bb is not None
                and lam_box[0] - 0.0005 < (bb[0] + bb[2]) / 2 < lam_box[2] + 0.0005
                and lam_box[1] - 0.0005 < (bb[1] + bb[3]) / 2 < lam_box[3] + 0.0005
            )
            if limpio in etiquetas or valor.strip().startswith("-") or dentro_lamina:
                e.Delete()
                log.append(f"  etiqueta cajete: {valor[:28]!r}")

    # --- filas del cajete: universidad/alumno, tema, profesor, pie ----------
    def escribir(
        row: tuple[float, float, float, float],
        valor: str,
        alto: float,
        color: int = WHITE,
        y_rel: float = 0.5,
    ) -> None:
        h = fit_height(valor, (row[2] - row[0]) - 0.002, alto)
        y = row[1] + (row[3] - row[1]) * y_rel - h * 0.5
        text(block, valor, row[0] + 0.0012, max(row[1] + 0.0004, y), h, color)

    # fila 0: universidad (arriba) + alumno (abajo)
    r0 = rows[0]
    escribir(r0, "UNIVERSIDAD CESAR VALLEJO", 0.0012, RED, y_rel=0.78)
    escribir(r0, f"ALUMNO: {ALUMNO}", 0.0015, WHITE, y_rel=0.25)

    escribir(rows[1], f"TEMA: {PROYECTO}", 0.0017, BLUE)
    escribir(rows[2], f"PROFESOR: {PROFESOR}", 0.0015)

    # filas restantes: pie del cajete (A3 tiene una fila extra para el plano)
    pie = rows[3:]
    if len(pie) >= 2:
        r = pie[0]
        ancho = (r[2] - r[0]) - 0.002
        variantes = [
            f"PLANO: {plano}    |    {CURSO}",
            CURSO,
            f"PLANO: {plano}",
        ]
        elegido = next(
            (v for v in variantes if ancho / (len(v) * CHW) >= 0.0011),
            variantes[-1],
        )
        escribir(r, elegido, 0.0015)
        pie = pie[1:]

    ult = pie[0]
    dividers_x = [d for d in dividers(block, ult[1], ult[3]) if ult[0] < d < ult[2]]
    cortes = [ult[0]] + dividers_x + [ult[2]]
    etiquetas_pie = ["FECHA", "ESCALA", "CICLO", "PLANO"]
    valores_pie = [FECHA, escala, CICLO, plano.split("|")[0].strip()]
    alto_fila = ult[3] - ult[1]
    for i in range(len(cortes) - 1):
        a, b = cortes[i], cortes[i + 1]
        if b - a < 0.004 or i >= len(valores_pie):
            continue
        valor = valores_pie[i]
        centro = (a + b) / 2
        etiqueta = etiquetas_pie[i]
        text(
            block,
            etiqueta,
            centro,
            ult[1] + alto_fila * 0.62,
            0.0008,
            GREY,
            align=1,
        )
        h = fit_height(valor, (b - a) - 0.0015, 0.0016)
        text(block, valor, centro, ult[1] + max(0.0004, alto_fila * 0.12), h, align=1)

    # columna LAMINA
    if lam_box:
        centro = (lam_box[0] + lam_box[2]) / 2
        text(block, "LAMINA", centro, lam_box[3] - 0.0016, 0.0008, GREY, align=1)
        h = fit_height(lamina, (lam_box[2] - lam_box[0]) - 0.0015, 0.0018)
        text(
            block,
            lamina,
            centro,
            lam_box[1] + max(0.0004, (lam_box[3] - lam_box[1]) * 0.22),
            h,
            BLUE,
            align=1,
        )

    return log


# --------------------------------------------------------------------------- #
# laminas nuevas
# --------------------------------------------------------------------------- #
def page_setup(doc: Any, layout: Any, media: str) -> None:
    pc3 = (
        Path.home()
        / "AppData"
        / "Roaming"
        / "Autodesk"
        / "AutoCAD 2026"
        / "R25.1"
        / "enu"
        / "plotters"
        / "DWG To PDF.pc3"
    )
    try:
        if pc3.exists():
            layout.ConfigName = str(pc3)
            layout.RefreshPlotDeviceInfo()
    except Exception:  # noqa: BLE001
        pass
    layout.CanonicalMediaName = media
    layout.StyleSheet = "acad.ctb"
    layout.PlotType = 5
    layout.UseStandardScale = False
    layout.SetCustomScale(1000.0, 1.0)
    layout.PlotRotation = 0
    layout.PaperUnits = 1
    layout.PlotWithPlotStyles = True
    layout.PlotWithLineweights = True
    layout.ScaleLineweights = False
    try:
        layout.PlotViewportBorders = False
        layout.CenterPlot = False
    except Exception:  # noqa: BLE001
        pass


A4 = "ISO_full_bleed_A4_(210.00_x_297.00_MM)"


def nueva_lamina(doc: Any, name: str) -> tuple[Any, Any]:
    if not reintentar(lambda: doc.Layouts.Item(name).Delete(), f"borrar {name}", 3):
        pass
    wait(0.4)
    hecho = reintentar(lambda: doc.Layouts.Add(name), f"crear layout {name}")
    if not hecho:
        raise RuntimeError(f"AutoCAD no dejo crear el layout {name}")
    layout = doc.Layouts.Item(name)
    wait(0.8)
    activate(doc, name)
    page_setup(doc, layout, A4)
    block = doc.PaperSpace
    return layout, block


def marco(block: Any, w: float, h: float) -> None:
    rect(block, 0.005, 0.005, w - 0.005, h - 0.005, RED, weight=-2)
    rect(block, 0.010, 0.010, w - 0.010, h - 0.010, RED, weight=-3)


def logo(block: Any, x0: float, y0: float, size: float = 0.020) -> list[Any]:
    """Escudo UCV aproximado (mallete + arcos) dibujado con lineas."""
    s = size / 2.05
    tx = x0 + size / 2
    ty = y0
    pts = [
        (-0.50, 0.00),
        (-0.45, 1.30),
        (-0.30, 1.75),
        (-0.10, 1.95),
        (0.00, 2.05),
        (0.10, 1.95),
        (0.30, 1.75),
        (0.45, 1.30),
        (0.50, 0.00),
        (-0.50, 0.00),
    ]
    coords: list[float] = []
    for px, py in pts:
        coords.extend((tx + px * s, ty + py * s))
    e = block.AddLightWeightPolyline(variant_array(coords))
    style(e, ROTULO, RED)
    for r, cy in ((0.42, 0.85), (0.30, 0.95), (0.18, 1.05)):
        style(block.AddArc(variant_point(tx, ty + cy * s, 0.0), r * s, 180.0, 360.0), ROTULO, RED)
    for x, y0_, y1_ in ((-0.18, 0.45, 0.85), (-0.08, 0.45, 0.85)):
        style(
            block.AddLine(
                variant_point(tx + x * s, ty + y0_ * s), variant_point(tx + x * s, ty + y1_ * s)
            ),
            ROTULO,
            RED,
        )
    style(
        block.AddArc(variant_point(tx - 0.13 * s, ty + 0.85 * s, 0.0), 0.05 * s, 180.0, 360.0),
        ROTULO,
        RED,
    )
    style(
        block.AddLine(
            variant_point(tx + 0.08 * s, ty + 0.45 * s), variant_point(tx + 0.13 * s, ty + 0.80 * s)
        ),
        ROTULO,
        RED,
    )
    style(
        block.AddLine(
            variant_point(tx + 0.13 * s, ty + 0.80 * s), variant_point(tx + 0.18 * s, ty + 0.45 * s)
        ),
        ROTULO,
        RED,
    )
    style(block.AddArc(variant_point(tx, ty + 0.62 * s, 0.0), 0.04 * s, 0.0, 360.0), ROTULO, RED)
    return []


def logo_real(doc: Any, block: Any, x0: float, y0: float, alto: float = 0.026) -> bool:
    """Copia el escudo del cajete original (A4_PA) y lo reubica/escala."""
    try:
        activate(doc, "A4_PA")
        src = doc.PaperSpace
        cel = cajete_cells(src)
        rows = cel["rows"]
        x_izq = min(r[0] for r in rows)
        y_bajo = min(r[1] for r in rows) - 0.002
        y_alto = max(r[3] for r in rows) + 0.002
        grupo = []
        for i in range(int(src.Count)):
            e = src.Item(i)
            try:
                if str(e.Layer) != MARCO:
                    continue
            except Exception:  # noqa: BLE001
                continue
            bb = bbox(e)
            if not bb:
                continue
            if bb[2] <= x_izq + 0.0005 and bb[1] >= y_bajo and bb[3] <= y_alto:
                grupo.append(e)
        if not grupo:
            return False

        bb0 = [
            min(bbox(e)[0] for e in grupo),
            min(bbox(e)[1] for e in grupo),
            max(bbox(e)[2] for e in grupo),
            max(bbox(e)[3] for e in grupo),
        ]
        alto0 = bb0[3] - bb0[1]
        base = variant_point(bb0[0], bb0[1], 0.0)
        res = doc.CopyObjects(variant_objects(grupo), block)
        copies = res[0] if isinstance(res, tuple) else res
        k = alto / alto0 if alto0 > 0 else 1.0
        for raw in copies:
            ent = as_dynamic(raw)
            try:
                ent.ScaleEntity(base, k)
                ent.Move(base, variant_point(x0, y0, 0.0))
            except Exception:  # noqa: BLE001
                pass
        return True
    except Exception:  # noqa: BLE001
        return False


def cajete(
    doc: Any,
    block: Any,
    w: float,
    lamina: str,
    plano: str,
    escala: str,
) -> float:
    """Membrete horizontal limpio abajo. Devuelve la cota superior del cajete."""
    x0, x1 = 0.010, w - 0.010
    y0, y1 = 0.010, 0.042
    rect(block, x0, y0, x1, y1, RED, weight=-2)
    if not logo_real(doc, block, x0 + 0.003, y0 + 0.002, 0.024):
        logo(block, x0 + 0.004, y0 + 0.004, 0.026)
    xt = x0 + 0.034
    line(block, xt, y0, xt, y1, RED, weight=-2)

    col2 = x1 - 0.052
    line(block, col2, y0, col2, y1, RED, weight=-2)
    for yy in (0.018, 0.026, 0.034):
        line(block, xt, yy, x1, yy, RED, weight=-3)

    text(block, "UNIVERSIDAD CESAR VALLEJO", xt + 0.002, y1 - 0.0055, 0.0016, RED)
    text(block, PROYECTO, col2 + 0.002, y1 - 0.0055, 0.0015, BLUE)
    text(block, f"LAMINA: {lamina}", col2 + 0.002, 0.0288, 0.0020, BLUE)
    text(block, f"ESCALA: {escala}", col2 + 0.002, 0.0208, 0.0016)
    text(block, f"FECHA: {FECHA}", col2 + 0.002, 0.0128, 0.0016)

    text(block, f"PLANO: {plano}", xt + 0.002, 0.0288, 0.0022, WHITE)
    text(block, f"ALUMNO: {ALUMNO}", xt + 0.002, 0.0208, 0.0017)
    text(block, f"PROFESOR: {PROFESOR}", xt + 0.002, 0.0128, 0.0017)
    return y1


def encabezado(block: Any, w: float, titulo: str, subtitulo: str = "") -> None:
    text(block, titulo, 0.010, 0.278, 0.0034, BLUE)
    if subtitulo:
        text(block, subtitulo, 0.010, 0.2705, 0.0018, WHITE)
    line(block, 0.010, 0.268, w - 0.010, 0.268, BLUE, weight=-4)


# --------------------------------------------------------------------------- #
# datos del dibujo
# --------------------------------------------------------------------------- #
FAMILIAS = (
    ("A-PUERTA", "PUERTAS"),
    ("A-NORTE", "SIMBOLOS"),
    ("OBJ-PLANTA", "VEGETACION"),
    ("OBJ-INODORO", "SANITARIOS"),
    ("OBJ-LAVAMANOS", "SANITARIOS"),
    ("OBJ-DUCHA", "SANITARIOS"),
    ("OBJ-TINA", "SANITARIOS"),
    ("OBJ-LAVADERO", "SANITARIOS"),
    ("OBJ-LAVAPLATOS", "SANITARIOS"),
    ("OBJ-LAVADORA", "SERVICIOS"),
    ("OBJ-REFRI", "ELECTRO"),
    ("OBJ-MICROONDAS", "ELECTRO"),
    ("OBJ-ISLA-COCINA", "COCINA"),
)


def familia(nombre: str) -> str:
    for pref, fam in FAMILIAS:
        if nombre.startswith(pref):
            return fam
    return "MOBILIARIO"


def medidas_bloque(doc: Any, nombre: str) -> tuple[float, float]:
    """Ancho y largo (m) de la definicion del bloque."""
    try:
        definition = doc.Blocks.Item(nombre)
    except Exception:  # noqa: BLE001
        return (0.0, 0.0)
    x0, y0, x1, y1 = 1e9, 1e9, -1e9, -1e9
    for i in range(int(definition.Count)):
        bb = bbox(definition.Item(i))
        if not bb:
            continue
        x0, y0 = min(x0, bb[0]), min(y0, bb[1])
        x1, y1 = max(x1, bb[2]), max(y1, bb[3])
    if x1 < x0:
        return (0.0, 0.0)
    return (round(x1 - x0, 2), round(y1 - y0, 2))


def inventario(doc: Any) -> list[dict[str, Any]]:
    usos: dict[str, int] = {}
    ms = doc.ModelSpace
    for i in range(int(ms.Count)):
        try:
            e = ms.Item(i)
            if str(e.ObjectName) == "AcDbBlockReference":
                usos[str(e.Name)] = usos.get(str(e.Name), 0) + 1
        except Exception:  # noqa: BLE001
            continue

    filas: list[dict[str, Any]] = []
    for i in range(int(doc.Blocks.Count)):
        try:
            nombre = str(doc.Blocks.Item(i).Name)
        except Exception:  # noqa: BLE001
            continue
        if nombre.startswith(("*", "_")):
            continue
        if not (nombre.startswith("OBJ-") or nombre.startswith("A-")):
            continue
        ancho, largo = medidas_bloque(doc, nombre)
        filas.append(
            {
                "nombre": nombre,
                "familia": familia(nombre),
                "ancho": ancho,
                "largo": largo,
                "usos": usos.get(nombre, 0),
            }
        )
    filas.sort(key=lambda r: (r["familia"], r["nombre"]))
    return filas


def cuadro_ambientes(doc: Any) -> list[list[str]]:
    """Reconstruye el cuadro de datos desde los rotulos del modelo."""
    ms = doc.ModelSpace
    celdas: list[tuple[float, float, str]] = []
    for i in range(int(ms.Count)):
        try:
            e = ms.Item(i)
            if str(e.ObjectName) not in ("AcDbText", "AcDbMText"):
                continue
            lay = str(e.Layer)
            if lay != "A-TEXTOS":
                continue
            ip = e.InsertionPoint
            x, y = f(ip[0]), f(ip[1])
            if not (45.0 < x < 62.5 and 8.4 < y < 17.6):
                continue
            celdas.append((round(x, 2), round(y, 2), str(e.TextString).strip()))
        except Exception:  # noqa: BLE001
            continue

    por_y: dict[float, list[tuple[float, str]]] = {}
    for x, y, txt in celdas:
        por_y.setdefault(y, []).append((x, txt))

    columnas = [47.27, 49.47, 55.85, 58.05, 60.29]
    filas: list[list[str]] = []
    for y in sorted(por_y, reverse=True):
        items = sorted(por_y[y])
        fila = [""] * len(columnas)
        for x, txt in items:
            idx = min(range(len(columnas)), key=lambda i: abs(columnas[i] - x))
            if fila[idx]:
                fila[idx] += " " + txt
            else:
                fila[idx] = txt
        if any(fila):
            filas.append(fila)
    return filas


# --------------------------------------------------------------------------- #
# laminas
# --------------------------------------------------------------------------- #
def catalogo(doc: Any, bloques: list[dict[str, Any]], inicio: int, name: str, numero: int) -> None:
    w, h = 0.210, 0.297
    _, block = nueva_lamina(doc, name)
    marco(block, w, h)
    encabezado(
        block,
        w,
        "CATALOGO DE BLOQUES - BIBLIOTECA DE OBJETOS",
        "Mobiliario, sanitarios, electrodomesticos, vegetacion, "
        "simbolos y puertas. Medidas en metros.",
    )
    cajete(doc, block, w, f"A-0{numero}", "CATALOGO DE BLOQUES", "1:125")

    cols, rows = 4, 5
    x0, y0 = 0.010, 0.046
    x1, y1 = w - 0.010, 0.262
    cw = (x1 - x0) / cols
    ch = (y1 - y0) / rows
    escala = 0.008  # 1:125 con el modelo en metros

    for idx in range(cols * rows):
        k = inicio + idx
        cx = x0 + (idx % cols) * cw
        cy = y1 - (idx // cols + 1) * ch
        rect(block, cx + 0.001, cy + 0.001, cx + cw - 0.001, cy + ch - 0.001, GREY, weight=-1)
        if k >= len(bloques):
            continue
        b = bloques[k]
        # caja del bloque
        bx = cx + 0.002
        by = cy + 0.011
        bw = cw - 0.004
        ch - 0.014
        try:
            ref = block.InsertBlock(
                variant_point(cx + cw / 2, cy + ch / 2 + 0.004),
                b["nombre"],
                escala,
                escala,
                escala,
                0.0,
            )
            bb = bbox(ref)
            if bb:
                dx = (cx + cw / 2) - (bb[0] + bb[2]) / 2
                dy = (cy + ch / 2 + 0.004) - (bb[1] + bb[3]) / 2
                ref.Move(variant_point(0, 0, 0), variant_point(dx, dy, 0))
            try:
                ref.Layer = "A-MOBILIARIO"
            except Exception:  # noqa: BLE001
                pass
        except Exception as exc:  # noqa: BLE001
            text(block, f"(no se pudo insertar) {exc}", bx, by, 0.0010, RED)

        nombre = b["nombre"]
        alto = fit_height(nombre, bw, 0.0017)
        text(block, nombre, cx + 0.002, cy + 0.0068, alto, WHITE)
        dims = f"{b['ancho']:.2f} x {b['largo']:.2f} m  |  {b['familia']}"
        text(block, dims, cx + 0.002, cy + 0.0030, fit_height(dims, bw, 0.0013), GREY)


def biblioteca(doc: Any, bloques: list[dict[str, Any]]) -> None:
    w, h = 0.210, 0.297
    ancho_total = w - 0.020
    cols = [0.012, 0.080, 0.038, 0.020, 0.020, 0.020]
    factor = ancho_total / sum(cols)
    cols = [c * factor for c in cols]

    for parte, (ini, fin) in enumerate(((0, 17), (17, 34)), start=1):
        nombre = f"A4_BIBLIOTECA_{parte}"
        _, block = nueva_lamina(doc, nombre)
        marco(block, w, h)
        encabezado(
            block,
            w,
            f"BIBLIOTECA DE BLOQUES - INDICE ({parte}/2)",
            "Listado de bloques usados en las plantas, con medidas y "
            "numero de inserciones en el modelo.",
        )
        cajete(doc, block, w, f"A-0{5 + parte}", "BIBLIOTECA DE BLOQUES", "S/E")

        data = [["N", "BLOQUE", "FAMILIA", "ANCHO", "LARGO", "USOS"]]
        for i, b in enumerate(bloques[ini:fin], start=ini + 1):
            data.append(
                [
                    str(i),
                    b["nombre"],
                    b["familia"],
                    f"{b['ancho']:.2f}",
                    f"{b['largo']:.2f}",
                    str(b["usos"]),
                ]
            )

        tabla(
            block,
            data,
            (0.010, 0.258),
            (0.258 - 0.050) / (len(data) + 1),
            cols,
            0.0015,
            [5, 0, 0, 5, 5, 5],
            titulo="BIBLIOTECA DE BLOQUES - MOBILIARIO Y EQUIPAMIENTO",
            max_alto=0.208,
        )


def datos(doc: Any, filas: list[list[str]]) -> list[list[str]]:
    w, h = 0.210, 0.297
    _, block = nueva_lamina(doc, "A4_DATOS")
    marco(block, w, h)
    encabezado(
        block,
        w,
        "CUADRO DE DATOS TECNICOS - AMBIENTES",
        "Tabla nativa de AutoCAD (AcDbTable), editable y exportable a "
        "Excel. Dimensiones y areas en metros.",
    )
    cajete(doc, block, w, "A-08", "CUADRO DE DATOS", "S/E")

    # normalizar: 5 columnas, encabezado legible
    limpio: list[list[str]] = []
    for fila in filas:
        vals = list(fila)
        vals += [""] * (5 - len(vals))
        vals = vals[:5]
        # se descartan titulo/nota del cuadro original: ya estan en la lamina
        if sum(1 for c in vals if str(c).strip()) <= 1:
            continue
        if str(vals[0]).strip().upper() == "NIVEL":
            continue
        limpio.append(vals)

    data = [["NIVEL", "AMBIENTE", "ANCHO", "LARGO", "AREA"]]
    for vals in limpio:
        nivel, ambiente, ancho, largo, area = vals
        data.append([nivel, ambiente, ancho, largo, area])

    ancho_total = w - 0.020
    cols = [0.026, 0.088, 0.024, 0.024, 0.024]
    factor = ancho_total / sum(cols)
    cols = [c * factor for c in cols]
    tabla(
        block,
        data,
        (0.010, 0.258),
        0.0068,
        cols,
        0.0016,
        [0, 0, 5, 5, 5],
        max_alto=0.212,
    )
    return limpio


def tabla(
    block: Any,
    data: list[list[str]],
    origen: tuple[float, float],
    alto_fila: float,
    cols: list[float],
    alto_texto: float,
    alineacion: list[int] | None = None,
    titulo: str | None = None,
    max_alto: float | None = None,
) -> Any:
    """Tabla AcDbTable.

    AutoCAD reserva una fila de titulo (0-based), asi que los datos empiezan en
    la fila 1. Ademas no acepta filas/columnas por debajo de ~3 unidades: la
    tabla se construye a escala 1000 (mm) y despues se reduce al tamano de la
    hoja (que trabaja en metros). Sigue siendo un AcDbTable nativo y editable.
    """
    filas, columnas = len(data), len(cols)
    # AutoCAD no acepta filas de menos de ~9 unidades: se elige la escala de
    # construccion para que la fila nativa quede justo por encima de ese minimo
    # y, al reducir, la fila final sea exactamente `alto_fila`.
    s = max(100.0, 9.6 / alto_fila) if alto_fila > 0 else 1000.0
    total_filas = filas + (1 if titulo else 0)
    t = block.AddTable(
        variant_point(origen[0], origen[1]),
        total_filas,
        columnas,
        float(alto_fila * s),
        float(cols[0] * s),
    )
    try:
        t.Layer = ROTULO
    except Exception:  # noqa: BLE001
        pass

    desplazamiento = 1 if titulo else 0
    for r in range(filas):
        for c in range(columnas):
            valor = data[r][c] if c < len(data[r]) else ""
            try:
                t.SetText(r + desplazamiento, c, valor)
            except Exception:  # noqa: BLE001
                try:
                    t.SetTextString(r + desplazamiento, c, valor)
                except Exception:  # noqa: BLE001
                    pass
            try:
                t.SetCellTextHeight(r + desplazamiento, c, float(alto_texto * s))
            except Exception:  # noqa: BLE001
                pass
            alin = 5
            if alineacion:
                alin = alineacion[c]
            try:
                t.SetCellAlignment(r + desplazamiento, c, alin)
            except Exception:  # noqa: BLE001
                pass
    if titulo:
        try:
            t.SetText(0, 0, titulo)
            t.SetCellTextHeight(0, 0, float(alto_texto * 1.25 * s))
            t.SetCellAlignment(0, 0, 5)
        except Exception:  # noqa: BLE001
            pass
        try:
            t.MergeCells(0, 0, 0, columnas - 1)
        except Exception:  # noqa: BLE001
            pass
    for r in range(total_filas):
        try:
            t.SetRowHeight(r, float(alto_fila * s))
        except Exception:  # noqa: BLE001
            pass
    for c, ancho in enumerate(cols):
        try:
            t.SetColumnWidth(c, float(ancho * s))
        except Exception:  # noqa: BLE001
            pass

    try:
        t.ScaleEntity(variant_point(origen[0], origen[1], 0.0), 1.0 / s)
    except Exception:  # noqa: BLE001
        pass

    # AutoCAD impone un minimo de altura de fila: si la tabla no entra en la
    # lamina se reduce de nuevo, manteniendo la esquina superior izquierda.
    if max_alto:
        bb = bbox(t)
        if bb and (bb[3] - bb[1]) > max_alto:
            k = max_alto / (bb[3] - bb[1])
            try:
                t.ScaleEntity(variant_point(origen[0], origen[1], 0.0), k)
            except Exception:  # noqa: BLE001
                pass
    return t


# --------------------------------------------------------------------------- #
# excel
# --------------------------------------------------------------------------- #
def exportar_excel(filas: list[list[str]], path: Path) -> bool:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
    except Exception:  # noqa: BLE001
        return exportar_csv(filas, path.with_suffix(".csv"))

    wb = Workbook()
    ws = wb.active
    ws.title = "CUADRO DE DATOS"
    ws.append(["NIVEL", "AMBIENTE", "ANCHO (m)", "LARGO (m)", "AREA (m2)"])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E79")
        cell.alignment = Alignment(horizontal="center")
    for fila in filas:
        if str(fila[0]).strip().upper() == "NIVEL":
            continue
        ws.append([fila[0], fila[1], f(fila[2]), f(fila[3]), f(fila[4])])
    for col, ancho in zip("ABCDE", (16, 30, 11, 11, 11), strict=False):
        ws.column_dimensions[col].width = ancho
    ws.freeze_panes = "A2"
    wb.save(path)
    return True


def exportar_csv(filas: list[list[str]], path: Path) -> bool:
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["NIVEL", "AMBIENTE", "ANCHO (m)", "LARGO (m)", "AREA (m2)"])
        writer.writerows(filas)
    return True


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    pythoncom.CoInitialize()
    app = win32com.client.GetActiveObject("AutoCAD.Application.25.1")
    doc = app.ActiveDocument
    doc.Activate()
    print("documento:", doc.Name)

    if doc.Saved is False:
        if reintentar(doc.Save, "guardar estado previo"):
            print("guardado el estado actual antes de trabajar")

    backup_dir = ROOT / "out" / "backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    backup = backup_dir / f"{Path(str(doc.FullName)).stem}_{stamp}.dwg"
    shutil.copy2(str(doc.FullName), backup)
    print("respaldo:", backup)

    if dry:
        print("(dry-run) no se modifica nada")
        return 0

    layer(doc, ROTULO, RED)
    layer(doc, "A-BLOQUES", WHITE, True)

    # 1. membretes existentes -------------------------------------------------
    planos = {
        "A4_PB": ("PLANTA BAJA", "A-01", "1:100", A4),
        "A4_PA": ("PLANTA ALTA", "A-02", "1:100", A4),
        "A3_D": (
            "PLANTAS + ZONIFICACION",
            "A-03",
            "1:125",
            "ISO_full_bleed_A3_(420.00_x_297.00_MM)",
        ),
    }
    for name, (plano, lamina, escala, media) in planos.items():
        try:
            log = limpiar_membrete(doc, name, plano, lamina, escala)
            page_setup(doc, doc.Layouts.Item(name), media)
            print(f"{name}: {len(log)} elementos retirados, page setup OK")
        except Exception as exc:  # noqa: BLE001
            print(f"{name}: ERROR {exc}")

    # 2. datos ---------------------------------------------------------------
    bloques = inventario(doc)
    filas = cuadro_ambientes(doc)
    print(f"bloques: {len(bloques)} | filas de cuadro: {len(filas)}")

    (ROOT / "out").mkdir(exist_ok=True)

    # 3. laminas nuevas ------------------------------------------------------
    for viejo in ("A4_BIBLIOTECA",):
        try:
            doc.Layouts.Item(viejo).Delete()
        except Exception:  # noqa: BLE001
            pass
    catalogo(doc, bloques, 0, "A4_BLOQUES_1", 4)
    catalogo(doc, bloques, 20, "A4_BLOQUES_2", 5)
    biblioteca(doc, bloques)
    filas_limpias = datos(doc, filas)
    print("laminas creadas: A4_BLOQUES_1, A4_BLOQUES_2, A4_BIBLIOTECA_1, A4_BIBLIOTECA_2, A4_DATOS")

    xlsx = ROOT / "out" / "cuadro_datos.xlsx"
    exportar_excel(filas_limpias, xlsx)
    print("excel:", xlsx)

    # 4. volver al modelo y guardar -----------------------------------------
    reintentar(lambda: setattr(doc, "ActiveLayout", doc.Layouts.Item("Model")), "ir a Model")
    reintentar(lambda: doc.SetVariable("CTAB", "Model"), "CTAB=Model")
    reintentar(lambda: doc.Regen(1), "regen")
    reintentar(doc.Save, "guardar")
    print("guardado:", doc.FullName)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
