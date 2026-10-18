"""Datos de la vivienda en lote 8x23 m con retiros laterales (REVISION v2).

SUPUESTOS (provisionales, revision de anteproyecto):
- Lote 8.00 x 23.00 m. Frente y=0 (calle), fondo y=23.
- Retiro lateral 1.00 m por lado -> ancho construible 6.00 m (x 1.00-7.00).
- Jardin frontal y 0-4; vivienda y 4-21; jardin posterior y 21-23.
- Lote AISLADO: las ventanas laterales (x=1 y x=7) son validas (dan a los retiros).
- Entre piso 2.80 m -> 16 alzadas x 0.175 m; escalera en U, ancho util 0.90 m.
- Piso 1 en el origen; Piso 2 desplazado X+16 (solo para dibujo).
- CORRECCIONES aplicadas (docs/REVISION-ARQ.md): grillas alineadas entre plantas,
  banos apilados (una bajante), patio de luz central junto a los banos, balcon
  posterior alineado sobre la terraza, SS.HH.1 >= 2.5 m2.
"""

from __future__ import annotations

OFF2 = 16.0

# ------------------------------------------------------------------ PISO 1
X1 = [1.0, 2.5, 4.0, 7.0]
Y1 = [4.0, 6.0, 8.5, 11.0, 13.0, 15.5, 18.0, 21.0]
ROOMS1 = [
    ("GARAJE", 0, 2, 0, 2),
    ("INGRESO", 2, 3, 0, 1),
    ("OFICINA", 2, 3, 1, 2),
    ("COCINA", 0, 2, 2, 3),
    ("LAVANDERIA", 0, 2, 3, 4),
    ("SALA-COMEDOR", 2, 3, 2, 4),
    ("SS.HH.1", 0, 1, 4, 5),
    ("PATIO DE LUZ", 1, 2, 4, 5),
    ("ESCALERA", 2, 3, 4, 5),
    ("ESTAR", 0, 2, 5, 6),
    ("PASILLO", 2, 3, 5, 6),
    ("TERRAZA", 0, 3, 6, 7),
]
OPEN1 = [
    # --- puertas
    {"axis": "h", "at": 4.0, "a": 1.5, "b": 3.9, "kind": "garage"},
    {"axis": "h", "at": 4.0, "a": 5.4, "b": 6.3, "kind": "door", "into": "+y"},
    {"axis": "v", "at": 4.0, "a": 4.5, "b": 5.4, "kind": "door", "into": "+x"},
    {"axis": "h", "at": 6.0, "a": 4.6, "b": 5.5, "kind": "door", "into": "+y"},
    {"axis": "h", "at": 8.5, "a": 4.6, "b": 5.6, "kind": "open"},
    {"axis": "v", "at": 4.0, "a": 9.0, "b": 10.0, "kind": "open"},
    {"axis": "h", "at": 11.0, "a": 1.4, "b": 2.3, "kind": "door", "into": "+y"},
    {"axis": "h", "at": 13.0, "a": 4.6, "b": 5.6, "kind": "open"},
    {"axis": "h", "at": 15.5, "a": 1.4, "b": 2.3, "kind": "door", "into": "-y"},
    {"axis": "h", "at": 15.5, "a": 4.5, "b": 6.5, "kind": "open"},
    {"axis": "v", "at": 4.0, "a": 16.0, "b": 17.3, "kind": "open"},
    {"axis": "h", "at": 18.0, "a": 1.6, "b": 3.8, "kind": "sliding"},
    {"axis": "h", "at": 18.0, "a": 4.6, "b": 6.6, "kind": "sliding"},
    # --- ventanas (lote aislado: laterales validas)
    {"axis": "v", "at": 1.0, "a": 5.0, "b": 6.6, "kind": "window"},
    {"axis": "v", "at": 1.0, "a": 9.0, "b": 10.2, "kind": "window"},
    {"axis": "v", "at": 1.0, "a": 11.4, "b": 12.4, "kind": "window"},
    {"axis": "v", "at": 1.0, "a": 13.7, "b": 14.7, "kind": "window"},
    {"axis": "v", "at": 1.0, "a": 16.2, "b": 17.6, "kind": "window"},
    {"axis": "v", "at": 7.0, "a": 6.8, "b": 7.9, "kind": "window"},
    {"axis": "v", "at": 7.0, "a": 9.5, "b": 11.5, "kind": "window"},
]
AXES_V1 = [1.0, 4.0, 7.0]
AXES_H1 = [4.0, 8.5, 13.0, 18.0, 21.0]
FIX1 = [
    ("A-AUTO", [1.5, 4.15], 0.0),
    ("A-COCINA", [1.15, 8.6], 0.0),
    ("A-INODORO", [1.1, 14.6], 0.0),
    ("A-LAVATORIO", [1.1, 13.2], 0.0),
    ("A-SOFA", [4.6, 9.5], 0.0),
    ("A-MESA", [5.4, 11.0], 0.0),
    ("A-MESA", [1.5, 16.8], 0.0),
]
TITLE1 = "PLANTA BAJA  1:100  -  VIVIENDA 8.00 x 23.00 m (construible 6.00)"

# ------------------------------------------------------------------ PISO 2
X2 = [1.0, 2.5, 4.0, 5.0, 7.0]
Y2 = [4.0, 7.0, 10.5, 13.0, 15.5, 18.0, 21.0]
ROOMS2 = [
    ("DORMITORIO PRINCIPAL", 0, 2, 0, 3),
    ("CORREDOR", 2, 3, 0, 4),
    ("DORMITORIO 2", 3, 4, 0, 1),
    ("DORMITORIO 3", 3, 4, 1, 3),
    ("SALA DE ESTAR", 0, 2, 2, 3),
    ("SS.HH. NUEVO", 0, 1, 3, 4),
    ("PATIO DE LUZ", 1, 2, 3, 4),
    ("ESCALERA", 2, 4, 3, 4),
    ("ESTAR/ESCRITORIO", 0, 2, 4, 5),
    ("PASILLO", 2, 4, 4, 5),
    ("BALCON POSTERIOR", 0, 4, 5, 6),
]
OPEN2 = [
    # --- puertas
    {"axis": "h", "at": 10.5, "a": 1.6, "b": 2.5, "kind": "door", "into": "-y"},
    {"axis": "v", "at": 4.0, "a": 11.0, "b": 12.4, "kind": "open"},
    {"axis": "v", "at": 5.0, "a": 5.0, "b": 5.9, "kind": "door", "into": "+x"},
    {"axis": "v", "at": 5.0, "a": 9.5, "b": 10.4, "kind": "door", "into": "+x"},
    {"axis": "h", "at": 13.0, "a": 4.2, "b": 5.0, "kind": "open"},
    {"axis": "h", "at": 15.5, "a": 1.4, "b": 2.3, "kind": "door", "into": "-y"},
    {"axis": "h", "at": 15.5, "a": 4.5, "b": 6.6, "kind": "open"},
    {"axis": "v", "at": 4.0, "a": 16.0, "b": 17.3, "kind": "open"},
    {"axis": "h", "at": 18.0, "a": 1.6, "b": 3.8, "kind": "sliding"},
    {"axis": "h", "at": 18.0, "a": 4.6, "b": 6.6, "kind": "sliding"},
    # --- ventanas
    {"axis": "h", "at": 4.0, "a": 1.6, "b": 3.4, "kind": "window"},
    {"axis": "v", "at": 1.0, "a": 5.5, "b": 7.5, "kind": "window"},
    {"axis": "v", "at": 1.0, "a": 8.5, "b": 9.7, "kind": "window"},
    {"axis": "h", "at": 4.0, "a": 5.4, "b": 6.6, "kind": "window"},
    {"axis": "v", "at": 7.0, "a": 4.6, "b": 6.0, "kind": "window"},
    {"axis": "v", "at": 7.0, "a": 8.0, "b": 10.0, "kind": "window"},
    {"axis": "v", "at": 1.0, "a": 11.0, "b": 12.5, "kind": "window"},
    {"axis": "v", "at": 1.0, "a": 13.7, "b": 14.7, "kind": "window"},
    {"axis": "v", "at": 1.0, "a": 16.2, "b": 17.6, "kind": "window"},
]
AXES_V2 = [1.0, 4.0, 5.0, 7.0]
AXES_H2 = [4.0, 10.5, 13.0, 18.0, 21.0]
FIX2 = [
    ("A-CAMA-140x200", [1.3, 4.4], 0.0),
    ("A-SOFA", [1.4, 11.4], 0.0),
    ("A-MESA", [2.5, 12.4], 0.0),
    ("A-CAMA-140x200", [5.2, 4.4], 0.0),
    ("A-CAMA-140x200", [5.2, 8.0], 0.0),
    ("A-INODORO", [1.1, 14.6], 0.0),
    ("A-LAVATORIO", [1.1, 13.2], 0.0),
]
TITLE2 = "PLANTA ALTA  1:100  -  VIVIENDA 8.00 x 23.00 m (construible 6.00)"
BALCON_FRONTAL = [[4.0, 2.0], [7.0, 2.0], [7.0, 4.0]]
STAIR2 = {"x0": 4.3, "x1": 6.7, "y0": 13.1, "y1": 15.4, "risers": 16, "rise": 0.175, "tread": 0.26}
