"""Independent reference solver for thermal-contact-stack."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import numpy as np

def load_cases(path: str | Path) -> list[dict[str, Any]]:
    return list(json.loads(Path(path).read_text(encoding="utf-8"))["cases"])

def _is_aligned(x_m: float, dx_m: float, length_m: float) -> bool:
    face = x_m / dx_m
    return -1e-10 <= x_m <= length_m + 1e-10 and abs(face - round(face)) <= 1e-9

def _face_index(x_m: float, dx_m: float) -> int:
    return int(round(x_m / dx_m))

def _validate(case: dict[str, Any]) -> None:
    length = float(case["length_m"]); n = int(case["num_cells"]); h = float(case["h_w_m2_k"])
    if length <= 0.0 or n < 4 or not (0.0 < h <= 10000.0): raise ValueError("invalid dimensions")
    dx = length / n; layers = case["layers"]; previous = 0.0; internal_faces: set[int] = set()
    if not layers: raise ValueError("missing layers")
    for index, layer in enumerate(layers):
        start = float(layer["x_start_m"]); end = float(layer["x_end_m"])
        if abs(start - previous) > 1e-10 or end <= start: raise ValueError("bad layers")
        if float(layer["k_w_m_k"]) <= 0.0 or float(layer.get("q_w_m3", 0.0)) < 0.0: raise ValueError("bad material")
        if not _is_aligned(end, dx, length): raise ValueError("unaligned layer")
        if index < len(layers) - 1: internal_faces.add(_face_index(end, dx))
        previous = end
    if abs(previous - length) > 1e-10: raise ValueError("coverage")
    for contact in case.get("contacts", []):
        if float(contact["r_contact_m2_k_w"]) < 0.0: raise ValueError("negative contact")
        if not _is_aligned(float(contact["x_m"]), dx, length): raise ValueError("unaligned contact")
        if _face_index(float(contact["x_m"]), dx) not in internal_faces: raise ValueError("contact location")

def _layer_at_center(layers: list[dict[str, Any]], x_m: float) -> dict[str, Any]:
    for index, layer in enumerate(layers):
        start = float(layer["x_start_m"]); end = float(layer["x_end_m"])
        if start <= x_m < end: return layer
        if index == len(layers) - 1 and abs(x_m - end) <= 1e-12: return layer
    raise ValueError(f"no layer contains x={x_m}")

def _internal_g(k_left: float, k_right: float, r_contact: float, dx_m: float) -> float:
    return 1.0 / (dx_m / (2.0 * k_left) + r_contact + dx_m / (2.0 * k_right))

def solve_case(case: dict[str, Any]) -> dict[str, Any]:
    _validate(case)
    length = float(case["length_m"]); n = int(case["num_cells"]); dx = length / n
    x_values = [(i + 0.5) * dx for i in range(n)]; layers = case["layers"]
    k_values = []; q_values = []
    for x_m in x_values:
        layer = _layer_at_center(layers, x_m); k_values.append(float(layer["k_w_m_k"])); q_values.append(float(layer.get("q_w_m3", 0.0)))
    contact_by_face = {_face_index(float(item["x_m"]), dx): float(item["r_contact_m2_k_w"]) for item in case.get("contacts", [])}
    face_contact = [0.0 for _ in range(n - 1)]; interfaces = []
    for layer in layers[:-1]:
        x_b = float(layer["x_end_m"]); face = _face_index(x_b, dx); r_contact = contact_by_face.get(face, 0.0)
        face_contact[face - 1] = r_contact; interfaces.append((x_b, face, r_contact))
    matrix = np.zeros((n, n), dtype=float); rhs = np.zeros(n, dtype=float)
    t_left = float(case["t_left_c"]); t_inf = float(case["t_inf_c"]); h = float(case["h_w_m2_k"])
    for i in range(n):
        if i == 0:
            g_left = 2.0 * k_values[i] / dx; matrix[i, i] += g_left; rhs[i] += g_left * t_left
        else:
            g_west = _internal_g(k_values[i - 1], k_values[i], face_contact[i - 1], dx); matrix[i, i] += g_west; matrix[i, i - 1] -= g_west
        if i == n - 1:
            g_right = 1.0 / (dx / (2.0 * k_values[i]) + 1.0 / h); matrix[i, i] += g_right; rhs[i] += g_right * t_inf
        else:
            g_east = _internal_g(k_values[i], k_values[i + 1], face_contact[i], dx); matrix[i, i] += g_east; matrix[i, i + 1] -= g_east
        rhs[i] += q_values[i] * dx
    temperatures = np.linalg.solve(matrix, rhs); diagnostics = []
    for x_b, face, r_contact in interfaces:
        m = face; t_l = float(temperatures[m - 1]); t_r = float(temperatures[m]); k_l = k_values[m - 1]; k_r = k_values[m]
        g_face = _internal_g(k_l, k_r, r_contact, dx); heat_flux = g_face * (t_l - t_r)
        t_face_left = t_l - heat_flux * dx / (2.0 * k_l); t_face_right = t_r + heat_flux * dx / (2.0 * k_r)
        diagnostics.append({"x_m": x_b, "heat_flux_w_m2": heat_flux, "temperature_left_c": t_face_left, "temperature_right_c": t_face_right, "contact_delta_t_c": t_face_left - t_face_right})
    g_left = 2.0 * k_values[0] / dx; g_right = 1.0 / (dx / (2.0 * k_values[-1]) + 1.0 / h)
    left_flux = g_left * (t_left - float(temperatures[0])); right_flux = g_right * (float(temperatures[-1]) - t_inf); source_total = sum(q * dx for q in q_values)
    return {"case_id": str(case["case_id"]), "x_m": x_values, "temperature_c": [float(v) for v in temperatures], "interface_diagnostics": diagnostics, "left_heat_flux_w_m2": left_flux, "right_heat_flux_w_m2": right_flux, "max_temperature_c": float(np.max(temperatures)), "energy_residual_w_m2": right_flux - left_flux - source_total}

def solve_cases(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [solve_case(case) for case in cases]
