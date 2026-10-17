"""Herramientas de analisis: informe del contenido del dibujo.

A diferencia de :meth:`InfoTools.get_entities` (listado crudo), este modulo
produce un informe agregado y legible: resumen por tipo/capa, extensiones
(extents), cotas con su medida y anotaciones. Sirve para verificar que lo que
se dibujo es correcto (por ejemplo, que una cota mida lo que debe).
"""

from __future__ import annotations

from typing import Any

from autocad_mcp.com import as_dynamic
from autocad_mcp.features.base import FeatureBase

_POLYLINES = ("AcDbPolyline", "AcDb2dPolyline", "AcDb3dPolyline")
_TEXT_TYPES = ("AcDbText", "AcDbMText", "AcDbAttribute")


def _round(value: Any, ndigits: int = 4) -> float:
    """Redondea un valor COM a float, tolerante a errores."""
    try:
        return round(float(value), ndigits)
    except (TypeError, ValueError):
        return 0.0


def _point(value: Any) -> list[float]:
    """Convierte un punto COM (VARIANT/safearray) a ``[x, y, z]``."""
    try:
        return [_round(value[0]), _round(value[1]), _round(value[2])]
    except (TypeError, IndexError, ValueError):
        return [0.0, 0.0, 0.0]


def _floats(value: Any) -> list[float]:
    """Convierte un safearray de doubles a lista de floats."""
    try:
        return [_round(v) for v in value]
    except (TypeError, ValueError):
        return []


class AnalysisTools(FeatureBase):
    """Genera un informe del contenido del ModelSpace actual."""

    def analyze_drawing(
        self,
        include_entities: bool = False,
        entity_type: str | None = None,
        layer: str | None = None,
        max_entities: int = 500,
        include_geometry: bool = True,
    ) -> dict[str, Any]:
        """Informe del dibujo: resumen, extents, cotas y anotaciones."""
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}

        doc = self.conn.doc
        try:
            model_space = self.conn.model_space()
            total = int(model_space.Count)
        except Exception as exc:  # noqa: BLE001
            return {"error": f"Failed to read model space: {exc}"}

        by_type: dict[str, int] = {}
        by_layer: dict[str, int] = {}
        dimensions: list[dict[str, Any]] = []
        annotations: list[dict[str, Any]] = []
        selected: list[dict[str, Any]] = []
        bb_min = [float("inf")] * 3
        bb_max = [float("-inf")] * 3

        limit = max(1, int(max_entities))
        for i in range(total):
            desc = self._describe(model_space, i, include_geometry)
            if desc is None:
                continue

            by_type[desc["type"]] = by_type.get(desc["type"], 0) + 1
            by_layer[desc["layer"]] = by_layer.get(desc["layer"], 0) + 1
            self._expand_extents(bb_min, bb_max, desc.get("bounds"))

            if "Dimension" in desc["type"]:
                dimensions.append(self._dimension_record(desc))
            elif desc["type"] in _TEXT_TYPES:
                annotations.append(self._annotation_record(desc))

            if self._passes_filter(desc, entity_type, layer) and len(selected) < limit:
                selected.append(desc)

        extents = self._extents(bb_min, bb_max)

        return {
            "success": True,
            "document": {
                "name": self.conn.document_name(),
                "path": str(getattr(doc, "Path", "") or ""),
            },
            "summary": {
                "total_entities": total,
                "counts_by_type": dict(sorted(by_type.items())),
                "counts_by_layer": dict(sorted(by_layer.items())),
            },
            "extents": extents,
            "dimensions": dimensions,
            "annotations": annotations,
            "filters": {"entity_type": entity_type, "layer": layer},
            "returned_count": len(selected),
            "entities": selected if include_entities else [],
            "message": (
                f"Analizados {total} objetos: {len(by_type)} tipos, "
                f"{len(dimensions)} cotas, {len(annotations)} anotaciones"
            ),
        }

    # --- helpers ---------------------------------------------------------
    @staticmethod
    def _passes_filter(desc: dict[str, Any], entity_type: str | None, layer: str | None) -> bool:
        if entity_type and entity_type.lower() not in desc["type"].lower():
            return False
        return not (layer and desc["layer"].lower() != layer.lower())

    @staticmethod
    def _expand_extents(
        bb_min: list[float], bb_max: list[float], bounds: dict[str, Any] | None
    ) -> None:
        if not bounds:
            return
        for k in range(3):
            bb_min[k] = min(bb_min[k], bounds["min"][k])
            bb_max[k] = max(bb_max[k], bounds["max"][k])

    @staticmethod
    def _extents(bb_min: list[float], bb_max: list[float]) -> dict[str, Any]:
        if bb_min[0] == float("inf"):
            return {"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0], "width": 0.0, "height": 0.0}
        width = _round(bb_max[0] - bb_min[0])
        height = _round(bb_max[1] - bb_min[1])
        return {
            "min": bb_min,
            "max": bb_max,
            "width": width,
            "height": height,
        }

    @staticmethod
    def _dimension_record(desc: dict[str, Any]) -> dict[str, Any]:
        geom = desc.get("geometry", {})
        return {
            "handle": desc["handle"],
            "type": desc["type"],
            "layer": desc["layer"],
            "measurement": geom.get("measurement"),
            "text_override": geom.get("textoverride"),
        }

    @staticmethod
    def _annotation_record(desc: dict[str, Any]) -> dict[str, Any]:
        geom = desc.get("geometry", {})
        return {
            "handle": desc["handle"],
            "type": desc["type"],
            "layer": desc["layer"],
            "text": geom.get("text"),
            "position": geom.get("position"),
        }

    def _describe(
        self, model_space: Any, index: int, include_geometry: bool
    ) -> dict[str, Any] | None:
        try:
            entity = as_dynamic(model_space.Item(index))
            obj = str(entity.ObjectName)
            desc: dict[str, Any] = {
                "index": index,
                "type": obj,
                "layer": str(entity.Layer),
                "handle": str(entity.Handle),
                "color": int(entity.color),
            }
        except Exception:  # noqa: BLE001
            return None

        try:
            desc["visible"] = bool(entity.Visible)
        except Exception:  # noqa: BLE001
            pass

        try:
            bb = entity.GetBoundingBox()
            desc["bounds"] = {
                "min": _point(bb[0]),
                "max": _point(bb[1]),
            }
        except Exception:  # noqa: BLE001
            pass

        if include_geometry:
            desc["geometry"] = self._geometry(entity, obj)
        return desc

    def _geometry(self, entity: Any, obj: str) -> dict[str, Any]:
        try:
            if obj == "AcDbLine":
                return {
                    "start": _point(entity.StartPoint),
                    "end": _point(entity.EndPoint),
                    "length": _round(entity.Length),
                }
            if obj == "AcDbCircle":
                return {"center": _point(entity.Center), "radius": _round(entity.Radius)}
            if obj == "AcDbArc":
                return {
                    "center": _point(entity.Center),
                    "radius": _round(entity.Radius),
                    "start_angle": _round(entity.StartAngle),
                    "end_angle": _round(entity.EndAngle),
                }
            if obj == "AcDbEllipse":
                return {
                    "center": _point(entity.Center),
                    "major_radius": _round(entity.MajorRadius),
                    "minor_radius": _round(entity.MinorRadius),
                }
            if obj in _POLYLINES:
                coords = _floats(entity.Coordinates)
                per_vertex = 2 if obj == "AcDbPolyline" else 3
                return {
                    "closed": bool(entity.Closed),
                    "vertex_count": len(coords) // per_vertex,
                    "coordinates": coords,
                }
            if obj == "AcDbPoint":
                return {"position": _point(entity.Coordinates)}
            if obj == "AcDbText":
                return {
                    "text": str(entity.TextString),
                    "position": _point(entity.InsertionPoint),
                    "height": _round(entity.Height),
                }
            if obj == "AcDbMText":
                return {
                    "text": str(entity.TextString),
                    "position": _point(entity.InsertionPoint),
                    "width": _round(entity.Width),
                }
            if obj == "AcDbBlockReference":
                return {
                    "block_name": str(entity.Name),
                    "position": _point(entity.InsertionPoint),
                }
            if obj == "AcDbHatch":
                return {"pattern": str(entity.PatternName), "loops": int(entity.NumberOfLoops)}
            if obj == "AcDbAttribute":
                return {
                    "text": str(entity.TextString),
                    "tag": str(entity.TagString),
                    "position": _point(entity.InsertionPoint),
                }
            if "Dimension" in obj:
                return self._dimension_geometry(entity)
        except Exception:  # noqa: BLE001
            return {}
        return {}

    @staticmethod
    def _dimension_geometry(entity: Any) -> dict[str, Any]:
        geom: dict[str, Any] = {}
        for attr in ("Measurement", "TextOverride", "TextPosition", "Rotation"):
            try:
                value = getattr(entity, attr)
                key = attr.lower()
                if attr == "TextPosition":
                    geom[key] = _point(value)
                elif attr == "TextOverride":
                    geom[key] = str(value)
                else:
                    geom[key] = _round(value)
            except Exception:  # noqa: BLE001
                continue
        return geom
