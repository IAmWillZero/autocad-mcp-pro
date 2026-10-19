"""Datos de las plantas de la vivienda UCV (referencial, segun reporte).

ORIENTACION CARDINAL (confirmada por el usuario):
- Frente = SUR, fondo = NORTE. Origen (0,0) = esquina SUROESTE.
- Eje X+ = ESTE (ancho del LOTE 8.00 m). Eje Y+ = NORTE (largo 23.00 m).
- Esquina SE (8,0), NE (8,23), NO (0,23). Unidades metros, 1:1 en Modelo.
- Retiros laterales 1.00 m -> ancho CONSTRUIDO 6.00 m (x 1.00..7.00).

Grillas COMPARTIDAS por las dos plantas (coordinacion de muros/ejes):
  X = [1.00, 4.00, 7.00]
  Y = [4.00, 6.67, 8.00, 8.33, 9.33, 11.33, 11.83, 13.00, 16.00]

SS.HH.: la vivienda tiene EXACTAMENTE dos banos. SS.HH. 1 (PB) y SS.HH. 2 (PA)
comparten la MISMA planta baja/alta (mismas X e Y): x 4.00..7.00, y 11.83..13.00,
situados al NORTE del nucleo de escalera (y 8.33..11.83).

DIMENSIONES de anteproyecto; NO son de replanteo. Lo que no consta se marca
PENDIENTE (ver cuadros y notas).
"""

from __future__ import annotations

# Zona de dibujo de las plantas desarrolladas (la zonificacion va aparte).
PB_OX = 40.0
PA_OX = 54.0

X1 = [1.0, 4.0, 7.0]
X2 = [1.0, 4.0, 7.0]
YS = [4.00, 6.67, 8.00, 8.33, 9.33, 11.33, 11.83, 13.00, 16.00]
Y1 = list(YS)
Y2 = list(YS)

ROOMS1 = [
    ("GARAJE", 0, 1, 0, 4),        # SO: x1-4 y4.00-9.33   = 16.00
    ("SALA-COMEDOR", 0, 1, 4, 8),  # O + centro            = 20.00
    ("OFICINA", 1, 2, 0, 1),       # SE: x4-7 y4.00-6.67   =  8.00
    ("LAVANDERIA", 1, 2, 1, 3),    # x4-7 y6.67-8.33       =  5.00
    ("ESCALERA", 1, 2, 3, 6),      # nucleo x4-7 y8.33-11.83 = 10.50
    ("SS.HH. 1", 1, 2, 6, 7),      # x4-7 y11.83-13.00     =  3.51 (N de escalera)
    ("COCINA", 1, 2, 7, 8),        # NE: x4-7 y13.00-16.00 =  9.00
]

ROOMS2 = [
    ("DORMITORIO 2", 0, 1, 0, 2),          # SO                    = 12.00
    ("SALA DE ESTAR", 0, 1, 2, 5),         # central               = 10.00
    ("DORMITORIO PRINCIPAL", 0, 1, 5, 8),  # NO                    = 14.00
    ("DORMITORIO 3", 1, 2, 0, 3),          # SE                    = 13.00
    ("ESCALERA", 1, 2, 3, 6),              # nucleo                = 10.50
    ("SS.HH. 2", 1, 2, 6, 7),              # N de escalera, apilado=  3.51
    ("HALL", 1, 2, 7, 8),                  # desembarco            =  9.00
]

# Categoria de zonificacion por ambiente (SOC/SER/PRI/CIR/LIB).
ZONE = {
    "GARAJE": "SER",
    "OFICINA": "SOC",
    "LAVANDERIA": "SER",
    "COCINA": "SER",
    "SS.HH. 1": "SER",
    "SS.HH. 2": "SER",
    "SALA-COMEDOR": "SOC",
    "DORMITORIO 2": "PRI",
    "DORMITORIO 3": "PRI",
    "DORMITORIO PRINCIPAL": "PRI",
    "SALA DE ESTAR": "PRI",
    "ESCALERA": "CIR",
    "HALL": "CIR",
}

# Estructura de escalera (apilada en ambas plantas): x4-7, y8.33-11.83.
STAIR = {"x0": 4.00, "x1": 7.00, "y0": 8.33, "y1": 11.83}

# --- vanos: {id, axis, at, a, b, kind, room, orient, sill} ---
OPEN1 = [
    {"id": "V-01", "axis": "h", "at": 4.0, "a": 1.4, "b": 3.7, "kind": "garage",
     "room": "GARAJE", "orient": "SUR", "sill": 0.0},
    {"id": "P-01", "axis": "h", "at": 4.0, "a": 4.6, "b": 5.5, "kind": "door",
     "into": "+y", "room": "OFICINA", "orient": "SUR", "sill": 0.0},
    {"id": "V-02", "axis": "v", "at": 1.0, "a": 5.5, "b": 7.5, "kind": "window",
     "room": "GARAJE", "orient": "OESTE", "sill": 0.9},
    {"id": "V-03", "axis": "v", "at": 1.0, "a": 10.5, "b": 12.4, "kind": "window",
     "room": "SALA-COMEDOR", "orient": "OESTE", "sill": 0.9},
    {"id": "V-04", "axis": "v", "at": 1.0, "a": 13.2, "b": 15.4, "kind": "window",
     "room": "SALA-COMEDOR", "orient": "OESTE", "sill": 0.9},
    {"id": "V-05", "axis": "v", "at": 7.0, "a": 4.3, "b": 5.9, "kind": "window",
     "room": "OFICINA", "orient": "ESTE", "sill": 0.9},
    {"id": "V-06", "axis": "v", "at": 7.0, "a": 6.9, "b": 8.2, "kind": "window",
     "room": "LAVANDERIA", "orient": "ESTE", "sill": 1.1},
    {"id": "V-07", "axis": "v", "at": 7.0, "a": 8.7, "b": 11.5, "kind": "window",
     "room": "ESCALERA", "orient": "ESTE", "sill": 0.9},
    {"id": "V-08", "axis": "v", "at": 7.0, "a": 12.0, "b": 12.8, "kind": "window",
     "room": "SS.HH. 1", "orient": "ESTE", "sill": 1.4},
    {"id": "V-09", "axis": "v", "at": 7.0, "a": 13.3, "b": 15.7, "kind": "window",
     "room": "COCINA", "orient": "ESTE", "sill": 1.0},
    {"id": "P-02", "axis": "h", "at": 16.0, "a": 1.6, "b": 3.6, "kind": "sliding",
     "room": "SALA-COMEDOR", "orient": "NORTE", "sill": 0.0},
    {"id": "V-10", "axis": "h", "at": 16.0, "a": 4.6, "b": 6.6, "kind": "window",
     "room": "COCINA", "orient": "NORTE", "sill": 1.0},
    {"id": "P-03", "axis": "h", "at": 6.67, "a": 5.0, "b": 5.9, "kind": "door",
     "into": "+y", "room": "LAVANDERIA", "orient": "INTERIOR", "sill": 0.0},
    {"id": "P-04", "axis": "h", "at": 8.33, "a": 5.0, "b": 5.9, "kind": "door",
     "into": "+y", "room": "ESCALERA", "orient": "INTERIOR", "sill": 0.0},
    {"id": "P-05", "axis": "v", "at": 4.0, "a": 9.0, "b": 11.5, "kind": "open",
     "room": "SALA-COMEDOR", "orient": "INTERIOR", "sill": 0.0},
    {"id": "P-06", "axis": "v", "at": 4.0, "a": 12.1, "b": 12.9, "kind": "door",
     "into": "-x", "room": "SS.HH. 1", "orient": "INTERIOR", "sill": 0.0},
    {"id": "P-07", "axis": "v", "at": 4.0, "a": 13.6, "b": 15.6, "kind": "open",
     "room": "COCINA", "orient": "INTERIOR", "sill": 0.0},
]
AXES_V1 = [1.0, 4.0, 7.0]
AXES_H1 = [4.0, 6.67, 8.33, 11.83, 13.0, 16.0]

OPEN2 = [
    {"id": "V-11", "axis": "h", "at": 4.0, "a": 1.6, "b": 3.4, "kind": "window",
     "room": "DORMITORIO 2", "orient": "SUR", "sill": 0.9},
    {"id": "V-12", "axis": "h", "at": 4.0, "a": 4.6, "b": 6.4, "kind": "window",
     "room": "DORMITORIO 3", "orient": "SUR", "sill": 0.9},
    {"id": "V-13", "axis": "v", "at": 1.0, "a": 5.0, "b": 7.0, "kind": "window",
     "room": "DORMITORIO 2", "orient": "OESTE", "sill": 0.9},
    {"id": "V-14", "axis": "v", "at": 1.0, "a": 12.5, "b": 15.0, "kind": "window",
     "room": "DORMITORIO PRINCIPAL", "orient": "OESTE", "sill": 0.9},
    {"id": "V-15", "axis": "v", "at": 7.0, "a": 5.0, "b": 7.0, "kind": "window",
     "room": "DORMITORIO 3", "orient": "ESTE", "sill": 0.9},
    {"id": "V-16", "axis": "v", "at": 7.0, "a": 13.5, "b": 15.5, "kind": "window",
     "room": "HALL", "orient": "ESTE", "sill": 0.9},
    {"id": "V-17", "axis": "v", "at": 7.0, "a": 12.0, "b": 12.8, "kind": "window",
     "room": "SS.HH. 2", "orient": "ESTE", "sill": 1.4},
    {"id": "V-18", "axis": "h", "at": 16.0, "a": 1.6, "b": 3.6, "kind": "window",
     "room": "DORMITORIO PRINCIPAL", "orient": "NORTE", "sill": 0.9},
    {"id": "P-08", "axis": "h", "at": 16.0, "a": 4.8, "b": 6.4, "kind": "sliding",
     "room": "HALL", "orient": "NORTE", "sill": 0.0},
    {"id": "P-09", "axis": "h", "at": 8.0, "a": 1.5, "b": 2.4, "kind": "door",
     "into": "-y", "room": "DORMITORIO 2", "orient": "INTERIOR", "sill": 0.0},
    {"id": "P-10", "axis": "h", "at": 8.33, "a": 4.6, "b": 5.5, "kind": "door",
     "into": "-y", "room": "DORMITORIO 3", "orient": "INTERIOR", "sill": 0.0},
    {"id": "P-11", "axis": "h", "at": 11.33, "a": 1.5, "b": 2.4, "kind": "door",
     "into": "+y", "room": "DORMITORIO PRINCIPAL", "orient": "INTERIOR", "sill": 0.0},
    {"id": "P-12", "axis": "h", "at": 11.83, "a": 4.6, "b": 5.4, "kind": "door",
     "into": "+y", "room": "SS.HH. 2", "orient": "INTERIOR", "sill": 0.0},
    {"id": "P-13", "axis": "v", "at": 4.0, "a": 9.0, "b": 11.0, "kind": "open",
     "room": "SALA DE ESTAR", "orient": "INTERIOR", "sill": 0.0},
]
AXES_V2 = [1.0, 4.0, 7.0]
AXES_H2 = [4.0, 8.0, 8.33, 11.33, 11.83, 13.0, 16.0]

FIX1 = [
    ("A-AUTO", [1.4, 4.4], 0.0),
    ("A-COCINA", [4.2, 13.8], 0.0),
    ("A-INODORO", [4.4, 12.4], 0.0),
    ("A-LAVATORIO", [5.3, 12.4], 0.0),
    ("A-DUCHA", [6.0, 11.95], 0.0),
    ("A-MESA", [1.5, 14.5], 0.0),
    ("A-SOFA", [1.4, 10.6], 0.0),
]
FIX2 = [
    ("A-CAMA-140x200", [1.3, 4.3], 0.0),
    ("A-CAMA-140x200", [5.2, 4.3], 0.0),
    ("A-CAMA-140x200", [1.3, 12.0], 0.0),
    ("A-SOFA", [1.3, 8.6], 0.0),
    ("A-MESA", [2.3, 9.6], 0.0),
    ("A-INODORO", [4.4, 12.4], 0.0),
    ("A-LAVATORIO", [5.3, 12.4], 0.0),
    ("A-DUCHA", [6.0, 11.95], 0.0),
]

TITLE1 = "PLANTA BAJA  1:100  (referencial)"
TITLE2 = "PLANTA ALTA  1:100  (referencial)"

# Contornos de area libre / balcones (PENDIENTE posicion real).
JARDIN_FRONTAL = [[0.0, 0.0], [8.0, 0.0], [8.0, 4.0], [0.0, 4.0]]
TERRAZA_POST = [[1.0, 16.0], [7.0, 16.0], [7.0, 20.0], [1.0, 20.0]]
JARDIN_POST = [[0.0, 21.0], [8.0, 21.0], [8.0, 23.0], [0.0, 23.0]]
BALCON_FRONTAL = [[1.0, 2.0], [7.0, 2.0], [7.0, 4.0], [1.0, 4.0]]
BALCON_POST = [[1.0, 16.0], [7.0, 16.0], [7.0, 18.0], [1.0, 18.0]]

# Niveles propuestos (altura entre pisos 2.80 m: PENDIENTE de confirmar).
NPT_PB = "+0.00"
NPT_PA = "+2.80"

# Cuadro de areas de referencia del reporte (para contraste).
REF_PB = {"GARAJE": 16.0, "OFICINA": 8.0, "LAVANDERIA": 5.0, "SS.HH. 1": 3.5,
          "COCINA": 10.5, "SALA-COMEDOR": 28.0}
REF_PA = {"DORMITORIO PRINCIPAL": 14.0, "SS.HH. 2": 3.5, "SALA DE ESTAR": 10.0,
          "DORMITORIO 2": 12.0, "DORMITORIO 3": 12.0}
