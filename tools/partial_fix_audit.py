#!/usr/bin/env python3
"""Cluster and wrong-fix audit for thermal-stack-calibration."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = ROOT / "tasks" / "thermal-stack-calibration"
APP_TEMPLATE = TASK_DIR / "environment" / "app"
TESTS_DIR = TASK_DIR / "tests"
SOLUTION = TASK_DIR / "solution" / "solve.sh"
DEFAULT_REPORT = TASK_DIR / "tests" / "fixtures" / "audit_report.json"

CLUSTERS = [
    "A_facility_normalization",
    "B_local_validation_schema",
    "C_state_order_coupling",
    "D_area_contact_temperature",
    "E_contact_consistency",
    "F_radiation_boundary_coupling",
]
ALL_MASK = (1 << len(CLUSTERS)) - 1


def _replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"expected snippet not found in {path.relative_to(path.parents[1])}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _append_after(path: Path, marker: str, addition: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker not in text:
        raise RuntimeError(f"expected marker not found in {path.relative_to(path.parents[1])}")
    path.write_text(text.replace(marker, marker + addition, 1), encoding="utf-8")


def mutate_all_t_to_k(app_dir: Path) -> None:
    _replace(
        app_dir / "thermal_stack" / "models.py",
        '''def temperature_to_c(value: Any, unit: str) -> float:
    number = parse_scalar(value)
    if unit.strip().upper() == "K":
        return number - KELVIN_OFFSET
    return number
''',
        '''def temperature_to_c(value: Any, unit: str) -> float:
    number = parse_scalar(value)
    return number + KELVIN_OFFSET
''',
    )


def mutate_dates_us(app_dir: Path) -> None:
    _replace(
        app_dir / "thermal_stack" / "models.py",
        '    return datetime.strptime(text, "%m/%d/%Y" if us_context else "%d/%m/%Y").date()\n',
        '    return datetime.strptime(text, "%m/%d/%Y").date()\n',
    )


def mutate_dates_eu(app_dir: Path) -> None:
    _replace(
        app_dir / "thermal_stack" / "models.py",
        '    return datetime.strptime(text, "%m/%d/%Y" if us_context else "%d/%m/%Y").date()\n',
        '    return datetime.strptime(text, "%d/%m/%Y").date()\n',
    )


def mutate_global_comma(app_dir: Path) -> None:
    _replace(
        app_dir / "thermal_stack" / "models.py",
        '    return tuple(float(part.strip()) for part in str(value).split(",") if part.strip())\n',
        '    return (parse_scalar(str(value).replace(",", ".")),)\n',
    )


def mutate_harmonic_only(app_dir: Path) -> None:
    _replace(
        app_dir / "thermal_stack" / "solver.py",
        '    return area_m2 / (dx_m / (2.0 * k_left) + r_contact + dx_m / (2.0 * k_right))\n',
        '    return area_m2 / (dx_m / ((2.0 * k_left * k_right) / (k_left + k_right)))\n',
    )


def mutate_area_twice(app_dir: Path) -> None:
    _replace(
        app_dir / "thermal_stack" / "solver.py",
        '    return area_m2 / (dx_m / (2.0 * k_left) + r_contact + dx_m / (2.0 * k_right))\n',
        '    return (area_m2 * area_m2) / (dx_m / (2.0 * k_left) + r_contact + dx_m / (2.0 * k_right))\n',
    )


def mutate_cache_unchanged(app_dir: Path) -> None:
    solver_path = app_dir / "thermal_stack" / "solver.py"
    _append_after(
        solver_path,
        '''class Mesh:
    dx_m: float
    x_m: list[float]
    k_w_m_k: list[float]
    q_w_m3: list[float]
    face_contact_r: list[float]
    interfaces: list[Interface]

''',
        "_MESH_CACHE = {}\n\n",
    )
    _replace(
        solver_path,
        '''def build_mesh(case: Case, override_contacts: dict[int, float] | None = None) -> Mesh:
    validate_case(case)
    dx_m = case.length_m / case.num_cells
''',
        '''def build_mesh(case: Case, override_contacts: dict[int, float] | None = None) -> Mesh:
    validate_case(case)
    key = (
        case.length_m,
        case.num_cells,
        tuple((layer.name, layer.x_start_m, layer.x_end_m) for layer in case.layers),
    )
    cached = _MESH_CACHE.get(key)
    if cached is not None:
        return cached
    dx_m = case.length_m / case.num_cells
''',
    )
    _replace(
        solver_path,
        "    return Mesh(dx_m, x_values, k_values, q_values, face_contact_r, interfaces)\n",
        '''    mesh = Mesh(dx_m, x_values, k_values, q_values, face_contact_r, interfaces)
    _MESH_CACHE[key] = mesh
    return mesh
''',
    )


def mutate_loose_convergence(app_dir: Path) -> None:
    _replace(
        app_dir / "thermal_stack" / "solver.py",
        '        "energy_residual_w_m2": float(energy_residual / case.area_m2),\n',
        '        "energy_residual_w_m2": 0.0,\n        "solver_status": "Converged!",\n',
    )


def mutate_temp_coeff_uses_celsius(app_dir: Path) -> None:
    _replace(
        app_dir / "thermal_stack" / "solver.py",
        "    eval_temp_k = KELVIN_OFFSET + 0.5 * (t_left_c + t_inf_c) + sum(offsets) / len(offsets)\n",
        "    eval_temp_k = 0.5 * (t_left_c + t_inf_c) + sum(offsets) / len(offsets)\n",
    )


def mutate_two_pass_only(app_dir: Path) -> None:
    """Replace fixed-point contact convergence with a single two-pass correction."""
    _replace(
        app_dir / "thermal_stack" / "solver.py",
        '''        for _ in range(80):
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
                break''',
        '''        mesh, temperatures, right_surface_c, h_rad = _solve_core(case, override_contacts=reff)
        diagnostics = _interface_diagnostics(case, mesh, temperatures)
        diag_by_face = {_face_index(d["x_m"], dx): d for d in diagnostics}
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
            reff[f] = rn''',
    )


def mutate_ignore_radiation(app_dir: Path) -> None:
    _replace(
        app_dir / "thermal_stack" / "solver.py",
        '''def _radiation_active(case: Case) -> bool:
    return case.right_radiation.emissivity > 0.0 and case.right_radiation.view_factor > 0.0
''',
        '''def _radiation_active(case: Case) -> bool:
    return False
''',
    )


def mutate_constant_ambient_radiation(app_dir: Path) -> None:
    _replace(
        app_dir / "thermal_stack" / "solver.py",
        "    t_surface_k = KELVIN_OFFSET + (case.t_inf_c if surface_temp_c is None else surface_temp_c)\n",
        "    t_surface_k = KELVIN_OFFSET + case.t_inf_c\n",
    )


def mutate_celsius_radiation(app_dir: Path) -> None:
    _replace(
        app_dir / "thermal_stack" / "solver.py",
        '''    t_surface_k = KELVIN_OFFSET + (case.t_inf_c if surface_temp_c is None else surface_temp_c)
    t_surround_k = KELVIN_OFFSET + case.right_radiation.t_surround_c
''',
        '''    t_surface_k = case.t_inf_c if surface_temp_c is None else surface_temp_c
    t_surround_k = case.right_radiation.t_surround_c
''',
    )


def mutate_radiation_replaces_convection(app_dir: Path) -> None:
    _replace(
        app_dir / "thermal_stack" / "solver.py",
        '''    h_total = case.h_w_m2_k + h_rad
    t_effective = (
        case.h_w_m2_k * case.t_inf_c + h_rad * case.right_radiation.t_surround_c
    ) / h_total
''',
        '''    h_total = h_rad
    t_effective = case.right_radiation.t_surround_c
''',
    )


def mutate_wrong_surround_temp(app_dir: Path) -> None:
    _replace(
        app_dir / "thermal_stack" / "solver.py",
        "    t_surround_k = KELVIN_OFFSET + case.right_radiation.t_surround_c\n",
        "    t_surround_k = KELVIN_OFFSET + case.t_inf_c\n",
    )
    _replace(
        app_dir / "thermal_stack" / "solver.py",
        "        case.h_w_m2_k * case.t_inf_c + h_rad * case.right_radiation.t_surround_c\n",
        "        case.h_w_m2_k * case.t_inf_c + h_rad * case.t_inf_c\n",
    )


WRONG_FIX_PROBES: dict[str, Callable[[Path], None]] = {
    "all_T_to_K": mutate_all_t_to_k,
    "dates_US": mutate_dates_us,
    "dates_EU": mutate_dates_eu,
    "global_comma": mutate_global_comma,
    "harmonic_only": mutate_harmonic_only,
    "area_twice": mutate_area_twice,
    "cache_unchanged": mutate_cache_unchanged,
    "loose_convergence": mutate_loose_convergence,
    "temp_coeff_uses_celsius": mutate_temp_coeff_uses_celsius,
    "two_pass_only": mutate_two_pass_only,
    "radiation_ignored": mutate_ignore_radiation,
    "radiation_constant_ambient": mutate_constant_ambient_radiation,
    "radiation_celsius": mutate_celsius_radiation,
    "radiation_replaces_convection": mutate_radiation_replaces_convection,
    "radiation_wrong_surround": mutate_wrong_surround_temp,
}

CLUSTER_MISSING_MUTATIONS: dict[str, Callable[[Path], None]] = {
    "A_facility_normalization": mutate_dates_us,
    "B_local_validation_schema": mutate_loose_convergence,
    "C_state_order_coupling": mutate_cache_unchanged,
    "D_area_contact_temperature": mutate_harmonic_only,
    "E_contact_consistency": mutate_two_pass_only,
    "F_radiation_boundary_coupling": mutate_ignore_radiation,
}


def run_cmd(cmd: list[str], *, env: dict[str, str] | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    full_env = os.environ.copy()
    full_env["PYTHONDONTWRITEBYTECODE"] = "1"
    if env:
        full_env.update(env)
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=full_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def apply_oracle(app_dir: Path) -> str:
    proc = run_cmd(["bash", str(SOLUTION)], env={"APP_DIR": str(app_dir)}, cwd=ROOT)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "oracle failed")
    return proc.stdout.strip()


def score_app(app_dir: Path) -> tuple[float, str]:
    with tempfile.TemporaryDirectory(prefix="tscal-score-") as tmp:
        log_dir = Path(tmp) / "logs"
        proc = run_cmd(
            ["bash", str(TESTS_DIR / "test.sh")],
            env={"APP_DIR": str(app_dir), "TESTS_DIR": str(TESTS_DIR), "LOG_DIR": str(log_dir)},
            cwd=ROOT,
        )
        reward_path = log_dir / "reward.txt"
        try:
            reward = float(reward_path.read_text(encoding="utf-8").strip())
        except Exception:
            reward = 0.0
        message = (proc.stderr or proc.stdout).strip().splitlines()
        return reward, "\n".join(message[:12])


def evaluate_cluster_state(mask: int) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="tscal-cluster-") as tmp:
        app_dir = Path(tmp) / "app"
        shutil.copytree(APP_TEMPLATE, app_dir)
        applied = []
        if mask != 0:
            apply_oracle(app_dir)
            for bit, cluster in enumerate(CLUSTERS):
                if not (mask & (1 << bit)):
                    CLUSTER_MISSING_MUTATIONS[cluster](app_dir)
                    applied.append(f"missing:{cluster}")
        reward, failure = score_app(app_dir)
        return {
            "mask": f"{mask:0{len(CLUSTERS)}b}",
            "reward": reward,
            "passes": reward == 1.0,
            "mutations": applied,
            "failure_excerpt": "" if reward == 1.0 else "verifier reward 0.0",
        }


def evaluate_wrong_probe(name: str, mutation: Callable[[Path], None]) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="tscal-probe-") as tmp:
        app_dir = Path(tmp) / "app"
        shutil.copytree(APP_TEMPLATE, app_dir)
        apply_oracle(app_dir)
        mutation(app_dir)
        reward, failure = score_app(app_dir)
        return {
            "probe": name,
            "reward": reward,
            "passes": reward == 1.0,
            "failure_excerpt": "" if reward == 1.0 else "verifier reward 0.0",
        }


def build_report() -> dict[str, object]:
    states = [evaluate_cluster_state(mask) for mask in range(1 << len(CLUSTERS))]
    probes = {name: evaluate_wrong_probe(name, mutation) for name, mutation in WRONG_FIX_PROBES.items()}
    passing_masks = [state["mask"] for state in states if state["passes"]]
    return {
        "task": "thermal-stack-calibration",
        "mode": "cluster-audit",
        "clusters": CLUSTERS,
        "states_evaluated": len(states),
        "passing_masks": passing_masks,
        "nop_reward": states[0]["reward"],
        "all_fixed_reward": states[ALL_MASK]["reward"],
        "cluster_states": states,
        "wrong_fix_probe_rewards": {name: item["reward"] for name, item in probes.items()},
        "wrong_fix_probes": probes,
        "passed": report_ok_values(states, probes),
    }


def report_ok_values(states: list[dict[str, object]], probes: dict[str, dict[str, object]]) -> bool:
    expected = 1 << len(CLUSTERS)
    full_mask = "1" * len(CLUSTERS)
    return (
        len(states) == expected
        and [state["mask"] for state in states if state["passes"]] == [full_mask]
        and states[0]["reward"] == 0.0
        and states[ALL_MASK]["reward"] == 1.0
        and all(item["reward"] == 0.0 for item in probes.values())
    )


def report_ok(report: dict[str, object]) -> bool:
    return bool(report.get("passed"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-report", type=Path, help="Write audit report to this path.")
    parser.add_argument(
        "--check-report",
        type=Path,
        nargs="?",
        const=DEFAULT_REPORT,
        help="Recompute and compare with an existing report.",
    )
    args = parser.parse_args()

    report = build_report()
    if args.write_report:
        args.write_report.parent.mkdir(parents=True, exist_ok=True)
        args.write_report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {args.write_report}")
    if args.check_report:
        expected = json.loads(args.check_report.read_text(encoding="utf-8"))
        if report != expected:
            print(f"audit report mismatch: {args.check_report}", file=sys.stderr)
            return 1
        print(f"audit report matches {args.check_report}")

    print(
        f"states={report['states_evaluated']} passing={report['passing_masks']} "
        f"nop={report['nop_reward']} all_fixed={report['all_fixed_reward']} "
        f"wrong_probe_rewards={report['wrong_fix_probe_rewards']}"
    )
    return 0 if report_ok(report) else 1


if __name__ == "__main__":
    raise SystemExit(main())
