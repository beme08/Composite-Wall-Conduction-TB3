"""Mesh construction and material/contact mapping."""

from __future__ import annotations

from dataclasses import dataclass

from .models import Case, Layer


@dataclass(frozen=True)
class Interface:
    x_m: float
    face_index: int
    r_contact_m2_k_w: float


@dataclass(frozen=True)
class Mesh:
    dx_m: float
    x_m: list[float]
    k_w_m_k: list[float]
    q_w_m3: list[float]
    face_contact_r: list[float]
    interfaces: list[Interface]


def _is_aligned(x_m: float, dx_m: float, length_m: float) -> bool:
    face = x_m / dx_m
    return -1e-10 <= x_m <= length_m + 1e-10 and abs(face - round(face)) <= 1e-9


def _face_index(x_m: float, dx_m: float) -> int:
    return int(round(x_m / dx_m))


def _layer_at_x(layers: tuple[Layer, ...], x_m: float) -> Layer:
    for index, layer in enumerate(layers):
        if layer.x_start_m <= x_m < layer.x_end_m:
            return layer
        if index == len(layers) - 1 and abs(x_m - layer.x_end_m) <= 1e-12:
            return layer
    raise ValueError(f"no layer contains x={x_m!r}")


def validate_case(case: Case) -> None:
    if case.length_m <= 0.0:
        raise ValueError("length_m must be positive")
    if case.num_cells < 4:
        raise ValueError("num_cells must be at least 4")
    if not (0.0 < case.h_w_m2_k <= 10000.0):
        raise ValueError("h_w_m2_k must be in (0, 10000]")
    if not case.layers:
        raise ValueError("at least one layer is required")
    dx_m = case.length_m / case.num_cells
    previous_end = 0.0
    internal_boundaries: set[int] = set()
    for index, layer in enumerate(case.layers):
        if layer.k_w_m_k <= 0.0:
            raise ValueError("layer conductivity must be positive")
        if layer.q_w_m3 < 0.0:
            raise ValueError("volumetric heat generation must be non-negative")
        if abs(layer.x_start_m - previous_end) > 1e-10:
            raise ValueError("layers must exactly cover the stack without gaps or overlaps")
        if layer.x_end_m <= layer.x_start_m:
            raise ValueError("layer end must exceed layer start")
        if not _is_aligned(layer.x_end_m, dx_m, case.length_m):
            raise ValueError("layer boundaries must align to cell faces")
        if index < len(case.layers) - 1:
            face = _face_index(layer.x_end_m, dx_m)
            if not (1 <= face <= case.num_cells - 1):
                raise ValueError("internal layer boundary must be internal")
            internal_boundaries.add(face)
        previous_end = layer.x_end_m
    if abs(previous_end - case.length_m) > 1e-10:
        raise ValueError("layers must end at length_m")
    for contact in case.contacts:
        if contact.r_contact_m2_k_w < 0.0:
            raise ValueError("contact resistance must be non-negative")
        if not _is_aligned(contact.x_m, dx_m, case.length_m):
            raise ValueError("contact interface must align to a cell face")
        if _face_index(contact.x_m, dx_m) not in internal_boundaries:
            raise ValueError("contact interface must be on an internal layer boundary")


def build_mesh(case: Case) -> Mesh:
    validate_case(case)
    dx_m = case.length_m / case.num_cells
    x_m = [(i + 0.5) * dx_m for i in range(case.num_cells)]
    k_values: list[float] = []
    q_values: list[float] = []
    for i in range(case.num_cells):
        x_probe = min((i + 1) * dx_m, case.length_m)
        layer = _layer_at_x(case.layers, x_probe)
        k_values.append(layer.k_w_m_k)
        q_values.append(layer.q_w_m3)
    contact_by_face = {_face_index(contact.x_m, dx_m): contact.r_contact_m2_k_w for contact in case.contacts}
    face_contact_r = [0.0 for _ in range(case.num_cells - 1)]
    interfaces: list[Interface] = []
    for layer in case.layers[:-1]:
        face = _face_index(layer.x_end_m, dx_m)
        r_contact = contact_by_face.get(face, 0.0)
        face_contact_r[face - 1] = r_contact
        interfaces.append(Interface(layer.x_end_m, face, r_contact))
    return Mesh(dx_m, x_m, k_values, q_values, face_contact_r, interfaces)
