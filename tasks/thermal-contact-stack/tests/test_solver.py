from __future__ import annotations
import json, math, os, unittest
from pathlib import Path
from typing import Any
from fixtures.reference_solver import load_cases, solve_cases
RESULT_KEYS = {"case_id", "x_m", "temperature_c", "interface_diagnostics", "left_heat_flux_w_m2", "right_heat_flux_w_m2", "max_temperature_c", "energy_residual_w_m2"}
INTERFACE_KEYS = {"x_m", "heat_flux_w_m2", "temperature_left_c", "temperature_right_c", "contact_delta_t_c"}
def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))
class SolverOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(Path(os.environ["RESULTS_PATH"]).read_text(encoding="utf-8"))
        cls.cases = load_cases(Path(os.environ["HIDDEN_CASES_PATH"])); cls.expected = solve_cases(cls.cases)
    def assert_close(self, actual: float, expected: float, label: str, abs_tol: float) -> None:
        self.assertTrue(math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=abs_tol), f"{label}: actual={actual!r} expected={expected!r}")
    def test_top_level_schema_is_exact(self) -> None:
        self.assertEqual(set(self.payload), {"results"}); self.assertIsInstance(self.payload["results"], list); self.assertEqual(len(self.payload["results"]), len(self.cases))
    def test_result_schema_is_exact(self) -> None:
        for case, result in zip(self.cases, self.payload["results"]):
            with self.subTest(case_id=case["case_id"]):
                self.assertEqual(set(result), RESULT_KEYS); self.assertEqual(result["case_id"], case["case_id"])
                self.assertEqual(len(result["x_m"]), int(case["num_cells"])); self.assertEqual(len(result["temperature_c"]), int(case["num_cells"]))
                self.assertEqual(len(result["interface_diagnostics"]), len(case["layers"]) - 1)
                prev = -math.inf
                for item in result["interface_diagnostics"]:
                    self.assertEqual(set(item), INTERFACE_KEYS); self.assertGreater(float(item["x_m"]), prev); prev = float(item["x_m"])
                    for key in INTERFACE_KEYS: self.assertTrue(_is_number(item[key]), key)
                for field in ("left_heat_flux_w_m2", "right_heat_flux_w_m2", "max_temperature_c", "energy_residual_w_m2"):
                    self.assertTrue(_is_number(result[field]), field)
    def test_numerical_values_match_reference(self) -> None:
        for result, expected in zip(self.payload["results"], self.expected):
            case_id = expected["case_id"]
            with self.subTest(case_id=case_id):
                for i, (a, b) in enumerate(zip(result["x_m"], expected["x_m"])): self.assert_close(a, b, f"{case_id}.x_m[{i}]", 1e-12)
                for i, (a, b) in enumerate(zip(result["temperature_c"], expected["temperature_c"])): self.assert_close(a, b, f"{case_id}.temperature_c[{i}]", 5e-4)
                for i, (a_item, b_item) in enumerate(zip(result["interface_diagnostics"], expected["interface_diagnostics"])):
                    self.assert_close(a_item["x_m"], b_item["x_m"], f"{case_id}.interface[{i}].x_m", 1e-12)
                    self.assert_close(a_item["heat_flux_w_m2"], b_item["heat_flux_w_m2"], f"{case_id}.interface[{i}].heat_flux", 1e-2)
                    self.assert_close(a_item["temperature_left_c"], b_item["temperature_left_c"], f"{case_id}.interface[{i}].temperature_left", 5e-4)
                    self.assert_close(a_item["temperature_right_c"], b_item["temperature_right_c"], f"{case_id}.interface[{i}].temperature_right", 5e-4)
                    self.assert_close(a_item["contact_delta_t_c"], b_item["contact_delta_t_c"], f"{case_id}.interface[{i}].contact_delta", 5e-4)
                for field in ("left_heat_flux_w_m2", "right_heat_flux_w_m2"): self.assert_close(result[field], expected[field], f"{case_id}.{field}", 1e-2)
                self.assert_close(result["max_temperature_c"], expected["max_temperature_c"], f"{case_id}.max_temperature_c", 5e-4)
                self.assert_close(result["energy_residual_w_m2"], expected["energy_residual_w_m2"], f"{case_id}.energy_residual_w_m2", 1e-2)
if __name__ == "__main__": unittest.main()
