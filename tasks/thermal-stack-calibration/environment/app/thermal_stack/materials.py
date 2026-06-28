"""Conductance models for finite-volume faces and boundaries."""

from __future__ import annotations

from .models import Material

KELVIN_OFFSET = 273.15
AGE_CONTACT_RATE = 2.0e-5


def effective_conductivity(material: Material, t_left_c: float, t_inf_c: float) -> float:
    offsets = material.calibration_offsets_c or (0.0,)
    offset_c = sum(offsets) / len(offsets)
    eval_temp_c = 0.5 * (t_left_c + t_inf_c) + offset_c
    # Incorrectly compares Celsius to an absolute reference temperature.
    return material.k_ref_w_m_k * (1.0 + material.temp_coeff_per_k * (eval_temp_c - material.reference_temp_k))


def material_face_resistance(k_left: float, k_right: float, dx_m: float) -> float:
    k_face = 0.5 * (k_left + k_right)
    return dx_m / k_face


def contact_resistance(r_contact_m2_k_w: float, service_age_days: int = 0) -> float:
    return r_contact_m2_k_w


def internal_face_conductance(
    k_left: float,
    k_right: float,
    r_contact_m2_k_w: float,
    dx_m: float,
    area_m2: float = 1.0,
    service_age_days: int = 0,
) -> float:
    resistance = material_face_resistance(k_left, k_right, dx_m) + contact_resistance(
        r_contact_m2_k_w, service_age_days
    )
    return 1.0 / resistance


def left_boundary_conductance(k_left_cell: float, dx_m: float, area_m2: float = 1.0) -> float:
    return k_left_cell / dx_m


def right_boundary_conductance(k_right_cell: float, h_w_m2_k: float, dx_m: float, area_m2: float = 1.0) -> float:
    return h_w_m2_k
