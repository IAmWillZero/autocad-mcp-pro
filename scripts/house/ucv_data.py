"""Datos de la vivienda UCV Magisterial 230 - correccion de diseno.

ORIENTACION CARDINAL (confirmada por el usuario):
- Frente = SUR, fondo = NORTE. Origen (0,0) = esquina SUROESTE.
- Eje X+ = ESTE (ancho del LOTE 8.00 m). Eje Y+ = NORTE (largo 23.00 m).
- Esquina SE (8,0), NE (8,23), NO (0,23). Unidades metros, 1:1 en Modelo.
- La planta baja ocupa TODO el ancho del lote (x 0.00..8.00), sin retiros
  laterales, y llega hasta y=21.00. No hay terraza.

SECUENCIA DEL SECTOR ESTE (de norte a sur):
  COCINA (con vista y salida al jardin posterior) -> LAVANDERIA ->
  SS.HH. 1 -> ESCALERA (pegada a la pared este) -> CORREDOR ->
  HALL DE RECIBO -> OFICINA (con vista al jardin frontal).

El hall de ingreso esta entre la cochera y la oficina, y abre directamente
a la sala de estar. Sala y comedor forman un espacio integrado; el comedor
queda al fondo, con ventanas amplias y salida al jardin posterior.

No se plantean terrazas. En planta alta hay un balcon interior hacia la escalera.
El jardin posterior ocupa y=21.00..23.00.

DIMENSIONES de anteproyecto; no son de replanteo. Muros de 0.15 m.
"""

from __future__ import annotations

# Zona de dibujo de las plantas desarrolladas (la zonificacion va aparte).
PB_OX = 40.0
PA_OX = 54.0

# Grillas por planta. X incluye el borde del corredor (5.80) y el eje de
# tabiqueria de los banos del segundo piso (5.50).
X1 = [0.0, 3.0, 4.4, 6.2, 8.0]
X2 = [0.0, 3.0, 4.4, 6.2, 8.0]

# Primer piso: ocupa TODO el ancho del lote (8.00 m) y llega hasta y=21.00.
# No hay retiros laterales ni terraza; queda el jardin posterior y=21..23.
Y1 = [4.00, 9.50, 12.50, 14.25, 16.00, 18.00, 19.00, 21.00]
# Segundo piso: misma huella que la planta baja (todo el ancho, y4.00-21.00).
Y2 = [4.00, 9.50, 11.60, 12.50, 14.25, 17.25, 19.00, 21.00]

#               label          i0 i1 j0 j1
ROOMS1 = [
    ("GARAJE", 0, 1, 0, 1),  # x0-3   y4.00-9.50  = 16.50
    ("HALL", 1, 2, 0, 1),  # x3-4.4 y4.00-9.50  =  7.70
    ("OFICINA", 2, 4, 0, 1),  # x4.4-8 y4.00-9.50  = 19.80
    ("ESCALERA", 2, 4, 1, 2),  # x4.4-8 y9.50-12.50 = 10.80
    ("CORREDOR", 1, 2, 1, 5),  # x3-4.4 y9.50-18.00 = 11.90
    ("SALA DE ESTAR", 0, 1, 1, 5),  # x0-3   y9.50-18.00 = 25.50
    ("SS.HH. 1", 2, 4, 2, 3),  # x4.4-8 y12.50-14.25=  6.30
    ("LAVANDERIA", 2, 4, 3, 4),  # x4.4-8 y14.25-16.00=  6.30
    ("COCINA", 2, 4, 4, 6),  # x4.4-8 y16.00-19.00= 10.80
    ("COMEDOR", 0, 2, 5, 7),  # x0-4.4 y18.00-21.00= 13.20
]

ROOMS2 = [
    ("DORMITORIO 2", 0, 2, 0, 1),  # x0-4.4 y4.00-9.50  = 24.20
    ("DORMITORIO 3", 2, 4, 0, 1),  # x4.4-8  y4.00-9.50  = 19.80
    ("SALA DE ESTAR", 0, 1, 1, 4),  # x0-3.0 y9.50-14.25  = 14.25
    ("HALL", 1, 2, 1, 4),  # x3.0-4.4 y9.50-14.25=  6.65 (circulacion)
    ("BALCON", 2, 3, 1, 2),  # x4.4-6.2 y9.50-11.60=  3.78 (interior, Dorm. 3)
    ("ESCALERA", 3, 4, 1, 3),  # x6.2-8  y9.50-12.50 =  5.40 (L, muro este)
    ("TRAMO 2", 2, 3, 2, 3),  # x4.4-6.2 y11.60-12.50= 1.62 (segundo tramo)
    ("SS.HH. 3", 2, 4, 3, 4),  # x4.4-8  y12.50-14.25 = 6.30 (sobre SS.HH.1 PB)
    ("DORMITORIO PRINCIPAL", 0, 2, 4, 7),  # x0-4.4 y14.25-21.00 = 29.70
    ("SS.HH. 2", 2, 4, 4, 5),  # x4.4-8 y14.25-17.25 = 10.80 (suite)
    ("VESTIDOR 2", 2, 4, 5, 6),  # x4.4-8 y17.25-21.00 = 13.50
]

# Categoria de zonificacion por ambiente (SOC/SER/PRI/CIR/LIB).
ZONE = {
    "GARAJE": "SER",
    "OFICINA": "SOC",
    "HALL": "CIR",
    "BALCON": "CIR",
    "ESCALERA": "CIR",
    "TRAMO 2": "CIR",
    "CORREDOR": "CIR",
    "LAVANDERIA": "SER",
    "COCINA": "SER",
    "SS.HH. 1": "SER",
    "SS.HH. 2": "SER",
    "SS.HH. 3": "SER",
    "SALA-COMEDOR": "SOC",
    "SALA DE ESTAR": "SOC",
    "COMEDOR": "SOC",
    "DORMITORIO 2": "PRI",
    "DORMITORIO 3": "PRI",
    "DORMITORIO PRINCIPAL": "PRI",
    "VESTIDOR 2": "PRI",
}

# Escalera en L: primer tramo pegado al muro ESTE, giro al oeste.
STAIR = {"x0": 4.40, "x1": 8.00, "y0": 9.50, "y1": 12.50}

# --- vanos: {id, axis, at, a, b, kind, room, orient, sill} ---
OPEN1 = [
    {
        "id": "V-01",
        "axis": "h",
        "at": 4.0,
        "a": 0.5,
        "b": 2.8,
        "kind": "garage",
        "room": "GARAJE",
        "orient": "SUR",
        "sill": 0.0,
    },
    {
        "id": "P-01",
        "axis": "h",
        "at": 4.0,
        "a": 3.15,
        "b": 4.25,
        "kind": "door",
        "into": "+y",
        "room": "HALL",
        "orient": "SUR",
        "sill": 0.0,
    },
    {
        "id": "V-20",
        "axis": "h",
        "at": 4.0,
        "a": 5.0,
        "b": 7.5,
        "kind": "window",
        "room": "OFICINA",
        "orient": "SUR",
        "sill": 0.9,
    },
    {
        "id": "P-11",
        "axis": "v",
        "at": 3.0,
        "a": 5.2,
        "b": 6.1,
        "kind": "door",
        "into": "-x",
        "room": "GARAJE",
        "orient": "INTERIOR",
        "sill": 0.0,
    },
    {
        "id": "P-03",
        "axis": "v",
        "at": 4.4,
        "a": 5.2,
        "b": 6.1,
        "kind": "door",
        "into": "+x",
        "room": "OFICINA",
        "orient": "INTERIOR",
        "sill": 0.0,
    },
    {
        "id": "P-32",
        "axis": "v",
        "at": 4.4,
        "a": 14.5,
        "b": 15.4,
        "kind": "door",
        "into": "+x",
        "room": "LAVANDERIA",
        "orient": "INTERIOR",
        "sill": 0.0,
    },
    {
        "id": "P-10",
        "axis": "h",
        "at": 9.5,
        "a": 3.2,
        "b": 4.1,
        "kind": "door",
        "into": "+y",
        "room": "CORREDOR",
        "orient": "INTERIOR",
        "sill": 0.0,
    },
    {
        "id": "P-12",
        "axis": "v",
        "at": 3.0,
        "a": 9.7,
        "b": 11.5,
        "kind": "open",
        "room": "SALA DE ESTAR",
        "orient": "INTERIOR",
        "sill": 0.0,
    },
    {
        "id": "P-15",
        "axis": "v",
        "at": 4.4,
        "a": 10.0,
        "b": 11.5,
        "kind": "open",
        "room": "ESCALERA",
        "orient": "INTERIOR",
        "sill": 0.0,
    },
    {
        "id": "P-05",
        "axis": "v",
        "at": 4.4,
        "a": 12.8,
        "b": 13.7,
        "kind": "door",
        "into": "+x",
        "room": "SS.HH. 1",
        "orient": "INTERIOR",
        "sill": 0.0,
    },
    {
        "id": "P-08",
        "axis": "v",
        "at": 4.4,
        "a": 16.2,
        "b": 17.8,
        "kind": "open",
        "room": "COCINA",
        "orient": "INTERIOR",
        "sill": 0.0,
    },
    {
        "id": "P-09",
        "axis": "h",
        "at": 18.0,
        "a": 0.8,
        "b": 4.2,
        "kind": "open",
        "room": "COMEDOR",
        "orient": "INTERIOR",
        "sill": 0.0,
    },
    {
        "id": "P-06",
        "axis": "v",
        "at": 4.4,
        "a": 18.5,
        "b": 19.0,
        "kind": "open",
        "room": "COCINA",
        "orient": "INTERIOR",
        "sill": 0.0,
    },
    {
        "id": "P-13",
        "axis": "h",
        "at": 21.0,
        "a": 1.5,
        "b": 3.5,
        "kind": "sliding",
        "room": "COMEDOR",
        "orient": "NORTE",
        "sill": 0.0,
    },
    {
        "id": "P-14",
        "axis": "h",
        "at": 19.0,
        "a": 5.5,
        "b": 7.5,
        "kind": "sliding",
        "room": "COCINA",
        "orient": "NORTE",
        "sill": 0.0,
    },
    {
        "id": "V-10",
        "axis": "h",
        "at": 21.0,
        "a": 0.4,
        "b": 1.3,
        "kind": "window",
        "room": "COMEDOR",
        "orient": "NORTE",
        "sill": 0.9,
    },
    {
        "id": "V-12",
        "axis": "h",
        "at": 21.0,
        "a": 3.7,
        "b": 4.2,
        "kind": "window",
        "room": "COMEDOR",
        "orient": "NORTE",
        "sill": 0.9,
    },
]
AXES_V1 = [0.0, 3.0, 4.4, 6.2, 8.0]
AXES_H1 = [4.0, 9.5, 12.5, 14.25, 16.0, 18.0, 21.0]

OPEN2 = [
    {
        "id": "V-11",
        "axis": "h",
        "at": 4.0,
        "a": 1.4,
        "b": 3.7,
        "kind": "window",
        "room": "DORMITORIO 2",
        "orient": "SUR",
        "sill": 0.9,
    },
    {
        "id": "V-13",
        "axis": "h",
        "at": 4.0,
        "a": 5.0,
        "b": 7.5,
        "kind": "window",
        "room": "DORMITORIO 3",
        "orient": "SUR",
        "sill": 0.9,
    },
    {
        "id": "V-16",
        "axis": "h",
        "at": 21.0,
        "a": 1.0,
        "b": 3.6,
        "kind": "window",
        "room": "DORMITORIO PRINCIPAL",
        "orient": "NORTE",
        "sill": 0.9,
    },
    {
        "id": "P-20",
        "axis": "h",
        "at": 9.5,
        "a": 3.2,
        "b": 4.1,
        "kind": "door",
        "into": "-y",
        "room": "DORMITORIO 2",
        "orient": "INTERIOR",
        "sill": 0.0,
    },
    {
        "id": "P-21",
        "axis": "h",
        "at": 9.5,
        "a": 4.8,
        "b": 5.7,
        "kind": "door",
        "into": "-y",
        "room": "DORMITORIO 3",
        "orient": "INTERIOR",
        "sill": 0.0,
    },
    {
        "id": "P-22",
        "axis": "v",
        "at": 3.0,
        "a": 10.5,
        "b": 13.5,
        "kind": "open",
        "room": "HALL",
        "orient": "INTERIOR",
        "sill": 0.0,
    },
    {
        "id": "P-23",
        "axis": "v",
        "at": 6.2,
        "a": 10.0,
        "b": 11.5,
        "kind": "open",
        "room": "ESCALERA",
        "orient": "INTERIOR",
        "sill": 0.0,
    },
    {
        "id": "P-24",
        "axis": "v",
        "at": 4.4,
        "a": 13.0,
        "b": 13.9,
        "kind": "door",
        "into": "+x",
        "room": "SS.HH. 3",
        "orient": "INTERIOR",
        "sill": 0.0,
    },
    {
        "id": "P-25",
        "axis": "h",
        "at": 14.25,
        "a": 3.2,
        "b": 4.2,
        "kind": "door",
        "into": "+y",
        "room": "DORMITORIO PRINCIPAL",
        "orient": "INTERIOR",
        "sill": 0.0,
    },
    {
        "id": "P-26",
        "axis": "v",
        "at": 4.4,
        "a": 15.0,
        "b": 15.9,
        "kind": "door",
        "into": "+x",
        "room": "SS.HH. 2",
        "orient": "INTERIOR",
        "sill": 0.0,
    },
    {
        "id": "P-27",
        "axis": "h",
        "at": 17.25,
        "a": 5.0,
        "b": 5.9,
        "kind": "door",
        "into": "+y",
        "room": "VESTIDOR 2",
        "orient": "INTERIOR",
        "sill": 0.0,
    },
    {
        "id": "P-28",
        "axis": "h",
        "at": 11.6,
        "a": 4.8,
        "b": 5.7,
        "kind": "open",
        "room": "TRAMO 2",
        "orient": "INTERIOR",
        "sill": 0.0,
    },
    {
        "id": "P-29",
        "axis": "v",
        "at": 4.4,
        "a": 11.7,
        "b": 12.4,
        "kind": "open",
        "room": "HALL",
        "orient": "INTERIOR",
        "sill": 0.0,
    },
    {
        "id": "P-30",
        "axis": "v",
        "at": 6.2,
        "a": 11.7,
        "b": 12.4,
        "kind": "open",
        "room": "ESCALERA",
        "orient": "INTERIOR",
        "sill": 0.0,
    },
    {
        "id": "P-31",
        "axis": "v",
        "at": 4.4,
        "a": 10.0,
        "b": 11.5,
        "kind": "open",
        "room": "BALCON",
        "orient": "INTERIOR",
        "sill": 0.0,
    },
]
AXES_V2 = [0.0, 3.0, 4.4, 6.2, 8.0]
AXES_H2 = [4.0, 9.5, 11.6, 12.5, 14.25, 17.25, 21.0]

# Sin mobiliario/bloques por ahora (pedido del usuario).
FIX1: list = []
FIX2: list = []

TITLE1 = "PLANTA BAJA  1:100  (sin terraza)"
TITLE2 = "PLANTA ALTA  1:100  (sin terraza; balcon interior)"

# Areas libres / jardin. El balcon del segundo piso es interior, no exterior.
JARDIN_FRONTAL = [[0.0, 0.0], [8.0, 0.0], [8.0, 4.0], [0.0, 4.0]]
TERRAZA_POST: list[list[float]] = []
JARDIN_POST = [[0.0, 21.0], [8.0, 21.0], [8.0, 23.0], [0.0, 23.0]]
JARDIN_NOTCH_PB = [[4.4, 19.0], [8.0, 19.0], [8.0, 21.0], [4.4, 21.0]]
TERRAZA_NOTCH = [[4.4, 19.0], [8.0, 19.0], [8.0, 21.0], [4.4, 21.0]]
BALCON_FRONTAL: list[list[float]] = []
BALCON_POST: list[list[float]] = []

# Niveles propuestos (altura entre pisos 2.80 m: PENDIENTE de confirmar).
NPT_PB = "+0.00"
NPT_PA = "+2.80"
H_ENTREPISO = 2.80
H_TECHO = 5.60

# Cuadro de areas de referencia del reporte (para contraste).
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
    "SS.HH. 2": 3.5,
    "SS.HH. 3": 3.5,
    "SALA DE ESTAR": 10.0,
    "DORMITORIO 2": 12.0,
    "DORMITORIO 3": 12.0,
}
