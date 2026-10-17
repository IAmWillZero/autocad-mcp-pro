"""Contrato MCP: esquemas de herramientas y mapeo a handlers.

IMPORTANTE: los nombres de herramientas y sus esquemas son un contrato publico.
Solo pueden cambiar de forma aditiva (nuevos campos opcionales). No renombrar ni
eliminar herramientas existentes.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import mcp.types as types

if TYPE_CHECKING:
    from autocad_mcp.service import AutoCADService

Handler = Callable[[dict[str, Any]], dict[str, Any]]


def list_tool_schemas() -> list[types.Tool]:
    """Esquemas de todas las herramientas MCP expuestas."""
    return [
        types.Tool(
            name="get_drawing_info",
            description="Get information about the current AutoCAD drawing including layers",
            input_schema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="list_documents",
            description="List all open AutoCAD drawings (name, path, active flag)",
            input_schema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="set_active_document",
            description="Bind the server to a specific open drawing by name (get names from list_documents)",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Document name as returned by list_documents (e.g. 'Drawing1.dwg')",
                    }
                },
                "required": ["name"],
            },
        ),
        types.Tool(
            name="get_entities",
            description="Get list of ALL entities in the current drawing with their properties and layer information",
            input_schema={
                "type": "object",
                "properties": {
                    "max_entities": {
                        "type": "integer",
                        "description": "Maximum number of entities to retrieve (default: all entities)",
                        "minimum": 1,
                    }
                },
                "required": [],
            },
        ),
        types.Tool(
            name="analyze_drawing",
            description=(
                "Analyze the current drawing and return a report: totals by type and layer, "
                "drawing extents, dimensions with their measured values (to verify them) and "
                "text annotations. Optionally include per-entity coordinates."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "include_entities": {
                        "type": "boolean",
                        "description": "Include the per-entity list with coordinates/geometry",
                        "default": False,
                    },
                    "entity_type": {
                        "type": "string",
                        "description": "Only include entities whose type contains this text (e.g. 'Line')",
                    },
                    "layer": {
                        "type": "string",
                        "description": "Only include entities on this layer",
                    },
                    "max_entities": {
                        "type": "integer",
                        "description": "Max entities listed when include_entities is true (default 500)",
                        "minimum": 1,
                        "default": 500,
                    },
                    "include_geometry": {
                        "type": "boolean",
                        "description": "Compute geometry (start/end, center, coordinates...) per entity",
                        "default": True,
                    },
                },
                "required": [],
            },
        ),
        types.Tool(
            name="create_structure",
            description="Create a structured building element (wall, door, window, room) with automatic layer assignment and labeling",
            input_schema={
                "type": "object",
                "properties": {
                    "structure_type": {
                        "type": "string",
                        "description": "Type of structure (wall, door, window, room, furniture, etc.)",
                        "enum": [
                            "wall",
                            "door",
                            "window",
                            "room",
                            "furniture",
                            "electrical",
                            "plumbing",
                            "hvac",
                        ],
                    },
                    "geometry_data": {
                        "type": "object",
                        "description": "Geometry data - use start/end for lines, center/radius for circles, corner1/corner2 for rectangles",
                    },
                    "color": {
                        "type": "string",
                        "description": "Color name (uses layer default if not specified)",
                        "default": "null",
                    },
                    "thickness": {
                        "type": "number",
                        "description": "Structure thickness (0.1 default for walls)",
                        "default": 0.0,
                    },
                    "custom_layer": {
                        "type": "string",
                        "description": "Custom layer name (uses automatic layer if not specified)",
                        "default": "null",
                    },
                    "label": {
                        "type": "string",
                        "description": "Optional text label for the structure",
                        "default": "null",
                    },
                },
                "required": ["structure_type", "geometry_data"],
            },
        ),
        types.Tool(
            name="create_or_get_layer",
            description="Create a new layer or get existing layer with specified properties",
            input_schema={
                "type": "object",
                "properties": {
                    "layer_name": {"type": "string", "description": "Name of the layer"},
                    "color": {"type": "string", "description": "Layer color", "default": "white"},
                    "description": {
                        "type": "string",
                        "description": "Layer description",
                        "default": "",
                    },
                },
                "required": ["layer_name"],
            },
        ),
        types.Tool(
            name="set_current_layer",
            description="Set the current active layer",
            input_schema={
                "type": "object",
                "properties": {
                    "layer_name": {
                        "type": "string",
                        "description": "Name of the layer to make active",
                    }
                },
                "required": ["layer_name"],
            },
        ),
        types.Tool(
            name="create_line",
            description="Create a line in AutoCAD with optional color and thickness",
            input_schema={
                "type": "object",
                "properties": {
                    "start": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Start point [x, y] or [x, y, z]",
                    },
                    "end": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "End point [x, y] or [x, y, z]",
                    },
                    "color": {
                        "type": "string",
                        "description": "Color name (red, blue, green, yellow, cyan, magenta, white, black, gray, light_gray) or ACI number",
                        "default": "white",
                    },
                    "thickness": {
                        "type": "number",
                        "description": "Line thickness (creates parallel lines)",
                        "default": 0.0,
                    },
                },
                "required": ["start", "end"],
            },
        ),
        types.Tool(
            name="create_circle",
            description="Create a circle in AutoCAD with optional color and thickness",
            input_schema={
                "type": "object",
                "properties": {
                    "center": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Center point [x, y] or [x, y, z]",
                    },
                    "radius": {"type": "number", "description": "Circle radius"},
                    "color": {
                        "type": "string",
                        "description": "Color name or ACI number",
                        "default": "white",
                    },
                    "thickness": {
                        "type": "number",
                        "description": "Circle thickness (creates concentric circles)",
                        "default": 0.0,
                    },
                },
                "required": ["center", "radius"],
            },
        ),
        types.Tool(
            name="create_rectangle",
            description="Create a rectangle in AutoCAD with optional color and thickness",
            input_schema={
                "type": "object",
                "properties": {
                    "corner1": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "First corner [x, y]",
                    },
                    "corner2": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Opposite corner [x, y]",
                    },
                    "color": {
                        "type": "string",
                        "description": "Color name or ACI number",
                        "default": "white",
                    },
                    "thickness": {
                        "type": "number",
                        "description": "Rectangle thickness",
                        "default": 0.0,
                    },
                },
                "required": ["corner1", "corner2"],
            },
        ),
        types.Tool(
            name="create_polyline",
            description="Create a 2D polyline in AutoCAD from a list of points, optionally closed, with optional width",
            input_schema={
                "type": "object",
                "properties": {
                    "points": {
                        "type": "array",
                        "description": "List of [x, y] vertices (min 2)",
                        "items": {"type": "array", "items": {"type": "number"}},
                    },
                    "closed": {
                        "type": "boolean",
                        "description": "Close the polyline",
                        "default": False,
                    },
                    "color": {
                        "type": "string",
                        "description": "Color name or ACI number",
                        "default": "white",
                    },
                    "width": {
                        "type": "number",
                        "description": "Constant width of the polyline",
                        "default": 0.0,
                    },
                },
                "required": ["points"],
            },
        ),
        types.Tool(
            name="create_text",
            description="Create text in AutoCAD with optional color",
            input_schema={
                "type": "object",
                "properties": {
                    "position": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Text position [x, y] or [x, y, z]",
                    },
                    "text": {"type": "string", "description": "Text content"},
                    "height": {"type": "number", "description": "Text height", "default": 1.0},
                    "color": {
                        "type": "string",
                        "description": "Text color name or ACI number",
                        "default": "white",
                    },
                },
                "required": ["position", "text"],
            },
        ),
        types.Tool(
            name="create_arc",
            description="Create an arc in AutoCAD with optional color and thickness",
            input_schema={
                "type": "object",
                "properties": {
                    "center": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Center point [x, y] or [x, y, z]",
                    },
                    "radius": {"type": "number", "description": "Arc radius"},
                    "start_angle": {
                        "type": "number",
                        "description": "Start angle in degrees (0° = positive X axis)",
                    },
                    "end_angle": {"type": "number", "description": "End angle in degrees"},
                    "color": {
                        "type": "string",
                        "description": "Color name or ACI number",
                        "default": "white",
                    },
                    "thickness": {
                        "type": "number",
                        "description": "Arc thickness (creates parallel arcs with connecting lines)",
                        "default": 0.0,
                    },
                },
                "required": ["center", "radius", "start_angle", "end_angle"],
            },
        ),
        types.Tool(
            name="delete_entity_by_handle",
            description="Delete a specific entity by its handle (get handle from get_entities)",
            input_schema={
                "type": "object",
                "properties": {
                    "handle": {"type": "string", "description": "Entity handle to delete"}
                },
                "required": ["handle"],
            },
        ),
        types.Tool(
            name="delete_entities_by_handles",
            description="Delete multiple entities by their handles",
            input_schema={
                "type": "object",
                "properties": {
                    "handles": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of entity handles to delete",
                    }
                },
                "required": ["handles"],
            },
        ),
        types.Tool(
            name="delete_entities_by_type",
            description="Delete all entities of a specific type (e.g., 'AcDbLine', 'AcDbCircle', 'AcDbText', 'AcDbArc')",
            input_schema={
                "type": "object",
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "description": "AutoCAD entity type (e.g., AcDbLine, AcDbCircle, AcDbText, AcDbArc)",
                    }
                },
                "required": ["entity_type"],
            },
        ),
        types.Tool(
            name="delete_entities_by_layer",
            description="Delete all entities on a specific layer",
            input_schema={
                "type": "object",
                "properties": {
                    "layer_name": {
                        "type": "string",
                        "description": "Layer name (e.g., '0' for default layer, 'WALLS', 'DOORS', etc.)",
                    }
                },
                "required": ["layer_name"],
            },
        ),
        types.Tool(
            name="delete_entities_by_color",
            description="Delete all entities with a specific color",
            input_schema={
                "type": "object",
                "properties": {
                    "color": {
                        "type": "string",
                        "description": "Color name (red, blue, green, etc.) or ACI number",
                    }
                },
                "required": ["color"],
            },
        ),
        types.Tool(
            name="delete_entities_by_type_and_color",
            description="Delete entities of a specific type AND color (e.g., only green text, only red lines)",
            input_schema={
                "type": "object",
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "description": "AutoCAD entity type (e.g., AcDbText, AcDbLine, AcDbCircle, AcDbArc)",
                    },
                    "color": {
                        "type": "string",
                        "description": "Color name (red, blue, green, etc.) or ACI number",
                    },
                },
                "required": ["entity_type", "color"],
            },
        ),
        types.Tool(
            name="delete_last_entities",
            description="Delete the last N entities created (most recent entities)",
            input_schema={
                "type": "object",
                "properties": {
                    "count": {
                        "type": "integer",
                        "description": "Number of recent entities to delete",
                        "default": 1,
                        "minimum": 1,
                    }
                },
                "required": [],
            },
        ),
        types.Tool(
            name="delete_all_entities",
            description="Delete ALL entities in the drawing (requires confirmation)",
            input_schema={
                "type": "object",
                "properties": {
                    "confirm": {
                        "type": "boolean",
                        "description": "Must be set to true to confirm deletion of all entities",
                        "default": False,
                    }
                },
                "required": ["confirm"],
            },
        ),
        types.Tool(
            name="undo_last_operation",
            description="Undo the last operation in AutoCAD (equivalent to Ctrl+Z)",
            input_schema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="change_entity_color",
            description="Change the color of an existing entity by its handle",
            input_schema={
                "type": "object",
                "properties": {
                    "handle": {
                        "type": "string",
                        "description": "Entity handle (get from get_entities)",
                    },
                    "color": {
                        "type": "string",
                        "description": "New color name or ACI number",
                    },
                },
                "required": ["handle", "color"],
            },
        ),
        types.Tool(
            name="zoom_extents",
            description="Zoom to show all objects in the drawing",
            input_schema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="health_check",
            description="Devuelve el estado OK/ERROR de la conexion con AutoCAD antes de operaciones criticas",
            input_schema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="get_metrics",
            description="Expone contadores de llamadas, latencia media y errores del servidor MCP",
            input_schema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="clear_cache",
            description="Fuerza el refresco de la cache TTL de get_entities y get_drawing_info",
            input_schema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="reload_config",
            description="Recarga la configuracion desde variables de entorno y .env",
            input_schema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="batch_execute",
            description="Agrupa varias operaciones de AutoCAD en una sola pasada por ModelSpace",
            input_schema={
                "type": "object",
                "properties": {
                    "operations": {
                        "type": "array",
                        "description": "Lista de operaciones a ejecutar en orden",
                        "items": {
                            "type": "object",
                            "properties": {
                                "tool": {
                                    "type": "string",
                                    "description": "Nombre de la herramienta MCP a invocar (create_line, create_circle, create_rectangle, create_text, create_arc)",
                                },
                                "arguments": {
                                    "type": "object",
                                    "description": "Argumentos de la herramienta",
                                },
                            },
                            "required": ["tool", "arguments"],
                        },
                    }
                },
                "required": ["operations"],
            },
        ),
    ]


def build_handlers(service: AutoCADService) -> dict[str, Handler]:
    """Construye el mapa nombre-de-tool -> funcion que ejecuta el servicio."""
    geo = service.geometry
    return {
        # info
        "get_drawing_info": lambda a: service.info.get_drawing_info(),
        "get_entities": lambda a: service.info.get_entities(a.get("max_entities")),
        "analyze_drawing": lambda a: service.analysis.analyze_drawing(
            a.get("include_entities", False),
            a.get("entity_type"),
            a.get("layer"),
            a.get("max_entities", 500),
            a.get("include_geometry", True),
        ),
        "list_documents": lambda a: service.documents.list_documents(),
        "set_active_document": lambda a: service.documents.set_active_document(a["name"]),
        # structures
        "create_structure": lambda a: service.structures.create_structure(
            a["structure_type"],
            a["geometry_data"],
            a.get("color"),
            a.get("thickness", 0.0),
            a.get("custom_layer"),
            a.get("label"),
        ),
        # layers
        "create_or_get_layer": lambda a: {
            "success": service.layer_tools.create_or_get_layer(
                a["layer_name"], a.get("color", "white"), a.get("description", "")
            ),
            "layer_name": a["layer_name"],
        },
        "set_current_layer": lambda a: {
            "success": service.layer_tools.set_current_layer(a["layer_name"]),
            "layer_name": a["layer_name"],
        },
        # geometry
        "create_line": lambda a: geo.create_line(
            a["start"], a["end"], a.get("color", "white"), a.get("thickness", 0.0)
        ),
        "create_circle": lambda a: geo.create_circle(
            a["center"], a["radius"], a.get("color", "white"), a.get("thickness", 0.0)
        ),
        "create_rectangle": lambda a: geo.create_rectangle(
            a["corner1"], a["corner2"], a.get("color", "white"), a.get("thickness", 0.0)
        ),
        "create_polyline": lambda a: geo.create_polyline(
            a["points"], a.get("closed", False), a.get("color", "white"), a.get("width", 0.0)
        ),
        "create_text": lambda a: geo.create_text(
            a["position"], a["text"], a.get("height", 1.0), a.get("color", "white")
        ),
        "create_arc": lambda a: geo.create_arc(
            a["center"],
            a["radius"],
            a["start_angle"],
            a["end_angle"],
            a.get("color", "white"),
            a.get("thickness", 0.0),
        ),
        # delete
        "delete_entity_by_handle": lambda a: service.deleter.delete_entity_by_handle(a["handle"]),
        "delete_entities_by_handles": lambda a: service.deleter.delete_entities_by_handles(
            a["handles"]
        ),
        "delete_entities_by_type": lambda a: service.deleter.delete_entities_by_type(
            a["entity_type"]
        ),
        "delete_entities_by_layer": lambda a: service.deleter.delete_entities_by_layer(
            a["layer_name"]
        ),
        "delete_entities_by_color": lambda a: service.deleter.delete_entities_by_color(a["color"]),
        "delete_entities_by_type_and_color": lambda a: (
            service.deleter.delete_entities_by_type_and_color(a["entity_type"], a["color"])
        ),
        "delete_last_entities": lambda a: service.deleter.delete_last_entities(a.get("count", 1)),
        "delete_all_entities": lambda a: service.deleter.delete_all_entities(
            a.get("confirm", False)
        ),
        # ops
        "undo_last_operation": lambda a: service.ops.undo_last_operation(),
        "change_entity_color": lambda a: service.ops.change_entity_color(a["handle"], a["color"]),
        "zoom_extents": lambda a: service.ops.zoom_extents(),
        "health_check": lambda a: service.ops.health_check(),
        "get_metrics": lambda a: service.ops.get_metrics(),
        "clear_cache": lambda a: service.ops.clear_cache(),
        "reload_config": lambda a: service.ops.reload_config(),
        "batch_execute": lambda a: service.ops.batch_execute(a.get("operations", [])),
    }
