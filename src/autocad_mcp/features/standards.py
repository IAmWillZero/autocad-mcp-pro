"""Aplicacion del estandar de dibujo (capas A-, unidades y estilo de cotas)."""

from __future__ import annotations

from typing import Any

from autocad_mcp.connection import AutoCADConnection
from autocad_mcp.features.base import FeatureBase
from autocad_mcp.standards import (
    DIM_STYLE_NAME,
    DIM_VARIABLES,
    STANDARD_LAYERS,
    UNITS_VARIABLES,
)


class StandardsTools(FeatureBase):
    """Prepara el documento con el estandar arquitectonico del estudio."""

    def __init__(self, conn: AutoCADConnection, cache: Any | None = None) -> None:
        super().__init__(conn, cache)

    def apply_standard(
        self,
        dim_text_height: float = 0.2,
        dim_arrow_size: float = 0.12,
    ) -> dict[str, Any]:
        """Crea las capas estandar, fija unidades metricas y el estilo de cotas."""
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}

        doc = self.conn.doc
        created_layers: list[str] = []
        existing_layers: list[str] = []

        # --- unidades (metros, metrico, 1:1) ---
        for u_name, u_value in UNITS_VARIABLES.items():
            try:
                doc.SetVariable(u_name, u_value)
            except Exception:  # noqa: BLE001
                pass

        # --- capas A- con color, espesor y tipo de linea ---
        for name, spec in STANDARD_LAYERS.items():
            try:
                doc.Layers.Item(name)
                existing_layers.append(name)
            except Exception:  # noqa: BLE001 - no existe: se crea
                try:
                    doc.Layers.Add(name)
                    created_layers.append(name)
                except Exception:  # noqa: BLE001
                    continue
            self._configure_layer(
                doc, name, spec.color, spec.lineweight, spec.linetype, spec.description
            )

        # crear/actualizar el estilo de cotas
        try:
            doc.DimStyles.Add(DIM_STYLE_NAME)
        except Exception:  # noqa: BLE001 - ya existe
            pass
        try:
            doc.ActiveDimStyle = doc.DimStyles.Item(DIM_STYLE_NAME)
        except Exception:  # noqa: BLE001
            pass
        for d_name, d_value in DIM_VARIABLES.items():
            try:
                doc.SetVariable(d_name, d_value)
            except Exception:  # noqa: BLE001
                pass
        for o_name, o_value in (("DIMTXT", dim_text_height), ("DIMASZ", dim_arrow_size)):
            try:
                doc.SetVariable(o_name, o_value)
            except Exception:  # noqa: BLE001
                pass

        # entidades nuevas: color y tipo de linea ByLayer
        for c_name, c_value in (("CECOLOR", "ByLayer"), ("CELTYPE", "ByLayer")):
            try:
                doc.SetVariable(c_name, c_value)
            except Exception:  # noqa: BLE001
                pass

        return {
            "success": True,
            "layers": list(STANDARD_LAYERS),
            "created_layers": created_layers,
            "existing_layers": existing_layers,
            "dim_style": DIM_STYLE_NAME,
            "dim_text_height": dim_text_height,
            "dim_arrow_size": dim_arrow_size,
            "units": "meters",
            "message": (
                f"Estandar aplicado: {len(created_layers)} capas creadas, "
                f"{len(existing_layers)} ya existian, estilo de cotas '{DIM_STYLE_NAME}'"
            ),
        }

    @staticmethod
    def _configure_layer(
        doc: Any,
        name: str,
        color: int,
        lineweight: int,
        linetype: str,
        description: str,
    ) -> None:
        layer = doc.Layers.Item(name)
        try:
            layer.color = color
        except Exception:  # noqa: BLE001
            pass
        try:
            layer.Lineweight = lineweight
        except Exception:  # noqa: BLE001
            pass
        try:
            doc.Linetypes.Load(linetype, "acad.lin")
            layer.Linetype = linetype
        except Exception:  # noqa: BLE001
            pass
        if description:
            try:
                layer.Description = description
            except Exception:  # noqa: BLE001
                pass
