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
| `check_texts.py` | detección de solapes de texto |
