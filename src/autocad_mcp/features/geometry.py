"""Herramientas de geometria basica: linea, circulo, rectangulo, texto, arco."""

from __future__ import annotations

import math
from typing import Any

from autocad_mcp.com import variant_point
from autocad_mcp.connection import AutoCADConnection, safe_operation
from autocad_mcp.features.base import FeatureBase


class GeometryTools(FeatureBase):
    """Creacion de entidades geometricas simples en el ModelSpace."""

    def __init__(self, conn: AutoCADConnection, cache: Any | None = None) -> None:
        super().__init__(conn, cache)

    def create_line(
        self,
        start: list[float],
        end: list[float],
        color: str | int = "white",
        thickness: float = 0.0,
    ) -> dict[str, Any]:
        """Crea una linea (con grosor opcional simulando lineas paralelas)."""
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}

        handles: list[str] = []

        def line_operation() -> Any:
            start_point = variant_point(start[0], start[1], start[2] if len(start) > 2 else 0.0)
            end_point = variant_point(end[0], end[1], end[2] if len(end) > 2 else 0.0)
            line = self.conn.model_space().AddLine(start_point, end_point)
            self.set_entity_color(line, color)
            self.conn.regen()
            return line

        main_line = safe_operation(line_operation)
        if main_line is None:
            return {
                "success": False,
                "error": "Failed to create line",
                "type": "AcDbLine",
                "color": color,
            }

        handles.append(self._handle(main_line, "line_main"))

        if thickness > 0:
            start_parallel, end_parallel = self.calculate_parallel_points(start, end, thickness)

            def parallel_line_operation() -> Any:
                p1 = variant_point(start_parallel[0], start_parallel[1], 0.0)
                p2 = variant_point(end_parallel[0], end_parallel[1], 0.0)
                line = self.conn.model_space().AddLine(p1, p2)
                self.set_entity_color(line, color)
                self.conn.regen()
                return line

            def cap1_operation() -> Any:
                p1 = variant_point(start[0], start[1], 0.0)
                p2 = variant_point(start_parallel[0], start_parallel[1], 0.0)
                return self._make_line(p1, p2, color)

            def cap2_operation() -> Any:
                p1 = variant_point(end[0], end[1], 0.0)
                p2 = variant_point(end_parallel[0], end_parallel[1], 0.0)
                return self._make_line(p1, p2, color)

            parallel_line = safe_operation(parallel_line_operation)
            if parallel_line is not None:
                handles.append(self._handle(parallel_line, "line_parallel"))
            cap1 = safe_operation(cap1_operation)
            if cap1 is not None:
                handles.append(self._handle(cap1, "line_cap1"))
            cap2 = safe_operation(cap2_operation)
            if cap2 is not None:
                handles.append(self._handle(cap2, "line_cap2"))

        self._invalidate()
        return {
            "success": True,
            "handles": handles,
            "type": "AcDbLine" + (" with thickness" if thickness > 0 else ""),
            "color": color,
            "thickness": thickness,
            "message": f"Line created from {start} to {end} with color {color}"
            + (f" and thickness {thickness}" if thickness > 0 else ""),
        }

    def create_circle(
        self,
        center: list[float],
        radius: float,
        color: str | int = "white",
        thickness: float = 0.0,
    ) -> dict[str, Any]:
        """Crea un circulo (con grosor opcional como circulos concentricos)."""
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}

        def circle_operation() -> Any:
            center_point = variant_point(
                center[0], center[1], center[2] if len(center) > 2 else 0.0
            )
            circle = self.conn.model_space().AddCircle(center_point, float(radius))
            self.set_entity_color(circle, color)
            self.conn.regen()
            return circle

        main_circle = safe_operation(circle_operation)
        if main_circle is None:
            return {
                "success": False,
                "error": "Failed to create circle",
                "type": "AcDbCircle",
                "color": color,
            }

        handles = [self._handle(main_circle, "circle_main")]

        if thickness > 0:

            def outer_operation() -> Any:
                center_point = variant_point(
                    center[0], center[1], center[2] if len(center) > 2 else 0.0
                )
                circle = self.conn.model_space().AddCircle(
                    center_point, float(radius + thickness / 2)
                )
                self.set_entity_color(circle, color)
                self.conn.regen()
                return circle

            def inner_operation() -> Any:
                center_point = variant_point(
                    center[0], center[1], center[2] if len(center) > 2 else 0.0
                )
                inner_radius = max(0.1, radius - thickness / 2)
                circle = self.conn.model_space().AddCircle(center_point, float(inner_radius))
                self.set_entity_color(circle, color)
                self.conn.regen()
                return circle

            outer = safe_operation(outer_operation)
            if outer is not None:
                handles.append(self._handle(outer, "circle_outer"))
            inner = safe_operation(inner_operation)
            if inner is not None:
                handles.append(self._handle(inner, "circle_inner"))

        self._invalidate()
        return {
            "success": True,
            "handles": handles,
            "type": "AcDbCircle" + (" with thickness" if thickness > 0 else ""),
            "color": color,
            "thickness": thickness,
            "message": f"Circle created at {center} with radius {radius}, color {color}"
            + (f" and thickness {thickness}" if thickness > 0 else ""),
        }

    def create_rectangle(
        self,
        corner1: list[float],
        corner2: list[float],
        color: str | int = "white",
        thickness: float = 0.0,
    ) -> dict[str, Any]:
        """Crea un rectangulo como 4 lineas."""
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}

        try:
            x1, y1 = float(corner1[0]), float(corner1[1])
            x2, y2 = float(corner2[0]), float(corner2[1])
        except (IndexError, TypeError, ValueError) as exc:
            return {"success": False, "error": f"Invalid corners: {exc}"}

        handles: list[str] = []
        edges = [
            ([x1, y1], [x2, y1]),
            ([x2, y1], [x2, y2]),
            ([x2, y2], [x1, y2]),
            ([x1, y2], [x1, y1]),
        ]
        for start, end in edges:
            result = self.create_line(start, end, color, thickness)
            if not result.get("success"):
                return {
                    "success": False,
                    "error": "Failed while creating rectangle edges",
                    "handles": handles,
                }
            handles.extend(result.get("handles", []))

        return {
            "success": True,
            "handles": handles,
            "type": "Rectangle" + (" with thickness" if thickness > 0 else ""),
            "color": color,
            "thickness": thickness,
            "message": f"Rectangle created from ({x1},{y1}) to ({x2},{y2}) with color {color}"
            + (f" and thickness {thickness}" if thickness > 0 else ""),
        }

    def create_text(
        self,
        position: list[float],
        text: str,
        height: float = 1.0,
        color: str | int = "white",
    ) -> dict[str, Any]:
        """Crea una entidad de texto."""
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}

        def text_operation() -> Any:
            text_point = variant_point(
                position[0], position[1], position[2] if len(position) > 2 else 0.0
            )
            obj = self.conn.model_space().AddText(str(text), text_point, float(height))
            self.set_entity_color(obj, color)
            self.conn.regen()
            return obj

        text_obj = safe_operation(text_operation)
        if text_obj is None:
            return {
                "success": False,
                "error": "Failed to create text",
                "type": "AcDbText",
                "color": color,
            }

        self._invalidate()
        return {
            "success": True,
            "handle": self._handle(text_obj, "text_created"),
            "type": "AcDbText",
            "color": color,
            "message": f"Text '{text}' created at {position} with height {height} and color {color}",
        }

    def create_arc(
        self,
        center: list[float],
        radius: float,
        start_angle: float,
        end_angle: float,
        color: str | int = "white",
        thickness: float = 0.0,
    ) -> dict[str, Any]:
        """Crea un arco (con grosor opcional como arcos paralelos)."""
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}

        start_rad = math.radians(start_angle)
        end_rad = math.radians(end_angle)

        def arc_operation() -> Any:
            center_point = variant_point(
                center[0], center[1], center[2] if len(center) > 2 else 0.0
            )
            arc = self.conn.model_space().AddArc(center_point, float(radius), start_rad, end_rad)
            self.set_entity_color(arc, color)
            self.conn.regen()
            return arc

        main_arc = safe_operation(arc_operation)
        if main_arc is None:
            return {
                "success": False,
                "error": "Failed to create arc",
                "type": "AcDbArc",
                "color": color,
            }

        handles = [self._handle(main_arc, "arc_main")]

        if thickness > 0:
            inner_radius = max(0.1, radius - thickness / 2)
            outer_radius = radius + thickness / 2

            def arc_at(r: float) -> Any:
                center_point = variant_point(
                    center[0], center[1], center[2] if len(center) > 2 else 0.0
                )
                arc = self.conn.model_space().AddArc(center_point, r, start_rad, end_rad)
                self.set_entity_color(arc, color)
                self.conn.regen()
                return arc

            inner = safe_operation(lambda: arc_at(inner_radius))
            if inner is not None:
                handles.append(self._handle(inner, "arc_inner"))
            outer = safe_operation(lambda: arc_at(outer_radius))
            if outer is not None:
                handles.append(self._handle(outer, "arc_outer"))

        self._invalidate()
        return {
            "success": True,
            "handles": handles,
            "type": "AcDbArc" + (" with thickness" if thickness > 0 else ""),
            "color": color,
            "thickness": thickness,
            "start_angle": start_angle,
            "end_angle": end_angle,
            "message": f"Arc created at {center} with radius {radius}, "
            f"from {start_angle}° to {end_angle}°, color {color}"
            + (f" and thickness {thickness}" if thickness > 0 else ""),
        }

    def calculate_parallel_points(
        self, start: list[float], end: list[float], thickness: float
    ) -> tuple[list[float], list[float]]:
        """Calcula los puntos de una linea paralela desplazada ``thickness/2``."""
        x1, y1 = start[0], start[1]
        x2, y2 = end[0], end[1]
        dx, dy = x2 - x1, y2 - y1
        length = math.sqrt(dx**2 + dy**2)
        if length == 0:
            return start, end

        offset = thickness / 2.0
        perp_x = -dy / length * offset
        perp_y = dx / length * offset
        return (
            [x1 + perp_x, y1 + perp_y],
            [x2 + perp_x, y2 + perp_y],
        )

    # --- helpers ---------------------------------------------------------
    def _make_line(self, p1: Any, p2: Any, color: str | int) -> Any:
        line = self.conn.model_space().AddLine(p1, p2)
        self.set_entity_color(line, color)
        self.conn.regen()
        return line

    @staticmethod
    def _handle(entity: Any, fallback: str) -> str:
        try:
            return str(entity.Handle)
        except Exception:  # noqa: BLE001
            return fallback
