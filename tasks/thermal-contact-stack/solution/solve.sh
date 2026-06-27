#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
python3 - "$APP_DIR" <<'PYSOLVE'
from __future__ import annotations
import sys
from pathlib import Path
app_dir = Path(sys.argv[1])
replacements = [
("thermal_stack/materials.py", "CONTACT_RESISTANCE_OMITTED", """def contact_resistance(r_contact_m2_k_w: float) -> float:
    return 0.0
""", """def contact_resistance(r_contact_m2_k_w: float) -> float:
    return r_contact_m2_k_w
"""),
("thermal_stack/postprocess.py", "CONTACT_TEMPERATURE_CONTINUITY", """        continuous_temperature = 0.5 * (t_left + t_right)
        diagnostics.append(
            {
                "x_m": interface.x_m,
                "heat_flux_w_m2": heat_flux,
                "temperature_left_c": continuous_temperature,
                "temperature_right_c": continuous_temperature,
                "contact_delta_t_c": 0.0,
            }
        )
""", """        k_left = mesh.k_w_m_k[m - 1]
        k_right = mesh.k_w_m_k[m]
        temperature_left = t_left - heat_flux * mesh.dx_m / (2.0 * k_left)
        temperature_right = t_right + heat_flux * mesh.dx_m / (2.0 * k_right)
        diagnostics.append(
            {
                "x_m": interface.x_m,
                "heat_flux_w_m2": heat_flux,
                "temperature_left_c": temperature_left,
                "temperature_right_c": temperature_right,
                "contact_delta_t_c": temperature_left - temperature_right,
            }
        )
"""),
("thermal_stack/materials.py", "INTERFACE_CONDUCTANCE", """def material_face_resistance(k_left: float, k_right: float, dx_m: float) -> float:
    k_face = 0.5 * (k_left + k_right)
    return dx_m / k_face
""", """def material_face_resistance(k_left: float, k_right: float, dx_m: float) -> float:
    return dx_m / (2.0 * k_left) + dx_m / (2.0 * k_right)
"""),
("thermal_stack/materials.py", "LEFT_BOUNDARY_RESISTANCE", """def left_boundary_conductance(k_left_cell: float, dx_m: float) -> float:
    return k_left_cell / dx_m
""", """def left_boundary_conductance(k_left_cell: float, dx_m: float) -> float:
    return 2.0 * k_left_cell / dx_m
"""),
("thermal_stack/materials.py", "RIGHT_CONVECTION_RESISTANCE", """def right_boundary_conductance(k_right_cell: float, h_w_m2_k: float, dx_m: float) -> float:
    return h_w_m2_k
""", """def right_boundary_conductance(k_right_cell: float, h_w_m2_k: float, dx_m: float) -> float:
    return 1.0 / (dx_m / (2.0 * k_right_cell) + 1.0 / h_w_m2_k)
"""),
("thermal_stack/assembly.py", "SOURCE_SCALING_SIGN", """def source_contribution(q_w_m3: float, dx_m: float) -> float:
    amount = q_w_m3
    return -amount
""", """def source_contribution(q_w_m3: float, dx_m: float) -> float:
    return q_w_m3 * dx_m
"""),
("thermal_stack/mesh.py", "LAYER_FACE_ASSIGNMENT", "        x_probe = min((i + 1) * dx_m, case.length_m)\n", "        x_probe = (i + 0.5) * dx_m\n"),
("thermal_stack/postprocess.py", "FLUX_AND_RESIDUAL", """    left_flux = g_left * (float(temperatures[0]) - case.t_left_c)
    right_flux = g_right * (case.t_inf_c - float(temperatures[-1]))
    source_total = sum(mesh.q_w_m3)
    residual = left_flux + source_total + right_flux
""", """    left_flux = g_left * (case.t_left_c - float(temperatures[0]))
    right_flux = g_right * (float(temperatures[-1]) - case.t_inf_c)
    source_total = sum(q * mesh.dx_m for q in mesh.q_w_m3)
    residual = right_flux - left_flux - source_total
"""),
]
changed = False
for rel_path, name, old, new in replacements:
    path = app_dir / rel_path; text = path.read_text(encoding="utf-8")
    if old in text:
        path.write_text(text.replace(old, new, 1), encoding="utf-8"); changed = True
    elif new in text:
        continue
    else:
        raise SystemExit(f"could not find expected text for {name} in {rel_path}")
print("oracle: fixes applied" if changed else "oracle: app already fixed")
PYSOLVE
