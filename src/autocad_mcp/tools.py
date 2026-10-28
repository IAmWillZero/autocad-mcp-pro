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
            name="apply_standard",
            description=(
                "Apply the architectural drawing standard: metric units (meters), the A- layer "
                "set with color/lineweight/linetype (A-MUROS-CARGA, A-MUROS-TABIQ, A-PUER-VENT, "
                "A-MOBILIARIO, A-COTAS, A-EJES, A-PROYECC, A-TEXTOS) and a scaled dimension style."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "dim_text_height": {
                        "type": "number",
                        "description": "Dimension text height in drawing units (meters)",
                        "default": 0.2,
                    },
                    "dim_arrow_size": {
                        "type": "number",
                        "description": "Dimension arrow size in drawing units (meters)",
                        "default": 0.12,
                    },
                },
                "required": [],
            },
        ),
        types.Tool(
            name="create_construction_grid",
            description=(
                "Draw construction axes (grid): vertical axes numbered 1..n and horizontal "
                "axes lettered A..n, each with bubbles and a centered label at both ends."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "vertical_positions": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "X positions of vertical axes (labeled 1, 2, 3...)",
                    },
                    "horizontal_positions": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Y positions of horizontal axes (labeled A, B, C...)",
                    },
                    "bubble_radius": {"type": "number", "default": 0.45},
                    "overshoot": {
                        "type": "number",
                        "description": "How far axes extend beyond the outer positions",
                        "default": 1.0,
                    },
                    "overshoot_bottom": {
                        "type": "number",
                        "description": "Override overshoot below the lowest horizontal axis (bubbles at extremes)",
                    },
                    "overshoot_top": {
                        "type": "number",
                        "description": "Override overshoot above the highest horizontal axis",
                    },
                    "overshoot_left": {
                        "type": "number",
                        "description": "Override overshoot left of the first vertical axis",
                    },
                    "overshoot_right": {
                        "type": "number",
                        "description": "Override overshoot right of the last vertical axis",
                    },
                    "text_height": {"type": "number", "default": 0.3},
                    "layer": {"type": "string", "default": "A-EJES"},
                },
                "required": [],
            },
        ),
        types.Tool(
            name="create_dimension",
            description=(
                "Create a dimension (rotated/linear, aligned, radial or diametric) on a layer, "
                "optionally using a named dimension style."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "dim_type": {
                        "type": "string",
                        "enum": ["rotated", "linear", "aligned", "radial", "diametric"],
                    },
                    "points": {
                        "type": "array",
                        "description": (
                            "rotated/aligned: [start, end]; radial/diametric: [center, chord]"
                        ),
                        "items": {"type": "array", "items": {"type": "number"}},
                    },
                    "dim_line_point": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Location of the dimension line (rotated/aligned)",
                    },
                    "rotation": {
                        "type": "number",
                        "description": "Rotation in degrees for rotated dimensions (0=horizontal, 90=vertical)",
                        "default": 0.0,
                    },
                    "leader_length": {
                        "type": "number",
                        "description": "Leader length for radial/diametric dimensions",
                        "default": 1.0,
                    },
                    "layer": {"type": "string", "default": "A-COTAS"},
                    "style": {
                        "type": "string",
                        "description": "Dimension style name (e.g. 'MCP-ARQ')",
                    },
                },
                "required": ["dim_type", "points"],
            },
        ),
        types.Tool(
            name="set_dimension_precision",
            description=(
                "Set the text precision (decimal places) of every dimension in model space. "
                "Applies a reliable DIMOVERRIDE of DIMDEC/DIMZIN to the existing dimensions "
                "(keeps them associative; only changes formatting)."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "decimals": {
                        "type": "integer",
                        "description": "Maximum number of decimal places (0-8)",
                        "default": 3,
                    },
                    "suppress_trailing_zeros": {
                        "type": "boolean",
                        "description": "Suppress trailing zeros (3.500 -> 3.5)",
                        "default": True,
                    },
                },
                "required": [],
            },
        ),
        types.Tool(
            name="list_blocks",
            description="List named block definitions available in the current drawing",
            input_schema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="insert_block",
            description="Insert a block reference by name at a position with scale and rotation",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Block definition name"},
                    "position": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Insertion point [x, y] or [x, y, z]",
                    },
                    "scale": {"type": "number", "default": 1.0},
                    "rotation": {
                        "type": "number",
                        "description": "Rotation in degrees",
                        "default": 0.0,
                    },
                    "layer": {
                        "type": "string",
                        "description": "Layer for the inserted reference (optional)",
                    },
                },
                "required": ["name", "position"],
            },
        ),
        types.Tool(
            name="explode_entities",
            description=(
                "Explode block references (by handle) into primitive entities; the original "
                "reference is deleted."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "handles": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Handles of block references to explode",
                    }
                },
                "required": ["handles"],
            },
        ),
        types.Tool(
            name="create_block",
            description=(
                "Create (or redefine) a block definition from existing entities given by handle. "
                "Entities are copied into the definition; optionally delete the originals."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Block definition name"},
                    "handles": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Handles of the entities to include in the block",
                    },
                    "base_point": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Block base/insertion point [x, y] (default 0,0)",
                    },
                    "delete_source": {
                        "type": "boolean",
                        "description": "Delete the original entities after creating the block",
                        "default": False,
                    },
                },
                "required": ["name", "handles"],
            },
        ),
        types.Tool(
            name="create_wall",
            description=(
                "Draw a wall as a closed outline polyline with a real thickness, offset from a "
                "centerline path (mitred joins). Ideal for A-MUROS-CARGA / A-MUROS-TABIQ."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "centerline": {
                        "type": "array",
                        "description": "Centerline vertices [[x, y], ...]",
                        "items": {"type": "array", "items": {"type": "number"}},
                    },
                    "thickness": {
                        "type": "number",
                        "description": "Wall thickness in drawing units (meters)",
                        "default": 0.15,
                    },
                    "closed": {
                        "type": "boolean",
                        "description": "Treat the centerline as a closed loop (ring wall)",
                        "default": False,
                    },
                    "color": {"type": "string", "default": "bylayer"},
                },
                "required": ["centerline"],
            },
        ),
        types.Tool(
            name="create_hatch",
            description=(
                "Fill one or more closed outlines (given by entity handles) with a predefined hatch "
                "pattern. Use 'SOLID' for wall poche or 'ANSI31' for hatching. Ideal for cut walls."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "handles": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Entity handles that form a closed loop (e.g. a wall polyline)",
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Predefined pattern (SOLID, ANSI31, ANSI37, AR-CONC, ...)",
                        "default": "SOLID",
                    },
                    "scale": {"type": "number", "default": 1.0},
                    "angle": {"type": "number", "default": 0.0},
                    "layer": {"type": "string", "default": "A-MUROS-CARGA"},
                    "color": {"type": "string", "default": "bylayer"},
                    "transparency": {
                        "type": "string",
                        "description": "Optional transparency: 'ByLayer' or a percent 0-90 (e.g. '50')",
                    },
                },
                "required": ["handles"],
            },
        ),
        types.Tool(
            name="create_table",
            description=(
                "Insert a native AutoCAD table (AcDbTable) and fill its cells with 'data' "
                "(list of rows). Use for the area table (cuadro de areas), legends and title "
                "blocks. Native tables are editable and can be linked/exported to Excel."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "data": {
                        "type": "array",
                        "description": "Rows of cell values: [[header...], [row...], ...]",
                        "items": {"type": "array", "items": {"type": ["string", "number"]}},
                    },
                    "position": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Insertion point of the top-left corner [x, y]",
                    },
                    "row_height": {"type": "number", "default": 0.4},
                    "col_width": {"type": "number", "default": 2.0},
                    "col_widths": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Optional per-column widths (overrides col_width per column)",
                    },
                    "title": {
                        "type": "string",
                        "description": "Optional title row added above 'data'",
                    },
                    "layer": {"type": "string", "default": "A-TEXTOS"},
                    "text_height": {"type": "number", "default": 0.18},
                },
                "required": ["data"],
            },
        ),
        types.Tool(
            name="list_layouts",
            description="List paper space layouts (tabs) with their plot style table and active flag",
            input_schema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="create_layout",
            description="Create a paper space layout (tab), optionally set paper size and plot style table",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "media": {
                        "type": "string",
                        "description": "Canonical media name (e.g. 'ISO_A4_(210.00_x_297.00_MM)')",
                    },
                    "plot_style_table": {
                        "type": "string",
                        "description": "Plot style table that already exists (e.g. 'acad.ctb')",
                    },
                },
                "required": ["name"],
            },
        ),
        types.Tool(
            name="set_active_layout",
            description="Activate a layout by name and switch to paper space",
            input_schema={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        ),
        types.Tool(
            name="create_viewport",
            description=(
                "Create a paper space viewport in a layout, with an optional scale "
                "(1:50 -> 0.02) and model view center."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "layout_name": {"type": "string"},
                    "center": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Viewport center in paper space [x, y]",
                    },
                    "width": {"type": "number"},
                    "height": {"type": "number"},
                    "scale": {
                        "type": "number",
                        "description": "Custom scale factor (e.g. 0.02 for 1:50)",
                    },
                    "view_center": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Model space point to center the view on [x, y]",
                    },
                    "locked": {"type": "boolean", "default": True},
                },
                "required": ["layout_name", "center", "width", "height"],
            },
        ),
        types.Tool(
            name="create_detail_sheet",
            description=(
                "Create a reusable metal-detail block library (bolts, nuts, washers, "
                "IPE/HEB sections, base plates, gussets, elastomeric bearings, cable "
                "clamps, anchor bolts, splices, stiffeners) and compose a printable "
                "A1 detail sheet layout with title block and 1:1 viewport."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "layout_name": {
                        "type": "string",
                        "description": "Paper-space tab to create/replace",
                        "default": "DETALLES-ACERO",
                    },
                    "origin": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Model-space grid origin [x, y] in mm (default 20000, 0)",
                    },
                    "include_dimensions": {
                        "type": "boolean",
                        "description": "Draw associative dimensions around each detail",
                        "default": True,
                    },
                },
                "required": [],
            },
        ),
        types.Tool(
            name="set_plot_style_table",
            description=(
                "Assign an existing plot style table (.ctb/.stb) to a layout. The file itself "
                "cannot be created via COM; it must already exist in AutoCAD."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "layout_name": {"type": "string"},
                    "table": {
                        "type": "string",
                        "description": "e.g. 'acad.ctb' or 'monochrome.ctb'",
                    },
                },
                "required": ["layout_name", "table"],
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
        types.Tool(
            name="create_box_solid",
            description=(
                "Crea una caja 3D (AcDb3dSolid) centrada en 'center'. "
                "Usa create_box_between para cajas rotadas o inclinadas."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "center": {"type": "array", "items": {"type": "number"}, "minItems": 2},
                    "length": {"type": "number", "description": "Dimension en X (m)"},
                    "width": {"type": "number", "description": "Dimension en Y (m)"},
                    "height": {"type": "number", "description": "Dimension en Z (m)"},
                    "layer": {"type": "string", "default": "S-ESTRUCTURA"},
                    "color": {"type": "string", "default": "bylayer"},
                    "rotation": {
                        "type": "number",
                        "description": "Rotacion sobre Z en grados",
                        "default": 0.0,
                    },
                },
                "required": ["center", "length", "width", "height"],
            },
        ),
        types.Tool(
            name="create_box_between",
            description=(
                "Caja 3D alineada entre dos puntos (diagonales de arriostramiento, "
                "segmentos de arco, montantes inclinados)."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "start": {"type": "array", "items": {"type": "number"}, "minItems": 2},
                    "end": {"type": "array", "items": {"type": "number"}, "minItems": 2},
                    "width": {"type": "number", "description": "Seccion transversal en Y (m)"},
                    "depth": {"type": "number", "description": "Seccion transversal en Z (m)"},
                    "layer": {"type": "string", "default": "S-ESTRUCTURA"},
                    "color": {"type": "string", "default": "bylayer"},
                },
                "required": ["start", "end", "width", "depth"],
            },
        ),
        types.Tool(
            name="create_cylinder_solid",
            description="Crea un cilindro 3D vertical (eje +Z) centrado en 'center'",
            input_schema={
                "type": "object",
                "properties": {
                    "center": {"type": "array", "items": {"type": "number"}, "minItems": 2},
                    "radius": {"type": "number"},
                    "height": {"type": "number"},
                    "layer": {"type": "string", "default": "S-ESTRUCTURA"},
                    "color": {"type": "string", "default": "bylayer"},
                },
                "required": ["center", "radius", "height"],
            },
        ),
        types.Tool(
            name="create_cylinder_between",
            description=(
                "Cilindro 3D entre dos puntos: cables, suspensores, tirantes, barras de celosia."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "start": {"type": "array", "items": {"type": "number"}, "minItems": 2},
                    "end": {"type": "array", "items": {"type": "number"}, "minItems": 2},
                    "radius": {"type": "number"},
                    "layer": {"type": "string", "default": "S-ESTRUCTURA"},
                    "color": {"type": "string", "default": "bylayer"},
                },
                "required": ["start", "end", "radius"],
            },
        ),
        types.Tool(
            name="create_sphere_solid",
            description="Crea una esfera 3D solida",
            input_schema={
                "type": "object",
                "properties": {
                    "center": {"type": "array", "items": {"type": "number"}, "minItems": 2},
                    "radius": {"type": "number"},
                    "layer": {"type": "string", "default": "S-ESTRUCTURA"},
                    "color": {"type": "string", "default": "bylayer"},
                },
                "required": ["center", "radius"],
            },
        ),
        types.Tool(
            name="extrude_polygon",
            description=(
                "Extruye un poligono cerrado (plano XY) en +Z, con angulo de "
                "desmoldeo opcional. Crea el region internamente."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "points": {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "items": {"type": "number"},
                            "minItems": 2,
                            "maxItems": 2,
                        },
                        "minItems": 3,
                    },
                    "height": {"type": "number"},
                    "taper_angle": {
                        "type": "number",
                        "description": "Angulo de desmoldeo en grados",
                        "default": 0.0,
                    },
                    "layer": {"type": "string", "default": "S-ESTRUCTURA"},
                    "color": {"type": "string", "default": "bylayer"},
                },
                "required": ["points", "height"],
            },
        ),
        types.Tool(
            name="boolean_solids",
            description=(
                "Union, interseccion o resta entre dos solidos 3D. En la resta, "
                "el resultado queda en target_handle."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "target_handle": {"type": "string"},
                    "tool_handle": {"type": "string"},
                    "operation": {
                        "type": "string",
                        "enum": ["union", "intersection", "subtraction"],
                        "default": "union",
                    },
                },
                "required": ["target_handle", "tool_handle"],
            },
        ),
        types.Tool(
            name="move_solid",
            description="Desplaza un solido 3D de base_point a destination",
            input_schema={
                "type": "object",
                "properties": {
                    "handle": {"type": "string"},
                    "base_point": {"type": "array", "items": {"type": "number"}, "minItems": 2},
                    "destination": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 2,
                    },
                },
                "required": ["handle", "base_point", "destination"],
            },
        ),
        types.Tool(
            name="rotate_solid",
            description="Rota un solido 3D alrededor de un eje (angulo en grados)",
            input_schema={
                "type": "object",
                "properties": {
                    "handle": {"type": "string"},
                    "axis_point": {"type": "array", "items": {"type": "number"}, "minItems": 2},
                    "axis_direction": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 2,
                    },
                    "angle": {"type": "number"},
                },
                "required": ["handle", "axis_point", "axis_direction", "angle"],
            },
        ),
        types.Tool(
            name="copy_solid",
            description=(
                "Copia un solido 3D una o varias veces. La primera copia queda en "
                "'destination' y las siguientes se separan por el mismo vector."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "handle": {"type": "string"},
                    "destination": {"type": "array", "items": {"type": "number"}, "minItems": 2},
                    "base_point": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 2,
                        "description": "Punto base; por defecto el centro del solido",
                    },
                    "count": {"type": "integer", "minimum": 1, "default": 1},
                    "rotation": {
                        "type": "number",
                        "description": "Giro en Z de cada copia (grados)",
                        "default": 0.0,
                    },
                },
                "required": ["handle", "destination"],
            },
        ),
        types.Tool(
            name="array_solids",
            description="Matriz lineal de copias de un solido separadas por 'offset'.",
            input_schema={
                "type": "object",
                "properties": {
                    "handle": {"type": "string"},
                    "count": {"type": "integer", "minimum": 1},
                    "offset": {"type": "array", "items": {"type": "number"}, "minItems": 2},
                },
                "required": ["handle", "count", "offset"],
            },
        ),
        types.Tool(
            name="scale_solid",
            description="Escala uniforme de un solido 3D respecto a un punto base.",
            input_schema={
                "type": "object",
                "properties": {
                    "handle": {"type": "string"},
                    "base_point": {"type": "array", "items": {"type": "number"}, "minItems": 2},
                    "factor": {"type": "number", "exclusiveMinimum": 0},
                },
                "required": ["handle", "base_point", "factor"],
            },
        ),
        types.Tool(
            name="get_solid_info",
            description=(
                "Resumen de solidos 3D: cantidad, volumen total, volumen por capa "
                "y extents del modelo."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "handles": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Limita el informe a estos handles",
                    },
                    "layer": {"type": "string", "description": "Filtra por capa"},
                    "include_entities": {
                        "type": "boolean",
                        "description": "Incluye el detalle por solido",
                        "default": False,
                    },
                },
                "required": [],
            },
        ),
        types.Tool(
            name="create_bridge",
            description=(
                "Genera un puente 3D completo (girder/arch/cable_stayed/suspension). "
                "Con preset='golden_gate' usa las dimensiones reales del Golden Gate "
                "(2737 m, luz principal 1280 m, torres 227 m). Con detail='bolted' "
                "anade vigas I, placas, rigidizadores, apoyos, herrajes y pernos."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["girder", "arch", "cable_stayed", "suspension"],
                        "default": "girder",
                    },
                    "preset": {"type": "string", "enum": ["golden_gate"]},
                    "name": {"type": "string"},
                    "origin": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 2,
                        "description": "Punto de insercion (centro del puente)",
                    },
                    "total_length": {"type": "number"},
                    "deck_width": {"type": "number"},
                    "deck_depth": {"type": "number"},
                    "clearance": {"type": "number", "description": "Cota del tablero"},
                    "main_span": {"type": "number"},
                    "side_span": {"type": "number"},
                    "tower_height": {"type": "number"},
                    "cable_sag": {"type": "number"},
                    "cable_diameter": {"type": "number"},
                    "suspender_spacing": {"type": "number"},
                    "spans": {"type": "integer", "minimum": 2},
                    "pylons": {"type": "integer", "minimum": 1},
                    "arch_rise": {"type": "number"},
                    "n_approach_piers": {"type": "integer", "minimum": 0},
                    "detail": {
                        "type": "string",
                        "enum": ["none", "members", "bolted"],
                        "default": "none",
                        "description": (
                            "Detalle metalico: none, members (vigas I, placas y "
                            "rigidizadores) o bolted (anade pernos/rivets)"
                        ),
                    },
                    "max_fasteners": {
                        "type": "integer",
                        "minimum": 0,
                        "default": 1200,
                        "description": "Tope de pernos/rivets cuando detail='bolted'",
                    },
                },
                "required": [],
            },
        ),
        types.Tool(
            name="create_cable",
            description=(
                "Crea un cable 3D entre dos puntos con flecha parabolica opcional, "
                "aproximado con cilindros (catenarias, tirantes, suspensores)."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "start": {"type": "array", "items": {"type": "number"}, "minItems": 2},
                    "end": {"type": "array", "items": {"type": "number"}, "minItems": 2},
                    "diameter": {"type": "number", "default": 0.12},
                    "sag": {
                        "type": "number",
                        "description": "Flecha maxima hacia abajo en metros",
                        "default": 0.0,
                    },
                    "samples": {"type": "integer", "minimum": 1, "default": 24},
                    "layer": {"type": "string", "default": "S-CABLES"},
                },
                "required": ["start", "end"],
            },
        ),
        types.Tool(
            name="list_bridge_presets",
            description="Lista las tipologias de puente y los presets con dimensiones reales.",
            input_schema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="get_ftool_status",
            description=(
                "Estado de FTOOL: ruta ejecutable detectada, carpeta de salida y "
                "limitaciones del formato .ftl 4.01."
            ),
            input_schema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="export_ftool_model",
            description=(
                "Exporta el modelo de barras 2D del puente a un archivo .ftl 4.01 de "
                "FTOOL, con material, secciones, apoyos, cargas y la opcion de incluir "
                "una carga puntual. Verifica la ida y vuelta del archivo."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "preset": {"type": "string", "default": "golden_gate"},
                    "path": {"type": "string", "description": "Ruta destino del .ftl"},
                    "load_x": {
                        "type": "number",
                        "description": "Posicion X de la carga puntual (m, centro = 0)",
                        "default": 0.0,
                    },
                    "load_kN": {
                        "type": "number",
                        "description": "Carga puntual vertical en kN (0 = solo peso propio)",
                        "default": 0.0,
                    },
                },
                "required": [],
            },
        ),
        types.Tool(
            name="analyze_bridge_load",
            description=(
                "Resuelve el puente 2D con una carga puntual y devuelve reacciones, "
                "flecha maxima, axiles incrementales de cables y suspensores y el "
                "chequeo de equilibrio. Incluye el estado de peso propio como referencia."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "preset": {"type": "string", "default": "golden_gate"},
                    "x": {
                        "type": "number",
                        "description": "Posicion X de la carga (m, centro = 0)",
                        "default": 0.0,
                    },
                    "magnitude": {
                        "type": "number",
                        "description": "Magnitud de la carga puntual en kN",
                        "default": 1000.0,
                    },
                    "geometric": {
                        "type": "boolean",
                        "description": "Incluye rigidez geometrica (P-Delta)",
                        "default": True,
                    },
                    "tension_only": {
                        "type": "boolean",
                        "description": "Desactiva cables y suspensores comprimidos",
                        "default": True,
                    },
                },
                "required": [],
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
        # standards / axes / dimensions / blocks
        "apply_standard": lambda a: service.standards.apply_standard(
            a.get("dim_text_height", 0.2),
            a.get("dim_arrow_size", 0.12),
        ),
        "create_construction_grid": lambda a: service.grid.create_construction_grid(
            vertical_positions=a.get("vertical_positions"),
            horizontal_positions=a.get("horizontal_positions"),
            bubble_radius=a.get("bubble_radius", 0.45),
            overshoot=a.get("overshoot", 1.0),
            text_height=a.get("text_height", 0.3),
            layer=a.get("layer", "A-EJES"),
            overshoot_bottom=a.get("overshoot_bottom"),
            overshoot_top=a.get("overshoot_top"),
            overshoot_left=a.get("overshoot_left"),
            overshoot_right=a.get("overshoot_right"),
        ),
        "create_dimension": lambda a: service.dimensions.create_dimension(
            a["dim_type"],
            a["points"],
            a.get("dim_line_point"),
            a.get("rotation", 0.0),
            a.get("leader_length", 1.0),
            a.get("layer", "A-COTAS"),
            a.get("style"),
        ),
        "set_dimension_precision": lambda a: service.dimensions.set_dimension_precision(
            a.get("decimals", 3),
            a.get("suppress_trailing_zeros", True),
        ),
        "list_blocks": lambda a: service.blocks.list_blocks(),
        "insert_block": lambda a: service.blocks.insert_block(
            a["name"],
            a["position"],
            a.get("scale", 1.0),
            a.get("rotation", 0.0),
            a.get("layer"),
        ),
        "explode_entities": lambda a: service.blocks.explode_entities(a["handles"]),
        "create_block": lambda a: service.blocks.create_block(
            a["name"],
            a["handles"],
            a.get("base_point"),
            a.get("delete_source", False),
        ),
        "create_wall": lambda a: service.geometry.create_wall(
            a["centerline"],
            a.get("thickness", 0.15),
            a.get("closed", False),
            a.get("color", "bylayer"),
        ),
        "create_hatch": lambda a: service.geometry.create_hatch(
            a["handles"],
            a.get("pattern", "SOLID"),
            a.get("scale", 1.0),
            a.get("angle", 0.0),
            a.get("layer", "A-MUROS-CARGA"),
            a.get("color", "bylayer"),
            a.get("transparency"),
        ),
        "create_table": lambda a: service.tables.create_table(
            a["data"],
            a.get("position"),
            a.get("row_height", 0.4),
            a.get("col_width", 2.0),
            a.get("col_widths"),
            a.get("title"),
            a.get("layer", "A-TEXTOS"),
            a.get("text_height", 0.18),
        ),
        # layouts / paper space / plot styles
        "list_layouts": lambda a: service.layouts.list_layouts(),
        "create_layout": lambda a: service.layouts.create_layout(
            a["name"], a.get("media"), a.get("plot_style_table")
        ),
        "set_active_layout": lambda a: service.layouts.set_active_layout(a["name"]),
        "create_viewport": lambda a: service.layouts.create_viewport(
            a["layout_name"],
            a["center"],
            a["width"],
            a["height"],
            a.get("scale"),
            a.get("view_center"),
            a.get("locked", True),
        ),
        "create_detail_sheet": lambda a: service.detail_sheet.create_detail_sheet(
            a.get("layout_name", "DETALLES-ACERO"),
            a.get("origin"),
            a.get("include_dimensions", True),
        ),
        "set_plot_style_table": lambda a: service.layouts.set_plot_style_table(
            a["layout_name"], a["table"]
        ),
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
        # 3D solids
        "create_box_solid": lambda a: service.solids.create_box_solid(
            a["center"],
            a["length"],
            a["width"],
            a["height"],
            a.get("layer", "S-ESTRUCTURA"),
            a.get("color", "bylayer"),
            a.get("rotation", 0.0),
        ),
        "create_box_between": lambda a: service.solids.create_box_between(
            a["start"],
            a["end"],
            a["width"],
            a["depth"],
            a.get("layer", "S-ESTRUCTURA"),
            a.get("color", "bylayer"),
        ),
        "create_cylinder_solid": lambda a: service.solids.create_cylinder_solid(
            a["center"],
            a["radius"],
            a["height"],
            a.get("layer", "S-ESTRUCTURA"),
            a.get("color", "bylayer"),
        ),
        "create_cylinder_between": lambda a: service.solids.create_cylinder_between(
            a["start"],
            a["end"],
            a["radius"],
            a.get("layer", "S-ESTRUCTURA"),
            a.get("color", "bylayer"),
        ),
        "create_sphere_solid": lambda a: service.solids.create_sphere_solid(
            a["center"],
            a["radius"],
            a.get("layer", "S-ESTRUCTURA"),
            a.get("color", "bylayer"),
        ),
        "extrude_polygon": lambda a: service.solids.extrude_polygon(
            a["points"],
            a["height"],
            a.get("taper_angle", 0.0),
            a.get("layer", "S-ESTRUCTURA"),
            a.get("color", "bylayer"),
        ),
        "boolean_solids": lambda a: service.solids.boolean_solids(
            a["target_handle"],
            a["tool_handle"],
            a.get("operation", "union"),
        ),
        "move_solid": lambda a: service.solids.move_solid(
            a["handle"], a["base_point"], a["destination"]
        ),
        "rotate_solid": lambda a: service.solids.rotate_solid(
            a["handle"], a["axis_point"], a["axis_direction"], a["angle"]
        ),
        "scale_solid": lambda a: service.solids.scale_solid(
            a["handle"], a["base_point"], a["factor"]
        ),
        "copy_solid": lambda a: service.solids.copy_solid(
            a["handle"],
            a["destination"],
            a.get("base_point"),
            a.get("count", 1),
            a.get("rotation", 0.0),
        ),
        "array_solids": lambda a: service.solids.array_solids(a["handle"], a["count"], a["offset"]),
        "get_solid_info": lambda a: service.solids.get_solid_info(
            a.get("handles"),
            a.get("layer"),
            a.get("include_entities", False),
        ),
        # bridges
        "create_bridge": lambda a: service.bridges.create_bridge(
            a.get("kind"),
            a.get("preset"),
            a.get("name"),
            a.get("origin"),
            a.get("total_length"),
            a.get("deck_width"),
            a.get("deck_depth"),
            a.get("clearance"),
            a.get("main_span"),
            a.get("side_span"),
            a.get("tower_height"),
            a.get("cable_sag"),
            a.get("cable_diameter"),
            a.get("suspender_spacing"),
            a.get("spans"),
            a.get("pylons"),
            a.get("arch_rise"),
            a.get("n_approach_piers"),
            a.get("detail"),
            a.get("max_fasteners"),
        ),
        "create_cable": lambda a: service.bridges.create_cable(
            a["start"],
            a["end"],
            a.get("diameter", 0.12),
            a.get("sag", 0.0),
            a.get("samples", 24),
            a.get("layer"),
        ),
        "list_bridge_presets": lambda a: service.bridges.list_bridge_presets(),
        # ftool (analisis estructural 2D)
        "get_ftool_status": lambda a: service.ftool.status(),
        "export_ftool_model": lambda a: service.ftool.export_model(
            a.get("preset", "golden_gate"),
            a.get("path"),
            a.get("load_x", 0.0),
            a.get("load_kN", 0.0),
        ),
        "analyze_bridge_load": lambda a: service.ftool.analyze_load(
            a.get("preset", "golden_gate"),
            a.get("x", 0.0),
            a.get("magnitude", 1000.0),
            a.get("geometric", True),
            a.get("tension_only", True),
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
