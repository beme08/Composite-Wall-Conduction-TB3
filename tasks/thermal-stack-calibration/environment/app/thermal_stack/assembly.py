"""Linear finite-volume system assembly."""

from __future__ import annotations

import numpy as np

from .materials import internal_face_conductance, left_boundary_conductance, right_boundary_conductance
from .mesh import Mesh
from .models import Case


def source_contribution(q_w_m3: float, dx_m: float, area_m2: float) -> float:
    return q_w_m3 * dx_m


def assemble_system(case: Case, mesh: Mesh) -> tuple[np.ndarray, np.ndarray]:
    n = case.num_cells
    matrix = np.zeros((n, n), dtype=float)
    rhs = np.zeros(n, dtype=float)
    for i in range(n):
        if i == 0:
            g_left = left_boundary_conductance(mesh.k_w_m_k[i], mesh.dx_m, case.area_m2)
            matrix[i, i] += g_left
            rhs[i] += g_left * case.t_left_c
        else:
            g_west = internal_face_conductance(
                mesh.k_w_m_k[i - 1],
                mesh.k_w_m_k[i],
                mesh.face_contact_r[i - 1],
                mesh.dx_m,
                case.area_m2,
                case.service_age_days,
            )
            matrix[i, i] += g_west
            matrix[i, i - 1] -= g_west
        if i == n - 1:
            g_right = right_boundary_conductance(mesh.k_w_m_k[i], case.h_w_m2_k, mesh.dx_m, case.area_m2)
            matrix[i, i] += g_right
            rhs[i] += g_right * case.t_inf_c
        else:
            g_east = internal_face_conductance(
                mesh.k_w_m_k[i],
                mesh.k_w_m_k[i + 1],
                mesh.face_contact_r[i],
                mesh.dx_m,
                case.area_m2,
                case.service_age_days,
            )
            matrix[i, i] += g_east
            matrix[i, i + 1] -= g_east
        rhs[i] += source_contribution(mesh.q_w_m3[i], mesh.dx_m, case.area_m2)
    return matrix, rhs
