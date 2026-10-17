"""Bloques: listar definiciones, insertar referencias y explotar."""

from __future__ import annotations

import math
from typing import Any

from autocad_mcp.com import as_dynamic, variant_point
from autocad_mcp.connection import AutoCADConnection
from autocad_mcp.features.base import FeatureBase


class BlockTools(FeatureBase):
    """Trabaja con definiciones de bloque y referencias en el ModelSpace."""

    def __init__(self, conn: AutoCADConnection, cache: Any | None = None) -> None:
        super().__init__(conn, cache)

    def list_blocks(self) -> dict[str, Any]:
        """Lista las definiciones de bloque con nombre (excluye anonimas/layout)."""
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}

        blocks: list[dict[str, Any]] = []
        try:
            collection = self.conn.doc.Blocks
            for i in range(int(collection.Count)):
                try:
                    block = collection.Item(i)
                    name = str(block.Name)
                except Exception:  # noqa: BLE001
                    continue
                if name.startswith("*"):
                    continue  # *Model_Space, *Paper_Space, *D.. (anonimos) no son utiles
                blocks.append({"name": name})
        except Exception as exc:  # noqa: BLE001
            return {"error": f"Failed to list blocks: {exc}"}

        blocks.sort(key=lambda b: b["name"])
        return {"success": True, "count": len(blocks), "blocks": blocks}

    def insert_block(
        self,
        name: str,
        position: list[float],
        scale: float = 1.0,
        rotation: float = 0.0,
        layer: str | None = None,
    ) -> dict[str, Any]:
        """Inserta una referencia de bloque (rotacion en grados)."""
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}

        try:
            ref = self.conn.model_space().InsertBlock(
                variant_point(*position),
                str(name),
                float(scale),
                float(scale),
                float(scale),
                math.radians(float(rotation)),
            )
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"Failed to insert block '{name}': {exc}"}

        if layer:
            try:
                ref.Layer = str(layer)
            except Exception:  # noqa: BLE001
                pass

        self.conn.regen()
        self._invalidate()
        return {
            "success": True,
            "block": str(name),
            "handle": self._handle(ref),
            "position": [float(position[0]), float(position[1])],
            "scale": float(scale),
            "rotation": float(rotation),
            "layer": layer,
            "message": f"Bloque '{name}' insertado en {position}",
        }

    def explode_entities(self, handles: list[str]) -> dict[str, Any]:
        """Explota referencias de bloque por handle y borra la referencia original."""
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}

        wanted = {str(h) for h in handles}
        exploded_refs: list[str] = []
        created = 0
        for entity in list(self._iter_modelspace()):
            try:
                handle = str(entity.Handle)
                if handle not in wanted or str(entity.ObjectName) != "AcDbBlockReference":
                    continue
                out = entity.Explode()
                created += len(out) if out else 0
                # COM deja viva la referencia: se borra explicitamente.
                entity.Delete()
                exploded_refs.append(handle)
            except Exception:  # noqa: BLE001
                continue

        if exploded_refs:
            self.conn.regen()
            self._invalidate()

        return {
            "success": True,
            "exploded_count": len(exploded_refs),
            "entities_created": created,
            "handles": exploded_refs,
            "message": (
                f"{len(exploded_refs)} bloques explotados -> {created} entidades primitivas"
            ),
        }

    def _iter_modelspace(self) -> Any:
        model_space = self.conn.model_space()
        for i in range(model_space.Count):
            try:
                # Late binding: las entidades de la coleccion llegan como la interfaz
                # base IAcadEntity, que no expone metodos como Explode().
                yield as_dynamic(model_space.Item(i))
            except Exception:  # noqa: BLE001
                continue

    @staticmethod
    def _handle(entity: Any) -> str:
        try:
            return str(entity.Handle)
        except Exception:  # noqa: BLE001
            return ""
