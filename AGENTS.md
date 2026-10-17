# AutoCAD MCP Server — AGENTS.md

Reglas para todo agente/modelo que trabaje sobre **autocad-mcp-pro**. Derivado del plan
`1792160211030-stack-agentes-mcp.md` y del proyecto original `autocad-mcp-server`
(MC. Peter Alejandro Pérez Chel).

## Stack

| Capa | Herramienta |
|---|---|
| Lenguaje | Python 3.11+ |
| Protocolo | SDK `mcp` (stdio) |
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
└── features/        # geometry, structures, info, documents, delete, ops
tests/               # unit tests (sin AutoCAD) + smoke_test.py (con AutoCAD)
```

## Reglas de unión (inmutables)

1. **Contrato MCP inmutable:** no eliminar ni renombrar herramientas MCP existentes
   (`get_drawing_info`, `get_entities`, `create_structure`, `create_line`, `create_circle`,
   `create_rectangle`, `create_text`, `create_arc`, `create_polyline`, `zoom_extents`,
   `undo_last_operation`,
   `change_entity_color`, `delete_*`, `list_documents`, `set_active_document`, etc.). Los esquemas solo cambian de forma aditiva
   (campos opcionales con default). Candidato de cambio: `tests/test_tool_contract.py`.
2. **Capa de adaptación única:** solo `connection.py` y `com.py` importan `pywin32`/`pythoncom`.
   Ningún otro módulo toca COM directo.
3. **No romper nada:** `ruff check`, `ruff format --check`, `mypy src` y `pytest` deben pasar.
4. **Nueva herramienta:** registrar con nombre único y documentarla aquí y en el `README.md`.

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
