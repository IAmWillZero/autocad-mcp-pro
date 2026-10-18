"""Herramienta de tablas: cuadros de areas, leyendas y rotulos tabulares.

Usa el objeto nativo ``AcDbTable`` de AutoCAD (``ModelSpace.AddTable``), que es
editable como tabla y exportable/importable desde Excel. Ideal para el cuadro de
areas en lugar de dibujarlo con lineas sueltas.
"""

from __future__ import annotations

from typing import Any

from autocad_mcp.com import variant_point
from autocad_mcp.connection import AutoCADConnection, safe_operation
from autocad_mcp.features.base import FeatureBase


class TableTools(FeatureBase):
    """Crea tablas nativas de AutoCAD rellenando sus celdas."""

    def __init__(self, conn: AutoCADConnection, cache: Any | None = None) -> None:
        super().__init__(conn, cache)

    def create_table(
        self,
        data: list[list[Any]],
        position: list[float] | None = None,
        row_height: float = 0.4,
        col_width: float = 2.0,
        col_widths: list[float] | None = None,
        title: str | None = None,
        layer: str = "A-TEXTOS",
        text_height: float = 0.18,
    ) -> dict[str, Any]:
        """Inserta una tabla y vuelca ``data`` (lista de filas) en sus celdas.

        ``data`` es una lista de filas; cada fila, una lista de celdas. La primera
        fila se usa normalmente como encabezado. Si ``title`` se indica, se agrega
        como fila superior fusionada.
        """
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}

        body = [[("" if c is None else str(c)) for c in row] for row in (data or [])]
        if title:
            body = [[str(title)]] + body

        # Filas rectangulares: todas con el mismo numero de columnas.
        cols = max((len(r) for r in body), default=0)
        if cols == 0 and (data or title):
            return {"success": False, "error": "data no contiene celdas"}
        rows = len(body)
        if rows == 0 or cols == 0:
            return {
                "success": False,
                "error": "data vacia: se requiere al menos 1 fila y 1 columna",
            }

        for r in body:
            r.extend([""] * (cols - len(r)))

        origin = list(position) if position else [0.0, 0.0]
        point = variant_point(
            float(origin[0]),
            float(origin[1]),
            float(origin[2]) if len(origin) > 2 else 0.0,
        )

        def table_operation() -> Any:
            table = self.conn.model_space().AddTable(
                point, rows, cols, float(row_height), float(col_width)
            )
            try:
                table.Layer = layer
            except Exception:  # noqa: BLE001 - capa inexistente en algunas versiones
                pass
            try:
                table.TitleSuppressed = True
                table.HeaderSuppressed = True
            except Exception:  # noqa: BLE001
                pass
            if col_widths:
                for c, cw in enumerate(col_widths[:cols]):
                    try:
                        table.SetColumnWidth(c, float(cw))
                    except Exception:  # noqa: BLE001
                        pass
            for r in range(rows):
                for c in range(cols):
                    value = body[r][c]
                    try:
                        table.SetText(r, c, value)
                    except Exception:  # noqa: BLE001 - firma distinta segun version
                        table.SetTextString(r, c, value)
                    try:
                        table.SetTextHeight(r, c, float(text_height))
                    except Exception:  # noqa: BLE001
                        pass
                    try:
                        # 5 = acMiddleCenter
                        table.SetCellAlignment(r, c, 5)
                    except Exception:  # noqa: BLE001
                        pass
            try:
                table.RegenerateTableSuppressed = False
            except Exception:  # noqa: BLE001
                pass
            self.conn.regen()
            return table

        table = safe_operation(table_operation)
        if table is None:
            return {"success": False, "error": "No se pudo crear la tabla", "type": "AcDbTable"}

        self._invalidate()
        return {
            "success": True,
            "handle": self._handle(table, "table"),
            "type": "AcDbTable",
            "rows": rows,
            "cols": cols,
            "row_height": row_height,
            "col_width": col_width,
            "layer": layer,
            "message": f"Tabla {rows}x{cols} creada en {origin} (capa {layer})",
        }

    @staticmethod
    def _handle(entity: Any, fallback: str) -> str:
        try:
            return str(entity.Handle)
        except Exception:  # noqa: BLE001
            return fallback
