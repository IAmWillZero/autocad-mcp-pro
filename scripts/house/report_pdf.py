"""Genera el informe tecnico del anteproyecto UCV Magisterial 230 en PDF.

El documento se escribe en el Escritorio y resume el estado verificado del DWG:
areas, zonificacion, puertas, ventanas, escalera, mobiliario y correcciones.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

import pymupdf as fitz

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "house"))

import ucv_areas as AR  # noqa: E402
import ucv_data as U  # noqa: E402

OUT = Path.home() / "Desktop" / "Informe_Vivienda_UCV_Magisterial_230.pdf"
PREVIEW = ROOT / "out" / "informe_pagina"

W, H = 595.0, 842.0
M = 42.0
NAVY = (0.055, 0.105, 0.190)
BLUE = (0.090, 0.300, 0.560)
TEAL = (0.000, 0.500, 0.500)
GOLD = (0.780, 0.580, 0.160)
INK = (0.120, 0.140, 0.170)
GRAY = (0.390, 0.420, 0.460)
LIGHT = (0.945, 0.955, 0.970)
PALE = (0.975, 0.978, 0.985)
RED = (0.650, 0.130, 0.130)
GREEN = (0.120, 0.430, 0.240)
WHITE = (1.0, 1.0, 1.0)
ZONE_RGB = {
    "SOC": (0.760, 0.180, 0.470),
    "SER": (0.150, 0.360, 0.760),
    "PRI": (0.160, 0.540, 0.300),
    "CIR": (0.850, 0.650, 0.120),
    "LIB": (0.480, 0.680, 0.300),
}


def fmt(v: float, dec: int = 2) -> str:
    return f"{v:.{dec}f}"


_ACCENTS = {
    "Informe tecnico": "Informe técnico",
    "INFORME TECNICO": "INFORME TÉCNICO",
    "tecnico": "técnico",
    "Tecnico": "Técnico",
    "zonificacion": "zonificación",
    "Zonificacion": "Zonificación",
    "ZONIFICACION": "ZONIFICACIÓN",
    "areas": "áreas",
    "Areas": "Áreas",
    "area": "área",
    "Area": "Área",
    "AREA": "ÁREA",
    "diseno": "diseño",
    "Diseno": "Diseño",
    "DISENO": "DISEÑO",
    "construccion": "construcción",
    "Construccion": "Construcción",
    "CONSTRUCCION": "CONSTRUCCIÓN",
    "lamina": "lámina",
    "Lamina": "Lámina",
    "LAMINA": "LÁMINA",
    "acotacion": "acotación",
    "Acotacion": "Acotación",
    "modulacion": "modulación",
    "Modulacion": "Modulación",
    "albanileria": "albañilería",
    "Albanileria": "Albañilería",
    "precusion": "precisión",
    "Precusion": "Precisión",
    "medulos": "módulos",
    "Medulos": "Módulos",
    "redisenaron": "rediseñaron",
    "rediseno": "rediseño",
    "Rediseno": "Rediseño",
    "garage": "garaje",
    "Garage": "Garaje",
    "porton": "portón",
    "Porton": "Portón",
    "balcon": "balcón",
    "Balcon": "Balcón",
    "verificacion": "verificación",
    "Verificacion": "Verificación",
    "tipologia": "tipología",
    "Tipologia": "Tipología",
    "parametro": "parámetro",
    "Parametro": "Parámetro",
    "linea": "línea",
    "Linea": "Línea",
    "rotulo": "rótulo",
    "Rotulo": "Rótulo",
    "rotulos": "rótulos",
    "revision": "revisión",
    "Revision": "Revisión",
    "version": "versión",
    "Version": "Versión",
    "automatizacion": "automatización",
    "Automatizacion": "Automatización",
    "arquitectonico": "arquitectónico",
    "Arquitectonico": "Arquitectónico",
    "arquitectonicas": "arquitectónicas",
    "Arquitectonicas": "Arquitectónicas",
    "circulacion": "circulación",
    "Circulacion": "Circulación",
    "ubicacion": "ubicación",
    "Ubicacion": "Ubicación",
    "observacion": "observación",
    "Observacion": "Observación",
    "conclusion": "conclusión",
    "Conclusion": "Conclusión",
    "lavanderia": "lavandería",
    "Lavanderia": "Lavandería",
    "jardin": "jardín",
    "Jardin": "Jardín",
    "maximo": "máximo",
    "maxima": "máxima",
    "minimo": "mínimo",
    "minima": "mínima",
    "publico": "público",
    "publica": "pública",
    "practico": "práctico",
    "practica": "práctica",
    "basico": "básico",
    "basica": "básica",
    "numerico": "numérico",
    "analisis": "análisis",
    "diagnostico": "diagnóstico",
    "electrico": "eléctrico",
    "hidraulico": "hidráulico",
    "acustico": "acústico",
    "termico": "térmico",
    "fisico": "físico",
    "logico": "lógico",
    "tecnica": "técnica",
    "Tecnica": "Técnica",
    "tecnicos": "técnicos",
    "Tecnicos": "Técnicos",
    "REVISION": "REVISIÓN",
    "precision": "precisión",
    "deficit": "déficit",
    "Deficit": "Déficit",
    "opcion": "opción",
    "Opcion": "Opción",
    "Minimo": "Mínimo",
    "Maxima": "Máxima",
    "intervencion": "intervención",
    "Intervencion": "Intervención",
    "confirmacion": "confirmación",
    "modifico": "modificó",
    "parametros": "parámetros",
    "computo": "cómputo",
    "cimentacion": "cimentación",
    "sismicos": "sísmicos",
    "electricas": "eléctricas",
    "evacuacion": "evacuación",
    "impermeabilizacion": "impermeabilización",
    "tecnicas": "técnicas",
    "ingenieria": "ingeniería",
    "nivelacion": "nivelación",
    "urbanistico": "urbanístico",
    "Urbanistico": "Urbanístico",
    "quedaria": "quedaría",
    "geometria": "geometría",
    "geometrica": "geométrica",
    "geometrico": "geométrico",
    "implicaria": "implicaría",
    "unico": "único",
    "unica": "única",
    "ademas": "además",
    "corrigio": "corrigió",
    "segun": "según",
    "carpinteria": "carpintería",
    "calculo": "cálculo",
    "calculos": "cálculos",
    "formula": "fórmula",
    "metodo": "método",
    "logica": "lógica",
    "fisica": "física",
    "critica": "crítica",
    "tipica": "típica",
    "sintesis": "síntesis",
    "energia": "energía",
    "practicas": "prácticas",
    "decision": "decisión",
    "amplio": "amplió",
    "informacion": "información",
    "comunicacion": "comunicación",
    "edificacion": "edificación",
    "distribucion": "distribución",
    "ampliacion": "ampliación",
    "especificacion": "especificación",
    "documentacion": "documentación",
    "senalizacion": "señalización",
    "iluminacion": "iluminación",
    "ventilacion": "ventilación",
    "superposicion": "superposición",
}


def accent(s: str) -> str:
    for src, dst in sorted(_ACCENTS.items(), key=lambda kv: len(kv[0]), reverse=True):
        s = re.sub(rf"\b{re.escape(src)}\b", dst, s)
    return s


def txt(page, x, y, s, size=9, font="helv", color=INK):
    page.insert_text((x, y), accent(str(s)), fontname=font, fontsize=size, color=color)


def para(page, x, y, w, h, s, size=9, font="helv", color=INK, leading=1.25):
    return page.insert_textbox(
        fitz.Rect(x, y, x + w, y + h),
        accent(str(s)),
        fontname=font,
        fontsize=size,
        color=color,
        lineheight=leading,
        align=fitz.TEXT_ALIGN_LEFT,
    )


def rect(page, x0, y0, x1, y1, color=INK, fill=None, width=0.7, opacity=1.0):
    page.draw_rect(
        fitz.Rect(x0, y0, x1, y1),
        color=color,
        fill=fill,
        width=width,
        fill_opacity=opacity,
    )


def line(page, x0, y0, x1, y1, color=GRAY, width=0.6):
    page.draw_line(fitz.Point(x0, y0), fitz.Point(x1, y1), color=color, width=width)


def header(page, section: str):
    rect(page, 0, 0, W, 60, color=NAVY, fill=NAVY, width=0)
    txt(page, M, 23, "VIVIENDA UCV MAGISTERIAL 230", 8, "hebo", WHITE)
    txt(page, M, 43, "Informe tecnico de anteproyecto", 15, "hebo", WHITE)
    label = accent(section)
    tw = fitz.get_text_length(label, "helv", 8)
    txt(page, W - M - tw, 23, section, 8, "helv", (0.80, 0.84, 0.90))
    date = "26 / 10 / 2026"
    dw = fitz.get_text_length(date, "helv", 8)
    txt(page, W - M - dw, 43, date, 8, "helv", (0.80, 0.84, 0.90))


def footer(page, n: int, total: int):
    line(page, M, H - 34, W - M, H - 34, LIGHT, 0.8)
    txt(page, M, H - 20, "Documento de anteproyecto - no apto para construccion", 7, "helv", GRAY)
    txt(page, W - M - 55, H - 20, f"Pag. {n} / {total}", 7, "hebo", GRAY)


def section(page, y, num: str, title: str, color=BLUE):
    txt(page, M, y, num, 15, "hebo", color)
    txt(page, M + 24, y, title, 13, "hebo", INK)
    line(page, M, y + 7, W - M, y + 7, (0.80, 0.84, 0.90), 0.7)
    return y + 22


def table(
    page,
    x,
    y,
    widths,
    headers,
    rows,
    row_h=13.5,
    size=7.5,
    aligns=None,
    header_size=7.5,
    zebra=True,
    header_color=NAVY,
):
    aligns = aligns or [0] * len(widths)
    total_w = sum(widths)
    rect(page, x, y, x + total_w, y + 17, color=header_color, fill=header_color, width=0)
    cx = x
    for i, head in enumerate(headers):
        al = aligns[i]
        tw = fitz.get_text_length(head, "helv", header_size)
        if al == 0:
            tx = cx + 4
        elif al == 1:
            tx = cx + widths[i] / 2 - tw / 2
        else:
            tx = cx + widths[i] - 4 - tw
        txt(page, tx, y + 11.5, head, header_size, "hebo", WHITE)
        cx += widths[i]
    cy = y + 17
    for j, row in enumerate(rows):
        if zebra and j % 2 == 1:
            rect(page, x, cy, x + total_w, cy + row_h, color=None, fill=PALE, width=0)
        cx = x
        for i, val in enumerate(row):
            al = aligns[i]
            if al == 0:
                tx = cx + 4
            elif al == 1:
                tx = cx + widths[i] / 2 - fitz.get_text_length(str(val), "helv", size) / 2
            else:
                tx = cx + widths[i] - 4 - fitz.get_text_length(str(val), "helv", size)
            txt(page, tx, cy + row_h * 0.68, str(val), size, "helv", INK)
            line(page, cx, cy, cx, cy + row_h, (0.86, 0.88, 0.91), 0.5)
            cx += widths[i]
        line(page, x, cy + row_h, x + total_w, cy + row_h, (0.86, 0.88, 0.91), 0.5)
        cy += row_h
    rect(page, x, y, x + total_w, cy, color=(0.76, 0.79, 0.84), width=0.7)
    return cy


def bullet(page, x, y, w, s, size=8.6, color=INK):
    txt(page, x, y, "•", size, "hebo", TEAL)
    remaining = para(page, x + 10, y - size, w - 10, 90, s, size, "helv", color, 1.18)
    used = 90.0 - max(0.0, remaining)
    return y + max(13.0, used + 4.0)


def zone_area(rooms, X, Y):
    out = Counter()
    for label, i0, i1, j0, j1 in rooms:
        cat = U.ZONE.get(label, "LIB")
        out[cat] += abs(X[i1] - X[i0]) * abs(Y[j1] - Y[j0])
    return out


ZS = 13.0

_ABBR = {
    "GARAJE": "GAR",
    "HALL": "HAL",
    "OFICINA": "OFI",
    "ESCALERA": "ESC",
    "CORREDOR": "COR",
    "SALA DE ESTAR": "SAL",
    "SS.HH. 1": "SS1",
    "LAVANDERIA": "LAV",
    "COCINA": "COC",
    "COMEDOR": "COM",
    "DORMITORIO 2": "D2",
    "DORMITORIO 3": "D3",
    "BALCON": "BAL",
    "TRAMO 2": "T2",
    "SS.HH. 3": "SS3",
    "DORMITORIO PRINCIPAL": "DP",
    "SS.HH. 2": "SS2",
    "VESTIDOR 2": "VES",
}


def draw_zoning(page, x, y, title, rooms, X, Y, free_bg=True):
    s = ZS
    x0, y0 = x, y + 23 * s
    # lote (fondo de area libre en PB)
    fill = ZONE_RGB["LIB"] if free_bg else None
    rect(page, x0, y0 - 23 * s, x0 + 8 * s, y0, (0.40, 0.44, 0.50), fill, 0.8, 0.16)
    for label, i0, i1, j0, j1 in rooms:
        xa, xb = x0 + X[i0] * s, x0 + X[i1] * s
        ya, yb = y0 - Y[j1] * s, y0 - Y[j0] * s
        cat = U.ZONE.get(label, "LIB")
        rect(page, xa, ya, xb, yb, ZONE_RGB[cat], ZONE_RGB[cat], 0.45, 0.22)
        if abs(X[i1] - X[i0]) >= 0.85 and abs(Y[j1] - Y[j0]) >= 1.0:
            short = _ABBR.get(label, label[:3])
            txt(page, xa + 2, ya + 8, short, 4.8, "helv", INK)
    # titulo y norte
    txt(page, x0, y - 6, title, 7.5, "hebo", INK)
    nx, ny = x0 + 8 * s + 13, y + 21
    line(page, nx, ny + 19, nx, ny + 4, BLUE, 0.9)
    page.draw_polyline(
        [fitz.Point(nx, ny), fitz.Point(nx - 4, ny + 8), fitz.Point(nx + 4, ny + 8)],
        color=BLUE,
        fill=BLUE,
        width=0.5,
    )
    txt(page, nx - 2.5, ny - 2, "N", 6, "hebo", BLUE)


def main() -> int:
    sc = AR.schedule()
    total_pb, total_pa, total = sc["total_pb"], sc["total_pa"], sc["total"]
    terreno, libre = sc["terreno"], sc["area_libre"]
    ref_total = sum(sc["ref_pb"].values()) + sum(sc["ref_pa"].values())
    zpb, zpa = zone_area(U.ROOMS1, U.X1, U.Y1), zone_area(U.ROOMS2, U.X2, U.Y2)
    zones = {k: zpb[k] + zpa[k] for k in ("SOC", "SER", "PRI", "CIR")}

    doc = fitz.open()
    doc.set_metadata(
        {
            "title": "Informe tecnico - Vivienda UCV Magisterial 230",
            "author": "Oficina Tecnica / AutoCAD MCP",
            "subject": "Anteproyecto arquitectonico, plantas, zonificacion y mobiliario",
            "keywords": "UCV, vivienda, arquitectura, AutoCAD, informe",
        }
    )

    # ---------------- Portada ----------------
    p = doc.new_page(width=W, height=H)
    rect(p, 0, 0, W, 300, color=NAVY, fill=NAVY, width=0)
    rect(p, 0, 300, W, 306, color=GOLD, fill=GOLD, width=0)
    txt(p, M, 56, "INFORME TECNICO  /  ANTEPROYECTO", 9, "hebo", GOLD)
    txt(p, M, 100, "VIVIENDA", 30, "hebo", WHITE)
    txt(p, M, 140, "UCV MAGISTERIAL 230", 27, "hebo", WHITE)
    txt(
        p,
        M,
        178,
        "Plantas arquitectonicas, zonificacion y mobiliario",
        12,
        "helv",
        (0.82, 0.86, 0.92),
    )
    txt(
        p,
        M,
        214,
        "LOTE 8.00 x 23.00 m  |  DOS PLANTAS  |  ESCALA 1:100",
        9,
        "helv",
        (0.75, 0.80, 0.88),
    )
    txt(p, W - M - 120, 255, "26 de octubre de 2026", 9, "helv", (0.75, 0.80, 0.88))
    txt(p, W - M - 120, 271, "Version 1.2", 9, "hebo", WHITE)

    cards = [
        ("AREA TECHADA", f"{total:.2f} m2", "PB + PA"),
        ("AREA LIBRE", f"{libre:.2f} m2", f"{sc['libre_pct']:.2f}% del lote"),
        ("AMBIENTES", "21", "10 PB + 11 PA"),
        ("PUERTAS BLOQUE", "14", "12 batientes + 2 correderas"),
    ]
    cw, gap = 118.0, 14.0
    for i, (lab, val, sub) in enumerate(cards):
        x = M + i * (cw + gap)
        rect(p, x, 335, x + cw, 425, color=(0.84, 0.87, 0.91), fill=WHITE, width=0.8)
        rect(p, x, 335, x, 425, color=TEAL, fill=TEAL, width=0)
        txt(p, x + 10, 358, lab, 7, "hebo", GRAY)
        txt(p, x + 10, 386, val, 16, "hebo", NAVY)
        txt(p, x + 10, 407, sub, 7, "helv", GRAY)

    txt(p, M, 465, "CONTENIDO", 9, "hebo", BLUE)
    contents = [
        "1. Resumen ejecutivo y datos generales",
        "2. Comparativa con el programa de referencia",
        "3. Cuadro de areas por ambiente",
        "4. Zonificacion PB / PA y leyenda",
        "5. Puertas, ventanas y escalera",
        "6. Mobiliario, biblioteca y correcciones aplicadas",
        "7. Hallazgos, conclusiones y verificacion",
    ]
    for i, c in enumerate(contents):
        txt(p, M + 10, 486 + i * 17, c, 9, "helv", INK)

    rect(p, M, 620, W - M, 708, color=(0.93, 0.80, 0.45), fill=(0.995, 0.965, 0.880), width=0.8)
    txt(p, M + 12, 643, "HALLAZGO PRINCIPAL DE LA REVISION", 8, "hebo", RED)
    para(
        p,
        M + 12,
        652,
        W - 2 * M - 24,
        44,
        f"El anteproyecto desarrolla {total:.2f} m2 techados, mientras que el programa de "
        f"referencia suma {ref_total:.2f} m2. La diferencia es +{total - ref_total:.2f} m2 "
        f"({(total / ref_total - 1) * 100:.1f}%). Se recomienda validar el alcance antes de "
        "congelar la propuesta; ya se aplico la correccion de area libre y se verifico la distribucion.",
        8.2,
        "helv",
        INK,
        1.18,
    )
    txt(
        p,
        M,
        H - 20,
        "Elaborado con AutoCAD 2026 + automatizacion MCP. DWG unico de trabajo.",
        7,
        "helv",
        GRAY,
    )

    # ---------------- Pagina 2: resumen y datos ----------------
    p = doc.new_page(width=W, height=H)
    header(p, "RESUMEN / DATOS GENERALES")
    y = section(p, 93, "01", "Resumen ejecutivo")
    para(
        p,
        M,
        y,
        W - 2 * M,
        78,
        "El presente informe documenta el estado del anteproyecto de la vivienda UCV "
        "Magisterial 230, desarrollado en dos plantas sobre un lote de 8.00 x 23.00 m. "
        "La planta baja integra garage, hall, oficina, sala de estar, comedor, cocina, "
        "lavanderia, SS.HH. y escalera; la planta alta contiene tres dormitorios, dos "
        "SS.HH., vestidor, balcon, hall y escalera. El DWG conserva las plantas, la "
        "zonificacion, el cuadro de areas y la hoja de biblioteca de bloques.",
        8.8,
    )
    y += 82
    y = section(p, y, "02", "Datos generales del proyecto")
    data_rows = [
        ("Ubicacion / referencia", "Lote esquina, frente SUR; fondo NORTE"),
        ("Terreno", "8.00 x 23.00 m = 184.00 m2"),
        ("Huella / area techada", f"128.80 m2 por planta / {total:.2f} m2 totales"),
        ("Altura entrepiso", "2.80 m; 16 contrapasos de 0.175 m"),
        ("Sistema constructivo", "Muros de 0.15 m; albañileria confinada"),
        ("Escala de dibujo", "1:100 en modelo; unidades en metros"),
        ("Lamina de trabajo", "Vivienda_UCV_Magisterial_230_PLANTAS.dwg"),
    ]
    y = table(p, M, y, [150, 355], ["Concepto", "Valor"], data_rows, 15, 8.2) + 20

    y = section(p, y, "03", "Comparativa con el programa de referencia")
    ref_rows = [
        (
            "Primer piso",
            f"{total_pb:.2f}",
            f"{sum(sc['ref_pb'].values()):.2f}",
            f"+{total_pb - sum(sc['ref_pb'].values()):.2f}",
        ),
        (
            "Segundo piso",
            f"{total_pa:.2f}",
            f"{sum(sc['ref_pa'].values()):.2f}",
            f"+{total_pa - sum(sc['ref_pa'].values()):.2f}",
        ),
        ("TOTAL", f"{total:.2f}", f"{ref_total:.2f}", f"+{total - ref_total:.2f}"),
    ]
    y = (
        table(
            p,
            M,
            y,
            [150, 120, 120, 115],
            ["Nivel", "Anteproyecto (m2)", "Referencia (m2)", "Diferencia (m2)"],
            ref_rows,
            15,
            8.2,
            [0, 2, 2, 2],
        )
        + 12
    )
    para(
        p,
        M,
        y,
        W - 2 * M,
        34,
        "La referencia no incluye hall, corredor, escalera, balcon, vestidor ni el SS.HH. "
        "adicional; ademas, la sala y el comedor se comparan como un solo ambiente. "
        "Por ello la brecha es referencial y debe validarse con el programa del curso.",
        7.8,
        "helv",
        GRAY,
    )
    y += 40
    y = section(p, y, "04", "Criterios de diseno aplicados")
    for s in [
        "Modulacion estructural y muros de 0.15 m; sin columnas visibles en planta.",
        "Zonificacion por categorias: social, servicios, privada, circulacion y area libre.",
        "Puertas y ventanas como bloques o vanos identificados; puerta principal de 1.10 m.",
        "Escalera en L con dos tramos, descanso, pasamanos y flecha de sentido.",
        "Mobiliario de alto diseno en biblioteca separada; se inserta en ambas plantas.",
        "Acotacion en metros con dos decimales y cuadro de areas coherente con el DWG.",
    ]:
        y = bullet(p, M, y, W - 2 * M, s)

    # ---------------- Pagina 3: cuadro de areas ----------------
    p = doc.new_page(width=W, height=H)
    header(p, "CUADRO DE AREAS")
    y = section(p, 93, "05", "Cuadro de areas por ambiente")
    para(
        p,
        M,
        y,
        W - 2 * M,
        28,
        "Dimensiones interiores obtenidas de la grilla modular. Las areas se expresan en "
        "metros cuadrados con dos decimales; los subtotales coinciden con el DWG y con la tabla.",
        7.8,
        "helv",
        GRAY,
    )
    y += 28

    def room_rows(rooms, X, Y):
        out = []
        for label, i0, i1, j0, j1 in rooms:
            a, b = abs(X[i1] - X[i0]), abs(Y[j1] - Y[j0])
            out.append((label, f"{a:.2f} x {b:.2f}", f"{a * b:.2f}"))
        return out

    rows_pb = room_rows(U.ROOMS1, U.X1, U.Y1)
    rows_pb.append(("SUBTOTAL PRIMER PISO", "", f"{total_pb:.2f}"))
    y = (
        table(
            p,
            M,
            y,
            [205, 145, 120],
            ["Ambiente - Primer piso", "Dimensiones (m)", "Area (m2)"],
            rows_pb,
            14.2,
            7.8,
            [0, 1, 2],
        )
        + 18
    )
    rows_pa = room_rows(U.ROOMS2, U.X2, U.Y2)
    rows_pa.append(("SUBTOTAL SEGUNDO PISO", "", f"{total_pa:.2f}"))
    y = (
        table(
            p,
            M,
            y,
            [205, 145, 120],
            ["Ambiente - Segundo piso", "Dimensiones (m)", "Area (m2)"],
            rows_pa,
            14.2,
            7.8,
            [0, 1, 2],
        )
        + 18
    )

    res_rows = [
        ("Area techada primer piso", f"{total_pb:.2f} m2"),
        ("Area techada segundo piso", f"{total_pa:.2f} m2"),
        ("AREA TECHADA TOTAL", f"{total:.2f} m2"),
        ("Area libre (jardines)", f"{libre:.2f} m2"),
        ("Area del terreno", f"{terreno:.2f} m2"),
    ]
    y = table(p, M, y, [300, 170], ["Resumen", "Valor"], res_rows, 15, 8.2, [0, 2])
    para(
        p,
        M,
        y + 12,
        W - 2 * M,
        30,
        "Nota: el area libre resulta de descontar la huella de 128.80 m2 al terreno de "
        "184.00 m2; incluye jardin frontal y posterior. No se suman areas de dos plantas "
        "para comparar con el terreno.",
        7.6,
        "helv",
        GRAY,
    )

    # ---------------- Pagina 4: zonificacion ----------------
    p = doc.new_page(width=W, height=H)
    header(p, "ZONIFICACION")
    y = section(p, 93, "06", "Zonificacion de ambas plantas")
    para(
        p,
        M,
        y,
        W - 2 * M,
        40,
        "Esquema de categorias por ambiente. Los rellenos son indicativos y no reemplazan "
        "la lamina de zonificacion del DWG; la leyenda es unica para PB y PA.",
        7.8,
        "helv",
        GRAY,
    )
    y += 40
    draw_zoning(p, 60, y + 10, "PLANTA BAJA - PB", U.ROOMS1, U.X1, U.Y1, True)
    draw_zoning(p, 320, y + 10, "PLANTA ALTA - PA", U.ROOMS2, U.X2, U.Y2, False)

    # leyenda
    ly = y + 10 + 23 * ZS + 20
    txt(p, 60, ly, "LEYENDA", 8, "hebo", BLUE)
    names = [
        ("SOC", "Zona social"),
        ("SER", "Zona servicios"),
        ("PRI", "Zona privada"),
        ("CIR", "Circulacion"),
        ("LIB", "Area libre"),
    ]
    for i, (k, name) in enumerate(names):
        yy = ly + 16 + i * 15
        rect(p, 60, yy - 8, 72, yy + 2, ZONE_RGB[k], ZONE_RGB[k], 0.4, 0.55)
        txt(p, 78, yy, name, 7.5, "helv", INK)

    zrows = [
        ("Zona social (SOC)", f"{zones['SOC']:.2f}", f"{zones['SOC'] / total * 100:.1f}%"),
        ("Zona servicios (SER)", f"{zones['SER']:.2f}", f"{zones['SER'] / total * 100:.1f}%"),
        ("Zona privada (PRI)", f"{zones['PRI']:.2f}", f"{zones['PRI'] / total * 100:.1f}%"),
        ("Circulacion (CIR)", f"{zones['CIR']:.2f}", f"{zones['CIR'] / total * 100:.1f}%"),
        ("Area libre (LIB)", f"{libre:.2f}", "26.1% del lote"),
        ("TOTAL TECHADO", f"{sum(zones.values()):.2f}", "100.0%"),
    ]
    table(
        p,
        300,
        ly - 8,
        [125, 60, 68],
        ["Categoria", "Area (m2)", "% techado"],
        zrows,
        13.5,
        7.4,
        [0, 2, 2],
    )
    para(
        p,
        300,
        ly + 104,
        230,
        52,
        "La zonificacion cubre PB y PA. Las areas por categoria suman el area techada "
        "(257.60 m2); el area libre se informa por separado para no duplicar la lectura "
        "del lote. El fondo verde de PB representa el area libre; PA muestra solo areas "
        "techadas. El bloque A-NORTE se inserta en ambas plantas y en la zonificacion.",
        7.4,
        "helv",
        GRAY,
    )

    # ---------------- Pagina 5: puertas, ventanas, escalera ----------------
    p = doc.new_page(width=W, height=H)
    header(p, "PUERTAS / VENTANAS / ESCALERA")
    y = section(p, 93, "07", "Puertas y bloques de carpinteria")
    door_rows = [
        ("A-PUERTA-110", "1.10 x 2.10", "1", "P-01 ingreso principal"),
        ("A-PUERTA-100", "1.00 x 2.10", "1", "P-25 dormitorio principal"),
        ("A-PUERTA-090", "0.90 x 2.10", "10", "P-03/05/10/11/20/21/24/26/27/32"),
        ("A-PUERTA-CORREDERA-200", "2.00 x 2.10", "2", "P-13 comedor / P-14 cocina"),
        ("TOTAL", "", "14", "12 batientes + 2 correderas"),
    ]
    y = (
        table(
            p,
            M,
            y,
            [155, 105, 55, 195],
            ["Bloque", "Medida (m)", "Cant.", "Ubicacion / puerta"],
            door_rows,
            14,
            7.7,
            [0, 1, 1, 0],
        )
        + 10
    )
    para(
        p,
        M,
        y,
        W - 2 * M,
        24,
        "La biblioteca conserva ademas A-PUERTA-070, A-PUERTA-080 y A-PUERTA-120 para "
        "futuras variantes. La puerta principal se amplio de 0.80 a 1.10 m y usa el bloque "
        "A-PUERTA-110, con hoja y abanico de giro.",
        7.6,
        "helv",
        GRAY,
    )
    y += 48

    y = section(p, y, "08", "Ventanas y vanos abiertos")
    win_rows = [
        ("V-01", "2.30", "Garage", "Porton / panel, no bloque de puerta"),
        ("V-20", "2.50", "Oficina PB", "Ventana sur"),
        ("V-10", "0.90", "Comedor", "Ventana norte"),
        ("V-12", "0.50", "Comedor", "Ventana norte"),
        ("V-11", "2.30", "Dormitorio 2", "Ventana sur"),
        ("V-13", "2.50", "Dormitorio 3", "Ventana sur"),
        ("V-16", "2.60", "Dormitorio principal", "Ventana norte"),
    ]
    y = (
        table(
            p,
            M,
            y,
            [55, 65, 155, 235],
            ["ID", "Ancho (m)", "Ambiente", "Observacion"],
            win_rows,
            13.2,
            7.4,
            [0, 1, 0, 0],
        )
        + 8
    )
    para(
        p,
        M,
        y,
        W - 2 * M,
        22,
        "Se corrigio la nomenclatura duplicada V-12 de PA a V-13. Los vanos abiertos "
        "(11) no llevan hoja: P-06, P-08, P-09, P-12, P-15, P-22, P-23, P-28, P-29, P-30, P-31.",
        7.4,
        "helv",
        GRAY,
    )
    y += 48

    y = section(p, y, "09", "Escalera: verificacion geometrica")
    stair_rows = [
        ("Tipologia", "L de dos tramos con descanso"),
        ("Contrapasos", "16 (rotulo 16 ESC)"),
        ("Altura entrepiso", "2.80 m"),
        ("Contrapaso", "0.175 m"),
        ("Ancho de tramo", "0.90 m"),
        ("Tramo 1 / Tramo 2", "2.10 m / 1.80 m"),
        ("Descanso", "1.80 x 0.90 m (esquina NE)"),
        ("Huella resultante", "0.21 m / 0.30 m - revisar uniformidad"),
    ]
    y_stair = table(
        p,
        M,
        y,
        [155, 310],
        ["Parametro", "Valor / observacion"],
        stair_rows,
        13.5,
        7.8,
    )
    para(
        p,
        M,
        y_stair + 14,
        W - 2 * M,
        34,
        "La escalera se dibuja completa en ambas plantas, con pasamanos, flecha SUBE/BAJA "
        "y arranque. Para el detalle se recomienda uniformar la huella (0.25-0.28 m) y "
        "verificar altura libre y pasamanos segun normativa aplicable.",
        7.4,
        "helv",
        GRAY,
    )

    # ---------------- Pagina 6: mobiliario y correcciones ----------------
    p = doc.new_page(width=W, height=H)
    header(p, "MOBILIARIO / CORRECCIONES")
    y = section(p, 93, "10", "Mobiliario y biblioteca de bloques")
    mob_rows = [
        ("OBJ-ROPERO-240", "4", "Dormitorios y vestidor"),
        ("OBJ-PLANTA-INTERIOR", "7", "Sala, oficina, dormitorios"),
        ("OBJ-ESCRITORIO-140", "3", "Oficina PB + dormitorios PA"),
        ("OBJ-INODORO-SUSP", "3", "SS.HH. 1, 2 y 3"),
        ("OBJ-LAVAMANOS-100", "3", "SS.HH. 1, 2 y 3"),
        ("OBJ-DUCHA-WALKIN", "3", "SS.HH. 1, 2 y 3"),
        ("OBJ-SOFA-MOD-260", "2", "Sala PB y sala PA"),
        ("OBJ-MESA-CENTRO-120", "2", "Sala PB y sala PA"),
        ("OBJ-ALFOMBRA-240", "2", "Sala PB y sala PA"),
        ("OBJ-SILLA-LOUNGE", "4", "Dos por sala, PB y PA"),
        ("OBJ-MESA-LATERAL-060", "3", "Salas PB/PA y balcon PA"),
        ("OBJ-CAMA-SINGLE", "2", "Dormitorios 2 y 3"),
        ("OBJ-CAMA-QUEEN", "1", "Dormitorio principal"),
        ("OBJ-LIBRERO-200", "2", "Oficina PB, muros oeste y este"),
        ("OBJ-COMEDOR-6P / ISLA-180 / TV / LAVADERO / TINA", "5", "Comedor, cocina, sala y SS.HH."),
        ("OBJ-REFRI-090", "1", "Cocina PB"),
        ("OBJ-LAVAPLATOS-060", "1", "Cocina PB"),
        ("OBJ-MICROONDAS-060", "1", "Cocina PB"),
        ("OBJ-LAVADORA-060", "1", "Lavanderia PB"),
        ("OBJ-PLANTA-JARDIN", "9", "Jardin PB, terraza y balcon PA"),
        ("OBJ-AUTO-450", "1", "Cochera PB"),
        ("TOTAL MOBILIARIO", "60", "25 tipos de bloque; 30 PB + 30 PA"),
    ]
    y = (
        table(
            p,
            M,
            y,
            [235, 55, 215],
            ["Bloque / familia", "Cant.", "Ubicacion"],
            mob_rows,
            13.4,
            7.4,
            [0, 1, 0],
        )
        + 12
    )
    para(
        p,
        M,
        y,
        W - 2 * M,
        26,
        "La biblioteca BIBLIOTECA contiene 34 bloques y se conserva como hoja separada. "
        "Los libreros OBJ-LIBRERO-200 se redisenaron con cuatro modulos y libros visibles "
        "para que se lean a 1:100; antes se veian como una barra maciza.",
        7.6,
        "helv",
        GRAY,
    )
    y += 52

    y = section(p, y, "11", "Correcciones aplicadas en esta revision")
    fixes = [
        "Cotas en metros con dos decimales exactos: DIMDEC=2 y DIMZIN=0; 29 cotas revisadas.",
        "Puerta principal ampliada a 1.10 m con bloque A-PUERTA-110; biblioteca con 1.10 y 1.20.",
        "Escalera completa: segundo tramo limitado a 1.80 m, descanso 1.80 x 0.90 y borde de losa.",
        "Rotulo DESCANSO reemplazado por TRAMO 2 para coincidir con el segundo tramo dibujado.",
        "Escalones dibujados antes de los rotulos para que ESCALERA/TRAMO 2 queden legibles.",
        "Oficina PB con dos libreros de 2.00 x 0.35 en muros oeste y este.",
        "Acceso de lavanderia cambiado a pasillo; cocina reorganizada con isla, refri, fregadero y microondas.",
        "Isla de cocina reducida a OBJ-ISLA-COCINA-180 (1.80 x 0.90 m) para conservar circulaciones adecuadas.",
        "Vehiculo OBJ-AUTO-450 redisenado como bloque 4.50 x 1.80 m con carroceria, techo, lunas, puertas, ruedas, espejos, faros y paragolpes.",
        "Salas PB y PA complementadas con rincones de lectura: una silla lounge y una mesa lateral por planta, sin bloquear accesos.",
        "Vestidor PA depurado a un solo ropero; plantas de balcon y terraza separadas para evitar interferencias.",
        "Se agregaron plantas de jardin, automovil, lavadora y detalles de cocina.",
        "Bloque A-NORTE profesional insertado en PB, PA y zonificacion (3 referencias).",
        "Nomenclatura de ventana PA corregida de V-12 a V-13 para evitar duplicidad.",
        "Verificacion geometrica: 0 solapes entre objetos de mobiliario/equipamiento, 0 lineas duplicadas y vehiculo dentro de la cochera.",
    ]
    for s in fixes:
        y = bullet(p, M, y, W - 2 * M, s, 8.2)

    # ---------------- Pagina 7: hallazgos y cierre ----------------
    p = doc.new_page(width=W, height=H)
    header(p, "HALLAZGOS / CIERRE")
    y = section(p, 93, "12", "Hallazgos que requieren decision")
    findings = [
        "Brecha de area: 257.60 m2 construidos vs 126.00 m2 de referencia (+131.60 m2). "
        "La correccion de area libre ya fue aplicada; queda validar el alcance del programa oficial.",
        "Huella de escalera: las huellas resultantes son 0.21 m y 0.30 m; uniformar a 0.25-0.28 m "
        "en el detalle y verificar contrapaso, pasamanos y altura libre.",
        "Porton de garage V-01: se dibuja como panel de 2.30 m, no como bloque de puerta; "
        "si se requiere bloque, crear A-PORTON-230 y reemplazar el panel.",
        "Los 11 vanos abiertos no llevan hoja; si alguno debe cerrar, asignar bloque y ajustar "
        "el cuadro de puertas.",
        "La tabla de areas y la zonificacion son coherentes con el DWG, pero deben revisarse "
        "contra el programa oficial del curso antes de la entrega final.",
    ]
    for f in findings:
        y = bullet(p, M, y, W - 2 * M, f, 8.2)
    y += 4

    y = section(p, y, "13", "Conclusiones")
    para(
        p,
        M,
        y,
        W - 2 * M,
        72,
        "El DWG queda ordenado en una sola lamina de trabajo: plantas PB y PA, zonificacion "
        "con leyenda unica, cuadro de areas, tabla de datos, norte profesional y hoja de "
        "biblioteca con 34 bloques. Las correcciones de esta revision se concentran en "
        "precision de cotas, puerta principal, escalera, libreros, vehiculo, circulaciones, norte y nomenclatura. "
        "El anteproyecto es consistente internamente; la principal decision pendiente es "
        "el alcance de area frente al programa de referencia.",
        8.6,
    )
    y += 80

    y = section(p, y, "14", "Verificacion de consistencia")
    ver_rows = [
        ("Entidades en modelo", "714", "Verificado"),
        ("Referencias de bloque", "77", "Verificado"),
        ("Puertas en bloque", "14", "Verificado"),
        ("Mobiliario insertado", "60", "Verificado"),
        ("Libreros de oficina", "2", "Verificado"),
        ("Bloques A-NORTE", "3", "Verificado"),
        ("Cotas / precision", "29 / 2 dec.", "Verificado"),
        ("Hatches de zonificacion", "30", "Verificado"),
        ("Solapes mobiliario/equipamiento", "0", "Verificado"),
        ("Area PB / PA", "128.80 / 128.80", "Coincide"),
        ("Area techada total", "257.60 m2", "Coincide"),
    ]
    y = (
        table(
            p,
            M,
            y,
            [230, 145, 130],
            ["Indicador", "Valor", "Estado"],
            ver_rows,
            14.2,
            7.7,
            [0, 2, 1],
        )
        + 22
    )

    rect(p, M, y, W - M, y + 70, color=(0.80, 0.84, 0.88), fill=LIGHT, width=0.7)
    txt(p, M + 12, y + 20, "Elaborado por", 8, "hebo", GRAY)
    txt(p, M + 12, y + 38, "Oficina Tecnica / AutoCAD MCP", 10, "hebo", NAVY)
    txt(p, M + 12, y + 54, "26 de octubre de 2026  |  Version 1.2", 8, "helv", GRAY)
    txt(p, W - M - 150, y + 38, "Documento de anteproyecto", 9, "hebo", BLUE)
    txt(p, W - M - 150, y + 54, "No apto para construccion", 8, "helv", RED)

    # ---------------- Pagina 8: anexo de pendientes ----------------
    p = doc.new_page(width=W, height=H)
    header(p, "ANEXO A / PENDIENTES")

    y = section(p, 93, "15", "Cumplimiento de area libre: correccion aplicada")
    para(
        p,
        M,
        y,
        W - 2 * M,
        30,
        "El lote tiene 184.00 m2. Se aplico una franja descubierta de 3.60 x 2.00 m "
        "en el extremo norte de PB y PA. El area libre final es 55.20 m2 (30.00%) y "
        "la huella final es 128.80 m2 por planta.",
        7.7,
        "helv",
        GRAY,
    )
    y += 36

    y = (
        table(
            p,
            M,
            y,
            [128, 128, 128, 127],
            ["Minimo exigido", "Area libre final", "Estado", "Huella final"],
            [("55.20 m2", "55.20 m2 (30.00%)", "Cumple", "128.80 m2")],
            18,
            8.3,
            [1, 1, 1, 1],
        )
        + 16
    )

    result_rows = [
        ("Cocina PB", "18.00", "10.80", "-7.20", "Queda 3.60 x 3.00 m"),
        ("Vestidor PA", "13.50", "6.30", "-7.20", "Queda 3.60 x 1.75 m"),
        ("Huella", "136.00", "128.80", "-7.20", "Por planta"),
        ("Area libre", "48.00", "55.20", "+7.20", "30.00% del lote"),
        ("Total techado", "272.00", "257.60", "-14.40", "PB + PA"),
    ]
    y = (
        table(
            p,
            M,
            y,
            [118, 95, 95, 95, 108],
            ["Ambiente / indicador", "Antes", "Despues", "Variacion", "Observacion"],
            result_rows,
            19,
            7.0,
            [0, 2, 2, 2, 0],
        )
        + 14
    )

    rect(p, M, y, W - M, y + 88, color=(0.93, 0.80, 0.45), fill=(0.995, 0.965, 0.880), width=0.8)
    txt(p, M + 12, y + 18, "CAMBIO APLICADO", 8, "hebo", GREEN)
    para(
        p,
        M + 12,
        y + 26,
        W - 2 * M - 24,
        54,
        "Se aplico la Opcion B: retiro de 3.60 x 2.00 m en el extremo norte de cocina PB "
        "y vestidor PA, generando area libre descubierta. La cocina queda en 10.80 m2 y "
        "el vestidor en 6.30 m2; la huella final es 128.80 m2 por planta y el total "
        "techado 257.60 m2. El cambio esta incorporado al DWG y al cuadro de areas; "
        "queda pendiente validar funcionamiento, estructura y normativa municipal.",
        7.4,
        "helv",
        INK,
        1.18,
    )
    y += 102

    y = section(p, y, "16", "Requisitos para ser apto para construccion")
    permit_rows = [
        (
            "Legal / urbanistico",
            "Licencia, parametros urbanos, retiros, altura, coeficientes y 30% libre",
        ),
        (
            "Estructuras",
            "Estudio de suelos, calculo estructural, cimentacion, losas y detalles sismicos",
        ),
        (
            "Instalaciones",
            "Sanitarias, electricas, gas, ventilacion, drenaje pluvial y tanque de agua",
        ),
        (
            "Seguridad",
            "Escalera (huella/contrapaso/pasamanos), evacuacion, incendios y accesibilidad",
        ),
        (
            "Detalle arquitectonico",
            "Puertas/ventanas, porton, vanos, impermeabilizacion, acabados y mobiliario fijo",
        ),
        (
            "Documentos de obra",
            "Planos constructivos, especificaciones tecnicas, metrados, presupuesto y cronograma",
        ),
        (
            "Validaciones",
            "Programa de areas, cuadro de vanos, revision municipal y firmas profesionales",
        ),
    ]
    y = (
        table(
            p,
            M,
            y,
            [130, 381],
            ["Frente pendiente", "Documento / accion necesaria"],
            permit_rows,
            24,
            7.3,
            [0, 0],
        )
        + 14
    )

    rect(p, M, y, W - M, y + 46, color=(0.80, 0.84, 0.88), fill=LIGHT, width=0.7)
    para(
        p,
        M + 12,
        y + 10,
        W - 2 * M - 24,
        30,
        "Estado actual: anteproyecto arquitectonico, no apto para construccion. "
        "El 30% de area libre, la nivelacion de huellas y los documentos de ingenieria "
        "son condiciones previas para iniciar la revision municipal.",
        7.4,
        "helv",
        INK,
        1.16,
    )

    total_pages = len(doc)
    for i in range(1, total_pages):
        footer(doc[i], i + 1, total_pages)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT, deflate=True, garbage=3)
    doc.close()

    # Vista previa para control de calidad (no es el entregable).
    preview = fitz.open(OUT)
    for i in range(total_pages):
        pix = preview[i].get_pixmap(dpi=100, colorspace=fitz.csRGB)
        pix.save(str(PREVIEW) + f"_{i + 1}.png")
    preview.close()
    print(f"PDF: {OUT}")
    print(f"Paginas: {total_pages}")
    print(f"Area PB/PA/total: {total_pb:.2f} / {total_pa:.2f} / {total:.2f}")
    print(f"Zonas: { {k: round(v, 2) for k, v in zones.items()} }")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
