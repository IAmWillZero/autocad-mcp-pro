"""Tests del mapeo de colores ACI."""

from __future__ import annotations

from autocad_mcp.colors import DEFAULT_COLOR_INDEX, color_index


def test_named_colors() -> None:
    assert color_index("red") == 1
    assert color_index("BLUE") == 5
    assert color_index("white") == 7


def test_int_passthrough() -> None:
    assert color_index(42) == 42


def test_unknown_defaults() -> None:
    assert color_index("not-a-color") == DEFAULT_COLOR_INDEX
