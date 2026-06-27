"""Data models and JSON normalization for thermal-stack cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
class Case:
    case_id: str
    length_m: float
    num_cells: int
    t_left_c: float
    t_inf_c: float
    h_w_m2_k: float
    layers: tuple[Layer, ...]
    contacts: tuple[Contact, ...] = ()


def layer_from_dict(raw: dict[str, Any]) -> Layer:
    return Layer(str(raw["name"]), float(raw["x_start_m"]), float(raw["x_end_m"]), float(raw["k_w_m_k"]), float(raw.get("q_w_m3", 0.0)))


def contact_from_dict(raw: dict[str, Any]) -> Contact:
    return Contact(float(raw["x_m"]), float(raw["r_contact_m2_k_w"]))


def case_from_dict(raw: dict[str, Any]) -> Case:
    return Case(
        case_id=str(raw["case_id"]),
        length_m=float(raw["length_m"]),
        num_cells=int(raw["num_cells"]),
        t_left_c=float(raw["t_left_c"]),
        t_inf_c=float(raw["t_inf_c"]),
        h_w_m2_k=float(raw["h_w_m2_k"]),
        layers=tuple(layer_from_dict(item) for item in raw["layers"]),
        contacts=tuple(contact_from_dict(item) for item in raw.get("contacts", [])),
    )
