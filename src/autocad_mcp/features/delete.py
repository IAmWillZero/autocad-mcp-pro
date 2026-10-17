"""Herramientas de borrado de entidades."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from autocad_mcp.cache import TTLCache
from autocad_mcp.colors import color_index
from autocad_mcp.connection import AutoCADConnection
from autocad_mcp.features.base import FeatureBase


class DeleteTools(FeatureBase):
    """Elimina entidades por handle, tipo, capa o color."""

    def __init__(self, conn: AutoCADConnection, cache: TTLCache) -> None:
        super().__init__(conn, cache)

    def _iter_modelspace(self) -> Any:
        model_space = self.conn.model_space()
        for i in range(model_space.Count):
            try:
                yield model_space.Item(i)
            except Exception:  # noqa: BLE001
                continue

    def _delete_with_filter(self, predicate: Callable[[Any], bool]) -> dict[str, Any]:
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}

        deleted: list[str] = []
        for entity in list(self._iter_modelspace()):
            try:
                if predicate(entity):
                    handle = str(entity.Handle)
                    entity.Delete()
                    deleted.append(handle)
            except Exception:  # noqa: BLE001
                continue

        if deleted:
            self.conn.regen()
            self._invalidate()

        return {
            "success": True,
            "deleted_count": len(deleted),
            "handles": deleted,
        }

    def delete_entity_by_handle(self, handle: str) -> dict[str, Any]:
        """Elimina una entidad por su handle."""
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}

        for entity in list(self._iter_modelspace()):
            try:
                if str(entity.Handle) == str(handle):
                    entity.Delete()
                    self.conn.regen()
                    self._invalidate()
                    return {
                        "success": True,
                        "handle": str(handle),
                        "message": f"Entity with handle {handle} deleted successfully",
                    }
            except Exception:  # noqa: BLE001
                continue
        return {"error": f"Entity with handle {handle} not found"}

    def delete_entities_by_handles(self, handles: list[str]) -> dict[str, Any]:
        wanted = {str(h) for h in handles}
        result = self._delete_with_filter(lambda e: str(e.Handle) in wanted)
        result["requested_count"] = len(wanted)
        return result

    def delete_entities_by_type(self, entity_type: str) -> dict[str, Any]:
        return self._delete_with_filter(lambda e: str(e.ObjectName) == entity_type)

    def delete_entities_by_layer(self, layer_name: str) -> dict[str, Any]:
        return self._delete_with_filter(lambda e: str(e.Layer) == layer_name)

    def delete_entities_by_color(self, color: str | int) -> dict[str, Any]:
        idx = color_index(color)
        return self._delete_with_filter(lambda e: int(e.color) == idx)

    def delete_entities_by_type_and_color(
        self, entity_type: str, color: str | int
    ) -> dict[str, Any]:
        idx = color_index(color)
        return self._delete_with_filter(
            lambda e: str(e.ObjectName) == entity_type and int(e.color) == idx
        )

    def delete_last_entities(self, count: int = 1) -> dict[str, Any]:
        """Elimina las ultimas ``count`` entidades creadas."""
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}

        try:
            model_space = self.conn.model_space()
            total = int(model_space.Count)
            to_delete = max(0, min(int(count), total))
            deleted: list[str] = []

            for i in range(total - 1, total - to_delete - 1, -1):
                try:
                    entity = model_space.Item(i)
                    deleted.append(str(entity.Handle))
                    entity.Delete()
                except Exception:  # noqa: BLE001
                    continue

            if deleted:
                self.conn.regen()
                self._invalidate()

            return {
                "success": True,
                "requested_count": int(count),
                "deleted_count": len(deleted),
                "handles": deleted,
            }
        except Exception as exc:  # noqa: BLE001
            return {"error": f"Failed to delete last entities: {exc}"}

    def delete_all_entities(self, confirm: bool = False) -> dict[str, Any]:
        """Elimina todas las entidades (requiere confirm=True) y purga lo huerfano."""
        if not confirm:
            return {"error": "Deletion not confirmed. Set confirm=true."}
        result = self._delete_with_filter(lambda _: True)
        purged = self._purge()
        result["purged"] = purged
        result["message"] = f"Se eliminaron {result.get('deleted_count', 0)} entidades" + (
            " y se purgo el dibujo" if purged else ""
        )
        return result

    def _purge(self) -> bool:
        """Purga bloques/capas/estilos sin uso (best-effort)."""
        try:
            for _ in range(3):
                self.conn.doc.PurgeAll()
            return True
        except Exception:  # noqa: BLE001
            return False
