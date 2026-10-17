"""Bloques: listar definiciones, insertar referencias y explotar."""

from __future__ import annotations

import math
from typing import Any

from autocad_mcp.com import as_dynamic, variant_objects, variant_point
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

    def create_block(
        self,
        name: str,
        handles: list[str],
        base_point: list[float] | None = None,
        delete_source: bool = False,
    ) -> dict[str, Any]:
        """Crea (o redefine) una definicion de bloque a partir de entidades por handle.

        Las entidades se COPian a la definicion (``Document.CopyObjects``). Con
        ``delete_source=True`` se borran ademas los originales del ModelSpace
        (equivale a BLOCK con "convertir en bloque").
        """
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}
        if not name:
            return {"success": False, "error": "name es obligatorio"}

        wanted = {str(h) for h in handles}
        if not wanted:
            return {"success": False, "error": "handles vacio"}

        doc = self.conn.doc
        model_space = self.conn.model_space()
        sources: list[Any] = []
        for i in range(model_space.Count):
            try:
                entity = model_space.Item(i)
                if str(entity.Handle) in wanted:
                    sources.append(entity)
            except Exception:  # noqa: BLE001
                continue
        if not sources:
            return {"success": False, "error": "No se encontraron entidades con esos handles"}

        base = [float(v) for v in (base_point or [0.0, 0.0, 0.0])]
        while len(base) < 3:
            base.append(0.0)

        # Redefinir: si ya existe, se elimina antes.
        try:
            doc.Blocks.Item(name).Delete()
        except Exception:  # noqa: BLE001 - no existia
            pass

        try:
            block = doc.Blocks.Add(variant_point(base[0], base[1], base[2]), str(name))
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"No se pudo crear el bloque '{name}': {exc}"}

        try:
            doc.CopyObjects(variant_objects(sources), block)
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"CopyObjects fallo: {exc}"}

        if delete_source:
            for entity in sources:
                try:
                    entity.Delete()
                except Exception:  # noqa: BLE001
                    pass

        self.conn.regen()
        self._invalidate()
        return {
            "success": True,
            "block": str(name),
            "entities": len(sources),
            "deleted_source": bool(delete_source),
            "base_point": base,
            "message": f"Bloque '{name}' definido con {len(sources)} entidades"
            + (" (originales borrados)" if delete_source else ""),
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
