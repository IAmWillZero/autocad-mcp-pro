"""Base compartida por los modulos de features."""

from __future__ import annotations

from typing import Any

from autocad_mcp.cache import TTLCache
from autocad_mcp.colors import color_index
from autocad_mcp.connection import AutoCADConnection


class FeatureBase:
    """Utilidades comunes: acceso a conexion, cache e invalidacion."""

    def __init__(self, conn: AutoCADConnection, cache: TTLCache | None = None) -> None:
        self.conn = conn
        self.cache = cache

    def _invalidate(self) -> None:
        """Invalida los datos derivados del dibujo tras una mutacion."""
        if self.cache is None:
            return
        self.cache.invalidate_prefix("entities")
        self.cache.invalidate("drawing_info")

    @staticmethod
    def set_entity_color(entity: Any, color: str | int) -> None:
        """Aplica color a una entidad, ignorando errores de version.

        Se usa ``color`` en minuscula porque el typelib de AutoCAD 2025 expone
        la propiedad asi (DISPID 1280); el *late binding* es case-insensitive.
        """
        try:
            entity.color = color_index(color)
        except Exception:  # noqa: BLE001
            pass
