"""Smoke test de las herramientas CAD contra AutoCAD REAL.

Requiere Windows + AutoCAD abierto con un dibujo cargado. NO lo ejecuta pytest
(el nombre no empieza por ``test_``); se lanza a mano:

    python tests/smoke_test.py

Crea entidades, las lee de vuelta con ``get_entities`` y reporta PASS/FAIL por caso.
Al terminar limpia el dibujo (borra todo lo que creo).
"""

from __future__ import annotations

import sys

from autocad_mcp.service import AutoCADService

_results: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    _results.append((name, condition, detail))
    mark = "PASS" if condition else "FAIL"
    print(f"[{mark}] {name} {detail}".rstrip())


def types_of(service: AutoCADService) -> list[str]:
    data = service.info.get_entities()
    if "error" in data:
        return []
    return [e["type"] for e in data.get("entities", [])]


def main() -> int:
    service = AutoCADService()

    print("Conectando a AutoCAD...")
    if not service.connect():
        print("ERROR: no se pudo conectar. ¿Está AutoCAD abierto con un dibujo?")
        return 2

    print(f"Documento: {service.conn.document_name()}")

    # --- documentos abiertos ---
    docs = service.documents.list_documents()
    check("list_documents success", bool(docs.get("success")))
    check("list_documents devuelve >=1 dibujo", docs.get("count", 0) >= 1)

    # Limpieza inicial
    service.deleter.delete_all_entities(confirm=True)
    check("limpieza inicial (0 entidades)", service.info.get_entities()["returned_count"] == 0)

    # --- create_line ---
    line = service.geometry.create_line([0, 0], [10, 0], "red")
    check("create_line success", bool(line.get("success")))
    check("create_line aparece en get_entities", "AcDbLine" in types_of(service))

    # --- create_circle ---
    circle = service.geometry.create_circle([5, 5], 2.5, "blue")
    check("create_circle success", bool(circle.get("success")))
    check("create_circle aparece", "AcDbCircle" in types_of(service))

    # --- create_rectangle (polilinea cerrada) ---
    rect = service.geometry.create_rectangle([0, 0], [20, 10], "green")
    check("create_rectangle success", bool(rect.get("success")))
    check("create_rectangle crea 1 polilinea", len(rect.get("handles", [])) == 1)

    # --- create_polyline ---
    poly = service.geometry.create_polyline([[0, 0], [5, 0], [5, 5]], closed=True, color="yellow")
    check("create_polyline success", bool(poly.get("success")))
    check("create_polyline aparece", "AcDbPolyline" in types_of(service))

    # --- create_text ---
    text = service.geometry.create_text([1, 1], "HOLA", 1.0, "white")
    check("create_text success", bool(text.get("success")))
    check("create_text aparece", "AcDbText" in types_of(service))

    # --- create_arc ---
    arc = service.geometry.create_arc([0, 0], 5, 0, 90, "cyan")
    check("create_arc success", bool(arc.get("success")))
    check("create_arc aparece", "AcDbArc" in types_of(service))

    # --- create_structure (capa automatica) ---
    wall = service.structures.create_structure(
        "wall", {"start": [0, 0], "end": [0, 20]}, label="M1"
    )
    check("create_structure success", bool(wall.get("success")))
    check("create_structure usa capa A-MUROS-CARGA", wall.get("layer") == "A-MUROS-CARGA")

    # --- invalidacion de cache (fix Camino A) ---
    before = service.info.get_entities()["returned_count"]
    service.geometry.create_circle([50, 50], 1.0, "magenta")
    after = service.info.get_entities()["returned_count"]
    check("cache se invalida al crear", after == before + 1, f"({before} -> {after})")

    # --- delete por handle ---
    handle = circle.get("handles", [None])[0]
    if handle:
        deleted = service.deleter.delete_entity_by_handle(handle)
        check("delete_entity_by_handle success", bool(deleted.get("success")))
        check("la entidad borrada desaparece", handle not in _handles(service))
    else:
        check("delete_entity_by_handle (sin handle)", False)

    # --- drawing info ---
    info = service.info.get_drawing_info()
    check("get_drawing_info", "error" not in info)

    # --- analyze_drawing (informe + verificacion de cotas) ---
    from autocad_mcp.com import variant_point

    ms = service.conn.model_space()
    ms.AddDimAligned(variant_point(0, 0), variant_point(10, 0), variant_point(5, -3))
    report = service.analysis.analyze_drawing(include_entities=True)
    check("analyze_drawing success", bool(report.get("success")))
    check("analyze resumen por tipo", report["summary"]["counts_by_type"].get("AcDbLine", 0) >= 1)
    check("analyze extents > 0", report["extents"]["width"] > 0)
    check("analyze detecta cotas", len(report.get("dimensions", [])) >= 1)
    check(
        "analyze: la cota mide ~10",
        any(abs((d.get("measurement") or 0) - 10.0) < 0.01 for d in report.get("dimensions", [])),
    )
    check("analyze incluye geometria", any("geometry" in e for e in report.get("entities", [])))

    # --- apply_standard (capas A- + unidades + estilo de cotas) ---
    std = service.standards.apply_standard()
    check("apply_standard success", bool(std.get("success")))
    check("apply_standard define capas A-", "A-MUROS-CARGA" in std.get("layers", []))
    check("apply_standard estilo de cotas", std.get("dim_style") == "MCP-ARQ")

    # --- create_construction_grid ---
    grid = service.grid.create_construction_grid([0, 5], [0, 4])
    check("create_construction_grid success", bool(grid.get("success")))
    check("create_construction_grid crea entidades", grid.get("entities_created", 0) > 0)

    # --- create_dimension ---
    dim = service.dimensions.create_dimension(
        "rotated", [[0, 0], [5, 0]], [2.5, -2], layer="A-COTAS", style="MCP-ARQ"
    )
    check("create_dimension success", bool(dim.get("success")))
    check("create_dimension mide ~5", abs((dim.get("measurement") or 0) - 5.0) < 0.01)

    # --- bloques: definicion (COM) + list + insert + explode ---
    doc = service.conn.doc
    blk = doc.Blocks.Add(variant_point(0, 0), "SMOKE-BLOCK")
    blk.AddLine(variant_point(0, 0), variant_point(1, 1))
    listing = service.blocks.list_blocks()
    check("list_blocks success", bool(listing.get("success")))
    check(
        "list_blocks incluye bloque definido",
        any(b["name"] == "SMOKE-BLOCK" for b in listing.get("blocks", [])),
    )
    insertion = service.blocks.insert_block("SMOKE-BLOCK", [50, 50])
    check("insert_block success", bool(insertion.get("success")))
    exploded = service.blocks.explode_entities([insertion.get("handle", "")])
    check(
        "explode_entities success",
        bool(exploded.get("success")) and exploded.get("exploded_count") == 1,
    )

    # --- create_wall (polilinea de contorno con espesor real) ---
    wall = service.geometry.create_wall([[0, 30], [5, 30]], thickness=0.15, color="bylayer")
    check("create_wall success", bool(wall.get("success")))
    check("create_wall crea 1 polilinea", len(wall.get("handles", [])) == 1)

    # --- create_block desde handles (con borrado de originales) ---
    l1 = service.geometry.create_line([80, 80], [81, 81], "bylayer")
    l2 = service.geometry.create_line([81, 80], [80, 81], "bylayer")
    made = service.blocks.create_block(
        "SMOKE-DEF",
        [l1["handles"][0], l2["handles"][0]],
        delete_source=True,
    )
    check("create_block success", bool(made.get("success")) and made.get("entities") == 2)
    listing2 = service.blocks.list_blocks()
    check(
        "create_block aparece en list_blocks",
        any(b["name"] == "SMOKE-DEF" for b in listing2.get("blocks", [])),
    )

    # --- layouts / paper space / plot styles ---
    laylist = service.layouts.list_layouts()
    check("list_layouts success", bool(laylist.get("success")))
    check(
        "list_layouts incluye Model",
        any(lay["name"] == "Model" for lay in laylist.get("layouts", [])),
    )
    made_layout = service.layouts.create_layout("MCP-TEST", plot_style_table="acad.ctb")
    check("create_layout success", bool(made_layout.get("success")))
    viewport = service.layouts.create_viewport(
        "MCP-TEST", [100, 100], 150, 100, scale=0.02, view_center=[0, 0]
    )
    check("create_viewport success", bool(viewport.get("success")))
    plot = service.layouts.set_plot_style_table("MCP-TEST", "monochrome.ctb")
    check("set_plot_style_table success", bool(plot.get("success")))
    back = service.layouts.set_active_layout("Model")
    check("set_active_layout Model", bool(back.get("success")))

    # Limpieza final
    service.deleter.delete_all_entities(confirm=True)

    passed = sum(1 for _, ok, _ in _results if ok)
    total = len(_results)
    print(f"\n{passed}/{total} checks PASS")
    return 0 if passed == total else 1


def _handles(service: AutoCADService) -> set[str]:
    data = service.info.get_entities()
    return {e["handle"] for e in data.get("entities", [])}


if __name__ == "__main__":
    sys.exit(main())
