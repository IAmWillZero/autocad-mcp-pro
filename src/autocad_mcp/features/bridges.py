"""Puentes en 3D: generador parametrico sobre :mod:`autocad_mcp.features.solids`.

Cuatro tipologias: ``girder`` (viga-losa), ``arch`` (arco), ``cable_stayed``
(atirantado) y ``suspension`` (colgante). Todo se modela a escala real en metros
con solidos ``AcDb3dSolid`` sobre capas ``S-`` (Estructuras).

El preset ``golden_gate`` usa las dimensiones publicas del Golden Gate Bridge:
luz principal 1280 m, vanos laterales 343 m, longitud total 2737 m, torres de
227 m sobre el agua, calado 67 m, tablero de 27.4 m y cables de 0.92 m.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from typing import Any

from autocad_mcp.cache import TTLCache
from autocad_mcp.connection import AutoCADConnection
from autocad_mcp.features.base import FeatureBase
from autocad_mcp.features.solids import SolidTools
from autocad_mcp.layers import BRIDGE_LAYERS

KINDS = ("girder", "arch", "cable_stayed", "suspension")

# Niveles de detalle metalico: sin detalle, solo miembros/placas, o con pernos.
DETAIL_LEVELS = ("none", "members", "bolted")

# Densidades medias (kg/m3) para el desglose por material.
MATERIAL_DENSITIES: dict[str, float] = {
    "hormigon": 2400.0,
    "acero": 7850.0,
    "asfalto": 2400.0,
}

# Material estructural asignado a cada capa S-.
LAYER_MATERIAL: dict[str, str] = {
    "S-TABLERO": "hormigon",
    "S-VIGAS": "acero",
    "S-PILAS": "hormigon",
    "S-TORRES": "acero",
    "S-CABLES": "acero",
    "S-ESTRIBOS": "hormigon",
    "S-ARCO": "acero",
    "S-PAVIMENTO": "asfalto",
    "S-EQUIPAMIENTO": "acero",
    "S-PLACAS": "acero",
    "S-RIGIDIZADORES": "acero",
    "S-PERNOS": "acero",
}

PRESET_DESCRIPTIONS: dict[str, str] = {
    "golden_gate": "Golden Gate Bridge: suspension de 2737 m, luz principal 1280 m, torres 227 m",
}


def material_breakdown(by_layer: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Agrupa volumenes por capa en volumen y masa por material.

    Devuelve ``{material: {density_kg_m3, volume_m3, mass_t, layers}}`` con las
    masas en toneladas metricas (``volumen * densidad / 1000``).
    """
    materials: dict[str, dict[str, Any]] = {}
    for layer, info in by_layer.items():
        material = LAYER_MATERIAL.get(layer, "acero")
        density = MATERIAL_DENSITIES[material]
        volume = float(info.get("volume") or 0.0)
        bucket = materials.setdefault(
            material,
            {
                "density_kg_m3": density,
                "volume_m3": 0.0,
                "mass_t": 0.0,
                "layers": [],
            },
        )
        bucket["volume_m3"] += volume
        bucket["mass_t"] += volume * density / 1000.0
        if layer not in bucket["layers"]:
            bucket["layers"].append(layer)

    for bucket in materials.values():
        bucket["volume_m3"] = round(float(bucket["volume_m3"]), 2)
        bucket["mass_t"] = round(float(bucket["mass_t"]), 2)
        bucket["layers"].sort()
    return dict(sorted(materials.items()))


def cable_points(
    start: list[float],
    end: list[float],
    sag: float = 0.0,
    samples: int = 24,
) -> list[list[float]]:
    """Puntos de un cable entre ``start`` y ``end`` con flecha parabolica.

    ``sag`` es la flecha maxima en metros, medida hacia abajo en Z. Con
    ``sag=0`` el cable es una recta. Se usa para generar los segmentos de
    cilindro que aproximan la catenaria.
    """
    if samples < 1:
        raise ValueError("samples debe ser >= 1")
    if sag < 0:
        raise ValueError("sag no puede ser negativo")
    if len(start) < 2 or len(end) < 2:
        raise ValueError("los puntos requieren al menos x e y")
    sx, sy, sz = _point3(start)
    ex, ey, ez = _point3(end)
    if (sx, sy, sz) == (ex, ey, ez):
        raise ValueError("start y end coinciden")

    points: list[list[float]] = []
    for index in range(samples + 1):
        t = index / samples
        points.append(
            [
                sx + (ex - sx) * t,
                sy + (ey - sy) * t,
                sz + (ez - sz) * t - sag * 4.0 * t * (1.0 - t),
            ]
        )
    return points


def _point3(point: list[float]) -> tuple[float, float, float]:
    z = float(point[2]) if len(point) > 2 else 0.0
    return float(point[0]), float(point[1]), z


def _distance(start: list[float], end: list[float]) -> float:
    dx = float(end[0]) - float(start[0])
    dy = float(end[1]) - float(start[1])
    dz = _point3(end)[2] - _point3(start)[2]
    return float((dx * dx + dy * dy + dz * dz) ** 0.5)


# Preset con dimensiones reales documentadas (metros).
PRESETS: dict[str, dict[str, Any]] = {
    "golden_gate": {
        "kind": "suspension",
        "name": "GOLDEN GATE",
        "total_length": 2737.0,
        "deck_width": 27.4,
        "deck_depth": 7.6,
        "clearance": 67.0,
        "main_span": 1280.0,
        "side_span": 343.0,
        "tower_height": 227.0,
        "cable_sag": 143.0,
        "cable_diameter": 0.92,
        "suspender_spacing": 15.24,
        "n_approach_piers": 7,
    },
}


@dataclass(frozen=True)
class BridgeSpec:
    """Dimensiones de un puente, en metros, con el origen en el centro."""

    kind: str = "girder"
    name: str = "PUENTE"
    total_length: float = 300.0
    deck_width: float = 12.0
    deck_depth: float = 1.5
    clearance: float = 8.0
    main_span: float = 200.0
    side_span: float = 50.0
    tower_height: float = 60.0
    cable_sag: float = 22.0
    cable_diameter: float = 0.35
    suspender_spacing: float = 10.0
    spans: int = 3
    pylons: int = 2
    arch_rise: float = 30.0
    n_approach_piers: int = 7
    detail: str = "none"
    max_fasteners: int = 1200
    origin: tuple[float, float, float] = (0.0, 0.0, 0.0)

    @property
    def deck_top(self) -> float:
        return self.clearance + self.deck_depth

    def validate(self) -> str | None:
        """Devuelve un mensaje de error o ``None`` si la geometria es coherente."""
        if self.kind not in KINDS:
            return f"kind invalido '{self.kind}' (usa {', '.join(KINDS)})"
        if self.detail not in DETAIL_LEVELS:
            return f"detail invalido '{self.detail}' (usa {', '.join(DETAIL_LEVELS)})"
        if self.max_fasteners < 0:
            return "max_fasteners no puede ser negativo"
        if self.total_length <= 0:
            return "total_length debe ser > 0"
        if self.deck_width <= 0 or self.deck_depth <= 0:
            return "deck_width y deck_depth deben ser > 0"
        if self.clearance < 0:
            return "clearance no puede ser negativo"
        if self.kind == "suspension":
            if self.main_span <= 0 or self.side_span < 0:
                return "main_span debe ser > 0 y side_span >= 0"
            if self.main_span + 2 * self.side_span > self.total_length:
                return "main_span + 2*side_span excede total_length"
            if self.tower_height <= self.deck_top:
                return "tower_height debe superar la cota del tablero"
            available = self.tower_height - self.deck_top
            if self.cable_sag <= 0 or self.cable_sag >= available:
                return "cable_sag fuera de rango (0 < sag < altura de torre - tablero)"
            if self.cable_diameter <= 0 or self.suspender_spacing <= 0:
                return "cable_diameter y suspender_spacing deben ser > 0"
        if self.kind == "arch" and self.arch_rise <= 0:
            return "arch_rise debe ser > 0"
        if self.kind == "cable_stayed" and self.pylons < 1:
            return "pylons debe ser >= 1"
        if self.kind == "girder" and self.spans < 2:
            return "spans debe ser >= 2"
        return None


@dataclass
class BridgeResult:
    """Acumulador de solidos creados durante el armado."""

    handles: list[str] = field(default_factory=list)
    volume: float = 0.0

    def add(self, result: dict[str, Any]) -> None:
        if result.get("success"):
            self.handles.extend(result.get("handles", []))
            self.volume += float(result.get("volume") or 0.0)


class BridgeTools(FeatureBase):
    """Genera puentes 3D completos combinando solidos."""

    def __init__(
        self,
        conn: AutoCADConnection,
        cache: TTLCache | None = None,
        solids: SolidTools | None = None,
    ) -> None:
        super().__init__(conn, cache)
        self.solids = solids or SolidTools(conn, cache)
        self._off = (0.0, 0.0, 0.0)
        self._built = BridgeResult()
        self._fasteners = 0
        self._fastener_cap = 0

    # --- API -------------------------------------------------------------
    def create_bridge(
        self,
        kind: str | None = None,
        preset: str | None = None,
        name: str | None = None,
        origin: list[float] | None = None,
        total_length: float | None = None,
        deck_width: float | None = None,
        deck_depth: float | None = None,
        clearance: float | None = None,
        main_span: float | None = None,
        side_span: float | None = None,
        tower_height: float | None = None,
        cable_sag: float | None = None,
        cable_diameter: float | None = None,
        suspender_spacing: float | None = None,
        spans: int | None = None,
        pylons: int | None = None,
        arch_rise: float | None = None,
        n_approach_piers: int | None = None,
        detail: str | None = None,
        max_fasteners: int | None = None,
    ) -> dict[str, Any]:
        """Crea un puente 3D.

        ``preset`` aporta dimensiones reales y los demas argumentos las
        sobrescriben (todos opcionales). ``detail`` anade el detalle metalico
        (``members``: vigas I, placas y rigidizadores; ``bolted``: ademas
        pernos/rivets hasta ``max_fasteners``).
        """
        if not self.conn.ensure():
            return {"success": False, "error": "Not connected to AutoCAD"}
        if preset and preset not in PRESETS:
            return {"success": False, "error": f"preset desconocido '{preset}'"}

        spec = self._build_spec(
            kind=kind,
            preset=preset,
            name=name,
            origin=origin,
            total_length=total_length,
            deck_width=deck_width,
            deck_depth=deck_depth,
            clearance=clearance,
            main_span=main_span,
            side_span=side_span,
            tower_height=tower_height,
            cable_sag=cable_sag,
            cable_diameter=cable_diameter,
            suspender_spacing=suspender_spacing,
            spans=spans,
            pylons=pylons,
            arch_rise=arch_rise,
            n_approach_piers=n_approach_piers,
            detail=detail,
            max_fasteners=max_fasteners,
        )
        error = spec.validate()
        if error is not None:
            return {"success": False, "error": error}

        self._off = spec.origin
        self._built = BridgeResult()
        self._fasteners = 0
        self._fastener_cap = spec.max_fasteners
        self._ensure_layers()

        with self.solids.batch():
            if spec.kind == "suspension":
                self._build_suspension(spec)
            elif spec.kind == "cable_stayed":
                self._build_cable_stayed(spec)
            elif spec.kind == "arch":
                self._build_arch(spec)
            else:
                self._build_girder(spec)

        report = self._solid_report()
        by_layer = report.get("by_layer") or {}
        materials = material_breakdown(by_layer)
        return {
            "success": True,
            "bridge": spec.name,
            "kind": spec.kind,
            "solids": len(self._built.handles),
            "handles": self._built.handles,
            "volume": round(self._built.volume, 2),
            "mass": round(sum(float(m["mass_t"]) for m in materials.values()), 2),
            "materials": materials,
            "extents": report.get("extents"),
            "by_layer": by_layer,
            "detail": spec.detail,
            "fasteners": self._fasteners,
            "spec": {
                "total_length": spec.total_length,
                "deck_width": spec.deck_width,
                "deck_depth": spec.deck_depth,
                "clearance": spec.clearance,
                "main_span": spec.main_span,
                "side_span": spec.side_span,
                "tower_height": spec.tower_height,
                "cable_sag": spec.cable_sag,
                "cable_diameter": spec.cable_diameter,
                "suspender_spacing": spec.suspender_spacing,
                "detail": spec.detail,
                "max_fasteners": spec.max_fasteners,
            },
        }

    def _solid_report(self) -> dict[str, Any]:
        """Lee el resumen del modelo, reintentando si AutoCAD aun esta ocupado."""
        report: dict[str, Any] = {"success": False, "error": "sin lectura"}
        for attempt in range(3):
            report = self.solids.get_solid_info(handles=self._built.handles)
            by_layer = report.get("by_layer") or {}
            if report.get("success") and "" not in by_layer:
                return report
            time.sleep(1.0 * (attempt + 1))
        return report

    def list_bridge_presets(self) -> dict[str, Any]:
        """Catalogo de presets y tipologias disponibles (sin tocar AutoCAD)."""
        return {
            "success": True,
            "kinds": list(KINDS),
            "presets": [
                {
                    "preset": key,
                    "description": PRESET_DESCRIPTIONS.get(key, ""),
                    **values,
                }
                for key, values in PRESETS.items()
            ],
        }

    def create_cable(
        self,
        start: list[float],
        end: list[float],
        diameter: float = 0.12,
        sag: float = 0.0,
        samples: int = 24,
        layer: str | None = None,
    ) -> dict[str, Any]:
        """Crea un cable 3D entre dos puntos, con flecha parabolica opcional.

        Se aproxima con cilindros entre puntos (``samples`` segmentos): es la
        misma tecnica que usan los puentes colgantes para las catenarias.
        """
        if not self.conn.ensure():
            return {"success": False, "error": "Not connected to AutoCAD"}
        if diameter <= 0:
            return {"success": False, "error": "diameter debe ser > 0"}
        layer = layer or self._layer("cable")
        try:
            points = cable_points(start, end, sag, samples)
        except ValueError as exc:
            return {"success": False, "error": str(exc)}

        handles: list[str] = []
        volume = 0.0
        length = 0.0
        radius = diameter / 2.0
        for index in range(len(points) - 1):
            p0, p1 = points[index], points[index + 1]
            length += _distance(p0, p1)
            result = self.solids.create_cylinder_between(p0, p1, radius, layer)
            if not result.get("success"):
                return {
                    "success": False,
                    "error": result.get("error", "no se pudo crear el cable"),
                    "handles": handles,
                }
            handles.extend(result.get("handles", []))
            volume += float(result.get("volume") or 0.0)

        return {
            "success": bool(handles),
            "handles": handles,
            "segments": len(handles),
            "length": round(length, 3),
            "volume": round(volume, 6),
            "diameter": diameter,
            "sag": sag,
            "layer": layer,
            "points": points,
        }

    # --- especificacion --------------------------------------------------
    def _build_spec(self, **kwargs: Any) -> BridgeSpec:
        preset = kwargs.pop("preset", None)
        spec = BridgeSpec(**PRESETS[preset]) if preset else BridgeSpec()
        changes: dict[str, Any] = {}
        changes = {k: v for k, v in kwargs.items() if v is not None and hasattr(spec, k)}
        return replace(spec, **changes) if changes else spec

    def _ensure_layers(self) -> None:
        for info in BRIDGE_LAYERS.values():
            self.solids.layer_tools.create_or_get_layer(
                info["name"], info["color"], info["description"]
            )

    # --- helpers de geometria -------------------------------------------
    def _box(
        self,
        x0: float,
        x1: float,
        y0: float,
        y1: float,
        z0: float,
        z1: float,
        layer: str,
    ) -> dict[str, Any]:
        ox, oy, oz = self._off
        center = [(x0 + x1) / 2 + ox, (y0 + y1) / 2 + oy, (z0 + z1) / 2 + oz]
        if x1 == x0 or y1 == y0 or z1 == z0:
            return {"success": False, "error": "caja con dimension nula"}
        result = self.solids.create_box_solid(
            center, abs(x1 - x0), abs(y1 - y0), abs(z1 - z0), layer
        )
        self._built.add(result)
        return result

    def _cyl(
        self, start: list[float], end: list[float], radius: float, layer: str
    ) -> dict[str, Any]:
        ox, oy, oz = self._off
        p1 = [start[0] + ox, start[1] + oy, start[2] + oz]
        p2 = [end[0] + ox, end[1] + oy, end[2] + oz]
        result = self.solids.create_cylinder_between(p1, p2, radius, layer)
        self._built.add(result)
        return result

    def _beam_between(
        self,
        start: list[float],
        end: list[float],
        width: float,
        depth: float,
        layer: str,
    ) -> dict[str, Any]:
        """Barra de seccion rectangular entre dos puntos (diagonales)."""
        ox, oy, oz = self._off
        p1 = [start[0] + ox, start[1] + oy, start[2] + oz]
        p2 = [end[0] + ox, end[1] + oy, end[2] + oz]
        result = self.solids.create_box_between(p1, p2, width, depth, layer)
        self._built.add(result)
        return result

    @staticmethod
    def _layer(key: str) -> str:
        return BRIDGE_LAYERS[key]["name"]

    # --- detalle metalico ------------------------------------------------
    def _fastener(self, start: list[float], end: list[float], radius: float = 0.032) -> bool:
        """Perno/rivet cilindrico entre dos puntos, limitado por el tope."""
        if self._fasteners >= self._fastener_cap:
            return False
        result = self._cyl(start, end, radius, self._layer("fastener"))
        if not result.get("success"):
            return False
        self._fasteners += 1
        return True

    def _fastener_row(
        self,
        x: float,
        y: float,
        z: float,
        axis: str,
        count: int,
        spacing: float,
        length: float,
        radius: float = 0.032,
    ) -> int:
        """Fila centrada de pernos en X, Y o Z. Devuelve cuantos se crearon."""
        created = 0
        offsets = [(-(count - 1) / 2.0 + index) * spacing for index in range(count)]
        for offset in offsets:
            if axis == "x":
                start = [x + offset - length / 2, y, z]
                end = [x + offset + length / 2, y, z]
            elif axis == "y":
                start = [x, y + offset - length / 2, z]
                end = [x, y + offset + length / 2, z]
            else:
                start = [x, y, z + offset - length / 2]
                end = [x, y, z + offset + length / 2]
            if not self._fastener(start, end, radius):
                break
            created += 1
        return created

    def _i_beam_x(
        self,
        x0: float,
        x1: float,
        y: float,
        z0: float,
        z1: float,
        flange: float,
        web: float,
        flange_t: float,
        layer: str,
    ) -> None:
        """Viga I de eje X: ala superior, ala inferior y alma."""
        self._box(x0, x1, y - flange / 2, y + flange / 2, z1 - flange_t, z1, layer)
        self._box(x0, x1, y - flange / 2, y + flange / 2, z0, z0 + flange_t, layer)
        self._box(x0, x1, y - web / 2, y + web / 2, z0 + flange_t, z1 - flange_t, layer)

    def _i_beam_y(
        self,
        y0: float,
        y1: float,
        x: float,
        z0: float,
        z1: float,
        flange: float,
        web: float,
        flange_t: float,
        layer: str,
    ) -> None:
        """Viga I de eje Y: ala superior, ala inferior y alma."""
        self._box(x - flange / 2, x + flange / 2, y0, y1, z1 - flange_t, z1, layer)
        self._box(x - flange / 2, x + flange / 2, y0, y1, z0, z0 + flange_t, layer)
        self._box(x - web / 2, x + web / 2, y0, y1, z0 + flange_t, z1 - flange_t, layer)

    # --- elementos comunes ----------------------------------------------
    def _deck(self, spec: BridgeSpec) -> None:
        """Tablero: losa, vigas de borde, calzada, mediana y senalizacion."""
        half = spec.total_length / 2
        y = spec.deck_width / 2
        top = spec.deck_top
        self._box(-half, half, -y, y, top - 0.35, top, self._layer("deck"))
        self._box(-half, half, -y, y, spec.clearance, spec.clearance + 0.45, self._layer("girder"))
        for side in (-1, 1):
            self._box(
                -half,
                half,
                min(side * (y - 0.45), side * y),
                max(side * (y - 0.45), side * y),
                spec.clearance,
                top,
                self._layer("girder"),
            )
            self._box(
                -half,
                half,
                min(side * (y - 1.25), side * (y - 0.45)),
                max(side * (y - 1.25), side * (y - 0.45)),
                top,
                top + 1.1,
                self._layer("girder"),
            )

        # Calzada de asfalto: dos carriles separados por una mediana de hormigon.
        sidewalk = max(1.8, min(3.2, spec.deck_width * 0.105))
        road_y = max(0.5, y - sidewalk)
        median_half = max(0.3, min(0.6, spec.deck_width * 0.022))
        pave_top = top + 0.08
        for side in (-1, 1):
            self._box(
                -half,
                half,
                min(side * median_half, side * road_y),
                max(side * median_half, side * road_y),
                top,
                pave_top,
                self._layer("pavement"),
            )
            # Aceras peatonales entre la calzada y la barrera exterior.
            self._box(
                -half,
                half,
                min(side * road_y, side * (y - 0.45)),
                max(side * road_y, side * (y - 0.45)),
                top,
                top + 0.25,
                self._layer("deck"),
            )

        self._box(
            -half,
            half,
            -median_half,
            median_half,
            top,
            top + 0.75,
            self._layer("deck"),
        )

        # Senalizacion horizontal: 3 carriles por calzada (6 en total).
        for side in (-1, 1):
            lane_inner = median_half
            lane_outer = road_y
            lane = (lane_outer - lane_inner) / 3.0
            for index in (1, 2):
                ly = side * (lane_inner + lane * index)
                self._box(
                    -half,
                    half,
                    ly - 0.06,
                    ly + 0.06,
                    pave_top,
                    pave_top + 0.01,
                    self._layer("pavement"),
                )

    def _truss(self, spec: BridgeSpec) -> None:
        """Celosia de rigidez del tablero: montantes y diagonales en ambas caras.

        Es lo que da al Golden Gate su perfil caracteristico: el canto del
        tablero (7.6 m) esta formado por una cercha Warren, no por una viga llena.
        """
        half = spec.total_length / 2
        top = spec.deck_top
        bottom = spec.clearance
        y = spec.deck_width / 2 - 0.9
        spacing = max(6.0, spec.suspender_spacing)
        panels = max(4, int(2 * half / spacing))
        step = 2 * half / panels
        for side in (-1, 1):
            cy = side * y
            for index in range(panels):
                x = -half + index * step
                x2 = min(x + step, half)
                self._box(
                    x - 0.35,
                    x + 0.35,
                    cy - 0.28,
                    cy + 0.28,
                    bottom,
                    top,
                    self._layer("girder"),
                )
                z0, z1 = (bottom, top) if index % 2 == 0 else (top, bottom)
                self._beam_between([x, cy, z0], [x2, cy, z1], 0.3, 0.3, self._layer("girder"))

    def _approach_piers(self, spec: BridgeSpec) -> None:
        """Pilas del viaducto de acceso, a ambos lados."""
        half = spec.total_length / 2
        inner = spec.main_span / 2 + spec.side_span
        approach = half - inner
        if approach <= 0 or spec.n_approach_piers <= 0:
            return
        step = approach / (spec.n_approach_piers + 1)
        for side in (-1, 1):
            for index in range(1, spec.n_approach_piers + 1):
                x = side * (inner + index * step)
                self._box(x - 4, x + 4, -9, 9, -10, spec.clearance, self._layer("pier"))
                self._box(
                    x - 5,
                    x + 5,
                    -11,
                    11,
                    spec.clearance - 1.5,
                    spec.clearance,
                    self._layer("pier"),
                )

    def _abutments(self, spec: BridgeSpec) -> None:
        half = spec.total_length / 2
        for side in (-1, 1):
            x = side * half
            self._box(
                min(x, x - side * 18),
                max(x, x - side * 18),
                -spec.deck_width / 2 - 2,
                spec.deck_width / 2 + 2,
                spec.clearance - 18,
                spec.clearance,
                self._layer("abutment"),
            )

    def _abutment_details(self, spec: BridgeSpec) -> None:
        """Aletas escalonadas en los estribos y bloques de anclaje de los cables."""
        half = spec.total_length / 2
        for side in (-1, 1):
            x = side * half
            for step in range(3):
                width = 24.0 - 4.0 * step
                z0 = spec.clearance - 18.0 + 4.0 * step
                z1 = z0 + 5.0
                self._box(
                    min(x, x - side * 14.0),
                    max(x, x - side * 14.0),
                    -width / 2,
                    width / 2,
                    z0,
                    z1,
                    self._layer("abutment"),
                )

        inner = spec.main_span / 2 + spec.side_span
        if inner < half:
            z_center = max(0.0, spec.clearance * 0.6)
            for side in (-1, 1):
                ax = side * inner
                for dy in (7.0, -7.0):
                    self._box(
                        ax - 10,
                        ax + 10,
                        dy - 3,
                        dy + 3,
                        z_center - 3,
                        z_center + 3,
                        self._layer("abutment"),
                    )

    def _cross_frames(self, spec: BridgeSpec) -> None:
        """Vigas transversales de piso entre las dos celosias del tablero."""
        half = spec.total_length / 2
        top = spec.deck_top
        bottom = spec.clearance
        y = spec.deck_width / 2 - 0.9
        spacing = max(6.0, spec.suspender_spacing)
        panels = max(4, int(2 * half / spacing))
        step = 2 * half / panels
        for index in range(0, panels + 1, 2):
            x = -half + index * step
            self._beam_between([x, -y, bottom], [x, y, bottom], 0.45, 0.6, self._layer("girder"))
            self._beam_between(
                [x, -y, top - 0.35],
                [x, y, top - 0.35],
                0.3,
                0.35,
                self._layer("girder"),
            )

    def _bottom_bracing(self, spec: BridgeSpec) -> None:
        """Arriostramiento horizontal en X entre vigas transversales."""
        half = spec.total_length / 2
        bottom = spec.clearance + 0.5
        y = spec.deck_width / 2 - 0.9
        spacing = max(6.0, spec.suspender_spacing)
        panels = max(4, int(2 * half / spacing))
        step = 2 * half / panels
        for index in range(0, panels, 2):
            x0 = -half + index * step
            x1 = min(x0 + 2 * step, half)
            if x1 - x0 < step * 0.5:
                continue
            self._beam_between([x0, -y, bottom], [x1, y, bottom], 0.22, 0.28, self._layer("girder"))
            self._beam_between([x0, y, bottom], [x1, -y, bottom], 0.22, 0.28, self._layer("girder"))

    def _railings(self, spec: BridgeSpec) -> None:
        """Barandillas peatonales: dos largueros y postes cada 2 paneles."""
        half = spec.total_length / 2
        y = spec.deck_width / 2 - 0.85
        base = spec.deck_top + 0.25
        spacing = max(9.0, spec.suspender_spacing * 2.0)
        count = max(1, int(2 * half / spacing))
        for side in (-1, 1):
            cy = side * y
            for z in (base + 1.35, base + 1.95):
                self._box(
                    -half,
                    half,
                    cy - 0.06,
                    cy + 0.06,
                    z,
                    z + 0.12,
                    self._layer("equipment"),
                )
            for index in range(count + 1):
                x = -half + 2 * half * index / count
                self._box(
                    x - 0.08,
                    x + 0.08,
                    cy - 0.08,
                    cy + 0.08,
                    base,
                    base + 2.1,
                    self._layer("equipment"),
                )

    def _streetlights(self, spec: BridgeSpec) -> None:
        """Farolas alternas cada 76.2 m (250 ft) sobre las aceras."""
        half = spec.total_length / 2
        base = spec.deck_top + 0.25
        spacing = 76.2
        count = max(1, int(2 * half / spacing))
        y = spec.deck_width / 2 - 0.85
        for index in range(count):
            side = 1 if index % 2 == 0 else -1
            x = -half + (index + 0.5) * (2 * half / count)
            cy = side * y
            self._cyl([x, cy, base], [x, cy, base + 9.0], 0.12, self._layer("equipment"))
            self._beam_between(
                [x, cy, base + 8.8],
                [x, cy - side * 2.6, base + 9.2],
                0.12,
                0.12,
                self._layer("equipment"),
            )
            self._box(
                x - 0.45,
                x + 0.45,
                min(cy - side * 2.9, cy - side * 2.5),
                max(cy - side * 2.9, cy - side * 2.5),
                base + 9.05,
                base + 9.25,
                self._layer("equipment"),
            )

    def _tower_caps(self, tx: float, spec: BridgeSpec) -> None:
        """Remate superior de la torre y monturas (saddles) de los cables."""
        top = spec.tower_height
        leg_y = spec.deck_width / 2 + 2.2
        self._box(
            tx - 1.8,
            tx + 1.8,
            -leg_y - 3.5,
            leg_y + 3.5,
            top - 4.0,
            top,
            self._layer("tower"),
        )
        for side in (-1, 1):
            cy = side * leg_y
            self._box(
                tx - 2.4,
                tx + 2.4,
                cy - 1.8,
                cy + 1.8,
                top,
                top + 2.2,
                self._layer("tower"),
            )
            self._box(
                tx - 3.0,
                tx + 3.0,
                cy - 2.2,
                cy + 2.2,
                top + 2.2,
                top + 2.6,
                self._layer("equipment"),
            )

    def _fenders(self, spec: BridgeSpec) -> None:
        """Diques de proteccion (fenders) alrededor de las pilas de las torres."""
        half_main = spec.main_span / 2
        for side in (-1, 1):
            tx = side * half_main
            for ring in (-1, 1):
                self._box(
                    tx - 26,
                    tx + 26,
                    min(ring * 18, ring * 22),
                    max(ring * 18, ring * 22),
                    -12,
                    6,
                    self._layer("pier"),
                )
                self._box(
                    min(tx + ring * 22, tx + ring * 26),
                    max(tx + ring * 22, tx + ring * 26),
                    -18,
                    18,
                    -12,
                    6,
                    self._layer("pier"),
                )

    def _expansion_joints(self, spec: BridgeSpec) -> None:
        """Juntas de dilatacion en estribos, torres y anclajes."""
        half = spec.total_length / 2
        inner = spec.main_span / 2 + spec.side_span
        positions = {-half, -spec.main_span / 2, spec.main_span / 2, half}
        if inner < half:
            positions.update((-inner, inner))
        y = spec.deck_width / 2
        for x in sorted(positions):
            # En los extremos la junta queda dentro del tablero para no alterar
            # la longitud total de 2737 m.
            if abs(abs(x) - half) < 1e-6:
                x0, x1 = (x - 0.9, x) if x > 0 else (x, x + 0.9)
            else:
                x0, x1 = x - 0.45, x + 0.45
            self._box(
                x0,
                x1,
                -y,
                y,
                spec.deck_top,
                spec.deck_top + 0.06,
                self._layer("equipment"),
            )

    def _fort_point_arch(self, spec: BridgeSpec) -> None:
        """Arco Fort Point bajo el vano lateral sur (lado +X)."""
        if spec.side_span < 40.0:
            return
        span = min(98.0, spec.side_span * 0.85)
        center = spec.main_span / 2 + span / 2 + 6.0
        rise = min(28.0, spec.clearance - 12.0)
        if rise <= 3.0:
            return
        samples = 18
        y_rib = spec.deck_width / 2 - 2.4
        deck_bottom = spec.clearance - 0.45
        for side in (-1, 1):
            cy = side * y_rib
            previous: list[float] | None = None
            for index in range(samples + 1):
                t = index / samples
                x = center - span / 2 + span * t
                z = (spec.clearance - 2.0) - (rise - 2.0) * (2.0 * t - 1.0) ** 2
                point = [x, cy, z]
                if previous is not None:
                    self._beam_between(previous, point, 2.2, 1.8, self._layer("arch"))
                previous = point
            for index in range(2, samples - 1, 2):
                t = index / samples
                x = center - span / 2 + span * t
                z = (spec.clearance - 2.0) - (rise - 2.0) * (2.0 * t - 1.0) ** 2
                if deck_bottom - z < 3.0:
                    continue
                self._box(
                    x - 0.5,
                    x + 0.5,
                    cy - 0.5,
                    cy + 0.5,
                    z,
                    deck_bottom,
                    self._layer("arch"),
                )

    # --- detalle metalico: miembros, placas, apoyos y pernos --------------
    def _steel_details(self, spec: BridgeSpec) -> None:
        """Anade el detalle metalico segun ``spec.detail``.

        ``members`` crea vigas I, placas de nudo/empalme, rigidizadores,
        diafragmas, apoyos y herrajes de cable. ``bolted`` anade ademas
        pernos/rivets hasta ``spec.max_fasteners``.
        """
        if spec.detail == "none":
            return
        self._deck_steel(spec)
        self._deck_splices(spec)

        if spec.kind == "suspension":
            for side in (-1, 1):
                self._tower_stiffeners(spec, side * spec.main_span / 2)
            self._bearings(spec, self._suspension_supports(spec))
            self._cable_anchorages(spec)
        elif spec.kind == "cable_stayed":
            for px in self._pylon_positions(spec):
                self._pylon_stiffeners(spec, px)
            supports = [side * spec.total_length / 2 for side in (-1, 1)]
            supports.extend(self._pylon_positions(spec))
            self._bearings(spec, supports)
        elif spec.kind == "arch":
            self._arch_splices(spec)
            span = min(spec.main_span, spec.total_length * 0.85)
            supports = [side * spec.total_length / 2 for side in (-1, 1)]
            supports.extend(side * span / 2 for side in (-1, 1))
            self._bearings(spec, supports)
        else:
            supports = [side * spec.total_length / 2 for side in (-1, 1)]
            clear = spec.total_length / spec.spans
            for index in range(1, spec.spans):
                supports.append(-spec.total_length / 2 + index * clear)
            self._bearings(spec, supports)

    def _deck_steel(self, spec: BridgeSpec) -> None:
        """Vigas longitudinales I y vigas transversales de piso bajo la losa."""
        half = spec.total_length / 2
        top = spec.deck_top
        y_limit = max(1.5, spec.deck_width / 2 - 2.8)
        stringers = max(4, min(8, int(spec.deck_width / 3.0)))
        if stringers % 2:
            stringers += 1
        depth = min(1.4, max(0.5, spec.deck_depth * 0.35))
        z1 = top - 0.35
        z0 = z1 - depth
        for index in range(stringers):
            y = -y_limit + 2.0 * y_limit * index / (stringers - 1)
            if abs(y) < 0.6:
                continue
            self._i_beam_x(
                -half,
                half,
                y,
                z0,
                z1,
                0.5,
                0.06,
                min(0.10, depth / 5.0),
                self._layer("plate"),
            )

        spacing = max(6.0, spec.suspender_spacing)
        panels = max(4, int(2 * half / spacing))
        step = 2 * half / panels
        floor_z1 = z0 - 0.05
        floor_z0 = floor_z1 - min(1.2, max(0.6, spec.deck_depth * 0.3))
        for index in range(0, panels + 1, 2):
            x = -half + index * step
            self._i_beam_y(
                -y_limit,
                y_limit,
                x,
                floor_z0,
                floor_z1,
                0.55,
                0.07,
                0.12,
                self._layer("plate"),
            )

    def _deck_splices(self, spec: BridgeSpec) -> None:
        """Placas de empalme en los cordones de las celosias del tablero."""
        half = spec.total_length / 2
        count = 12 if spec.total_length >= 200.0 else 4
        y = spec.deck_width / 2 - 0.9
        z_levels = (spec.clearance + 0.55, spec.deck_top - 0.55)
        for index in range(count):
            x = -half + (index + 0.5) * 2.0 * half / count
            for side in (-1, 1):
                cy = side * y
                plate_y0, plate_y1 = cy + side * 0.30, cy + side * 0.38
                for zc in z_levels:
                    self._box(
                        x - 0.75,
                        x + 0.75,
                        plate_y0,
                        plate_y1,
                        zc - 0.45,
                        zc + 0.45,
                        self._layer("plate"),
                    )
                    if spec.detail == "bolted":
                        self._fastener_row(
                            x,
                            cy,
                            zc,
                            "x",
                            3,
                            0.45,
                            1.0,
                            radius=0.034,
                        )

    def _tower_stiffeners(self, spec: BridgeSpec, tx: float) -> None:
        """Rigidizadores verticales y cartelas en los fustes de la torre."""
        top = spec.tower_height
        leg_y = spec.deck_width / 2 + 2.2
        levels = max(4, int(top / 18.0))
        for index in range(levels):
            z = top * (index + 0.5) / levels
            t = min(1.0, max(0.0, z / top))
            sx = 3.4 - 1.4 * t
            sy = 5.6 - 2.4 * t
            for side in (-1, 1):
                cy = side * leg_y
                for face in (-1, 1):
                    self._box(
                        tx + face * sx / 2,
                        tx + face * (sx / 2 + 0.06),
                        cy - sy / 2,
                        cy + sy / 2,
                        z - 0.4,
                        z + 0.4,
                        self._layer("stiffener"),
                    )
        for fraction in (0.12, 0.30, 0.46, 0.62, 0.76, 0.88, 0.97):
            zc = top * fraction
            for side in (-1, 1):
                cy = side * leg_y
                for face in (-1, 1):
                    self._box(
                        tx + face * 1.45,
                        tx + face * 1.55,
                        cy - 1.2,
                        cy + 1.2,
                        zc - 0.7,
                        zc + 0.7,
                        self._layer("stiffener"),
                    )

    def _pylon_stiffeners(self, spec: BridgeSpec, px: float) -> None:
        """Rigidizadores en los pilonos atirantados."""
        leg_y = spec.deck_width / 2 + 1.0
        z0 = spec.clearance
        z1 = spec.tower_height
        levels = max(4, int((z1 - z0) / 16.0))
        for index in range(levels):
            z = z0 + (z1 - z0) * (index + 0.5) / levels
            for side in (-1, 1):
                cy = side * leg_y
                for face in (-1, 1):
                    self._box(
                        px + face * 2.2,
                        px + face * 2.26,
                        cy - 1.5,
                        cy + 1.5,
                        z - 0.4,
                        z + 0.4,
                        self._layer("stiffener"),
                    )

    def _cable_anchorages(self, spec: BridgeSpec) -> None:
        """Placas y zapatas de anclaje de los cables principales."""
        ax = spec.main_span / 2 + spec.side_span
        z_base = max(0.0, spec.clearance * 0.6 - 3.0)
        for side in (-1, 1):
            x = side * ax
            for dy in (-7.0, 7.0):
                self._box(
                    x - 3.2,
                    x + 3.2,
                    dy - 1.4,
                    dy + 1.4,
                    z_base,
                    z_base + 0.6,
                    self._layer("plate"),
                )
                self._box(
                    x - 2.2,
                    x + 2.2,
                    dy - 1.0,
                    dy + 1.0,
                    z_base + 0.6,
                    z_base + 1.5,
                    self._layer("plate"),
                )
                self._box(
                    x - 1.1,
                    x + 1.1,
                    dy - 0.7,
                    dy + 0.7,
                    z_base + 1.5,
                    z_base + 2.3,
                    self._layer("stiffener"),
                )
                if spec.detail == "bolted":
                    for dx in (-1.6, 1.6):
                        for ddy in (-0.7, 0.7):
                            self._fastener(
                                [x + dx, dy + ddy, z_base - 0.5],
                                [x + dx, dy + ddy, z_base + 1.0],
                                radius=0.04,
                            )

    def _suspension_supports(self, spec: BridgeSpec) -> list[float]:
        supports = [side * spec.main_span / 2 for side in (-1, 1)]
        supports.extend(side * spec.total_length / 2 for side in (-1, 1))
        inner = spec.main_span / 2 + spec.side_span
        approach = spec.total_length / 2 - inner
        if approach > 0 and spec.n_approach_piers > 0:
            step = approach / (spec.n_approach_piers + 1)
            supports.extend(
                side * (inner + index * step)
                for side in (-1, 1)
                for index in range(1, spec.n_approach_piers + 1)
            )
        return sorted({round(x, 6) for x in supports})

    def _bearings(self, spec: BridgeSpec, positions: list[float]) -> None:
        """Apoyos de acero bajo cada linea de celosia o viga."""
        y = max(0.6, spec.deck_width / 2 - 0.9)
        limit = spec.total_length / 2 - 0.9
        for x in sorted({round(value, 6) for value in positions}):
            if abs(x) > limit:
                x = limit if x >= 0 else -limit
            for side in (-1, 1):
                self._bearing(spec, x, side * y)

    def _bearing(self, spec: BridgeSpec, x: float, y: float) -> None:
        """Apoyo tipo placa: placa de asiento, placa de base y rigidizador."""
        z = spec.clearance
        self._box(x - 0.9, x + 0.9, y - 0.55, y + 0.55, z - 0.45, z - 0.25, self._layer("plate"))
        self._box(x - 0.7, x + 0.7, y - 0.45, y + 0.45, z - 0.25, z, self._layer("plate"))
        self._box(x - 0.12, x + 0.12, y - 0.30, y + 0.30, z, z + 0.45, self._layer("stiffener"))
        if spec.detail == "bolted":
            for dx in (-0.55, 0.55):
                for dy in (-0.25, 0.25):
                    self._fastener(
                        [x + dx, y + dy, z - 0.55],
                        [x + dx, y + dy, z + 0.05],
                        radius=0.035,
                    )

    def _arch_splices(self, spec: BridgeSpec) -> None:
        """Placas de empalme en las costillas del arco."""
        span = min(spec.main_span, spec.total_length * 0.85)
        rise = spec.arch_rise
        yc = max(1.2, spec.deck_width / 2 - 1.8)
        count = 12 if span >= 120.0 else 4
        for index in range(count):
            x = -span / 2 + (index + 0.5) * span / count
            z_arch = rise * (1.0 - (x / (span / 2)) ** 2)
            for side in (-1, 1):
                cy = side * yc
                self._box(
                    x - 0.8,
                    x + 0.8,
                    cy - 1.15,
                    cy - 0.95,
                    z_arch - 1.0,
                    z_arch + 1.0,
                    self._layer("plate"),
                )
                if spec.detail == "bolted":
                    self._fastener_row(x, cy - 1.05, z_arch, "x", 3, 0.45, 0.4, radius=0.034)

    def _build_girder(self, spec: BridgeSpec) -> None:
        self._deck(spec)
        self._railings(spec)
        self._streetlights(spec)
        self._expansion_joints(spec)
        self._abutments(spec)
        clear = spec.total_length / spec.spans
        for index in range(1, spec.spans):
            x = -spec.total_length / 2 + index * clear
            self._box(x - 4, x + 4, -8, 8, -10, spec.clearance, self._layer("pier"))
            self._box(
                x - 5,
                x + 5,
                -spec.deck_width / 2 - 1.5,
                spec.deck_width / 2 + 1.5,
                spec.clearance - 1.5,
                spec.clearance,
                self._layer("pier"),
            )
        self._steel_details(spec)

    def _build_suspension(self, spec: BridgeSpec) -> None:
        self._deck(spec)
        self._truss(spec)
        self._cross_frames(spec)
        self._bottom_bracing(spec)
        self._railings(spec)
        self._streetlights(spec)
        self._expansion_joints(spec)
        self._fort_point_arch(spec)
        self._abutments(spec)
        self._abutment_details(spec)
        self._fenders(spec)
        self._approach_piers(spec)

        half_main = spec.main_span / 2
        inner = half_main + spec.side_span
        top = spec.tower_height
        deck_top = spec.deck_top
        cable_y = spec.deck_width / 2 - 0.8
        radius = spec.cable_diameter / 2

        for side in (-1, 1):
            tx = side * half_main
            self._box(tx - 17, tx + 17, -15, 15, -15, spec.clearance, self._layer("pier"))
            self._tower(tx, spec)
            self._tower_caps(tx, spec)

        for side in (-1, 1):
            ax = side * inner
            self._box(ax - 28, ax + 28, -19, 19, -10, 40, self._layer("abutment"))

        main_samples = self._main_cable(spec, half_main, top)

        for side in (-1, 1):
            cy = side * cable_y
            self._cable_run(main_samples, radius, cy)
            self._suspenders_main(spec, half_main, deck_top, cy)
            for sub_side in (-1, 1):
                x0 = sub_side * half_main
                x1 = sub_side * inner
                steps = max(4, int(spec.side_span / 24))
                samples = []
                for i in range(steps + 1):
                    t = i / steps
                    samples.append([x0 + (x1 - x0) * t, top + (40.0 - top) * t])
                self._cable_run(samples, radius, cy)
                self._suspenders_side(spec, samples, deck_top, cy)
        self._steel_details(spec)

    def _tower(self, tx: float, spec: BridgeSpec) -> None:
        """Torre de dos fustes escalonados con riostras horizontales y X."""
        top = spec.tower_height
        leg_y = spec.deck_width / 2 + 2.2
        segments = 6
        z = 0.0
        for index in range(segments):
            z0 = z
            z1 = top * (index + 1) / segments
            shrink = index / (segments - 1)
            sx = 3.4 - 1.4 * shrink
            sy = 5.6 - 2.4 * shrink
            for side in (-1, 1):
                cy = side * leg_y
                self._box(
                    tx - sx / 2,
                    tx + sx / 2,
                    cy - sy / 2,
                    cy + sy / 2,
                    z0,
                    z1,
                    self._layer("tower"),
                )
            # Arriostramiento en X entre los dos fustes (plano transversal).
            for a, b in ((-1, 1), (1, -1)):
                self._beam_between(
                    [tx, a * leg_y, z0],
                    [tx, b * leg_y, z1],
                    1.2,
                    1.2,
                    self._layer("tower"),
                )
            z = z1

        for fraction in (0.12, 0.30, 0.46, 0.62, 0.76, 0.88, 0.97):
            zc = top * fraction
            self._box(
                tx - 1.4,
                tx + 1.4,
                -leg_y,
                leg_y,
                zc - 1.0,
                zc + 1.0,
                self._layer("tower"),
            )

    def _main_cable(self, spec: BridgeSpec, half_main: float, top: float) -> list[list[float]]:
        samples: list[list[float]] = []
        steps = 40
        for index in range(steps + 1):
            x = -half_main + 2 * half_main * index / steps
            z = top - spec.cable_sag * (1.0 - (x / half_main) ** 2)
            samples.append([x, z])
        return samples

    def _cable_run(self, samples: list[list[float]], radius: float, cable_y: float) -> None:
        for index in range(len(samples) - 1):
            x0, z0 = samples[index]
            x1, z1 = samples[index + 1]
            self._cyl([x0, cable_y, z0], [x1, cable_y, z1], radius, self._layer("cable"))

    def _suspenders_main(
        self,
        spec: BridgeSpec,
        half_main: float,
        deck_top: float,
        cable_y: float,
    ) -> None:
        spacing = spec.suspender_spacing
        count = int((2 * half_main - spacing) / spacing)
        for index in range(1, count + 1):
            x = -half_main + index * spacing
            z = spec.tower_height - spec.cable_sag * (1.0 - (x / half_main) ** 2)
            self._suspender(x, z, deck_top, cable_y, spec=spec)

    def _suspenders_side(
        self,
        spec: BridgeSpec,
        samples: list[list[float]],
        deck_top: float,
        cable_y: float,
    ) -> None:
        spacing = spec.suspender_spacing
        x0, z0 = samples[0]
        x1, z1 = samples[-1]
        count = int(abs(x1 - x0) / spacing)
        for index in range(1, count + 1):
            t = index / (count + 1)
            z = z0 + (z1 - z0) * t
            if z > deck_top + 1.0:
                self._suspender(x0 + (x1 - x0) * t, z, deck_top, cable_y, spec=spec)

    def _suspender(
        self,
        x: float,
        z_cable: float,
        deck_top: float,
        cable_y: float,
        spec: BridgeSpec | None = None,
    ) -> None:
        """Pendola doble: dos cables gemelos y su abrazadera sobre el cable principal."""
        if z_cable <= deck_top + 0.5:
            return
        for offset in (-0.35, 0.35):
            self._cyl(
                [x, cable_y + offset, deck_top],
                [x, cable_y + offset, z_cable],
                0.07,
                self._layer("cable"),
            )
        self._box(
            x - 0.7,
            x + 0.7,
            cable_y - 0.8,
            cable_y + 0.8,
            z_cable - 0.5,
            z_cable + 0.5,
            self._layer("cable"),
        )
        if spec is None or spec.detail == "none":
            return

        plate = self._layer("plate")
        # Semi-abrazaderas exteriores que muerden el cable principal.
        for face in (-1, 1):
            self._box(
                x + face * 0.62,
                x + face * 0.86,
                cable_y - 0.9,
                cable_y + 0.9,
                z_cable - 0.55,
                z_cable + 0.55,
                plate,
            )
        # Sockets y pasadores de los dos cables del suspensor sobre el tablero.
        for offset in (-0.35, 0.35):
            cy = cable_y + offset
            self._box(
                x - 0.30,
                x + 0.30,
                cy - 0.24,
                cy + 0.24,
                deck_top + 0.15,
                deck_top + 0.85,
                plate,
            )
            self._box(
                x - 0.42,
                x + 0.42,
                cy - 0.32,
                cy + 0.32,
                deck_top,
                deck_top + 0.18,
                plate,
            )
            self._cyl(
                [x, cy - 0.50, deck_top + 0.50],
                [x, cy + 0.50, deck_top + 0.50],
                0.07,
                plate,
            )
        if spec.detail == "bolted":
            for dx in (-0.5, 0.5):
                self._fastener(
                    [x + dx, cable_y - 0.95, z_cable],
                    [x + dx, cable_y + 0.95, z_cable],
                    radius=0.04,
                )

    def _build_cable_stayed(self, spec: BridgeSpec) -> None:
        self._deck(spec)
        self._railings(spec)
        self._streetlights(spec)
        self._expansion_joints(spec)
        self._abutments(spec)
        half = spec.total_length / 2
        deck_top = spec.deck_top
        leg_y = spec.deck_width / 2 + 1.0

        for px in self._pylon_positions(spec):
            self._box(px - 14, px + 14, -16, 16, -15, spec.clearance, self._layer("pier"))
            for side in (-1, 1):
                cy = side * leg_y
                self._box(
                    px - 2.2,
                    px + 2.2,
                    cy - 2.2,
                    cy + 2.2,
                    spec.clearance,
                    spec.tower_height,
                    self._layer("tower"),
                )
            self._box(
                px - 2.2,
                px + 2.2,
                -leg_y,
                leg_y,
                spec.tower_height - 4.0,
                spec.tower_height,
                self._layer("tower"),
            )
            self._box(
                px - 2.0,
                px + 2.0,
                -leg_y,
                leg_y,
                deck_top + 6.0,
                deck_top + 8.0,
                self._layer("tower"),
            )

            reach = max(spec.main_span / 2, spec.total_length / 8)
            for direction in (-1, 1):
                for index in range(1, 9):
                    ax = px + direction * reach * index / 8
                    if abs(ax) > half:
                        continue
                    for side in (-1, 1):
                        self._cyl(
                            [px, side * leg_y, spec.tower_height - 1.0],
                            [ax, side * (spec.deck_width / 2 - 0.5), deck_top],
                            0.16,
                            self._layer("cable"),
                        )
        self._steel_details(spec)

    def _pylon_positions(self, spec: BridgeSpec) -> list[float]:
        if spec.pylons <= 1:
            return [0.0]
        span = min(spec.main_span, spec.total_length * 0.8)
        step = span / (spec.pylons - 1)
        return [-span / 2 + index * step for index in range(spec.pylons)]

    def _build_arch(self, spec: BridgeSpec) -> None:
        self._deck(spec)
        self._railings(spec)
        self._streetlights(spec)
        self._expansion_joints(spec)
        self._abutments(spec)
        span = min(spec.main_span, spec.total_length * 0.85)
        rise = spec.arch_rise
        deck_bottom = spec.clearance
        rib_width = 2.0
        rib_depth = 2.2
        samples = 40

        outer: list[list[float]] = []
        inner: list[list[float]] = []
        for index in range(samples + 1):
            x = -span / 2 + span * index / samples
            z_out = rise * (1.0 - (x / (span / 2)) ** 2)
            outer.append([x, z_out])
            inner.append([x, max(0.0, z_out - rib_depth)])

        profile = outer + list(reversed(inner))
        for side in (-1, 1):
            yc = side * (spec.deck_width / 2 - 1.8)
            result = self.solids.extrude_polygon(profile, rib_width, 0.0, self._layer("arch"))
            if not result.get("success"):
                continue
            self._built.add(result)
            handle = result["handle"]
            self.solids.rotate_solid(handle, [0, 0, 0], [1, 0, 0], 90.0)
            self.solids.move_solid(
                handle,
                [0, 0, 0],
                [self._off[0], yc + self._off[1] + rib_width / 2, self._off[2]],
            )
            for index in range(2, samples - 1, 4):
                x = -span / 2 + span * index / samples
                z_arch = rise * (1.0 - (x / (span / 2)) ** 2)
                if z_arch >= deck_bottom - 0.5:
                    continue
                self._box(
                    x - 0.5,
                    x + 0.5,
                    yc - 0.5,
                    yc + 0.5,
                    z_arch,
                    deck_bottom,
                    self._layer("arch"),
                )

        for side in (-1, 1):
            sx = side * span / 2
            if abs(sx) < spec.total_length / 2 - 1:
                self._box(
                    sx - 8,
                    sx + 8,
                    -spec.deck_width / 2,
                    spec.deck_width / 2,
                    -10,
                    deck_bottom,
                    self._layer("pier"),
                )
        self._steel_details(spec)
