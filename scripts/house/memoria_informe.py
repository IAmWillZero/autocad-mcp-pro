"""Genera la MEMORIA DESCRIPTIVA del proyecto Vivienda UCV Magisterial 230.

Usa como base el modelo de informe `1. Estructura Informe. CCGR (4).docx`:
misma portada y estilos (Normal, Heading 2/3/4, List Paragraph), pero con el
contenido del proyecto arquitectonico. Incluye los datos reales del DWG
(cuadro de ambientes y areas) tomados de out/cuadro_datos.xlsx.

Salida: out/Memoria_Descriptiva_Vivienda_UCV_Magisterial_230.docx
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import docx  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402

MODELO = Path(r"C:\Users\I Am Will\Downloads\1. Estructura Informe. CCGR (4).docx")
SALIDA = ROOT / "out" / "Memoria_Descriptiva_Vivienda_UCV_Magisterial_230.docx"

INTEGRANTES = [
    "JESÚS ALEXIS ALVARADO HIDALGO",
    "JEAN FRANK ARELLAN LÓPEZ",
    "ANALY DIANA DOMINGUES CAQUI",
    "EMERSON VICENTE CHAVEZ CASTILLO",
    "JUMAR YOSHIRO QUIÑONES RAMÍREZ",
    "WILLIAMS RONALDO SIGUEÑAS ORTIZ",
]
DOCENTE = "M.S. MARIBEL MARCELA NORIEGA FALCÓN"

# --------------------------------------------------------------------------- #
# datos del proyecto (verificados en el DWG)
# --------------------------------------------------------------------------- #
PROYECTO = "VIVIENDA UCV MAGISTERIAL 230"
TERRENO = (8.00, 23.00, 184.00)
TECHADA = (128.80, 128.80, 257.60)
LIBRE = (55.20, 30.0)

PB = [
    ("GARAJE", 3.00, 5.50, 16.50),
    ("HALL", 1.40, 5.50, 7.70),
    ("OFICINA", 3.60, 5.50, 19.80),
    ("ESCALERA", 3.60, 3.00, 10.80),
    ("CORREDOR", 1.40, 8.50, 11.90),
    ("SALA DE ESTAR", 3.00, 8.50, 25.50),
    ("SS.HH. 1", 3.60, 1.75, 6.30),
    ("LAVANDERIA", 3.60, 1.75, 6.30),
    ("COCINA", 3.60, 3.00, 10.80),
    ("COMEDOR", 4.40, 3.00, 13.20),
]
PA = [
    ("DORMITORIO 2", 4.40, 5.50, 24.20),
    ("DORMITORIO 3", 3.60, 5.50, 19.80),
    ("SALA DE ESTAR", 3.00, 4.75, 14.25),
    ("HALL", 1.40, 4.75, 6.65),
    ("BALCON", 1.80, 2.10, 3.78),
    ("ESCALERA", 1.80, 3.00, 5.40),
    ("TRAMO 2", 1.80, 0.90, 1.62),
    ("SS.HH. 3", 3.60, 1.75, 6.30),
    ("DORMITORIO PRINCIPAL", 4.40, 6.75, 29.70),
    ("SS.HH. 2", 3.60, 3.00, 10.80),
    ("VESTIDOR 2", 3.60, 1.75, 6.30),
]


def reemplazar(parrafo, texto: str) -> None:
    """Pone el texto conservando el estilo/tamano del parrafo."""
    for r in list(parrafo.runs):
        r._element.getparent().remove(r._element)
    if parrafo.runs:
        parrafo.runs[0].text = texto
    else:
        parrafo.add_run(texto)


def eliminar(parrafo) -> None:
    parrafo._element.getparent().remove(parrafo._element)


def clonar_estilo(doc, nombre: str):
    return doc.styles[nombre]


def add_par(doc, texto: str, estilo: str = "Normal"):
    p = doc.add_paragraph(texto)
    try:
        p.style = clonar_estilo(doc, estilo)
    except Exception:  # noqa: BLE001
        pass
    return p


def tabla_ambientes(doc, filas, titulo):
    t = doc.add_table(rows=1 + len(filas) + 1, cols=4)
    t.style = "Table Grid"
    cab = t.rows[0].cells
    cab[0].text = "AMBIENTE"
    cab[1].text = "ANCHO (m)"
    cab[2].text = "LARGO (m)"
    cab[3].text = "AREA (m2)"
    for i, (amb, a, b, area) in enumerate(filas, start=1):
        c = t.rows[i].cells
        c[0].text = amb
        c[1].text = f"{a:.2f}"
        c[2].text = f"{b:.2f}"
        c[3].text = f"{area:.2f}"
    pie = t.rows[-1].cells
    pie[0].text = titulo
    pie[3].text = f"{sum(f[3] for f in filas):.2f}"
    return t


def main() -> int:
    doc = docx.Document(MODELO)

    # ---------------- portada ------------------------------------------- #
    # el modelo tiene las lineas de portada como parrafos 6..22
    textos = {p.text.strip(): i for i, p in enumerate(doc.paragraphs) if p.text.strip()}
    paras = doc.paragraphs

    def poner(contiene: str, nuevo: str) -> None:
        for p in paras:
            if contiene in p.text:
                reemplazar(p, nuevo)
                return

    poner("CAMBIO CIMATICO", "EXPRESIÓN GRÁFICA - GRUPO A1")
    poner("Influencia de las lluvias", f"{PROYECTO} — MEMORIA DESCRIPTIVA")
    poner("EUDES YAURI HUAROC", DOCENTE)

    # autores: el modelo tiene 6 nombres de ejemplo
    viejos = [
        "JESÚS ALEXIS ALVARADO HIDALGO",
        "JEAN FRANK ARELLAN LOPEZ",
        "ANALY DIANA DOMINGUEZ CAQUI",
        "LENIN BOHUMER JARA LEIVA",
        "JUMAR YOSHIRO QUIÑONES RAMIREZ",
        "WILLIAMS RONALDO SIGUEÑAS ORTIZ",
    ]
    for viejo, nuevo in zip(viejos, INTEGRANTES, strict=False):
        poner(viejo, nuevo)

    # ---------------- cuerpo -------------------------------------------- #
    # borrar todo desde "Índice" en adelante
    corte = None
    for i, p in enumerate(doc.paragraphs):
        if p.text.strip() == "Índice":
            corte = i
            break
    if corte is not None:
        for p in list(doc.paragraphs[corte:]):
            eliminar(p)
    # borrar las tablas del modelo (matriz de riesgos, priorizacion)
    for t in list(doc.tables):
        t._element.getparent().remove(t._element)

    # ---------------- contenido nuevo ------------------------------------ #
    add_par(doc, "Índice", "Heading 1")
    for linea in (
        "I. INTRODUCCIÓN",
        "II. MARCO TEÓRICO Y NORMATIVO",
        "III. MEMORIA DESCRIPTIVA",
        "    1. Ubicación y terreno",
        "    2. Zonificación arquitectónica",
        "    3. Distribución por niveles",
        "    4. Áreas y cuadro de ambientes",
        "    5. Especificaciones técnicas",
        "IV. CONCLUSIONES Y RECOMENDACIONES",
        "V. BIBLIOGRAFÍA",
    ):
        add_par(doc, linea)
    doc.add_page_break()

    add_par(doc, "I. INTRODUCCIÓN", "Heading 2")
    add_par(
        doc,
        f"La presente memoria descriptiva documenta el anteproyecto de la "
        f"{PROYECTO}, una vivienda unifamiliar de dos niveles desarrollada en el "
        f"curso de Expresión Gráfica (Grupo A1). El proyecto se plantea sobre un "
        f"lote urbano de {TERRENO[0]:.2f} m de frente por {TERRENO[1]:.2f} m de "
        f"fondo ({TERRENO[2]:.2f} m2) y responde al programa arquitectónico de una "
        f"familia de 4-6 integrantes, con áreas sociales amplias, dormitorios con "
        f"baño y la máxima área libre posible dentro del terreno.",
    )
    add_par(
        doc,
        "El documento describe la ubicación, la zonificación, la distribución "
        "por niveles, las áreas verificadas y las especificaciones técnicas "
        "consideradas en el modelo, y se complementa con las láminas A4 "
        "(plantas, catálogo de bloques, biblioteca y cuadro de datos) y la "
        "lámina A3 de presentación.",
    )

    add_par(doc, "II. MARCO TEÓRICO Y NORMATIVO", "Heading 2")
    for t in (
        "Reglamento Nacional de Edificaciones (RNE) - Norma A.020 Vivienda: "
        "dimensiones mínimas de ambientes y zonificación.",
        "Norma A.010 Condiciones Generales de Diseño: unidades en metros, "
        "acotado y convenciones gráficas.",
        "Área libre: la vivienda mantiene libre el 30.0% del lote, exigido "
        "para lotes de esta tipología.",
    ):
        add_par(doc, t, "List Paragraph")

    add_par(doc, "III. MEMORIA DESCRIPTIVA", "Heading 2")

    add_par(doc, "1. Ubicación y terreno", "Heading 3")
    add_par(
        doc,
        f"Terreno rectangular urbano de {TERRENO[0]:.2f} m x {TERRENO[1]:.2f} m "
        f"= {TERRENO[2]:.2f} m2. Frente orientado al acceso vehicular y "
        f"peatonal (garaje y hall en planta baja).",
    )

    add_par(doc, "2. Zonificación arquitectónica", "Heading 3")
    for t in (
        "ZONA SOCIAL: sala de estar, comedor, cocina, oficina (planta baja) y "
        "sala de estar (planta alta).",
        "ZONA PRIVADA: dormitorio principal con vestidor y SS.HH., "
        "dormitorios secundarios (planta alta).",
        "ZONA DE SERVICIOS: SS.HH., lavandería, cocina (planta baja).",
        "CIRCULACIÓN: escalera de dos tramos, hall y corredor.",
        "ÁREA LIBRE: jardín/patio interior del lote.",
    ):
        add_par(doc, t, "List Paragraph")

    add_par(doc, "3. Distribución por niveles", "Heading 3")
    add_par(
        doc,
        "Planta baja (1.er piso, 128.80 m2 techados): garaje, hall, oficina, "
        "escalera, corredor, sala de estar, SS.HH. 1, lavandería, cocina y "
        "comedor.",
    )
    add_par(
        doc,
        "Planta alta (2.do piso, 128.80 m2 techados): dormitorio principal con "
        "vestidor y SS.HH., dormitorios 2 y 3, sala de estar, hall, balcón, "
        "escalera y SS.HH. 2 y 3.",
    )

    add_par(doc, "4. Áreas y cuadro de ambientes", "Heading 3")
    add_par(
        doc,
        f"Área techada total: {TECHADA[2]:.2f} m2 ({TECHADA[0]:.2f} m2 por "
        f"nivel). Área libre: {LIBRE[0]:.2f} m2 = {LIBRE[1]:.1f}% del terreno "
        f"(cumple el mínimo de 30%). Los mismos datos están disponibles en la "
        f"lámina A4_DATOS y en el archivo cuadro_datos.xlsx.",
    )
    add_par(doc, "Planta baja", "Heading 4")
    tabla_ambientes(doc, PB, "SUBTOTAL 1.er PISO")
    add_par(doc, "Planta alta", "Heading 4")
    tabla_ambientes(doc, PA, "SUBTOTAL 2.do PISO")

    add_par(doc, "5. Especificaciones técnicas", "Heading 3")
    for t in (
        "Muros portantes de albañilería de 0.15-0.20 m y mamparas divisorias "
        "de 0.10 m.",
        "Puertas metálicas/madera de 0.70 a 1.20 m y puerta corredera de "
        "2.00 m (bloques A-PUERTA).",
        "Unidades: metros. Cotas en metros con dos decimales.",
        "Escalas de láminas: 1:100 (plantas A4), 1:125 (presentación A3 y "
        "catálogo de bloques).",
    ):
        add_par(doc, t, "List Paragraph")

    add_par(doc, "IV. CONCLUSIONES Y RECOMENDACIONES", "Heading 2")
    for t in (
        "El proyecto cumple el programa arquitectónico y la zonificación "
        "solicitada, con 257.60 m2 techados en dos niveles.",
        "El área libre (30.0%) cumple el mínimo; se recomienda no aumentar la "
        "huella edificada para conservar margen.",
        "Las láminas A4/A3 quedan listas para completar los MVIEW y el "
        "trazado final.",
    ):
        add_par(doc, t, "List Paragraph")

    add_par(doc, "V. BIBLIOGRAFÍA", "Heading 2")
    for t in (
        "Reglamento Nacional de Edificaciones - Norma A.020 Vivienda.",
        "Universidad César Vallejo - Material del curso de Expresión Gráfica.",
    ):
        add_par(doc, t, "List Paragraph")

    doc.save(SALIDA)
    print("memoria:", SALIDA)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
