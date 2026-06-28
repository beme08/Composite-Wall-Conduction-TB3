"""JSON and CSV input/output helpers."""

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
        rows = csv.DictReader(handle, delimiter=";")
        materials = [material_from_dict(dict(row)) for row in rows]
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
    payload = {"results": results}
    Path(path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
