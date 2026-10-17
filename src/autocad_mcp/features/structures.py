"""Herramientas de estructuras: muros, puertas, ventanas, habitaciones y etiquetas."""

from __future__ import annotations

import math
from typing import Any

from autocad_mcp.cache import TTLCache
from autocad_mcp.connection import AutoCADConnection
from autocad_mcp.features.base import FeatureBase
from autocad_mcp.features.geometry import GeometryTools
from autocad_mcp.layers import (
    STRUCTURE_LAYERS,
    LayerTools,
    layer_for_structure_type,
)


class StructureTools(FeatureBase):
    """Crea elementos estructurales con asignacion automatica de capa."""

    def __init__(
        self,
        conn: AutoCADConnection,
        cache: TTLCache,
        geometry: GeometryTools,
        layer_tools: LayerTools,
    ) -> None:
        super().__init__(conn, cache)
        self.geometry = geometry
        self.layer_tools = layer_tools

    def create_structure(
        self,
        structure_type: str,
        geometry_data: dict[str, Any],
        color: str | int | None = None,
        thickness: float = 0.0,
        custom_layer: str | None = None,
        label: str | None = None,
    ) -> dict[str, Any]:
        """Crea una estructura con capa automatica y etiqueta opcional."""
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}

        if custom_layer:
            layer_name = custom_layer
            self.layer_tools.create_or_get_layer(
                layer_name, color or "white", f"Custom layer for {structure_type}"
            )
        else:
            layer_name = layer_for_structure_type(structure_type)

        original_layer = self.layer_tools.current_layer_name()
        self.layer_tools.set_current_layer(layer_name)

        if color is None:
            color = self.layer_tools.layer_color(layer_name) or "bylayer"

        lowered = structure_type.lower()
        if lowered in ("wall", "partition"):
            result = self.create_wall(geometry_data, color, thickness)
        elif lowered in ("door", "opening"):
            result = self.create_door(geometry_data, color, thickness)
        elif lowered == "window":
            result = self.create_window(geometry_data, color, thickness)
        elif lowered == "room":
            result = self.create_room(geometry_data, color, thickness)
        else:
            result = self._create_generic(geometry_data, color, thickness)

        if "error" in result and not result.get("success"):
            if original_layer:
                self.layer_tools.set_current_layer(original_layer)
            return result

        created: list[str] = list(result.get("handles", []))

        if label:
            label_result = self.add_structure_label(geometry_data, label)
            created.extend(label_result.get("handles", []))

        if original_layer:
            self.layer_tools.set_current_layer(original_layer)

        return {
            "success": True,
            "structure_type": structure_type,
            "layer": layer_name,
            "handles": created,
            "color": color,
            "thickness": thickness,
            "label": label,
            "message": f"{structure_type} created on layer {layer_name}"
            + (f" with label '{label}'" if label else ""),
        }

    def _create_generic(
        self, geometry_data: dict[str, Any], color: str | int, thickness: float
    ) -> dict[str, Any]:
        if "start" in geometry_data and "end" in geometry_data:
            return self.geometry.create_line(
                geometry_data["start"], geometry_data["end"], color, thickness
            )
        if "center" in geometry_data and "radius" in geometry_data:
            return self.geometry.create_circle(
                geometry_data["center"], geometry_data["radius"], color, thickness
            )
        if "corner1" in geometry_data and "corner2" in geometry_data:
            return self.geometry.create_rectangle(
                geometry_data["corner1"], geometry_data["corner2"], color, thickness
            )
        return {"success": False, "error": "Unsupported geometry data"}

    def create_wall(
        self, geometry_data: dict[str, Any], color: str | int = "white", thickness: float = 0.1
    ) -> dict[str, Any]:
        """Crea un muro (linea con grosor)."""
        if "start" not in geometry_data or "end" not in geometry_data:
            return {"error": "Wall requires start and end points"}
        wall_thickness = thickness if thickness > 0 else 0.1
        return self.geometry.create_line(
            geometry_data["start"], geometry_data["end"], color, wall_thickness
        )

    def create_door(
        self, geometry_data: dict[str, Any], color: str | int = "green", thickness: float = 0.0
    ) -> dict[str, Any]:
        """Crea una puerta (hueco + arco de apertura)."""
        if "start" not in geometry_data or "end" not in geometry_data:
            return {"error": "Door requires start and end points"}

        handles: list[str] = []
        result = self.geometry.create_line(
            geometry_data["start"], geometry_data["end"], color, thickness
        )
        if result.get("success"):
            handles.extend(result.get("handles", []))

        if "width" in geometry_data:
            arc_result = self.geometry.create_arc(
                geometry_data["start"], geometry_data["width"], 0, 90, color, 0
            )
            if arc_result.get("success"):
                handles.extend(arc_result.get("handles", []))

        return {
            "success": True,
            "handles": handles,
            "type": "Door",
            "color": color,
            "message": f"Door created from {geometry_data['start']} to {geometry_data['end']}",
        }

    def create_window(
        self, geometry_data: dict[str, Any], color: str | int = "cyan", thickness: float = 0.0
    ) -> dict[str, Any]:
        """Crea una ventana (hueco + linea interior)."""
        if "start" not in geometry_data or "end" not in geometry_data:
            return {"error": "Window requires start and end points"}

        handles: list[str] = []
        result = self.geometry.create_line(
            geometry_data["start"], geometry_data["end"], color, thickness
        )
        if result.get("success"):
            handles.extend(result.get("handles", []))

        start = geometry_data["start"]
        end = geometry_data["end"]
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = math.sqrt(dx**2 + dy**2)
        if length > 0:
            offset = 0.05
            perp_x = -dy / length * offset
            perp_y = dx / length * offset
            inner = self.geometry.create_line(
                [start[0] + perp_x, start[1] + perp_y],
                [end[0] + perp_x, end[1] + perp_y],
                color,
                0,
            )
            if inner.get("success"):
                handles.extend(inner.get("handles", []))

        return {
            "success": True,
            "handles": handles,
            "type": "Window",
            "color": color,
            "message": f"Window created from {geometry_data['start']} to {geometry_data['end']}",
        }

    def create_room(
        self, geometry_data: dict[str, Any], color: str | int = "white", thickness: float = 0.1
    ) -> dict[str, Any]:
        """Crea una habitacion (rectangulo)."""
        if "corner1" not in geometry_data or "corner2" not in geometry_data:
            return {"error": "Room requires corner1 and corner2 points"}
        return self.geometry.create_rectangle(
            geometry_data["corner1"], geometry_data["corner2"], color, thickness
        )

    def add_structure_label(self, geometry_data: dict[str, Any], label: str) -> dict[str, Any]:
        """Anade una etiqueta de texto en la capa ANNOTATION."""
        position = self._label_position(geometry_data)
        original_layer = self.layer_tools.current_layer_name()
        self.layer_tools.set_current_layer(STRUCTURE_LAYERS["annotation"]["name"])
        result = self.geometry.create_text(position, label, 0.2, "white")
        if original_layer:
            self.layer_tools.set_current_layer(original_layer)
        return result

    @staticmethod
    def _label_position(geometry_data: dict[str, Any]) -> list[float]:
        if "center" in geometry_data:
            return list(geometry_data["center"])
        if "start" in geometry_data and "end" in geometry_data:
            start, end = geometry_data["start"], geometry_data["end"]
            return [(start[0] + end[0]) / 2, (start[1] + end[1]) / 2]
        if "corner1" in geometry_data and "corner2" in geometry_data:
            c1, c2 = geometry_data["corner1"], geometry_data["corner2"]
            return [(c1[0] + c2[0]) / 2, (c1[1] + c2[1]) / 2]
        return [0.0, 0.0]
