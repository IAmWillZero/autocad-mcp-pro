"""Guard de contrato: nombres de herramientas MCP estables y sin duplicados."""

from __future__ import annotations

from autocad_mcp.tools import list_tool_schemas

# Conjunto de herramientas publicas. Cambiar solo de forma aditiva.
EXPECTED_TOOLS = {
    "get_drawing_info",
    "get_entities",
    "analyze_drawing",
    "apply_standard",
    "create_construction_grid",
    "create_dimension",
    "list_blocks",
    "insert_block",
    "explode_entities",
    "list_documents",
    "set_active_document",
    "create_structure",
    "create_or_get_layer",
    "set_current_layer",
    "create_line",
    "create_circle",
    "create_rectangle",
    "create_polyline",
    "create_text",
    "create_arc",
    "delete_entity_by_handle",
    "delete_entities_by_handles",
    "delete_entities_by_type",
    "delete_entities_by_layer",
    "delete_entities_by_color",
    "delete_entities_by_type_and_color",
    "delete_last_entities",
    "delete_all_entities",
    "undo_last_operation",
    "change_entity_color",
    "zoom_extents",
    "health_check",
    "get_metrics",
    "clear_cache",
    "reload_config",
    "batch_execute",
}


def test_tool_names_are_exactly_expected() -> None:
    names = {tool.name for tool in list_tool_schemas()}
    assert names == EXPECTED_TOOLS


def test_no_duplicate_tool_names() -> None:
    names = [tool.name for tool in list_tool_schemas()]
    assert len(names) == len(set(names))


def test_every_tool_has_object_schema() -> None:
    for tool in list_tool_schemas():
        assert tool.input_schema["type"] == "object"
        assert tool.description
