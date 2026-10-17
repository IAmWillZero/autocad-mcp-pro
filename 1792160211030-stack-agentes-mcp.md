# Plan: Stack básico potente y reglas de unión de agentes/modelos — AutoCAD MCP Server

**Plan:** `1792160211030-stack-agentes-mcp.md`
**Estado:** Listo para implementación

---

## 1. Objetivo

Definir un stack básico pero potente para el servidor AutoCAD MCP y las reglas de integración para que distintos agentes y modelos de código puedan trabajar sobre el servidor sin romper contratos existentes.

Decisión resuelta: la unión es **agentes de código + MCP** (consumen las herramientas MCP existentes). "No romper nada" significa: no eliminar ni renombrar herramientas MCP, mantener el esquema de entrada/salida estable, y que los tests de CI pasen.

---

## 2. Stack básico potente

| Capa | Herramienta | Rol |
|---|---|---|
| Lenguaje | Python 3.11+ | Runtime del servidor (ya usado) |
| Protocolo | SDK `mcp` | Transporte stdio, registro de herramientas, capacidades |
| Automatización CAD | `pywin32`, `pythoncom` | COM hacia AutoCAD (Windows) |
| Empaquetado | `pyproject.toml` + setuptools | Instalación reproducible (`pip install -e .`) |
| Lint + formato | `ruff` | Un solo binary, rápido, reemplaza flake8/isort/black |
| Tipos estáticos | `mypy` | Detección de errores antes del runtime |
| Tests | `pytest`, `pytest-asyncio`, `pytest-mock` | Tests con mocks de COM (sin AutoCAD real) |
| Configuración | `pydantic-settings` | Variables de entorno con valores por defecto |
| Reintentos | `tenacity` | Backoff exponencial para COM inestable |
| Caché | `cachetools` / `functools.lru_cache` | TTL para entidades y capas; reduce llamadas COM |
| Logging | `structlog` / `logging` | Logging estructurado con correlation ID |
| Métricas | `prometheus_client` | Contador de llamadas, latencia, errores (`get_metrics`) |
| Calidad local | `pre-commit` | Hooks de lint/format/test antes de cada commit |
| CI | GitHub Actions | Matriz: lint, typecheck, test, build en cada push |
| Contenedor | `Docker` + `docker-compose` | Build multi-stage, capa de dependencias cacheada |

---

## 3. Reglas de unión de agentes y modelos (sin romper nada)

Estas reglas aplican a cualquier agente o modelo que se integre con el servidor.

### 3.1 Contrato MCP inmutable
- Las herramientas MCP existentes (`get_drawing_info`, `get_entities`, `create_structure`, etc.) **no se eliminan ni renombran**.
- Los esquemas de entrada (JSON Schema) y salida de cada herramienta se mantienen estables; cambios solo son aditivos (campos opcionales nuevos con valor por defecto).
- Cualquier herramienta nueva se registra con nombre único y se documenta en `AGENTS.md`.

### 3.2 Capa de adaptación única
- Los agentes y modelos **no acceden directo a `pywin32`/`COM`**. Toda interacción con AutoCAD pasa por la clase `AutoCADCOMServer` y sus herramientas MCP expuestas.
- Esto desacopla al agente del runtime de CAD y permite tests sin AutoCAD instalado.

### 3.3 Ejecución no bloqueante y caché
- Las llamadas COM lentas se ejecutan en `run_in_executor` (no bloquean el event loop `asyncio`).
- `get_entities` y `get_drawing_info` usan caché con TTL para evitar recorrer `ModelSpace` repetidamente.
- Se añade herramienta `batch_execute` para agrupar operaciones en una sola pasada por `ModelSpace`.

### 3.4 Resiliencia de conexión
- Reconexión con `tenacity` (backoff exponencial) + circuit breaker.
- `health_check` devuelve estado `OK`/`ERROR` antes de operaciones críticas.
- Fallo parcial no aborta todo el lote: `try/except` por entidad, continuar con el resto.

### 3.5 Observabilidad mínima
- Logging estructurado con correlation ID por llamada MCP.
- Métricas: contador de llamadas, latencia, errores (expuesto vía `get_metrics`).
- Cada agente que ejecute operaciones debe poder consultar `get_metrics` y `health_check`.

### 3.6 Tests obligatorios sin AutoCAD real
- Toda funcionalidad nueva debe tener tests unitarios con `pytest-mock` mockeando `pywin32`/`COM`.
- Tests de integración con AutoCAD real son opcionales y condicionados a su disponibilidad (no bloquean CI).
- Umbral mínimo de cobertura definido en CI.

### 3.7 Versionado y rollback
- Versión del servidor en `pyproject.toml` y `server_version` en `InitializationOptions`.
- Cambios rompientes requieren nueva versión mayor y aviso en `AGENTS.md`.
- Rollback: `git revert` del commit afectado + reinicio del cliente MCP (Claude Desktop).

---

## 4. Flujo de datos (resumen)

```
Agente/Modelo (código)
        ↓ llama herramienta MCP (stdio JSON-RPC)
Server.call_tool → validación de entrada
        ↓ caché TTL (si aplica y no expiró)
Conexión COM (tenacity + circuit breaker)
        ↓ AutoCAD Application → ModelSpace
Operación (AddLine / Delete / etc.) → doc.Regen
        ↓ Respuesta JSON al agente
```

---

## 5. Tareas ordenadas

### Fase A — Stack y calidad
1. Crear `pyproject.toml` con todas las dependencias del stack.
2. Añadir `.gitignore`, `AGENTS.md`, actualizar `README.md`.
3. Configurar `ruff` (lint + formato), `mypy`, `.pre-commit-config.yaml`.
4. Añadir logging estructurado y configuración por variables de entorno.

### Fase B — Arquitectura y reglas de unión
5. Extraer conexión COM a `connection.py` (reconexión, `tenacity`, circuit breaker).
6. Crear `cache.py` con caché TTL para `get_entities` y `get_drawing_info`.
7. Extraer registro de herramientas a `tools.py` (registro centralizado, sin duplicados).
8. Crear `server.py` delgado que orchestre conexión, caché y herramientas.
9. Añadir herramientas de operación: `health_check`, `batch_execute`, `get_metrics`, `clear_cache`, `reload_config`.

### Fase C — Tests y CI
10. Tests unitarios con mocks de COM (sin AutoCAD real).
11. Pipeline CI: `ruff check`, `ruff format --check`, `mypy`, `pytest` en cada push.
12. `docker-compose.yml` para desarrollo y `Dockerfile` multi-stage.

---

## 6. Validación

- `ruff check` y `ruff format --check` limpios.
- `mypy` sin errores nuevos (estricto en módulos nuevos, progresivo en legacy).
- `pytest` pasa con mocks de COM.
- `docker build` exitoso.
- Conexión real a AutoCAD: `get_drawing_info`, `create_line`, `delete_entity_by_handle` funcionan.
- `health_check` devuelve `OK`; `get_metrics` expone contadores.
- Ninguna herramienta MCP existente eliminada ni renombrada.

---

## 7. Riesgos y mitigación

| Riesgo | Mitigación |
|---|---|
| Agente llama COM directamente | Revisión de código en PR; prohibir imports de `pywin32` fuera de `connection.py` |
| Cambio rompiente en esquema de herramienta | JSON Schema estático en tests; CI falla si cambia esquema de herramienta existente |
| COM cuelga y bloquea el servidor | `run_in_executor` + timeouts + `tenacity` backoff |
| Caché devuelve datos obsoletos | TTL corto + herramienta `clear_cache` para forzar refresco |

---

## 8. Fuera de scope

- Soporte multi-plataforma no-Windows (COM es exclusivo de Windows).
- Cambio de transporte distinto a stdio.
- Publicación obligatoria en PyPI (instalación directa desde git por ahora).
- Soporte multi-documento de AutoCAD simultáneo (solo `ActiveDocument`).

---

Artefacto principal: este plan (`1792160211030-stack-agentes-mcp.md`).
