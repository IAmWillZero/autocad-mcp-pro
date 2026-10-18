# autocad-mcp-pro

Servidor **MCP (Model Context Protocol)** que da control conversacional sobre **Autodesk AutoCAD**
vía automatización **COM**. Permite que un asistente de IA (Claude, Cursor, VS Code, opencode…)
dibuje geometría, cree estructuras arquitectónicas, gestione capas y limpie el dibujo en tiempo real.

> **Derivado** del proyecto original `autocad-mcp-server` de
> **MC. Peter Alejandro Pérez Chel** (licencia MIT, ver `LICENSE`). Esta versión reorganiza el
> código en un paquete mantenible y corrige comportamientos (ver *Mejoras*).

**Plataforma:** Windows (COM). **Python:** 3.11+. AutoCAD debe estar abierto con un dibujo cargado.

---

## Instalación

```bash
python -m venv venv
venv\Scripts\activate
pip install -e .            # runtime
pip install -e ".[dev]"     # desarrollo (ruff, mypy, pytest)
```

## Ejecución

```bash
python -m autocad_mcp
# o, tras instalar el entrypoint:
autocad-mcp-pro
```

Registra el servidor en tu cliente MCP indicando `python` + la ruta al paquete o el entrypoint.
El transporte es **stdio**, así que sirve para cualquier cliente MCP.

---

## Arquitectura

```
src/autocad_mcp/
├── server.py        # servidor MCP delgado (list_tools / call_tool, stdio)
├── tools.py         # contrato MCP: esquemas de tools + dispatch
├── service.py       # fachada que compone conexión, caché y features
├── connection.py    # conexión COM: reintentos (tenacity) + circuit breaker
├── config.py        # configuración por entorno (pydantic-settings)
├── cache.py         # caché TTL con invalidación por clave/prefijo
├── colors.py        # mapeo de colores a índices ACI
├── layers.py        # definiciones de capas + operaciones de capas
├── obs.py           # logging estructurado + métricas (prometheus opcional)
├── com.py           # helpers VARIANT de pywin32 (único punto junto a connection)
├── standards.py     # estándar de dibujo: capas A-, espesores, estilo de cotas, unidades
└── features/        # operaciones CAD por dominio
    ├── geometry.py    # línea, círculo, rectángulo, polilínea, texto, arco, muro (contorno)
    ├── structures.py  # muros, puertas, ventanas, habitaciones, etiquetas
    ├── info.py        # get_drawing_info, get_entities
    ├── analysis.py    # analyze_drawing: resumen, extents, cotas y anotaciones
    ├── standards.py   # apply_standard: capas A-, unidades, estilo de cotas
    ├── grid.py        # create_construction_grid: ejes con burbujas y rótulos
    ├── dimensions.py  # create_dimension + set_dimension_precision (cotas)
    ├── blocks.py      # list_blocks, create_block, insert_block, explode_entities
    ├── layouts.py     # list/create/set_active layout, create_viewport, plot style table
    ├── documents.py   # list_documents, set_active_document (multi-dibujo)
    ├── delete.py      # borrado por handle/tipo/capa/color (+ purge en delete_all)
    └── ops.py         # undo, recolor, zoom, salud, métricas, batch
```

Regla: **solo `connection.py` y `com.py` tocan `pywin32`/COM**. El resto usa la conexión.

### Multi-documento

Por defecto el servidor se **engancha al dibujo activo en el momento de conectar** y opera sobre él,
aunque cambies de pestaña en AutoCAD (no sigue el foco). Si cierras ese dibujo, se reengancha de forma
silenciosa al que quede activo.

Con varios DWGs abiertos usa:

- `list_documents` → dibujos abiertos con `name`, `path` y `active`.
- `set_active_document(name)` → fija en cuál opera el servidor a partir de ahí.

Si no quieres sorpresas, enfoca el dibujo correcto antes de conectar, o cierra los demás.

---

## Herramientas MCP

| Grupo | Herramientas |
|---|---|
| Info | `get_drawing_info`, `get_entities`, `analyze_drawing`, `health_check`, `get_metrics` |
| Documentos | `list_documents`, `set_active_document` |
| Estándar | `apply_standard` (unidades metro, capas `A-`, estilo de cotas a escala) |
| Ejes | `create_construction_grid` (ejes numerados/letrados; burbujas y rótulo en ambos extremos, con *overshoot* por lado: `overshoot_bottom/top/left/right`) |
| Cotas | `create_dimension` (rotada/alineada/radial/diametral), `set_dimension_precision` (máx. decimales del texto vía `DIMOVERRIDE`) |
| Bloques | `list_blocks`, `create_block` (definir desde entidades por handle), `insert_block`, `explode_entities` |
| Estructuras | `create_structure` (wall/door/window/room + etiquetas; capas `A-`/`I-` automáticas) |
| Muros | `create_wall` (polilínea de contorno con **espesor real**, uniones a inglete), `create_hatch` (poche: relleno `SOLID`/`ANSI31`… de un contorno cerrado) |
| Tablas | `create_table` (tabla nativa `AcDbTable`: cuadro de áreas, leyendas y rótulos; ancho por columna con `col_widths`). Editable y exportable a Excel; su alto/ancho de fila siguen el **estilo de tabla** del dibujo |
| Layouts | `list_layouts`, `create_layout`, `set_active_layout`, `create_viewport` (escala 1:50 → `0.02`), `set_plot_style_table` (`acad.ctb`…) |
| Geometría | `create_line`, `create_circle`, `create_rectangle` (polilínea cerrada), `create_polyline`, `create_text`, `create_arc` |
| Capas | `create_or_get_layer`, `set_current_layer` |
| Borrado | `delete_entity_by_handle`, `delete_entities_by_handles`, `delete_entities_by_type`, `delete_entities_by_layer`, `delete_entities_by_color`, `delete_entities_by_type_and_color`, `delete_last_entities`, `delete_all_entities` (+ purge) |
| Edición | `change_entity_color`, `undo_last_operation`, `zoom_extents` |
| Ops | `clear_cache`, `reload_config`, `batch_execute` |

### Estándar de dibujo (`apply_standard`)

Aplica el estándar arquitectónico del estudio: unidades en **metros** (`INSUNITS=6`, métrico) y las
capas `A-` con color, **espesor jerárquico** y tipo de línea, más el estilo de cotas `MCP-ARQ`
(texto 0.20 m, flecha 0.12 m — a escala real, no del zoom):

| Capa | Color | Espesor | Tipo de línea |
|---|---|---|---|
| `A-MUROS-CARGA` | azul (5) | 0.50 mm | Continua |
| `A-MUROS-TABIQ` | blanco (7) | 0.30 mm | Continua |
| `A-PUER-VENT` | cian (4) | 0.25 mm | Continua |
| `A-MOBILIARIO` | gris (8) | 0.13 mm | Continua |
| `A-COTAS` | rojo (1) | 0.13 mm | Continua |
| `A-EJES` | gris (9) | 0.13 mm | CENTER |
| `A-PROYECC` | rojo (1) | 0.13 mm | HIDDEN |
| `A-TEXTOS` | amarillo (2) | 0.13 mm | Continua |

Todo se dibuja **1:1** en Model con medidas reales; las entidades nuevas quedan **ByLayer**.

Elementos que no son arquitectónicos (MEP, terreno) usan prefijos por disciplina:
`I-ELECTR` / `I-SANIT` / `I-CLIM` (instalaciones) y `A-SITIO` (terreno). `create_structure` y
`create_or_get_layer` resuelven la capa automáticamente (`wall`→`A-MUROS-CARGA`,
`partition`→`A-MUROS-TABIQ`, `door`/`window`→`A-PUER-VENT`, `furniture`→`A-MOBILIARIO`,
`text`/`dimension`→`A-TEXTOS`, etc.).

### Layouts y trazado

El dibujo se hace **1:1 en Model**; la presentación va en **Layouts (espacio papel)**:

- `create_layout(name, media, plot_style_table)` → nueva pestaña; `media` es el nombre canónico
  del papel (p. ej. `ISO_A4_(210.00_x_297.00_MM)`).
- `create_viewport(layout_name, center, width, height, scale, view_center)` → ventana al modelo;
  `scale` es el factor (1:50 → `0.02`, 1:100 → `0.01`).
- `set_active_layout(name)` / `list_layouts()` → cambiar y listar pestañas.
- `set_plot_style_table(layout_name, table)` → asigna un `.ctb`/`.stb` **existente** (`acad.ctb`,
  `monochrome.ctb`…).

> **Nota:** el archivo `.CTB`/`.STB` es binario y AutoCAD **no lo expone por COM**. Este servidor
> asigna el estilo de trazado y fija los **espesores de línea por capa** (que es lo que el `.CTB`
> usa por defecto con `UseObjectLineweight`), pero crear/editar el `.CTB` se hace en AutoCAD
> (*Page Setup Manager* → *Plot Style Table Editor*).

---

## Mejoras frente a la base original

- **Código separado en módulos** (antes: todo en `server.py`).
- **`success` veraz:** `create_line`, `create_text` y `create_arc` ya no devuelven `success: true`
  cuando la operación falló.
- **Caché invalidada en las mutaciones:** crear/borrar/recolorear refresca `get_entities` y
  `get_drawing_info` (antes devolvía datos obsoletos hasta expirar el TTL).
- **Menos errores silenciosos:** los fallos COM se registran en logs estructurados.
- **`prometheus_client` realmente usado** (exporta métricas si está instalado).
- **`create_rectangle` es ahora una polilínea cerrada** (un solo objeto `AcDbPolyline`, no 4 líneas sueltas).
- **Nueva tool `create_polyline`** (polilíneas 2D con cierre y ancho opcionales).
- **Nuevas tools `list_documents` / `set_active_document`** para elegir entre varios dibujos abiertos.
- **Nueva tool `analyze_drawing`**: informe del dibujo (resumen por tipo/capa, extents, cotas con su
  medida y anotaciones) para verificar que lo dibujado es correcto.
- **Layouts/espacio papel**: `list_layouts`, `create_layout`, `set_active_layout`,
  `create_viewport` (con escala) y `set_plot_style_table`.
- **Nuevas tools de bloque `create_block`** (definir bloques desde entidades por handle, con
  `Document.CopyObjects`) y **`create_wall`** (muro como polilínea de contorno con espesor real).
- **Nueva tool `create_table`** (tabla nativa `AcDbTable`): cuadro de áreas, leyendas y rótulos
  editables en AutoCAD y exportables a Excel, en lugar de dibujarlos con líneas sueltas.
- **`create_structure` alineado al estándar `A-`** (antes usaba `WALLS`/`DOORS`/…); añade capas `I-`
  para instalaciones y `A-SITIO` para terreno.
- **Estándar de dibujo profesional**: `apply_standard` (capas `A-` con espesores jerárquicos, unidades
  en metros y estilo de cotas a escala), `create_construction_grid` (ejes de construcción),
  `create_dimension` (cotas) y `list_blocks`/`insert_block`/`explode_entities` (bloques). Ver
  *Estándar de dibujo* arriba.
- **`delete_all_entities` purga el dibujo** (bloques/capas/estilos huérfanos) tras borrar.
- **Compatible con el SDK `mcp` v2** (handlers `on_list_tools`/`on_call_tool` en el constructor;
  `input_schema` en snake_case). Requiere `mcp>=2,<3`.
- **Logs a `stderr`:** por stdio, `stdout` es exclusivo del protocolo JSON-RPC; escribir logs ahí
  corrompía los mensajes. Ahora structlog emite por `stderr`.
- **Color COM en minúscula (`entity.color`):** el typelib de AutoCAD 2025 expone esa propiedad en
  minúscula (DISPID 1280); el *late binding* es case-insensitive, así que `color` funciona en todos los casos.

---

## Verificación

- **Sin AutoCAD** (CI): `ruff check`, `mypy`, `pytest`.
- **Con AutoCAD abierto** (manual): `python tests/smoke_test.py` crea entidades, las lee de vuelta
  con `get_entities` y reporta `PASS/FAIL` por caso.

```bash
ruff check .
ruff format --check .
mypy src
pytest
python tests/smoke_test.py   # requiere AutoCAD
```

## Licencia

MIT — ver `LICENSE`. Este software usa automatización local permitida por Autodesk, pero no está
respaldado por Autodesk, Inc. Requiere una licencia legítima de AutoCAD.
