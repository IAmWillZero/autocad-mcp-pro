"""Estandar de dibujo arquitectonico (datos puros, sin COM).

Define la tabla de capas ``A-`` (Arquitectura), el estilo de cotas a escala y
las unidades por defecto. Los modulos de features aplican estos datos sobre el
documento; aqui solo viven las constantes para no duplicarlas.
"""

from __future__ import annotations

from dataclasses import dataclass

# Prefijos por disciplina (convencion): A- Arquitectura, S- Estructuras,
# M- Mecanica/Instalaciones.
DEFAULT_PREFIX = "A-"


@dataclass(frozen=True)
class LayerSpec:
    """Propiedades estandar de una capa."""

    color: int  # indice ACI
    lineweight: int  # en centesimas de mm (50 = 0.50 mm)
    linetype: str  # "Continuous", "CENTER", "HIDDEN", ...
    description: str = ""


# Tabla de capas estandar con jerarquia de espesores (0.50 -> 0.13 mm).
STANDARD_LAYERS: dict[str, LayerSpec] = {
    "A-MUROS-CARGA": LayerSpec(5, 50, "Continuous", "Muros estructurales cortados"),
    "A-MUROS-TABIQ": LayerSpec(7, 30, "Continuous", "Tabiques divisorios no estructurales"),
    "A-PUER-VENT": LayerSpec(4, 25, "Continuous", "Carpinterias: puertas y ventanas"),
    "A-MOBILIARIO": LayerSpec(8, 13, "Continuous", "Mobiliario y sanitarios fijos"),
    "A-COTAS": LayerSpec(1, 13, "Continuous", "Lineas de dimension principales"),
    "A-EJES": LayerSpec(9, 13, "CENTER", "Ejes estructurales (raya-punto)"),
    "A-PROYECC": LayerSpec(1, 13, "HIDDEN", "Volados, vacios, losas superiores"),
    "A-TEXTOS": LayerSpec(2, 13, "Continuous", "Rotulos y textos generales"),
}

# Estilo de cotas a escala 1:1 en metros (texto/flecha chicos).
DIM_STYLE_NAME = "MCP-ARQ"
DIM_VARIABLES: dict[str, float] = {
    "DIMTXT": 0.2,  # altura de texto
    "DIMASZ": 0.12,  # tamano de flecha
    "DIMEXE": 0.15,  # excedente de linea de extension
    "DIMEXO": 0.08,  # separacion del origen
    "DIMGAP": 0.05,  # separacion texto/linea
    "DIMSCALE": 1.0,  # escala de cotas (1:1 en model)
    "DIMDEC": 3,  # maximo 3 decimales en el texto de cota
    "DIMZIN": 8,  # suprime ceros finales (3.500 -> 3.5)
}

# INSUNITS: 6 = metros.
INSUNITS_METERS = 6
UNITS_VARIABLES: dict[str, int] = {
    "INSUNITS": INSUNITS_METERS,
    "LUNITS": 2,  # decimal
    "LUPREC": 2,
    "MEASUREMENT": 1,  # metrico
}


def axis_number_label(index: int) -> str:
    """Rotulo numerico para el eje vertical ``index`` (1, 2, 3...)."""
    return str(index)


def axis_letter_label(index: int) -> str:
    """Rotulo alfabetico para el eje horizontal ``index`` (A, B, C...)."""
    letters = ""
    n = index
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters
