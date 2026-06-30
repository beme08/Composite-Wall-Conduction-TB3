#!/usr/bin/env python3
"""Reference verifier-time identification program."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np


DT = 0.001
PROBE_SAMPLES = 2000
HANKEL_ROWS = 300
HANKEL_COLS = 300
ORDER_CAP = 12


def call_oracle(oracle: str, u: list[float], dt: float = DT) -> list[float]:
    with tempfile.TemporaryDirectory(prefix="sysid-probe-") as tmp_s:
        tmp = Path(tmp_s)
        inp = tmp / "input.json"
        out = tmp / "output.json"
        inp.write_text(json.dumps({"dt": dt, "u": u}), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, oracle, "--input", str(inp), "--output", str(out)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"oracle failed with {proc.returncode}: {proc.stdout}")
        data = json.loads(out.read_text(encoding="utf-8"))
        return [float(v) for v in data["y"]]


def era_from_markov(markov: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rows = HANKEL_ROWS
    cols = HANKEL_COLS
    if len(markov) < rows + cols + 2:
        raise ValueError("not enough Markov samples")
    h0 = np.empty((rows, cols), dtype=float)
    h1 = np.empty((rows, cols), dtype=float)
    for i in range(rows):
        h0[i, :] = markov[i + 1 : i + 1 + cols]
        h1[i, :] = markov[i + 2 : i + 2 + cols]
    u, s, vh = np.linalg.svd(h0, full_matrices=False)
    if s[0] <= 0.0:
        raise ValueError("degenerate impulse response")
    rank = int(np.sum(s > s[0] * 1e-8))
    rank = max(1, min(rank, ORDER_CAP))
    u_r = u[:, :rank]
    s_r = s[:rank]
    vh_r = vh[:rank, :]
    sqrt_s = np.diag(np.sqrt(s_r))
    inv_sqrt_s = np.diag(1.0 / np.sqrt(s_r))
    a = inv_sqrt_s @ u_r.T @ h1 @ vh_r.T @ inv_sqrt_s
    b = sqrt_s @ vh_r[:, 0:1]
    c = u_r[0:1, :] @ sqrt_s
    d = np.array([[float(markov[0])]], dtype=float)
    return a, b, c, d


def matrix_to_json(value: np.ndarray) -> list[list[float]]:
    return [[float(x) for x in row] for row in value.tolist()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--oracle", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    impulse = [0.0] * PROBE_SAMPLES
    impulse[0] = 1.0
    y = np.array(call_oracle(args.oracle, impulse), dtype=float)
    a, b, c, d = era_from_markov(y)
    eigvals = np.linalg.eigvals(a)
    if np.max(np.abs(eigvals)) >= 1.0:
        raise RuntimeError("identified model is not stable")
    model = {
        "type": "state_space_siso",
        "continuous_time": False,
        "sample_time": DT,
        "model_order": int(a.shape[0]),
        "A": matrix_to_json(a),
        "B": matrix_to_json(b),
        "C": matrix_to_json(c),
        "D": matrix_to_json(d),
    }
    Path(args.output).write_text(json.dumps(model, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
