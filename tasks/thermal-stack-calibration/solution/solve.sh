#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
python3 - "$APP_DIR" <<'PYSOLVE'
from __future__ import annotations

import sys
from pathlib import Path

app_dir = Path(sys.argv[1])

FILES = {
"thermal_stack/models.py": r'''"""Data models and JSON normalization for thermal-stack cases."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

KELVIN_OFFSET = 273.15


@dataclass(frozen=True)
class Layer:
    name: str
    x_start_m: float
    x_end_m: float
    k_w_m_k: float
    q_w_m3: float = 0.0


@dataclass(frozen=True)
class Contact:
    x_m: float
    r_contact_m2_k_w: float


@dataclass(frozen=True)
class Facility:
    city: str
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
    radiation_enabled: bool
    emissivity: float
    facility: Facility
    service_age_days: int
    layers: tuple[Layer, ...]
    contacts: tuple[Contact, ...] = ()


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


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def parse_facility_date(value: Any, facility: dict[str, Any]) -> date:
    text = str(value).strip()
    if "-" in text:
        return datetime.strptime(text, "%Y-%m-%d").date()
    country = str(facility.get("country", "")).strip().lower()
    city = str(facility.get("city", "")).strip().lower()
    us_context = country in {"us", "usa", "united states"} or city in {"austin", "phoenix", "boston"}
    return datetime.strptime(text, "%m/%d/%Y" if us_context else "%d/%m/%Y").date()


def temperature_to_c(value: Any, unit: str) -> float:
    number = parse_scalar(value)
    if unit.strip().upper() == "K":
        return number - KELVIN_OFFSET
    return number


def normalize_case_dict(raw_input: dict[str, Any]) -> dict[str, Any]:
    raw = copy.deepcopy(raw_input)
    raw.setdefault("area_m2", 1.0)
    raw.setdefault("temperature_unit", "C")
    raw.setdefault("radiation_enabled", False)
    raw.setdefault("emissivity", 0.0)
    raw.setdefault(
        "facility",
        {
            "city": "Austin",
            "country": "US",
            "installed_on": "01/01/2024",
            "measured_on": "01/02/2024",
        },
    )
    facility = copy.deepcopy(raw["facility"])
    installed = parse_facility_date(facility["installed_on"], facility)
    measured = parse_facility_date(facility["measured_on"], facility)
    facility["installed_on"] = installed.isoformat()
    facility["measured_on"] = measured.isoformat()
    length_unit = str(raw.get("length_unit", "m")).lower()
    unit_scale = 0.001 if length_unit == "mm" else 1.0
    if "length_mm" in raw:
        length_m = parse_scalar(raw["length_mm"]) / 1000.0
        unit_scale = 0.001 if length_unit == "mm" else 1.0
    else:
        length_m = parse_scalar(raw["length_m"]) * unit_scale
    layers = []
    for layer in raw["layers"]:
        layers.append(
            {
                "name": str(layer["name"]),
                "x_start_m": parse_scalar(layer["x_start_m"]) * unit_scale,
                "x_end_m": parse_scalar(layer["x_end_m"]) * unit_scale,
                "k_w_m_k": parse_scalar(layer["k_w_m_k"]),
                "q_w_m3": parse_scalar(layer.get("q_w_m3", 0.0)),
            }
        )
    contacts = []
    for contact in raw.get("contacts", []):
        contacts.append(
            {
                "x_m": parse_scalar(contact["x_m"]) * unit_scale,
                "r_contact_m2_k_w": parse_scalar(contact["r_contact_m2_k_w"]),
            }
        )
    normalized = {
        "case_id": str(raw["case_id"]),
        "length_m": length_m,
        "num_cells": int(raw["num_cells"]),
        "area_m2": parse_scalar(raw.get("area_m2", 1.0)),
        "t_left_c": temperature_to_c(raw["t_left_c"], str(raw.get("temperature_unit", "C"))),
        "t_inf_c": temperature_to_c(raw["t_inf_c"], str(raw.get("temperature_unit", "C"))),
        "h_w_m2_k": parse_scalar(raw["h_w_m2_k"]),
        "radiation_enabled": parse_bool(raw.get("radiation_enabled", False)),
        "emissivity": parse_scalar(raw.get("emissivity", 0.0)),
        "facility": facility,
        "layers": layers,
        "contacts": contacts,
    }
    if "sensor_offsets_c" in raw:
        normalized["sensor_offsets_c"] = raw["sensor_offsets_c"]
    return normalized


def layer_from_dict(raw: dict[str, Any]) -> Layer:
    return Layer(
        str(raw["name"]),
        parse_scalar(raw["x_start_m"]),
        parse_scalar(raw["x_end_m"]),
        parse_scalar(raw["k_w_m_k"]),
        parse_scalar(raw.get("q_w_m3", 0.0)),
    )


def contact_from_dict(raw: dict[str, Any]) -> Contact:
    return Contact(parse_scalar(raw["x_m"]), parse_scalar(raw["r_contact_m2_k_w"]))


def facility_from_dict(raw: dict[str, Any]) -> Facility:
    installed = parse_facility_date(raw["installed_on"], raw)
    measured = parse_facility_date(raw["measured_on"], raw)
    return Facility(str(raw.get("city", "")), str(raw.get("country", "")), installed, measured)


def case_from_dict(raw_input: dict[str, Any]) -> Case:
    raw = normalize_case_dict(raw_input)
    facility = facility_from_dict(raw["facility"])
    return Case(
        case_id=str(raw["case_id"]),
        length_m=parse_scalar(raw["length_m"]),
        num_cells=int(raw["num_cells"]),
        area_m2=parse_scalar(raw["area_m2"]),
        t_left_c=parse_scalar(raw["t_left_c"]),
        t_inf_c=parse_scalar(raw["t_inf_c"]),
        h_w_m2_k=parse_scalar(raw["h_w_m2_k"]),
        radiation_enabled=parse_bool(raw["radiation_enabled"]),
        emissivity=parse_scalar(raw["emissivity"]),
        facility=facility,
        service_age_days=max(0, (facility.measured_on - facility.installed_on).days),
        layers=tuple(layer_from_dict(item) for item in raw["layers"]),
        contacts=tuple(contact_from_dict(item) for item in raw.get("contacts", [])),
    )
''',
"thermal_stack/materials.py": r'''"""Conductance models for finite-volume faces and boundaries."""

from __future__ import annotations

STEFAN_BOLTZMANN = 5.670374419e-8
KELVIN_OFFSET = 273.15
AGE_CONTACT_RATE = 2.0e-5


def contact_resistance(r_contact_m2_k_w: float, service_age_days: int = 0) -> float:
    return r_contact_m2_k_w * (1.0 + AGE_CONTACT_RATE * service_age_days)


def internal_face_conductance(
    k_left: float,
    k_right: float,
    r_contact_m2_k_w: float,
    dx_m: float,
    area_m2: float = 1.0,
    service_age_days: int = 0,
) -> float:
    r_contact = contact_resistance(r_contact_m2_k_w, service_age_days)
    return area_m2 / (dx_m / (2.0 * k_left) + r_contact + dx_m / (2.0 * k_right))


def left_boundary_conductance(k_left_cell: float, dx_m: float, area_m2: float = 1.0) -> float:
    return area_m2 / (dx_m / (2.0 * k_left_cell))


def radiation_coefficient(t_inf_c: float, emissivity: float, radiation_enabled: bool) -> float:
    if not radiation_enabled:
        return 0.0
    t_inf_k = t_inf_c + KELVIN_OFFSET
    return 4.0 * emissivity * STEFAN_BOLTZMANN * (t_inf_k**3)


def right_boundary_conductance(
    k_right_cell: float,
    h_w_m2_k: float,
    dx_m: float,
    area_m2: float = 1.0,
    t_inf_c: float = 25.0,
    emissivity: float = 0.0,
    radiation_enabled: bool = False,
) -> float:
    h_total = h_w_m2_k + radiation_coefficient(t_inf_c, emissivity, radiation_enabled)
    return area_m2 / (dx_m / (2.0 * k_right_cell) + 1.0 / h_total)
''',
"thermal_stack/mesh.py": r'''"""Mesh construction and material/contact mapping."""

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
    if case.area_m2 <= 0.0:
        raise ValueError("area_m2 must be positive")
    if not (0.0 < case.h_w_m2_k <= 10000.0):
        raise ValueError("h_w_m2_k must be in (0, 10000]")
    if not (0.0 <= case.emissivity <= 1.0):
        raise ValueError("emissivity must be in [0, 1]")
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
    for x_probe in x_m:
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
''',
"thermal_stack/assembly.py": r'''"""Linear finite-volume system assembly."""

from __future__ import annotations

import numpy as np

from .materials import internal_face_conductance, left_boundary_conductance, right_boundary_conductance
from .mesh import Mesh
from .models import Case


def source_contribution(q_w_m3: float, dx_m: float, area_m2: float) -> float:
    return q_w_m3 * dx_m * area_m2


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
            g_right = right_boundary_conductance(
                mesh.k_w_m_k[i],
                case.h_w_m2_k,
                mesh.dx_m,
                case.area_m2,
                case.t_inf_c,
                case.emissivity,
                case.radiation_enabled,
            )
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
''',
"thermal_stack/postprocess.py": r'''"""Output diagnostics for solved thermal-stack cases."""

from __future__ import annotations

from typing import Any

import numpy as np

from .materials import (
    contact_resistance,
    internal_face_conductance,
    left_boundary_conductance,
    right_boundary_conductance,
)
from .mesh import Mesh
from .models import Case


def interface_diagnostics(case: Case, mesh: Mesh, temperatures: np.ndarray) -> list[dict[str, float]]:
    diagnostics: list[dict[str, float]] = []
    for interface in mesh.interfaces:
        m = interface.face_index
        t_left = float(temperatures[m - 1])
        t_right = float(temperatures[m])
        k_left = mesh.k_w_m_k[m - 1]
        k_right = mesh.k_w_m_k[m]
        r_contact = contact_resistance(interface.r_contact_m2_k_w, case.service_age_days)
        g_face = internal_face_conductance(k_left, k_right, interface.r_contact_m2_k_w, mesh.dx_m, case.area_m2, case.service_age_days)
        heat_flow = g_face * (t_left - t_right)
        heat_flux = heat_flow / case.area_m2
        temperature_left = t_left - heat_flow * mesh.dx_m / (2.0 * k_left * case.area_m2)
        temperature_right = t_right + heat_flow * mesh.dx_m / (2.0 * k_right * case.area_m2)
        diagnostics.append(
            {
                "x_m": interface.x_m,
                "heat_flux_w_m2": heat_flux,
                "heat_flow_w": heat_flow,
                "temperature_left_c": temperature_left,
                "temperature_right_c": temperature_right,
                "contact_delta_t_c": heat_flow * r_contact / case.area_m2,
            }
        )
    return diagnostics


def fluxes_and_residual(case: Case, mesh: Mesh, temperatures: np.ndarray) -> tuple[float, float, float, float, float]:
    g_left = left_boundary_conductance(mesh.k_w_m_k[0], mesh.dx_m, case.area_m2)
    g_right = right_boundary_conductance(
        mesh.k_w_m_k[-1],
        case.h_w_m2_k,
        mesh.dx_m,
        case.area_m2,
        case.t_inf_c,
        case.emissivity,
        case.radiation_enabled,
    )
    left_flow = g_left * (case.t_left_c - float(temperatures[0]))
    right_flow = g_right * (float(temperatures[-1]) - case.t_inf_c)
    source_total = sum(q * mesh.dx_m * case.area_m2 for q in mesh.q_w_m3)
    residual = right_flow - left_flow - source_total
    return left_flow / case.area_m2, right_flow / case.area_m2, left_flow, right_flow, residual


def build_result(case: Case, mesh: Mesh, temperatures: np.ndarray) -> dict[str, Any]:
    left_flux, right_flux, left_flow, right_flow, residual = fluxes_and_residual(case, mesh, temperatures)
    return {
        "case_id": case.case_id,
        "x_m": [float(value) for value in mesh.x_m],
        "temperature_c": [float(value) for value in temperatures],
        "interface_diagnostics": interface_diagnostics(case, mesh, temperatures),
        "left_heat_flux_w_m2": float(left_flux),
        "right_heat_flux_w_m2": float(right_flux),
        "left_heat_flow_w": float(left_flow),
        "right_heat_flow_w": float(right_flow),
        "max_temperature_c": float(np.max(temperatures)),
        "energy_residual_w": float(residual),
    }
''',
"thermal_stack/solver.py": r'''"""Top-level solver orchestration."""

from __future__ import annotations

import numpy as np

from .assembly import assemble_system
from .mesh import build_mesh
from .models import Case
from .postprocess import build_result


def solve_case(case: Case) -> dict[str, object]:
    mesh = build_mesh(case)
    matrix, rhs = assemble_system(case, mesh)
    temperatures = np.linalg.solve(matrix, rhs)
    return build_result(case, mesh, temperatures)
''',
"thermal_stack/io.py": r'''"""JSON input and output helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Case, case_from_dict


def load_raw_cases(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if set(payload) != {"cases"} or not isinstance(payload["cases"], list):
        raise ValueError("input JSON must contain only a top-level cases array")
    return list(payload["cases"])


def load_cases(path: str | Path) -> list[Case]:
    return [case_from_dict(item) for item in load_raw_cases(path)]


def write_results(path: str | Path, results: list[dict[str, Any]]) -> None:
    payload = {"results": results}
    Path(path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
''',
}

for rel_path, content in FILES.items():
    path = app_dir / rel_path
    path.write_text(content, encoding="utf-8")

print("oracle: v3 cluster fixes applied")
PYSOLVE
