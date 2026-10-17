"""Fachada que compone conexion, cache y modulos de features."""

from __future__ import annotations

from autocad_mcp.cache import TTLCache
from autocad_mcp.config import AutoCADMCPConfig, get_config
from autocad_mcp.connection import AutoCADConnection
from autocad_mcp.features.analysis import AnalysisTools
from autocad_mcp.features.blocks import BlockTools
from autocad_mcp.features.delete import DeleteTools
from autocad_mcp.features.dimensions import DimensionTools
from autocad_mcp.features.documents import DocumentTools
from autocad_mcp.features.geometry import GeometryTools
from autocad_mcp.features.grid import GridTools
from autocad_mcp.features.info import InfoTools
from autocad_mcp.features.ops import BatchTool, OpsTools
from autocad_mcp.features.standards import StandardsTools
from autocad_mcp.features.structures import StructureTools
from autocad_mcp.layers import LayerTools
from autocad_mcp.obs import Metrics


class AutoCADService:
    """Punto de entrada unico a las capacidades CAD de la aplicacion."""

    def __init__(self, config: AutoCADMCPConfig | None = None) -> None:
        self.config = config or get_config()
        self.metrics = Metrics(enabled=self.config.metrics_enabled)
        self.cache = TTLCache(ttl=self.config.cache_ttl_seconds, maxsize=self.config.cache_maxsize)
        self.conn = AutoCADConnection(self.config)

        self.layer_tools = LayerTools(self.conn)
        self.geometry = GeometryTools(self.conn, self.cache)
        self.structures = StructureTools(self.conn, self.cache, self.geometry, self.layer_tools)
        self.info = InfoTools(self.conn, self.cache)
        self.analysis = AnalysisTools(self.conn, self.cache)
        self.deleter = DeleteTools(self.conn, self.cache)
        self.documents = DocumentTools(self.conn, self.cache)
        self.standards = StandardsTools(self.conn, self.cache)
        self.grid = GridTools(self.conn, self.cache)
        self.blocks = BlockTools(self.conn, self.cache)
        self.dimensions = DimensionTools(self.conn, self.cache)

        batch_tools: dict[str, BatchTool] = {
            "create_line": self.geometry.create_line,
            "create_circle": self.geometry.create_circle,
            "create_rectangle": self.geometry.create_rectangle,
            "create_polyline": self.geometry.create_polyline,
            "create_text": self.geometry.create_text,
            "create_arc": self.geometry.create_arc,
        }
        self.ops = OpsTools(
            self.conn,
            self.cache,
            self.config,
            self.metrics,
            batch_tools,
            self.reload_config,
        )

    def connect(self) -> bool:
        """Conecta a AutoCAD.

        Ya no pre-crea capas legacy (WALLS/DOORS/...): el estandar ``A-`` se aplica
        con ``apply_standard`` y las capas de estructura se crean por demanda.
        """
        return bool(self.conn.connect())

    def reload_config(self) -> dict[str, object]:
        """Recarga configuracion y reajusta cache/metricas."""
        get_config.cache_clear()
        self.config = get_config()
        self.cache.ttl = self.config.cache_ttl_seconds
        self.cache.maxsize = self.config.cache_maxsize
        self.cache.clear()
        self.metrics = Metrics(enabled=self.config.metrics_enabled)
        self.ops.metrics = self.metrics
        return {"success": True, "config": self.config.model_dump()}
