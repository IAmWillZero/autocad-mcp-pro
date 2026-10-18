"""Tests del estandar de dibujo (datos puros, sin AutoCAD)."""

from __future__ import annotations

from autocad_mcp.standards import (
    DIM_VARIABLES,
    STANDARD_LAYERS,
    axis_letter_label,
    axis_number_label,
)


def test_layer_names_use_discipline_prefix() -> None:
    assert STANDARD_LAYERS
    for name in STANDARD_LAYERS:
        assert name.startswith("A-")


def test_lineweights_follow_hierarchy() -> None:
    carga = STANDARD_LAYERS["A-MUROS-CARGA"].lineweight
    tabique = STANDARD_LAYERS["A-MUROS-TABIQ"].lineweight
    carpinteria = STANDARD_LAYERS["A-PUER-VENT"].lineweight
    fino = STANDARD_LAYERS["A-COTAS"].lineweight
    assert carga > tabique > carpinteria > fino


def test_axis_linetype_is_center() -> None:
    assert STANDARD_LAYERS["A-EJES"].linetype == "CENTER"
    assert STANDARD_LAYERS["A-PROYECC"].linetype == "HIDDEN"


def test_dim_variables_scaled_for_meters() -> None:
    assert DIM_VARIABLES["DIMTXT"] == 0.2
    assert DIM_VARIABLES["DIMASZ"] == 0.12
    assert DIM_VARIABLES["DIMSCALE"] == 1.0


def test_dim_variables_limit_decimals() -> None:
    assert DIM_VARIABLES["DIMDEC"] == 3
    assert DIM_VARIABLES["DIMZIN"] == 8


def test_axis_labels() -> None:
    assert axis_number_label(3) == "3"
    assert axis_letter_label(1) == "A"
    assert axis_letter_label(26) == "Z"
    assert axis_letter_label(27) == "AA"
