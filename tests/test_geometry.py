"""Tests de las herramientas de geometria (sin AutoCAD).

Cubren la validacion de patrones del sombreado/poche y la resolucion de
contornos por handle, sin tocar COM.
"""

from __future__ import annotations

from typing import Any

from autocad_mcp.features.geometry import HATCH_PATTERNS, GeometryTools


class _FakeDoc:
    def HandleToObject(self, handle: str) -> Any:  # noqa: ARG002
        raise RuntimeError("handle inexistente")


class _FakeConn:
    def __init__(self) -> None:
        self.doc = _FakeDoc()

    def ensure(self) -> bool:
        return True

    def model_space(self) -> Any:
        raise AssertionError("no deberia tocar el ModelSpace")

    def regen(self) -> None:
        pass


def test_hatch_rejects_unknown_pattern() -> None:
    tools = GeometryTools(_FakeConn())  # type: ignore[arg-type]
    result = tools.create_hatch(["A1"], pattern="NOPE")
    assert result["success"] is False
    assert "NOPE" in result["error"]
    assert "SOLID" in HATCH_PATTERNS


def test_hatch_errors_when_no_loop_entities() -> None:
    tools = GeometryTools(_FakeConn())  # type: ignore[arg-type]
    result = tools.create_hatch(["missing"], pattern="SOLID")
    assert result["success"] is False
    assert "contorno" in result["error"]
