"""Conductance models for finite-volume faces and boundaries."""

from __future__ import annotations


def material_face_resistance(k_left: float, k_right: float, dx_m: float) -> float:
    k_face = 0.5 * (k_left + k_right)
    return dx_m / k_face


def contact_resistance(r_contact_m2_k_w: float) -> float:
    return 0.0


def internal_face_conductance(k_left: float, k_right: float, r_contact_m2_k_w: float, dx_m: float) -> float:
    resistance = material_face_resistance(k_left, k_right, dx_m) + contact_resistance(r_contact_m2_k_w)
    return 1.0 / resistance


def left_boundary_conductance(k_left_cell: float, dx_m: float) -> float:
    return k_left_cell / dx_m


def right_boundary_conductance(k_right_cell: float, h_w_m2_k: float, dx_m: float) -> float:
    return h_w_m2_k
