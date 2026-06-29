#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"

python3 - "$APP_DIR" <<'PYSOLVE'
from __future__ import annotations

import sys
from pathlib import Path

app_dir = Path(sys.argv[1])

FILES = {
"thermal_stack/__init__.py": r'''"""Thermal stack calibration solver package."""

from .io import load_cases, load_materials, write_results
from .models import Case, Contact, Facility, Layer, Material, Radiation
from .solver import solve_case

__all__ = [
    "Case",
    "Contact",
    "Facility",
    "Layer",
    "Material",
    "Radiation",
    "load_cases",
    "load_materials",
    "solve_case",
    "write_results",
]
''',
"thermal_stack/models.py": r'''"""Data models and normalization for thermal-stack calibration cases."""

from __future__ import annotations

import copy
import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

KELVIN_OFFSET = 273.15


@dataclass(frozen=True)
class Material:
    material_id: str
    certified_on: date
    k_ref_w_m_k: float
    temp_coeff_per_k: float
    reference_temp_k: float
    calibration_offsets_c: tuple[float, ...]


@dataclass(frozen=True)
class Layer:
    name: str
    x_start_m: float
    x_end_m: float
    material: Material
    q_w_m3: float = 0.0


@dataclass(frozen=True)
class Contact:
    x_m: float
    r_contact_m2_k_w: float
    contact_temp_coeff_per_k: float = 0.0
    contact_t_ref_c: float = 25.0


@dataclass(frozen=True)
class Radiation:
    emissivity: float = 0.0
    view_factor: float = 1.0
    t_surround_c: float = 0.0


@dataclass(frozen=True)
class Facility:
    city: str
    region: str
    country: str
    installed_on: date
    measured_on: date


@dataclass(frozen=True)
class Case:
    case_id: str
    length_m: float
    num_cells: int
    area_m2: float
    t_left_c: float
    t_inf_c: float
    h_w_m2_k: float
    facility: Facility
    service_age_days: int
    layers: tuple[Layer, ...]
    contacts: tuple[Contact, ...] = ()
    right_radiation: Radiation = Radiation()


def parse_scalar(value: Any) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if not isinstance(value, str):
        raise TypeError(f"expected scalar, got {type(value).__name__}")
    text = value.strip().replace("\u00a0", "")
    if "," in text and "." not in text and text.count(",") == 1:
        left, right = text.split(",", 1)
        if left.strip("+-").isdigit() and right.isdigit():
            text = f"{left}.{right}"
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


def temperature_to_c(value: Any, unit: str) -> float:
    number = parse_scalar(value)
    if unit.strip().upper() == "K":
        return number - KELVIN_OFFSET
    return number


def material_from_dict(raw: dict[str, Any]) -> Material:
    facility = {
        "city": raw.get("facility_city", ""),
        "region": raw.get("facility_region", ""),
        "country": raw.get("facility_country", ""),
    }
    return Material(
        material_id=str(raw["material_id"]),
        certified_on=parse_facility_date(raw["certified_on"], facility),
        k_ref_w_m_k=parse_scalar(raw["k_ref_w_m_k"]),
        temp_coeff_per_k=parse_scalar(raw["temp_coeff_per_k"]),
        reference_temp_k=parse_scalar(raw["reference_temp_k"]),
        calibration_offsets_c=parse_vector(raw.get("calibration_offsets_c", "0")),
    )


def _load_default_materials() -> dict[str, Material]:
    material_path = Path(__file__).resolve().parents[1] / "data" / "materials_db.csv"
    with material_path.open(encoding="utf-8", newline="") as handle:
        materials = [material_from_dict(dict(row)) for row in csv.DictReader(handle, delimiter=";")]
    return {material.material_id: material for material in materials}


def normalize_case_dict(raw_input: dict[str, Any]) -> dict[str, Any]:
    raw = copy.deepcopy(raw_input)
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
    facility = copy.deepcopy(raw["facility"])
    installed = parse_facility_date(facility["installed_on"], facility)
    measured = parse_facility_date(facility["measured_on"], facility)
    normalized_facility = {
        "city": str(facility.get("city", "")),
        "region": str(facility.get("region", "")),
        "country": str(facility.get("country", "")),
        "installed_on": installed.isoformat(),
        "measured_on": measured.isoformat(),
    }
    temp_unit = str(raw.get("temperature_unit", "C"))
    layers = []
    for layer in raw["layers"]:
        layers.append(
            {
                "name": str(layer["name"]),
                "x_start_m": parse_scalar(layer["x_start_m"]) * unit_scale,
                "x_end_m": parse_scalar(layer["x_end_m"]) * unit_scale,
                "material_id": str(layer["material_id"]),
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
        "t_surround_c": temperature_to_c(radiation_raw.get("t_surround_c", raw["t_inf_c"]), temp_unit),
    }
    return {
        "case_id": str(raw["case_id"]),
        "length_m": parse_scalar(raw["length_m"]) * unit_scale,
        "num_cells": int(raw["num_cells"]),
        "area_m2": parse_scalar(raw.get("area_m2", 1.0)),
        "t_left_c": temperature_to_c(raw["t_left_c"], temp_unit),
        "t_inf_c": temperature_to_c(raw["t_inf_c"], temp_unit),
        "h_w_m2_k": parse_scalar(raw["h_w_m2_k"]),
        "facility": normalized_facility,
        "layers": layers,
        "contacts": contacts,
        "right_radiation": radiation,
    }


def facility_from_dict(raw: dict[str, Any]) -> Facility:
    installed = parse_facility_date(raw["installed_on"], raw)
    measured = parse_facility_date(raw["measured_on"], raw)
    return Facility(
        city=str(raw.get("city", "")),
        region=str(raw.get("region", "")),
        country=str(raw.get("country", "")),
        installed_on=installed,
        measured_on=measured,
    )


def layer_from_dict(raw: dict[str, Any], materials: dict[str, Material]) -> Layer:
    return Layer(
        name=str(raw["name"]),
        x_start_m=parse_scalar(raw["x_start_m"]),
        x_end_m=parse_scalar(raw["x_end_m"]),
        material=materials[str(raw["material_id"])],
        q_w_m3=parse_scalar(raw.get("q_w_m3", 0.0)),
    )


def contact_from_dict(raw: dict[str, Any]) -> Contact:
    return Contact(
        x_m=parse_scalar(raw["x_m"]),
        r_contact_m2_k_w=parse_scalar(raw["r_contact_m2_k_w"]),
        contact_temp_coeff_per_k=parse_scalar(raw.get("contact_temp_coeff_per_k", 0.0)),
        contact_t_ref_c=parse_scalar(raw.get("contact_t_ref_c", 25.0)),
    )


def radiation_from_dict(raw: dict[str, Any]) -> Radiation:
    return Radiation(
        emissivity=parse_scalar(raw.get("emissivity", 0.0)),
        view_factor=parse_scalar(raw.get("view_factor", 1.0)),
        t_surround_c=parse_scalar(raw.get("t_surround_c", 0.0)),
    )


def case_from_dict(raw_input: dict[str, Any], materials: dict[str, Material] | None = None) -> Case:
    raw = normalize_case_dict(raw_input)
    materials = _load_default_materials() if materials is None else materials
    facility = facility_from_dict(raw["facility"])
    return Case(
        case_id=str(raw["case_id"]),
        length_m=parse_scalar(raw["length_m"]),
        num_cells=int(raw["num_cells"]),
        area_m2=parse_scalar(raw["area_m2"]),
        t_left_c=parse_scalar(raw["t_left_c"]),
        t_inf_c=parse_scalar(raw["t_inf_c"]),
        h_w_m2_k=parse_scalar(raw["h_w_m2_k"]),
        facility=facility,
        service_age_days=max(0, (facility.measured_on - facility.installed_on).days),
        layers=tuple(layer_from_dict(item, materials) for item in raw["layers"]),
        contacts=tuple(contact_from_dict(item) for item in raw.get("contacts", [])),
        right_radiation=radiation_from_dict(raw.get("right_radiation", {})),
    )
''',
"thermal_stack/io.py": r'''"""JSON and CSV input/output helpers."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .models import Case, Material, case_from_dict, material_from_dict

APP_ROOT = Path(__file__).resolve().parents[1]


def load_materials(path: str | Path | None = None) -> dict[str, Material]:
    material_path = Path(path) if path is not None else APP_ROOT / "data" / "materials_db.csv"
    with material_path.open(encoding="utf-8", newline="") as handle:
        materials = [material_from_dict(dict(row)) for row in csv.DictReader(handle, delimiter=";")]
    return {material.material_id: material for material in materials}


def load_raw_cases(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if set(payload) != {"cases"} or not isinstance(payload["cases"], list):
        raise ValueError("input JSON must contain only a top-level cases array")
    return list(payload["cases"])


def load_cases(path: str | Path) -> list[Case]:
    materials = load_materials()
    return [case_from_dict(item, materials) for item in load_raw_cases(path)]


def write_results(path: str | Path, results: list[dict[str, Any]]) -> None:
    Path(path).write_text(json.dumps({"results": results}, indent=2) + "\n", encoding="utf-8")
''',
"thermal_stack/solver.py": r'''"""Finite-volume solver for thermal-stack calibration cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .models import Case, Layer, Material

KELVIN_OFFSET = 273.15
AGE_CONTACT_RATE = 2.0e-5
STEFAN_BOLTZMANN = 5.670374419e-8


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
    if not (0.0 <= case.right_radiation.emissivity <= 1.0):
        raise ValueError("radiation emissivity must be in [0, 1]")
    if not (0.0 <= case.right_radiation.view_factor <= 1.0):
        raise ValueError("radiation view_factor must be in [0, 1]")
    if case.right_radiation.t_surround_c <= -KELVIN_OFFSET:
        raise ValueError("radiation surround temperature must be above absolute zero")


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


def _radiation_active(case: Case) -> bool:
    return case.right_radiation.emissivity > 0.0 and case.right_radiation.view_factor > 0.0


def _radiation_h(case: Case, surface_temp_c: float | None) -> float:
    if not _radiation_active(case):
        return 0.0
    t_surface_k = KELVIN_OFFSET + (case.t_inf_c if surface_temp_c is None else surface_temp_c)
    t_surround_k = KELVIN_OFFSET + case.right_radiation.t_surround_c
    return (
        case.right_radiation.emissivity
        * case.right_radiation.view_factor
        * STEFAN_BOLTZMANN
        * (t_surface_k + t_surround_k)
        * (t_surface_k * t_surface_k + t_surround_k * t_surround_k)
    )


def _right_boundary_state(case: Case, h_rad: float) -> tuple[float, float]:
    if h_rad <= 0.0:
        return case.h_w_m2_k, case.t_inf_c
    h_total = case.h_w_m2_k + h_rad
    t_effective = (
        case.h_w_m2_k * case.t_inf_c + h_rad * case.right_radiation.t_surround_c
    ) / h_total
    return h_total, t_effective


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


def _assemble(case: Case, mesh: Mesh, h_rad: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    n = case.num_cells
    matrix = np.zeros((n, n), dtype=float)
    rhs = np.zeros(n, dtype=float)
    h_right, t_right_reference = _right_boundary_state(case, h_rad)
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
            g_right = _right_g(mesh.k_w_m_k[i], h_right, mesh.dx_m, case.area_m2)
            matrix[i, i] += g_right
            rhs[i] += g_right * t_right_reference
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


def _solve_core(
    case: Case,
    override_contacts: dict[int, float] | None = None,
    right_surface_temp_c: float | None = None,
) -> tuple:
    mesh = build_mesh(case, override_contacts=override_contacts)
    h_rad = _radiation_h(case, right_surface_temp_c)
    matrix, rhs = _assemble(case, mesh, h_rad=h_rad)
    temperatures = np.linalg.solve(matrix, rhs)
    h_right, t_right_reference = _right_boundary_state(case, h_rad)
    right_flow = _right_g(mesh.k_w_m_k[-1], h_right, mesh.dx_m, case.area_m2) * (
        float(temperatures[-1]) - t_right_reference
    )
    right_surface_c = float(temperatures[-1]) - right_flow * mesh.dx_m / (
        2.0 * mesh.k_w_m_k[-1] * case.area_m2
    )
    return mesh, temperatures, right_surface_c, h_rad


def solve_case(case: Case) -> dict[str, Any]:
    has_temp_dependent = any(
        c.contact_temp_coeff_per_k != 0.0 for c in case.contacts
    )
    has_radiation = _radiation_active(case)
    if not has_temp_dependent and not has_radiation:
        mesh, temperatures, right_surface_c, h_rad = _solve_core(case)
    else:
        dx = case.length_m / case.num_cells
        reff: dict[int, float] = {}
        for c in case.contacts:
            f = _face_index(c.x_m, dx)
            reff[f] = _aged_contact(c.r_contact_m2_k_w, case.service_age_days)
        right_surface_c: float | None = None
        h_rad = 0.0

        for _ in range(80):
            mesh, temperatures, solved_surface_c, h_rad = _solve_core(
                case,
                override_contacts=reff,
                right_surface_temp_c=right_surface_c,
            )
            diagnostics = _interface_diagnostics(case, mesh, temperatures)
            diag_by_face = {_face_index(d["x_m"], dx): d for d in diagnostics}
            new_reff = dict(reff)
            max_rel = 0.0
            for c in case.contacts:
                coeff = c.contact_temp_coeff_per_k
                if coeff == 0.0:
                    continue
                f = _face_index(c.x_m, dx)
                if f not in diag_by_face:
                    continue
                d = diag_by_face[f]
                t_eval_c = 0.5 * (d["temperature_left_c"] + d["temperature_right_c"])
                rn = _effective_contact(
                    c.r_contact_m2_k_w, coeff, c.contact_t_ref_c,
                    case.service_age_days, t_eval_c,
                )
                max_rel = max(max_rel, abs(rn - reff.get(f, 0.0)) / max(abs(reff.get(f, 0.0)), 1e-12))
                new_reff[f] = rn
            previous_surface = case.t_inf_c if right_surface_c is None else right_surface_c
            if has_radiation:
                max_rel = max(
                    max_rel,
                    abs(solved_surface_c - previous_surface) / max(abs(solved_surface_c), 1.0),
                )
            reff = new_reff
            right_surface_c = solved_surface_c
            if max_rel < 1e-6:
                break
        mesh, temperatures, right_surface_c, h_rad = _solve_core(
            case,
            override_contacts=reff,
            right_surface_temp_c=right_surface_c,
        )

    left_flow = _left_g(mesh.k_w_m_k[0], mesh.dx_m, case.area_m2) * (case.t_left_c - float(temperatures[0]))
    h_right, t_right_reference = _right_boundary_state(case, h_rad)
    right_flow = _right_g(mesh.k_w_m_k[-1], h_right, mesh.dx_m, case.area_m2) * (
        float(temperatures[-1]) - t_right_reference
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
''',
"scripts/local_smoke.py": r'''#!/usr/bin/env python3
"""Loose local smoke checker used by facility technicians."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True)
    args = parser.parse_args()
    payload = json.loads(Path(args.results).read_text(encoding="utf-8"))
    worst = 0.0
    for result in payload.get("results", []):
        worst = max(worst, abs(float(result.get("energy_residual_w_m2", 0.0))))
        for value in result.get("temperature_c", []):
            if not math.isfinite(float(value)):
                print("not converged: non-finite temperature")
                return 1
    if worst < 1000.0:
        print("Converged! local smoke check passed")
    else:
        print("Warning: local residual diagnostic is outside the technician smoke threshold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
''',
}

for rel_path, content in FILES.items():
    path = app_dir / rel_path
    path.write_text(content, encoding="utf-8")

print("oracle: material-id calibration fix applied")
PYSOLVE
