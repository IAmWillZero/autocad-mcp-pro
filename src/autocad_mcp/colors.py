"""Mapeo de nombres de color a indices ACI (AutoCAD Color Index)."""

from __future__ import annotations

ACI_COLORS: dict[str, int] = {
    "red": 1,
    "yellow": 2,
    "green": 3,
    "cyan": 4,
    "blue": 5,
    "magenta": 6,
    "white": 7,
    "gray": 8,
    "grey": 8,
    "light_gray": 9,
    "light_grey": 9,
    "black": 0,
    "bylayer": 256,
    "byblock": 0,
}

DEFAULT_COLOR_INDEX = 7  # blanco/negro


def color_index(color: str | int) -> int:
    """Convierte un nombre de color (o un ACI ya numerico) a indice ACI."""
    if isinstance(color, int):
        return color
    return ACI_COLORS.get(str(color).strip().lower(), DEFAULT_COLOR_INDEX)
