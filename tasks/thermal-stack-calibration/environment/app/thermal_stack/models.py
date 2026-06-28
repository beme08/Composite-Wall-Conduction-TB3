"""Data models and JSON normalization for thermal-stack cases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


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


def normalize_case_dict(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw case dictionary before typed model construction."""
    # Legacy behavior mutates in place and applies mm conversion repeatedly.
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
    if str(raw.get("length_unit", "m")).lower() == "mm":
        raw["length_m"] = _scalar(raw["length_m"]) / 1000.0
    return raw


def _scalar(value: Any) -> float:
    text = str(value).strip().replace(",", ".")
    return float(text)


def _vector(value: Any) -> tuple[float, ...]:
    text = str(value).strip().replace(",", ".")
    try:
        return tuple(float(part.strip()) for part in text.split(",") if part.strip())
    except ValueError:
        return (0.0,)


def _parse_date(value: Any, facility: dict[str, Any]) -> date:
    text = str(value).strip()
    if "-" in text:
        return datetime.strptime(text, "%Y-%m-%d").date()
    # Legacy parser treats numeric dates as US dates everywhere.
    try:
        return datetime.strptime(text, "%m/%d/%Y").date()
    except ValueError:
        return datetime.strptime(text, "%d/%m/%Y").date()


def _temperature_to_c(value: Any, unit: str) -> float:
    # Kelvin inputs are accidentally passed through as Celsius.
    return _scalar(value)


def material_from_dict(raw: dict[str, Any]) -> Material:
    facility = {
        "city": raw.get("facility_city", ""),
        "region": raw.get("facility_region", ""),
        "country": raw.get("facility_country", ""),
    }
    return Material(
        material_id=str(raw["material_id"]),
        certified_on=_parse_date(raw["certified_on"], facility),
        k_ref_w_m_k=_scalar(raw["k_ref_w_m_k"]),
        temp_coeff_per_k=_scalar(raw["temp_coeff_per_k"]),
        reference_temp_k=_scalar(raw["reference_temp_k"]),
        calibration_offsets_c=_vector(raw.get("calibration_offsets_c", "0")),
    )


def facility_from_dict(raw: dict[str, Any]) -> Facility:
    return Facility(
        city=str(raw.get("city", "")),
        region=str(raw.get("region", "")),
        country=str(raw.get("country", "")),
        installed_on=_parse_date(raw["installed_on"], raw),
        measured_on=_parse_date(raw["measured_on"], raw),
    )


def layer_from_dict(raw: dict[str, Any], materials: dict[str, Material], unit_scale: float) -> Layer:
    material_id = str(raw["material_id"])
    return Layer(
        name=str(raw["name"]),
        x_start_m=_scalar(raw["x_start_m"]) * unit_scale,
        x_end_m=_scalar(raw["x_end_m"]) * unit_scale,
        material=materials[material_id],
        q_w_m3=_scalar(raw.get("q_w_m3", 0.0)),
    )


def contact_from_dict(raw: dict[str, Any], unit_scale: float) -> Contact:
    return Contact(_scalar(raw["x_m"]) * unit_scale, _scalar(raw["r_contact_m2_k_w"]))


def case_from_dict(raw_input: dict[str, Any], materials: dict[str, Material]) -> Case:
    raw = normalize_case_dict(raw_input)
    unit_scale = 0.001 if str(raw.get("length_unit", "m")).lower() == "mm" else 1.0
    facility = facility_from_dict(raw["facility"])
    temp_unit = str(raw.get("temperature_unit", "C"))
    return Case(
        case_id=str(raw["case_id"]),
        length_m=_scalar(raw["length_m"]) * unit_scale,
        num_cells=int(raw["num_cells"]),
        area_m2=_scalar(raw.get("area_m2", 1.0)),
        t_left_c=_temperature_to_c(raw["t_left_c"], temp_unit),
        t_inf_c=_temperature_to_c(raw["t_inf_c"], temp_unit),
        h_w_m2_k=_scalar(raw["h_w_m2_k"]),
        facility=facility,
        service_age_days=max(0, (facility.measured_on - facility.installed_on).days),
        layers=tuple(layer_from_dict(item, materials, unit_scale) for item in raw["layers"]),
        contacts=tuple(contact_from_dict(item, unit_scale) for item in raw.get("contacts", [])),
    )
