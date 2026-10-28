"""Modelado 3D por COM: solidos primitivos, extrusion y operaciones booleanas.

Convenciones verificadas contra AutoCAD 2026 (25.1) con *late binding*:

* ``AddBox``, ``AddCylinder`` y ``AddSphere`` reciben el **centro** de la primitiva
  (no una esquina): una caja de 10x5x2 en el origen ocupa de -5 a 5 en X.
* ``Boolean`` usa ``0=union``, ``1=interseccion``, ``2=resta``. El valor 3 no es
  valido; los nombres de ``AcBoolean`` no coinciden con los indices del typelib.
* ``AddExtrudedSolid`` exige un **Region**, no una polilinea: hay que llamar antes
  a ``AddRegion`` con la curva cerrada.
* ``AddExtrudedSolidAlongPath`` falla con trayectorias quebradas ("General modeling
  failure"), asi que los cables se aproximan con cilindros entre puntos.
* Los angulos de ``Rotate3D`` van en radianes.

Solo este modulo y :mod:`autocad_mcp.com` construyen VARIANTs; la conexion COM
sigue encapsulada en :mod:`autocad_mcp.connection`.
"""

from __future__ import annotations

import math
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

from autocad_mcp.cache import TTLCache
from autocad_mcp.com import as_dynamic, variant_array, variant_objects, variant_point
from autocad_mcp.connection import AutoCADConnection, safe_operation
from autocad_mcp.features.base import FeatureBase
from autocad_mcp.layers import LayerTools

# AcBoolean en late binding: 0=union, 1=interseccion, 2=resta.
AC_UNION = 0
AC_INTERSECTION = 1
AC_SUBTRACTION = 2
BOOLEAN_OPERATIONS: dict[str, int] = {
    "union": AC_UNION,
    "intersection": AC_INTERSECTION,
    "subtraction": AC_SUBTRACTION,
}

DEFAULT_SOLID_LAYER = "S-ESTRUCTURA"
SOLID_OBJECT_NAME = "AcDb3dSolid"


def _delta(start: list[float], end: list[float]) -> tuple[float, float, float, float]:
    """Vector start->end y su longitud, validando puntos de 3 coordenadas."""
    if len(start) < 2 or len(end) < 2:
        raise ValueError("los puntos requieren al menos x e y")
    sx, sy = float(start[0]), float(start[1])
    sz = float(start[2]) if len(start) > 2 else 0.0
    ex, ey = float(end[0]), float(end[1])
    ez = float(end[2]) if len(end) > 2 else 0.0
    dx, dy, dz = ex - sx, ey - sy, ez - sz
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    if length <= 0.0:
        raise ValueError("start y end coinciden: no hay eje")
    return dx, dy, dz, length


def cylinder_angles(start: list[float], end: list[float]) -> tuple[float, float, float]:
    """Angulos para alinear un cilindro (eje +Z) con el vector start->end.

    Devuelve ``(longitud, azimut, inclinacion)`` en radianes. El cilindro se rota
    primero sobre Y por ``inclinacion`` y luego sobre Z por ``azimut``.
    """
    dx, dy, dz, length = _delta(start, end)
    az = math.atan2(dy, dx)
    theta = math.atan2(math.hypot(dx, dy), dz)
    return length, az, theta


def box_angles(start: list[float], end: list[float]) -> tuple[float, float, float]:
    """Angulos para alinear una caja (eje +X) con el vector start->end.

    Devuelve ``(longitud, azimut, elevacion)`` en radianes. La caja se rota sobre
    Z por ``azimut`` y luego sobre su eje Y local por ``-elevacion``.
    """
    dx, dy, dz, length = _delta(start, end)
    az = math.atan2(dy, dx)
    el = math.atan2(dz, math.hypot(dx, dy))
    return length, az, el


class SolidTools(FeatureBase):
    """Solidos 3D (AcDb3dSolid): primitivas, extrusion y booleanos."""

    def __init__(
        self,
        conn: AutoCADConnection,
        cache: TTLCache | None = None,
        layer_tools: LayerTools | None = None,
    ) -> None:
        super().__init__(conn, cache)
        self.layer_tools = layer_tools or LayerTools(conn)
        self._ready_layers: set[str] = set()
        self._defer = False

    # --- infraestructura -------------------------------------------------
    @contextmanager
    def batch(self) -> Iterator[SolidTools]:
        """Agrupa creaciones: regenera e invalida cache una sola vez al salir."""
        previous = self._defer
        self._defer = True
        try:
            yield self
        finally:
            self._defer = previous
            if not previous:
                self.conn.regen()
                self._invalidate()

    def _prepare_layer(self, layer: str) -> None:
        if layer in self._ready_layers:
            return
        self.layer_tools.create_or_get_layer(layer, "white", "Modelado 3D")
        self._ready_layers.add(layer)

    def _finish(self, entity: Any, layer: str, color: str | int) -> Any:
        if layer:
            try:
                entity.Layer = layer
            except Exception:  # noqa: BLE001 - la capa pudo no crearse
                pass
        self.set_entity_color(entity, color)
        if not self._defer:
            self.conn.regen()
            self._invalidate()
        return entity

    @staticmethod
    def _handle(entity: Any, fallback: str = "solid") -> str:
        try:
            return str(entity.Handle)
        except Exception:  # noqa: BLE001
            return fallback

    @staticmethod
    def _volume(entity: Any) -> float | None:
        try:
            return float(as_dynamic(entity).Volume)
        except Exception:  # noqa: BLE001 - no todo objeto expone Volume
            return None

    @staticmethod
    def _bbox(entity: Any) -> tuple[list[float], list[float]] | None:
        try:
            low, high = as_dynamic(entity).GetBoundingBox()
            return (
                [float(low[0]), float(low[1]), float(low[2])],
                [float(high[0]), float(high[1]), float(high[2])],
            )
        except Exception:  # noqa: BLE001
            return None

    def _center(self, entity: Any) -> list[float] | None:
        box = self._bbox(entity)
        if box is None:
            return None
        return [(box[0][i] + box[1][i]) / 2.0 for i in range(3)]

    def _object(self, handle: str) -> Any:
        return as_dynamic(self.conn.doc.HandleToObject(str(handle)))

    def _result(self, entity: Any, **extra: Any) -> dict[str, Any]:
        handle = self._handle(entity)
        payload: dict[str, Any] = {
            "success": True,
            "handle": handle,
            "handles": [handle],
            "type": SOLID_OBJECT_NAME,
        }
        volume = self._volume(entity)
        if volume is not None:
            payload["volume"] = round(volume, 6)
        try:
            payload["layer"] = str(as_dynamic(entity).Layer)
        except Exception:  # noqa: BLE001
            pass
        payload.update(extra)
        return payload

    # --- primitivas ------------------------------------------------------
    def create_box_solid(
        self,
        center: list[float],
        length: float,
        width: float,
        height: float,
        layer: str = DEFAULT_SOLID_LAYER,
        color: str | int = "bylayer",
        rotation: float = 0.0,
    ) -> dict[str, Any]:
        """Caja 3D centrada en ``center`` (X=largo, Y=ancho, Z=alto)."""
        if not self.conn.ensure():
            return {"success": False, "error": "Not connected to AutoCAD"}
        for name, value in (("length", length), ("width", width), ("height", height)):
            if value <= 0:
                return {"success": False, "error": f"{name} debe ser > 0"}

        self._prepare_layer(layer)
        point = variant_point(*_xyz(center))

        def build() -> Any:
            return self.conn.model_space().AddBox(point, float(length), float(width), float(height))

        entity = safe_operation(build, delay=0.0)
        if entity is None:
            return {"success": False, "error": "Failed to create box solid"}

        if rotation:
            self._rotate_about(entity, _xyz(center), [0.0, 0.0, 1.0], math.radians(rotation))
        return self._result(
            self._finish(entity, layer, color),
            length=length,
            width=width,
            height=height,
            center=list(center),
        )

    def create_box_between(
        self,
        start: list[float],
        end: list[float],
        width: float,
        depth: float,
        layer: str = DEFAULT_SOLID_LAYER,
        color: str | int = "bylayer",
    ) -> dict[str, Any]:
        """Caja 3D con su eje X alineado entre dos puntos.

        Util para diagonales de arriostramiento y segmentos de arco.
        """
        if not self.conn.ensure():
            return {"success": False, "error": "Not connected to AutoCAD"}
        if width <= 0 or depth <= 0:
            return {"success": False, "error": "width y depth deben ser > 0"}
        try:
            length, az, el = box_angles(start, end)
        except ValueError as exc:
            return {"success": False, "error": str(exc)}

        sx, sy, sz = _xyz(start)
        ex, ey, ez = _xyz(end)
        center = [(sx + ex) / 2.0, (sy + ey) / 2.0, (sz + ez) / 2.0]

        self._prepare_layer(layer)
        point = variant_point(*center)

        def build() -> Any:
            return self.conn.model_space().AddBox(point, float(length), float(width), float(depth))

        entity = safe_operation(build, delay=0.0)
        if entity is None:
            return {"success": False, "error": "Failed to create box between points"}

        self._rotate_about(entity, center, [0.0, 0.0, 1.0], az)
        local_y = [-math.sin(az), math.cos(az), 0.0]
        self._rotate_about(entity, center, local_y, -el)
        return self._result(
            self._finish(entity, layer, color),
            width=width,
            depth=depth,
            length=round(length, 6),
            start=list(start),
            end=list(end),
        )

    def create_cylinder_solid(
        self,
        center: list[float],
        radius: float,
        height: float,
        layer: str = DEFAULT_SOLID_LAYER,
        color: str | int = "bylayer",
    ) -> dict[str, Any]:
        """Cilindro vertical centrado en ``center`` (eje +Z)."""
        if not self.conn.ensure():
            return {"success": False, "error": "Not connected to AutoCAD"}
        if radius <= 0 or height <= 0:
            return {"success": False, "error": "radius y height deben ser > 0"}

        self._prepare_layer(layer)
        point = variant_point(*_xyz(center))

        def build() -> Any:
            return self.conn.model_space().AddCylinder(point, float(radius), float(height))

        entity = safe_operation(build, delay=0.0)
        if entity is None:
            return {"success": False, "error": "Failed to create cylinder solid"}
        return self._result(
            self._finish(entity, layer, color),
            radius=radius,
            height=height,
            center=list(center),
        )

    def create_cylinder_between(
        self,
        start: list[float],
        end: list[float],
        radius: float,
        layer: str = DEFAULT_SOLID_LAYER,
        color: str | int = "bylayer",
    ) -> dict[str, Any]:
        """Cilindro solido entre dos puntos (cables, tirantes, suspensores)."""
        if not self.conn.ensure():
            return {"success": False, "error": "Not connected to AutoCAD"}
        if radius <= 0:
            return {"success": False, "error": "radius debe ser > 0"}
        try:
            length, az, theta = cylinder_angles(start, end)
        except ValueError as exc:
            return {"success": False, "error": str(exc)}

        sx, sy, sz = _xyz(start)
        ex, ey, ez = _xyz(end)
        center = [(sx + ex) / 2.0, (sy + ey) / 2.0, (sz + ez) / 2.0]

        self._prepare_layer(layer)
        point = variant_point(*center)

        def build() -> Any:
            return self.conn.model_space().AddCylinder(point, float(radius), float(length))

        entity = safe_operation(build, delay=0.0)
        if entity is None:
            return {"success": False, "error": "Failed to create cylinder between points"}

        self._rotate_about(entity, center, [0.0, 1.0, 0.0], theta)
        self._rotate_about(entity, center, [0.0, 0.0, 1.0], az)
        return self._result(
            self._finish(entity, layer, color),
            radius=radius,
            length=round(length, 6),
            start=list(start),
            end=list(end),
        )

    def create_sphere_solid(
        self,
        center: list[float],
        radius: float,
        layer: str = DEFAULT_SOLID_LAYER,
        color: str | int = "bylayer",
    ) -> dict[str, Any]:
        """Esfera solida centrada en ``center``."""
        if not self.conn.ensure():
            return {"success": False, "error": "Not connected to AutoCAD"}
        if radius <= 0:
            return {"success": False, "error": "radius debe ser > 0"}

        self._prepare_layer(layer)
        point = variant_point(*_xyz(center))

        def build() -> Any:
            return self.conn.model_space().AddSphere(point, float(radius))

        entity = safe_operation(build, delay=0.0)
        if entity is None:
            return {"success": False, "error": "Failed to create sphere solid"}
        return self._result(self._finish(entity, layer, color), radius=radius)

    def extrude_polygon(
        self,
        points: list[list[float]],
        height: float,
        taper_angle: float = 0.0,
        layer: str = DEFAULT_SOLID_LAYER,
        color: str | int = "bylayer",
    ) -> dict[str, Any]:
        """Extruye un poligono cerrado (plano XY) en +Z.

        Genera la polilinea y el region internamente, de modo que no consume
        ninguna entidad del usuario.
        """
        if not self.conn.ensure():
            return {"success": False, "error": "Not connected to AutoCAD"}
        if len(points) < 3:
            return {"success": False, "error": "se requieren al menos 3 puntos"}
        if height == 0:
            return {"success": False, "error": "height debe ser distinto de 0"}

        try:
            flat = [float(c) for p in points for c in (p[0], p[1])]
        except (IndexError, TypeError, ValueError) as exc:
            return {"success": False, "error": f"puntos invalidos: {exc}"}

        self._prepare_layer(layer)

        def build() -> Any:
            space = self.conn.model_space()
            polyline = space.AddLightWeightPolyline(variant_array(flat))
            polyline.Closed = True
            regions = space.AddRegion(variant_objects([polyline]))
            region = regions[0]
            solid = space.AddExtrudedSolid(region, float(height), math.radians(taper_angle))
            try:
                region.Delete()
            except Exception:  # noqa: BLE001 - la extrusion puede consumir el region
                pass
            return solid

        entity = safe_operation(build, delay=0.0)
        if entity is None:
            return {"success": False, "error": "Failed to extrude polygon"}

        result = self._result(
            self._finish(entity, layer, color),
            height=height,
            taper_angle=taper_angle,
            points_count=len(points),
        )
        return result

    # --- operaciones -----------------------------------------------------
    def boolean_solids(
        self,
        target_handle: str,
        tool_handle: str,
        operation: str = "union",
    ) -> dict[str, Any]:
        """Aplica union/interseccion/resta entre dos solidos 3D.

        En la resta, ``tool_handle`` se descarta y el resultado queda en
        ``target_handle``.
        """
        if not self.conn.ensure():
            return {"success": False, "error": "Not connected to AutoCAD"}
        op = BOOLEAN_OPERATIONS.get(str(operation).lower())
        if op is None:
            valid = ", ".join(sorted(BOOLEAN_OPERATIONS))
            return {"success": False, "error": f"operacion invalida '{operation}' (usa {valid})"}

        try:
            target = self._object(target_handle)
            tool = self._object(tool_handle)
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"handle inexistente: {exc}"}

        for label, entity, handle in (
            ("target", target, target_handle),
            ("tool", tool, tool_handle),
        ):
            if str(entity.ObjectName) != SOLID_OBJECT_NAME:
                return {
                    "success": False,
                    "error": f"{label} {handle} no es un solido 3D ({entity.ObjectName})",
                }

        def apply() -> Any:
            target.Boolean(op, tool)
            return target

        entity = safe_operation(apply, delay=0.0)
        if entity is None:
            return {"success": False, "error": "Boolean fallo (los solidos pueden no intersectar)"}

        self._invalidate()
        return self._result(entity, operation=operation, tool_handle=str(tool_handle))

    def move_solid(
        self,
        handle: str,
        base_point: list[float],
        destination: list[float],
    ) -> dict[str, Any]:
        """Desplaza un solido desde ``base_point`` hasta ``destination``."""
        if not self.conn.ensure():
            return {"success": False, "error": "Not connected to AutoCAD"}
        try:
            entity = self._object(handle)
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"handle inexistente: {exc}"}

        offset = [d - b for b, d in zip(_xyz(base_point), _xyz(destination), strict=True)]
        origin = variant_point(*_xyz(base_point))
        target = variant_point(*_xyz(destination))

        def apply() -> Any:
            entity.Move(origin, target)
            return entity

        moved = safe_operation(apply, delay=0.0)
        if moved is None:
            return {"success": False, "error": "Move fallo"}
        self._invalidate()
        return self._result(moved, offset=offset)

    def rotate_solid(
        self,
        handle: str,
        axis_point: list[float],
        axis_direction: list[float],
        angle: float,
    ) -> dict[str, Any]:
        """Rota un solido ``angle`` grados alrededor de un eje."""
        if not self.conn.ensure():
            return {"success": False, "error": "Not connected to AutoCAD"}
        try:
            entity = self._object(handle)
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"handle inexistente: {exc}"}
        if not any(abs(float(c)) > 0 for c in axis_direction):
            return {"success": False, "error": "axis_direction no puede ser nulo"}

        if not self._rotate_about(entity, _xyz(axis_point), axis_direction, math.radians(angle)):
            return {"success": False, "error": "Rotate3D fallo"}
        self._invalidate()
        return self._result(entity, angle=angle)

    def scale_solid(
        self,
        handle: str,
        base_point: list[float],
        factor: float,
    ) -> dict[str, Any]:
        """Escala uniforme de un solido respecto a ``base_point``."""
        if not self.conn.ensure():
            return {"success": False, "error": "Not connected to AutoCAD"}
        if factor <= 0:
            return {"success": False, "error": "factor debe ser > 0"}
        try:
            entity = self._object(handle)
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"handle inexistente: {exc}"}

        point = variant_point(*_xyz(base_point))

        def apply() -> Any:
            entity.ScaleEntity(point, float(factor))
            return entity

        scaled = safe_operation(apply, delay=0.0)
        if scaled is None:
            return {"success": False, "error": "ScaleEntity fallo"}
        self._invalidate()
        return self._result(scaled, factor=factor, base_point=list(base_point))

    def copy_solid(
        self,
        handle: str,
        destination: list[float],
        base_point: list[float] | None = None,
        count: int = 1,
        rotation: float = 0.0,
    ) -> dict[str, Any]:
        """Copia un solido ``count`` veces, separando cada copia por el vector
        ``destination - base_point`` (la primera copia cae en ``destination``).

        ``rotation`` (grados) gira cada copia sobre el eje Z en su destino.
        """
        if not self.conn.ensure():
            return {"success": False, "error": "Not connected to AutoCAD"}
        if count < 1:
            return {"success": False, "error": "count debe ser >= 1"}
        try:
            entity = self._object(handle)
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"handle inexistente: {exc}"}

        base = _xyz(base_point) if base_point is not None else self._center(entity)
        if base is None:
            return {"success": False, "error": "no se pudo calcular el centro del solido"}
        target = _xyz(destination)
        delta = [target[i] - base[i] for i in range(3)]
        if all(abs(component) < 1e-12 for component in delta):
            return {"success": False, "error": "destination coincide con base_point"}

        origin = variant_point(*base)
        handles: list[str] = []

        def duplicate() -> Any:
            return entity.Copy()

        for index in range(count):
            copy_entity = safe_operation(duplicate, delay=0.0)
            if copy_entity is None:
                return {
                    "success": False,
                    "error": "Copy fallo",
                    "handles": handles,
                }
            point = [base[i] + delta[i] * (index + 1) for i in range(3)]

            def place(item: Any = copy_entity, target_point: list[float] = point) -> Any:
                item.Move(origin, variant_point(*target_point))
                return item

            if safe_operation(place, delay=0.0) is None:
                return {"success": False, "error": "Move de la copia fallo", "handles": handles}
            if rotation:
                self._rotate_about(copy_entity, point, [0.0, 0.0, 1.0], math.radians(rotation))
            handles.append(self._handle(copy_entity))

        self._invalidate()
        return {
            "success": bool(handles),
            "handles": handles,
            "count": len(handles),
            "source": str(handle),
            "offset": [round(component, 6) for component in delta],
        }

    def array_solids(
        self,
        handle: str,
        count: int,
        offset: list[float],
    ) -> dict[str, Any]:
        """Crea una matriz lineal de ``count`` copias separadas por ``offset``."""
        if not self.conn.ensure():
            return {"success": False, "error": "Not connected to AutoCAD"}
        if count < 1:
            return {"success": False, "error": "count debe ser >= 1"}
        if count == 1:
            return {"success": True, "handles": [str(handle)], "count": 1, "source": str(handle)}
        try:
            entity = self._object(handle)
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"handle inexistente: {exc}"}
        base = self._center(entity)
        if base is None:
            return {"success": False, "error": "no se pudo calcular el centro del solido"}
        destination = [base[i] + _xyz(offset)[i] for i in range(3)]
        result = self.copy_solid(handle, destination, base, count - 1)
        if result.get("success"):
            result["count"] = count
            result["source"] = str(handle)
        return result

    # --- consulta --------------------------------------------------------
    def get_solid_info(
        self,
        handles: list[str] | None = None,
        layer: str | None = None,
        include_entities: bool = False,
    ) -> dict[str, Any]:
        """Resumen de solidos: cantidad, volumen total y extents."""
        if not self.conn.ensure():
            return {"success": False, "error": "Not connected to AutoCAD"}

        entities: list[Any] = []
        try:
            if handles:
                last_error = ""
                for attempt in range(3):
                    try:
                        self.conn.ensure()
                        entities = [self._object(h) for h in handles]
                        break
                    except Exception as exc:  # noqa: BLE001 - AutoCAD puede estar ocupado
                        last_error = str(exc)
                        entities = []
                        time.sleep(0.4 * (attempt + 1))
                if not entities:
                    return {"success": False, "error": f"no se pudo leer el modelo: {last_error}"}
            else:
                space = self.conn.model_space()
                for index in range(int(space.Count)):
                    entity = as_dynamic(space.Item(index))
                    if str(entity.ObjectName) == SOLID_OBJECT_NAME:
                        entities.append(entity)
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"no se pudo leer el modelo: {exc}"}

        per_layer: dict[str, dict[str, float]] = {}
        total_volume = 0.0
        rows: list[dict[str, Any]] = []
        low: list[float] | None = None
        high: list[float] | None = None

        for entity in entities:
            try:
                entity_layer = str(entity.Layer)
            except Exception:  # noqa: BLE001
                entity_layer = ""
            if layer and entity_layer != layer:
                continue
            volume = self._volume(entity) or 0.0
            total_volume += volume
            bucket = per_layer.setdefault(entity_layer, {"count": 0.0, "volume": 0.0})
            bucket["count"] += 1
            bucket["volume"] = round(bucket["volume"] + volume, 4)
            box = self._bbox(entity)
            if box is not None:
                low = (
                    box[0] if low is None else [min(a, b) for a, b in zip(low, box[0], strict=True)]
                )
                high = (
                    box[1]
                    if high is None
                    else [max(a, b) for a, b in zip(high, box[1], strict=True)]
                )
            if include_entities:
                rows.append(
                    {
                        "handle": self._handle(entity),
                        "layer": entity_layer,
                        "volume": round(volume, 4),
                        "bbox": box,
                    }
                )

        payload: dict[str, Any] = {
            "success": True,
            "count": len(rows)
            if include_entities
            else int(sum(b["count"] for b in per_layer.values())),
            "total_volume": round(total_volume, 4),
            "by_layer": dict(sorted(per_layer.items())),
        }
        if low is not None and high is not None:
            payload["extents"] = {
                "min": [round(c, 3) for c in low],
                "max": [round(c, 3) for c in high],
                "size": [round(hi - lo, 3) for lo, hi in zip(low, high, strict=True)],
            }
        if include_entities:
            payload["entities"] = rows
        return payload

    # --- helpers ---------------------------------------------------------
    def _rotate_about(
        self,
        entity: Any,
        point: Sequence[float],
        direction: Sequence[float],
        angle: float,
    ) -> bool:
        if angle == 0.0:
            return True
        origin = variant_point(*point)
        axis_end = variant_point(
            point[0] + float(direction[0]),
            point[1] + float(direction[1]),
            point[2] + float(direction[2]),
        )

        def apply() -> Any:
            entity.Rotate3D(origin, axis_end, float(angle))
            return entity

        return safe_operation(apply, delay=0.0) is not None


def _xyz(point: list[float]) -> tuple[float, float, float]:
    """Normaliza un punto a 3 coordenadas."""
    if len(point) < 2:
        raise ValueError("el punto requiere al menos x e y")
    z = float(point[2]) if len(point) > 2 else 0.0
    return float(point[0]), float(point[1]), z
