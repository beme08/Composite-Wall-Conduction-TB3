from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any

import numpy as np
from scipy.linalg import expm


TASK_DIR = Path(__file__).resolve().parents[1]
APP_TEMPLATE = TASK_DIR / "environment" / "app"
APP_DIR = Path(os.environ.get("APP_DIR", "/app"))
REPORT_PATH = Path(os.environ.get("SYSID_REPORT_PATH", "/tmp/hidden_resonance_sysid_report.json"))
PROBE_CORE = Path("/usr/local/lib/sysid_probe_core")
TRUTH_CORE = Path("/usr/local/lib/sysid_truth_core")
DT = 0.001
TP = 2.0
TE = 6.0
MODEL_ORDER_CAP = 12
REL_MSE_THRESHOLD = 1e-6
INSTANCE_COUNT = 3
NOBODY_UID = 65534
NOBODY_GID = 65534


def _write(path: Path, text: str, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def prepare_app(tmp: Path) -> tuple[Path, bool]:
    if (APP_DIR / "solution").exists() and (APP_DIR / "scripts").exists():
        app = APP_DIR
        mounted = True
    else:
        app = tmp / "app"
        shutil.copytree(APP_TEMPLATE, app)
        mounted = False
    (app / "solution").mkdir(parents=True, exist_ok=True)
    (app / "scripts").mkdir(parents=True, exist_ok=True)
    for directory in (app / "solution", app / "scripts"):
        try:
            directory.chmod(0o777)
        except PermissionError:
            pass
    for path in (app / "solution").glob("*"):
        try:
            if path.is_file():
                path.chmod(path.stat().st_mode | stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH | stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
        except PermissionError:
            pass
    return app, mounted


def lock_down_tests_tree() -> None:
    tests_root = Path("/tests")
    if os.geteuid() != 0 or not tests_root.exists():
        return
    for root, dirs, files in os.walk(tests_root):
        for name in dirs:
            try:
                (Path(root) / name).chmod(0o700)
            except OSError:
                pass
        for name in files:
            try:
                (Path(root) / name).chmod(0o600)
            except OSError:
                pass
    try:
        tests_root.chmod(0o700)
    except OSError:
        pass


def install_probe_wrapper(app: Path, instance_idx: int) -> None:
    trusted_dir = app / ".trusted_oracle"
    trusted_dir.mkdir(parents=True, exist_ok=True)
    try:
        trusted_dir.chmod(0o755)
    except OSError:
        pass
    wrapper = f"""#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess

CORE = {str(PROBE_CORE)!r}
INSTANCE = {instance_idx}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    return subprocess.run([CORE, str(INSTANCE), args.input, args.output]).returncode


if __name__ == "__main__":
    raise SystemExit(main())
"""
    _write(app / "scripts" / "simulate.py", wrapper, executable=True)


def demote_to_nobody() -> None:
    if os.geteuid() != 0:
        return
    try:
        os.setgroups([])
    except OSError:
        pass
    os.setgid(NOBODY_GID)
    os.setuid(NOBODY_UID)


def run_fit(app: Path, timeout_sec: float = 45.0) -> dict[str, Any]:
    model_path = app / "solution" / "model.json"
    if model_path.exists():
        model_path.unlink()
    cmd = [
        sys.executable,
        str(app / "solution" / "fit.py"),
        "--oracle",
        str(app / "scripts" / "simulate.py"),
        "--output",
        str(model_path),
    ]
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "PYTHONUNBUFFERED": "1",
        "HOME": "/tmp",
    }
    proc = subprocess.Popen(
        cmd,
        cwd=app,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
        preexec_fn=demote_to_nobody if os.geteuid() == 0 else None,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_sec)
        return {
            "timed_out": False,
            "returncode": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "model_path": str(model_path),
        }
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        stdout, stderr = proc.communicate()
        return {
            "timed_out": True,
            "returncode": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "model_path": str(model_path),
        }


def _matrix(value: Any, rows: int | None = None, cols: int | None = None) -> np.ndarray:
    if not isinstance(value, list) or not value or not all(isinstance(row, list) for row in value):
        raise ValueError("matrix must be a non-empty list of lists")
    lengths = {len(row) for row in value}
    if len(lengths) != 1 or next(iter(lengths)) == 0:
        raise ValueError("ragged or empty matrix")
    arr = np.array(value, dtype=float)
    if arr.ndim != 2 or not np.all(np.isfinite(arr)):
        raise ValueError("matrix values must be finite")
    if rows is not None and arr.shape[0] != rows:
        raise ValueError("matrix row count mismatch")
    if cols is not None and arr.shape[1] != cols:
        raise ValueError("matrix column count mismatch")
    return arr


def validate_model(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = {"type", "continuous_time", "sample_time", "model_order", "A", "B", "C", "D"}
    if set(payload) != expected:
        raise ValueError(f"unsupported model fields: {sorted(set(payload) ^ expected)}")
    if payload["type"] != "state_space_siso":
        raise ValueError("unsupported model type")
    if not isinstance(payload["continuous_time"], bool):
        raise ValueError("continuous_time must be boolean")
    if not isinstance(payload["model_order"], int) or not (1 <= payload["model_order"] <= MODEL_ORDER_CAP):
        raise ValueError("model_order outside cap")
    n = payload["model_order"]
    sample_time = float(payload["sample_time"])
    if not math.isfinite(sample_time) or sample_time <= 0.0:
        raise ValueError("sample_time must be positive finite")
    a = _matrix(payload["A"], n, n)
    b = _matrix(payload["B"], n, 1)
    c = _matrix(payload["C"], 1, n)
    d = _matrix(payload["D"], 1, 1)
    eigvals = np.linalg.eigvals(a)
    if payload["continuous_time"]:
        if np.max(np.real(eigvals)) >= -1e-12:
            raise ValueError("continuous-time model must be stable")
        ad, bd = discretize_continuous(a, b, DT)
    else:
        if abs(sample_time - DT) > 1e-12:
            raise ValueError("discrete model sample_time must be 0.001")
        if np.max(np.abs(eigvals)) >= 1.0:
            raise ValueError("discrete-time model must be stable")
        ad, bd = a, b
    return {
        "raw": payload,
        "A": a,
        "B": b,
        "C": c,
        "D": d,
        "Ad": ad,
        "Bd": bd,
        "sample_time": sample_time,
        "continuous_time": payload["continuous_time"],
    }


def discretize_continuous(a: np.ndarray, b: np.ndarray, dt: float) -> tuple[np.ndarray, np.ndarray]:
    n = a.shape[0]
    block = np.zeros((n + 1, n + 1), dtype=float)
    block[:n, :n] = a
    block[:n, n : n + 1] = b
    exp_block = expm(block * dt)
    return exp_block[:n, :n], exp_block[:n, n : n + 1]


def simulate_model(model: dict[str, Any], u: np.ndarray) -> np.ndarray:
    a = model["Ad"]
    b = model["Bd"]
    c = model["C"]
    d = model["D"]
    x = np.zeros((a.shape[0], 1), dtype=float)
    y = np.empty(len(u), dtype=float)
    for i, value in enumerate(u):
        u_arr = np.array([[float(value)]], dtype=float)
        y[i] = float((c @ x + d @ u_arr)[0, 0])
        x = a @ x + b @ u_arr
    return y


def oracle_response(core: Path, instance_idx: int, u: np.ndarray, dt: float = DT) -> np.ndarray:
    with tempfile.TemporaryDirectory(prefix="sysid-truth-") as tmp_s:
        tmp = Path(tmp_s)
        inp = tmp / "input.json"
        out = tmp / "output.json"
        inp.write_text(json.dumps({"dt": dt, "u": [float(v) for v in u]}), encoding="utf-8")
        proc = subprocess.run(
            [str(core), str(instance_idx), str(inp), str(out)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"oracle failed with {proc.returncode}: {proc.stdout}")
        data = json.loads(out.read_text(encoding="utf-8"))
        return np.array(data["y"], dtype=float)


def hidden_eval_inputs(instance_idx: int) -> list[np.ndarray]:
    n = int(TE / DT)
    rng = np.random.default_rng(20260700 + instance_idx)
    pulse = np.zeros(n, dtype=float)
    pulse[0] = 1.0
    pulse[700] = 0.55
    pulse[1200] = -0.35
    burst = np.zeros(n, dtype=float)
    t = np.arange(n) * DT
    mask = t < 1.65
    burst[mask] = 0.45 * np.sin(2 * np.pi * 8.0 * t[mask]) + 0.35 * np.sin(2 * np.pi * 17.0 * t[mask])
    burst = np.clip(burst, -0.95, 0.95)
    prbs = np.zeros(n, dtype=float)
    signs = rng.choice([-0.6, 0.6], size=180)
    for i, value in enumerate(signs):
        start = i * 10
        stop = min(start + 10, int(1.8 / DT))
        prbs[start:stop] = value
    return [pulse, burst, prbs]


def rel_mse(yhat: np.ndarray, ytrue: np.ndarray) -> float:
    start = int(TP / DT)
    diff = yhat[start:] - ytrue[start:]
    denom = float(np.mean(ytrue[start:] ** 2))
    return float(np.mean(diff**2) / max(denom, 1e-30))


def schema_negative_checks(tmp: Path) -> dict[str, Any]:
    base = {
        "type": "state_space_siso",
        "continuous_time": False,
        "sample_time": DT,
        "model_order": 1,
        "A": [[0.9]],
        "B": [[1.0]],
        "C": [[1.0]],
        "D": [[0.0]],
    }
    cases: dict[str, dict[str, Any]] = {}
    extra = dict(base)
    extra["callable"] = "print('no')"
    cases["extra_unsupported_field"] = extra
    too_big = dict(base)
    too_big["model_order"] = MODEL_ORDER_CAP + 1
    too_big["A"] = [[0.0 for _ in range(MODEL_ORDER_CAP + 1)] for _ in range(MODEL_ORDER_CAP + 1)]
    too_big["B"] = [[0.0] for _ in range(MODEL_ORDER_CAP + 1)]
    too_big["C"] = [[0.0 for _ in range(MODEL_ORDER_CAP + 1)]]
    cases["order_above_cap"] = too_big
    nan_case = dict(base)
    nan_case["A"] = [[float("nan")]]
    cases["nan"] = nan_case
    unstable = dict(base)
    unstable["A"] = [[1.01]]
    cases["unstable"] = unstable
    malformed = dict(base)
    malformed["B"] = [[1.0, 2.0]]
    cases["malformed_shape"] = malformed
    rejected = []
    for name, payload in cases.items():
        path = tmp / f"{name}.json"
        path.write_text(json.dumps(payload, allow_nan=True), encoding="utf-8")
        with unittest.TestCase().assertRaises(Exception):
            validate_model(path)
        rejected.append(name)
    valid_path = tmp / "valid_model.json"
    valid_path.write_text(json.dumps(base), encoding="utf-8")
    validate_model(valid_path)
    return {"valid_accepts": True, "rejected": sorted(rejected)}


class HiddenResonanceSysidTests(unittest.TestCase):
    def test_verifier_owned_sysid(self) -> None:
        report: dict[str, Any] = {
            "task": "hidden-resonance-sysid",
            "instances": [],
            "threshold": REL_MSE_THRESHOLD,
        }
        with tempfile.TemporaryDirectory(prefix="hidden-resonance-sysid-") as tmp_s:
            tmp = Path(tmp_s)
            app, mounted = prepare_app(tmp)
            report["app_under_test"] = {"path": str(app), "uses_mounted_app": mounted}
            self.assertTrue(PROBE_CORE.exists(), PROBE_CORE)
            self.assertTrue(TRUTH_CORE.exists(), TRUTH_CORE)
            if os.geteuid() == 0:
                self.assertFalse(bool(TRUTH_CORE.stat().st_mode & stat.S_IXOTH))
            lock_down_tests_tree()

            # Contract check: the public probe oracle refuses the scored tail horizon.
            install_probe_wrapper(app, 0)
            too_long = np.zeros(int(TP / DT) + 2, dtype=float)
            with tempfile.TemporaryDirectory(prefix="sysid-horizon-") as htmp_s:
                htmp = Path(htmp_s)
                inp = htmp / "input.json"
                out = htmp / "output.json"
                inp.write_text(json.dumps({"dt": DT, "u": [float(v) for v in too_long]}), encoding="utf-8")
                reject = subprocess.run(
                    [sys.executable, str(app / "scripts" / "simulate.py"), "--input", str(inp), "--output", str(out)],
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
                self.assertNotEqual(reject.returncode, 0, reject.stdout)
                report["horizon_rejection_rc"] = reject.returncode

            for instance_idx in range(INSTANCE_COUNT):
                install_probe_wrapper(app, instance_idx)
                fit_result = run_fit(app)
                self.assertFalse(fit_result["timed_out"], fit_result)
                self.assertEqual(fit_result["returncode"], 0, fit_result)
                model = validate_model(Path(fit_result["model_path"]))
                errors = []
                tail_rms = []
                for u in hidden_eval_inputs(instance_idx):
                    ytrue = oracle_response(TRUTH_CORE, instance_idx, u)
                    yhat = simulate_model(model, u)
                    errors.append(rel_mse(yhat, ytrue))
                    tail_rms.append(float(np.sqrt(np.mean(ytrue[int(TP / DT) :] ** 2))))
                max_error = max(errors)
                self.assertLessEqual(max_error, REL_MSE_THRESHOLD, {"instance": instance_idx, "errors": errors})
                report["instances"].append(
                    {
                        "instance": instance_idx,
                        "fit_returncode": fit_result["returncode"],
                        "model_order": model["raw"]["model_order"],
                        "max_rel_mse": max_error,
                        "rel_mse": errors,
                        "tail_rms": tail_rms,
                    }
                )

            report["schema"] = schema_negative_checks(tmp)
            REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
