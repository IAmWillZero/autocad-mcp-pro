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
| Modelado 3D | `create_box_solid`, `create_box_between`, `create_cylinder_solid`, `create_cylinder_between`, `create_sphere_solid`, `extrude_polygon`, `boolean_solids`, `move_solid`, `rotate_solid`, `scale_solid`, `copy_solid`, `array_solids`, `get_solid_info` (sólidos `AcDb3dSolid`, volumen y extents) |
| Puentes | `create_bridge` (tipologías `girder`/`arch`/`cable_stayed`/`suspension`, preset `golden_gate` con dimensiones reales), `create_cable` (catenaria con flecha), `list_bridge_presets` |
| Análisis 2D | `get_ftool_status`, `export_ftool_model` (`.ftl` 4.01 verificado por ida y vuelta), `analyze_bridge_load` (reacciones, flechas y axiles con carga puntual) |
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

Las **obras de arte** (puentes) usan la disciplina `S-` (Estructuras):

| Capa | Color | Espesor | Uso |
|---|---|---|---|
| `S-TABLERO` | cian (4) | 0.35 mm | Losa y superficie de rodadura |
| `S-VIGAS` | azul (5) | 0.25 mm | Vigas, diafragmas y barreras |
| `S-PILAS` | magenta (6) | 0.50 mm | Pilas, pilotes y cabezales |
| `S-TORRES` | rojo (1) | 0.50 mm | Torres y pilonos |
| `S-CABLES` | amarillo (2) | 0.25 mm | Cables principales, suspensores y tirantes |
| `S-ESTRIBOS` | verde (3) | 0.50 mm | Estribos y bloques de anclaje |
| `S-ARCO` | naranja (30) | 0.35 mm | Arcos y montantes |
| `S-PAVIMENTO` | gris (8) | 0.13 mm | Calzada de asfalto y señalización |
| `S-EQUIPAMIENTO` | cian (4) | 0.18 mm | Barandillas, farolas y juntas de dilatación |
| `S-PLACAS` | gris claro (9) | 0.18 mm | Vigas I, placas de nudo/empalme y apoyos |
| `S-RIGIDIZADORES` | gris (8) | 0.18 mm | Rigidizadores, diafragmas y cartelas |
| `S-PERNOS` | blanco (7) | 0.13 mm | Pernos, rivets y pasadores |

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

### Modelado 3D (`S-`)

El modelado se hace con sólidos reales `AcDb3dSolid` a escala 1:1 en metros, no con mallas ni
caras. Convenciones COM **verificadas en AutoCAD 2026 (25.1)** con *late binding*:

- `AddBox`, `AddCylinder` y `AddSphere` reciben el **centro** de la primitiva (no una esquina).
- `Boolean` usa `0 = unión`, `1 = intersección`, `2 = resta`; el valor `3` no es válido y los
  nombres de `AcBoolean` del typelib no coinciden con esos índices.
- `AddExtrudedSolid` exige un **`AcDbRegion`**, no una polilínea: `extrude_polygon` crea el
  *region* internamente y lo elimina después.
- `AddExtrudedSolidAlongPath` falla con trayectorias quebradas (*General modeling failure*), por eso
  los cables se aproximan con **cilindros entre puntos** (`create_cylinder_between`).
- `Rotate3D` trabaja en **radianes** (la tool `rotate_solid` recibe grados y convierte).

| Tool | Para qué sirve |
|---|---|
| `create_box_solid` | Caja centrada en `center` con `length/width/height` y rotación sobre Z |
| `create_box_between` | Caja alineada entre dos puntos (diagonales, montantes, segmentos de arco) |
| `create_cylinder_solid` / `create_cylinder_between` | Pilotes verticales / cables, suspensores y tirantes |
| `create_sphere_solid` | Nudos y detalles |
| `extrude_polygon` | Perfiles cerrados (arcos, losas) con ángulo de desmoldeo |
| `boolean_solids` | Unión, intersección y resta entre sólidos |
| `move_solid` / `rotate_solid` | Colocar y orientar piezas ya creadas |
| `scale_solid` | Escala uniforme respecto a un punto base |
| `copy_solid` / `array_solids` | Copiar un sólido (con giro opcional) o una matriz lineal de copias |
| `get_solid_info` | Cantidad, volumen total, volumen por capa y *extents* del modelo |

### Puentes (`create_bridge`)

Genera un puente completo combinando los sólidos anteriores: tablero, vigas, pilas, estribos,
torres, cables y suspensores, cada uno en su capa `S-`.

```jsonc
// Golden Gate a escala real con detalle metalico completo
{"preset": "golden_gate", "name": "GOLDEN GATE", "detail": "bolted"}

// Solo vigas I, placas y rigidizadores (sin pernos)
{"preset": "golden_gate", "detail": "members"}

// Viga-losa genérico de 3 vanos
{"kind": "girder", "total_length": 120, "deck_width": 10, "clearance": 10, "spans": 3}

// Atirantado con dos pilonos
{"kind": "cable_stayed", "total_length": 600, "main_span": 400, "tower_height": 120, "pylons": 2}
```

Tipologías: `girder` (viga-losa), `arch` (arco), `cable_stayed` (atirantado) y `suspension`
(colgante). Cualquier dimensión del preset se puede sobrescribir con los argumentos de la tool
(`total_length`, `deck_width`, `deck_depth`, `clearance`, `main_span`, `side_span`,
`tower_height`, `cable_sag`, `cable_diameter`, `suspender_spacing`, `spans`, `pylons`,
`arch_rise`, `n_approach_piers`, `origin`).

El detalle metálico es aditivo y se controla con `detail`:

| Valor | Qué añade |
|---|---|
| `none` (default) | Modelo estructural base, sin detalle metalico |
| `members` | Vigas I longitudinales y transversales, placas de nudo y empalme, rigidizadores de torre/pilono, cartelas, apoyos de placa y herrajes de cable (abrazaderas, sockets y pasadores) |
| `bolted` | Todo lo anterior más pernos/rivets en empalmes, apoyos, anclajes y abrazaderas, hasta `max_fasteners` (default 1200) |

Los pernos se generan como cilindros cortos en `S-PERNOS`; el tope `max_fasteners` evita que un
modelo grande sature el dibujo y el resultado informa cuántos se crearon realmente (`fasteners`).

El preset **`golden_gate`** usa las dimensiones públicas del Golden Gate Bridge:

| Dato | Valor |
|---|---|
| Longitud total | 2737 m |
| Luz principal | 1280 m |
| Vanos laterales | 343 m cada uno |
| Altura de torres | 227 m sobre el agua |
| Calado del tablero | 67 m |
| Ancho de tablero | 27.4 m |
| Canto del tablero | 7.6 m |
| Flecha del cable | 143 m |
| Diámetro del cable | 0.92 m |
| Separación de suspensores | 15.24 m |

El modelo incluye tablero con calzada de asfalto, mediana, aceras y señalización; cercha Warren con
vigas transversales y arriostramiento inferior en X; barandillas y farolas; torres con remates y
monturas de cable; suspensores dobles con abrazaderas; diques de protección (fenders); estribos
escalonados con bloques de anclaje; juntas de dilatación y el arco Fort Point. Con
`detail="bolted"` se añaden 8 vigas I de piso, vigas transversales, placas de empalme en los
cordones, rigidizadores en las torres, apoyos de acero, zapatas de anclaje de cable, sockets y
pasadores en cada suspensor, y una matriz de pernos/rivets en las conexiones. El resultado añade
**desglose por material** (hormigón 2400 kg/m³, acero 7850, asfalto 2400) con masa en toneladas.

Para construirlo en un dibujo nuevo, guardarlo y trazarlo:

```bash
python scripts/bridge/build_golden_gate.py                    # Golden Gate + DWG/PDF/JSON/MD
python scripts/bridge/build_golden_gate.py --detail members  # sin pernos
python scripts/bridge/build_golden_gate.py --max-fasteners 600
python scripts/bridge/build_golden_gate.py --smoke            # puente viga-losa de prueba
python scripts/bridge/build_golden_gate.py --out C:\salida    # otra carpeta
python scripts/bridge/build_golden_gate.py --no-plot          # sin PDF
python scripts/bridge/build_golden_gate.py --no-verify        # sin verificación
```

Los archivos se guardan en `~/Documents/BlancaNieves/salida` (DWG, PDF, JSON y un informe
`Puente-Golden-Gate.md` con sólidos, volumen, masa, materiales, capas y comprobaciones). La carpeta
se puede cambiar con `--out` o con la variable de entorno `GOLDEN_GATE_OUT`. Si el PDF está abierto
en un visor y Windows lo bloquea, se escribe una copia con marca de tiempo
(`Puente-Golden-Gate-<fecha>.pdf`) y el JSON/MD indican la ruta realmente generada.

### Análisis estructural 2D y FTOOL

El Golden Gate también se resuelve como modelo de barras 2D en el plano longitudinal X-Y, sin
necesidad de AutoCAD. Incluye tablero continuo, pilas y estribos, torres empotradas en la base,
cables principales con la flecha real (143 m) y suspensores cada 15.24 m.

| Dato | Valor |
|---|---|
| Nudos | 276 |
| Barras | 401 (130 cable, 142 tablero, 127 suspensores, 2 torres) |
| Anclajes | extremos de los vanos laterales, `x = ±983 m`, al nivel del tablero y 50 mm fuera del apoyo de pila |
| Aproximaciones | pilas cada ~64 m hasta los estribos en `x = ±1368.5 m` |
| Unidades | kN, m, rad; carga vertical positiva hacia abajo |

El **peso propio** se resuelve como estado de referencia: los axiles iniciales de cables
(`H = W·L / 8f`) y suspensores entran como cargas nodales equivalentes, de modo que el caso de
carga puntual se resuelve como incremento linealizado sobre ese estado. El solver es de rigidez
directa con matriz *skyline* LDLᵀ, iteración de **tracción-solo** y rigidez geométrica **P-Δ**.

Los anclajes se sitúan **al nivel del tablero** y 50 mm por fuera del apoyo de pila. El desfase
evita que FTOOL fusione ambos nudos (su tolerancia es de 1 mm) y perdería el apoyo de rodillo del
tablero; además mantiene la pendiente del cable decreciente hacia el anclaje. Con los anclajes 2 m
por debajo del tablero la última barra del cable se hacía convexa y aparecían compresiones falsas
en los suspensores extremos. Con la geometría actual el estado de peso propio deja **0 suspensores
destensados** y las 401 barras activas.

| Herramienta | Uso |
|---|---|
| `get_ftool_status` | Ruta de FTOOL detectada, carpeta de salida y limitaciones del formato |
| `export_ftool_model` | Escribe el `.ftl` 4.01 (con `load_x`/`load_kN` opcionales) y verifica la ida y vuelta |
| `analyze_bridge_load` | Resuelve una carga puntual y devuelve reacciones, flechas y axiles |

```jsonc
// Carga puntual de 1000 kN en el centro del vano principal
{"x": 0, "magnitude": 1000}

// Exportar el modelo con la carga incluida
{"load_x": 0, "load_kN": 1000}

// Guardar el .ftl en otra ruta
{"path": "C:/salida/Golden-Gate.ftl", "load_kN": 0}
```

Resultados de referencia con **1000 kN** en el centro:

| Magnitud | Peso propio | Incremento | Total |
|---|---:|---:|---:|
| Flecha máxima del tablero | 0.140 m | 0.131 m | 0.271 m |
| Axil máximo de cable | 487 685 kN | 1 930 kN | 489 615 kN |
| Axil máximo de suspensor | 3 043 kN | 92 kN | 3 136 kN |
| Reacción en base de torre | 1 216 236 kN | 3 253 kN | 1 219 489 kN |

El equilibrio global se comprueba con fuerzas y momentos: el error relativo es ~0 en `fy` y
~2e-6 en `mz`.

El archivo `.ftl` sigue el formato **FTL 4.01** documentado por ingeniería inversa. FTOOL no guarda
resultados: hay que abrirlo y ejecutar **Solve**. La edición estándar admite **un solo caso de
carga**, por eso la carga puntual se incluye al exportar. La configuración opcional
`AUTOCAD_MCP_FTOOL_EXE` y `AUTOCAD_MCP_FTOOL_OUTPUT_DIR` permite fijar el ejecutable y la carpeta
de salida.

```bash
# Modelo 2D + .ftl + JSON + informe en ~/Documents/BlancaNieves/salida
python scripts/bridge/analyze_golden_gate.py

# Barrido de posiciones de la carga
python scripts/bridge/analyze_golden_gate.py --load 2000 --sweep 0 320 640 960
```

Limitaciones: FTOOL resuelve elasticidad lineal **sin** rigidez geométrica, por lo que sus flechas
difieren de las del solver interno; los cables y suspensores se exportan como barras articuladas
(`truss`) y las torres/tablero como pórticos.

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
- **Modelado 3D real (`AcDb3dSolid`)**: 13 tools (cajas, cilindros, esferas, extrusión de regiones,
  booleanos, mover/rotar/escalar, copiar/array y `get_solid_info`), **`create_bridge`** con 4
  tipologías y el preset `golden_gate` a escala real (2737 m, torres 227 m), `create_cable` con
  flecha parabólica y `list_bridge_presets`. Ver *Modelado 3D* arriba.
- **Análisis estructural 2D y FTOOL** (3 tools): `get_ftool_status`, `export_ftool_model` (`.ftl`
  4.01 verificado por ida y vuelta) y `analyze_bridge_load` (reacciones, flechas, axiles y equilibrio
  con carga puntual). Incluye un solver propio con tracción-solo y P-Δ. Ver *Análisis estructural 2D
  y FTOOL* arriba.
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
- **Puente real** (manual): `python scripts/bridge/build_golden_gate.py` genera el Golden Gate en un
  dibujo nuevo, ejecuta una **verificación automática** de cotas, torres, suspensores y materiales, y
  guarda DWG, PDF, JSON y el informe `Puente-Golden-Gate.md`.
- **Análisis 2D** (sin AutoCAD): `python scripts/bridge/analyze_golden_gate.py` resuelve el modelo de
  barras, verifica el equilibrio global y el `.ftl`, y guarda el archivo de FTOOL, un JSON y el
  informe `Golden-Gate-Analisis.md`.

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
