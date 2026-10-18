"""Datos de la vivienda 8x23 m: grillas, salas, vanos, ejes, cotas y mobiliario.

SUPUESTOS (provisionales): Model 1:1 en metros. Frente y=0 (calle), fondo y=23.
Piso 1 en el origen; Piso 2 desplazado X+16. Altura entre pisos 2.80 m ->
16 alzadas x 0.175 m; escalera en U, ancho util 0.90 m.
"""

from __future__ import annotations

OFF2 = 16.0

# ------------------------------------------------------------------ PISO 1
X1 = [0.0, 1.5, 3.0, 5.5, 8.0]
Y1 = [4.0, 7.0, 10.5, 13.5, 16.0, 17.5, 21.0]
ROOMS1 = [
    ("GARAJE", 0, 2, 0, 2),
    ("INGRESO", 2, 3, 0, 1),
    ("OFICINA", 3, 4, 0, 1),
    ("SALA-COMEDOR", 2, 4, 1, 3),
    ("COCINA", 0, 2, 2, 3),
    ("LAVANDERIA", 0, 2, 3, 4),
    ("SS.HH.1", 0, 1, 4, 5),
    ("PASILLO", 1, 2, 4, 5),
    ("ESTAR", 2, 4, 3, 5),
    ("TERRAZA", 0, 4, 5, 6),
]
OPEN1 = [
    {"axis": "h", "at": 4.0, "a": 0.4, "b": 2.8, "kind": "garage"},
    {"axis": "h", "at": 4.0, "a": 3.6, "b": 4.5, "kind": "door", "into": "+y"},
    {"axis": "v", "at": 5.5, "a": 4.6, "b": 5.5, "kind": "door", "into": "+x"},
    {"axis": "h", "at": 7.0, "a": 3.4, "b": 4.3, "kind": "open"},
    {"axis": "v", "at": 3.0, "a": 11.0, "b": 12.4, "kind": "open"},
    {"axis": "h", "at": 10.5, "a": 0.9, "b": 1.9, "kind": "door", "into": "+y"},
    {"axis": "h", "at": 13.5, "a": 0.9, "b": 1.8, "kind": "door", "into": "+y"},
    {"axis": "h", "at": 16.0, "a": 1.6, "b": 2.5, "kind": "open"},
    {"axis": "v", "at": 1.5, "a": 16.3, "b": 17.2, "kind": "door", "into": "-x"},
    {"axis": "v", "at": 3.0, "a": 16.1, "b": 17.0, "kind": "open"},
    {"axis": "h", "at": 13.5, "a": 4.0, "b": 5.2, "kind": "open"},
    {"axis": "h", "at": 17.5, "a": 3.5, "b": 5.8, "kind": "sliding"},
    {"axis": "v", "at": 8.0, "a": 5.0, "b": 6.2, "kind": "window"},
    {"axis": "v", "at": 8.0, "a": 8.5, "b": 9.7, "kind": "window"},
    {"axis": "v", "at": 8.0, "a": 11.0, "b": 12.2, "kind": "window"},
    {"axis": "v", "at": 8.0, "a": 14.5, "b": 15.7, "kind": "window"},
    {"axis": "v", "at": 0.0, "a": 11.3, "b": 12.3, "kind": "window"},
    {"axis": "v", "at": 0.0, "a": 6.0, "b": 7.5, "kind": "window"},
    {"axis": "v", "at": 0.0, "a": 14.0, "b": 15.0, "kind": "window"},
]
AXES_V1 = [0.0, 3.0, 5.5, 8.0]
AXES_H1 = [4.0, 10.5, 17.5, 21.0]
FIX1 = [
    ("A-AUTO", [0.6, 4.9], 0.0),
    ("A-COCINA", [0.15, 10.65], 0.0),
    ("A-INODORO", [0.2, 16.15], 0.0),
    ("A-LAVATORIO", [0.75, 16.12], 0.0),
    ("A-SOFA", [3.3, 7.6], 0.0),
    ("A-MESA", [4.4, 10.0], 0.0),
    ("A-MESA", [1.2, 18.3], 0.0),
]
TITLE1 = "PLANTA BAJA  1:100  -  VIVIENDA 8.00 x 23.00 m"

# ------------------------------------------------------------------ PISO 2
X2 = [0.0, 3.0, 4.0, 6.0, 8.0]
Y2 = [4.0, 7.0, 9.0, 10.0, 11.0, 12.0, 14.5, 17.5]
ROOMS2 = [
    ("DORMITORIO PRINCIPAL", 0, 1, 0, 3),
    ("SALA DE ESTAR", 0, 1, 3, 6),
    ("CORREDOR", 1, 2, 0, 6),
    ("DORMITORIO 2", 2, 4, 0, 1),
    ("SS.HH. EXISTENTE", 2, 3, 1, 2),
    ("ROPERO", 3, 4, 1, 2),
    ("ESCALERA", 2, 3, 2, 5),
    ("SS.HH. NUEVO", 2, 3, 5, 6),
    ("DORMITORIO 3", 3, 4, 2, 6),
    ("BALCON POSTERIOR", 0, 4, 6, 7),
]
OPEN2 = [
    {"axis": "v", "at": 3.0, "a": 5.5, "b": 6.4, "kind": "door", "into": "-x"},
    {"axis": "v", "at": 3.0, "a": 11.5, "b": 12.4, "kind": "door", "into": "-x"},
    {"axis": "h", "at": 4.0, "a": 1.0, "b": 2.2, "kind": "window"},
    {"axis": "v", "at": 0.0, "a": 6.0, "b": 7.5, "kind": "window"},
    {"axis": "v", "at": 0.0, "a": 11.5, "b": 12.7, "kind": "window"},
    {"axis": "v", "at": 4.0, "a": 5.2, "b": 6.1, "kind": "door", "into": "+x"},
    {"axis": "v", "at": 8.0, "a": 4.6, "b": 5.8, "kind": "window"},
    {"axis": "h", "at": 4.0, "a": 5.0, "b": 7.0, "kind": "sliding"},
    {"axis": "v", "at": 4.0, "a": 7.6, "b": 8.5, "kind": "door", "into": "+x"},
    {"axis": "h", "at": 7.0, "a": 6.6, "b": 7.4, "kind": "door", "into": "+y"},
    {"axis": "v", "at": 4.0, "a": 9.5, "b": 11.8, "kind": "open"},
    {"axis": "v", "at": 4.0, "a": 12.7, "b": 13.6, "kind": "door", "into": "+x"},
    {"axis": "h", "at": 14.5, "a": 4.6, "b": 5.4, "kind": "window"},
    {"axis": "v", "at": 6.0, "a": 11.0, "b": 11.9, "kind": "door", "into": "+x"},
    {"axis": "v", "at": 8.0, "a": 12.0, "b": 13.2, "kind": "window"},
    {"axis": "h", "at": 14.5, "a": 1.0, "b": 2.6, "kind": "sliding"},
    {"axis": "h", "at": 14.5, "a": 6.5, "b": 7.5, "kind": "sliding"},
]
AXES_V2 = [0.0, 3.0, 4.0, 6.0, 8.0]
AXES_H2 = [4.0, 7.0, 11.0, 14.5, 17.5]
FIX2 = [
    ("A-CAMA-140x200", [0.3, 4.3], 0.0),
    ("A-SOFA", [0.15, 11.0], 0.0),
    ("A-MESA", [1.0, 12.5], 0.0),
    ("A-CAMA-140x200", [4.3, 4.3], 0.0),
    ("A-INODORO", [4.2, 7.2], 0.0),
    ("A-LAVATORIO", [4.2, 8.3], 0.0),
    ("A-CAMA-140x200", [6.2, 12.0], 0.0),
    ("A-INODORO", [4.2, 12.3], 0.0),
    ("A-LAVATORIO", [5.3, 12.25], 0.0),
    ("A-DUCHA", [4.05, 13.55], 0.0),
]
TITLE2 = "PLANTA ALTA  1:100  -  VIVIENDA 8.00 x 23.00 m"
BALCON_FRONTAL = [[4.0, 1.5], [8.0, 1.5], [8.0, 4.0]]
STAIR2 = {"x0": 4.0, "x1": 6.0, "y0": 9.0, "y1": 12.0, "risers": 16, "rise": 0.175, "tread": 0.26}
