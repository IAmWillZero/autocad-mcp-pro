"""Layouts (espacio papel), viewports y estilo de trazado (.ctb/.stb)."""

from __future__ import annotations

import time
from typing import Any

from autocad_mcp.com import as_dynamic, variant_point
from autocad_mcp.connection import AutoCADConnection, safe_operation
from autocad_mcp.features.base import FeatureBase

# acActiveSpace: 1 = espacio papel.
AC_PAPER_SPACE = 1


class LayoutTools(FeatureBase):
    """Gestiona layouts, viewports y el estilo de trazado del documento activo."""

    def __init__(self, conn: AutoCADConnection, cache: Any | None = None) -> None:
        super().__init__(conn, cache)

    def list_layouts(self) -> dict[str, Any]:
        """Lista los layouts (pestañas) con su estilo de trazado y cuál esta activo."""
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}

        active = self._active_layout_name()
        layouts: list[dict[str, Any]] = []
        try:
            collection = self.conn.doc.Layouts
            for i in range(int(collection.Count)):
                try:
                    layout = collection.Item(i)
                    name = str(layout.Name)
                except Exception:  # noqa: BLE001
                    continue
                entry: dict[str, Any] = {"name": name, "active": name == active}
                try:
                    entry["plot_style_table"] = str(layout.StyleSheet)
                except Exception:  # noqa: BLE001
                    pass
                layouts.append(entry)
        except Exception as exc:  # noqa: BLE001
            return {"error": f"Failed to list layouts: {exc}"}

        return {"success": True, "count": len(layouts), "layouts": layouts}

    def create_layout(
        self,
        name: str,
        media: str | None = None,
        plot_style_table: str | None = None,
    ) -> dict[str, Any]:
        """Crea un layout (pestana de espacio papel) con papel y estilo de trazado."""
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}
        if not name:
            return {"success": False, "error": "name es obligatorio"}

        try:
            layout = self.conn.doc.Layouts.Add(str(name))
        except Exception as exc:  # noqa: BLE001 - suele ser "ya existe"
            return {"success": False, "error": f"No se pudo crear el layout '{name}': {exc}"}

        if media:
            try:
                layout.CanonicalMediaName = str(media)
            except Exception:  # noqa: BLE001
                pass
        if plot_style_table:
            try:
                layout.StyleSheet = str(plot_style_table)
            except Exception:  # noqa: BLE001
                pass

        self._invalidate()
        return {
            "success": True,
            "name": str(layout.Name),
            "media": media,
            "plot_style_table": plot_style_table,
            "message": f"Layout '{name}' creado",
        }

    def set_active_layout(self, name: str) -> dict[str, Any]:
        """Activa un layout (cambia la pestana actual) y pasa a espacio papel."""
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}
        try:
            layout = self.conn.doc.Layouts.Item(str(name))
            self.conn.doc.ActiveLayout = layout
            self.conn.doc.ActiveSpace = AC_PAPER_SPACE
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"No se pudo activar el layout '{name}': {exc}"}

        time.sleep(0.5)  # AutoCAD queda ocupado un instante al cambiar de pestana
        self._invalidate()
        return {"success": True, "active_layout": str(name), "message": f"Layout '{name}' activado"}

    def create_viewport(
        self,
        layout_name: str,
        center: list[float],
        width: float,
        height: float,
        scale: float | None = None,
        view_center: list[float] | None = None,
        locked: bool = True,
    ) -> dict[str, Any]:
        """Crea un viewport en un layout. ``scale`` es 1:50 -> 1/50 = 0.02."""
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}

        try:
            layout = self.conn.doc.Layouts.Item(str(layout_name))
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"Layout '{layout_name}' no existe: {exc}"}

        # El viewport se agrega al espacio papel activo: primero activamos el layout.
        try:
            self.conn.doc.ActiveLayout = layout
            self.conn.doc.ActiveSpace = AC_PAPER_SPACE
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.5)

        def add_operation() -> Any:
            paper = as_dynamic(self.conn.doc.PaperSpace)
            return paper.AddPViewport(
                variant_point(center[0], center[1]), float(width), float(height)
            )

        viewport = safe_operation(add_operation)
        if viewport is None:
            return {"success": False, "error": "No se pudo crear el viewport"}

        if scale:
            try:
                viewport.CustomScale = float(scale)
            except Exception:  # noqa: BLE001
                pass
        if view_center:
            try:
                viewport.Target = variant_point(view_center[0], view_center[1], 0.0)
            except Exception:  # noqa: BLE001
                pass
        if locked:
            try:
                viewport.DisplayLocked = True
            except Exception:  # noqa: BLE001
                pass

        self.conn.regen()
        self._invalidate()
        return {
            "success": True,
            "layout": str(layout_name),
            "handle": self._handle(viewport),
            "center": [float(center[0]), float(center[1])],
            "size": [float(width), float(height)],
            "scale": scale,
            "message": f"Viewport creado en '{layout_name}'"
            + (f" a escala {scale}" if scale else ""),
        }

    def set_plot_style_table(self, layout_name: str, table: str) -> dict[str, Any]:
        """Asigna un estilo de trazado (.ctb/.stb) a un layout.

        El archivo .CTB/.STB es binario y NO se puede crear por COM: se elige de los
        que ya existan en AutoCAD (p. ej. ``acad.ctb``, ``monochrome.ctb``).
        """
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}
        try:
            layout = self.conn.doc.Layouts.Item(str(layout_name))
            layout.StyleSheet = str(table)
        except Exception as exc:  # noqa: BLE001
            return {
                "success": False,
                "error": f"No se pudo asignar '{table}' a '{layout_name}': {exc}",
            }
        return {
            "success": True,
            "layout": str(layout_name),
            "plot_style_table": str(table),
            "message": f"Layout '{layout_name}' usara el estilo de trazado '{table}'",
        }

    def _active_layout_name(self) -> str:
        try:
            return str(self.conn.doc.ActiveLayout.Name)
        except Exception:  # noqa: BLE001
            return ""

    @staticmethod
    def _handle(entity: Any) -> str:
        try:
            return str(entity.Handle)
        except Exception:  # noqa: BLE001
            return ""
