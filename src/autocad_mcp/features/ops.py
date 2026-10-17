"""Operaciones de servidor: undo, recolor, zoom, salud, metricas y batch."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from autocad_mcp.cache import TTLCache
from autocad_mcp.colors import color_index
from autocad_mcp.config import AutoCADMCPConfig
from autocad_mcp.connection import AutoCADConnection
from autocad_mcp.features.base import FeatureBase
from autocad_mcp.obs import Metrics

BatchTool = Callable[..., dict[str, Any]]


class OpsTools(FeatureBase):
    """Operaciones transversales del servidor."""

    def __init__(
        self,
        conn: AutoCADConnection,
        cache: TTLCache,
        config: AutoCADMCPConfig,
        metrics: Metrics,
        batch_tools: dict[str, BatchTool],
        reload_cb: Callable[[], dict[str, Any]],
    ) -> None:
        super().__init__(conn, cache)
        self.config = config
        self.metrics = metrics
        self.batch_tools = batch_tools
        self._reload_cb = reload_cb

    def undo_last_operation(self) -> dict[str, Any]:
        """Deshace la ultima operacion (equivale a Ctrl+Z)."""
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}
        try:
            self.conn.doc.SendCommand("._UNDO 1 ")
            self._invalidate()
            return {"success": True, "message": "Undo command sent"}
        except Exception as exc:  # noqa: BLE001
            return {"error": f"Failed to undo: {exc}"}

    def change_entity_color(self, handle: str, color: str | int) -> dict[str, Any]:
        """Cambia el color de una entidad por su handle."""
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}

        idx = color_index(color)
        for entity in self._iter_entities():
            try:
                if str(entity.Handle) == str(handle):
                    entity.color = idx
                    self.conn.regen()
                    self._invalidate()
                    return {"success": True, "handle": str(handle), "color": idx}
            except Exception:  # noqa: BLE001
                continue
        return {"error": f"Entity with handle {handle} not found"}

    def zoom_extents(self) -> dict[str, Any]:
        """Ajusta el zoom para mostrar todos los objetos."""
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}
        try:
            self.conn.app.ZoomExtents()
            return {"success": True, "message": "Zoom extents executed"}
        except Exception as exc:  # noqa: BLE001
            return {"error": f"Failed to zoom extents: {exc}"}

    def health_check(self) -> dict[str, Any]:
        """Estado OK/ERROR de la conexion con AutoCAD."""
        try:
            if not self.conn.ensure():
                return {"status": "ERROR", "error": "Not connected to AutoCAD"}
            name = self.conn.document_name()
            return {"status": "OK", "connected": True, "document": name}
        except Exception as exc:  # noqa: BLE001
            return {"status": "ERROR", "error": str(exc)}

    def get_metrics(self) -> dict[str, Any]:
        """Contadores de llamadas, errores y latencia media."""
        return self.metrics.snapshot()

    def clear_cache(self) -> dict[str, Any]:
        """Vacia la cache TTL de entidades e info del dibujo."""
        if self.cache is not None:
            self.cache.clear()
        return {"success": True, "message": "Cache cleared"}

    def reload_config(self) -> dict[str, Any]:
        """Recarga la configuracion desde el entorno / .env."""
        return self._reload_cb()

    def batch_execute(self, operations: list[dict[str, Any]]) -> dict[str, Any]:
        """Ejecuta varias operaciones de geometria en una sola pasada."""
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}

        results: list[dict[str, Any]] = []
        for idx, op in enumerate(operations):
            tool_name: str = op.get("tool") or ""
            args = op.get("arguments", {}) or {}
            fn = self.batch_tools.get(tool_name)
            if fn is None:
                results.append(
                    {
                        "index": idx,
                        "tool": tool_name,
                        "error": f"Unknown or unsupported tool: {tool_name}",
                    }
                )
                continue
            try:
                results.append({"index": idx, "tool": tool_name, "result": fn(**args)})
            except Exception as exc:  # noqa: BLE001
                results.append({"index": idx, "tool": tool_name, "error": str(exc)})

        return {"success": True, "executed": len(results), "results": results}

    def _iter_entities(self) -> Any:
        model_space = self.conn.model_space()
        for i in range(model_space.Count):
            try:
                yield model_space.Item(i)
            except Exception:  # noqa: BLE001
                continue
