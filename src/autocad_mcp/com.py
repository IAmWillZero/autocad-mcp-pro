"""Utilidades de bajo nivel para construir VARIANTs COM de pywin32.

Unico punto (junto con :mod:`autocad_mcp.connection`) que importa pywin32/pythoncom.
"""

from __future__ import annotations

from typing import Any

import pythoncom
import win32com.client


def variant_point(x: float, y: float, z: float = 0.0) -> Any:
    """Crea un VARIANT de punto SAFEARRAY (VT_R8) para COM."""
    return win32com.client.VARIANT(
        pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(x), float(y), float(z)]
    )


def variant_array(flat_coords: list[float]) -> Any:
    """Crea un VARIANT SAFEARRAY (VT_R8) a partir de una lista plana de floats."""
    return win32com.client.VARIANT(
        pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(c) for c in flat_coords]
    )
