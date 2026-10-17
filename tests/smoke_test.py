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
    check("create_structure usa capa WALLS", wall.get("layer") == "WALLS")

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
