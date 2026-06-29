"""Finite-volume solver for thermal-stack calibration cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .models import Case, Layer, Material

KELVIN_OFFSET = 273.15
AGE_CONTACT_RATE = 2.0e-5


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


def effective_conductivity(material: Material, t_left_c: float, t_inf_c: float) -> float:
    offsets = material.calibration_offsets_c or (0.0,)
    eval_temp_k = KELVIN_OFFSET + 0.5 * (t_left_c + t_inf_c) + sum(offsets) / len(offsets)
    return material.k_ref_w_m_k * (1.0 + material.temp_coeff_per_k * (eval_temp_k - material.reference_temp_k))


def _is_aligned(x_m: float, dx_m: float, length_m: float) -> bool:
    face = x_m / dx_m
    return -1e-10 <= x_m <= length_m + 1e-10 and abs(face - round(face)) <= 1e-9


def _face_index(x_m: float, dx_m: float) -> int:
    return int(round(x_m / dx_m))


def _layer_at_center(layers: tuple[Layer, ...], x_m: float) -> Layer:
    for index, layer in enumerate(layers):
        if layer.x_start_m <= x_m < layer.x_end_m:
            return layer
        if index == len(layers) - 1 and abs(x_m - layer.x_end_m) <= 1e-12:
            return layer
    raise ValueError(f"no layer contains x={x_m}")


def validate_case(case: Case) -> None:
    if case.length_m <= 0.0 or case.num_cells < 4 or not (0.0 < case.h_w_m2_k <= 10000.0):
        raise ValueError("invalid dimensions")
    if case.area_m2 <= 0.0:
        raise ValueError("area_m2 must be positive")
    dx_m = case.length_m / case.num_cells
    previous_end = 0.0
    internal_faces: set[int] = set()
    if not case.layers:
        raise ValueError("at least one layer is required")
    for index, layer in enumerate(case.layers):
        if abs(layer.x_start_m - previous_end) > 1e-10 or layer.x_end_m <= layer.x_start_m:
            raise ValueError("layers must exactly cover the stack without gaps or overlaps")
        if effective_conductivity(layer.material, case.t_left_c, case.t_inf_c) <= 0.0:
            raise ValueError("layer conductivity must be positive")
        if layer.q_w_m3 < 0.0:
            raise ValueError("volumetric heat generation must be non-negative")
        if not _is_aligned(layer.x_end_m, dx_m, case.length_m):
            raise ValueError("layer boundaries must align to cell faces")
        if index < len(case.layers) - 1:
            internal_faces.add(_face_index(layer.x_end_m, dx_m))
        previous_end = layer.x_end_m
    if abs(previous_end - case.length_m) > 1e-10:
        raise ValueError("layers must end at length_m")
    for contact in case.contacts:
        if contact.r_contact_m2_k_w < 0.0:
            raise ValueError("contact resistance must be non-negative")
        if not _is_aligned(contact.x_m, dx_m, case.length_m):
            raise ValueError("contact interface must align to a cell face")
        if _face_index(contact.x_m, dx_m) not in internal_faces:
            raise ValueError("contact interface must be on an internal layer boundary")


def _aged_contact(r_contact: float, service_age_days: int) -> float:
    return r_contact * (1.0 + AGE_CONTACT_RATE * service_age_days)


def _effective_contact(
    r_contact: float, temp_coeff: float, t_ref_c: float,
    service_age_days: int, t_eval_c: float,
) -> float:
    if temp_coeff == 0.0:
        return _aged_contact(r_contact, service_age_days)
    aged = _aged_contact(r_contact, service_age_days)
    return aged * (1.0 + temp_coeff * (t_eval_c - t_ref_c))


def _internal_g(k_left: float, k_right: float, r_contact: float, dx_m: float, area_m2: float) -> float:
    return area_m2 / (dx_m / (2.0 * k_left) + r_contact + dx_m / (2.0 * k_right))


def _left_g(k_left: float, dx_m: float, area_m2: float) -> float:
    return area_m2 / (dx_m / (2.0 * k_left))


def _right_g(k_right: float, h_w_m2_k: float, dx_m: float, area_m2: float) -> float:
    return area_m2 / (dx_m / (2.0 * k_right) + 1.0 / h_w_m2_k)


def build_mesh(case: Case, override_contacts: dict[int, float] | None = None) -> Mesh:
    validate_case(case)
    dx_m = case.length_m / case.num_cells
    x_values = [(i + 0.5) * dx_m for i in range(case.num_cells)]
    k_values: list[float] = []
    q_values: list[float] = []
    for x_m in x_values:
        layer = _layer_at_center(case.layers, x_m)
        k_values.append(effective_conductivity(layer.material, case.t_left_c, case.t_inf_c))
        q_values.append(layer.q_w_m3)
    if override_contacts is not None:
        contact_by_face = override_contacts
    else:
        contact_by_face = {
            _face_index(contact.x_m, dx_m): _aged_contact(contact.r_contact_m2_k_w, case.service_age_days)
            for contact in case.contacts
        }
    face_contact_r = [0.0 for _ in range(case.num_cells - 1)]
    interfaces: list[Interface] = []
    for layer in case.layers[:-1]:
        face = _face_index(layer.x_end_m, dx_m)
        r_contact = contact_by_face.get(face, 0.0)
        face_contact_r[face - 1] = r_contact
        interfaces.append(Interface(layer.x_end_m, face, r_contact))
    return Mesh(dx_m, x_values, k_values, q_values, face_contact_r, interfaces)


def _assemble(case: Case, mesh: Mesh) -> tuple[np.ndarray, np.ndarray]:
    n = case.num_cells
    matrix = np.zeros((n, n), dtype=float)
    rhs = np.zeros(n, dtype=float)
    for i in range(n):
        if i == 0:
            g_left = _left_g(mesh.k_w_m_k[i], mesh.dx_m, case.area_m2)
            matrix[i, i] += g_left
            rhs[i] += g_left * case.t_left_c
        else:
            g_west = _internal_g(
                mesh.k_w_m_k[i - 1],
                mesh.k_w_m_k[i],
                mesh.face_contact_r[i - 1],
                mesh.dx_m,
                case.area_m2,
            )
            matrix[i, i] += g_west
            matrix[i, i - 1] -= g_west
        if i == n - 1:
            g_right = _right_g(mesh.k_w_m_k[i], case.h_w_m2_k, mesh.dx_m, case.area_m2)
            matrix[i, i] += g_right
            rhs[i] += g_right * case.t_inf_c
        else:
            g_east = _internal_g(
                mesh.k_w_m_k[i],
                mesh.k_w_m_k[i + 1],
                mesh.face_contact_r[i],
                mesh.dx_m,
                case.area_m2,
            )
            matrix[i, i] += g_east
            matrix[i, i + 1] -= g_east
        rhs[i] += mesh.q_w_m3[i] * mesh.dx_m * case.area_m2
    return matrix, rhs


def _interface_diagnostics(case: Case, mesh: Mesh, temperatures: np.ndarray) -> list[dict[str, float]]:
    diagnostics: list[dict[str, float]] = []
    for interface in mesh.interfaces:
        m = interface.face_index
        t_left = float(temperatures[m - 1])
        t_right = float(temperatures[m])
        k_left = mesh.k_w_m_k[m - 1]
        k_right = mesh.k_w_m_k[m]
        heat_flow = _internal_g(k_left, k_right, interface.r_contact_m2_k_w, mesh.dx_m, case.area_m2) * (
            t_left - t_right
        )
        heat_flux = heat_flow / case.area_m2
        temperature_left = t_left - heat_flow * mesh.dx_m / (2.0 * k_left * case.area_m2)
        temperature_right = t_right + heat_flow * mesh.dx_m / (2.0 * k_right * case.area_m2)
        diagnostics.append(
            {
                "x_m": interface.x_m,
                "heat_flux_w_m2": heat_flux,
                "temperature_left_c": temperature_left,
                "temperature_right_c": temperature_right,
                "contact_delta_t_c": temperature_left - temperature_right,
            }
        )
    return diagnostics


def _solve_core(case: Case, override_contacts: dict[int, float] | None = None) -> tuple:
    mesh = build_mesh(case, override_contacts=override_contacts)
    matrix, rhs = _assemble(case, mesh)
    temperatures = np.linalg.solve(matrix, rhs)
    return mesh, temperatures


def solve_case(case: Case) -> dict[str, Any]:
    mesh, temperatures = _solve_core(case)

    has_temp_dependent = any(
        c.contact_temp_coeff_per_k != 0.0 for c in case.contacts
    )
    if has_temp_dependent:
        diagnostics = _interface_diagnostics(case, mesh, temperatures)
        override: dict[int, float] = {}
        for i, contact in enumerate(case.contacts):
            coeff = contact.contact_temp_coeff_per_k
            if coeff != 0.0 and i < len(diagnostics):
                t_eval_c = 0.5 * (diagnostics[i]["temperature_left_c"] + diagnostics[i]["temperature_right_c"])
                r_eff = _effective_contact(
                    contact.r_contact_m2_k_w,
                    coeff,
                    contact.contact_t_ref_c,
                    case.service_age_days,
                    t_eval_c,
                )
                override[_face_index(contact.x_m, mesh.dx_m)] = r_eff
        mesh, temperatures = _solve_core(case, override_contacts=override)

    left_flow = _left_g(mesh.k_w_m_k[0], mesh.dx_m, case.area_m2) * (case.t_left_c - float(temperatures[0]))
    right_flow = _right_g(mesh.k_w_m_k[-1], case.h_w_m2_k, mesh.dx_m, case.area_m2) * (
        float(temperatures[-1]) - case.t_inf_c
    )
    source_total = sum(q * mesh.dx_m * case.area_m2 for q in mesh.q_w_m3)
    energy_residual = right_flow - left_flow - source_total
    return {
        "case_id": case.case_id,
        "x_m": [float(value) for value in mesh.x_m],
        "temperature_c": [float(value) for value in temperatures],
        "interface_diagnostics": _interface_diagnostics(case, mesh, temperatures),
        "left_heat_flux_w_m2": float(left_flow / case.area_m2),
        "right_heat_flux_w_m2": float(right_flow / case.area_m2),
        "max_temperature_c": float(np.max(temperatures)),
        "energy_residual_w_m2": float(energy_residual / case.area_m2),
    }
