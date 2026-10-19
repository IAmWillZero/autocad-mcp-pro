"""Datos de las plantas de la vivienda UCV (referencial, segun reporte).

ORIENTACION CARDINAL (hipotesis; PENDIENTE de confirmar con datos reales del lote):
- Frente = SUR, fondo = NORTE. Origen (0,0) = esquina SUROESTE.
- Eje X+ = ESTE (ancho 8.00 m). Eje Y+ = NORTE (largo 23.00 m).
- Esquina SE (8,0), NE (8,23), NO (0,23). Unidades metros, 1:1 en Modelo.

Retiros laterales 1.00 m -> ancho construible 6.00 m (x 1.00..7.00).
Vivienda y 4.00..16.00. Jardin frontal (SUR) y 0..4; terraza posterior (NORTE)
y 16..20; jardin posterior (NORTE) y 21..23.

DIMENSIONES: de anteproyecto; NO son de replanteo. Las que no constan en la
referencia se marcan como PENDIENTES (ver comentarios y cuadro de vanos).
"""

from __future__ import annotations

# Zona en X / Y de referencia de dibujo (las plantas se dibujan aparte).
PB_OX = 40.0
PA_OX = 54.0

# ------------------------------------------------------------------ PISO 1
X1 = [1.0, 4.0, 7.0]
Y1 = [4.0, 6.67, 8.33, 9.5, 13.0, 16.0]
ROOMS1 = [
    ("GARAJE", 0, 1, 0, 3),          # SO: x1-4, y4.0-9.5   = 16.50
    ("SALA", 0, 1, 3, 5),            # O:  x1-4, y9.5-16.0  = 19.50
    ("OFICINA", 1, 2, 0, 1),         # SE: x4-7, y4.0-6.67  =  8.00
    ("LAVANDERIA", 1, 2, 1, 2),      # S de la cocina       =  5.00
    ("SS.HH. 1", 1, 2, 2, 3),        # x4-7, y8.33-9.5      =  3.50 (PENDIENTE pos.)
    ("COCINA", 1, 2, 3, 4),          # E junto a sala-com.  = 10.50
    ("COMEDOR", 1, 2, 4, 5),         # N de la cocina       =  9.00
]
# Vano = {id, axis, at, a, b, kind, room, orient, sill}; orient S/N/E/O.
OPEN1 = [
    {"id": "V-01", "axis": "h", "at": 4.0, "a": 1.4, "b": 3.7, "kind": "garage",
     "room": "GARAJE", "orient": "SUR", "sill": 0.0},
    {"id": "P-01", "axis": "h", "at": 4.0, "a": 4.6, "b": 5.5, "kind": "door",
     "into": "+y", "room": "OFICINA", "orient": "SUR", "sill": 0.0},
    {"id": "V-02", "axis": "v", "at": 1.0, "a": 5.5, "b": 7.5, "kind": "window",
     "room": "GARAJE", "orient": "OESTE", "sill": 0.9},
    {"id": "V-03", "axis": "v", "at": 1.0, "a": 10.2, "b": 12.4, "kind": "window",
     "room": "SALA", "orient": "OESTE", "sill": 0.9},
    {"id": "V-04", "axis": "v", "at": 1.0, "a": 13.2, "b": 15.4, "kind": "window",
     "room": "SALA", "orient": "OESTE", "sill": 0.9},
    {"id": "V-05", "axis": "v", "at": 7.0, "a": 4.3, "b": 5.9, "kind": "window",
     "room": "OFICINA", "orient": "ESTE", "sill": 0.9},
    {"id": "V-06", "axis": "v", "at": 7.0, "a": 6.9, "b": 8.2, "kind": "window",
     "room": "LAVANDERIA", "orient": "ESTE", "sill": 1.1},
    {"id": "V-07", "axis": "v", "at": 7.0, "a": 8.5, "b": 9.3, "kind": "window",
     "room": "SS.HH. 1", "orient": "ESTE", "sill": 1.4},
    {"id": "V-08", "axis": "v", "at": 7.0, "a": 9.8, "b": 12.6, "kind": "window",
     "room": "COCINA", "orient": "ESTE", "sill": 1.0},
    {"id": "P-02", "axis": "h", "at": 16.0, "a": 1.6, "b": 3.6, "kind": "sliding",
     "room": "SALA", "orient": "NORTE", "sill": 0.0},
    {"id": "V-09", "axis": "h", "at": 16.0, "a": 4.6, "b": 6.6, "kind": "window",
     "room": "COMEDOR", "orient": "NORTE", "sill": 0.9},
    {"id": "P-03", "axis": "v", "at": 4.0, "a": 4.9, "b": 5.8, "kind": "door",
     "into": "-x", "room": "OFICINA", "orient": "INTERIOR", "sill": 0.0},
    {"id": "P-04", "axis": "h", "at": 9.5, "a": 4.6, "b": 5.4, "kind": "door",
     "into": "-y", "room": "SS.HH. 1", "orient": "INTERIOR", "sill": 0.0},
    {"id": "P-05", "axis": "h", "at": 13.0, "a": 4.5, "b": 5.4, "kind": "door",
     "into": "+y", "room": "COCINA", "orient": "INTERIOR", "sill": 0.0},
]
AXES_V1 = [1.0, 4.0, 7.0]
AXES_H1 = [4.0, 6.67, 9.5, 13.0, 16.0]
FIX1 = [
    ("A-AUTO", [1.5, 4.2], 0.0),
    ("A-COCINA", [4.2, 9.6], 0.0),
    ("A-INODORO", [4.4, 8.5], 0.0),
    ("A-LAVATORIO", [5.3, 8.5], 0.0),
    ("A-MESA", [5.2, 14.4], 0.0),
    ("A-SOFA", [1.3, 11.0], 0.0),
]
TITLE1 = "PLANTA BAJA  1:100  (referencial)"

# ------------------------------------------------------------------ PISO 2
X2 = [1.0, 4.0, 7.0]
Y2 = [4.0, 8.0, 8.33, 9.5, 10.83, 11.33, 16.0]
ROOMS2 = [
    ("DORMITORIO 2", 0, 1, 0, 1),          # SO (ventana/balcon frontal S) = 12.00
    ("SALA DE ESTAR", 0, 1, 1, 5),         # central                     = 10.00
    ("DORMITORIO PRINCIPAL", 0, 1, 5, 6),  # NO (norte y oeste escalera)  = 14.00
    ("DORMITORIO 3", 1, 2, 0, 2),          # SE (ventana/balcon frontal S)= 13.00
    ("SS.HH. NUEVO", 1, 2, 2, 3),          # sobre el SS.HH. de la PB     =  3.50
    ("SS.HH. EXISTENTE", 1, 2, 3, 4),      #                              4.00
    ("ESCALERA / HALL", 1, 2, 4, 6),       # desembarco                   = 15.50
]
OPEN2 = [
    {"id": "V-10", "axis": "h", "at": 4.0, "a": 1.6, "b": 3.4, "kind": "window",
     "room": "DORMITORIO 2", "orient": "SUR", "sill": 0.9},
    {"id": "V-11", "axis": "h", "at": 4.0, "a": 4.6, "b": 6.4, "kind": "window",
     "room": "DORMITORIO 3", "orient": "SUR", "sill": 0.9},
    {"id": "V-12", "axis": "v", "at": 1.0, "a": 5.0, "b": 7.0, "kind": "window",
     "room": "DORMITORIO 2", "orient": "OESTE", "sill": 0.9},
    {"id": "V-13", "axis": "v", "at": 1.0, "a": 12.5, "b": 15.0, "kind": "window",
     "room": "DORMITORIO PRINCIPAL", "orient": "OESTE", "sill": 0.9},
    {"id": "V-14", "axis": "v", "at": 7.0, "a": 5.0, "b": 7.0, "kind": "window",
     "room": "DORMITORIO 3", "orient": "ESTE", "sill": 0.9},
    {"id": "V-15", "axis": "v", "at": 7.0, "a": 12.0, "b": 14.0, "kind": "window",
     "room": "ESCALERA / HALL", "orient": "ESTE", "sill": 0.9},
    {"id": "V-16", "axis": "h", "at": 16.0, "a": 1.6, "b": 3.6, "kind": "window",
     "room": "DORMITORIO PRINCIPAL", "orient": "NORTE", "sill": 0.9},
    {"id": "P-06", "axis": "h", "at": 16.0, "a": 4.8, "b": 6.4, "kind": "sliding",
     "room": "ESCALERA / HALL", "orient": "NORTE", "sill": 0.0},
    {"id": "P-07", "axis": "h", "at": 8.0, "a": 1.5, "b": 2.4, "kind": "door",
     "into": "-y", "room": "DORMITORIO 2", "orient": "INTERIOR", "sill": 0.0},
    {"id": "P-08", "axis": "v", "at": 4.0, "a": 4.9, "b": 5.8, "kind": "door",
     "into": "-x", "room": "DORMITORIO 3", "orient": "INTERIOR", "sill": 0.0},
    {"id": "P-09", "axis": "v", "at": 4.0, "a": 12.0, "b": 12.9, "kind": "door",
     "into": "-x", "room": "DORMITORIO PRINCIPAL", "orient": "INTERIOR", "sill": 0.0},
    {"id": "P-10", "axis": "v", "at": 4.0, "a": 9.6, "b": 10.4, "kind": "door",
     "into": "-x", "room": "SS.HH. EXISTENTE", "orient": "INTERIOR", "sill": 0.0},
]
AXES_V2 = [1.0, 4.0, 7.0]
AXES_H2 = [4.0, 8.0, 11.33, 16.0]
FIX2 = [
    ("A-CAMA-140x200", [1.3, 4.4], 0.0),
    ("A-CAMA-140x200", [5.2, 4.4], 0.0),
    ("A-SOFA", [1.3, 9.0], 0.0),
    ("A-MESA", [2.3, 10.2], 0.0),
    ("A-CAMA-140x200", [1.3, 13.0], 0.0),
    ("A-INODORO", [4.4, 8.5], 0.0),
    ("A-LAVATORIO", [5.3, 8.5], 0.0),
]
TITLE2 = "PLANTA ALTA  1:100  (referencial)"

# Contornos de area libre / balcones (PENDIENTE posicion y dimension reales).
JARDIN_FRONTAL = [[0.0, 0.0], [8.0, 0.0], [8.0, 4.0], [0.0, 4.0]]
TERRAZA_POST = [[1.0, 16.0], [7.0, 16.0], [7.0, 20.0], [1.0, 20.0]]
JARDIN_POST = [[0.0, 21.0], [8.0, 21.0], [8.0, 23.0], [0.0, 23.0]]
BALCON_FRONTAL = [[1.0, 2.0], [7.0, 2.0], [7.0, 4.0], [1.0, 4.0]]
BALCON_POST = [[1.0, 16.0], [7.0, 16.0], [7.0, 18.0], [1.0, 18.0]]
