"""Cotas: creacion de dimensiones con estilo a escala."""

from __future__ import annotations

import math
from typing import Any

from autocad_mcp.com import variant_point
from autocad_mcp.connection import AutoCADConnection
from autocad_mcp.features.base import FeatureBase

_LINEAR_TYPES = ("rotated", "linear")
_SUPPORTED = ("rotated", "linear", "aligned", "radial", "diametric")


def dimoverride_command(decimals: int, suppress_trailing_zeros: bool = True) -> str:
    """Secuencia de ``DIMOVERRIDE`` que fija DIMDEC/DIMZIN en todas las cotas.

    ``SetVariable("DIMDEC", ...)`` no siempre se adhiere al estilo de cotas de
    AutoCAD; ``DIMOVERRIDE`` aplica el formato a las cotas existentes de forma
    fiable y mantiene la cota asociativa (solo cambia el formato del texto).
    """
    dimzin = 8 if suppress_trailing_zeros else 0
    return f"_.DIMOVERRIDE\nDIMDEC\n{int(decimals)}\nDIMZIN\n{dimzin}\n\nALL\n\n"


class DimensionTools(FeatureBase):
    """Crea cotas alineadas, rotadas, radiales y diametrales."""

    def __init__(self, conn: AutoCADConnection, cache: Any | None = None) -> None:
        super().__init__(conn, cache)

    def create_dimension(
        self,
        dim_type: str,
        points: list[list[float]],
        dim_line_point: list[float] | None = None,
        rotation: float = 0.0,
        leader_length: float = 1.0,
        layer: str = "A-COTAS",
        style: str | None = None,
    ) -> dict[str, Any]:
        """Crea una cota.

        - ``rotated``/``linear``: points=[start, end], ``dim_line_point``, ``rotation`` (grados)
        - ``aligned``: points=[start, end], ``dim_line_point``
        - ``radial``/``diametric``: points=[center, chord], ``leader_length``
        """
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}

        dt = str(dim_type).lower()
        if dt not in _SUPPORTED:
            return {"success": False, "error": f"dim_type invalido: {dim_type}. Use {_SUPPORTED}"}
        if len(points) < 2:
            return {"success": False, "error": "Se requieren al menos 2 puntos"}

        model_space = self.conn.model_space()
        p0 = variant_point(*points[0])
        p1 = variant_point(*points[1])

        try:
            if dt in _LINEAR_TYPES:
                if dim_line_point is None:
                    return {"success": False, "error": "rotated/linear requiere dim_line_point"}
                dim = model_space.AddDimRotated(
                    p0, p1, variant_point(*dim_line_point), math.radians(float(rotation))
                )
            elif dt == "aligned":
                if dim_line_point is None:
                    return {"success": False, "error": "aligned requiere dim_line_point"}
                dim = model_space.AddDimAligned(p0, p1, variant_point(*dim_line_point))
            elif dt == "radial":
                dim = model_space.AddDimRadial(p0, p1, float(leader_length))
            else:  # diametric
                dim = model_space.AddDimDiametric(p0, p1, float(leader_length))
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"Failed to create dimension: {exc}"}

        try:
            dim.Layer = layer
        except Exception:  # noqa: BLE001
            pass
        if style:
            try:
                dim.StyleName = str(style)
            except Exception:  # noqa: BLE001
                pass
        try:
            dim.Update()
        except Exception:  # noqa: BLE001
            pass

        self.conn.regen()
        self._invalidate()
        return {
            "success": True,
            "dim_type": dt,
            "handle": self._handle(dim),
            "layer": layer,
            "measurement": self._measurement(dim),
            "message": f"Cota {dt} creada en capa {layer}",
        }

    def set_dimension_precision(
        self,
        decimals: int = 3,
        suppress_trailing_zeros: bool = True,
    ) -> dict[str, Any]:
        """Ajusta la precision del texto de todas las cotas del espacio modelo.

        Aplica ``DIMOVERRIDE`` (DIMDEC/DIMZIN) porque ``SetVariable`` no siempre
        se adhiere al estilo de cotas. Las cotas siguen siendo asociativas: solo
        cambia el formato del texto.
        """
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}

        dec = max(0, min(8, int(decimals)))
        try:
            self.conn.doc.SendCommand(dimoverride_command(dec, suppress_trailing_zeros))
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"Failed to override dimensions: {exc}"}

        self.conn.regen()
        self._invalidate()
        return {
            "success": True,
            "decimals": dec,
            "suppress_trailing_zeros": bool(suppress_trailing_zeros),
            "message": f"Precision de cotas aplicada: {dec} decimales",
        }

    @staticmethod
    def _handle(entity: Any) -> str:
        try:
            return str(entity.Handle)
        except Exception:  # noqa: BLE001
            return ""

    @staticmethod
    def _measurement(entity: Any) -> float | None:
        try:
            return round(float(entity.Measurement), 4)
        except Exception:  # noqa: BLE001
            return None
