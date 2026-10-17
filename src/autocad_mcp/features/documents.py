"""Herramientas de gestion de documentos abiertos (multi-dibujo)."""

from __future__ import annotations

from typing import Any

from autocad_mcp.cache import TTLCache
from autocad_mcp.connection import AutoCADConnection
from autocad_mcp.features.base import FeatureBase


class DocumentTools(FeatureBase):
    """Lista los dibujos abiertos y permite elegir en cual operar."""

    def __init__(self, conn: AutoCADConnection, cache: TTLCache) -> None:
        super().__init__(conn, cache)

    def list_documents(self) -> dict[str, Any]:
        """Devuelve los documentos abiertos en AutoCAD."""
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}
        documents = self.conn.list_documents()
        return {
            "success": True,
            "count": len(documents),
            "active_document": self.conn.document_name(),
            "documents": documents,
        }

    def set_active_document(self, name: str) -> dict[str, Any]:
        """Engancha el servidor a un documento por nombre."""
        if not self.conn.ensure():
            return {"error": "Not connected to AutoCAD"}
        if not self.conn.set_active_document(name):
            return {"success": False, "error": f"Document '{name}' not found"}
        self._invalidate()
        return {"success": True, "active_document": name}
