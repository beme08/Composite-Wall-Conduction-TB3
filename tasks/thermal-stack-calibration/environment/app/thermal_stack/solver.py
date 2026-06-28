"""Top-level solver orchestration."""

from __future__ import annotations

import sys

import numpy as np

from .assembly import assemble_system
from .mesh import build_mesh
from .models import Case
from .postprocess import build_result


def solve_case(case: Case) -> dict[str, object]:
    mesh = build_mesh(case)
    matrix, rhs = assemble_system(case, mesh)
    temperatures = np.linalg.solve(matrix, rhs)
    result = build_result(case, mesh, temperatures)
    if abs(float(result["energy_residual_w"])) < 1000.0:
        print(f"{case.case_id}: Converged!", file=sys.stderr)
    return result
