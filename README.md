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
└── features/        # operaciones CAD por dominio
    ├── geometry.py    # línea, círculo, rectángulo, texto, arco
    ├── structures.py  # muros, puertas, ventanas, habitaciones, etiquetas
    ├── info.py        # get_drawing_info, get_entities
    ├── delete.py      # borrado por handle/tipo/capa/color
    └── ops.py         # undo, recolor, zoom, salud, métricas, batch
```

Regla: **solo `connection.py` y `com.py` tocan `pywin32`/COM**. El resto usa la conexión.

---

## Herramientas MCP

| Grupo | Herramientas |
|---|---|
| Info | `get_drawing_info`, `get_entities`, `health_check`, `get_metrics` |
| Estructuras | `create_structure` (wall/door/window/room + etiquetas y capas automáticas) |
| Geometría | `create_line`, `create_circle`, `create_rectangle`, `create_text`, `create_arc` |
| Capas | `create_or_get_layer`, `set_current_layer` |
| Borrado | `delete_entity_by_handle`, `delete_entities_by_handles`, `delete_entities_by_type`, `delete_entities_by_layer`, `delete_entities_by_color`, `delete_entities_by_type_and_color`, `delete_last_entities`, `delete_all_entities` |
| Edición | `change_entity_color`, `undo_last_operation`, `zoom_extents` |
| Ops | `clear_cache`, `reload_config`, `batch_execute` |

---

## Mejoras frente a la base original

- **Código separado en módulos** (antes: todo en `server.py`).
- **`success` veraz:** `create_line`, `create_text` y `create_arc` ya no devuelven `success: true`
  cuando la operación falló.
- **Caché invalidada en las mutaciones:** crear/borrar/recolorear refresca `get_entities` y
  `get_drawing_info` (antes devolvía datos obsoletos hasta expirar el TTL).
- **Menos errores silenciosos:** los fallos COM se registran en logs estructurados.
- **`prometheus_client` realmente usado** (exporta métricas si está instalado).

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
