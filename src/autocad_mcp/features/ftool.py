"""Analisis estructural 2D y exportacion a FTOOL.

El modulo convierte un puente colgante (por defecto el Golden Gate) en un
modelo de barras 2D en el plano longitudinal X-Y, lo resuelve con un solver de
rigidez directa (elementos de pórtico y cables/barras articuladas) y escribe el
mismo modelo en formato ``.ftl`` de FTOOL 4.01.

Unidades: kN, m, radianes. Las cargas verticales son positivas hacia abajo.
El ``.ftl`` se genera siguiendo el formato documentado por ingenieria inversa
(https://github.com/nicchonsanchez/ftool-reverse-engineering). FTOOL no guarda
resultados: hay que abrir el archivo y ejecutar ``Solve`` para verlos.
"""

from __future__ import annotations

import math
import os
import shutil
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from autocad_mcp.config import AutoCADMCPConfig, get_config
from autocad_mcp.features.bridges import PRESETS

FTOOL_MANUAL = "https://www.tecgraf.puc-rio.br/ftool/downloads/ftoolman_en.pdf"
FTOOL_FORMAT = "https://github.com/nicchonsanchez/ftool-reverse-engineering"

# Conectividad del Golden Gate: 2737 m totales, 1966 m colgantes y 385.5 m de
# viaducto de acceso a cada lado.
GOLDEN_GATE_APPROACH = 385.5


class StructuralError(ValueError):
    """Error de modelado o de estabilidad estructural."""


@dataclass(frozen=True)
class Material:
    """Material isotropo lineal (E en kN/m2, rho en kN/m3)."""

    name: str
    E: float
    nu: float
    rho: float
    alpha: float


@dataclass(frozen=True)
class Section:
    """Seccion generica: area (m2) e inercia (m4)."""

    name: str
    A: float
    inertia: float


@dataclass
class FrameNode:
    """Nodo 2D. ``support`` fija (X, Y, giro); ``load`` en kN y kN*m."""

    x: float
    y: float
    tag: str = "deck"
    support: tuple[bool, bool, bool] = (False, False, False)
    load: tuple[float, float, float] = (0.0, 0.0, 0.0)
    support_tag: str = ""


@dataclass
class FrameMember:
    """Barra entre dos nodos. ``kind``: ``frame`` (pórtico) o ``truss``."""

    i: int
    j: int
    section: int
    group: str
    kind: str = "frame"
    uniform_load: float = 0.0


@dataclass
class FrameModel:
    """Modelo de barras 2D listo para resolver o exportar."""

    name: str
    nodes: list[FrameNode]
    members: list[FrameMember]
    materials: list[Material] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)
    load_case: str = "Load Case 01"
    origin_index: int = 0
    meta: dict[str, Any] = field(default_factory=dict)

    def bbox(self) -> tuple[float, float, float, float]:
        xs = [node.x for node in self.nodes]
        ys = [node.y for node in self.nodes]
        return min(xs), max(xs), min(ys), max(ys)

    def count_by(self, attr: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for member in self.members:
            value = str(getattr(member, attr))
            counts[value] = counts.get(value, 0) + 1
        return dict(sorted(counts.items()))


# ---------------------------------------------------------------------------
# Solver de rigidez directa (pórtico 2D con elementos truss)
# ---------------------------------------------------------------------------
_DOFS = 3


def _element_stiffness(
    x1: float, y1: float, x2: float, y2: float, E: float, A: float, inertia: float
) -> tuple[list[list[float]], list[list[float]], list[list[float]], float, float, float]:
    """Rigidez local/global y cosenos directores de una barra."""
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)
    if length <= 1e-9:
        raise StructuralError("barra de longitud nula")
    c = dx / length
    s = dy / length
    ea = E * A
    ei = E * inertia
    l2 = length * length
    l3 = l2 * length

    axial = ea / length
    bend12 = 12.0 * ei / l3
    bend6 = 6.0 * ei / l2
    bend4 = 4.0 * ei / length
    bend2 = 2.0 * ei / length
    local = [
        [axial, 0.0, 0.0, -axial, 0.0, 0.0],
        [0.0, bend12, bend6, 0.0, -bend12, bend6],
        [0.0, bend6, bend4, 0.0, -bend6, bend2],
        [-axial, 0.0, 0.0, axial, 0.0, 0.0],
        [0.0, -bend12, -bend6, 0.0, bend12, -bend6],
        [0.0, bend6, bend2, 0.0, -bend6, bend4],
    ]
    transform = [
        [c, s, 0.0, 0.0, 0.0, 0.0],
        [-s, c, 0.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, c, s, 0.0],
        [0.0, 0.0, 0.0, -s, c, 0.0],
        [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
    ]
    # k_global = T^T * k_local * T
    temp = [
        [sum(local[a][k] * transform[k][b] for k in range(6)) for b in range(6)] for a in range(6)
    ]
    global_k = [
        [sum(transform[k][a] * temp[k][b] for k in range(6)) for b in range(6)] for a in range(6)
    ]
    return global_k, local, transform, length, c, s


def _transpose_mul(transform: list[list[float]], vector: list[float]) -> list[float]:
    """T^T * vector (6x6 por 6)."""
    return [sum(transform[k][a] * vector[k] for k in range(6)) for a in range(6)]


def _mat_vec(matrix: list[list[float]], vector: list[float]) -> list[float]:
    return [sum(matrix[a][b] * vector[b] for b in range(len(vector))) for a in range(len(matrix))]


def _skyline_factor(
    rows: list[list[float]], start: list[int]
) -> tuple[list[list[float]], list[float]]:
    """Factorizacion LDL^T de una matriz simetrica en perfil (skyline)."""
    size = len(rows)
    diagonal = [0.0] * size
    max_diag = max((abs(rows[i][-1]) for i in range(size)), default=1.0)
    tolerance = max(1e-12, max_diag * 1e-14)
    for i in range(size):
        row_i = rows[i]
        first_i = start[i]
        for j in range(first_i, i):
            row_j = rows[j]
            first_j = start[j]
            first_k = max(first_i, first_j)
            value = row_i[j - first_i]
            for k in range(first_k, j):
                value -= row_i[k - first_i] * diagonal[k] * row_j[k - first_j]
            row_i[j - first_i] = value / diagonal[j]
        pivot = row_i[i - first_i]
        for k in range(first_i, i):
            pivot -= row_i[k - first_i] ** 2 * diagonal[k]
        if pivot <= tolerance:
            raise StructuralError(
                "matriz de rigidez singular o no definida positiva: "
                "la estructura es inestable o hay un mecanismo"
            )
        diagonal[i] = pivot
    return rows, diagonal


def _skyline_solve(
    rows: list[list[float]], start: list[int], diagonal: list[float], rhs: list[float]
) -> list[float]:
    """Resuelve L D L^T x = b con los factores de :func:`_skyline_factor`."""
    size = len(rhs)
    y = rhs.copy()
    for i in range(size):
        row_i = rows[i]
        first = start[i]
        value = y[i]
        for k in range(first, i):
            value -= row_i[k - first] * y[k]
        y[i] = value
    z = [y[i] / diagonal[i] for i in range(size)]
    x = z.copy()
    for i in range(size - 1, -1, -1):
        row_i = rows[i]
        first = start[i]
        value = x[i]
        for k in range(first, i):
            x[k] -= row_i[k - first] * value
    return x


def _geometric_stiffness(c: float, s: float, length: float, n0: float) -> list[list[float]]:
    """Rigidez geometrica (P-Delta) global de una barra con axil ``n0``.

    Solo se usa en barras ``truss`` (cables y suspensores), donde la traccion
    aporta rigidez transversal. Sin este termino la rigidez de un cable
    discretizado depende de la malla y no representa el puente real.
    """
    if n0 == 0.0:
        return [[0.0] * 6 for _ in range(6)]
    factor = n0 / length
    unit = [
        [s * s, -s * c, -s * s, s * c],
        [-s * c, c * c, s * c, -c * c],
        [-s * s, s * c, s * s, -s * c],
        [s * c, -c * c, -s * c, c * c],
    ]
    matrix = [[0.0] * 6 for _ in range(6)]
    mapping = (0, 1, 3, 4)
    for row, global_row in enumerate(mapping):
        for column, global_column in enumerate(mapping):
            matrix[global_row][global_column] = factor * unit[row][column]
    return matrix


def _geometric_local(length: float, n0: float) -> list[list[float]]:
    """Rigidez geometrica local (solo terminos transversales)."""
    matrix = [[0.0] * 6 for _ in range(6)]
    if n0 == 0.0:
        return matrix
    factor = n0 / length
    matrix[1][1] = factor
    matrix[1][4] = -factor
    matrix[4][1] = -factor
    matrix[4][4] = factor
    return matrix


def _fixed_end_forces(length: float, c: float, s: float, q: float) -> list[float]:
    """Fuerzas de extremo de una carga vertical uniforme ``q`` (positiva abajo).

    La carga se proyecta sobre los ejes locales de la barra, de modo que una
    barra inclinada recibe tanto la componente transversal como la axial.
    """
    q_local_x = -q * s
    q_local_y = -q * c
    return [
        -q_local_x * length / 2.0,
        -q_local_y * length / 2.0,
        -q_local_y * length * length / 12.0,
        -q_local_x * length / 2.0,
        -q_local_y * length / 2.0,
        q_local_y * length * length / 12.0,
    ]


def _solve_linear_system(
    model: FrameModel,
    active: list[bool],
    initial_forces: dict[int, float] | None = None,
    *,
    reference: bool = False,
) -> dict[str, Any]:
    """Ensambla y resuelve el modelo para un conjunto activo de barras.

    ``initial_forces`` son los axiles de la matriz geometrica. Si ``reference``
    es ``True`` se anaden tambien como cargas nodales equivalentes: el estado
    inicial (pretensado + peso propio) queda entonces en equilibrio y la
    solucion devuelve el incremento respecto de el.
    """
    material = model.materials[0]
    nodes = model.nodes
    node_count = len(nodes)

    # Ordenar por X y luego Y para minimizar el ancho de banda del skyline.
    order = sorted(range(node_count), key=lambda index: (nodes[index].x, nodes[index].y))
    position = [0] * node_count
    for slot, node_index in enumerate(order):
        position[node_index] = slot

    fixed = [False] * (node_count * _DOFS)
    for index, node in enumerate(nodes):
        for dof, restrained in enumerate(node.support):
            if restrained:
                fixed[position[index] * _DOFS + dof] = True

    free_index = [-1] * (node_count * _DOFS)
    free_count = 0
    for dof in range(node_count * _DOFS):
        if not fixed[dof]:
            free_index[dof] = free_count
            free_count += 1
    if free_count == 0:
        raise StructuralError("el modelo no tiene grados de libertad libres")

    start = list(range(free_count))
    member_data: list[dict[str, Any]] = []
    frame_nodes: set[int] = set()
    for index, member in enumerate(model.members):
        section = model.sections[member.section - 1]
        is_active = active[index]
        if member.kind == "truss":
            area = section.A if is_active else section.A * 1e-6
            inertia = 0.0
        else:
            area = section.A
            inertia = section.inertia
            frame_nodes.add(member.i)
            frame_nodes.add(member.j)
        node_i = nodes[member.i]
        node_j = nodes[member.j]
        global_k, local_k, transform, length, c, s = _element_stiffness(
            node_i.x, node_i.y, node_j.x, node_j.y, material.E, area, inertia
        )
        geometric_local = [[0.0] * 6 for _ in range(6)]
        initial = 0.0
        if initial_forces and member.kind == "truss":
            n0 = initial_forces.get(index, 0.0) if is_active else 0.0
            if n0:
                initial = n0
                geometric = _geometric_stiffness(c, s, length, n0)
                geometric_local = _geometric_local(length, n0)
                global_k = [
                    [global_k[row][column] + geometric[row][column] for column in range(6)]
                    for row in range(6)
                ]
        dofs = [
            position[member.i] * _DOFS,
            position[member.i] * _DOFS + 1,
            position[member.i] * _DOFS + 2,
            position[member.j] * _DOFS,
            position[member.j] * _DOFS + 1,
            position[member.j] * _DOFS + 2,
        ]
        free_dofs = [free_index[dof] for dof in dofs]
        for _local_a, global_a in enumerate(free_dofs):
            if global_a < 0:
                continue
            for _local_b, global_b in enumerate(free_dofs):
                if global_b < 0:
                    continue
                if global_a >= global_b:
                    start[global_a] = min(start[global_a], global_b)
        member_data.append(
            {
                "member": member,
                "section": section,
                "active": is_active,
                "dofs": dofs,
                "free_dofs": free_dofs,
                "k": global_k,
                "local_k": local_k,
                "geometric_local": geometric_local,
                "initial": initial,
                "transform": transform,
                "length": length,
                "c": c,
                "s": s,
                "ea": material.E * area,
                "ei": material.E * inertia,
            }
        )

    rows: list[list[float]] = [[0.0] * (i - start[i] + 1) for i in range(free_count)]
    for data in member_data:
        k = data["k"]
        free_dofs = data["free_dofs"]
        for local_a, global_a in enumerate(free_dofs):
            if global_a < 0:
                continue
            for local_b, global_b in enumerate(free_dofs):
                if global_b < 0:
                    continue
                if global_a >= global_b:
                    rows[global_a][global_b - start[global_a]] += k[local_a][local_b]

    # Regularizacion de giros en nodos que solo tienen barras truss.
    for index in range(node_count):
        if index in frame_nodes:
            continue
        dof = free_index[position[index] * _DOFS + 2]
        if dof >= 0:
            rows[dof][dof - start[dof]] += 1.0

    rhs = [0.0] * free_count
    applied_total = [0.0] * (node_count * _DOFS)
    for index, node in enumerate(nodes):
        for dof, value in enumerate(node.load):
            global_dof = position[index] * _DOFS + dof
            applied_total[global_dof] += value
            if free_index[global_dof] >= 0:
                rhs[free_index[global_dof]] += value

    for data in member_data:
        loaded_member: FrameMember = data["member"]
        if loaded_member.kind != "frame" or abs(loaded_member.uniform_load) <= 0.0:
            continue
        fixed_end = _fixed_end_forces(
            data["length"], data["c"], data["s"], loaded_member.uniform_load
        )
        equivalent = _transpose_mul(data["transform"], fixed_end)
        for dof, value in zip(data["dofs"], equivalent, strict=True):
            if free_index[dof] >= 0:
                rhs[free_index[dof]] -= value

    # Cargas nodales equivalentes del pretensado: si el estado inicial esta en
    # equilibrio con el peso propio, el sistema queda sin carga neta.
    if reference:
        for data in member_data:
            force = float(data["initial"])
            if not force:
                continue
            c = float(data["c"])
            s = float(data["s"])
            dofs = data["dofs"]
            first = (force * c, force * s, 0.0, -force * c, -force * s, 0.0)
            for local_index, value in enumerate(first):
                dof = dofs[local_index]
                if free_index[dof] >= 0:
                    rhs[free_index[dof]] += value

    rows, diagonal = _skyline_factor(rows, start)
    solution = _skyline_solve(rows, start, diagonal, rhs)

    displacements = [0.0] * (node_count * _DOFS)
    for dof in range(node_count * _DOFS):
        if free_index[dof] >= 0:
            displacements[dof] = solution[free_index[dof]]

    # Fuerzas de extremo de barra en coordenadas locales y globales.
    # R = suma(fuerzas de barra sobre el nodo) - carga exterior nodal.
    residual = [0.0] * (node_count * _DOFS)
    forces: list[dict[str, Any]] = []
    for data in member_data:
        member = data["member"]
        dofs = data["dofs"]
        local_displacements = [
            sum(data["transform"][row][column] * displacements[dofs[column]] for column in range(6))
            for row in range(6)
        ]
        local_end = _mat_vec(data["local_k"], local_displacements)
        geometric_force = _mat_vec(data["geometric_local"], local_displacements)
        local_end = [a + b for a, b in zip(local_end, geometric_force, strict=True)]
        if member.kind == "frame" and abs(member.uniform_load) > 0.0:
            fixed_end = _fixed_end_forces(data["length"], data["c"], data["s"], member.uniform_load)
            local_end = [a + b for a, b in zip(local_end, fixed_end, strict=True)]
        increment = list(local_end)
        initial = float(data["initial"])
        total_end = list(local_end)
        if initial:
            total_end[0] -= initial
            total_end[3] += initial
        balance = total_end if reference else increment
        global_end = _transpose_mul(data["transform"], balance)
        for local_index, global_dof in enumerate(dofs):
            residual[global_dof] += global_end[local_index]
        axial = total_end[3]
        if not data["active"]:
            axial = 0.0
        forces.append(
            {
                "member": member,
                "axial": axial,
                "axial_increment": increment[3],
                "shear_i": total_end[1],
                "shear_j": total_end[4],
                "moment_i": total_end[2],
                "moment_j": total_end[5],
                "local_end": total_end,
                "local_displacements": local_displacements,
            }
        )

    reactions: list[dict[str, Any]] = []
    for index, node in enumerate(nodes):
        if not any(node.support):
            continue
        values = [0.0, 0.0, 0.0]
        for dof in range(_DOFS):
            if node.support[dof]:
                global_dof = position[index] * _DOFS + dof
                values[dof] = residual[global_dof] - applied_total[global_dof]
        reactions.append(
            {
                "node": index,
                "x": node.x,
                "y": node.y,
                "support": node.support,
                "support_tag": node.support_tag or node.tag,
                "fx": values[0],
                "fy": values[1],
                "mz": values[2],
            }
        )

    return {
        "displacements": displacements,
        "node_displacements": [
            displacements[position[index] * _DOFS + dof]
            for index in range(node_count)
            for dof in range(_DOFS)
        ],
        "position": position,
        "reactions": reactions,
        "forces": forces,
        "free_dofs": free_count,
        "active": active,
    }


# ---------------------------------------------------------------------------
# Analisis: iteracion traccion-solo + rigidez geometrica
# ---------------------------------------------------------------------------


def _clone_model(
    model: FrameModel, *, name: str | None = None, load_case: str | None = None
) -> FrameModel:
    """Copia profunda del modelo (nodos y barras independientes)."""
    return FrameModel(
        name=name or model.name,
        nodes=[
            FrameNode(node.x, node.y, node.tag, node.support, node.load, node.support_tag)
            for node in model.nodes
        ],
        members=[
            FrameMember(
                member.i, member.j, member.section, member.group, member.kind, member.uniform_load
            )
            for member in model.members
        ],
        materials=list(model.materials),
        sections=list(model.sections),
        load_case=load_case or model.load_case,
        origin_index=model.origin_index,
        meta=dict(model.meta),
    )


def _member_length(model: FrameModel, member: FrameMember) -> float:
    first = model.nodes[member.i]
    second = model.nodes[member.j]
    return math.hypot(second.x - first.x, second.y - first.y)


def initial_tension(model: FrameModel) -> dict[int, float]:
    """Estimacion inicial de axiles para la matriz geometrica.

    Los cables reciben el axil horizontal que equilibra el peso propio del
    tablero y de los cables en el vano principal ( parabola ``H = W L / 8 f`` )
    y los suspensores el peso del tablero que tributan. Es solo un punto de
    partida: :func:`solve_frame` itera hasta que los axiles convergen.
    """
    meta = model.meta
    deck_load = float(meta.get("deck_load", 0.0))
    main_span = float(meta.get("main_span", 0.0))
    tower_x = float(meta.get("tower_x", main_span / 2.0))
    sag = float(meta.get("sag", 0.0))
    cable_weight = 0.0
    for node in model.nodes:
        if node.tag in ("cable", "tower_top") and abs(node.x) <= tower_x + 1e-9:
            cable_weight -= node.load[1]
    horizontal = 0.0
    if sag > 0.0:
        total = deck_load * main_span + cable_weight
        horizontal = total * main_span / (8.0 * sag)

    # Vecinos de cada nodo del cable para calcular el axil exacto que debe
    # llevar cada suspensor en el estado de peso propio.
    adjacency: dict[int, list[int]] = {}
    for index, member in enumerate(model.members):
        if member.group == "cable":
            adjacency.setdefault(member.i, []).append(index)
            adjacency.setdefault(member.j, []).append(index)

    guess: dict[int, float] = {}
    for index, member in enumerate(model.members):
        if member.group == "cable":
            first = model.nodes[member.i]
            second = model.nodes[member.j]
            length = math.hypot(second.x - first.x, second.y - first.y)
            cosine = abs(second.x - first.x) / length if length else 1.0
            guess[index] = horizontal / max(cosine, 1e-3)
        elif member.group == "hanger":
            first = model.nodes[member.i]
            second = model.nodes[member.j]
            cable_node = member.j if first.tag == "deck" else member.i
            slopes: dict[float, float] = {}
            node = model.nodes[cable_node]
            for cable_index in adjacency.get(cable_node, []):
                cable = model.members[cable_index]
                other = cable.j if cable.i == cable_node else cable.i
                dx = model.nodes[other].x - node.x
                dy = model.nodes[other].y - node.y
                if abs(dx) > 1e-9:
                    slopes[dx] = dy / dx
            vertical = 0.0
            left = [value for key, value in slopes.items() if key < 0.0]
            right = [value for key, value in slopes.items() if key > 0.0]
            if left and right:
                vertical = horizontal * (min(right) - max(left))
            weight = -node.load[1]
            guess[index] = max(vertical - weight, 0.0)
        elif member.group == "tower":
            guess[index] = 0.0
    return guess


def _solve_case(
    model: FrameModel,
    active: list[bool],
    initial_forces: dict[int, float] | None,
    tension_only: bool,
    max_iterations: int,
    *,
    reference: bool = False,
) -> dict[str, Any]:
    """Resuelve y, si procede, itera el conjunto de barras traccionadas."""
    current = list(active)
    seen: set[tuple[bool, ...]] = set()
    result = _solve_linear_system(model, current, initial_forces, reference=reference)
    iterations = 1
    if not tension_only:
        result["iterations"] = iterations
        return result
    for _ in range(max_iterations):
        key = tuple(current)
        if key in seen:
            break
        seen.add(key)
        axial = [float(item["axial"]) for item in result["forces"]]
        scale = max((abs(value) for value in axial), default=1.0) or 1.0
        force_tolerance = max(1e-3, scale * 1e-6)
        displacement_scale = max(
            (abs(value) for value in result["node_displacements"]), default=1.0
        )
        length_tolerance = max(1e-9, displacement_scale * 1e-6)
        updated = list(current)
        for index, member in enumerate(model.members):
            if member.kind != "truss":
                continue
            if current[index]:
                if axial[index] < -force_tolerance:
                    updated[index] = False
            else:
                local = result["forces"][index]["local_displacements"]
                if local[3] - local[0] > length_tolerance:
                    updated[index] = True
        if updated == current:
            break
        current = updated
        result = _solve_linear_system(model, current, initial_forces, reference=reference)
        iterations += 1
    result["iterations"] = iterations
    return result


def solve_frame(
    model: FrameModel,
    *,
    initial_forces: dict[int, float] | None = None,
    prestress: dict[int, float] | None = None,
    active: list[bool] | None = None,
    tension_only: bool = True,
    geometric: bool = True,
    reference: bool = False,
    max_iterations: int = 40,
    geometric_iterations: int = 8,
    tolerance: float = 1e-3,
) -> dict[str, Any]:
    """Resuelve el modelo iterando traccion-solo y rigidez geometrica.

    Si ``initial_forces`` es ``None`` los axiles se estiman con
    :func:`initial_tension` y se refinan hasta que la matriz geometrica deja de
    cambiar. Con ``reference=True`` esos axiles se anaden como cargas nodales
    equivalentes: el modelo esta entonces en el estado de peso propio y la
    solucion es el incremento respecto de el (practicamente nulo). ``prestress``
    se conserva por compatibilidad y se ignora.
    """
    current = list(active) if active is not None else [True] * len(model.members)
    trial = initial_forces
    result: dict[str, Any]
    if trial is None and geometric:
        trial = initial_tension(model)
        for _ in range(geometric_iterations):
            result = _solve_case(
                model,
                current,
                trial,
                tension_only,
                max_iterations,
                reference=reference,
            )
            updated = {
                index: max(float(item["axial"]), 0.0)
                for index, item in enumerate(result["forces"])
                if model.members[index].kind == "truss"
            }
            change = 0.0
            for index, value in updated.items():
                before = trial.get(index, 0.0)
                change = max(change, abs(value - before) / max(abs(value), 1.0))
            trial = updated
            current = list(result["active"])
            if change < tolerance:
                break
    else:
        result = _solve_case(
            model,
            current,
            trial if geometric else None,
            tension_only,
            max_iterations,
            reference=reference,
        )
    result["active"] = list(result.get("active", current))
    result["initial_forces"] = {index: round(value, 3) for index, value in (trial or {}).items()}
    return result


def equilibrium_check(model: FrameModel, result: dict[str, Any]) -> dict[str, Any]:
    """Comprueba el equilibrio global: cargas aplicadas + reacciones = 0.

    Incluye la suma de fuerzas en X e Y y la suma de momentos respecto al
    origen de coordenadas, de modo que detecta desequilibrios que las fuerzas
    por si solas no revelan.
    """
    applied = [0.0, 0.0, 0.0]
    for node in model.nodes:
        fx, fy, mz = node.load
        applied[0] += fx
        applied[1] += fy
        applied[2] += node.x * fy - node.y * fx + mz
    for member in model.members:
        if not member.uniform_load:
            continue
        first = model.nodes[member.i]
        second = model.nodes[member.j]
        length = _member_length(model, member)
        total = member.uniform_load * length
        applied[1] -= total
        applied[2] -= total * (first.x + second.x) / 2.0
    reactions = [0.0, 0.0, 0.0]
    for item in result["reactions"]:
        fx = float(item["fx"])
        fy = float(item["fy"])
        reactions[0] += fx
        reactions[1] += fy
        reactions[2] += float(item["x"]) * fy - float(item["y"]) * fx + float(item["mz"])
    residual = [a + b for a, b in zip(applied, reactions, strict=True)]
    scale = max(abs(applied[1]), 1.0)
    xs = [node.x for node in model.nodes]
    length_scale = (max(xs) - min(xs)) if xs else 1.0
    moment_scale = max(abs(applied[1]) * length_scale, abs(applied[2]), 1.0)

    def clean(values: list[float], digits: int) -> list[float]:
        """Redondea y normaliza el cero negativo (``-0.0`` en JSON)."""
        return [round(value, digits) + 0.0 for value in values]

    return {
        "applied": clean(applied, 3),
        "reactions": clean(reactions, 3),
        "residual": clean(residual, 6),
        "relative_error_fy": round(abs(residual[1]) / scale, 9),
        "relative_error_mz": round(abs(residual[2]) / moment_scale, 9),
    }


def _set_point_load(
    model: FrameModel, x: float, magnitude: float, *, tag: str = "deck"
) -> tuple[int, float]:
    """Aplica una carga vertical (kN, positiva hacia abajo) en el nodo mas cercano."""
    candidates = [index for index, node in enumerate(model.nodes) if node.tag == tag] or list(
        range(len(model.nodes))
    )
    index = min(candidates, key=lambda item: abs(model.nodes[item].x - x))
    node = model.nodes[index]
    node.load = (node.load[0], node.load[1] - magnitude, node.load[2])
    return index, node.x


def _find_node(model: FrameModel, tag: str) -> int:
    for index, node in enumerate(model.nodes):
        if node.tag == tag:
            return index
    raise StructuralError(f"no hay nodo con etiqueta {tag!r}")


def _nan_filter(value: float, digits: int = 4) -> float:
    """Redondea para el informe, descartando NaN/inf y el ``-0.0``.

    Sin normalizar el cero negativo, los resultados JSON acaban mostrando
    ``-0.0`` y el informe ``-0.00`` cuando el valor es nulo.
    """
    if math.isnan(value) or math.isinf(value):
        return 0.0
    return round(value, digits) + 0.0


def summarize(
    model: FrameModel,
    result: dict[str, Any],
    *,
    increment: bool = False,
) -> dict[str, Any]:
    """Resumen legible: flechas, reacciones, axiles y momentos del tablero.

    Con ``increment=True`` los axiles son el incremento respecto del estado de
    peso propio (caso de carga puntual) en lugar del axil total.
    """
    u = result["node_displacements"]
    deck = [index for index, node in enumerate(model.nodes) if node.tag == "deck"]
    if not deck:
        deck = list(range(len(model.nodes)))

    def dy(index: int) -> float:
        return float(u[index * 3 + 1])

    worst = min(deck, key=dy)
    max_deflection = -dy(worst)

    groups = {
        "cable": [index for index, member in enumerate(model.members) if member.group == "cable"],
        "hanger": [index for index, member in enumerate(model.members) if member.group == "hanger"],
        "deck": [index for index, member in enumerate(model.members) if member.group == "deck"],
        "tower": [index for index, member in enumerate(model.members) if member.group == "tower"],
    }
    forces = result["forces"]

    def axial(group: str) -> list[float]:
        key = "axial_increment" if increment else "axial"
        return [float(forces[index][key]) for index in groups[group]]

    cable_axial = axial("cable")
    hanger_axial = axial("hanger")
    hanger_total = [float(forces[index]["axial"]) for index in groups["hanger"]]
    deck_moments: list[float] = []
    hogging = 0.0
    sagging = 0.0
    for index in groups["deck"]:
        left = -float(forces[index]["moment_i"])
        right = float(forces[index]["moment_j"])
        deck_moments.extend((left, right))
        hogging = min(hogging, left, right)
        sagging = max(sagging, left, right)

    tower_drift = 0.0
    tower_base_moment = 0.0
    for index in groups["tower"]:
        member = model.members[index]
        tower_base_moment = max(tower_base_moment, abs(float(forces[index]["moment_i"])))
        for node_index in (member.i, member.j):
            tower_drift = max(tower_drift, abs(u[node_index * 3]))

    support_reactions: dict[str, dict[str, float]] = {}
    for item in result["reactions"]:
        tag = str(item["support_tag"])
        entry = support_reactions.setdefault(tag, {"fx": 0.0, "fy": 0.0, "mz": 0.0, "count": 0})
        entry["fx"] += float(item["fx"])
        entry["fy"] += float(item["fy"])
        entry["mz"] += float(item["mz"])
        entry["count"] += 1

    slack = 0
    for index, value in zip(groups["hanger"], hanger_total, strict=True):
        if not result["active"][index] or value <= 0.0:
            slack += 1

    return {
        "max_deck_deflection": _nan_filter(max_deflection),
        "max_deck_deflection_x": _nan_filter(model.nodes[worst].x, 2),
        "deck_moment_max_sagging": _nan_filter(sagging),
        "deck_moment_max_hogging": _nan_filter(hogging),
        "cable_tension_max": _nan_filter(max(cable_axial, default=0.0)),
        "cable_tension_min": _nan_filter(min(cable_axial, default=0.0)),
        "hanger_tension_max": _nan_filter(max(hanger_axial, default=0.0)),
        "hangers": len(groups["hanger"]),
        "slack_hangers": slack,
        "tower_drift_max": _nan_filter(tower_drift),
        "tower_base_moment_max": _nan_filter(tower_base_moment),
        "reactions": {
            tag: {key: _nan_filter(value) for key, value in entry.items()}
            for tag, entry in sorted(support_reactions.items())
        },
        "equilibrium": equilibrium_check(model, result),
        "iterations": result["iterations"],
        "active_truss": sum(
            1
            for index, member in enumerate(model.members)
            if member.kind == "truss" and result["active"][index]
        ),
    }


def analyze_point_load(
    model: FrameModel,
    *,
    x: float = 0.0,
    magnitude: float = 1000.0,
    geometric: bool = True,
    tension_only: bool = True,
) -> dict[str, Any]:
    """Analiza una carga puntual vertical sobre el tablero.

    Devuelve el estado de peso propio (referencia), el incremento debido a la
    carga y el total. El incremento es la respuesta linealizada sobre el estado
    de peso propio (rigidez elastica + geometrica de los cables).
    """
    if magnitude < 0:
        raise StructuralError("la carga puntual debe ser positiva (hacia abajo)")

    dead_model = _clone_model(model, load_case="Dead load")
    dead_result = solve_frame(dead_model, tension_only=False, reference=True)
    initial = {
        index: max(float(item["axial"]), 0.0)
        for index, item in enumerate(dead_result["forces"])
        if model.members[index].kind == "truss"
    }

    live_model = _clone_model(model, load_case="Point load")
    for node in live_model.nodes:
        node.load = (0.0, 0.0, 0.0)
    for member in live_model.members:
        member.uniform_load = 0.0
    node_index, applied_x = _set_point_load(live_model, x, magnitude)
    live_result = solve_frame(
        live_model,
        initial_forces=initial if geometric else None,
        tension_only=tension_only,
    )

    dead_summary = summarize(dead_model, dead_result)
    live_summary = summarize(live_model, live_result, increment=True)
    live_summary["load"] = {
        "magnitude": _nan_filter(magnitude, 3),
        "x": _nan_filter(applied_x, 3),
        "requested_x": _nan_filter(x, 3),
        "node": node_index,
        "deflection_at_load": _nan_filter(live_result["node_displacements"][node_index * 3 + 1]),
    }

    combined = {
        "cable_tension_max": _nan_filter(
            dead_summary["cable_tension_max"] + live_summary["cable_tension_max"]
        ),
        "cable_tension_min": _nan_filter(
            dead_summary["cable_tension_min"] + live_summary["cable_tension_min"]
        ),
        "hanger_tension_max": _nan_filter(
            dead_summary["hanger_tension_max"] + live_summary["hanger_tension_max"]
        ),
        "reactions": {
            tag: {
                key: (
                    value
                    if key == "count"
                    else _nan_filter(live_summary["reactions"].get(tag, {}).get(key, 0.0) + value)
                )
                for key, value in entry.items()
            }
            for tag, entry in dead_summary["reactions"].items()
        },
        "deck_moment_max_sagging": _nan_filter(
            dead_summary["deck_moment_max_sagging"] + live_summary["deck_moment_max_sagging"]
        ),
        "deck_moment_max_hogging": _nan_filter(
            dead_summary["deck_moment_max_hogging"] + live_summary["deck_moment_max_hogging"]
        ),
    }

    return {
        "model": _model_info(model),
        "dead_load": dead_summary,
        "point_load": live_summary,
        "combined": combined,
        "solver": {
            "method": "rigidez directa 2D (skyline LDL^T)",
            "geometric_stiffness": geometric,
            "tension_only": tension_only,
            "units": "kN, m, rad",
        },
    }


def _model_info(model: FrameModel) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for member in model.members:
        counts[member.group] = counts.get(member.group, 0) + 1
    return {
        "name": model.name,
        "nodes": len(model.nodes),
        "members": len(model.members),
        "members_by_group": dict(sorted(counts.items())),
        "sections": [section.name for section in model.sections],
        "material": model.materials[0].name if model.materials else "",
        "extents": [round(value, 3) for value in model.bbox()],
        "meta": model.meta,
    }


# ---------------------------------------------------------------------------
# Modelo 2D del Golden Gate
# ---------------------------------------------------------------------------

STEEL = Material("A36 Steel", 2.0e8, 0.3, 78.5, 1.2e-5)

# Secciones equivalentes del plano longitudinal (las dos celosias y los dos
# cables se suman en una sola barra 2D). A en m2, I en m4.
SECTIONS = {
    "deck": Section("Deck truss 2x", 1.4, 12.0),
    "cable": Section("Main cable 2x D0.92", 1.33, 0.0),
    "hanger": Section("Hanger pair", 0.016, 0.0),
    "tower": Section("Tower leg pair", 10.0, 120.0),
}


def build_suspension_model(
    preset: str = "golden_gate",
    *,
    deck_load: float = 190.0,
    cable_load: float = 104.0,
    tower_load: float = 785.0,
    hanger_spacing: float | None = None,
    side_sag: float = 0.0,
) -> FrameModel:
    """Construye el modelo de barras 2D del puente colgante (plano X-Y).

    El tablero es continuo y se apoya en estribos, pilas y torres; los cables
    principales son barras ``truss`` con la geometria real (flecha 143 m), los
    suspensores verticales cada 15.24 m y las torres empotradas en la base. El
    peso propio del tablero y de las torres entra como carga uniforme; el de
    los cables como carga nodal (tributaria) para no perder la componente
    axial en las barras inclinadas.

    Los anclajes se situan al final de los vanos laterales (x = +/-983 m), a
    nivel del tablero y 50 mm por fuera del apoyo de la pila, y las
    aproximaciones continuan hasta los estribos (x = +/-1368.5 m) sobre pilas
    cada 64 m.

    Unidades: kN, m. Las cargas verticales son positivas hacia abajo.
    """
    if preset not in PRESETS:
        raise StructuralError(f"preset desconocido: {preset!r}")
    spec = PRESETS[preset]
    total = float(spec["total_length"])
    main_span = float(spec["main_span"])
    side_span = float(spec["side_span"])
    tower_y = float(spec["tower_height"])
    deck_y = float(spec["clearance"])
    sag = float(spec["cable_sag"])
    spacing = float(hanger_spacing or spec["suspender_spacing"])

    half = total / 2.0
    tower_x = main_span / 2.0
    pier_x = tower_x + side_span
    cable_low = tower_y - sag
    y_pier = deck_y

    # Flecha del vano lateral coherente con el axil horizontal del vano
    # principal (misma cuerda continua sobre la torre).
    cable_length = main_span * (1.0 + 8.0 / 3.0 * (sag / main_span) ** 2)
    horizontal = (deck_load * main_span + cable_load * cable_length) * main_span / (8.0 * sag)
    funicular = (deck_load + cable_load * 1.01) * side_span * side_span / (8.0 * horizontal)
    if side_sag <= 0.0:
        side_sag = funicular

    n_main = max(2, round(tower_x / spacing))
    sp_main = tower_x / n_main
    n_side = max(2, round(side_span / sp_main))
    sp_side = side_span / n_side
    approach = half - pier_x
    n_app = max(2, round(approach / 64.0))
    sp_app = approach / n_app

    half_x: list[float] = [0.0]
    half_x += [index * sp_main for index in range(1, n_main + 1)]
    half_x += [tower_x + index * sp_side for index in range(1, n_side + 1)]
    half_x += [pier_x + index * sp_app for index in range(1, n_app + 1)]
    xs = [-value for value in reversed(half_x)] + half_x[1:]

    def cable_y(x: float) -> float:
        ax = abs(x)
        if ax <= tower_x:
            return cable_low + sag * (ax / tower_x) ** 2
        if ax <= pier_x:
            t = (ax - tower_x) / side_span
            chord = tower_y + (y_pier - tower_y) * t
            return chord - 4.0 * side_sag * t * (1.0 - t)
        return y_pier

    nodes: list[FrameNode] = []
    deck_index: dict[float, int] = {}
    for x in xs:
        ax = abs(x)
        support: tuple[bool, bool, bool] = (False, False, False)
        support_tag = ""
        if ax >= pier_x - 1e-9 or abs(ax - tower_x) < 1e-9:
            support = (True, True, False) if x <= -half + 1e-9 else (False, True, False)
            if ax >= half - 1e-9:
                support_tag = "abutment"
            elif ax >= pier_x - 1e-9:
                support_tag = "pier"
            else:
                support_tag = "tower"
        deck_index[round(x, 6)] = len(nodes)
        nodes.append(FrameNode(x, deck_y, "deck", support=support, support_tag=support_tag))

    # Nodos del cable en el vano principal y en los vanos laterales. Los
    # anclajes son nudos independientes del tablero, al nivel del tablero y
    # ligeramente por fuera del apoyo de pila (ver mas abajo).
    cable_path: list[int] = []
    for x in xs:
        ax = abs(x)
        if ax >= pier_x - 1e-9:
            continue
        cable_path.append(len(nodes))
        nodes.append(
            FrameNode(
                x,
                cable_y(x),
                "tower_top" if abs(ax - tower_x) < 1e-9 else "cable",
            )
        )
    # El macizo de anclaje se situa a nivel del tablero y 50 mm por fuera del
    # apoyo de la pila. Ese desfase evita dos problemas: FTOOL fusiona nodos con
    # la misma coordenada (tolerancia de 1 mm) y se perderia el apoyo de rodillo
    # del tablero, y ademas mantiene la pendiente del cable decreciente hacia el
    # anclaje; si el anclaje baja de ese nivel la ultima barra se hace convexa y
    # aparecen compresiones falsas en los suspensores extremos.
    anchor_offset = 0.05
    anchors: list[int] = []
    for sign in (-1.0, 1.0):
        anchors.append(len(nodes))
        nodes.append(
            FrameNode(
                sign * (pier_x + anchor_offset),
                y_pier,
                "anchorage",
                support=(True, True, True),
                support_tag="anchorage",
            )
        )

    members: list[FrameMember] = []
    section_index = {name: index + 1 for index, name in enumerate(SECTIONS)}
    sections = list(SECTIONS.values())

    for left, right in zip(xs, xs[1:], strict=False):
        members.append(
            FrameMember(
                deck_index[round(left, 6)],
                deck_index[round(right, 6)],
                section_index["deck"],
                "deck",
                "frame",
                deck_load,
            )
        )

    ordered_cable = [
        anchors[0],
        *cable_path,
        anchors[1],
    ]
    for first, second in zip(ordered_cable, ordered_cable[1:], strict=False):
        members.append(FrameMember(first, second, section_index["cable"], "cable", "truss"))

    hangers = 0
    for index in cable_path:
        node = nodes[index]
        if abs(abs(node.x) - tower_x) < 1e-9:
            continue
        if node.y - deck_y < 4.0:
            continue
        members.append(
            FrameMember(
                deck_index[round(node.x, 6)],
                index,
                section_index["hanger"],
                "hanger",
                "truss",
            )
        )
        hangers += 1

    for sign in (-1.0, 1.0):
        base = len(nodes)
        nodes.append(
            FrameNode(
                sign * tower_x,
                0.0,
                "tower",
                support=(True, True, True),
                support_tag="tower_base",
            )
        )
        top = next(index for index in cable_path if abs(nodes[index].x - sign * tower_x) < 1e-9)
        members.append(FrameMember(base, top, section_index["tower"], "tower", "frame", tower_load))

    # Peso propio de los cables como carga nodal tributaria.
    path_lengths: list[float] = []
    for first, second in zip(ordered_cable, ordered_cable[1:], strict=False):
        path_lengths.append(
            math.hypot(nodes[second].x - nodes[first].x, nodes[second].y - nodes[first].y)
        )
    for position, index in enumerate(ordered_cable):
        before = path_lengths[position - 1] if position > 0 else 0.0
        after = path_lengths[position] if position < len(path_lengths) else 0.0
        weight = cable_load * (before + after) / 2.0
        if weight <= 0.0:
            continue
        node = nodes[index]
        node.load = (node.load[0], node.load[1] - weight, node.load[2])
    # El peso de cable tributario del nudo de la torre se deja en ese nudo: la
    # torre lo transmite directamente a su base, que es lo que ocurre en la
    # realidad. Antes se trasladaba al nudo contiguo porque la torre era el nudo
    # raiz del ``.ftl``; ahora el origen es el anclaje, asi que ese motivo ya no
    # aplica.

    return FrameModel(
        name=f"{spec['name']} - modelo 2D",
        nodes=nodes,
        members=members,
        materials=[STEEL],
        sections=sections,
        load_case="Dead load",
        meta={
            "preset": preset,
            "total_length": total,
            "main_span": main_span,
            "side_span": side_span,
            "tower_x": tower_x,
            "pier_x": pier_x,
            "anchor_offset": anchor_offset,
            "approach_piers": n_app,
            "approach_spacing": round(sp_app, 4),
            "deck_y": deck_y,
            "tower_y": tower_y,
            "cable_low": cable_low,
            "sag": sag,
            "side_sag": round(side_sag, 4),
            "hanger_spacing": round(sp_main, 4),
            "hangers": hangers,
            "deck_load": deck_load,
            "cable_load": cable_load,
            "tower_load": tower_load,
        },
    )


# ---------------------------------------------------------------------------
# Exportacion a FTOOL (.ftl 4.01)
# ---------------------------------------------------------------------------
_FTL_TOLERANCE = 1e-3


def _ftl_float(value: float, digits: int = 5) -> str:
    """Formatea un flotante con exponente de tres digitos (``+4.00000e+000``)."""
    if not math.isfinite(value):
        raise StructuralError("el .ftl no admite valores no finitos")
    if value == 0.0:
        value = 0.0  # evita escribir "-0.00000e+000"
    mantissa, exponent = f"{value:+.{digits}e}".split("e")
    return f"{mantissa}e{int(exponent):+04d}"


def _ftl_compact(value: float) -> str:
    """Flotante compacto para materiales, secciones y cargas."""
    if not math.isfinite(value):
        raise StructuralError("el .ftl no admite valores no finitos")
    if value == 0.0:
        return "0"
    if float(value).is_integer() and abs(value) < 1e9:
        return str(int(value))
    text = f"{value:.6g}"
    if "e" in text:
        mantissa, exponent = text.split("e")
        return f"{mantissa}e{int(exponent):+04d}"
    return text


def _ftl_name(name: str) -> str:
    """Nombre seguro para el formato: ASCII, sin comillas ni saltos de linea.

    FTOOL guarda los ``.ftl`` en Latin-1; se eliminan los acentos para que el
    archivo sea identico en cualquier configuracion regional.
    """
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    clean = " ".join(ascii_name.replace("'", " ").split())
    return clean[:60] or "unnamed"


def _ftl_support(support: tuple[bool, bool, bool]) -> str:
    states = " ".join("1" if value else "0" for value in support)
    return f"0 {states} {_ftl_float(0.0, 8)}"


def _ftl_flags(member: FrameMember) -> str:
    """Barras ``truss`` con articulacion en ambos extremos."""
    return "0 1 1 0 0 1" if member.kind == "truss" else "0 0 0 0 0 1"


def _section_inertia(section: Section) -> float:
    """Inercia exportable: FTOOL necesita I > 0 aunque la barra sea articulada."""
    return max(section.inertia, 1e-9)


def _ftl_bbox(first: FrameNode, second: FrameNode) -> str:
    values = (
        min(first.x, second.x),
        max(first.x, second.x),
        min(first.y, second.y),
        max(first.y, second.y),
    )
    return " ".join(_ftl_float(value) for value in values)


class _UnionFind:
    """Union-find para construir el arbol de expansion del modelo."""

    def __init__(self, size: int) -> None:
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, first: int, second: int) -> bool:
        root_a = self.find(first)
        root_b = self.find(second)
        if root_a == root_b:
            return False
        if self.rank[root_a] < self.rank[root_b]:
            root_a, root_b = root_b, root_a
        self.parent[root_b] = root_a
        if self.rank[root_a] == self.rank[root_b]:
            self.rank[root_a] += 1
        return True


def _merge_coincident_nodes(
    model: FrameModel, tolerance: float = _FTL_TOLERANCE
) -> tuple[FrameModel, int]:
    """Fusiona nodos con la misma coordenada (tolerancia 1 mm).

    FTOOL deriva la topologia de las coordenadas: dos nudos en el mismo punto
    son el mismo nudo. Los apoyos se suman (OR) y las cargas se acumulan.
    """
    clone = _clone_model(model)
    kept: list[int] = []
    remap = [-1] * len(clone.nodes)
    for index, node in enumerate(clone.nodes):
        target = -1
        for candidate in kept:
            other = clone.nodes[candidate]
            if abs(other.x - node.x) <= tolerance and abs(other.y - node.y) <= tolerance:
                target = candidate
                break
        if target < 0:
            kept.append(index)
            remap[index] = index
            continue
        other = clone.nodes[target]
        other.support = (
            other.support[0] or node.support[0],
            other.support[1] or node.support[1],
            other.support[2] or node.support[2],
        )
        other.load = (
            other.load[0] + node.load[0],
            other.load[1] + node.load[1],
            other.load[2] + node.load[2],
        )
        if node.support_tag and not other.support_tag:
            other.support_tag = node.support_tag
        remap[index] = target
    if len(kept) == len(clone.nodes):
        return clone, 0
    position = {old: new for new, old in enumerate(kept)}
    members: list[FrameMember] = []
    seen: set[tuple[int, int, int, str]] = set()
    for member in clone.members:
        first = position[remap[member.i]]
        second = position[remap[member.j]]
        if first == second:
            continue
        key = (min(first, second), max(first, second), member.section, member.group)
        if key in seen:
            continue
        seen.add(key)
        members.append(
            FrameMember(
                first,
                second,
                member.section,
                member.group,
                member.kind,
                member.uniform_load,
            )
        )
    clone.nodes = [clone.nodes[index] for index in kept]
    clone.members = members
    return clone, len(model.nodes) - len(kept)


def _spanning_tree(model: FrameModel) -> tuple[list[int], list[int]]:
    """Arbol de expansion que deja solo barras de tablero como conectores.

    Se incorporan primero cables, torres y suspensores; asi los ciclos que
    cierran las barras del tablero (horizontales) son los unicos conectores y
    su bbox no es ambigua.
    """
    priority = {"cable": 0, "tower": 1, "hanger": 2, "deck": 3}
    order = sorted(
        range(len(model.members)),
        key=lambda index: (
            priority.get(model.members[index].group, 4),
            0 if model.members[index].kind == "truss" else 1,
            index,
        ),
    )
    union = _UnionFind(len(model.nodes))
    tree: list[int] = []
    connectors: list[int] = []
    for index in order:
        member = model.members[index]
        if union.union(member.i, member.j):
            tree.append(index)
        else:
            connectors.append(index)
    return sorted(tree), sorted(connectors)


def _creation_order(model: FrameModel, tree: list[int], origin: int) -> list[tuple[int, int, int]]:
    """Ordena las barras del arbol como ``(barra, padre, hijo)`` por niveles."""
    adjacency: dict[int, list[tuple[int, int]]] = {}
    for index in tree:
        member = model.members[index]
        adjacency.setdefault(member.i, []).append((member.j, index))
        adjacency.setdefault(member.j, []).append((member.i, index))
    visited = {origin}
    queue = [origin]
    result: list[tuple[int, int, int]] = []
    while queue:
        parent = queue.pop(0)
        for child, member_index in adjacency.get(parent, []):
            if child in visited:
                continue
            visited.add(child)
            queue.append(child)
            result.append((member_index, parent, child))
    if len(visited) != len(model.nodes):
        raise StructuralError("el modelo no es conexo: no se puede exportar a FTOOL")
    return result


def _prepare_ftl_model(model: FrameModel) -> tuple[FrameModel, dict[str, Any]]:
    """Copia fusionada y trasladada para que el nudo de menor x quede en (0, 0).

    FTOOL toma ese nudo como origen, y no admite carga nodal en el.
    """
    if not model.materials or not model.sections:
        raise StructuralError("el .ftl necesita al menos un material y una seccion")
    if len(model.nodes) < 2 or not model.members:
        raise StructuralError("el modelo esta vacio")
    merged, merged_nodes = _merge_coincident_nodes(model)
    for member in merged.members:
        if not 1 <= member.section <= len(merged.sections):
            raise StructuralError(f"barra con seccion invalida: {member.section}")
    origin = min(
        range(len(merged.nodes)),
        key=lambda index: (merged.nodes[index].x, merged.nodes[index].y),
    )
    node = merged.nodes[origin]
    if node.load != (0.0, 0.0, 0.0):
        raise StructuralError("FTOOL no permite carga nodal en el nudo origen (0, 0)")
    offset_x = node.x
    offset_y = node.y
    for item in merged.nodes:
        item.x -= offset_x
        item.y -= offset_y
    return merged, {
        "merged_nodes": merged_nodes,
        "origin": [round(offset_x, 3), round(offset_y, 3)],
        "nodes": len(merged.nodes),
        "members": len(merged.members),
    }


def model_to_ftl(model: FrameModel, *, title: str | None = None) -> str:
    """Serializa el modelo 2D al formato ``.ftl`` de FTOOL 4.01.

    El archivo contiene un unico caso de carga (limitacion de la edicion
    estandar). Las cargas nodales se escriben con el signo de FTOOL (positivo
    hacia arriba) a partir de la convencion interna (positivo hacia abajo).
    """
    prepared, info = _prepare_ftl_model(model)
    nodes = prepared.nodes
    # El origen trasladado siempre es la primera coordenada (0, 0).
    origin = next(index for index, node in enumerate(nodes) if node.x == 0.0 and node.y == 0.0)

    nodal_defs: list[tuple[float, float, float]] = []
    nodal_index: dict[tuple[float, float, float], int] = {}
    node_load: dict[int, int] = {}
    for index, node in enumerate(nodes):
        key = (round(node.load[0], 6), round(node.load[1], 6), round(node.load[2], 6))
        if key == (0.0, 0.0, 0.0):
            continue
        if key not in nodal_index:
            nodal_index[key] = len(nodal_defs) + 1
            nodal_defs.append(key)
        node_load[index] = nodal_index[key]

    uniform_defs: list[float] = []
    uniform_index: dict[float, int] = {}
    for member in prepared.members:
        value = round(member.uniform_load, 6)
        if value == 0.0:
            continue
        if value not in uniform_index:
            uniform_index[value] = len(uniform_defs) + 1
            uniform_defs.append(value)

    tree, connectors = _spanning_tree(prepared)
    creation = _creation_order(prepared, tree, origin)

    xs = [node.x for node in nodes]
    ys = [node.y for node in nodes]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    viewport = " ".join(_ftl_float(value) for value in (xmin, xmax, ymin, ymax))

    lines = [
        "401 0",
        "206",
        "1",
        (
            f"0 1 {max(1, len(prepared.materials))} {max(1, len(prepared.sections))} "
            f"{len(nodes) - 1} {len(nodes) + 1} {len(prepared.members) + 1} 0 0 0 0"
        ),
        f"{_ftl_float((xmin + xmax) / 2.0)} {_ftl_float((ymin + ymax) / 2.0)}",
        viewport,
        "0.01 0.01",
        "1 0 1 0 1 1 1 0 0 0 1 1 0 0 0",
        "0 0",
        "3 131075 4 33 65 129 147969 1025 2049 257",
        "131075 131081 131089 4097 8193 65545 131075",
        "4 7 7 2 8 2 8 4 0 2",
        "12 0 0 9 9 7 7 4 2 6",
        "1 1",
        "0 1 1 1 1 0",
        "1 1 0",
        "1",
        f"'{_ftl_name(title or prepared.load_case)}' 1",
        "0",
        str(len(nodal_defs)),
    ]
    for fx, fy, mz in nodal_defs:
        lines.append(f"'Nodal' {_ftl_compact(fx)} {_ftl_compact(-fy)} {_ftl_compact(mz)}")
    lines.append("0")
    lines.append(str(len(uniform_defs)))
    lines.extend(f"0 'Uniform' 0 {_ftl_compact(-value)}" for value in uniform_defs)
    lines.append("0")
    lines.append("0")
    lines.append(str(len(prepared.materials)))
    for material in prepared.materials:
        lines.append(f"'{_ftl_name(material.name)}' 0")
        lines.append(
            " "
            + " ".join(
                _ftl_compact(value)
                for value in (material.E, material.nu, material.rho, material.alpha)
            )
        )
    lines.append(str(len(prepared.sections)))
    for section in prepared.sections:
        lines.append(f"'{_ftl_name(section.name)}' 0 0")
        lines.append(
            " "
            + " ".join(
                _ftl_compact(value)
                for value in (section.A, 0.0, _section_inertia(section), 0.0, 0.0, 0.0)
            )
        )
    lines.extend(
        [
            "0",
            "0",
            _ftl_support(nodes[origin].support),
            "0 0 0",
            "0",
            "0 0 0 0",
        ]
    )

    node_ids = {origin: 0}
    created = 0
    block = 0
    for member_index, parent, child in creation:
        created += 1
        block += 1
        node_ids[child] = created
        member = prepared.members[member_index]
        first = nodes[child]
        second = nodes[parent]
        lines.extend(
            [
                "1",
                f"2 1 1 1 1 {2 * created - 1} {2 * created - 1} {created + 2} 1 1 {block + 1}",
                f"{_ftl_float(first.x)} {_ftl_float(first.y)}",
                "0",
                _ftl_bbox(first, second),
                _ftl_flags(member),
                "1",
                str(member.section),
                "0",
                str(uniform_index.get(round(member.uniform_load, 6), 0)),
                "0",
                "0",
                _ftl_support(first.support),
                "0 0 0",
                str(node_load.get(child, 0)),
                "0 0 0 0",
            ]
        )
    for member_index in connectors:
        block += 1
        member = prepared.members[member_index]
        first = nodes[member.i]
        second = nodes[member.j]
        reference = max(node_ids[member.i], node_ids[member.j])
        lines.extend(
            [
                "1",
                (
                    f"4 1 1 {2 * created - 1} 1 {created + 2} 1 {reference} "
                    f"{created + 2} 1 {block + 1}"
                ),
                viewport,
                "0",
                _ftl_bbox(first, second),
                "0 0 0 0 0 1",
                "1",
                str(member.section),
                "0",
                str(uniform_index.get(round(member.uniform_load, 6), 0)),
                "0",
                "0",
            ]
        )
    lines.append(" 0")
    return "\n".join(lines) + "\n"


def _corner_key(point: tuple[float, float]) -> tuple[float, float]:
    return (round(point[0], 3), round(point[1], 3))


def _opposite_corner(
    point: tuple[float, float], bbox: tuple[float, float, float, float]
) -> tuple[float, float]:
    """Esquina diagonalmente opuesta del bbox (convencion de FTOOL)."""
    xmin, xmax, ymin, ymax = bbox
    on_xmin = abs(point[0] - xmin) <= _FTL_TOLERANCE
    on_xmax = abs(point[0] - xmax) <= _FTL_TOLERANCE
    on_ymin = abs(point[1] - ymin) <= _FTL_TOLERANCE
    on_ymax = abs(point[1] - ymax) <= _FTL_TOLERANCE
    if on_xmin and on_ymin:
        return (xmax, ymax)
    if on_xmax and on_ymax:
        return (xmin, ymin)
    if on_xmin and on_ymax:
        return (xmax, ymin)
    if on_xmax and on_ymin:
        return (xmin, ymax)
    raise StructuralError("la coordenada no coincide con una esquina del bbox")


def _parse_quoted(line: str) -> tuple[str, str]:
    """Separa el nombre entre comillas del resto de la linea.

    Las cargas uniformes llevan un flag numerico antes del nombre
    (``0 'Uniform' 0 -12``), por eso se busca la primera comilla en cualquier
    posicion y no solo al principio.
    """
    text = line.strip()
    start = text.find("'")
    if start < 0:
        parts = text.split(maxsplit=1)
        return parts[0], parts[1] if len(parts) > 1 else ""
    end = text.find("'", start + 1)
    if end < 0:
        raise StructuralError(f"nombre sin cerrar: {line!r}")
    return text[start + 1 : end], text[end + 1 :].strip()


def _existing_corners(
    bbox: tuple[float, float, float, float], node_index: dict[tuple[float, float], int]
) -> tuple[int, int]:
    """Devuelve los dos nudos existentes de un conector a partir de su bbox."""
    xmin, xmax, ymin, ymax = bbox
    if abs(xmax - xmin) <= _FTL_TOLERANCE or abs(ymax - ymin) <= _FTL_TOLERANCE:
        points = {
            _corner_key((xmin, ymin)),
            _corner_key((xmax, ymin)),
            _corner_key((xmin, ymax)),
            _corner_key((xmax, ymax)),
        }
        existing = sorted(point for point in points if point in node_index)
        if len(existing) != 2:
            raise StructuralError("conector degenerado con nudos inexistentes")
        return node_index[existing[0]], node_index[existing[1]]
    main = (_corner_key((xmin, ymin)), _corner_key((xmax, ymax)))
    anti = (_corner_key((xmin, ymax)), _corner_key((xmax, ymin)))
    main_ok = all(point in node_index for point in main)
    anti_ok = all(point in node_index for point in anti)
    if main_ok and not anti_ok:
        return node_index[main[0]], node_index[main[1]]
    if anti_ok and not main_ok:
        return node_index[anti[0]], node_index[anti[1]]
    raise StructuralError("conector ambiguo: las dos diagonales existen")


def parse_ftl(text: str) -> FrameModel:
    """Lee un ``.ftl`` 4.01 y reconstruye el modelo de barras 2D.

    Se usa para verificar la ida y vuelta del exportador. La topologia se
    deriva de las coordenadas, igual que hace FTOOL.
    """
    lines = text.splitlines()
    if len(lines) < 40 or not lines[0].strip().startswith("401"):
        raise StructuralError("no es un archivo .ftl de FTOOL 4.01")
    index = 16
    cases = int(lines[index].strip())
    if cases < 1:
        raise StructuralError("el .ftl no tiene casos de carga")
    index += 1
    load_case, _ = _parse_quoted(lines[index])
    index += 2
    nodal_defs: list[tuple[float, float, float]] = []
    for _ in range(int(lines[index].strip())):
        index += 1
        _, rest = _parse_quoted(lines[index])
        values = [float(value) for value in rest.split()]
        nodal_defs.append((values[0], values[1], values[2]))
    index += 2
    uniform_defs: list[float] = []
    for _ in range(int(lines[index].strip())):
        index += 1
        _, rest = _parse_quoted(lines[index])
        values = [float(value) for value in rest.split()]
        uniform_defs.append(values[1])
    index += 2
    index += 1 + int(lines[index].strip())
    materials: list[Material] = []
    for _ in range(int(lines[index].strip())):
        index += 1
        name, _ = _parse_quoted(lines[index])
        index += 1
        values = [float(value) for value in lines[index].split()]
        materials.append(Material(name, values[0], values[1], values[2], values[3]))
    index += 1
    sections: list[Section] = []
    for _ in range(int(lines[index].strip())):
        index += 1
        name, _ = _parse_quoted(lines[index])
        index += 1
        values = [float(value) for value in lines[index].split()]
        inertia = values[1] if len(values) == 2 else values[2]
        sections.append(Section(name, values[0], inertia))
    index += 3
    support = [int(value) for value in lines[index].split()[:4]]
    index += 4

    nodes: list[FrameNode] = [
        FrameNode(
            0.0,
            0.0,
            "origin",
            (bool(support[1]), bool(support[2]), bool(support[3])),
            support_tag="origin",
        )
    ]
    node_index: dict[tuple[float, float], int] = {(0.0, 0.0): 0}
    members: list[FrameMember] = []

    def node_at(point: tuple[float, float]) -> int:
        key = _corner_key(point)
        if key not in node_index:
            node_index[key] = len(nodes)
            nodes.append(FrameNode(point[0], point[1], "imported"))
        return node_index[key]

    while index < len(lines):
        marker = lines[index].strip()
        if not marker or marker == "0":
            break
        if marker != "1":
            raise StructuralError(f"bloque inesperado en la linea {index + 1}: {lines[index]!r}")
        header = [int(value) for value in lines[index + 1].split()]
        flags = [int(value) for value in lines[index + 5].split()]
        kind = "truss" if flags[1] and flags[2] else "frame"
        if header[0] == 2:
            start = [float(value) for value in lines[index + 2].split()]
            bbox = tuple(float(value) for value in lines[index + 4].split())
            if len(bbox) != 4:
                raise StructuralError("bbox invalida en bloque 2 1")
            second = _opposite_corner((start[0], start[1]), bbox)
            node = node_at((start[0], start[1]))
            other = node_at(second)
            values = [int(value) for value in lines[index + 12].split()[:4]]
            nodes[node].support = (bool(values[1]), bool(values[2]), bool(values[3]))
            load_id = int(lines[index + 14].strip())
            if load_id:
                fx, fy, mz = nodal_defs[load_id - 1]
                nodes[node].load = (fx, -fy, mz)
            uniform_id = int(lines[index + 9].strip())
            members.append(
                FrameMember(
                    node,
                    other,
                    int(lines[index + 7].strip()),
                    "imported",
                    kind,
                    -uniform_defs[uniform_id - 1] if uniform_id else 0.0,
                )
            )
            index += 16
        elif header[0] == 4:
            bbox = tuple(float(value) for value in lines[index + 4].split())
            if len(bbox) != 4:
                raise StructuralError("bbox invalida en bloque 4 1")
            node_a, node_b = _existing_corners(bbox, node_index)
            uniform_id = int(lines[index + 9].strip())
            members.append(
                FrameMember(
                    node_a,
                    node_b,
                    int(lines[index + 7].strip()),
                    "imported",
                    kind,
                    -uniform_defs[uniform_id - 1] if uniform_id else 0.0,
                )
            )
            index += 12
        else:
            raise StructuralError(f"tipo de bloque desconocido: {header[0]}")
    return FrameModel(
        name="FTOOL import",
        nodes=nodes,
        members=members,
        materials=materials,
        sections=sections,
        load_case=load_case,
    )


def _quantized(value: float, digits: int = 5) -> float:
    """Redondea como el formato de 5 decimales del ``.ftl``.

    Se usa para comparar ida y vuelta: el archivo solo guarda 5 decimales de
    mantisa, asi que comparar con la precision original daria diferencias
    falsas de decimas de milimetro.
    """
    return float(f"{value:.{digits}e}")


def _compact_value(value: float) -> float:
    """Valor tal como lo reconstruye el parser tras ``_ftl_compact``."""
    return float(_ftl_compact(value))


def _normalized_model(model: FrameModel) -> dict[str, Any]:
    """Vista sin orden ni etiquetas, a la precision real del archivo."""
    nodes = sorted(
        (
            _quantized(node.x),
            _quantized(node.y),
            tuple(node.support),
            tuple(_compact_value(value) for value in node.load),
        )
        for node in model.nodes
    )
    members = sorted(
        (
            tuple(
                sorted(
                    (
                        (_quantized(model.nodes[member.i].x), _quantized(model.nodes[member.i].y)),
                        (_quantized(model.nodes[member.j].x), _quantized(model.nodes[member.j].y)),
                    )
                )
            ),
            member.section,
            _compact_value(member.uniform_load),
            member.kind,
        )
        for member in model.members
    )
    materials = sorted(
        (
            material.name,
            _compact_value(material.E),
            _compact_value(material.nu),
            _compact_value(material.rho),
            _compact_value(material.alpha),
        )
        for material in model.materials
    )
    sections = sorted(
        (section.name, _compact_value(section.A), _compact_value(_section_inertia(section)))
        for section in model.sections
    )
    return {
        "nodes": nodes,
        "members": members,
        "materials": materials,
        "sections": sections,
    }


def verify_ftl(model: FrameModel) -> dict[str, Any]:
    """Exporta, reimporta y compara el modelo (ida y vuelta)."""
    text = model_to_ftl(model)
    prepared, info = _prepare_ftl_model(model)
    parsed = parse_ftl(text)
    expected = _normalized_model(prepared)
    actual = _normalized_model(parsed)
    differences = [
        f"{key}: esperado {len(expected[key])}, obtenido {len(actual[key])}"
        for key in ("nodes", "members", "materials", "sections")
        if expected[key] != actual[key]
    ]
    return {
        "ok": not differences,
        "nodes": len(parsed.nodes),
        "members": len(parsed.members),
        "materials": len(parsed.materials),
        "sections": len(parsed.sections),
        "merged_nodes": info["merged_nodes"],
        "origin_offset": info["origin"],
        "lines": len(text.splitlines()),
        "differences": differences,
    }


# ---------------------------------------------------------------------------
# Herramientas MCP de FTOOL
# ---------------------------------------------------------------------------
class FToolTools:
    """Estado de FTOOL, exportacion ``.ftl`` y analisis de cargas."""

    def __init__(self, config: AutoCADMCPConfig | None = None) -> None:
        self.config = config or get_config()

    def _output_dir(self) -> Path:
        configured = (self.config.ftool_output_dir or "").strip()
        if configured:
            return Path(configured).expanduser()
        return Path.home() / "Documents" / "BlancaNieves" / "salida"

    def _resolve_exe(self) -> str | None:
        configured = (self.config.ftool_exe or "").strip()
        if configured:
            candidate = Path(configured).expanduser()
            if candidate.is_file():
                return str(candidate)
            found = shutil.which(configured)
            if found:
                return found
        for name in ("Ftool", "ftool", "Ftool.exe", "ftool.exe"):
            found = shutil.which(name)
            if found:
                return found
        roots = [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
            Path(os.environ.get("LOCALAPPDATA", "")),
        ]
        for root in roots:
            if not root or not root.is_dir():
                continue
            for folder in sorted(root.glob("Ftool*")):
                if not folder.is_dir():
                    continue
                for exe in folder.rglob("Ftool.exe"):
                    return str(exe)
        return None

    def status(self) -> dict[str, Any]:
        exe = self._resolve_exe()
        return {
            "success": True,
            "installed": exe is not None,
            "ftool_exe": exe or "",
            "configured_exe": self.config.ftool_exe,
            "output_dir": str(self._output_dir()),
            "format": "FTL 4.01",
            "format_reference": FTOOL_FORMAT,
            "manual": FTOOL_MANUAL,
            "engine": "solver 2D interno (rigidez directa, P-Delta, traccion-solo)",
            "limitations": [
                "FTOOL no guarda resultados: abrir el .ftl y pulsar Solve.",
                "El .ftl es lineal (sin rigidez geometrica): las flechas difieren "
                "del solver interno.",
                "Solo un caso de carga (edicion estandar de FTOOL).",
                "La carga puntual debe incluirse al exportar (load_kN) para verla en FTOOL.",
            ],
        }

    def export_model(
        self,
        preset: str = "golden_gate",
        path: str | None = None,
        load_x: float = 0.0,
        load_kN: float = 0.0,
    ) -> dict[str, Any]:
        model = build_suspension_model(preset)
        if load_kN:
            _set_point_load(model, load_x, load_kN)
        text = model_to_ftl(model)
        default_name = f"{preset.replace('_', '-').title()}-modelo-2D.ftl"
        target = Path(path) if path else self._output_dir() / default_name
        target = target.expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
        return {
            "success": True,
            "path": str(target.resolve()),
            "bytes": len(text.encode("utf-8")),
            "lines": len(text.splitlines()),
            "load": {"x": round(load_x, 3), "kN": round(load_kN, 3)},
            "model": _model_info(model),
            "verified": verify_ftl(model),
            "ftool": self.status(),
        }

    def analyze_load(
        self,
        preset: str = "golden_gate",
        x: float = 0.0,
        magnitude: float = 1000.0,
        geometric: bool = True,
        tension_only: bool = True,
    ) -> dict[str, Any]:
        model = build_suspension_model(preset)
        result = analyze_point_load(
            model,
            x=x,
            magnitude=magnitude,
            geometric=geometric,
            tension_only=tension_only,
        )
        exe = self._resolve_exe()
        result["ftool"] = {
            "installed": exe is not None,
            "ftool_exe": exe or "",
            "note": ("Resultados del solver interno; exporta el .ftl para contrastarlos en FTOOL."),
        }
        return {"success": True, **result}
