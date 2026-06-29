"""Independent reference solver for thermal-stack-calibration."""

from __future__ import annotations

import copy
import csv
import json
import math
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np

KELVIN_OFFSET = 273.15
AGE_CONTACT_RATE = 2.0e-5
STEFAN_BOLTZMANN = 5.670374419e-8
TASK_DIR = Path(__file__).resolve().parents[2]
APP_DATA = Path(os.environ["APP_DIR"]) / "data" if "APP_DIR" in os.environ else TASK_DIR / "environment" / "app" / "data"


def load_cases(path: str | Path) -> list[dict[str, Any]]:
    return list(json.loads(Path(path).read_text(encoding="utf-8"))["cases"])


def parse_scalar(value: Any) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if not isinstance(value, str):
        raise TypeError(f"expected scalar, got {type(value).__name__}")
    text = value.strip().replace("\u00a0", "")
    if "," in text and "." not in text:
        if text.count(",") == 1 and all(part.strip("+-").isdigit() for part in text.split(",")):
            text = text.replace(",", ".")
    return float(text)


def parse_vector(value: Any) -> tuple[float, ...]:
    if value is None:
        return (0.0,)
    if isinstance(value, (list, tuple)):
        return tuple(parse_scalar(item) for item in value)
    return tuple(float(part.strip()) for part in str(value).split(",") if part.strip())


def parse_facility_date(value: Any, facility: dict[str, Any]) -> date:
    text = str(value).strip()
    if "-" in text:
        return datetime.strptime(text, "%Y-%m-%d").date()
    country = str(facility.get("country", facility.get("facility_country", ""))).strip().lower()
    region = str(facility.get("region", facility.get("facility_region", ""))).strip().lower()
    city = str(facility.get("city", facility.get("facility_city", ""))).strip().lower()
    us_context = country in {"us", "usa", "united states"} or region in {"tx", "az"} or city in {
        "austin",
        "phoenix",
        "boston",
    }
    return datetime.strptime(text, "%m/%d/%Y" if us_context else "%d/%m/%Y").date()


def normalize_temperature_to_c(value: Any, unit: str) -> float:
    number = parse_scalar(value)
    if unit.strip().upper() == "K":
        return number - KELVIN_OFFSET
    return number


def load_materials(path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    material_path = Path(path) if path is not None else APP_DATA / "materials_db.csv"
    materials: dict[str, dict[str, Any]] = {}
    with material_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter=";"):
            facility = {
                "city": row.get("facility_city", ""),
                "region": row.get("facility_region", ""),
                "country": row.get("facility_country", ""),
            }
            material = {
                "material_id": str(row["material_id"]),
                "certified_on": parse_facility_date(row["certified_on"], facility),
                "k_ref_w_m_k": parse_scalar(row["k_ref_w_m_k"]),
                "temp_coeff_per_k": parse_scalar(row["temp_coeff_per_k"]),
                "reference_temp_k": parse_scalar(row["reference_temp_k"]),
                "calibration_offsets_c": parse_vector(row.get("calibration_offsets_c", "0")),
            }
            materials[material["material_id"]] = material
    return materials


def normalize_case(raw_case: dict[str, Any], materials: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    raw = copy.deepcopy(raw_case)
    materials = materials or load_materials()
    raw.setdefault("area_m2", 1.0)
    raw.setdefault("temperature_unit", "C")
    raw.setdefault(
        "facility",
        {
            "city": "Austin",
            "region": "TX",
            "country": "US",
            "installed_on": "01/01/2026",
            "measured_on": "01/02/2026",
        },
    )
    unit_scale = 0.001 if str(raw.get("length_unit", "m")).lower() == "mm" else 1.0
    facility = raw["facility"]
    installed = parse_facility_date(facility["installed_on"], facility)
    measured = parse_facility_date(facility["measured_on"], facility)
    temp_unit = str(raw.get("temperature_unit", "C"))
    layers = []
    for layer in raw["layers"]:
        material = materials[str(layer["material_id"])]
        layers.append(
            {
                "name": str(layer["name"]),
                "x_start_m": parse_scalar(layer["x_start_m"]) * unit_scale,
                "x_end_m": parse_scalar(layer["x_end_m"]) * unit_scale,
                "material": material,
                "q_w_m3": parse_scalar(layer.get("q_w_m3", 0.0)),
            }
        )
    contacts = []
    for contact in raw.get("contacts", []):
        contacts.append(
            {
                "x_m": parse_scalar(contact["x_m"]) * unit_scale,
                "r_contact_m2_k_w": parse_scalar(contact["r_contact_m2_k_w"]),
                "contact_temp_coeff_per_k": parse_scalar(contact.get("contact_temp_coeff_per_k", 0.0)),
                "contact_t_ref_c": parse_scalar(contact.get("contact_t_ref_c", 25.0)),
            }
        )
    radiation_raw = raw.get("right_radiation") or {}
    radiation = {
        "emissivity": parse_scalar(radiation_raw.get("emissivity", 0.0)),
        "view_factor": parse_scalar(radiation_raw.get("view_factor", 1.0)),
        "t_surround_c": normalize_temperature_to_c(
            radiation_raw.get("t_surround_c", raw["t_inf_c"]),
            temp_unit,
        ),
    }
    return {
        "case_id": str(raw["case_id"]),
        "length_m": parse_scalar(raw["length_m"]) * unit_scale,
        "num_cells": int(raw["num_cells"]),
        "area_m2": parse_scalar(raw.get("area_m2", 1.0)),
        "t_left_c": normalize_temperature_to_c(raw["t_left_c"], temp_unit),
        "t_inf_c": normalize_temperature_to_c(raw["t_inf_c"], temp_unit),
        "h_w_m2_k": parse_scalar(raw["h_w_m2_k"]),
        "facility_installed_on": installed,
        "facility_measured_on": measured,
        "service_age_days": max(0, (measured - installed).days),
        "layers": layers,
        "contacts": contacts,
        "right_radiation": radiation,
    }


def _effective_k(material: dict[str, Any], t_left_c: float, t_inf_c: float) -> float:
    offsets = material["calibration_offsets_c"] or (0.0,)
    eval_temp_k = KELVIN_OFFSET + 0.5 * (t_left_c + t_inf_c) + sum(offsets) / len(offsets)
    return material["k_ref_w_m_k"] * (1.0 + material["temp_coeff_per_k"] * (eval_temp_k - material["reference_temp_k"]))


def _is_aligned(x_m: float, dx_m: float, length_m: float) -> bool:
    face = x_m / dx_m
    return -1e-10 <= x_m <= length_m + 1e-10 and abs(face - round(face)) <= 1e-9


def _face_index(x_m: float, dx_m: float) -> int:
    return int(round(x_m / dx_m))


def _validate(case: dict[str, Any]) -> None:
    length = case["length_m"]
    n = case["num_cells"]
    h = case["h_w_m2_k"]
    if length <= 0.0 or n < 4 or not (0.0 < h <= 10000.0):
        raise ValueError("invalid dimensions")
    if case["area_m2"] <= 0.0:
        raise ValueError("invalid area")
    dx = length / n
    layers = case["layers"]
    previous = 0.0
    internal_faces: set[int] = set()
    if not layers:
        raise ValueError("missing layers")
    for index, layer in enumerate(layers):
        start = layer["x_start_m"]
        end = layer["x_end_m"]
        if abs(start - previous) > 1e-10 or end <= start:
            raise ValueError("bad layers")
        if _effective_k(layer["material"], case["t_left_c"], case["t_inf_c"]) <= 0.0:
            raise ValueError("bad material")
        if layer.get("q_w_m3", 0.0) < 0.0:
            raise ValueError("bad source")
        if not _is_aligned(end, dx, length):
            raise ValueError("unaligned layer")
        if index < len(layers) - 1:
            internal_faces.add(_face_index(end, dx))
        previous = end
    if abs(previous - length) > 1e-10:
        raise ValueError("coverage")
    for contact in case.get("contacts", []):
        if contact["r_contact_m2_k_w"] < 0.0:
            raise ValueError("negative contact")
        if not _is_aligned(contact["x_m"], dx, length):
            raise ValueError("unaligned contact")
        if _face_index(contact["x_m"], dx) not in internal_faces:
            raise ValueError("contact location")
    radiation = case.get("right_radiation", {})
    emissivity = radiation.get("emissivity", 0.0)
    view_factor = radiation.get("view_factor", 1.0)
    t_surround_c = radiation.get("t_surround_c", case["t_inf_c"])
    if not (0.0 <= emissivity <= 1.0):
        raise ValueError("bad radiation emissivity")
    if not (0.0 <= view_factor <= 1.0):
        raise ValueError("bad radiation view factor")
    if t_surround_c <= -KELVIN_OFFSET:
        raise ValueError("bad radiation surround temperature")


def _layer_at_center(layers: list[dict[str, Any]], x_m: float) -> dict[str, Any]:
    for index, layer in enumerate(layers):
        start = layer["x_start_m"]
        end = layer["x_end_m"]
        if start <= x_m < end:
            return layer
        if index == len(layers) - 1 and abs(x_m - end) <= 1e-12:
            return layer
    raise ValueError(f"no layer contains x={x_m}")


def _aged_contact(r_contact: float, service_age_days: int) -> float:
    return r_contact * (1.0 + AGE_CONTACT_RATE * service_age_days)


def _effective_contact(r_contact: float, temp_coeff: float, t_ref_c: float,
                       service_age_days: int, t_eval_c: float) -> float:
    if temp_coeff == 0.0:
        return _aged_contact(r_contact, service_age_days)
    aged = _aged_contact(r_contact, service_age_days)
    return aged * (1.0 + temp_coeff * (t_eval_c - t_ref_c))


def _internal_g(k_left: float, k_right: float, r_contact: float, dx_m: float, area_m2: float) -> float:
    return area_m2 / (dx_m / (2.0 * k_left) + r_contact + dx_m / (2.0 * k_right))


def _left_g(k_left: float, dx_m: float, area_m2: float) -> float:
    return area_m2 / (dx_m / (2.0 * k_left))


def _right_g(k_right: float, h: float, dx_m: float, area_m2: float) -> float:
    return area_m2 / (dx_m / (2.0 * k_right) + 1.0 / h)


def _radiation_active(case: dict[str, Any]) -> bool:
    radiation = case.get("right_radiation", {})
    return radiation.get("emissivity", 0.0) > 0.0 and radiation.get("view_factor", 1.0) > 0.0


def _radiation_h(case: dict[str, Any], surface_temp_c: float | None) -> float:
    if not _radiation_active(case):
        return 0.0
    radiation = case["right_radiation"]
    t_surface_k = KELVIN_OFFSET + (case["t_inf_c"] if surface_temp_c is None else surface_temp_c)
    t_surround_k = KELVIN_OFFSET + radiation["t_surround_c"]
    return (
        radiation["emissivity"]
        * radiation["view_factor"]
        * STEFAN_BOLTZMANN
        * (t_surface_k + t_surround_k)
        * (t_surface_k * t_surface_k + t_surround_k * t_surround_k)
    )


def _right_boundary_state(case: dict[str, Any], h_rad: float) -> tuple[float, float]:
    h_conv = case["h_w_m2_k"]
    if h_rad <= 0.0:
        return h_conv, case["t_inf_c"]
    h_total = h_conv + h_rad
    t_effective = (h_conv * case["t_inf_c"] + h_rad * case["right_radiation"]["t_surround_c"]) / h_total
    return h_total, t_effective


def _solve_core(
    case: dict[str, Any],
    contact_resistances: dict[int, float] | None = None,
    right_surface_temp_c: float | None = None,
) -> dict[str, Any]:
    """Solve once using the given contact resistances (or defaults from aged contacts)."""
    length = case["length_m"]
    n = case["num_cells"]
    dx = length / n
    area = case["area_m2"]
    x_values = [(i + 0.5) * dx for i in range(n)]
    layers = case["layers"]
    k_values = []
    q_values = []
    for x_m in x_values:
        layer = _layer_at_center(layers, x_m)
        k_values.append(_effective_k(layer["material"], case["t_left_c"], case["t_inf_c"]))
        q_values.append(layer.get("q_w_m3", 0.0))
    if contact_resistances is not None:
        contact_by_face = contact_resistances
    else:
        contact_by_face = {
            _face_index(item["x_m"], dx): _aged_contact(item["r_contact_m2_k_w"], case["service_age_days"])
            for item in case.get("contacts", [])
        }
    face_contact = [0.0 for _ in range(n - 1)]
    interfaces = []
    for layer in layers[:-1]:
        x_b = layer["x_end_m"]
        face = _face_index(x_b, dx)
        r_contact = contact_by_face.get(face, 0.0)
        face_contact[face - 1] = r_contact
        interfaces.append((x_b, face, r_contact))
    matrix = np.zeros((n, n), dtype=float)
    rhs = np.zeros(n, dtype=float)
    t_left = case["t_left_c"]
    h_rad = _radiation_h(case, right_surface_temp_c)
    h_right, t_right_reference = _right_boundary_state(case, h_rad)
    for i in range(n):
        if i == 0:
            g_left = _left_g(k_values[i], dx, area)
            matrix[i, i] += g_left
            rhs[i] += g_left * t_left
        else:
            g_west = _internal_g(k_values[i - 1], k_values[i], face_contact[i - 1], dx, area)
            matrix[i, i] += g_west
            matrix[i, i - 1] -= g_west
        if i == n - 1:
            g_right = _right_g(k_values[i], h_right, dx, area)
            matrix[i, i] += g_right
            rhs[i] += g_right * t_right_reference
        else:
            g_east = _internal_g(k_values[i], k_values[i + 1], face_contact[i], dx, area)
            matrix[i, i] += g_east
            matrix[i, i + 1] -= g_east
        rhs[i] += q_values[i] * dx * area
    temperatures = np.linalg.solve(matrix, rhs)
    residual_vec = matrix @ temperatures - rhs
    diagnostics = []
    for x_b, face, r_contact in interfaces:
        m = face
        t_l = float(temperatures[m - 1])
        t_r = float(temperatures[m])
        k_l = k_values[m - 1]
        k_r = k_values[m]
        heat_flow = _internal_g(k_l, k_r, r_contact, dx, area) * (t_l - t_r)
        heat_flux = heat_flow / area
        t_face_left = t_l - heat_flow * dx / (2.0 * k_l * area)
        t_face_right = t_r + heat_flow * dx / (2.0 * k_r * area)
        diagnostics.append(
            {
                "x_m": x_b,
                "heat_flux_w_m2": heat_flux,
                "temperature_left_c": t_face_left,
                "temperature_right_c": t_face_right,
                "contact_delta_t_c": t_face_left - t_face_right,
            }
        )
    left_flow = _left_g(k_values[0], dx, area) * (t_left - float(temperatures[0]))
    right_flow = _right_g(k_values[-1], h_right, dx, area) * (float(temperatures[-1]) - t_right_reference)
    right_surface_c = float(temperatures[-1]) - right_flow * dx / (2.0 * k_values[-1] * area)
    source_total = sum(q * dx * area for q in q_values)
    energy_residual = right_flow - left_flow - source_total
    return {
        "case_id": case["case_id"],
        "x_m": x_values,
        "temperature_c": [float(v) for v in temperatures],
        "interface_diagnostics": diagnostics,
        "left_heat_flux_w_m2": left_flow / area,
        "right_heat_flux_w_m2": right_flow / area,
        "max_temperature_c": float(np.max(temperatures)),
        "energy_residual_w_m2": float(energy_residual / area),
        "_linear_residual_inf": float(np.max(np.abs(residual_vec))),
        "_normalized_case": case,
        "_energy_residual_w": float(energy_residual),
        "_dx": dx,
        "_k_values": k_values,
        "_right_surface_c": float(right_surface_c),
        "_right_h_rad_w_m2_k": float(h_rad),
    }


def solve_case(raw_case: dict[str, Any]) -> dict[str, Any]:
    case = normalize_case(raw_case)
    _validate(case)

    # Fixed-point iteration for temperature-dependent contact resistance
    cs = case.get("contacts", [])
    has_temp_dependent = any(c.get("contact_temp_coeff_per_k", 0.0) != 0.0 for c in cs)
    has_radiation = _radiation_active(case)
    if not has_temp_dependent and not has_radiation:
        result = _solve_core(case)
        return {k: v for k, v in result.items() if not k.startswith("_")}

    dx = case["length_m"] / case["num_cells"]
    reff: dict[int, float] = {}
    for c in cs:
        f = _face_index(c["x_m"], dx)
        reff[f] = _aged_contact(c["r_contact_m2_k_w"], case["service_age_days"])
    right_surface_c: float | None = None

    for _ in range(80):
        result = _solve_core(case, contact_resistances=reff, right_surface_temp_c=right_surface_c)
        diag_by_face = {_face_index(d["x_m"], dx): d for d in result["interface_diagnostics"]}
        new_reff = dict(reff)
        max_rel = 0.0
        for c in cs:
            coeff = c.get("contact_temp_coeff_per_k", 0.0)
            if coeff == 0.0:
                continue
            f = _face_index(c["x_m"], dx)
            if f not in diag_by_face:
                continue
            d = diag_by_face[f]
            t_eval_c = 0.5 * (d["temperature_left_c"] + d["temperature_right_c"])
            rn = _effective_contact(
                c["r_contact_m2_k_w"], coeff, c.get("contact_t_ref_c", 25.0),
                case["service_age_days"], t_eval_c,
            )
            max_rel = max(max_rel, abs(rn - reff[f]) / max(abs(reff[f]), 1e-12))
            new_reff[f] = rn
        previous_surface = case["t_inf_c"] if right_surface_c is None else right_surface_c
        new_surface = result["_right_surface_c"] if has_radiation else right_surface_c
        if has_radiation:
            max_rel = max(
                max_rel,
                abs(new_surface - previous_surface)
                / max(abs(new_surface), 1.0),
            )
        reff = new_reff
        right_surface_c = new_surface
        if max_rel < 1e-6:
            break

    result = _solve_core(case, contact_resistances=reff, right_surface_temp_c=right_surface_c)
    return {k: v for k, v in result.items() if not k.startswith("_")}


def public_result(result: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if not key.startswith("_")}


def solve_cases(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [public_result(solve_case(case)) for case in cases]


def analytic_constant_k_no_source(case: dict[str, Any], x_values: list[float]) -> list[float]:
    normalized = normalize_case(case)
    if len(normalized["layers"]) != 1:
        raise ValueError("expected one layer")
    layer = normalized["layers"][0]
    if abs(layer.get("q_w_m3", 0.0)) > 0.0:
        raise ValueError("expected no source")
    k = _effective_k(layer["material"], normalized["t_left_c"], normalized["t_inf_c"])
    length = normalized["length_m"]
    h = normalized["h_w_m2_k"]
    t_left = normalized["t_left_c"]
    t_inf = normalized["t_inf_c"]
    flux = (t_left - t_inf) / (length / k + 1.0 / h)
    return [t_left - flux * x / k for x in x_values]


def check_physical_invariants(raw_case: dict[str, Any], result: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    normalized = normalize_case(raw_case)
    temps = [float(v) for v in result["temperature_c"]]
    if any(t <= -KELVIN_OFFSET for t in temps):
        failures.append("temperature not positive in kelvin")
    if abs(float(result["energy_residual_w_m2"])) > 1e-6:
        failures.append("energy residual exceeds 1e-6 W/m2")
    if len(normalized["layers"]) == 1 and result["interface_diagnostics"]:
        failures.append("single-layer case emitted interfaces")
    source_total = sum(
        layer.get("q_w_m3", 0.0) * (layer["x_end_m"] - layer["x_start_m"]) * normalized["area_m2"]
        for layer in normalized["layers"]
    )
    if source_total == 0.0 and normalized["t_left_c"] >= normalized["t_inf_c"]:
        for a, b in zip(temps, temps[1:]):
            if a + 1e-9 < b:
                failures.append("no-source temperature profile is not monotone")
                break
    if len(normalized["layers"]) == 1 and source_total == 0.0 and not _radiation_active(normalized):
        expected_temps = analytic_constant_k_no_source(raw_case, result["x_m"])
        for actual, expected in zip(temps, expected_temps):
            if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=5e-4):
                failures.append("constant-k analytical comparison failed")
                break
    return failures
