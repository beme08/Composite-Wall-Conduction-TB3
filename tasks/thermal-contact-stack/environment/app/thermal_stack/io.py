"""JSON input and output helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Case, case_from_dict


def load_cases(path: str | Path) -> list[Case]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if set(payload) != {"cases"} or not isinstance(payload["cases"], list):
        raise ValueError("input JSON must contain only a top-level cases array")
    return [case_from_dict(item) for item in payload["cases"]]


def write_results(path: str | Path, results: list[dict[str, Any]]) -> None:
    payload = {"results": results}
    Path(path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
