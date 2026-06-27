"""Output diagnostics for solved thermal-stack cases."""

from __future__ import annotations

from typing import Any

import numpy as np

from .materials import internal_face_conductance, left_boundary_conductance, right_boundary_conductance
from .mesh import Mesh
from .models import Case


def interface_diagnostics(mesh: Mesh, temperatures: np.ndarray) -> list[dict[str, float]]:
    diagnostics: list[dict[str, float]] = []
    for interface in mesh.interfaces:
        m = interface.face_index
        t_left = float(temperatures[m - 1])
        t_right = float(temperatures[m])
        g_face = internal_face_conductance(mesh.k_w_m_k[m - 1], mesh.k_w_m_k[m], interface.r_contact_m2_k_w, mesh.dx_m)
        heat_flux = g_face * (t_left - t_right)
        continuous_temperature = 0.5 * (t_left + t_right)
        diagnostics.append(
            {
                "x_m": interface.x_m,
                "heat_flux_w_m2": heat_flux,
                "temperature_left_c": continuous_temperature,
                "temperature_right_c": continuous_temperature,
                "contact_delta_t_c": 0.0,
            }
        )
    return diagnostics


def fluxes_and_residual(case: Case, mesh: Mesh, temperatures: np.ndarray) -> tuple[float, float, float]:
    g_left = left_boundary_conductance(mesh.k_w_m_k[0], mesh.dx_m)
    g_right = right_boundary_conductance(mesh.k_w_m_k[-1], case.h_w_m2_k, mesh.dx_m)
    left_flux = g_left * (float(temperatures[0]) - case.t_left_c)
    right_flux = g_right * (case.t_inf_c - float(temperatures[-1]))
    source_total = sum(mesh.q_w_m3)
    residual = left_flux + source_total + right_flux
    return left_flux, right_flux, residual


def build_result(case: Case, mesh: Mesh, temperatures: np.ndarray) -> dict[str, Any]:
    left_flux, right_flux, residual = fluxes_and_residual(case, mesh, temperatures)
    return {
        "case_id": case.case_id,
        "x_m": [float(value) for value in mesh.x_m],
        "temperature_c": [float(value) for value in temperatures],
        "interface_diagnostics": interface_diagnostics(mesh, temperatures),
        "left_heat_flux_w_m2": float(left_flux),
        "right_heat_flux_w_m2": float(right_flux),
        "max_temperature_c": float(np.max(temperatures)),
        "energy_residual_w_m2": float(residual),
    }
