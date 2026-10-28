# AutoCAD MCP Server — AGENTS.md

Reglas para todo agente/modelo que trabaje sobre **autocad-mcp-pro**. Derivado del plan
`1792160211030-stack-agentes-mcp.md` y del proyecto original `autocad-mcp-server`
(MC. Peter Alejandro Pérez Chel).

## Stack

| Capa | Herramienta |
|---|---|
| Lenguaje | Python 3.11+ |
| Protocolo | SDK `mcp` v2 (stdio) |
| Automatización CAD | `pywin32`, `pythoncom` (COM, solo Windows) |
| Empaquetado | `pyproject.toml` + setuptools (src layout) |
| Lint + formato | `ruff` |
| Tipos | `mypy` |
| Tests | `pytest`, `pytest-asyncio`, `pytest-mock` |
| Config | `pydantic-settings` |
| Reintentos | `tenacity` |
| Caché | TTL propio (`autocad_mcp.cache`) |
| Logging | `structlog` |
| Métricas | `prometheus_client` (opcional en runtime) |

## Estructura

```
src/autocad_mcp/
├── server.py        # servidor MCP delgado (stdio)
├── tools.py         # contrato MCP: esquemas + dispatch
├── service.py       # fachada: conexión + caché + features
├── connection.py    # conexión COM (tenacity + circuit breaker)
├── com.py           # helpers VARIANT
├── config.py / cache.py / colors.py / layers.py / obs.py
├── standards.py     # estándar de dibujo (capas A-/S-, espesores, cotas, unidades)
└── features/        # analysis, standards, grid, dimensions, blocks, geometry, structures,
                     # info, documents, delete, ops, solids (3D), bridges (puentes),
                     # ftool (analisis 2D + exportacion .ftl)
tests/               # unit tests (sin AutoCAD) + smoke_test.py (con AutoCAD)
scripts/bridge/      # build_golden_gate.py: genera el puente, verifica y guarda DWG/PDF/JSON/MD
                     # analyze_golden_gate.py: modelo 2D, .ftl de FTOOL, JSON y MD
```

## Reglas de unión (inmutables)

1. **Contrato MCP inmutable:** no eliminar ni renombrar herramientas MCP existentes
   (`get_drawing_info`, `get_entities`, `analyze_drawing`, `apply_standard`, `create_construction_grid`,
   `create_dimension`, `list_blocks`, `insert_block`, `explode_entities`, `create_block`, `create_wall`,
   `list_layouts`, `create_layout`, `set_active_layout`, `create_viewport`, `set_plot_style_table`,
   `create_structure`,
   `create_line`, `create_circle`,
   `create_rectangle`, `create_text`, `create_arc`, `create_polyline`, `zoom_extents`,
   `undo_last_operation`,
   `change_entity_color`, `delete_*`, `list_documents`, `set_active_document`,
   `create_box_solid`, `create_box_between`, `create_cylinder_solid`, `create_cylinder_between`,
   `create_sphere_solid`, `extrude_polygon`, `boolean_solids`, `move_solid`, `rotate_solid`,
   `scale_solid`, `copy_solid`, `array_solids`, `get_solid_info`, `create_bridge`, `create_cable`,
   `list_bridge_presets`, `get_ftool_status`, `export_ftool_model`, `analyze_bridge_load`, etc.).
   Los esquemas solo cambian de forma aditiva (campos opcionales con default). Candidato de cambio:
   `tests/test_tool_contract.py` (65 herramientas).2. **Capa de adaptación única:** solo `connection.py` y `com.py` importan `pywin32`/`pythoncom`.
   Ningún otro módulo toca COM directo.
3. **`stdout` limpio:** por stdio, `stdout` es exclusivo del JSON-RPC de MCP. Los logs van a
   `stderr` (structlog con `PrintLoggerFactory(file=sys.stderr)`).
4. **Nombres COM exactos:** usar el nombre tal cual lo expone el typelib. En AutoCAD 2025 la
   propiedad de color es `entity.color` / `layer.color` (minúscula, DISPID 1280); el *late binding*
   tolera el case, pero el *early binding* (gen_py) no.
5. **Convenciones 3D verificadas (AutoCAD 2026):** `AddBox`/`AddCylinder`/`AddSphere` reciben el
   **centro**; `Boolean` es `0=unión, 1=intersección, 2=resta` (3 falla); `AddExtrudedSolid` exige un
   `AcDbRegion`; `AddExtrudedSolidAlongPath` falla con trayectorias quebradas (cables = cilindros
   entre puntos); `Rotate3D` en radianes. Ver `features/solids.py`.
6. **No romper nada:** `ruff check`, `ruff format --check`, `mypy src` y `pytest` deben pasar.
7. **Nueva herramienta:** registrar con nombre único y documentarla aquí y en el `README.md`.
8. **Análisis estructural (`features/ftool.py`):** el modelo 2D del Golden Gate (276 nudos, 401
   barras) se resuelve con rigidez directa (skyline LDLᵀ), tracción-solo y P-Δ; el peso propio es el
   estado de referencia y la carga puntual se resuelve como incremento. Los anclajes van al nivel del
   tablero y 50 mm por fuera del apoyo de pila: FTOOL fusiona nudos a menos de 1 mm y, si se baja el
   anclaje, la última barra del cable se hace convexa y comprime los suspensores extremos. El `.ftl`
   4.01 se exporta con un solo caso de carga y debe verificar ida y vuelta (`verify_ftl`). FTOOL no
   guarda resultados: abrir el archivo y ejecutar `Solve`. FTOOL es lineal sin rigidez geométrica,
   así que sus flechas difieren de las del solver interno.
9. **Detalle metálico de puentes (`create_bridge`):** `detail` es aditivo y vale `none` (default),
   `members` (vigas I, placas de nudo/empalme, rigidizadores, apoyos, abrazaderas y sockets) o
   `bolted` (añade pernos/rivets hasta `max_fasteners`, default 1200). Las capas nuevas son
   `S-PLACAS`, `S-RIGIDIZADORES` y `S-PERNOS`, todas de acero. Los pernos son cilindros cortos y el
   resultado devuelve `detail` y `fasteners` (cantidad realmente creada).

## Definition of Done (cada tarea)

1. Función implementada en el módulo de dominio correcto (`features/*`).
2. `ruff` + `mypy` limpios.
3. Test unitario (sin AutoCAD) que cubra la lógica nueva cuando sea posible.
4. **Verificación funcional en AutoCAD real:** `python tests/smoke_test.py` con `PASS`.
5. PR contra `main`.

## Cómo ejecutar

```bash
pip install -e ".[dev]"
python -m autocad_mcp
```

AutoCAD debe estar abierto con un dibujo cargado antes de conectar.

## Calidad

```bash
ruff check .
ruff format --check .
mypy src
pytest
python tests/smoke_test.py   # requiere AutoCAD abierto
```

## Flujo de trabajo

- Ramas `feat/*`, `fix/*`; PR a `main` (GitHub Flow).
- Issues + Milestones (sprints) + tablero Kanban.
- Commits con Conventional Commits (`feat:`, `fix:`, `refactor:`…).
