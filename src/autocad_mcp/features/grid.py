"""Ejes de construccion (grilla arquitectonica) con burbujas y rotulos."""

from __future__ import annotations

from typing import Any

from autocad_mcp.com import variant_point
from autocad_mcp.connection import AutoCADConnection, safe_operation
from autocad_mcp.features.base import FeatureBase
from autocad_mcp.standards import axis_letter_label, axis_number_label


class GridTools(FeatureBase):
    """Dibuja ejes de construccion (numeros verticales, letras horizontales)."""

    def __init__(self, conn: AutoCADConnection, cache: Any | None = None) -> None:
        super().__init__(conn, cache)

    def create_construction_grid(
        self,
        vertical_positions: list[float] | None = None,
        horizontal_positions: list[float] | None = None,
        bubble_radius: float = 0.45,
        overshoot: float = 1.0,
        text_height: float = 0.3,
        layer: str = "A-EJES",
    ) -> dict[str, Any]:
        """Crea los ejes: lineas con burbujas y rotulo en ambos extremos."""
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}

        vertical = [float(v) for v in (vertical_positions or [])]
        horizontal = [float(v) for v in (horizontal_positions or [])]
        if not vertical and not horizontal:
            return {
                "success": False,
                "error": "Se requiere al menos vertical_positions u horizontal_positions",
            }

        model_space = self.conn.model_space()
        handles: list[str] = []
        radius = float(bubble_radius)

        y_lo = (min(horizontal) if horizontal else 0.0) - float(overshoot)
        y_hi = (max(horizontal) if horizontal else 0.0) + float(overshoot)
        x_lo = (min(vertical) if vertical else 0.0) - float(overshoot)
        x_hi = (max(vertical) if vertical else 0.0) + float(overshoot)

        def add_axis(
            line_start: list[float],
            line_end: list[float],
            ends: list[list[float]],
            label: str,
        ) -> None:
            def make_line() -> Any:
                return self._new_line(model_space, line_start, line_end, layer)

            line = safe_operation(make_line)
            if line is not None:
                handles.append(self._handle(line))
            for end in ends:

                def make_circle(center: list[float] = end) -> Any:
                    return self._new_circle(model_space, center, radius, layer)

                bubble = safe_operation(make_circle)
                if bubble is not None:
                    handles.append(self._handle(bubble))
                text_pos = [end[0] - text_height / 3.0, end[1] - text_height / 2.0]

                def make_text(pos: list[float] = text_pos, txt: str = label) -> Any:
                    return self._new_text(model_space, pos, txt, text_height, layer)

                text = safe_operation(make_text)
                if text is not None:
                    handles.append(self._handle(text))

        # ejes verticales -> numeros 1..n
        for index, x in enumerate(vertical, start=1):
            add_axis(
                [x, y_lo],
                [x, y_hi],
                [[x, y_lo], [x, y_hi]],
                axis_number_label(index),
            )

        # ejes horizontales -> letras A..n
        for index, y in enumerate(horizontal, start=1):
            add_axis(
                [x_lo, y],
                [x_hi, y],
                [[x_lo, y], [x_hi, y]],
                axis_letter_label(index),
            )

        self.conn.regen()
        self._invalidate()
        return {
            "success": True,
            "layer": layer,
            "vertical_axes": len(vertical),
            "horizontal_axes": len(horizontal),
            "entities_created": len(handles),
            "handles": handles,
            "message": (
                f"Grilla creada: {len(vertical)} ejes verticales y "
                f"{len(horizontal)} horizontales ({len(handles)} entidades)"
            ),
        }

    # --- helpers ---------------------------------------------------------
    @staticmethod
    def _new_line(model_space: Any, start: list[float], end: list[float], layer: str) -> Any:
        line = model_space.AddLine(variant_point(*start), variant_point(*end))
        line.Layer = layer
        return line

    @staticmethod
    def _new_circle(model_space: Any, center: list[float], radius: float, layer: str) -> Any:
        circle = model_space.AddCircle(variant_point(*center), radius)
        circle.Layer = layer
        return circle

    @staticmethod
    def _new_text(
        model_space: Any, position: list[float], text: str, height: float, layer: str
    ) -> Any:
        obj = model_space.AddText(text, variant_point(*position), height)
        obj.Layer = layer
        return obj

    @staticmethod
    def _handle(entity: Any) -> str:
        try:
            return str(entity.Handle)
        except Exception:  # noqa: BLE001
            return ""
