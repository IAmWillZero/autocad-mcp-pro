"""Datos de las plantas de la vivienda UCV (referencial, segun reporte).

Criterio: lote 8x23, retiros laterales 1.00 m -> ancho construible 6.00 m
(x 1.00..7.00). Frente y=0. Programa de areas del reporte (referencial):
- PB: garaje 16, oficina 8, lavanderia 5, SS.HH. 3.5, cocina 10.5, sala-comedor 28.
- PA: dorm. principal 14, SS.HH. existente 4, SS.HH. nuevo 3.5, dorm. 2 12,
      dorm. 3 12, sala de estar 10.

Las dimensiones son de anteproyecto (no de replanteo); deben verificarse.
"""

from __future__ import annotations

PB_OX = 40.0
PA_OX = 54.0

# ------------------------------------------------------------------ PISO 1
X1 = [1.0, 4.0, 7.0]
Y1 = [4.0, 6.7, 8.37, 9.6, 12.9, 16.0]
ROOMS1 = [
    ("GARAJE", 0, 2, 0, 1),          # 6x2.70 = 16.2
    ("OFICINA", 0, 1, 1, 3),         # 3x2.90 =  8.7
    ("LAVANDERIA", 1, 2, 1, 2),      # 3x1.67 =  5.0
    ("SS.HH. 1", 1, 2, 2, 3),        # 3x1.23 =  3.7
    ("COCINA", 0, 1, 3, 4),          # 3x3.30 =  9.9
    ("COMEDOR", 1, 2, 3, 4),         # 3x3.30 =  9.9
    ("SALA", 0, 2, 4, 5),            # 6x3.10 = 18.6
]
OPEN1 = [
    {"axis": "h", "at": 4.0, "a": 1.4, "b": 3.8, "kind": "garage"},
    {"axis": "h", "at": 4.0, "a": 5.4, "b": 6.3, "kind": "door", "into": "+y"},
    {"axis": "v", "at": 1.0, "a": 7.0, "b": 8.4, "kind": "window"},
    {"axis": "v", "at": 4.0, "a": 7.3, "b": 8.2, "kind": "door", "into": "-x"},
    {"axis": "v", "at": 4.0, "a": 6.9, "b": 7.7, "kind": "door", "into": "+x"},
    {"axis": "v", "at": 7.0, "a": 6.9, "b": 8.1, "kind": "window"},
    {"axis": "h", "at": 9.6, "a": 4.4, "b": 5.2, "kind": "door", "into": "-y"},
    {"axis": "v", "at": 7.0, "a": 8.5, "b": 9.4, "kind": "window"},
    {"axis": "v", "at": 4.0, "a": 10.2, "b": 12.6, "kind": "open"},
    {"axis": "h", "at": 12.9, "a": 4.4, "b": 6.6, "kind": "open"},
    {"axis": "v", "at": 1.0, "a": 10.2, "b": 12.4, "kind": "window"},
    {"axis": "h", "at": 16.0, "a": 1.8, "b": 5.0, "kind": "sliding"},
    {"axis": "v", "at": 1.0, "a": 13.5, "b": 15.3, "kind": "window"},
]
AXES_V1 = [1.0, 4.0, 7.0]
AXES_H1 = [4.0, 6.7, 9.6, 12.9, 16.0]
FIX1 = [
    ("A-AUTO", [1.6, 4.2], 0.0),
    ("A-COCINA", [1.15, 9.9], 0.0),
    ("A-INODORO", [4.6, 8.9], 0.0),
    ("A-LAVATORIO", [5.4, 8.7], 0.0),
    ("A-MESA", [5.4, 10.6], 0.0),
    ("A-SOFA", [3.0, 14.2], 0.0),
]
TITLE1 = "PLANTA BAJA  1:100  -  VIVIENDA UCV MAGISTERIAL N.230 (referencial)"

# ------------------------------------------------------------------ PISO 2
X2 = [1.0, 4.0, 7.0]
Y2 = [4.0, 6.33, 7.66, 8.82, 9.66, 13.66]
ROOMS2 = [
    ("DORMITORIO PRINCIPAL", 0, 2, 0, 1),  # 6x2.33 = 14.0
    ("SS.HH. EXISTENTE", 1, 2, 1, 2),      # 3x1.33 =  4.0
    ("SS.HH. NUEVO", 1, 2, 2, 3),          # 3x1.16 =  3.5
    ("ROPERO", 1, 2, 3, 4),                # 3x0.84 =  2.5
    ("SALA DE ESTAR", 0, 1, 1, 4),         # 3x3.33 = 10.0
    ("DORMITORIO 2", 0, 1, 4, 5),          # 3x4.00 = 12.0
    ("DORMITORIO 3", 1, 2, 4, 5),          # 3x4.00 = 12.0
]
OPEN2 = [
    {"axis": "h", "at": 4.0, "a": 2.0, "b": 4.5, "kind": "window"},
    {"axis": "h", "at": 6.33, "a": 1.5, "b": 2.4, "kind": "door", "into": "-y"},
    {"axis": "v", "at": 4.0, "a": 6.6, "b": 7.4, "kind": "door", "into": "-x"},
    {"axis": "v", "at": 7.0, "a": 6.5, "b": 7.5, "kind": "window"},
    {"axis": "v", "at": 4.0, "a": 7.9, "b": 8.6, "kind": "door", "into": "-x"},
    {"axis": "v", "at": 4.0, "a": 8.9, "b": 9.6, "kind": "open"},
    {"axis": "v", "at": 1.0, "a": 7.0, "b": 9.0, "kind": "window"},
    {"axis": "h", "at": 9.66, "a": 1.5, "b": 2.4, "kind": "door", "into": "+y"},
    {"axis": "v", "at": 1.0, "a": 10.5, "b": 12.5, "kind": "window"},
    {"axis": "v", "at": 4.0, "a": 10.0, "b": 10.9, "kind": "door", "into": "-x"},
    {"axis": "v", "at": 7.0, "a": 10.5, "b": 12.5, "kind": "window"},
    {"axis": "h", "at": 13.66, "a": 1.5, "b": 3.8, "kind": "sliding"},
    {"axis": "h", "at": 13.66, "a": 4.6, "b": 6.6, "kind": "sliding"},
]
AXES_V2 = [1.0, 4.0, 7.0]
AXES_H2 = [4.0, 6.33, 9.66, 13.66]
FIX2 = [
    ("A-CAMA-140x200", [1.3, 4.4], 0.0),
    ("A-CAMA-140x200", [5.2, 4.4], 0.0),
    ("A-INODORO", [4.6, 7.0], 0.0),
    ("A-LAVATORIO", [5.4, 6.8], 0.0),
    ("A-SOFA", [2.2, 7.0], 0.0),
    ("A-MESA", [2.2, 8.6], 0.0),
    ("A-CAMA-140x200", [1.3, 11.2], 0.0),
    ("A-CAMA-140x200", [5.2, 11.2], 0.0),
]
TITLE2 = "PLANTA ALTA  1:100  -  VIVIENDA UCV MAGISTERIAL N.230 (referencial)"
