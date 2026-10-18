# scripts/house — dibujo de la vivienda de referencia (2 plantas, 8×23 m)

Scripts de desarrollo que dibujan, por COM (MCP), una vivienda de dos plantas
sobre un lote de 8×23 m, aplicando el estándar del estudio (capas `A-`, unidades
m, cotas a 3 niveles, muros con espesor real, vanos, mobiliario en bloques,
poche de muros, cuadro de áreas y norte).

## Requisitos

- AutoCAD abierto (con cualquier dibujo o ninguno).
- Entorno instalado: `pip install -e ".[dev]"`.

Los scripts **no tocan** otros documentos abiertos: crean/usan un DWG dedicado
`out/CASA.dwg` (carpeta `out/`, ignorada por git).

## Ejecución

Desde la raíz del repo:

```bash
python scripts/house/draw_house.py     # dibuja y crea los layouts
python scripts/house/mk_layouts.py     # recrea PLANTA BAJA / PLANTA ALTA (si hace falta)
python scripts/house/verify_house.py   # conteos, capas, ByLayer, bbox
python scripts/house/check_texts.py    # solapes de texto (debe imprimir 0)
```

El estándar de la casa se define en `house_data.py` (grillas, salas, vanos,
mobiliario, escalera). Todas las cotas del programa son **provisionales** hasta
que el comitente confirme el programa y el tipo de lote (aislado vs. entre
medianeras).

## Archivos

| Archivo | Rol |
|---|---|
| `house_data.py` | datos (grillas X/Y, salas, vanos, bloques, escalera, títulos) |
| `house_geom.py` | muros únicos, vanos, espesores, aperturas |
| `house_draw.py` | etiquetas de ambientes, escalera, ejes, cotas |
| `house_blocks.py` | definición de bloques (puerta, artefactos, muebles) |
| `house_main.py` | helpers (`_retry`, `_draw_floor`) |
| `draw_house.py` | orquestador: dibuja todo y arma layouts |
| `mk_layouts.py` | layouts A3 con viewport a escala |
| `verify_house.py` | verificación determinística del dibujo |
| `check_texts.py` | detección de solapes de texto (bbox real) |
| `check_labels.py` | verifica que cada rótulo quede **dentro** de su ambiente |

## Tabla de áreas (`create_table`) — nota importante

La tool MCP `create_table` inserta una tabla nativa (`AcDbTable`). En este AutoCAD la
API COM **no permite fijar** alto de fila ni ancho de columna (quedan gobernados por
el *estilo de tabla* activo), y por eso el cuadro de áreas del dibujo se traza con
líneas a escala real (`_draw_area_table`).

Para que `create_table` salga a escala métrica, configura el estilo de tabla antes
de usarla (una sola vez por plantilla/DWG):

1. `_TABLESTYLE` → **New** → nombre `MCP-TABLA`.
2. En *Data*: **Text height** = `0.18`, **Row height** = `0.40`.
3. En *Title/Header*: text height `0.18` (o desactiva ambas filas).
4. Cierra el diálogo y crea una tabla con `_TABLE` (usa `MCP-TABLA`). El estilo
   activo queda en la variable de sistema `CTABLESTYLE`.
5. Desde ahí, `create_table` respetará ese estilo.

Con el estilo activo correcto, `create_table(data=[["AMBIENTE","AREA"], ...])`
inserta el cuadro de áreas editable y exportable a Excel.

