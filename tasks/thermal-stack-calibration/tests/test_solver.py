from __future__ import annotations

import copy
import importlib.util
import json
import math
import os
import sys
import unittest
from pathlib import Path
from typing import Any

from fixtures.reference_solver import (
    check_physical_invariants,
    load_cases,
    normalize_case,
    solve_cases,
)

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


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _load_app_models_module():
    app_dir = Path(os.environ["APP_DIR"])
    init_path = app_dir / "thermal_stack" / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        "thermal_stack",
        init_path,
        submodule_search_locations=[str(app_dir / "thermal_stack")],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load app thermal_stack package")
    module = importlib.util.module_from_spec(spec)
    sys.modules.pop("thermal_stack", None)
    sys.modules["thermal_stack"] = module
    spec.loader.exec_module(module)
    from thermal_stack.models import normalize_case_dict  # type: ignore

    return normalize_case_dict


class SolverOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(Path(os.environ["RESULTS_PATH"]).read_text(encoding="utf-8"))
        cls.cases = load_cases(Path(os.environ["HIDDEN_CASES_PATH"]))
        cls.expected = solve_cases(cls.cases)

    def assert_close(self, actual: float, expected: float, label: str, abs_tol: float) -> None:
        self.assertTrue(
            math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=abs_tol),
            f"{label}: actual={actual!r} expected={expected!r}",
        )

    def test_top_level_schema_is_exact(self) -> None:
        self.assertEqual(set(self.payload), {"results"})
        self.assertIsInstance(self.payload["results"], list)
        self.assertEqual(len(self.payload["results"]), len(self.cases))

    def test_result_schema_is_exact(self) -> None:
        for case, result in zip(self.cases, self.payload["results"]):
            with self.subTest(case_id=case["case_id"]):
                self.assertEqual(set(result), RESULT_KEYS)
                self.assertEqual(result["case_id"], case["case_id"])
                self.assertEqual(len(result["x_m"]), int(normalize_case(case)["num_cells"]))
                self.assertEqual(len(result["temperature_c"]), int(normalize_case(case)["num_cells"]))
                self.assertEqual(
                    len(result["interface_diagnostics"]),
                    len(normalize_case(case)["layers"]) - 1,
                )
                prev = -math.inf
                for item in result["interface_diagnostics"]:
                    self.assertEqual(set(item), INTERFACE_KEYS)
                    self.assertGreater(float(item["x_m"]), prev)
                    prev = float(item["x_m"])
                    for key in INTERFACE_KEYS:
                        self.assertTrue(_is_number(item[key]), key)
                for field in (
                    "left_heat_flux_w_m2",
                    "right_heat_flux_w_m2",
                    "max_temperature_c",
                    "energy_residual_w_m2",
                ):
                    self.assertTrue(_is_number(result[field]), field)

    def test_numerical_values_match_reference(self) -> None:
        for result, expected in zip(self.payload["results"], self.expected):
            case_id = expected["case_id"]
            with self.subTest(case_id=case_id):
                for i, (a, b) in enumerate(zip(result["x_m"], expected["x_m"])):
                    self.assert_close(a, b, f"{case_id}.x_m[{i}]", 1e-12)
                for i, (a, b) in enumerate(zip(result["temperature_c"], expected["temperature_c"])):
                    self.assert_close(a, b, f"{case_id}.temperature_c[{i}]", 5e-4)
                for i, (a_item, b_item) in enumerate(
                    zip(result["interface_diagnostics"], expected["interface_diagnostics"])
                ):
                    self.assert_close(a_item["x_m"], b_item["x_m"], f"{case_id}.interface[{i}].x_m", 1e-12)
                    self.assert_close(
                        a_item["heat_flux_w_m2"],
                        b_item["heat_flux_w_m2"],
                        f"{case_id}.interface[{i}].heat_flux_w_m2",
                        1e-3,
                    )
                    self.assert_close(
                        a_item["temperature_left_c"],
                        b_item["temperature_left_c"],
                        f"{case_id}.interface[{i}].temperature_left",
                        5e-4,
                    )
                    self.assert_close(
                        a_item["temperature_right_c"],
                        b_item["temperature_right_c"],
                        f"{case_id}.interface[{i}].temperature_right",
                        5e-4,
                    )
                    self.assert_close(
                        a_item["contact_delta_t_c"],
                        b_item["contact_delta_t_c"],
                        f"{case_id}.interface[{i}].contact_delta",
                        5e-4,
                    )
                for field in ("left_heat_flux_w_m2", "right_heat_flux_w_m2"):
                    self.assert_close(result[field], expected[field], f"{case_id}.{field}", 1e-3)
                self.assert_close(
                    result["max_temperature_c"],
                    expected["max_temperature_c"],
                    f"{case_id}.max_temperature_c",
                    5e-4,
                )
                self.assert_close(
                    result["energy_residual_w_m2"],
                    expected["energy_residual_w_m2"],
                    f"{case_id}.energy_residual_w_m2",
                    1e-7,
                )

    def test_physical_invariants(self) -> None:
        for case, result in zip(self.cases, self.payload["results"]):
            with self.subTest(case_id=case["case_id"]):
                failures = check_physical_invariants(case, result)
                self.assertFalse(failures, "; ".join(failures))

    def test_repeated_cases_are_order_independent(self) -> None:
        by_id = {result["case_id"]: result for result in self.payload["results"]}
        pairs = [
            ("h006_repeat_base_first", "h008_repeat_base_after_regime"),
        ]
        for first, second in pairs:
            with self.subTest(first=first, second=second):
                self.assertIn(first, by_id)
                self.assertIn(second, by_id)
                a = {**by_id[first], "case_id": second}
                self.assertEqual(a, by_id[second])

    def test_normalization_is_idempotent_and_non_mutating(self) -> None:
        # Grade the normalization contract behaviorally: the case-normalization
        # entry point must be idempotent and must not mutate the raw input case.
        # This intentionally does NOT call case_from_dict with a one-argument
        # signature: the baseline tool defines case_from_dict(raw_input, materials)
        # and the instruction never asks solvers to change that signature, so a
        # correct solver that preserves the two-argument call must not be failed
        # here. Behavioral unit/locale generalization is graded by the other tests.
        normalize_case_dict = _load_app_models_module()
        probes = [
            case
            for case in self.cases
            if case["case_id"] in {"h004_decimal_comma_material_case", "h005_kelvin_input_metric_mm"}
        ]
        self.assertTrue(probes)
        for raw in probes:
            with self.subTest(case_id=raw["case_id"]):
                original = copy.deepcopy(raw)
                normalized_once = normalize_case_dict(copy.deepcopy(raw))
                normalized_twice = normalize_case_dict(copy.deepcopy(normalized_once))
                self.assertEqual(normalized_once, normalized_twice)
                self.assertEqual(raw, original)


if __name__ == "__main__":
    unittest.main()
