#!/usr/bin/env python3
"""Case differentiation and 256-state partial-fix audit."""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = ROOT / "tasks" / "thermal-stack-calibration"
APP_TEMPLATE = TASK_DIR / "environment" / "app"
HIDDEN_CASES = TASK_DIR / "tests" / "fixtures" / "hidden_cases.json"
DEFAULT_REPORT = TASK_DIR / "tests" / "fixtures" / "audit_report.json"

sys.path.insert(0, str(TASK_DIR / "tests"))
from fixtures.reference_solver import load_cases, solve_cases  # noqa: E402


DEFECT_CLASSES = [
    "CONTACT_RESISTANCE_OMITTED",
    "CONTACT_TEMPERATURE_CONTINUITY",
    "INTERFACE_CONDUCTANCE",
    "LEFT_BOUNDARY_RESISTANCE",
    "RIGHT_CONVECTION_RESISTANCE",
    "SOURCE_SCALING_SIGN",
    "LAYER_FACE_ASSIGNMENT",
    "FLUX_AND_RESIDUAL",
]

FIXES = {
    "CONTACT_RESISTANCE_OMITTED": (
        "thermal_stack/materials.py",
        """def contact_resistance(r_contact_m2_k_w: float) -> float:
    return 0.0
""",
        """def contact_resistance(r_contact_m2_k_w: float) -> float:
    return r_contact_m2_k_w
""",
    ),
    "CONTACT_TEMPERATURE_CONTINUITY": (
        "thermal_stack/postprocess.py",
        """        continuous_temperature = 0.5 * (t_left + t_right)
        diagnostics.append(
            {
                "x_m": interface.x_m,
                "heat_flux_w_m2": heat_flux,
                "temperature_left_c": continuous_temperature,
                "temperature_right_c": continuous_temperature,
                "contact_delta_t_c": 0.0,
            }
        )
""",
        """        k_left = mesh.k_w_m_k[m - 1]
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
""",
    ),
    "INTERFACE_CONDUCTANCE": (
        "thermal_stack/materials.py",
        """def material_face_resistance(k_left: float, k_right: float, dx_m: float) -> float:
    k_face = 0.5 * (k_left + k_right)
    return dx_m / k_face
""",
        """def material_face_resistance(k_left: float, k_right: float, dx_m: float) -> float:
    return dx_m / (2.0 * k_left) + dx_m / (2.0 * k_right)
""",
    ),
    "LEFT_BOUNDARY_RESISTANCE": (
        "thermal_stack/materials.py",
        """def left_boundary_conductance(k_left_cell: float, dx_m: float) -> float:
    return k_left_cell / dx_m
""",
        """def left_boundary_conductance(k_left_cell: float, dx_m: float) -> float:
    return 2.0 * k_left_cell / dx_m
""",
    ),
    "RIGHT_CONVECTION_RESISTANCE": (
        "thermal_stack/materials.py",
        """def right_boundary_conductance(k_right_cell: float, h_w_m2_k: float, dx_m: float) -> float:
    return h_w_m2_k
""",
        """def right_boundary_conductance(k_right_cell: float, h_w_m2_k: float, dx_m: float) -> float:
    return 1.0 / (dx_m / (2.0 * k_right_cell) + 1.0 / h_w_m2_k)
""",
    ),
    "SOURCE_SCALING_SIGN": (
        "thermal_stack/assembly.py",
        """def source_contribution(q_w_m3: float, dx_m: float) -> float:
    amount = q_w_m3
    return -amount
""",
        """def source_contribution(q_w_m3: float, dx_m: float) -> float:
    return q_w_m3 * dx_m
""",
    ),
    "LAYER_FACE_ASSIGNMENT": (
        "thermal_stack/mesh.py",
        "        x_probe = min((i + 1) * dx_m, case.length_m)\n",
        "        x_probe = (i + 0.5) * dx_m\n",
    ),
    "FLUX_AND_RESIDUAL": (
        "thermal_stack/postprocess.py",
        """    left_flux = g_left * (float(temperatures[0]) - case.t_left_c)
    right_flux = g_right * (case.t_inf_c - float(temperatures[-1]))
    source_total = sum(mesh.q_w_m3)
    residual = left_flux + source_total + right_flux
""",
        """    left_flux = g_left * (case.t_left_c - float(temperatures[0]))
    right_flux = g_right * (float(temperatures[-1]) - case.t_inf_c)
    source_total = sum(q * mesh.dx_m for q in mesh.q_w_m3)
    residual = right_flux - left_flux - source_total
""",
    ),
}

RESULT_KEYS = {
    "case_id",
    "x_m",
    "temperature_c",
    "interface_diagnostics",
    "left_heat_flux_w_m2",
    "right_heat_flux_w_m2",
    "max_temperature_c",
    "energy_residual_w_m2",
}
INTERFACE_KEYS = {
    "x_m",
    "heat_flux_w_m2",
    "temperature_left_c",
    "temperature_right_c",
    "contact_delta_t_c",
}

TOLERANCES = {
    "temperature": 5e-4,
    "interface_temperature": 5e-4,
    "contact_delta_t": 5e-4,
    "flux": 1e-2,
    "energy_residual": 1e-2,
}
FIELD_TOLERANCES = {
    "temperature_c": TOLERANCES["temperature"],
    "max_temperature_c": TOLERANCES["temperature"],
    "interface_diagnostics.temperature_left_c": TOLERANCES["interface_temperature"],
    "interface_diagnostics.temperature_right_c": TOLERANCES["interface_temperature"],
    "interface_diagnostics.contact_delta_t_c": TOLERANCES["contact_delta_t"],
    "interface_diagnostics.heat_flux_w_m2": TOLERANCES["flux"],
    "left_heat_flux_w_m2": TOLERANCES["flux"],
    "right_heat_flux_w_m2": TOLERANCES["flux"],
    "energy_residual_w_m2": TOLERANCES["energy_residual"],
}
REQUIRED_MARGIN = 10.0


def apply_fixes(app_dir: Path, fixed_classes: list[str]) -> None:
    for name in fixed_classes:
        rel_path, old, new = FIXES[name]
        path = app_dir / rel_path
        text = path.read_text(encoding="utf-8")
        if old in text:
            path.write_text(text.replace(old, new, 1), encoding="utf-8")
        elif new in text:
            continue
        else:
            raise RuntimeError(f"could not apply {name}")


def run_variant(fixed_classes: list[str]) -> tuple[int, dict[str, Any] | None, str]:
    with tempfile.TemporaryDirectory(prefix="tscal-audit-") as tmp:
        tmp_path = Path(tmp)
        app_dir = tmp_path / "app"
        shutil.copytree(APP_TEMPLATE, app_dir)
        apply_fixes(app_dir, fixed_classes)
        out = tmp_path / "results.json"
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.run(
            [
                sys.executable,
                str(app_dir / "scripts" / "run_solver.py"),
                "--cases",
                str(HIDDEN_CASES),
                "--output",
                str(out),
            ],
            cwd=tmp_path,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if proc.returncode != 0:
            return proc.returncode, None, proc.stderr or proc.stdout
        try:
            return 0, json.loads(out.read_text(encoding="utf-8")), ""
        except Exception as exc:
            return 1, None, f"invalid json: {exc}"


def close(actual: float, expected: float, tol: float) -> bool:
    return math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=tol)


def compare_results(actual: dict[str, Any], expected: list[dict[str, Any]]) -> str | None:
    if set(actual) != {"results"}:
        return "top-level schema"
    results = actual["results"]
    if not isinstance(results, list) or len(results) != len(expected):
        return "result count"
    for got, exp in zip(results, expected):
        cid = exp["case_id"]
        if set(got) != RESULT_KEYS:
            return f"{cid}.schema"
        if got["case_id"] != cid:
            return "case order/id"
        if len(got["x_m"]) != len(exp["x_m"]):
            return f"{cid}.x_m.length"
        for index, (actual_x, expected_x) in enumerate(zip(got["x_m"], exp["x_m"])):
            if not close(actual_x, expected_x, 1e-12):
                return f"{cid}.x_m[{index}]"
        if len(got["temperature_c"]) != len(exp["temperature_c"]):
            return f"{cid}.temperature_c.length"
        for index, (actual_t, expected_t) in enumerate(zip(got["temperature_c"], exp["temperature_c"])):
            if not close(actual_t, expected_t, TOLERANCES["temperature"]):
                return f"{cid}.temperature_c[{index}]"
        if len(got["interface_diagnostics"]) != len(exp["interface_diagnostics"]):
            return f"{cid}.interface.count"
        for index, (actual_item, expected_item) in enumerate(
            zip(got["interface_diagnostics"], exp["interface_diagnostics"])
        ):
            if set(actual_item) != INTERFACE_KEYS:
                return f"{cid}.interface[{index}].schema"
            if not close(actual_item["x_m"], expected_item["x_m"], 1e-12):
                return f"{cid}.interface[{index}].x_m"
            if not close(actual_item["heat_flux_w_m2"], expected_item["heat_flux_w_m2"], TOLERANCES["flux"]):
                return f"{cid}.interface[{index}].heat_flux_w_m2"
            for field in ("temperature_left_c", "temperature_right_c"):
                if not close(actual_item[field], expected_item[field], TOLERANCES["interface_temperature"]):
                    return f"{cid}.interface[{index}].{field}"
            if not close(
                actual_item["contact_delta_t_c"],
                expected_item["contact_delta_t_c"],
                TOLERANCES["contact_delta_t"],
            ):
                return f"{cid}.interface[{index}].contact_delta_t_c"
        for field in ("left_heat_flux_w_m2", "right_heat_flux_w_m2"):
            if not close(got[field], exp[field], TOLERANCES["flux"]):
                return f"{cid}.{field}"
        if not close(got["max_temperature_c"], exp["max_temperature_c"], TOLERANCES["temperature"]):
            return f"{cid}.max_temperature_c"
        if not close(got["energy_residual_w_m2"], exp["energy_residual_w_m2"], TOLERANCES["energy_residual"]):
            return f"{cid}.energy_residual_w_m2"
    return None


def field_signal_summary(actual_case: dict[str, Any], expected_case: dict[str, Any]) -> dict[str, dict[str, float]]:
    temperature_error = max(
        [abs(float(a) - float(b)) for a, b in zip(actual_case["temperature_c"], expected_case["temperature_c"])],
        default=0.0,
    )
    max_temperature_error = abs(
        float(actual_case["max_temperature_c"]) - float(expected_case["max_temperature_c"])
    )

    interface_left_error = 0.0
    interface_right_error = 0.0
    interface_flux_error = 0.0
    contact_delta_error = 0.0
    for actual_item, expected_item in zip(
        actual_case["interface_diagnostics"],
        expected_case["interface_diagnostics"],
    ):
        interface_left_error = max(
            interface_left_error,
            abs(float(actual_item["temperature_left_c"]) - float(expected_item["temperature_left_c"])),
        )
        interface_right_error = max(
            interface_right_error,
            abs(float(actual_item["temperature_right_c"]) - float(expected_item["temperature_right_c"])),
        )
        contact_delta_error = max(
            contact_delta_error,
            abs(float(actual_item["contact_delta_t_c"]) - float(expected_item["contact_delta_t_c"])),
        )
        interface_flux_error = max(
            interface_flux_error,
            abs(float(actual_item["heat_flux_w_m2"]) - float(expected_item["heat_flux_w_m2"])),
        )

    raw_errors = {
        "temperature_c": temperature_error,
        "max_temperature_c": max_temperature_error,
        "interface_diagnostics.temperature_left_c": interface_left_error,
        "interface_diagnostics.temperature_right_c": interface_right_error,
        "interface_diagnostics.contact_delta_t_c": contact_delta_error,
        "interface_diagnostics.heat_flux_w_m2": interface_flux_error,
        "left_heat_flux_w_m2": abs(
            float(actual_case["left_heat_flux_w_m2"]) - float(expected_case["left_heat_flux_w_m2"])
        ),
        "right_heat_flux_w_m2": abs(
            float(actual_case["right_heat_flux_w_m2"]) - float(expected_case["right_heat_flux_w_m2"])
        ),
        "energy_residual_w_m2": abs(
            float(actual_case["energy_residual_w_m2"]) - float(expected_case["energy_residual_w_m2"])
        ),
    }
    return {
        field: {
            "max_abs_error": error,
            "tolerance": FIELD_TOLERANCES[field],
            "signal_margin_vs_tolerance": error / FIELD_TOLERANCES[field],
        }
        for field, error in raw_errors.items()
    }


def metric_summary(actual_case: dict[str, Any], expected_case: dict[str, Any]) -> dict[str, Any]:
    field_signals = field_signal_summary(actual_case, expected_case)
    temperature_error = max(
        field_signals["temperature_c"]["max_abs_error"],
        field_signals["max_temperature_c"]["max_abs_error"],
    )
    interface_temperature_error = max(
        field_signals["interface_diagnostics.temperature_left_c"]["max_abs_error"],
        field_signals["interface_diagnostics.temperature_right_c"]["max_abs_error"],
    )
    contact_delta_error = field_signals["interface_diagnostics.contact_delta_t_c"]["max_abs_error"]
    flux_error = max(
        field_signals["interface_diagnostics.heat_flux_w_m2"]["max_abs_error"],
        field_signals["left_heat_flux_w_m2"]["max_abs_error"],
        field_signals["right_heat_flux_w_m2"]["max_abs_error"],
    )
    residual_error = abs(
        float(actual_case["energy_residual_w_m2"]) - float(expected_case["energy_residual_w_m2"])
    )
    margins = [item["signal_margin_vs_tolerance"] for item in field_signals.values()]
    return {
        "max_abs_temperature_error": temperature_error,
        "max_abs_interface_temperature_error": interface_temperature_error,
        "max_abs_contact_delta_t_error": contact_delta_error,
        "max_abs_flux_error": flux_error,
        "max_abs_energy_residual_error": residual_error,
        "signal_margin_vs_tolerance": max(margins),
        "field_signals": field_signals,
    }


def strongest_failure_signature(
    actual: dict[str, Any],
    expected: list[dict[str, Any]],
    fallback: str | None,
) -> str | None:
    try:
        results = actual["results"]
        if not isinstance(results, list) or len(results) != len(expected):
            return fallback
        best_signature: str | None = None
        best_margin = -1.0
        for actual_case, expected_case in zip(results, expected):
            if set(actual_case) != RESULT_KEYS or actual_case["case_id"] != expected_case["case_id"]:
                return fallback
            if len(actual_case["temperature_c"]) != len(expected_case["temperature_c"]):
                return fallback
            if len(actual_case["interface_diagnostics"]) != len(expected_case["interface_diagnostics"]):
                return fallback
            field_signals = field_signal_summary(actual_case, expected_case)
            for field, signal in field_signals.items():
                margin = signal["signal_margin_vs_tolerance"]
                if margin > best_margin:
                    best_margin = margin
                    best_signature = f"{expected_case['case_id']}.{field}"
        if best_margin > 0.0:
            return best_signature
    except Exception:
        return fallback
    return fallback


def evaluate_state(mask: int, expected: list[dict[str, Any]]) -> tuple[float, str | None, str | None]:
    fixed = [name for bit, name in enumerate(DEFECT_CLASSES) if mask & (1 << bit)]
    rc, actual, message = run_variant(fixed)
    if rc != 0 or actual is None:
        failure = message or "runner failed"
        return 0.0, failure, failure
    mismatch = compare_results(actual, expected)
    if mismatch is None:
        return 1.0, None, None
    return 0.0, mismatch, strongest_failure_signature(actual, expected, mismatch)


def case_differentiation_report(expected: list[dict[str, Any]]) -> dict[str, Any]:
    expected_by_id = {case["case_id"]: case for case in expected}
    all_fixed = DEFECT_CLASSES[:]
    coverage: dict[str, Any] = {}
    weak_cases: list[dict[str, Any]] = []

    for defect in DEFECT_CLASSES:
        fixed_except_defect = [name for name in all_fixed if name != defect]
        rc, actual, message = run_variant(fixed_except_defect)
        if rc != 0 or actual is None:
            coverage[defect] = {
                "defect_name": defect,
                "target_hidden_cases": [],
                "max_abs_temperature_error": 0.0,
                "max_abs_interface_temperature_error": 0.0,
                "max_abs_contact_delta_t_error": 0.0,
                "max_abs_flux_error": 0.0,
                "max_abs_energy_residual_error": 0.0,
                "verifier_passes_with_defect": False,
                "signal_margin_vs_tolerance": 0.0,
                "detected": False,
                "runner_error": message,
            }
            weak_cases.append(
                {
                    "case_id": None,
                    "defect": defect,
                    "max_signal_margin": 0.0,
                    "required_margin": REQUIRED_MARGIN,
                    "recommendation": "Fix defective variant runner before trusting hidden coverage",
                }
            )
            continue

        verifier_passes = compare_results(actual, expected) is None
        totals = {
            "max_abs_temperature_error": 0.0,
            "max_abs_interface_temperature_error": 0.0,
            "max_abs_contact_delta_t_error": 0.0,
            "max_abs_flux_error": 0.0,
            "max_abs_energy_residual_error": 0.0,
            "signal_margin_vs_tolerance": 0.0,
        }
        detected_cases: list[str] = []
        output_fields: set[str] = set()
        field_signal_margins = {field: 0.0 for field in FIELD_TOLERANCES}
        case_margins: list[dict[str, Any]] = []
        for actual_case in actual["results"]:
            case_id = actual_case["case_id"]
            summary = metric_summary(actual_case, expected_by_id[case_id])
            responsible = sorted(
                field
                for field, signal in summary["field_signals"].items()
                if signal["signal_margin_vs_tolerance"] >= REQUIRED_MARGIN
            )
            case_margins.append(
                {
                    "case_id": case_id,
                    "signal_margin_vs_tolerance": round(summary["signal_margin_vs_tolerance"], 6),
                    "output_fields": responsible,
                }
            )
            if summary["signal_margin_vs_tolerance"] >= REQUIRED_MARGIN:
                detected_cases.append(case_id)
                output_fields.update(responsible)
            for field, signal in summary["field_signals"].items():
                field_signal_margins[field] = max(
                    field_signal_margins[field],
                    signal["signal_margin_vs_tolerance"],
                )
            for key, value in summary.items():
                if key in totals:
                    totals[key] = max(totals[key], value)

        detected = (not verifier_passes) and bool(detected_cases)
        coverage[defect] = {
            "defect_name": defect,
            "target_hidden_cases": detected_cases,
            "detecting_case_ids": detected_cases,
            "output_fields_responsible": sorted(output_fields),
            "field_signal_margins": {
                field: round(margin, 6)
                for field, margin in sorted(field_signal_margins.items())
                if margin >= REQUIRED_MARGIN
            },
            "max_abs_temperature_error": totals["max_abs_temperature_error"],
            "max_abs_interface_temperature_error": totals["max_abs_interface_temperature_error"],
            "max_abs_contact_delta_t_error": totals["max_abs_contact_delta_t_error"],
            "max_abs_flux_error": totals["max_abs_flux_error"],
            "max_abs_energy_residual_error": totals["max_abs_energy_residual_error"],
            "verifier_passes_with_defect": verifier_passes,
            "signal_margin_vs_tolerance": totals["signal_margin_vs_tolerance"],
            "detected": detected,
            "case_signal_margins": sorted(
                case_margins,
                key=lambda item: item["signal_margin_vs_tolerance"],
                reverse=True,
            )[:5],
        }
        if not detected:
            best_case = max(case_margins, key=lambda item: item["signal_margin_vs_tolerance"], default=None)
            weak_cases.append(
                {
                    "case_id": None if best_case is None else best_case["case_id"],
                    "defect": defect,
                    "max_signal_margin": 0.0 if best_case is None else best_case["signal_margin_vs_tolerance"],
                    "required_margin": REQUIRED_MARGIN,
                    "recommendation": "Increase contrast, contact resistance, source strength, or boundary sensitivity for this defect",
                }
            )

    passed = all(item["detected"] for item in coverage.values())
    return {
        "mode": "case-differentiation",
        "passed": passed,
        "tolerance_multiplier_required": REQUIRED_MARGIN,
        "defect_coverage": coverage,
        "weak_cases": weak_cases,
        "redesign_required": not passed,
    }


def build_report() -> dict[str, Any]:
    cases = load_cases(HIDDEN_CASES)
    expected = solve_cases(cases)
    all_mask = (1 << len(DEFECT_CLASSES)) - 1
    passing_masks: list[str] = []
    failure_signatures: dict[str, int] = {}
    single_fix_rewards: dict[str, float] = {}
    all_but_one_rewards: dict[str, float] = {}
    single_fix_failure_signatures: dict[str, str | None] = {}
    all_but_one_failure_signatures: dict[str, str | None] = {}
    nop_reward = 0.0
    all_fixed_reward = 0.0

    for mask in range(1 << len(DEFECT_CLASSES)):
        reward, mismatch, signature = evaluate_state(mask, expected)
        if mask == 0:
            nop_reward = reward
        if mask == all_mask:
            all_fixed_reward = reward
        if mask != 0 and mask & (mask - 1) == 0:
            defect = DEFECT_CLASSES[int(math.log2(mask))]
            single_fix_rewards[defect] = reward
            single_fix_failure_signatures[defect] = signature or mismatch
        missing = all_mask ^ mask
        if missing and missing & (missing - 1) == 0:
            defect = DEFECT_CLASSES[int(math.log2(missing))]
            all_but_one_rewards[defect] = reward
            all_but_one_failure_signatures[defect] = signature or mismatch
        if reward == 1.0:
            passing_masks.append(f"0x{mask:02x}")
        else:
            key = signature or mismatch or "unknown mismatch"
            failure_signatures[key] = failure_signatures.get(key, 0) + 1

    case_report = case_differentiation_report(expected)
    return {
        "task": "thermal-stack-calibration",
        "defect_classes": DEFECT_CLASSES,
        "states_evaluated": 1 << len(DEFECT_CLASSES),
        "passing_masks": passing_masks,
        "nop_reward": nop_reward,
        "all_fixed_reward": all_fixed_reward,
        "single_fix_rewards": single_fix_rewards,
        "all_but_one_rewards": all_but_one_rewards,
        "single_fix_failure_signatures": single_fix_failure_signatures,
        "all_but_one_failure_signatures": all_but_one_failure_signatures,
        "case_differentiation": case_report,
        "failure_signature_mode": "strongest_output_field_signal_margin",
        "failure_signature_counts": dict(sorted(failure_signatures.items())),
    }


def report_ok(report: dict[str, Any]) -> bool:
    return (
        report["states_evaluated"] == 256
        and report["passing_masks"] == ["0xff"]
        and report["nop_reward"] == 0.0
        and report["all_fixed_reward"] == 1.0
        and all(value == 0.0 for value in report["single_fix_rewards"].values())
        and all(value == 0.0 for value in report["all_but_one_rewards"].values())
        and report["case_differentiation"]["passed"] is True
        and report["case_differentiation"]["redesign_required"] is False
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-report", type=Path, help="Write compact audit report to this path.")
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

    case_report = report["case_differentiation"]
    print(
        f"states={report['states_evaluated']} passing={report['passing_masks']} "
        f"nop={report['nop_reward']} all_fixed={report['all_fixed_reward']} "
        f"case_diff={case_report['passed']} margin_required={case_report['tolerance_multiplier_required']}"
    )
    return 0 if report_ok(report) else 1


if __name__ == "__main__":
    raise SystemExit(main())
