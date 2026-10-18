"""Tests de la herramienta de cotas (sin AutoCAD).

Cubren la construccion de la secuencia ``DIMOVERRIDE`` que fija la precision
del texto de las cotas (maximo de decimales y supresion de ceros finales).
"""

from __future__ import annotations

from autocad_mcp.features.dimensions import dimoverride_command


def test_dimoverride_sets_decimals_and_suppresses_zeros() -> None:
    cmd = dimoverride_command(3, True)
    assert "DIMDEC" in cmd
    assert "\n3\n" in cmd
    assert "DIMZIN\n8" in cmd
    assert cmd.count("_.") == 1
    assert cmd.endswith("ALL\n\n")


def test_dimoverride_can_keep_trailing_zeros() -> None:
    cmd = dimoverride_command(2, False)
    assert "DIMDEC\n2\n" in cmd
    assert "DIMZIN\n0" in cmd
