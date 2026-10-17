"""Herramientas de inspeccion: informacion del dibujo y entidades."""

from __future__ import annotations

import time
from typing import Any

from autocad_mcp.cache import TTLCache
from autocad_mcp.connection import AutoCADConnection
from autocad_mcp.features.base import FeatureBase


class InfoTools(FeatureBase):
    """Lee informacion del documento y del ModelSpace (con cache TTL)."""

    def __init__(self, conn: AutoCADConnection, cache: TTLCache) -> None:
        super().__init__(conn, cache)

    def get_drawing_info(self) -> dict[str, Any]:
        """Informacion del dibujo actual (archivo, capas, conteo de entidades)."""
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}

        cached: dict[str, Any] | None = self.cache.get("drawing_info") if self.cache else None
        if cached is not None:
            return cached

        doc = self.conn.doc
        info: dict[str, Any] = {
            "filename": "Unknown",
            "path": "Unknown",
            "entity_count": 0,
            "saved": False,
            "current_layer": "Unknown",
            "total_layers": 0,
            "available_layers": [],
        }

        try:
            info["filename"] = str(doc.Name)
        except Exception:  # noqa: BLE001
            pass
        try:
            info["path"] = str(doc.Path) if doc.Path else "Not saved"
        except Exception:  # noqa: BLE001
            pass
        try:
            info["saved"] = bool(doc.Saved)
        except Exception:  # noqa: BLE001
            pass
        try:
            info["current_layer"] = str(doc.ActiveLayer.Name)
        except Exception:  # noqa: BLE001
            pass
        try:
            info["entity_count"] = int(doc.ModelSpace.Count)
        except Exception:  # noqa: BLE001
            pass

        try:
            layers = doc.Layers
            info["total_layers"] = int(layers.Count)
            layer_list = []
            for i in range(layers.Count):
                try:
                    layer = layers.Item(i)
                    layer_list.append(
                        {
                            "name": str(layer.Name),
                            "color": int(layer.Color),
                            "frozen": bool(layer.Freeze),
                            "locked": bool(layer.Lock),
                        }
                    )
                except Exception:  # noqa: BLE001
                    continue
            info["available_layers"] = layer_list
        except Exception:  # noqa: BLE001
            pass

        if self.cache:
            self.cache.set("drawing_info", info)
        return info

    def get_entities(self, max_entities: int | None = None) -> dict[str, Any]:
        """Lista entidades del ModelSpace, agrupadas por capa."""
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}

        cache_key = f"entities:{max_entities}"
        cached_entities: dict[str, Any] | None = self.cache.get(cache_key) if self.cache else None
        if cached_entities is not None:
            return cached_entities

        try:
            model_space = self.conn.model_space()
            try:
                total_count = int(model_space.Count)
            except Exception:  # noqa: BLE001
                total_count = 0

            count = total_count if max_entities is None else min(total_count, max_entities)

            entities: list[dict[str, Any]] = []
            batch_size = 100
            processed = 0
            while processed < count:
                batch_end = min(processed + batch_size, count)
                for i in range(processed, batch_end):
                    entity_info = self._read_entity(model_space, i)
                    if entity_info is not None:
                        entities.append(entity_info)
                processed = batch_end
                if processed % 500 == 0 and processed < count:
                    time.sleep(0.1)

            entities_by_layer: dict[str, list[dict[str, Any]]] = {}
            for entity in entities:
                entities_by_layer.setdefault(entity["layer"], []).append(entity)

            result = {
                "entities": entities,
                "entities_by_layer": entities_by_layer,
                "total_count": total_count,
                "returned_count": len(entities),
                "layer_summary": {k: len(v) for k, v in entities_by_layer.items()},
            }
            if self.cache:
                self.cache.set(cache_key, result)
            return result
        except Exception as exc:  # noqa: BLE001
            return {"error": f"Failed to get entities: {exc}"}

    @staticmethod
    def _read_entity(model_space: Any, index: int) -> dict[str, Any] | None:
        try:
            entity = model_space.Item(index)
            info: dict[str, Any] = {
                "index": index,
                "type": str(entity.ObjectName),
                "layer": str(entity.Layer),
                "handle": str(entity.Handle),
                "color": int(entity.Color),
            }
        except Exception:  # noqa: BLE001
            return None

        try:
            info["visible"] = bool(entity.Visible)
        except Exception:  # noqa: BLE001
            pass

        name = info["type"]
        try:
            if name == "AcDbLine":
                sp, ep = entity.StartPoint, entity.EndPoint
                info["start_point"] = [sp[0], sp[1], sp[2]]
                info["end_point"] = [ep[0], ep[1], ep[2]]
            elif name == "AcDbCircle":
                c = entity.Center
                info["center"] = [c[0], c[1], c[2]]
                info["radius"] = float(entity.Radius)
            elif name == "AcDbText":
                ip = entity.InsertionPoint
                info["position"] = [ip[0], ip[1], ip[2]]
                info["text_string"] = str(entity.TextString)
                info["height"] = float(entity.Height)
        except Exception:  # noqa: BLE001
            pass
        return info
