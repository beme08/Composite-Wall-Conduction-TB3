"""Data models and normalization for thermal-stack calibration cases."""

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
    )
