"""Definiciones de capas y gestion de capas de AutoCAD."""

from __future__ import annotations

from autocad_mcp.colors import color_index
from autocad_mcp.connection import AutoCADConnection

# Capas predefinidas por tipo de estructura, alineadas al estandar de dibujo:
#   A- Arquitectura, I- Instalaciones (MEP). Ver autocad_mcp.standards.
STRUCTURE_LAYERS: dict[str, dict[str, str]] = {
    "walls": {
        "name": "A-MUROS-CARGA",
        "color": "blue",
        "description": "Muros estructurales cortados",
    },
    "partitions": {"name": "A-MUROS-TABIQ", "color": "white", "description": "Tabiques divisorios"},
    "doors": {"name": "A-PUER-VENT", "color": "cyan", "description": "Puertas"},
    "windows": {"name": "A-PUER-VENT", "color": "cyan", "description": "Ventanas"},
    "furniture": {
        "name": "A-MOBILIARIO",
        "color": "gray",
        "description": "Mobiliario y artefactos",
    },
    "electrical": {"name": "I-ELECTR", "color": "red", "description": "Instalacion electrica"},
    "plumbing": {"name": "I-SANIT", "color": "blue", "description": "Instalacion sanitaria"},
    "hvac": {"name": "I-CLIM", "color": "magenta", "description": "Climatizacion y ventilacion"},
    "structure": {
        "name": "A-MUROS-CARGA",
        "color": "blue",
        "description": "Elementos estructurales",
    },
    "annotation": {"name": "A-TEXTOS", "color": "yellow", "description": "Textos y rotulos"},
    "site": {"name": "A-SITIO", "color": "green", "description": "Terreno y paisajismo"},
    "utilities": {
        "name": "I-ELECTR",
        "color": "red",
        "description": "Lineas y equipos de servicio",
    },
}

# Mapeo de palabra clave en el nombre del tipo -> clave de STRUCTURE_LAYERS.
STRUCTURE_TYPE_KEYWORDS: dict[str, str] = {
    "wall": "walls",
    "partition": "partitions",
    "tabique": "partitions",
    "door": "doors",
    "window": "windows",
    "furniture": "furniture",
    "chair": "furniture",
    "table": "furniture",
    "bed": "furniture",
    "electrical": "electrical",
    "outlet": "electrical",
    "switch": "electrical",
    "light": "electrical",
    "plumbing": "plumbing",
    "toilet": "plumbing",
    "sink": "plumbing",
    "hvac": "hvac",
    "vent": "hvac",
    "duct": "hvac",
    "structure": "structure",
    "beam": "structure",
    "column": "structure",
    "text": "annotation",
    "dimension": "annotation",
    "site": "site",
    "tree": "site",
    "utility": "utilities",
}

DEFAULT_LAYER = "0"


def layer_for_structure_type(structure_type: str) -> str:
    """Devuelve la capa por defecto para un tipo de estructura dado."""
    lowered = structure_type.lower()
    for keyword, layer_key in STRUCTURE_TYPE_KEYWORDS.items():
        if keyword in lowered:
            return STRUCTURE_LAYERS[layer_key]["name"]
    return DEFAULT_LAYER


class LayerTools:
    """Operaciones de capas sobre el documento activo."""

    def __init__(self, conn: AutoCADConnection) -> None:
        self.conn = conn

    def create_or_get_layer(
        self, layer_name: str, color: str | int = "white", description: str = ""
    ) -> bool:
        """Crea una capa nueva o reutiliza la existente."""
        if not self.conn.ensure():
            return False

        try:
            layers = self.conn.doc.Layers
            try:
                layers.Item(layer_name)
                return True
            except Exception:  # noqa: BLE001 - la capa no existe, se crea
                pass

            new_layer = layers.Add(layer_name)
            new_layer.color = color_index(color)
            try:
                new_layer.Description = description
            except Exception:  # noqa: BLE001 - no soportado en algunas versiones
                pass
            return True
        except Exception:  # noqa: BLE001
            return False

    def set_current_layer(self, layer_name: str) -> bool:
        """Establece la capa activa."""
        if not self.conn.ensure():
            return False

        try:
            self.conn.doc.ActiveLayer = self.conn.doc.Layers.Item(layer_name)
            return True
        except Exception:  # noqa: BLE001
            return False

    def current_layer_name(self) -> str | None:
        """Nombre de la capa activa, o ``None`` si no se puede leer."""
        try:
            return str(self.conn.doc.ActiveLayer.Name)
        except Exception:  # noqa: BLE001
            return None

    def ensure_structure_layers(self) -> None:
        """Crea todas las capas predefinidas si no existen."""
        for info in STRUCTURE_LAYERS.values():
            self.create_or_get_layer(info["name"], info["color"], info["description"])

    def layer_color(self, layer_name: str) -> str | None:
        """Color configurado para una capa predefinida."""
        for info in STRUCTURE_LAYERS.values():
            if info["name"] == layer_name:
                return info["color"]
        return None
